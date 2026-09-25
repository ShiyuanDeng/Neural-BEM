"""SC-037 fixed-gate evaluation and comparison. Zero field solves."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiments.shape_continuation import atlas_strategy_tests as ast,spd_cases as sc

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'SC-035-state-band'
CASES=('peanut','circle_to_c','circle_to_star','kite')
rows=[]
fig,axes=plt.subplots(1,4,figsize=(16,4.5),layout='constrained')
lines=['| Case | SC-035 low RMS (mm) | SC-037 RMS (mm) | SC-037 / low | SC-037 work | Status |',
       '|---|---:|---:|---:|---:|---|']
for ax,case in zip(axes,CASES):
    previous=sc.read(BASE/'runs'/case/'low/continue.json')
    d=sc.read(HERE/'runs'/case/'result.json')
    error=d['score']['symmetric_rms_mm'];old=previous['score']['symmetric_rms_mm']
    ratio=error/old
    rows.append(dict(case=case,previous_rms_mm=old,new_rms_mm=error,ratio=ratio,
        work=d['work']['work_units'],status=d['status'],before_release=d.get('before_release_geometry')))
    lines.append(f"| {case} | {old:.6f} | {error:.6f} | {ratio:.4f} | {d['work']['work_units']} | {d['status']} |")
    truth=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    for curve,label,color in [(truth,'Truth','black'),(ast.curve_from(previous['curve']),f'SC-035: {old:.3f} mm','#2a8a72'),
                             (ast.curve_from(d['curve']),f'SC-037: {error:.3f} mm','#ae6b26')]:
        z=curve.values(4096)*50;ax.plot(z.real,z.imag,label=label,color=color)
    ax.set(title=case.replace('circle_to_',''),xlabel='x (mm)',ylabel='y (mm)',aspect='equal')
    ax.legend(fontsize=8)
star_high=sc.read(BASE/'runs/circle_to_star/high/continue.json')['score']['symmetric_rms_mm']
by_case={r['case']:r for r in rows}
criteria=dict(star_vs_high=by_case['circle_to_star']['new_rms_mm']/star_high<=1.05,
              peanut_vs_low=by_case['peanut']['ratio']<=1.25,
              c_vs_low=by_case['circle_to_c']['ratio']<=1.25,
              kite_vs_low=by_case['kite']['ratio']<=1.25,
              all_completed=all(r['status']=='COMPLETED_SCHEDULE' for r in rows))
sc.write(HERE/'decision.json',dict(passed=all(criteria.values()),criteria=criteria,rows=rows,
    star_ratio_vs_high=by_case['circle_to_star']['new_rms_mm']/star_high,
    total_inverse_units=sum(r['work'] for r in rows),evaluation_units=76))
(HERE/'comparison.md').write_text('\n'.join(lines)+'\n')
fig.savefig(HERE/'boundaries.png',dpi=180)
