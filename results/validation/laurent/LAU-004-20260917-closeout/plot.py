"""Regenerate the LAU-004 summary from immutable saved pilot rows."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap,BoundaryNorm
from matplotlib.patches import Patch
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent/'LAU-004-20260917-pilot-01'
rows = list(csv.DictReader((ROOT/'policies.csv').open()))
cases = ['ellipse-ka5','asymmetric_star-ka5']
arms = ['JOINT_TANGENT','PRIMAL_TANGENT','PRIMAL_DUAL_TANGENT']
scenarios = ['anchor','train_minus_0.001','train_plus_0.001','train_minus_0.005',
             'train_plus_0.005','evaluation_motion','shifted_sources']
labels = ['Ellipse · joint','Ellipse · protected primal','Ellipse · protected primal + adjoint',
          'Star · joint','Star · protected primal','Star · protected primal + adjoint']
fig,(left,right) = plt.subplots(1,2,figsize=(14,5.4),gridspec_kw={'width_ratios':[1,1.4]},layout='constrained')
mat = np.zeros((6,7))
for i,(case,arm) in enumerate((c,a) for c in cases for a in arms):
    subset = {r['scenario']:r for r in rows if r['case']==case and r['arm']==arm}
    base = subset['anchor']
    rank,dim = int(base['frozen_rank']),int(base['dimension'])
    left.barh(i,rank/dim,color=['#89939e','#007f8b','#b7791f'][i%3],height=.65)
    left.text(rank/dim+.015,i,f'{rank}/{dim}',va='center',fontsize=10)
    for j,s in enumerate(scenarios):
        row = subset[s]
        mat[i,j] = 0 if row['action']=='REUSE' else (2 if row['frozen_pass']=='True' else 1)
left.set_xlim(0,1.08)
left.set_xticks([0,.25,.5,.75,1],['0%','25%','50%','75%','100%'])
left.set_yticks(range(6),labels,fontsize=9)
left.invert_yaxis()
left.axvline(.5,color='#333333',ls='--',lw=1)
left.set_title('Selected rank / full trace dimension')
left.set_xlabel('Half-dimension target shown dashed')
colors = ['#007f8b','#cf6a4c','#edc96b']
right.imshow(mat,cmap=ListedColormap(colors),norm=BoundaryNorm([-.5,.5,1.5,2.5],3),aspect='auto')
right.set_yticks(range(6),['']*6)
right.set_xticks(range(7),['Anchor','−0.1%','+0.1%','−0.5%','+0.5%','Unused\nmotion','New\nsources'],fontsize=9)
for i in range(6):
    for j in range(7):
        right.text(j,i,'reuse' if mat[i,j]==0 else 'rebuild',ha='center',va='center',fontsize=9,
                   color='white' if mat[i,j] in [0,1] else '#303030')
right.set_title('Guard decisions · all 42 delivered outputs pass')
right.legend(handles=[Patch(color=colors[0],label='Reuse (18)'),
    Patch(color=colors[1],label='Reject inaccurate model (18)'),
    Patch(color=colors[2],label='Conservative rebuild (6)')],loc='upper center',
    bbox_to_anchor=(.5,-.15),ncol=2,frameon=False,fontsize=9)
fig.suptitle('LAU-004: smaller protected bases, guarded reuse',fontsize=16)
fig.savefig(HERE/'protected_reuse.png',dpi=170)
fig.savefig(HERE/'protected_reuse.pdf')
