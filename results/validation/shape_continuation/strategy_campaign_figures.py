"""Report-only figures for SC-042/043/044; read JSON, never run the inverse."""
import importlib.util
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('campaign_common',ROOT/'SC-042-state-strategies/run.py')
c=importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
COLORS={'none':'#555555','once':'#0072B2','boundary':'#D55E00','cap':'#009E73',
        'fixed':'#555555','stagnation':'#0072B2','atlas':'#D55E00'}
LABELS={'none':'Unchanged','once':'Cleanup once','boundary':'Cleanup each stage','cap':'State cap',
        'fixed':'Fixed release','stagnation':'Stagnation rule','atlas':'Action diagnostic'}


def read(path):
    return c.sc.read(path) if path.exists() else None


def curve(ax,record,**kw):
    z=50*c.ast.curve_from(record).values(2048)
    z=np.r_[z,z[0]]
    ax.plot(z.real,z.imag,**kw)


def finish(fig,axes,folder,name,title):
    handles,labels=[],[]
    for ax in axes.flat:
        for handle,label in zip(*ax.get_legend_handles_labels()):
            if label not in labels:
                handles.append(handle)
                labels.append(label)
    fig.suptitle(title,fontsize=14)
    fig.legend(handles,labels,loc='lower center',ncol=3,frameon=False)
    fig.tight_layout(rect=(0,.075,1,.94))
    fig.savefig(folder/f'{name}.png',dpi=170)
    fig.savefig(folder/f'{name}.pdf')
    plt.close(fig)


def state_strategies():
    folder=ROOT/'SC-042-state-strategies'
    fig,axes=plt.subplots(2,3,figsize=(13,8))
    progress,paxes=plt.subplots(2,3,figsize=(13,8))
    count=0
    for case,ax,pax in zip(c.CASES,axes.flat,paxes.flat):
        truth=c.sc.read(c.ast.source_folder(case)/'truth.json')
        curve(ax,truth,color='black',lw=1.8,label='Truth')
        initial=c.start_record(case)[0]
        curve(ax,c.ast.curve_record(initial),color='#AAAAAA',lw=1,ls=':',label='Start')
        completed=0
        for arm in c.ARMS:
            base=folder/'runs'/case/arm
            result=read(base/'result.json')
            if result is None:continue
            count+=1
            completed+=1
            curve(ax,result['curve'],color=COLORS[arm],lw=1,label=LABELS[arm])
            states=read(base/'progress.json')['states']
            # Cleanup resets are deliberate discontinuities, not descent steps.
            for stage in dict.fromkeys(s['stage'] for s in states):
                segment=[s for s in states if s['stage']==stage]
                pax.plot([s['total_units'] for s in segment],[s['score']['rms_mm'] for s in segment],
                         '.-',ms=3,color=COLORS[arm],lw=1,label=LABELS[arm])
            final=result['score']['rms_mm']
            bad=result['outcome']!='COMPLETED_SCHEDULE' or not result['audit_passed']
            pax.scatter([result['total_units']],[final],marker='x' if bad else 'o',s=35,
                        color=COLORS[arm],zorder=5)
        ax.set(title=f'{case.replace("_"," ")} ({completed}/4)',xlabel='x / mm',ylabel='y / mm',aspect='equal')
        pax.set(title=case.replace('_',' '),xlabel='Fitting work units',ylabel='Boundary RMS / mm',yscale='log')
        if case=='wrong_circle':
            pax.set_ylim(1e-4,1e-3)
            pax.text(.5,.92,'Below 0.01 mm comparison floor',transform=pax.transAxes,ha='center',fontsize=9)
        pax.grid(alpha=.2)
    finish(fig,axes,folder,'geometry',f'SC-042: matched state strategies — {count}/24 scored paths')
    finish(progress,paxes,folder,'geometry_by_work',f'SC-042: geometry against charged fitting work — {count}/24; × = stopped or audit failed')


