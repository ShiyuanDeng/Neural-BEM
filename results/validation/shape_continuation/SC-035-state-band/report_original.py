"""Final briefing figure against the bitwise-replayed original hybrid."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiments.shape_continuation import atlas_strategy_tests as ast,spd_cases as sc

HERE=Path(__file__).resolve().parent
fig,axes=plt.subplots(1,4,figsize=(16,4.4),layout='constrained')
for ax,case in zip(axes,('peanut','circle_to_c','circle_to_star','kite')):
    truth=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    original=sc.read(HERE.parent/'SC-036-matched-finite-paths/inverse'/case/'normal/result.json')
    state=sc.read(HERE/'runs'/case/'low/continue.json')
    for curve,label,color,ls in [(truth,'Truth','black','-'),
        (ast.curve_from(original['final_curve']),f"Original: {original['score']['symmetric_rms_mm']:.3f} mm",'#4b70a2','--'),
        (ast.curve_from(state['curve']),f"State band: {state['score']['symmetric_rms_mm']:.3f} mm",'#238970','-')]:
        z=curve.values(4096)*50
        ax.plot(z.real,z.imag,color=color,ls=ls,label=label,lw=1.5)
    ax.set(title=case.replace('circle_to_',''),xlabel='x (mm)',ylabel='y (mm)',aspect='equal')
    ax.legend(fontsize=8,loc='best')
    ax.spines[['top','right']].set_visible(False)
fig.savefig(HERE/'original_vs_state_band.png',dpi=180)
