from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
ROOT=Path.cwd()
SAVED=ROOT/'results/validation/shape_continuation/SC-030-spd008-comparison/runs/repeat_0'
t=2*np.pi*np.arange(4096)/4096
def points(record):
    component=record[0]
    k=component['maximum_mode']; v=np.array(component['parameters'])
    cosine=v[:2*(k+1)].reshape(-1,2)
    sine=np.vstack((np.zeros(2),v[2*(k+1):].reshape(-1,2)))
    phase=t[:,None]*np.arange(k+1)
    return (np.cos(phase)@cosine+np.sin(phase)@sine-.5)*1000

fig,axes=plt.subplots(1,2,figsize=(10,5),layout='constrained')
for ax,case,label,folder in zip(axes,('wrong_circle','circle_to_star'),('Circle','Five-lobe star'),('circle_staged','star_staged')):
    initial=(np.array([.48,.52])+.065*np.column_stack((np.cos(t),np.sin(t)))-.5)*1000
    radius=.05 if case=='wrong_circle' else .05*(1+.25*np.cos(5*t))
    truth=1000*np.column_stack((radius*np.cos(t),radius*np.sin(t)))
    original=points(json.loads((SAVED/case/'spd008/final_state.json').read_text()))
    staged=points(json.loads((HERE/folder/'result.json').read_text())['final_state'])
    for p,color,style,name,width in [(initial,'#8d959e','--','Initial circle',1.),(original,'#c53b43','-','Original full-order start',1.6),(truth,'#20252c','-','True boundary',3.),(staged,'#008979','--','SPD with staged order',1.7)]:
        q=np.vstack((p,p[0]));ax.plot(q[:,0],q[:,1],color=color,ls=style,lw=width,label=name)
    ax.set_title(label);ax.set_aspect('equal');ax.set_xlim(-90,75);ax.set_ylim(-75,90)
    ax.set_xlabel('x − 0.5 m (mm)');ax.set_ylabel('y − 0.5 m (mm)')
    ax.grid(alpha=.15)
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='outside lower center',ncol=2,frameon=False)
fig.suptitle('Single-object recovery with the current SPD fitter',fontsize=14)
fig.savefig(HERE/'boundaries.png',dpi=180)
fig.savefig(HERE/'boundaries.pdf')
fig.savefig(HERE/'boundaries.svg')
svg=HERE/'boundaries.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