def band_policies():
    folder=ROOT/'SC-043-prospective-band'
    fig,axes=plt.subplots(2,3,figsize=(13,8))
    count=0
    for case,ax in zip(c.CASES,axes.flat):
        for policy in ('fixed','stagnation','atlas'):
            base=folder/'runs'/case/policy
            result=read(base/'result.json')
            if result is None:continue
            count+=1
            states=read(base/'progress.json')
            if states:
                for block in dict.fromkeys(s['block'] for s in states['states']):
                    segment=[s for s in states['states'] if s['block']==block]
                    ax.plot([s['total_units'] for s in segment],[s['score']['rms_mm'] for s in segment],
                            '.-',color=COLORS[policy],lw=1,label=LABELS[policy])
            bad=result['outcome']!='COMPLETED_SCHEDULE' or not result['audit_passed']
            ax.scatter([result['total_units']],[result['score']['rms_mm']],marker='x' if bad else 'o',s=35,color=COLORS[policy])
        ax.set(title=case.replace('_',' '),xlabel='Fitting + diagnostic work',ylabel='Boundary RMS / mm',yscale='log')
        if case=='wrong_circle':
            ax.set_ylim(1e-4,1e-3)
            ax.text(.5,.92,'Below 0.01 mm comparison floor',transform=ax.transAxes,ha='center',fontsize=9)
        ax.grid(alpha=.2)
    finish(fig,axes,folder,'geometry_by_work',f'SC-043: prospective rules with diagnostics charged — {count}/18 scored paths')


def kite_feature():
    folder=ROOT/'SC-042-state-strategies'
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    truth=c.sc.read(c.ast.source_folder('kite')/'truth.json')
    initial=c.start_record('kite')[0]
    nodes=initial.nodes(16384)
    point=50*nodes.points[np.argmax(abs(nodes.curvatures))]
    for ax in axes.flat:
        curve(ax,truth,color='black',lw=2,label='Truth')
        curve(ax,c.ast.curve_record(initial),color='#AAAAAA',ls=':',lw=1.5,label='Start')
        for arm in c.ARMS:
            result=read(folder/'runs'/'kite'/arm/'result.json')
            if result:
                curve(ax,result['curve'],color=COLORS[arm],lw=1.3,label=LABELS[arm])
        ax.set(xlabel='x / mm',ylabel='y / mm',aspect='equal')
        ax.grid(alpha=.15)
    axes[0].set_title('Whole boundary')
    axes[1].set(xlim=(point[0]-1.2,point[0]+1.2),ylim=(point[1]-1.2,point[1]+1.2),
                title='Flank artifact\nZoom fixed at initial curvature maximum')
    finish(fig,axes,folder,'kite_feature','SC-042: kite boundary and flank artifact')


def fresh_shapes():
    folder=ROOT/'SC-044-noisy-fresh-cases'
    fig,axes=plt.subplots(2,3,figsize=(13,8))
    count=0
    for row,case in enumerate(('asymmetric_lobes','deep_c')):
        for column,profile in enumerate(('clean','noise_seed_0','noise_seed_1')):
            ax=axes[row,column]
            curve(ax,read(folder/'inputs'/case/'truth.json'),color='black',lw=1.8,label='Truth')
            for arm in ('none','boundary','cap'):
                result=read(folder/'runs'/case/profile/arm/'result.json')
                if result is None or 'curve' not in result:continue
                count+=1
                curve(ax,result['curve'],color=COLORS[arm],lw=1,label=LABELS[arm])
            ax.set(title=f'{case.replace("_"," ")} / {profile}',xlabel='x / mm',ylabel='y / mm',aspect='equal')
    finish(fig,axes,folder,'geometry',f'SC-044: two fixed new shapes, paired noise draws — {count}/18 scored paths')


def cavity_feature():
    folder=ROOT/'SC-044-noisy-fresh-cases'
    base=read(folder/'runs/deep_c/clean/none/result.json')
    if base is None:return
    nodes=c.ast.curve_from(base['curve']).nodes(16384)
    point=50*nodes.points[np.argmax(abs(nodes.curvatures))]
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    for ax in axes:
        curve(ax,read(folder/'inputs/deep_c/truth.json'),color='black',lw=2,label='Truth')
        for arm in ('none','boundary','cap'):
            result=read(folder/'runs/deep_c/clean'/arm/'result.json')
            if result:
                curve(ax,result['curve'],color=COLORS[arm],lw=1.4,label=LABELS[arm])
        ax.set(xlabel='x / mm',ylabel='y / mm',aspect='equal')
        ax.grid(alpha=.15)
    axes[0].set_title('Whole boundary, clean data')
    axes[1].set(xlim=(point[0]-4,point[0]+4),ylim=(point[1]-4,point[1]+4),
                title='Post-fit diagnostic zoom\nUnfiltered endpoint curvature maximum')
    finish(fig,axes,folder,'cavity_feature','SC-044: local artifact on the deeper C')


if __name__=='__main__':
    c.verify()
    state_strategies()
    kite_feature()
    band_policies()
    fresh_shapes()
    cavity_feature()
