"""Read saved LAU-003 measurements; no physics or basis selection is rerun."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent/'LAU-003-20260917-pilot-01'
rows = list(csv.DictReader((BUNDLE/'comparisons.csv').open()))
fig, axes = plt.subplots(2,2,figsize=(11,7),sharex=True,layout='constrained')
scenarios = ['anchor','offset_minus','offset_plus','shifted_sources']
colors = ['#81909e','#086788','#ed7d31']
for i,case in enumerate(['ellipse-ka5','asymmetric_star-ka5']):
    for j,(metric,gate,title) in enumerate([
        ('worst_data_derivative_error',1e-3,'Worst physical shape-derivative error'),
        ('lifted_residual',1e-6,'Independent physical residual')]):
        ax = axes[i,j]
        for arm,color in zip(['FORWARD','TANGENT','PRIMAL_DUAL'],colors):
            selected = [next(r for r in rows if r['case']==case and r['arm']==arm and r['scenario']==s) for s in scenarios]
            rank,dimension = selected[0]['rank'],selected[0]['dimension']
            ax.semilogy(range(4),[float(r[metric]) for r in selected],'-o',color=color,
                label=f'{arm.replace("_"," ").title()} ({rank}/{dimension})',lw=1.8,ms=5)
        ax.axhline(gate,color='#b51c3a',ls='--',lw=1,label='Acceptance gate')
        ax.set_title(('Ellipse' if i==0 else 'Asymmetric star')+' · '+title,fontsize=11)
        ax.set_xticks(range(4),['Anchor','−0.5% radius','+0.5% radius','New sources'],fontsize=9)
        ax.grid(axis='y',alpha=.18)
        ax.set_ylim(1e-13,100)
        ax.set_ylabel('Relative error')
        if j==0: ax.legend(fontsize=8,loc='upper left')
fig.suptitle('LAU-003: matching fields is insufficient for shape inversion',fontsize=15)
fig.savefig(HERE/'sensitivity_reuse.png',dpi=180)
fig.savefig(HERE/'sensitivity_reuse.pdf')
