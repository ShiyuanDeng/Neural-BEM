"""NG-001 paired geometry component study; frozen TG-002 moves, no fitting.

Run in EMNerf with single BLAS/OpenMP threads and PYTHONPATH=solvers:.
Incremental evidence and all failed attempts are retained. Output must be fresh.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import platform
import subprocess
import time
import traceback
from unittest.mock import patch

import numpy as np
import scipy
import torch

from bem_inverse.coefficient_geometry import CoefficientGeometry, CoefficientUnresolved, crop, nu
from bem_inverse.interval_geometry import IntervalGeometry
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.geometry_runtime import geometry_runtime, geometry_batch
from bem_inverse.analytic_projection import projection_derivatives
from bem_inverse.batched import BatchedCertifiedUpdate
from bem_inverse.device_certified import DeviceCertifiedUpdate
from bem_inverse.io import read, write, digest, curve_from, curve_record
from bem_inverse.spectral import spectral_project
from . import campaign

ROOT=campaign.ROOT
PRIOR=ROOT/'results/validation/cleaned_interfaces/GC-001'
UNIT=.05
DIAGNOSTIC={'start','circle__c4','kite__c4','hook__c4','aphex_twin__c4'}


@contextmanager
def no_curve_samples():
    with (patch.object(FourierCurve,'nodes',side_effect=AssertionError('new engine used nodes')),
          patch.object(FourierCurve,'values',side_effect=AssertionError('new engine evaluated curve grid')),
          patch.object(FourierCurve,'from_samples',side_effect=AssertionError('new engine fitted samples'))):
        yield


def sync():
    if torch.cuda.is_available() and torch.cuda.is_initialized():
        torch.cuda.synchronize()


def measured(fn):
    sync()
    begun=time.perf_counter()
    try:
        result=fn()
        sync()
        return result,dict(success=True,seconds=time.perf_counter()-begun)
    except (ValueError,AssertionError,RuntimeError) as exc:
        sync()
        return None,dict(success=False,reason=getattr(exc,'reason',type(exc).__name__),detail=str(exc),
                         receipt=getattr(exc,'receipt',None),seconds=time.perf_counter()-begun)


def error(delta, row):
    # Diagnostics only; acceptance in the new geometry code uses no samples.
    values=FourierCurve(delta).values(2*row['N'])
    return dict(l1_m=UNIT*float(np.sum(np.abs(delta))),l2_m=UNIT*float(np.linalg.norm(delta)),
                maximum_m=UNIT*float(np.max(np.abs(values))),
                l1_relative=float(np.sum(np.abs(delta))/row['sigma0']))


def complex_array(row):
    return np.array([complex(z['real'],z['imag']) for z in row])


def validity(verifier, base, accepted, proposed):
    cheap=verifier.increment(base,accepted,proposed)
    if cheap['outcome']=='valid':
        return dict(**cheap,tier='direct_increment')
    full=verifier.certify(proposed)
    return dict(**full,tier='arc_range_cover',increment_attempt=cheap,
                total_seconds=cheap['seconds']+full['seconds'])


def controls(output):
    curves={'circle':FourierCurve.circle(1.3),'ellipse_gentle':FourierCurve(np.array([.2,0,1.3])),
            'ellipse_thin':FourierCurve(np.array([.8,0,1.3]))}
    for a in (.2,.49,.5,1.):
        c=np.zeros(5,complex)
        c[3:]=[1.,a]
        curves[f'quadratic_{a:g}']=FourierCurve(c)
    results=[]
    for name,small in curves.items():
        curve=FourierCurve(crop(small.coefficients,8))
        verifier=IntervalGeometry()
        with no_curve_samples():
            certificate=verifier.certify(curve.coefficients)
            model,prep=measured(lambda:CoefficientGeometry(curve,2,band=256))
            candidate,trial=(None,None) if model is None else measured(lambda:model.trial(np.array([.001,.0002,0,0,0])))
        entry=dict(id=name,curve=curve_record(curve),certificate=certificate,preparation=prep,trial=trial)
        if candidate is not None:
            base=spectral_project(curve,np.zeros(5),8,8192,UNIT)[0]
            ref=curve.coefficients+spectral_project(curve,np.array([.001,.0002,0,0,0]),8,8192,UNIT)[0]-base
            entry['maximum_coefficient_error_m']=UNIT*float(np.sum(np.abs(candidate[0]-ref)))
            entry['construction_receipt']=candidate[2]
        results.append(entry)
        write(output/'controls.json',results)
    return results


def derivative_panel(row, moves, models, control_space, output):
    if row['id'] not in DIAGNOSTIC or not all(models.values()):
        return
    directions=np.stack([np.asarray(m['coefficients'])/m['size_m'] for m in moves[:3]])
    curve=curve_from(row['curve'])
    analytic,analytic_time=measured(lambda:projection_derivatives(curve,row['M'],curve.band,2*row['N'],UNIT)@directions.T)
    refined,refined_time=measured(lambda:projection_derivatives(curve,row['M'],curve.band,4*row['N'],UNIT)@directions.T)
    def rel(a,b):
        return np.linalg.norm(a-b,axis=0)/np.maximum(np.linalg.norm(b,axis=0),1e-10)
    result=dict(directions=directions,current_full_prepared=control_space.derivatives@directions.T,
                analytic_seconds=analytic_time,refined_seconds=refined_time,
                reference_refinement=None if refined is None or analytic is None else rel(analytic,refined),arms={})
    for name,model in models.items():
        with no_curve_samples():
            tangent,timing=measured(lambda:model.tangent(directions))
        arm=dict(timing=timing)
        if tangent is not None:
            dot,receipt=tangent
            arm.update(receipt=receipt,derivatives=dot,
                       current_relative_errors=rel(dot,control_space.derivatives@directions.T),
                       reference_relative_errors=None if refined is None else rel(dot,refined),finite_differences=[])
            for eps in (1e-7,5e-8):
                differences=[]
                failures=[]
                begin=time.perf_counter()
                for d in directions:
                    with no_curve_samples():
                        plus,p=measured(lambda:model.trial(eps*d))
                        minus,m=measured(lambda:model.trial(-eps*d))
                    failures.extend([x for x in (p,m) if not x['success']])
                    if plus is not None and minus is not None:
                        differences.append((plus[0]-minus[0])/(2*eps))
                arm['finite_differences'].append(dict(step_m=eps,seconds=time.perf_counter()-begin,
                    failures=failures,relative_errors=None if len(differences)!=3 else rel(np.stack(differences,axis=1),dot)))
        result['arms'][name]=arm
        write(output/'derivatives'/f"{row['id']}.json",result)


def state_run(row,output):
    curve=curve_from(row['curve'])
    prior_files=sorted((PRIOR/'precision'/row['id']).glob('*m-d*.json'))
    priors=[read(p) for p in prior_files]
    moves=[r['move'] for r in priors]
    # Canonical ordering preserves the three small-step derivative directions.
    order=np.argsort([m['size_m']*10+m['direction']*1e-12 for m in moves])
    moves=[moves[i] for i in order]
    priors=[priors[i] for i in order]
    write(output/'states'/row['id']/'inputs.json',dict(state=row,moves=moves,
          prior_hashes={str(p.relative_to(ROOT)):digest(p) for p in prior_files}))
    models,preparations={},{}
    for name,B in [('coarse',max(256,4*curve.band)),('fine',max(512,8*curve.band))]:
        with no_curve_samples():
            model,timing=measured(lambda:CoefficientGeometry(curve,row['M'],band=B))
        models[name]=model
        preparations[name]=dict(**timing,working_band=B,receipt=None if model is None else model.receipt)
    verifier=IntervalGeometry()
    with no_curve_samples():
        base_certificate=verifier.certify(curve.coefficients)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    current=DeviceCertifiedUpdate(UNIT,device=device) if device=='cuda' else BatchedCertifiedUpdate(UNIT,device='cpu')
    control_space,control_prep=measured(lambda:current.prepare(curve,row['M'],curve.band))
    if control_space is None:
        raise RuntimeError(f"current preparation failed: {control_prep}")
    preparations['current']=dict(**control_prep,settings=current.settings())
    write(output/'states'/row['id']/'preparation.json',dict(arms=preparations,base_certificate=base_certificate))
    zeros=np.zeros(2*row['M']+1)
    fine_base=spectral_project(curve,zeros,curve.band,2*row['N'],UNIT)[0]
    records=[]
    for move,prior in zip(moves,priors):
        proposals={}
        a=np.asarray(move['coefficients'])
        current_trial,current_time=measured(lambda:current.trial(control_space,a))
        record=dict(state=row['id'],move=move,current=dict(**current_time,accepted=current_trial is not None,
                    tiers=list(current.records)),arms={})
        ref,ref_time=measured(lambda:curve.coefficients+spectral_project(curve,a,curve.band,2*row['N'],UNIT)[0]-fine_base)
        record['reference_time']=ref_time
        if ref is not None:
            archived=complex_array(prior['reference_coefficients'])
            record.update(reference_coefficients=ref,archived_reference_qualified=prior['reference_qualified'],
                          reference_archive_error=error(ref-archived,row))
            if current_trial is not None:
                actual=current_trial[0].coefficients
                record['current'].update(coefficients=actual,receipt=current_trial[1],error=error(actual-ref,row))
                record['reference_refinement']=error(actual-ref,row)
            else:
                coarse=curve.coefficients+spectral_project(curve,a,curve.band,row['N'],UNIT)[0]-control_space.base_projection
                record['reference_refinement']=error(coarse-ref,row)
            record['reference_qualified']=bool(record['reference_refinement']['l1_relative']<=1e-7 and
                                                    record['reference_archive_error']['l1_relative']<=1e-7)
        for name,model in models.items():
            if model is None:
                record['arms'][name]=dict(success=False,reason='base_construction_failed',seconds=0.)
                continue
            with no_curve_samples():
                proposed,timing=measured(lambda:model.trial(a))
            arm=dict(**timing)
            if proposed is not None:
                coefficients,moved,receipt=proposed
                proposals[name]=proposed
                arm.update(coefficients=coefficients,construction_receipt=receipt,
                           error=None if ref is None else error(coefficients-ref,row))
                if name=='coarse':
                    with no_curve_samples():
                        checks={role:validity(verifier,base_certificate,curve.coefficients,c)
                                for role,c in [('moved',moved),('candidate',coefficients)]}
                    arm.update(validity=checks,accepted=all(c['outcome']=='valid' for c in checks.values()))
                    if base_certificate['outcome']=='valid':
                        d=checks['candidate'].get('increment_nu_upper',checks['candidate'].get('increment_attempt',{}).get('increment_nu_upper'))
                        b=base_certificate['lower_W']
                        arm['same_bound_cheap_comparison']=dict(direct=bool(d is not None and d<b),
                            squared=bool(d is not None and 2*nu(curve.coefficients)*d+d*d<b*b))
                elif 'coarse' in proposals:
                    coarse_proof=record['arms']['coarse']['validity']['moved']
                    with no_curve_samples():
                        arm['validity']={'moved':validity(verifier,coarse_proof,proposals['coarse'][1],moved)}
            record['arms'][name]=arm
        if all(record['arms'].get(n,{}).get('success') for n in ('coarse','fine')):
            record['working_band_refinement']=error(complex_array_from_value(record['arms']['coarse']['coefficients'])-
                                                    complex_array_from_value(record['arms']['fine']['coefficients']),row)
            if record['working_band_refinement']['l1_relative']>1e-5:
                record['arms']['coarse']['accepted']=False
                record['arms']['coarse']['accuracy_refusal']='working_band_refinement'
            if record['arms']['fine'].get('validity',{}).get('moved',{}).get('outcome')!='valid':
                record['arms']['coarse']['accepted']=False
                record['arms']['coarse']['accuracy_refusal']='fine_moved_unresolved'
        elif record['arms']['coarse']['success']:
            record['arms']['coarse']['accepted']=False
            record['arms']['coarse']['accuracy_refusal']='fine_construction_unresolved'
        records.append(record)
        write(output/'states'/row['id']/f"{move['id']}.json",record)
    derivative_panel(row,moves,models,control_space,output)
    write(output/'states'/row['id']/'current_counts.json',current.counts)
    return records


def complex_array_from_value(a):
    return np.asarray(a,complex)


def summarize(output):
    output=Path(output)
    paths=sorted((output/'states').glob('*/*m-d*.json'))
    rows=[read(p) for p in paths]
    states=[read(p) for p in sorted((output/'states').glob('*/preparation.json'))]
    result=dict(trials=len(rows),states=len(states),current_accepted=sum(r['current']['accepted'] for r in rows),arms={})
    for name in ('coarse','fine'):
        successful=[r for r in rows if r['arms'][name]['success']]
        qualified=[r for r in successful if r.get('reference_qualified')]
        errors=[r['arms'][name]['error'] for r in qualified]
        stats=lambda x:dict(median=float(np.median(x)),maximum=float(np.max(x)),sum=float(np.sum(x))) if x else None
        result['arms'][name]=dict(constructed=len(successful),qualified_references=len(qualified),
            within_production_gate=sum(e['l1_relative']<=1e-5 for e in errors),
            within_tight_gate=sum(e['l1_relative']<=1e-7 for e in errors),
            l1_error_nm=stats([e['l1_m']*1e9 for e in errors]),sampled_error_nm=stats([e['maximum_m']*1e9 for e in errors]),
            construction_seconds=stats([r['arms'][name]['seconds'] for r in successful]),
            failure_reasons=dict(Counter(r['arms'][name].get('reason') for r in rows if not r['arms'][name]['success'])),
            preparation_seconds=stats([s['arms'][name]['seconds'] for s in states]),
            current_to_construction_ratio=stats([r['current']['seconds']/r['arms'][name]['seconds'] for r in qualified if r['current']['accepted']]))
    result['current_trial_seconds']=stats([r['current']['seconds'] for r in rows])
    result['current_preparation_seconds']=stats([s['arms']['current']['seconds'] for s in states])
    coarse=[r for r in rows if r['arms']['coarse']['success']]
    checks=[c for r in rows for name in ('coarse','fine') for c in r['arms'][name].get('validity',{}).values()]
    result['validity']=dict(accepted=sum(r['arms']['coarse'].get('accepted',False) for r in coarse),
        outcomes=dict(Counter(c['outcome'] for c in checks)),tiers=dict(Counter(c['tier'] for c in checks)),
        disagreement_with_current=sum(r['arms']['coarse'].get('accepted',False)!=r['current']['accepted'] for r in rows),
        seconds=stats([c.get('total_seconds',c['seconds']) for c in checks]),
        base_outcomes=dict(Counter(s['base_certificate']['outcome'] for s in states)),
        base_seconds=stats([s['base_certificate']['seconds'] for s in states]))
    same=[r['arms']['coarse']['same_bound_cheap_comparison'] for r in coarse if 'same_bound_cheap_comparison' in r['arms']['coarse']]
    result['same_bound_cheap_tests']=dict(trials=len(same),direct=sum(c['direct'] for c in same),squared=sum(c['squared'] for c in same))
    paired=[r for r in rows if all(r['arms'][n]['success'] for n in ('coarse','fine'))]
    totals=[r['arms']['coarse']['seconds']+r['arms']['fine']['seconds']+
            sum(c.get('total_seconds',c['seconds']) for n in ('coarse','fine')
                for c in r['arms'][n].get('validity',{}).values()) for r in paired]
    result['complete_new_trial_seconds']=stats(totals)
    result['current_to_complete_new_ratio']=stats([r['current']['seconds']/total for r,total in zip(paired,totals)])
    tangents=[read(p) for p in sorted((output/'derivatives').glob('*.json'))]
    result['tangents']={}
    for name in ('coarse','fine'):
        arms=[t['arms'][name] for t in tangents if t['arms'][name]['timing']['success']]
        errors=[e for a in arms for e in a['reference_relative_errors']]
        self_errors=[e for a in arms for f in a['finite_differences'] if f['relative_errors'] is not None for e in f['relative_errors']]
        result['tangents'][name]=dict(states=len(arms),columns=len(errors),within_gate=sum(e<=1e-3 for e in errors),
                                    reference_relative=stats(errors),finite_difference_relative=stats(self_errors),
                                    three_direction_seconds=stats([a['timing']['seconds'] for a in arms]))
    write(output/'report.json',result)
    return result


def run(output,selected=None):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    begun=time.perf_counter()
    try:
        campaign.verify(require_inputs=True)
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        prior=read(PRIOR/'manifest.json')
        states=prior['states']
        if selected:
            states=[s for s in states if s['id'] in selected.split(',')]
        sources=[Path(__file__),ROOT/'solvers/bem_inverse/coefficient_geometry.py',ROOT/'solvers/bem_inverse/interval_geometry.py',
                 ROOT/'pytest/bem_inverse/test_coefficient_geometry.py',ROOT/'docs/iterations/node_free_geometry/NG-001_plan.md']
        for name in ('spectral.py','geometry.py','certified.py','batched.py','device_certified.py','analytic_projection.py'):
            sources.append(ROOT/'solvers/bem_inverse'/name)
        hashes={str(p.relative_to(ROOT)):digest(p) for p in sources}
        write(output/'manifest.json',dict(experiment='NG-001',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            source_hashes=hashes,prior_manifest_sha256=digest(PRIOR/'manifest.json'),states=states,
            environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,torch=torch.__version__,
                             cuda_available=torch.cuda.is_available(),threads=1),physics_calls=0,
            scope='curve-quadrature-free construction; float64 accuracy residuals; directed interval admissibility',
            current_gpu_preparation=torch.cuda.is_available(),full_jacobian_cost_comparison=False))
        for p in sources:
            target=output/'source_snapshot'/p.relative_to(ROOT)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(p.read_bytes())
        controls(output)
        with geometry_runtime('both'),geometry_batch():
            for i,row in enumerate(states):
                records=state_run(row,output)
                print('STATE',i+1,len(states),row['id'],'constructed',sum(r['arms']['coarse']['success'] for r in records),flush=True)
        changed=[p for p,h in hashes.items() if digest(ROOT/p)!=h]
        write(output/'completion.json',dict(completed=True,total_seconds=time.perf_counter()-begun,source_changes=changed,
                                           no_curve_sample_guards_passed=True,physics_calls=0))
        if changed:
            raise RuntimeError(f'sources changed during measurement: {changed}')
        result=summarize(output)
        print(result,flush=True)
    except BaseException:
        write(output/'failure.json',dict(traceback=traceback.format_exc(),seconds=time.perf_counter()-begun))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/validation/node_free_geometry/NG-001/run-01')
    parser.add_argument('--states',default=None,help='Optional declared subset; full run is default.')
    parser.add_argument('--report',action='store_true')
    args=parser.parse_args()
    if args.report:
        print(summarize(args.output))
    else:
        run(args.output,args.states)
