"""Read-back audit and figures for MA-006; no forward or inverse runs."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def rel(a, b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b), 1e-300))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sufficient(rows, arm, inverse):
    def passed(row):
        v = row['arms'][arm]
        return (v['data_error'] <= 1e-3 and v['jacobian_error'] <= 1e-3 and
                (not inverse or (v['gradient_error'] <= 1e-2 and v['step_error'] <= 1e-2)))
    result = None
    for row in reversed(rows):
        if not passed(row):
            break
        result = row['cutoff']
    return result


def audit(folder, records):
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((folder/'manifest.json').read_text())
    differences = [p for group in ('sources','inputs') for p,h in manifest[group].items()
                   if sha(root/p) != h]
    if differences:
        raise AssertionError('Source/input digest mismatch: '+str(differences))
    worst = dict(stored_metric=0., modal_residual=0., data_readout=0., jacobian_contraction=0.)
    count=0
    for d in records:
        path=folder/d['id']/'atlas.npz'
        assert sha(path)==d['artifact_sha256']
        with np.load(path) as z:
            a,b,r,x = z['A'],z['B'],z['R'],z['trace_coefficients']
            n=d['nodes']; sources=len(z['sources'])
            y,j,observed=z['y_reference'],z['J_reference'],z['diagnostic_observed']
            physical=np.concatenate([np.fft.ifft(block,axis=0,norm='ortho') for block in np.split(x,2)]) / z['flux_scale'][:,None]
            reconstructed_j = ((physical[:n,:sources]*physical[:n,sources:]*z['weights'][:,None]).T @ z['h']) * ((d['contrast']-1)*d['k']**2)
            worst['modal_residual']=max(worst['modal_residual'],rel(a@x,b))
            worst['data_readout']=max(worst['data_readout'],rel(np.diag(r@x[:,:sources]),y))
            worst['jacobian_contraction']=max(worst['jacobian_contraction'],rel(reconstructed_j,j))
            for column in z['selected_columns']:
                assert z[f'dA_{column}'].shape==a.shape
                assert z[f'dB_{column}'].shape==b.shape
                assert z[f'dR_{column}'].shape==r.shape
            for row in d['rows']:
                k=row['cutoff']
                for arm,values in row['arms'].items():
                    ya,ja=z[f'{arm}_y_K{k}'],z[f'{arm}_J_K{k}']
                    scale=np.linalg.norm(y)
                    gradient=np.real((ja/scale).conj().T @ ((ya-observed)/scale))
                    step=np.linalg.solve(np.real((ja/scale).conj().T @ (ja/scale))+float(z['ridge'])*np.eye(ja.shape[1]),-gradient)
                    computed=dict(data_error=rel(ya,y),jacobian_error=rel(ja,j),
                                  gradient_error=rel(gradient,z['diagnostic_gradient']),step_error=rel(step,z['diagnostic_step']),
                                  worst_column_scaled=float(np.max(np.linalg.norm(ja-j,axis=0))/np.max(np.linalg.norm(j,axis=0))))
                    for key,value in computed.items():
                        worst['stored_metric']=max(worst['stored_metric'],abs(value-values[key])/max(1.,abs(value)))
                    count+=1
            passed=all(d['qualification'][key]<=limit for key,limit in d['qualification_limits'].items())
            assert passed==d['qualified']
            for arm in ('projection','reduced'):
                for key,inverse in [('data_jacobian',False),('local_update',True)]:
                    expect=sufficient(d['rows'],arm,inverse) if passed else None
                    assert expect==d['cutoffs'][arm][key]
    assert max(worst.values())<1e-9,worst
    index=json.loads((folder/'index.json').read_text())
    assert index['qualified']==sum(d['qualified'] for d in records)
    assert index['artifact_bytes']==sum(d['artifact_bytes'] for d in records)
    result=dict(passed=True,cells=len(records),arm_rows=count,source_hashes=len(manifest['sources']),
                input_hashes=len(manifest['inputs']),worst=worst,
                report_source_sha256=sha(Path(__file__)),
                metrics_sha256={d['id']:sha(folder/d['id']/'metrics.json') for d in records},
                note='Recomputes saved metrics, qualifications, cutoff choices, reference contraction and readout; no campaign rerun.')
    (folder/'readback_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def matrix_figure(folder, key, filename, label):
    names=['circle_c13.3_f2.5','star_c13.3_f2.5','c_c13.3_f2.5']
    fig,axes=plt.subplots(4,3,figsize=(11,12),layout='constrained')
    block_labels=['Dirichlet → equation 1','Flux → equation 1','Dirichlet → equation 2','Flux → equation 2']
    for column,name in enumerate(names):
        with np.load(folder/name/'atlas.npz') as z:
            n=len(z['modes']); matrix=z[key]
            idx=np.array([int(np.nonzero(z['modes']==m)[0][0]) for m in range(-64,65)])
            for block,(i,j) in enumerate([(0,0),(0,1),(1,0),(1,1)]):
                values=np.abs(matrix[np.ix_(idx+i*n,idx+j*n)])
                values=np.log10(np.maximum(values/max(values.max(),1e-300),1e-12))
                ax=axes[block,column]
                im=ax.imshow(values,origin='lower',extent=(-64.5,64.5,-64.5,64.5),vmin=-12,vmax=0,cmap='magma',aspect='equal')
                if block==0:ax.set_title(['Circle','Star','C'][column])
                if column==0:ax.set_ylabel(block_labels[block]+'\nEquation order i')
                if block==3:ax.set_xlabel('Trace order j')
    fig.colorbar(im,ax=axes,label='log10 magnitude / maximum in displayed block',shrink=.75)
    fig.suptitle(label+' · contrast 13.3 · 2.5 GHz\nStored-parameter flux basis; each block scaled separately',fontsize=13)
    fig.savefig(folder/filename,dpi=160)
    plt.close(fig)


def errors_figure(folder, records):
    names=['star_c13.3_f2.5','c_c13.3_f2.5','star_D_c13.3_f2.5']
    lookup={d['id']:d for d in records}
    fig,axes=plt.subplots(3,3,figsize=(12,9),sharex=True,layout='constrained')
    styles=dict(projection=('#2879b9','--'),reduced=('#c2442d','-'),schur=('#36835b',':'))
    for col,name in enumerate(names):
        d=lookup[name]
        for row,(metric,threshold,label) in enumerate([('data_error',1e-3,'Relative data error'),('jacobian_error',1e-3,'Relative Jacobian error'),('step_error',1e-2,'Relative local-step error')]):
            ax=axes[row,col]
            for arm,(color,style) in styles.items():
                ax.semilogy([r['cutoff'] for r in d['rows']], [max(1e-14,r['arms'][arm][metric]) for r in d['rows']],style,color=color,marker='.',label=arm)
            ax.axhline(threshold,color='.4',lw=1,ls='--')
            ax.grid(alpha=.15);ax.set_ylim(1e-14,1e3)
            if col==0:ax.set_ylabel(label)
            if row==0:ax.set_title(['Star truth','C truth','MA-004 star endpoint'][col])
            if row==2:ax.set_xlabel('Trace cutoff $K_u$')
    axes[0,0].legend(loc='lower left',fontsize=8)
    fig.suptitle('Projection accuracy does not certify a reduced solve\nContrast 13.3 · 2.5 GHz · shape band P=12 · fixed 1% synthetic residual',fontsize=13)
    fig.savefig(folder/'cutoff_errors.png',dpi=170)
    plt.close(fig)


def report(folder):
    index=json.loads((folder/'index.json').read_text())
    records=[json.loads((folder/name/'metrics.json').read_text()) for name in index['cells']]
    checked=audit(folder,records)
    matrix_figure(folder,'A','operator_blocks.png','Modal Müller matrix A')
    matrix_figure(folder,'dA_11','operator_derivative_blocks.png','Modal Müller derivative D_cos6 A')
    errors_figure(folder,records)
    lines=['# MA-006 evidence — modal operators and trace cutoff','',
           'Ten fixed cells; nine qualify. This is a projected-Nyström modal atlas in the stored curve parameter, with flux unknowns and a unitary DFT. It is not a coefficient-native assembler or a deployed adaptive solver.','',
           '[Contract](../../../../docs/iterations/modal_atlas/iteration_06/03_plan.md) · [Interpretation](../../../../docs/iterations/modal_atlas/iteration_07/01_results.md)','',
           'The frozen contract records status at launch. `index.json` and the interpretation record completion.','',
           '## Smallest sufficient tested cutoff','',
           'Data/J requires both relative errors ≤ 1e-3. The local-update gate additionally requires gradient and fixed-ridge step errors ≤ 1e-2. Every larger tested cutoff must also pass. Shape directions extend only through P=12. These are ladder values, not exact minimal cutoffs.','',
           '| Cell | Qualified | Projection: data/J | Reduced: data/J | Projection: local update | Reduced: local update |','|---|---|---:|---:|---:|---:|']
    for d in records:
        p,r=d['cutoffs']['projection'],d['cutoffs']['reduced']
        values=[p['data_jacobian'],r['data_jacobian'],p['local_update'],r['local_update']]
        lines.append('| '+d['id']+' | '+str(d['qualified'])+' | '+' | '.join('—' if v is None else str(v) for v in values)+' |')
    lines += ['', '![Cutoff errors](cutoff_errors.png)','',
              '## Persistent atlas','',
              'Each `<cell>/atlas.npz` contains the full complex 1024 × 1024 modal matrix `A` (four 512 × 512 trace blocks), joint source/reciprocal RHS `B`, receiver map `R`, both Dirichlet and flux `trace_coefficients`, geometry and basis metadata, and selected `dA`, `dB`, `dR` for constant and cosine-6 shape directions. The first 24 RHS columns are sources and the next 24 are unit-strength reciprocal receivers. `modes` specifies FFT ordering; coefficients use unitary normalization, not Fourier-series 1/N normalization.','',
              'It also retains the complex data/Jacobians, gradients, steps and reduced traces for every cutoff, plus reference and independently refined data/Jacobians. `feedback_K*` records A_LL^{-1} A_LH x_H. Full matrices permit later block, Schur, derivative and acquisition-aware analysis without regenerating the BIE solves.','',
              '`metrics.json` stores qualifications, four-block low/high coupling norms, retained conditioning, both trace tails, Schur corrections, discrete/Hadamard derivative comparisons, timings and artifact hashes. `manifest.json` freezes numerical sources, the two endpoint inputs, acquisition input and run environment.','',
              '![Operator blocks](operator_blocks.png)','',
              '![Selected operator derivative](operator_derivative_blocks.png)','',
              '## Validation, work and limits','',
              f"Read-back audit: **PASS**, {checked['arm_rows']} arm/cutoff records. Five tests passed before collection. Actual campaign: {index['seconds']:.1f} s, {index['work']['nodal_assemblies']} nodal assemblies, {index['work']['nodal_factorizations']} nodal factorizations, {index['work']['modal_factorizations']} reduced/Schur factorizations, {index['artifact_bytes']/2**20:.1f} MiB of numerical snapshots. One CPU worker and one BLAS thread. Timings are descriptive; host load was not controlled.", '',
              'The work ledger names primary reference/reduced/derivative RHS columns. Schur high-block elimination also solves against A_HL and B_H (sum over cutoffs of retained dimension + 48 RHS per cell), its corrected low solve uses 48 RHS, and the feedback diagnostic uses another 48 retained RHS. These diagnostic costs are additional to the primary RHS counters; factorization counts include all three per cutoff. No end-to-end speedup is claimed.','',
              'The failed C endpoint passes field/Jacobian grid checks but misses the fixed Cartesian direction-window fidelity gate: normal-basis projection discrepancy 2.17e-4 exceeds 1e-4. Its raw matrices are retained, but it receives no cutoff recommendation. This does not diagnose its reconstruction failure.','',
              'The 25-column Hadamard Jacobian and the two selected discrete-model derivatives are distinct objects at finite cutoff. The latter include changes in matrix, incident map and readout. A small data error alone does not certify either derivatives or a useful update. Schur reconstruction is a correctness control with full omitted-space work, not a compression method.','',
              'No high-update-band (M=37–85) qualification, native coefficient-workspace study, parameter-gauge invariance, noise model, timing benefit, or inverse recovery is established here.','',
              '## Reproduction','',
              '```bash',
              'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1',
              'export PYTHONPATH=solvers:. SC_FORWARD_BACKEND=cpu',
              '/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q -p no:cacheprovider experiments/modal_atlas',
              '/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_atlas.operator_atlas collect --output <fresh-directory>',
              '/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_atlas.operator_atlas_report results/validation/modal_atlas/MA-006',
              '```','']
    (folder/'README.md').write_text('\n'.join(lines))
    print(json.dumps(checked,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',type=Path)
    report(parser.parse_args().folder)
