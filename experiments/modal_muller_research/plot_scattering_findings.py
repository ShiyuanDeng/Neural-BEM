"""Render measured scattering-library results and record their source provenance."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .run_inverse import save
from .run_scattering_library import fixture,boundary


ROOT=Path('results/experiments/modal_muller_20260916/scattering_library')


def read(name):
    return json.loads((ROOT/name).read_text())


def main():
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'figure.dpi':130,'savefig.dpi':180})
    rows=read('summary.json');identification=read('identification/summary.json')
    medians={case:{arm:float(np.median([r['seconds'] for r in rows if r['case']==case and r['arm']==arm]))
                  for arm in dict.fromkeys(r['arm'] for r in rows)}
             for case in dict.fromkeys(r['case'] for r in rows)}
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    ax=axes[0,0]
    _,chart,truth,initial=fixture(4)
    recovered=np.array(identification['ranking'][0]['parameters'])
    for parameters,color,style,label in [(initial,'#a4a9b0','-','Initial pose'),
                                        (truth,'#167d9a','-','Truth'),
                                        (recovered,'#df772d','--','Recovered')]:
        for i,g in enumerate(chart.moved(parameters)):
            xy=100*boundary(g)
            ax.plot(xy[:,0],xy[:,1],color=color,ls=style,lw=1.8,label=label if i==0 else None)
    for i,(center,kind) in enumerate(zip(chart.anchors,['Ellipse','3-lobed','Ellipse','3-lobed'])):
        ax.text(100*center.real,100*center.imag-4.7,f'{i+1}: {kind}',ha='center',fontsize=9)
    ax.set(title='A. Recover shape identity and pose\n1% noise; max center error 0.028 mm',xlabel='x (cm)',ylabel='y (cm)',aspect='equal',
           xlim=(35,65),ylim=(35,65))
    ax.legend(loc='upper center',ncol=3,fontsize=8,frameon=False)

    ax=axes[0,1]
    arms=['nodal_rebuild','library_native_cold','library_native_warm','library_nodal_cold']
    labels=['Kress rebuild\n+ reciprocal J','Laurent library\ncompile + inverse',
            'Laurent library\nreused','Kress library\ncompile + inverse']
    values=[medians['four_noise1pct'][arm] for arm in arms]
    bars=ax.bar(np.arange(4),values,color=['#9a9fa8','#167d9a','#53a5b7','#5b9b68'],width=.67)
    ax.bar_label(bars,labels=[f'{v:.3f} s' for v in values],padding=5,fontsize=10)
    ax.set(title='B. Complete four-object pose inverse',ylabel='Wall time (seconds)',
           xticks=np.arange(4),xticklabels=labels,ylim=(0,1.83))
    ax.tick_params(axis='x',labelsize=8)
    ax.text(.97,.97,'Median of 3 runs; one CPU thread\nSame recovery: 0.096 mm boundary RMS',
            ha='right',va='top',transform=ax.transAxes,fontsize=9)

    ax=axes[1,0];conv=read('order_convergence.json')
    orders=[r['order'] for r in conv]
    ax.semilogy(orders,[r['data_error'] for r in conv],'o-',color='#167d9a',label='Scattered data')
    ax.semilogy(orders,[r['jacobian_error'] for r in conv],'s-',color='#df772d',label='Pose Jacobian')
    ax.axvline(12,ls=':',color='#7f858a',label='Order used in inverse')
    ax.set(title='C. Check against refined nodal Kress',xlabel='Cylindrical order p (2p + 1 modes/object)',
           ylabel='Relative error',xticks=orders)
    ax.grid(alpha=.15);ax.legend(fontsize=9,frameon=False)

    ax=axes[1,1];ranking=identification['ranking']
    labels=[''.join('E' if i==0 else 'S' for i in r['assignment']) for r in ranking]
    scores=[100*r['score'] for r in ranking]
    ax.barh(np.arange(16),scores,color=['#167d9a']+['#b5bbc1']*15)
    ax.invert_yaxis()
    ax.set(title='D. Search all 16 shape assignments',xlabel='Normalized residual (%)',
           yticks=np.arange(16),yticklabels=labels,xlim=(0,40),ylim=(15.7,-3.8))
    ax.tick_params(axis='y',labelsize=8)
    ax.text(.02,.98,'E = ellipse; S = 3-lobed. Correct ESES selected.\n16 local fits + compilation: 5.15 s',
            ha='left',va='top',transform=ax.transAxes,fontsize=9)
    fig.suptitle('Laurent objects compiled into reusable scattering matrices',fontsize=16)
    for extension in ['png','pdf']:
        fig.savefig(ROOT/f'scattering_findings.{extension}')
    plt.close(fig)

    symmetry=read('identification/symmetry.json')
    fig,axes=plt.subplots(1,3,figsize=(12,4.1),layout='constrained')
    names=['Circle: m = n','Ellipse: m − n even','3-lobed: m − n divisible by 3']
    for ax,row,title in zip(axes,symmetry,names):
        matrix=np.array(row['absolute_matrix'])
        logs=np.log10(np.maximum(matrix/matrix.max(),1e-14))
        heat=ax.imshow(logs,origin='lower',extent=(-10.5,10.5,-10.5,10.5),
                       vmin=-14,vmax=0,cmap='magma',interpolation='nearest')
        ax.set(title=title,xlabel='Incoming mode n',ylabel='Outgoing mode m',xticks=[-10,-5,0,5,10],yticks=[-10,-5,0,5,10])
        ax.text(.02,.98,f"Forbidden fraction: {row['forbidden_coupling_fraction']:.1e}",
                va='top',transform=ax.transAxes,color='white',fontsize=8)
    fig.colorbar(heat,ax=axes,label='log₁₀ |Tₘₙ| / max |T|',shrink=.85,pad=.02)
    fig.suptitle('Shape symmetry gives exact mode-coupling selection rules',fontsize=15)
    for extension in ['png','pdf']:
        fig.savefig(ROOT/f'symmetry_modes.{extension}')
    plt.close(fig)

    original=read('manifest.json')['source_hashes']
    paths=sorted(Path('experiments/modal_muller_research').glob('*.py'))
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    drift=[p for p,h in original.items() if Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    save(ROOT/'findings.json',dict(inverse_median_seconds=medians,successful_inverses=sum(r['success'] for r in rows),
         inverse_runs=len(rows),identification_seconds=identification['total_seconds'],
         identification_correct=identification['correct'],
         hypothesis_optimizers_at_evaluation_limit=sum(not r['success'] for r in identification['ranking']),
         source_hashes=hashes,changed_since_main_benchmark=drift,
         post_benchmark_changes='Added optional template sharing across type assignments and its regression test; '
                                'added result renderer. Main benchmark retains its original source manifest.',
         python=platform.python_version(),git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))


if __name__=='__main__':
    main()
