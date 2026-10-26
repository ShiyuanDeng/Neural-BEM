"""Summarize saved IS-001 receipts; never starts numerical solves."""
from pathlib import Path
import csv
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from bem_inverse.io import write
from experiments.linear_solves.is001 import OUT,ROOT,inputs


def build():
    profile=[]
    for state in ('release','final'):
        rows=json.loads((OUT/f'profile_{state}.json').read_text())
        for frequency in ('real','damped'):
            selected=[r for r in rows if r['frequency']==frequency]
            first=selected[0];warm=selected[1:]
            med=lambda function:float(np.median([function(r) for r in warm]))
            rec=dict(state=state,Ku=first['Ku'],frequency=frequency,
                first_forward_ms=1000*first['wall_forward'],
                first_geometry_ms=1000*first['stages']['geometry'],
                first_assembly_ms=1000*first['stages']['assembly'],
                warm_forward_jacobian_ms=1000*med(lambda r:r['wall_forward']+r['stages']['jacobian']))
            for key in ('assembly','waves','factorization'):
                rec[key+'_ms']=1000*med(lambda r:r['stages'][key])
            for key in ('forward_trace_solve','reciprocal_trace_solve','fields_other','hadamard_and_checks'):
                rec[key+'_ms']=1000*med(lambda r:r['split'][key])
            rec['factorization_share_percent']=100*med(lambda r:r['stages']['factorization']/(r['wall_forward']+r['stages']['jacobian']))
            rec['all_linear_share_percent']=100*med(lambda r:(r['stages']['factorization']+r['split']['forward_trace_solve']+r['split']['reciprocal_trace_solve'])/(r['wall_forward']+r['stages']['jacobian']))
            rec['first_factorization_share_percent']=100*first['stages']['factorization']/(first['wall_forward']+first['stages']['jacobian'])
            profile.append(rec)
    table=[];contractions=[]
    for path in sorted(OUT.glob('*_balanced_solves.json')):
        result=json.loads(path.read_text());stem=path.name.split('_balanced_solves')[0]
        state,rest=stem.split('_Ku');Ku,frequency=rest.split('_');Ku=int(Ku)
        LU=np.median([r['seconds'] for r in result['records'] if r['method']=='LU'])
        anchor=np.median(result['anchor_factor_seconds'])
        contractions.append(dict(state=state,Ku=Ku,frequency=frequency,
            right_residual_norm=result['right_residual_operator_norm_2'],
            spectral_radius=result['right_residual_operator_spectral_radius']))
        for method in dict.fromkeys(r['method'] for r in result['records']):
            rows=[r for r in result['records'] if r['method']==method]
            passed=all(r.get('converged',True) and r['accuracy']['prediction_relative']<=1e-9 for r in rows)
            elapsed=float(np.median([r['seconds'] for r in rows]));delta=float(LU-elapsed)
            reuse=int(np.floor(anchor/delta)+1) if passed and delta>0 and method.startswith('anchored') else None
            table.append(dict(state=state,Ku=Ku,unknowns=result['matrix_shape'][0],frequency=frequency,
                method=method,repetitions=len(rows),seconds=elapsed,passed=passed,
                iterations=rows[-1].get('iterations'),block_widths=rows[-1].get('block_widths'),
                prediction_relative=max(r['accuracy']['prediction_relative'] for r in rows),
                reciprocal_relative=max(r['accuracy']['reciprocal_relative'] for r in rows),
                jacobian_relative=max(r['accuracy']['jacobian_relative'] for r in rows),
                true_residual=max(r['accuracy']['residual'] for r in rows),
                anchor_factor_seconds=float(anchor),break_even_reuses=reuse,
                observed_residual_ratio=rows[-1].get('observed_residual_ratio')))
    displacement=[];curves=inputs()
    for state in ('release','final','large'):
        current,anchor=curves[state],curves[state+'_anchor']
        differences=.05*(current.values(4096)-anchor.values(4096))
        displacement.append(dict(state=state,maximum_point_displacement_mm=1000*float(abs(differences).max()),
            rms_point_displacement_mm=1000*float(np.sqrt(np.mean(abs(differences)**2)))))
    write(OUT/'summary.json',dict(profiles=profile,solvers=table,contractions=contractions,displacements=displacement,
        amortization='strict break-even n=floor(anchor_factor/(LU-current_iterative))+1; assumes equal future target costs, not measured trajectory reuse',
        physics_timing='forward+Jacobian duration combines disjoint measurements from the same call; component medians need not sum to median total'))
    for name,rows in [('profile_table',profile),('solver_table',table),('contraction_table',contractions)]:
        if not rows:continue
        with (OUT/(name+'.csv')).open('w') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    for frequency in ('real','damped'):
        fig,ax=plt.subplots(figsize=(6,4))
        for method,label in [('LU','LU, setup + 48 RHS'),('anchored_global_GMRES','Anchored global GMRES'),('anchored_block_GMRES','Anchored block GMRES')]:
            rows=sorted([r for r in table if r['state']=='release' and r['frequency']==frequency and r['method']==method],key=lambda r:r['unknowns'])
            ax.plot([r['unknowns'] for r in rows],[1000*r['seconds'] for r in rows],marker='o',label=label)
        ax.set(xscale='log',yscale='log',xlabel='System unknowns',ylabel='Median solve time (ms)',title=f'Hook c13.3, 2.5 GHz {frequency}; fixed release curve')
        ax.text(.02,.97,'Anchor setup excluded',transform=ax.transAxes,va='top',fontsize=9)
        ax.legend(fontsize=8,loc='lower right');ax.grid(alpha=.3);fig.tight_layout();fig.savefig(OUT/f'crossover_{frequency}.svg');fig.savefig(OUT/f'crossover_{frequency}.png',dpi=160);plt.close(fig)
    return dict(profile=profile,table=table,contractions=contractions,displacement=displacement)

if __name__=='__main__':
    result=build()
    print(json.dumps(result,indent=2))
