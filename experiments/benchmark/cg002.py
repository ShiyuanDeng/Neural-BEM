"""CG-002 fixed complex paths to the actual TG-002 measured-data objective."""
import gzip
import json
from pathlib import Path
import resource
import subprocess
from time import perf_counter
import traceback

import numpy as np
from scipy.optimize import newton

from bem_inverse.complex_radius import ComplexDomainError, pseudo_arclength, record_state, track
from bem_inverse.continuation.forward import solve
from bem_inverse.continuation.geometry import FourierCurve
from . import cg001 as C

OUTPUT = C.ROOT/'results/validation/complex_geometry/CG-002/run-01'
SOURCE = C.ROOT/'results/validation/complex_geometry/CG-001/run-02'


def compressed(path, value):
    with gzip.open(path, 'wt') as stream:
        json.dump(C.portable(value), stream, separators=(',', ':'), allow_nan=False)


class RealWindow:
    def __init__(self, model):
        self.model = model

    def state(self, q, t):
        if not -2 <= float(np.real(t)) <= 3:
            raise ComplexDomainError('Real homotopy left registered [-2,3] window')
        return self.model.state(q,t)


def run(output=OUTPUT):
    if output.exists():
        raise FileExistsError('Preserve existing evidence')
    output.mkdir(parents=True)
    started = perf_counter()
    C.ACTIVE_BUDGET = C.Budget(started,300.)
    outcome = dict(status='STARTED')
    summaries = {}
    try:
        C.campaign.verify(require_inputs=True)
        original = json.loads((SOURCE/'manifest.json').read_text())
        sources = original['source_hashes']
        if not all(C.sha(C.ROOT/p)==v for p,v in sources.items()):
            raise ValueError('Qualified numerical sources have changed')
        sources.update({str(Path(__file__).relative_to(C.ROOT)):C.sha(__file__),
            'docs/iterations/complex_geometry/CG-002_plan.md':C.sha(
                C.ROOT/'docs/iterations/complex_geometry/CG-002_plan.md')})
        C.write(output/'manifest.json',dict(experiment='CG-002',source_hashes=sources,
            parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C.ROOT,text=True).strip(),
            qualification_sha256=C.sha(SOURCE/'qualification.json'),
            input_manifest_sha256=original['input_manifest_sha256'],
            case='circle__c13.3',frequency_ghz=1.5,q0=1.3,heights=[.001,.01,.1],
            pal_steps=20000,pal_ds=.0002,workers=1,blas_threads=1))
        model,refined=C.instrument(13.3,(1.5,)),C.instrument(13.3,(1.5,),12)
        real_control=RealWindow(model)
        tangent=model.state(1.3,0)
        direction=np.sign((-tangent['Ft']/tangent['Fq']).real)
        tasks=[('natural',lambda:track(model,1.3,[0.,1.]),False)]
        for sign in (1,-1):
            tasks.append((f'real_arc_{sign:+d}',lambda sign=sign:pseudo_arclength(
                real_control,1.3,0.,direction=sign*direction,steps=20000,ds=.0002),True))
        for height in (.001,.01,.1):
            for sign in (1,-1):
                eta=sign*height
                tasks.append((f'dogleg_{eta:+g}',lambda eta=eta:track(
                    model,1.3,[0.,1j*eta,1+1j*eta,1.]),False))
            tasks.append((f'half_step_{height:g}',lambda height=height:track(
                model,1.3,[0.,1j*height,1+1j*height,1.],max_step=.002),False))
        for name,thunk,is_arc in tasks:
            C.ACTIVE_BUDGET.check()
            before=model.counters()
            result=thunk()
            result['counter_delta']={k:model.counters()[k]-before[k] for k in before}
            result['summary']=C.path_summary(model,result)
            path=output/f'{name}.json.gz'
            compressed(path,result)
            states=result['states']
            indices=set(range(len(states))) if not is_arc else set(
                np.linspace(0,len(states)-1,min(65,len(states)),dtype=int).tolist())
            indices.update([len(states)-1,int(np.argmin([r['margin'] for r in states])),
                            int(np.argmax([abs(r['q'].imag) for r in states]))])
            checks=[]
            for i in sorted(indices):
                r=states[i]; fine=refined.state(r['q'],r['t'])
                checks.append(dict(index=i,field=C.relative(model.jets(r['q'])[0][0],refined.jets(r['q'])[0][0]),
                    stationarity=abs(fine['F'])/fine['scale'],
                    Fq_relative=abs(fine['Fq']-r['Fq'])/max(1.,abs(r['Fq']))))
            endpoints=[]
            if is_arc:
                for a,b in zip(states[:-1],states[1:]):
                    if (a['t'].real-1)*(b['t'].real-1)<=0:
                        q=newton(lambda q:model.state(q,1.)['F'].real,b['q'].real,
                            fprime=lambda q:model.state(q,1.)['Fq'].real,tol=1e-13)
                        if not min(a['q'].real,b['q'].real)-1e-8<=q<=max(a['q'].real,b['q'].real)+1e-8:
                            raise ValueError('t=1 correction left its tracked real bracket')
                        endpoints.append(record_state(model,q,1.))
            elif abs(states[-1]['t']-1.)<=1e-10:
                endpoints=[states[-1]]
            classified=[]
            for endpoint in endpoints:
                q=endpoint['q']; fine=refined.state(q,1.)
                real=abs(q.imag)<=1e-8
                minimum=real and fine['Fq'].real>1e-6 and endpoint['Fq'].real>1e-6
                audited=abs(fine['F'])/fine['scale']<=1e-8
                check=dict(q=q,real=real,minimum=bool(minimum),stationarity=abs(fine['F'])/fine['scale'],
                    Fq=fine['Fq'],data_loss=model.real_loss(q) if real else None)
                if real:
                    obs=model.observations[0]
                    reference=[solve(FourierCurve.circle(q.real),obs.wavenumber,model.contrast,
                        obs.acquisition,n,execution_backend='cpu').prediction for n in (512,1024)]
                    exact=model.jets(q.real)[0][0]*model.scales[0]
                    check.update(nodal_error=C.relative(exact,reference[1]),
                                 nodal_refinement=C.relative(reference[0],reference[1]))
                    audited=audited and max(check['nodal_error'],check['nodal_refinement'])<=1e-8
                check['qualified_real_minimum']=bool(minimum and audited)
                classified.append(check)
            result['refined_checks']=checks
            result['t1_endpoints']=classified
            result['numerically_qualified']=bool(max(c['field'] for c in checks)<=1e-8 and
                max(c['stationarity'] for c in checks)<=1e-8 and
                max(c['Fq_relative'] for c in checks)<=1e-8)
            compressed(path,result)
            summaries[name]=dict(**result['summary'],numerically_qualified=result['numerically_qualified'],
                t1_endpoints=classified,counter_delta=result['counter_delta'])
            C.write(output/'summary_progress.json',summaries)
            print('ARM',name,summaries[name],flush=True)
        comparisons={}
        for height in (.001,.01,.1):
            a=summaries[f'dogleg_{height:+g}']['endpoint_q']
            b=summaries[f'dogleg_{-height:+g}']['endpoint_q']
            h=summaries[f'half_step_{height:g}']['endpoint_q']
            comparisons[str(height)]=dict(conjugate_error=abs(a-np.conj(b)),half_step_error=abs(a-h))
        passes=all(s['numerically_qualified'] for s in summaries.values()) and all(
            max(row.values())<=1e-7 for row in comparisons.values())
        positive=[summaries[f'dogleg_{height:+g}'] for height in (.001,.01,.1)]
        returned=sum(any(e['qualified_real_minimum'] for e in s['t1_endpoints']) for s in positive)
        outcome=dict(status=('REAL_MINIMUM_RETURNED' if returned else 'NO_REAL_RETURN_IN_TESTED_ROUTES')
            if passes else 'NUMERICAL_QUALIFICATION_FAILED',positive_real_minima=returned,
            summaries=summaries,comparisons=comparisons,counters=model.counters(),refined_counters=refined.counters(),
            sources_unchanged=all(C.sha(C.ROOT/p)==v for p,v in sources.items()))
    except Exception:
        outcome=dict(status='EXCEPTION',traceback=traceback.format_exc(),summaries=summaries)
        print(outcome['traceback'],flush=True)
    outcome.update(seconds=perf_counter()-started,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    C.write(output/'outcome.json',outcome)
    print('OUTCOME',outcome['status'],outcome['seconds'],flush=True)
    return outcome


if __name__=='__main__':
    answer=run()
    if answer['status']=='EXCEPTION':
        raise SystemExit(1)
