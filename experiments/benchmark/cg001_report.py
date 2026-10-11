"""Read-only combined Track12 report; never evaluates fields or fits a shape."""
import gzip
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'results/validation/complex_geometry'


def read(path):
    if str(path).endswith('.gz'):
        with gzip.open(path,'rt') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def complex_array(states,key):
    return np.array([complex(*row[key]) for row in states])


def validate():
    first=BASE/'CG-001/run-02'; completion=BASE/'CG-001/run-03'; second=BASE/'CG-002/run-01'
    qual=read(first/'qualification.json'); local=read(first/'continuation.json')
    done=read(completion/'completion.json'); end=read(second/'outcome.json')
    assert qual['passed'] and done['control_passed']
    assert done['initial_200_step_reproduction']==0
    assert local['status']=='UNQUALIFIED_TRANSPORT' and not local['arclength_crossed_fold']
    assert done['verdict']=='QUALIFIED_LOCAL_MONODROMY'
    count=sum(sum(f['qualified'] and 0<=f['t']<=1 for f in read(p)['folds']) for p in first.glob('census_*.json'))
    assert count==134
    assert len(end['summaries'])==12 and end['positive_real_minima']==0
    max_field=max_stationarity=max_hessian=0.
    for path in second.glob('*.json.gz'):
        receipt=read(path)
        assert receipt['numerically_qualified']
        for check in receipt['refined_checks']:
            max_field=max(max_field,check['field'])
            max_stationarity=max(max_stationarity,check['stationarity'])
            max_hessian=max(max_hessian,check['Fq_relative'])
        if path.name.startswith(('dogleg','half_step')):
            assert receipt['summary']['status']=='COMPLETED'
            assert len(receipt['t1_endpoints'])==1
            ep=receipt['t1_endpoints'][0]
            assert not ep['real'] and abs(ep['q'][1])>1e-8
    assert max_field<=1e-8 and max_stationarity<=1e-8 and max_hessian<=1e-8
    for row in end['comparisons'].values():
        assert max(row.values())<=1e-7
    return dict(validated=True,detected_qualified_folds_0_to_1=count,
        cg002_arms=12,cg002_positive_real_returns=0,
        maximum_cg002_field_refinement=max_field,
        maximum_cg002_scaled_stationarity=max_stationarity,
        maximum_cg002_hessian_refinement=max_hessian)


