"""Read-only ON-003 receipts -> reproducible tables/figures/coverage inventory."""
import csv
import cmath
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/validation/cleaned_interfaces/ON-003'


def main():
    manifest=json.loads((OUT/'manifest.json').read_text()); receipts=[]
    for xi in (1,2,4,8):
        p=OUT/f'stage_A_xi{xi}/receipt.json'
        if p.exists():
            d=json.loads(p.read_text()); assert d['xi_over_kstar']==xi and len(d['rows'])==192
            assert d['manifest_sha256']==hashlib.sha256((OUT/'manifest.json').read_bytes()).hexdigest()
            # Rebuild every reported diagonal error from retained arrays.
            import numpy as np
            wave_order=json.loads((p.parent/'near_and_flat_controls.json').read_text())['wave_order']
            indices={label:i for i,label in enumerate(wave_order)}
            for grid in (128,256):
                with np.load(p.parent/f'grid{grid}_arrays.npz') as saved:
                    modes=saved['modes']; spectra={key:saved[key] for key in saved.files if key.startswith(('far_','near_','exact_'))}
                    for row in (r for r in d['rows'] if r['grid']==grid):
                        o,i=indices[row['exterior']],indices[row['interior']]
                        j={'V':0,'K':1,'Kprime':1,'T':2}[row['block']]
                        use=abs(modes)<=row['trace_cutoff']
                        candidate=spectra[f'near_{o}']+spectra[f'far_{o}']-spectra[f'near_{i}']-spectra[f'far_{i}']
                        reference=spectra[f'exact_{o}']-spectra[f'exact_{i}']
                        error=float(np.max(abs(candidate[j,use]-reference[j,use])))
                        assert np.isclose(error,row['absolute_max_error'],rtol=1e-12,atol=1e-14)
            receipts.append(d)
    summary=[]; flat=[]; near=[]; timing=[]
    for d in receipts:
        xi=d['xi_over_kstar']
        for grid in (128,256):
            for cutoff in (64,128):
                rows=[r for r in d['rows'] if r['grid']==grid and r['trace_cutoff']==cutoff]
                row=dict(xi_over_kstar=xi,grid=grid,trace_cutoff=cutoff)
                for block in ('V','K','Kprime','T'):
                    worst=max((r for r in rows if r['block']==block),key=lambda r:r['normalized_max_diagonal_error'])
                    row[block+'_error_over_scale']=worst['normalized_max_diagonal_error']
                row['all_diagonal_controls_passed']=all(row[b+'_error_over_scale']<=1e-7 for b in ('V','K','Kprime','T'))
                summary.append(row)
        for r in d['near_controls']: near.append(dict(xi_over_kstar=xi,**r))
        for r in d['flat']:
            k=complex(*r['k']); omega=r['omega']; S=complex(*r['near'])
            if r['grazing']: full=F=None; amp=None
            else:
                z=omega*omega-k*k
                # Explicit outgoing limiting-absorption side for real k.
                if k.imag==0: z=complex(z.real,-0.)
                root=cmath.sqrt(z); full=1/(2*root); F=full-S
                amp=(abs(S)+abs(F))/abs(full)
            flat.append(dict(xi_over_kstar=xi,k_real=k.real,k_imag=k.imag,omega=omega,near_real=S.real,near_imag=S.imag,full_real=full.real if full is not None else None,full_imag=full.imag if full is not None else None,far_real=F.real if F is not None else None,far_imag=F.imag if F is not None else None,cancellation_amplification=amp,independent_near_absolute_error=r['independent_absolute_error'],grazing_near_only=r['grazing']))
        for g in d['grids']:
            timing.append(dict(xi_over_kstar=xi,grid=g['grid'],complete_control_process_seconds=d['seconds'],circle_diagonal_map_setup_seconds=g['map_setup_seconds'],all_media_radial_512_seconds=sum(r['seconds'] for r in g['far_quadrature']),persistent_circle_diagonal_maps_bytes=g['persistent_diagonal_control_maps_bytes'],max_radial_workspace_bytes=max(r['transient_workspace_bytes'] for r in g['far_quadrature']),radial_256_512_multiplier_difference=max(r['multiplier_max_difference'] for r in g['far_quadrature']),L_m=g['L_m'],q_spacing_per_m=g['far_quadrature'][0]['q_spacing_per_m'],q_max_axis_per_m=g['far_quadrature'][0]['q_max_axis_per_m']))
    for name,rows in [('operator_summary',summary),('flat_cancellation',flat),('near_controls',near),('control_costs',timing)]:
        if rows:
            with (OUT/f'{name}.csv').open('w') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    inventory=[]
    for state in manifest['states']:
        for contrast in (.5,4.,13.3):
            for frequency in (.25e9,2.5e9):
                for kind in ('real','damped'):
                    inventory.append(dict(state=state['id'],contrast=contrast,frequency_hz=frequency,kind=kind,trace_cutoffs=[64,128],circle_diagonal_control='executed' if state['id']=='start' and len(receipts)==4 else 'unrun',full_block_basis_and_complex_actions='unrun',full_24_pair_fields='unrun',field_jacobian='unrun_conditional_forward_not_qualified',complete_service_timing='unrun'))
    (OUT/'coverage.json').write_text(json.dumps(inventory,indent=2)+'\n')
    lines=['# ON-003 circle diagonal control summary','','Necessary screens only; full fields and curved states are unrun.','', '| xi/k_star | grid | cutoff | V / scale | K / scale | T / scale |','|---:|---:|---:|---:|---:|---:|']
    lines.extend(f'| {r["xi_over_kstar"]} | {r["grid"]} | {r["trace_cutoff"]} | {r["V_error_over_scale"]:.3g} | {r["K_error_over_scale"]:.3g} | {r["T_error_over_scale"]:.3g} |' for r in summary)
    (OUT/'table.md').write_text('\n'.join(lines)+'\n')
    if receipts:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,3,figsize=(11.5,3.8),constrained_layout=True)
        for ax,block in zip(axes,('V','K','T')):
            for grid,marker in ((128,'o'),(256,'s')):
                rr=[r for r in summary if r['grid']==grid and r['trace_cutoff']==128]
                ax.plot([r['xi_over_kstar'] for r in rr],[r[block+'_error_over_scale'] for r in rr],marker=marker,label=f'{grid}² grid')
            ax.axhline(1e-7,color='gray',linestyle='--',label='circle control gate')
            ax.set_xscale('log',base=2);ax.set_yscale('log');ax.set_xticks([1,2,4,8],['1','2','4','8']);ax.set_xlabel('xi / k_star');ax.set_title(block+' diagonal control');ax.grid(alpha=.25)
        axes[0].set_ylabel('Worst absolute error / reference block scale');axes[-1].legend(fontsize=8)
        fig.suptitle('ON-003: complete-near circle control, trace cutoff 128')
        fig.savefig(OUT/'operator_errors.png',dpi=180);plt.close(fig)
    (OUT/'summary.json').write_text(json.dumps(dict(split_choices_executed=len(receipts),diagonal_rows=sum(len(d['rows']) for d in receipts),full_forward_configurations_qualified=0,any_circle_diagonal_control_pass=any(r['all_diagonal_controls_passed'] for r in summary),total_control_seconds=sum(d['seconds'] for d in receipts)),indent=2)+'\n')
    print('Validated',len(receipts),'split receipts;',len(inventory),'fixed configurations inventoried')


if __name__=='__main__':main()
