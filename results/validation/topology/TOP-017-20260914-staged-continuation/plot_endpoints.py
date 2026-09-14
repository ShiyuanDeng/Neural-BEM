"""Render saved endpoint metrics only; no forward or inverse imports/calls."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='TOP-017'
import matplotlib.pyplot as plt
BUNDLE=Path(__file__).resolve().parent
report=json.loads((BUNDLE/'scorecard.json').read_text())
fig,axes=plt.subplots(2,2,figsize=(10,6.8),sharex=True,constrained_layout=True)
colors={'S':'#b5681a','F':'#136ea5'}
for row,scene in enumerate(('far-two-stars','central-ellipse-star')):
    for trial in (r for r in report['trials'] if r['scene']==scene):
        records=[(1,trial['initial'])]+[(r['stage'],r['score']) for r in trial['stages'] if 'score' in r]
        for col,metric in enumerate(('boundary','evaluation')):
            ax=axes[row,col]
            value=lambda s:1000*s['geometry']['maximum_matched_hausdorff_m'] if metric=='boundary' else s['maximum_evaluation_error']
            ax.plot([n for n,s in records],[value(s) for n,s in records],'-o',color=colors[trial['arm']],label=trial['arm'],lw=2,markersize=5)
            for n,s in records:
                if not s['numerically_qualified']:
                    ax.scatter([n],[value(s)],marker='x',s=100,color='#b90021',zorder=5,linewidths=2)
            ax.set_yscale('log');ax.grid(True,alpha=.2)
            ax.axhline(1 if metric=='boundary' else .05,color='#333333',ls=':',lw=1)
            ax.set_title(scene.replace('-',' ')+' · '+metric,fontsize=11)
            ax.set_ylabel('Boundary error (mm)' if metric=='boundary' else 'Worst 1.5/2.5-GHz relative error')
            ax.set_xticks([1,2,3,4],['Reused 1','2','3','4'])
            ax.legend(title='Training arm',loc='best')
    for ax in axes[row]:ax.set_xlim(.8,4.2)
for ax in axes[-1]:ax.set_xlabel('Predetermined stage endpoint')
fig.suptitle('TOP-017: endpoint quality through the approved schedule',fontsize=15)
fig.supxlabel('Dotted lines: original gates. Red ×: numerically unqualified score. Missing endpoints were not scored.',fontsize=9)
fig.savefig(BUNDLE/'endpoint_quality.png',dpi=180)
fig.savefig(BUNDLE/'endpoint_quality.svg',metadata={'Date':None})
svg=BUNDLE/'endpoint_quality.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
