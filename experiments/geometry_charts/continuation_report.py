"""Compare the four completed TA-001 chart fits with their saved NR-001 controls."""
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from bem_inverse.io import curve_from, read, write
from .continuation import FOLDER
from .replay import ROWS, SOURCE, UNIT, geometry_metrics


def main():
    table=[]
    failures=[]
    figure,axes=plt.subplots(2,2,figsize=(9,9),layout='constrained')
    for (case,_),ax in zip(ROWS,axes.ravel()):
        reference=read(SOURCE/case/'result.json')
        folder=FOLDER/'chart/runs'/case
        result=read(folder/'result.json')
        check=read(folder/'final_audit.json')
        stage=result['stages'][-1]['stage']
        stage_row=read(folder/(stage+'.json'))
        failed=[f for t in stage_row['trials'] for f in t.get('physics_failures',[])]
        failure=failed[0] if failed else {}
        failure_metrics=None
        if 'candidate_coefficients' in failure:
            failure_metrics=geometry_metrics(curve_from(failure['candidate_coefficients']))
        failures.append(dict(case=case,message=failure.get('message'),metrics=failure_metrics))
        row=dict(case=case,recovered=result['recovered'],reference_recovered=reference['recovered'],
            outcome=result['outcome'],reference_outcome=reference['outcome'],
            last_stage=stage,reference_last_stage=reference['stages'][-1]['stage'],
            rms_mm=result['metrics']['rms_mm'],reference_rms_mm=reference['metrics']['rms_mm'],
            hausdorff_upper_mm=result['metrics']['hausdorff_upper_mm'],
            reference_hausdorff_upper_mm=reference['metrics']['hausdorff_upper_mm'],
            maximum_residual=result['maximum_residual'],reference_maximum_residual=reference['maximum_residual'],
            final_check=result['final_audit_passed'],reference_final_check=reference['final_audit_passed'],
            fit_units=result['fit_and_localization_units'],reference_fit_units=reference['fit_and_localization_units'],
            fit_seconds=result['fit_and_localization_seconds'],total_seconds=result['total_seconds'],
            reference_total_seconds=reference['total_seconds'],
            final_check_seconds=check['seconds'],
            physics_failure=failure.get('message'),
            closure_refusals=result['geometry_work'].get('chart_closure_refusals',0),
            max_rss_mb=result['resources']['max_rss_mb'],
            gpu_max_reserved_mib=result['resources']['gpu']['max_reserved_mib'])
        table.append(row)
        target=curve_from(read(SOURCE.parents[1].parent/'TG-002'/'inputs'/result['case']['case']/'truth.json'))
        for curve,color,label in [(target,'#202020','Truth'),(curve_from(reference['final_curve']),'#d43d28','NR-001'),
                                  (curve_from(result['final_curve']),'#0068a8','Chart')]:
            z=curve.values(8192)*UNIT*1000
            z=np.r_[z,z[0]]
            ax.plot(z.real,z.imag,color=color,label=label,lw=1.5)
        ax.set_title(f'{case}\nRMS: NR {row["reference_rms_mm"]:.2f}, chart {row["rms_mm"]:.2f} mm')
        ax.set_aspect('equal',adjustable='box')
        ax.grid(alpha=.2)
        ax.set_xlabel('x relative to centre (mm)')
        ax.set_ylabel('y relative to centre (mm)')
    axes[0,0].legend()
    figure.savefig(FOLDER/'endpoints.png',dpi=150)
    plt.close(figure)
    with (FOLDER/'comparison.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(table[0]))
        writer.writeheader();writer.writerows(table)
    write(FOLDER/'comparison.json',dict(rows=table,recovered=sum(t['recovered'] for t in table),
                                       reference_recovered=sum(t['reference_recovered'] for t in table)))
    write(FOLDER/'refused_geometry.json',dict(rows=failures,description='Saved failed candidates only; no extra fits or physics.'))
    for r in table:
        print(r,flush=True)


if __name__=='__main__':
    main()
