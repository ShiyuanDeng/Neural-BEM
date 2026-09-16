"""Summarize saved inverse runs; does not rerun or retime the experiments."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from .inverse import ShapeChart
from .run_inverse import boundary,save


def main():
    os.environ.setdefault('MPLCONFIGDIR','/tmp/modal_muller_matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=Path('results/experiments/modal_muller_20260916')
    load=lambda path: json.loads((root/path).read_text())
    rows=load('hadamard_inverse/summary.json')
    adaptive=load('adaptive_shape_modes/summary.json')
    cases=['clean','noise_1pct','unmodeled_mode7']
    arms=['nodal64','native_hadamard','nodal_hadamard']
    labels=['Nodal operator derivative','Modal reciprocity derivative','Nodal reciprocity derivative']
    colors=['#c76a2c','#7051a5','#157b78']
    medians={case:{arm:float(np.median([r['seconds'] for r in rows
        if r['case']==case and r['arm']==arm])) for arm in arms} for case in cases}
    fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
    fig.suptitle('Modal Müller inverse: faster derivatives and residual-driven shape modes',fontsize=15)
    ax=axes[0,0]
    for index,(arm,label,color) in enumerate(zip(arms,labels,colors)):
        values=[medians[case][arm] for case in cases]
        bars=ax.bar(np.arange(3)+(index-1)*.24,values,.23,label=label,color=color)
        ax.bar_label(bars,labels=[f'{v:.3f}' for v in values],padding=3,fontsize=8)
    ax.set(xticks=np.arange(3),xticklabels=['Clean','1% noise','Missing mode + noise'],
           ylabel='Whole inverse time (s; log scale)',yscale='log',ylim=(.06,12),
           title='Median of 3 runs; initial model has 9 parameters')
    ax.legend(fontsize=8,loc='upper left')
    ax.grid(axis='y',alpha=.15)
    raw=load('hadamard_inverse/unmodeled_mode7_inputs.json')
    before=load('hadamard_inverse/unmodeled_mode7_native_hadamard_0.json')
    after=load('adaptive_shape_modes/unmodeled_mode7.json')
    truth=boundary(ShapeChart(modes=tuple(raw['truth_modes'])),raw['truth'])
    xy_before=boundary(ShapeChart(modes=tuple(raw['fit_modes'])),before['parameters'])
    xy_after=boundary(ShapeChart(modes=tuple(after['final_modes'])),after['final_parameters'])
    ax=axes[0,1]
    for xy,label,color,style in [(truth,'Truth','black','-'),
                               (xy_before,'Before enrichment','#c76a2c','--'),
                               (xy_after,'After adding mode 7','#157b78',':')]:
        xy=(xy-.5)*1000
        ax.plot(xy[:,0],xy[:,1],color=color,linestyle=style,label=label,lw=1.7)
    ax.set(xlabel='x − 0.5 m (mm)',ylabel='y − 0.5 m (mm)',aspect='equal',
           title='An absent shape mode, selected without truth')
    ax.legend(fontsize=8)
    ax=axes[1,0]
    angles=np.arange(len(truth))*360/len(truth)
    for xy,label,color in [(xy_before,'Before: RMS 0.681 mm','#c76a2c'),
                           (xy_after,'After: RMS 0.061 mm','#157b78')]:
        ax.plot(angles,1000*np.linalg.norm(xy-truth,axis=1),label=label,color=color)
    ax.set(xlabel='Boundary parameter (degrees)',ylabel='Corresponding-point error (mm)',
           xlim=(0,360),title='Adding mode 7 reduces the geometric error by 11×')
    ax.legend(fontsize=8)
    ax.grid(alpha=.15)
    ax=axes[1,1]
    modes=[4,6,7,8]
    for index,(case,label,color) in enumerate([
            ('noise_1pct','Noise only: no mode selected','#7051a5'),
            ('unmodeled_mode7','Missing mode + noise: mode 7 selected','#157b78')]):
        record=load('adaptive_shape_modes/'+case+'.json')
        ranking={r['mode']:r['predicted_loss_decrease'] for r in record['selection']['ranking']}
        ax.bar(np.arange(4)+(index-.5)*.34,[ranking[m] for m in modes],.33,label=label,color=color)
    ax.axhline(record['selection']['noise_threshold'],color='black',ls='--',lw=1,
               label='Exploratory noise threshold')
    ax.set(xticks=np.arange(4),xticklabels=modes,xlabel='Candidate shape harmonic',
           ylabel='Predicted loss decrease',yscale='log',ylim=(8e-8,4e-4),
           title='Residual scores after removing existing shape directions')
    ax.legend(fontsize=8,loc='upper left')
    fig.savefig(root/'inverse_findings.png',dpi=180)
    fig.savefig(root/'inverse_findings.pdf')
    save(root/'inverse_findings.json',dict(median_seconds=medians,adaptive=adaptive,
        timing_scope='All inverse work; excludes independent data generation and final validation. '
                     'Mode enrichment is additional and is not included in the base timing bars.',
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in Path('experiments/modal_muller_research').glob('*.py')}))


if __name__=='__main__':
    main()
