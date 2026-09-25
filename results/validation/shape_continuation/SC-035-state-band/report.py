"""SC-035 report rebuild from saved states, without field solves."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiments.shape_continuation import atlas_strategy_tests as ast,spd_cases as sc
from experiments.shape_continuation.finite_path_study import geometric_score

HERE=Path(__file__).resolve().parent
CASES=('peanut','circle_to_c','circle_to_star','kite')
COLORS={'low':'#2a8a72','high':'#ad5555'}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
phase='continue' if all((HERE/'runs'/c/a/'continue.json').exists() for c in CASES for a in ('low','high')) else 'pilot'
fig,axes=plt.subplots(1,4,figsize=(16,4.7),layout='constrained')
lines=['| Case | Low K RMS (mm) | High K RMS (mm) | Ratio | Low / high work | Low / high status |',
       '|---|---:|---:|---:|---:|---|']
summary=[]
for ax,case in zip(axes,CASES):
    truth=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    z=truth.values(4096)*50;ax.plot(z.real,z.imag,color='black',label='Truth',lw=1.5)
    data={}
    for arm in ('low','high'):
        d=sc.read(HERE/'runs'/case/arm/f'{phase}.json')
        data[arm]=d
        z=ast.curve_from(d['curve']).values(4096)*50
        error=d.get('score',{}).get('symmetric_rms_mm',d['geometry']['rms_mm'])
        ax.plot(z.real,z.imag,color=COLORS[arm],label=f'{arm.title()} K: {error:.3f} mm')
    a,b=data['low'],data['high']
    errors=[r.get('score',{}).get('symmetric_rms_mm',r['geometry']['rms_mm']) for r in (a,b)]
    ratio=errors[0]/errors[1]
    lines.append(f"| {case} | {errors[0]:.6f} | {errors[1]:.6f} | {ratio:.4f} | {a['work']['work_units']} / {b['work']['work_units']} | {a['status']} / {b['status']} |")
    summary.append(dict(case=case,low_rms_mm=errors[0],high_rms_mm=errors[1],ratio=ratio,
        low_work=a['work']['work_units'],high_work=b['work']['work_units'],
        low_status=a['status'],high_status=b['status']))
    ax.set(title=case.replace('circle_to_',''),xlabel='x (mm)',ylabel='y (mm)',aspect='equal')
    ax.legend(fontsize=8,loc='best')
fig.savefig(HERE/f'{phase}_boundaries.png',dpi=180);plt.close(fig)
(HERE/f'{phase}_table.md').write_text('\n'.join(lines)+'\n')
sc.write(HERE/f'{phase}_comparison.json',dict(rows=summary,
    geometric_mean_ratio=float(np.exp(np.mean(np.log([r['ratio'] for r in summary]))))))
if phase=='continue':
    fig,axes=plt.subplots(1,4,figsize=(16,4),layout='constrained')
    stage_data=[]
    for ax,case in zip(axes,CASES):
        truth=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
        for arm in ('low','high'):
            points=[]
            for j,label in enumerate(('stage_1','stage_2','stage_3','stage_4','stage_5_release_repeat'),1):
                p=HERE/'runs'/case/arm/f'{label}_history.json'
                if p.exists():
                    d=sc.read(p)
                    if d['history']:
                        curve=ast.curve_from(d['history'][-1]['coefficients'])
                        score=geometric_score(curve,truth)
                        points.append((j,score['rms_mm']))
                        stage_data.append(dict(case=case,arm=arm,stage=j,**score))
            ax.plot([v[0] for v in points],[v[1] for v in points],'o-',label=arm.title()+' K',color=COLORS[arm])
        ax.set(title=case.replace('circle_to_',''),xlabel='Stage (5 = release/repeat)',ylabel='RMS error (mm)',yscale='log',xticks=[1,2,3,4,5])
        ax.grid(alpha=.2);ax.legend()
    fig.savefig(HERE/'stage_errors.png',dpi=180);plt.close(fig)
    sc.write(HERE/'stage_geometry.json',stage_data)
