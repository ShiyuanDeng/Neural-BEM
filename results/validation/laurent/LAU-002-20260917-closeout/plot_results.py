"""Render the frozen LAU-002 results; no solver or acceptance logic changes."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
def rows(name,file):
    with (HERE.parent/name/file).open() as stream:
        return list(csv.DictReader(stream))

scalar=rows('LAU-002-20260917-scalar-qualified-02','convergence.csv')
transfer=rows('LAU-002-20260917-transfer-campaign-01','transfer.csv')
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                     'svg.fonttype':'none','savefig.facecolor':'white'})
fig,(left,right)=plt.subplots(1,2,figsize=(13.5,6.3))
fig.subplots_adjust(left=.07,right=.98,bottom=.2,top=.79,wspace=.34)
fig.suptitle('Published compression converges; transmission savings depend on the case',
             x=.07,ha='left',y=.97,fontsize=17,fontweight='bold')
fig.text(.07,.9,'LAU-002 | Independent scalar reproduction and 312 transmission comparisons',color='#475569')
for arm,color,label in [('CFG','#64748b','Dense Galerkin'),('FFG_mu1.1','#007f86',r'Published mask, $\mu=1.1$'),
                         ('FFG_mu1.2','#315ba8',r'Published mask, $\mu=1.2$'),('FFG_mu1.4','#ad5a18',r'Published mask, $\mu=1.4$')]:
    rr=[r for r in scalar if r['example']=='3' and r['arm']==arm]
    left.loglog([2*int(r['n'])-1 for r in rr],[float(r['error_l2']) for r in rr],
                'o-',ms=4,lw=1.7,color=color,label=label)
left.set(title='Scalar ellipse: analytic density',xlabel='Number of Fourier unknowns (2n - 1)',
         ylabel=r'Density $L^2$ error',ylim=(4e-16,1))
left.grid(True,which='major',color='#e2e8f0',lw=.7)
left.legend(loc='lower left',fontsize=9,frameon=False)
left.annotate('0.69% of entries\nerror 1.6e-11',xy=(2047,1.628e-11),xytext=(310,7e-10),
              fontsize=10,color='#007f86',arrowprops=dict(arrowstyle='-',color='#007f86'))
cases=list(dict.fromkeys(r['case'] for r in transfer))
for i,case in enumerate(cases):
    good=[r for r in transfer if r['case']==case and r['passes_all']=='True']
    if good:
        best=min(good,key=lambda r:float(r['stored_slots'])/float(r['original_dense_slots']))
        value=100*float(best['stored_slots'])/float(best['original_dense_slots'])
        right.barh(i,value,color='#007f86' if 'circle@' in case else '#315ba8',height=.62)
        right.text(value+1.8,i,f'{value:.1f}%',va='center',fontsize=10)
    else:
        right.barh(i,100,color='#f8fafc',edgecolor='#cbd5e1',hatch='///',height=.62)
        right.text(50,i,'No passing setting',va='center',ha='center',color='#a04422',fontsize=10)
right.set_yticks(np.arange(len(cases)),[s.replace('asymmetric_star','Asym. star').replace('star@','Star@').replace('ellipse','Ellipse').replace('circle','Circle').replace('@ka',', ka = ') for s in cases])
right.invert_yaxis()
right.set(xlim=(0,112),xticks=[0,25,50,75,100],
          xlabel='Represented slots / original dense slots (%)',
          title='Transmission: smallest passing representation')
right.axvline(100,ls=':',color='#94a3b8',lw=1)
fig.text(.07,.08,'Scalar: the printed tables are not reproduced exactly. Transmission: noncircular passes use an adapted mask.',fontsize=10,color='#475569')
fig.text(.07,.045,'Counts include protected forward terms; the transmission implementation still assembles and solves dense matrices. No runtime gain claimed.',fontsize=10,color='#475569')
fig.savefig(HERE/'literature_progress.png',dpi=170)
fig.savefig(HERE/'literature_progress.svg')
