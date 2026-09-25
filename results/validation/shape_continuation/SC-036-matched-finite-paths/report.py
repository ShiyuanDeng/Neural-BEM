"""Rebuild SC-036 tables and figures from saved artifacts, zero field solves."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc

HERE=Path(__file__).resolve().parent
COLORS={'normal':'#286090','ray':'#c76821'}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})

fig,axes=plt.subplots(1,3,figsize=(14,4.1),layout='constrained')
rows=[]
for p in sorted(HERE.glob('*/result.json')):
    d=sc.read(p)
    best={}
    for arm in ('normal','ray'):
        r=[r for r in d['trials'] if r['path']==arm and r['accepted']]
        if r:
            best[arm]=max(r,key=lambda r:r['refined_decrease'])
    rows.append(dict(state=p.parent.name,base_rms=d['base_geometry']['rms_mm'],
                     radius=d['base_geometry']['radius_mm'],best=best))
d=sc.read(HERE/'peanut_3/result.json')
truth=ast.curve_from(sc.read(ast.source_folder('peanut')/'truth.json'))
history=sc.read(sc.ROOT/'results/validation/shape_continuation/SC-029-atlas-strategies/runs/baseline/peanut/none/stage_1_history.json')
base=ast.curve_from(history['history'][3]['coefficients'])
for curve,label,color,ls in [(truth,'Truth','#222222','-'),(base,'Current state','#888888','--')]:
    z=curve.values(4096)*50
    axes[0].plot(z.real,z.imag,color=color,ls=ls,label=label)
for arm in ('normal','ray'):
    valid=[r for r in d['trials'] if r['path']==arm and r['accepted']]
    best=max(valid,key=lambda r:r['refined_decrease'])
    backtrack=int(round(-np.log2(best['scale'])))
    curve=ast.curve_from(sc.read(HERE/f'peanut_3/{arm}_{backtrack}_curve.json'))
    z=curve.values(4096)*50
    axes[0].plot(z.real,z.imag,color=COLORS[arm],label=f"{arm.title()}: {best['rms_mm']:.2f} mm RMS")
    trials=[r for r in d['trials'] if r['path']==arm and r['accepted']]
    axes[1].plot([r['scale'] for r in trials],[r['refined_decrease'] for r in trials],
                 'o-',color=COLORS[arm],label=arm.title())
axes[0].set(aspect='equal',xlabel='x (mm)',ylabel='y (mm)',title='Identical tangent, different finite progress')
axes[0].legend(fontsize=8,loc='best')
axes[1].set(xscale='log',xlabel='Multiplier of identical LM step',ylabel='Actual refined objective decrease',
            title='Early peanut corner: 3.15× larger decrease')
axes[1].legend();axes[1].grid(alpha=.2)
coordinates=sc.read(HERE.parent/'SC-036-coordinate-review/results.json')
for case,label,color in [('wrong_circle_truth','Circle','#666666'),('circle_to_star_truth','Five-lobe star','#8e5b9a'),('circle_to_c_truth','Non-star C','#2c927b')]:
    values=coordinates[case]['coordinates']['translation_normal_energy_captured']['x']
    axes[2].plot([int(m) for m in values],[100*values[m] for m in values],'o-',label=label,color=color)
axes[2].set(xlabel='Arclength normal band M',ylabel='Rigid x translation energy captured (%)',
            title='Coordinate bandwidth is not shape complexity',ylim=(50,101),xscale='log')
axes[2].legend(fontsize=8);axes[2].grid(alpha=.2)
fig.savefig(HERE/'screen.png',dpi=180)
plt.close(fig)

lines=['| State | Current RMS / radius (mm) | Normal best scale / RMS | Ray best scale / RMS | Decrease ratio ray/normal |',
       '|---|---:|---:|---:|---:|']
for d in rows:
    a,b=d['best'].get('normal'),d['best'].get('ray')
    cell=lambda r: f"{r['scale']:.5g} / {r['rms_mm']:.4f}" if r else 'none admissible'
    ratio=f"{b['refined_decrease']/a['refined_decrease']:.3f}" if a and b else '—'
    lines.append(f"| {d['state']} | {d['base_rms']:.4f} / {d['radius']:.4f} | {cell(a)} | {cell(b)} | {ratio} |")
(HERE/'screen_table.md').write_text('\n'.join(lines)+'\n')

paths=[HERE/'inverse'/case/arm/'result.json' for case in ('peanut','kite','circle_to_star','circle_to_c') for arm in ('normal','ray')]
if all(p.exists() for p in paths):
    fig,axes=plt.subplots(1,4,figsize=(16,4.5),layout='constrained')
    lines=['| Case | Normal RMS (mm) | Ray RMS (mm) | Ratio | Normal / ray inverse units | Status normal / ray |',
           '|---|---:|---:|---:|---:|---|']
    for ax,case in zip(axes,('peanut','kite','circle_to_star','circle_to_c')):
        truth=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
        z=truth.values(4096)*50;ax.plot(z.real,z.imag,color='black',lw=1.5,label='Truth')
        scores={}
        for arm in ('normal','ray'):
            d=sc.read(HERE/'inverse'/case/arm/'result.json')
            scores[arm]=d
            z=ast.curve_from(d['final_curve']).values(4096)*50
            error=d['score']['symmetric_rms_mm']
            ax.plot(z.real,z.imag,color=COLORS[arm],label=f'{arm.title()}: {error:.3f} mm')
        a,b=scores['normal'],scores['ray']
        ea,eb=[d['score']['symmetric_rms_mm'] for d in (a,b)]
        lines.append(f"| {case} | {ea:.5f} | {eb:.5f} | {eb/ea:.3f} | {a['work']['work_units']} / {b['work']['work_units']} | {a['status']} / {b['status']} |")
        ax.set(title=case.replace('circle_to_',''),xlabel='x (mm)',ylabel='y (mm)',aspect='equal')
        ax.legend(fontsize=8,loc='best')
    fig.savefig(HERE/'inverse_boundaries.png',dpi=180)
    plt.close(fig)
    (HERE/'inverse_table.md').write_text('\n'.join(lines)+'\n')
