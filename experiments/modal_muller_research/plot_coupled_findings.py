"""Plot saved coupled recoveries and derivative benchmarks without rerunning them."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from .run_frequency_design import chart_from_record
from .run_inverse import boundary,save


def main():
    os.environ.setdefault('MPLCONFIGDIR','/tmp/modal_muller_matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9})
    root=Path('results/experiments/modal_muller_20260916/coupled_inverse')
    load=lambda name: json.loads((root/name).read_text())
    raw=load('missing_two_modes_inputs.json')
    before=load('missing_two_modes_native_dense_0.json')
    first=load('missing_two_modes_enrichment.json')
    final=load('frequency_design/missing_two_modes.json')
    control=load('frequency_design/noise_1pct.json')
    actions=load('action_benchmark.json')
    fig=plt.figure(figsize=(14,8.2),layout='constrained')
    grid=fig.add_gridspec(2,3)
    fig.suptitle('Coupled modal inversion: locate a missing harmonic, then choose data that can see it',fontsize=15)
    ax=fig.add_subplot(grid[0,:2])
    stages=[(raw['truth_chart'],raw['truth'],'Truth','black','-',2.4),
            (raw['chart'],before['parameters'],'Initial fitted model','#c76a2c','--',1.5),
            (first['final_chart'],first['final_parameters'],'After left mode 5','#7051a5','-.',1.4),
            (final['final_chart'],final['final_parameters'],'After 2.5 GHz + right mode 7','#157b78',':',1.8)]
    for record,parameters,label,color,style,width in stages:
        chart=chart_from_record(record);x=np.array(parameters)
        for index,(c,sl) in enumerate(zip(chart.charts,chart.slices)):
            xy=(boundary(c,x[sl])-.5)*1000
            ax.plot(xy[:,0],xy[:,1],label=label if index==0 else None,color=color,ls=style,lw=width)
    ax.set(xlabel='x − 0.5 m (mm)',ylabel='y − 0.5 m (mm)',aspect='equal',
           title='Two interacting objects; 1% measurement noise')
    ax.legend(fontsize=8,loc='upper left')
    ax=fig.add_subplot(grid[0,2])
    for index,(name,color) in enumerate([('Left object','#7051a5'),('Right object','#157b78')]):
        values=[entry['components'][index]['boundary_rms_mm'] for entry in
                [before['metrics'],first['after'],final['after']]]
        bars=ax.bar(np.arange(3)+(index-.5)*.32,values,.3,label=name,color=color)
        ax.bar_label(bars,labels=[f'{v:.3f}' for v in values],padding=3,fontsize=8)
    ax.set(xticks=np.arange(3),xticklabels=['Initial fit','+ left mode 5','+ new data\n+ right mode 7'],
           ylabel='Boundary RMS error (mm; log scale)',yscale='log',ylim=(.012,5),
           title='Combined error: 1.759 → 0.846 → 0.030 mm')
    ax.legend(fontsize=8,loc='upper right');ax.grid(axis='y',alpha=.15)
    ax=fig.add_subplot(grid[1,0])
    for record,label,color in [(final,'Weak right mode 7','#157b78'),(control,'Noise-only candidate','#7051a5')]:
        rows=record['design']['candidates']
        frequencies=[r['frequency_hz']/1e9 for r in rows];score=[r['score'] for r in rows]
        ax.semilogy(frequencies,score,'o-',label=label,color=color)
        chosen=next(r for r in rows if r['frequency_hz']==record['design']['selected_frequency_hz'])
        ax.scatter(chosen['frequency_hz']/1e9,chosen['score'],s=160,facecolors='none',edgecolors=color,lw=2)
    ax.set(xlabel='Candidate extra frequency (GHz)',ylabel='Projected sensitivity score',
           title='Choose frequency from the current estimate')
    ax.legend(fontsize=8);ax.grid(alpha=.15)
    ax=fig.add_subplot(grid[1,1])
    for index,(key,label,color) in enumerate([('dense_array_bytes','Explicit Jacobian','#c76a2c'),
                                           ('trace_array_bytes','Trace/coefficient arrays','#157b78')]):
        values=[r[key]/1e6 for r in actions]
        bars=ax.bar(np.arange(3)+(index-.5)*.32,values,.3,label=label,color=color)
        ax.bar_label(bars,labels=[f'{v:.2f}' for v in values],padding=3,fontsize=8)
    ax.set(xticks=np.arange(3),xticklabels=['24 × 24','96 × 96','192 × 192'],yscale='log',ylim=(.1,250),
           xlabel='Receiver × source count',ylabel='Derivative array payload (MB)',
           title='82 shape parameters; 49 trace modes per trace')
    ax.legend(fontsize=8);ax.grid(axis='y',alpha=.15)
    ax.text(.02,.02,'Excludes forward state and temporary workspaces',transform=ax.transAxes,fontsize=7)
    ax=fig.add_subplot(grid[1,2])
    for key,label,color,style in [('dense_jvp','Explicit Jv','#c76a2c','-'),
                                 ('dense_vjp','Explicit Jᵀw','#c76a2c','--'),
                                 ('trace_jvp','Trace Jv','#157b78','-'),
                                 ('trace_vjp','Trace Jᵀw','#157b78','--')]:
        ax.loglog([r['measurements'] for r in actions],[r['timings'][key]*1000 for r in actions],
                  marker='o',color=color,ls=style,label=label)
    ax.set(xlabel='Measurements per frequency',ylabel='Action time (ms)',
           title='Larger acquisitions benefit; small ones do not')
    ax.legend(fontsize=8);ax.grid(alpha=.15)
    fig.savefig(root/'coupled_findings.png',dpi=180)
    fig.savefig(root/'coupled_findings.pdf')
    rows=load('summary.json')
    medians={case:{arm:float(np.median([r['seconds'] for r in rows if r['case']==case and r['arm']==arm]))
                  for arm in ['native_dense','nodal_dense']} for case in ['clean','noise_1pct','missing_two_modes']}
    save(root/'findings_summary.json',dict(median_inverse_seconds=medians,
        initial_boundary_rms_mm=before['metrics']['boundary_rms_mm'],
        enriched_boundary_rms_mm=first['after']['boundary_rms_mm'],
        final_boundary_rms_mm=final['after']['boundary_rms_mm'],
        final_held_out_error=final['after']['held_out_error'],
        derivative_payload_ratio=actions[-1]['dense_array_bytes']/actions[-1]['trace_array_bytes'],
        jvp_speed_ratio=actions[-1]['timings']['dense_jvp']/actions[-1]['timings']['trace_jvp'],
        vjp_speed_ratio=actions[-1]['timings']['dense_vjp']/actions[-1]['timings']['trace_vjp'],
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in Path('experiments/modal_muller_research').glob('*.py')}))


if __name__=='__main__':
    main()