def report():
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt']='track12-cg001-cg002'
    import matplotlib.pyplot as plt
    checked=validate()
    first=BASE/'CG-001/run-02'; completion=BASE/'CG-001/run-03'; second=BASE/'CG-002/run-01'
    output=BASE/'report'; output.mkdir(exist_ok=True)
    local=read(first/'continuation.json'); endpoint=read(second/'outcome.json')
    fold=local['fold']; qf=fold['q']
    fig,axes=plt.subplots(2,3,figsize=(15,8.4),constrained_layout=True)
    blue,orange,green,red='#315b9e','#d28126','#39865a','#b94343'
    real=read(completion/'path_arclength_completed.json')['states']
    natural=read(first/'path_natural.json')['states']
    loop=read(first/'path_one_loop.json')['states']
    for states,color,label in ((real,green,'Real pseudo-arclength'),(natural,red,'Natural parameter')):
        axes[0,0].plot((complex_array(states,'q').real-qf)*50,complex_array(states,'t').real,
                       color=color,lw=2,label=label)
    axes[0,0].scatter([0],[fold['t']],marker='x',s=60,color='black',label='Qualified fold',zorder=4)
    axes[0,0].scatter([(complex(*loop[-1]['q']).real-qf)*50],[loop[-1]['t'][0]],
                      color=orange,s=35,label='After one complex loop',zorder=4)
    axes[0,0].set(title='A. Real continuation also passes the fold',xlabel='Radius minus fold radius (mm)',ylabel='Data parameter t')
    ts=complex_array(loop,'t'); qs=complex_array(loop,'q')
    axes[0,1].plot(ts.real,ts.imag,color=blue,lw=2)
    axes[0,1].scatter([fold['t']],[0],color='black',marker='x',label='Fold value')
    axes[0,1].scatter([ts[0].real],[ts[0].imag],color=green,s=35,label='Start / end parameter')
    axes[0,1].set(title='B. One loop in complex data space',xlabel='Re(t)',ylabel='Im(t)')
    axes[0,2].plot((qs.real-qf)*50,qs.imag*50,color=blue,lw=2)
    axes[0,2].scatter([(qs[0].real-qf)*50],[qs[0].imag*50],color=green,s=35,label='Start: minimum')
    axes[0,2].scatter([(qs[-1].real-qf)*50],[qs[-1].imag*50],color=orange,s=35,label='Return: maximum')
    axes[0,2].set(title='C. The loop exchanges real stationary roots',xlabel='Re(radius) minus fold radius (mm)',ylabel='Im(radius) (mm)')
    colors=['#355c9d','#a34482','#d77a25']
    for height,color in zip((.001,.01,.1),colors):
        states=read(second/f'dogleg_{height:+g}.json.gz')['states']
        t=complex_array(states,'t');q=complex_array(states,'q')
        axes[1,0].plot(t.real,t.imag,color=color,lw=1.5,label=f'Height {height:g}')
        axes[1,1].plot(t.real,q.imag*50,color=color,lw=1.5,label=f'Height {height:g}')
    axes[1,0].set(title='D. Three fixed routes to measured data',xlabel='Re(t)',ylabel='Im(t)',xlim=(-.02,1.02))
    axes[1,1].set(title='E. All three reach the same nonreal endpoint',xlabel='Re(t)',ylabel='Im(radius) (mm)')
    heights=np.array([.001,.01,.1])
    for sign,color,label in ((1,blue,'Upper paths'),(-1,orange,'Lower paths')):
        values=[endpoint['summaries'][f'dogleg_{sign*h:+g}']['endpoint_q'][1]*50 for h in heights]
        axes[1,2].plot(heights,values,'o-',color=color,label=label)
    axes[1,2].axhline(0,color='black',lw=.8,label='Required: real radius')
    axes[1,2].set(title='F. No real endpoint in the tested route family',xlabel='Detour height |Im(t)|',
                  ylabel='Endpoint Im(radius) (mm)',xscale='log')
    for ax in axes.flat:
        ax.grid(alpha=.16)
        ax.legend(fontsize=8,loc='best')
        ax.tick_params(labelsize=8)
    axes[0,1].legend(fontsize=8,loc='upper right')
    fig.suptitle('Track 12 · Local fold transport succeeds; tested paths have no real return\n'
                 'Exact transmission disk, fixed center · TG-002 circle data · contrast 13.3 · 1.5 GHz',fontsize=13)
    fig.savefig(output/'track12.png',dpi=190)
    fig.savefig(output/'track12.svg',metadata={'Date':None})
    svg=output/'track12.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)
    (output/'validation.json').write_text(json.dumps(checked,indent=2)+'\n')
    lines=['# Track 12 — saved evidence report','',
        'CG-001: qualified local complex branch exchange, with a successful real pseudo-arclength control.',
        'CG-002: 0/3 fixed positive doglegs returned to a real shape at t=1; conjugate and half-step controls agree.',
        '', '![Track 12](track12.png)', '',
        '| Route height | Endpoint real radius (mm) | Endpoint imaginary radius (mm) | Half-step difference (q units) |',
        '|---:|---:|---:|---:|']
    for h in heights:
        q=endpoint['summaries'][f'dogleg_{h:+g}']['endpoint_q']
        lines.append(f'| {h:g} | {q[0]*50:.9f} | {q[1]*50:.9f} | {endpoint["comparisons"][str(h)]["half_step_error"]:.3g} |')
    lines+=['','This report reads saved JSON only. Fixed-center radius studies do not establish unrestricted shape recovery.',
            '', '[Local mechanism](../CG-001/run-03/completion.json) · [Endpoint study](../CG-002/run-01/outcome.json)', '']
    (output/'README.md').write_text('\n'.join(lines))
    print(json.dumps(checked,indent=2))


if __name__=='__main__':
    report()
