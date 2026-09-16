"""Measured shape-T inverse results and the mode bands of Laurent perturbations."""
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .run_deformation_inverse import ROOT
from .run_inverse import save
from .deformation_inverse import shape_fixture
from .run_scattering_library import boundary


def read(name): return json.loads((ROOT/name).read_text())


def main():
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'figure.dpi':130,'savefig.dpi':180})
    rows=read('summary.json')
    cases=list(dict.fromkeys(r['case'] for r in rows));arms=list(dict.fromkeys(r['arm'] for r in rows))
    medians={c:{a:float(np.median([r['seconds'] for r in rows if r['case']==c and r['arm']==a]))
                for a in arms} for c in cases}
    differences={}
    for case in cases:
        reference=np.array(read(case+'_nodal_rebuild64_0.json')['parameters'])
        differences[case]={arm:float(np.max(np.abs(np.array(read(case+'_'+arm+'_0.json')['parameters'])-reference)))
                           for arm in arms}
    frozen={case:read(case+'_frozen_control.json') for case in cases}
    history=read('four_noise1pct_native_relinearized_0.json')
    fig,axes=plt.subplots(2,2,figsize=(13,9.5),layout='constrained')
    ax=axes[0,0];_,chart,truth,initial=shape_fixture(4)
    for x,color,style,label in [(initial,'#a4a9b0','-','Initial'),(truth,'#167d9a','-','Truth'),
                              (np.array(history['parameters']),'#df772d','--','Recovered')]:
        for i,g in enumerate(chart.moved(x)):
            xy=100*boundary(g)
            ax.plot(xy[:,0],xy[:,1],color=color,ls=style,lw=1.8,label=label if i==0 else None)
    ax.set(title='A. Shape and pose recovered together\n24 unknowns; 1% noise',xlabel='x (cm)',ylabel='y (cm)',
           aspect='equal',xlim=(35,65),ylim=(35,65))
    ax.legend(loc='upper center',ncol=3,frameon=False,fontsize=9)
    ax.text(.5,.5,f"Boundary RMS: {history['metrics']['boundary_rms_mm']:.3f} mm\n3 pose + 3 Laurent coordinates per object",
            ha='center',va='center',transform=ax.transAxes,fontsize=9)

    ax=axes[0,1]
    order=['nodal_rebuild64','nodal_rebuild_qualified','native_exact','native_relinearized','nodal_exact','nodal_relinearized']
    labels=['Full Kress, N=64','Full Kress, qualified N=32','Laurent T, rebuild each trial',
            'Laurent T, checked local models','Kress T, rebuild each trial','Kress T, checked local models']
    values=[medians['four_noise1pct'][a] for a in order]
    bars=ax.barh(np.arange(6),values,color=['#999fa8','#717782','#167d9a','#53a5b7','#3d8657','#86b497'])
    ax.bar_label(bars,labels=[f'{v:.3f} s' for v in values],padding=5,fontsize=9)
    ax.set(title='B. Complete inverse, including compilation',xlabel='Wall time (seconds)',yticks=np.arange(6),
           yticklabels=labels,xlim=(0,max(values)*1.22))
    ax.invert_yaxis();ax.tick_params(axis='y',labelsize=9)
    ax.text(.98,.02,'Median of 3 runs; one CPU thread',ha='right',transform=ax.transAxes,fontsize=9)

    ax=axes[1,0];steps=history['history'];iteration=np.arange(1,len(steps)+1)
    ax.semilogy(iteration,[s['actual_residual'] for s in steps],'o-',color='#167d9a',label='Freshly compiled residual')
    ax.semilogy(iteration,[s['model_data_discrepancy'] for s in steps],'s-',color='#df772d',label='Local-model discrepancy')
    ax.set(title='C. Recompile to remove approximation bias',xlabel='Outer shape-model update',
           ylabel='Normalized data norm',xticks=iteration)
    ax.grid(alpha=.15);ax.legend(frameon=False,fontsize=9)

    ax=axes[1,1];ranges=read('frozen_range.json');s=np.array([r['deformation_scale'] for r in ranges])
    e=np.array([r['data_error'] for r in ranges])
    ax.loglog(s,e,'o-',color='#df772d',label='Frozen first-order T model')
    ax.loglog(s,e[0]*(s/s[0])**2,'--',color='#999fa8',label='Quadratic growth guide')
    ax.axhline(.01,color='#167d9a',ls=':',label='1% noise level')
    ax.set(title='D. A single frozen shape model is insufficient',xlabel='Deformation relative to benchmark truth',
           ylabel='Relative forward-model error',xticks=s,xticklabels=[str(v) for v in s])
    ax.legend(frameon=False,fontsize=9);ax.grid(alpha=.15)
    fig.suptitle('Differentiate the scattering matrix in Laurent shape coordinates',fontsize=16)
    for ext in ['png','pdf']: fig.savefig(ROOT/f'deformation_findings.{ext}')
    plt.close(fig)

    fingerprints=read('mode_fingerprints.json')
    fig,axes=plt.subplots(1,3,figsize=(12,4.1),layout='constrained')
    for ax,row in zip(axes,fingerprints):
        a=np.array(row['absolute_derivative']);logs=np.log10(np.maximum(a/a.max(),1e-14))
        heat=ax.imshow(logs,origin='lower',extent=(-12.5,12.5,-12.5,12.5),vmin=-14,vmax=0,cmap='magma',interpolation='nearest')
        harmonic=row['radial_harmonic']
        ax.set(title=f'Radial harmonic {harmonic}: |m − n| = {harmonic}',xlabel='Incoming mode n',ylabel='Outgoing mode m',
               xticks=[-12,-6,0,6,12],yticks=[-12,-6,0,6,12])
    fig.colorbar(heat,ax=axes,label='log₁₀ |δTₘₙ| / max |δT|',shrink=.85,pad=.02)
    fig.suptitle('At a circle, each shape harmonic opens two specific mode-coupling bands',fontsize=14)
    for ext in ['png','pdf']: fig.savefig(ROOT/f'shape_mode_fingerprints.{ext}')
    plt.close(fig)
    manifest=read('manifest.json')
    drift=[p for p,h in manifest['source_hashes'].items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    save(ROOT/'findings.json',dict(median_seconds=medians,maximum_parameter_difference_from_kress64=differences,
        successful_runs=sum(r['success'] for r in rows),runs=len(rows),
        frozen_controls={c:dict(seconds=v['seconds_including_compilation'],model_residual=v['residual_norm'],metrics=v['metrics'])
                         for c,v in frozen.items()},changed_since_benchmark=drift,
        renderer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))


if __name__=='__main__': main()
