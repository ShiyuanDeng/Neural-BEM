"""NG-002 targeted follow-up; frozen numerical controls, no inverse fitting."""
import argparse
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np

from bem_inverse.coefficient_geometry import CoefficientGeometry
from bem_inverse.interval_geometry import IntervalGeometry
from bem_inverse.io import read,write,digest,curve_from
from bem_inverse.analytic_projection import projection_derivatives
from bem_inverse.spectral import spectral_project
from .ng001 import ROOT,UNIT,DIAGNOSTIC,no_curve_samples,measured,error,complex_array

PRIOR=ROOT/'results/validation/node_free_geometry/NG-001/run-02'


def models_for(curve,M,output,engine_kwargs=None):
    cache={}
    def model(B):
        if B not in cache:
            with no_curve_samples():
                obj,timing=measured(lambda:CoefficientGeometry(curve,M,band=B,
                    **({'speed_method':'newton'} if engine_kwargs is None else engine_kwargs)))
            cache[B]=(obj,timing)
            write(output/'preparations.json',{str(b):dict(t,construction_receipt=None if m is None else m.receipt)
                                            for b,(m,t) in cache.items()})
        return cache[B]
    return model,cache


def tangents(row,old,model,output):
    if row['id'] not in DIAGNOSTIC:
        return
    curve=curve_from(row['curve'])
    directions=np.array([r['move']['coefficients'] for r in old[:3]])/old[0]['move']['size_m']
    B=max(256,4*curve.band)
    while B<=2048:
        if model(B)[0] is not None and model(2*B)[0] is not None:
            break
        B*=2
    if B>2048:
        write(output/'tangent.json',dict(success=False,reason='no_base_pair'))
        return
    reference=projection_derivatives(curve,row['M'],curve.band,4*row['N'],UNIT)@directions.T
    check=projection_derivatives(curve,row['M'],curve.band,2*row['N'],UNIT)@directions.T
    prior=read(PRIOR/'derivatives'/f"{row['id']}.json")
    current=np.array([complex_array(r) for r in prior['current_full_prepared']])
    rel=lambda a,b:np.linalg.norm(a-b,axis=0)/np.maximum(np.linalg.norm(b,axis=0),1e-10)
    result=dict(success=True,reference_refinement=rel(check,reference),directions=directions,arms={})
    for b in (B,2*B):
        obj=model(b)[0]
        with no_curve_samples():
            tangent,timing=measured(lambda:obj.tangent(directions))
        arm=dict(timing=timing)
        if tangent is not None:
            dot,receipt=tangent
            arm.update(receipt=receipt,reference_relative=rel(dot,reference),current_relative=rel(dot,current),
                       derivatives=dot,finite_difference_relative=[])
            for eps in (1e-7,5e-8):
                columns=[]
                for d in directions:
                    with no_curve_samples():
                        plus,p=measured(lambda:obj.trial(eps*d))
                        minus,m=measured(lambda:obj.trial(-eps*d))
                    if plus is not None and minus is not None:
                        columns.append((plus[0]-minus[0])/(2*eps))
                arm['finite_difference_relative'].append(dict(step_m=eps,completed=len(columns),
                    errors=None if len(columns)!=3 else rel(np.stack(columns,axis=1),dot)))
        result['arms'][str(b)]=arm
    write(output/'tangent.json',result)


def state(row,output,engine_kwargs=None,coarse_limit=2048):
    curve=curve_from(row['curve'])
    folder=output/'states'/row['id']
    files=list((PRIOR/'states'/row['id']).glob('*m-d*.json'))
    old=sorted([read(p) for p in files],key=lambda r:(r['move']['size_m'],r['move']['direction']))
    write(folder/'inputs.json',dict(state=row,prior_files={str(p.relative_to(ROOT)):digest(p) for p in files}))
    model,cache=models_for(curve,row['M'],folder,engine_kwargs)
    fixed_B=max(256,4*curve.band)
    records=[]
    for prior in old:
        a=np.array(prior['move']['coefficients'])
        trials={}
        def trial(b):
            if b not in trials:
                obj,preparation=model(b)
                if obj is None:
                    trials[b]=(None,dict(success=False,reason='base_construction_failed',seconds=0.,
                                         base_reason=preparation.get('reason')))
                else:
                    with no_curve_samples():
                        proposed,timing=measured(lambda:obj.trial(a))
                    trials[b]=(proposed,timing)
            return trials[b]
        started=time.perf_counter()
        B=fixed_B
        selected=None
        while B<=coarse_limit:
            coarse,c=trial(B)
            fine,f=trial(2*B)
            if coarse is not None and fine is not None:
                refinement=error(coarse[0]-fine[0],row)
                if refinement['l1_relative']<=1e-5:
                    selected=(B,coarse,fine,refinement)
                    break
            if time.perf_counter()-started>20:
                break
            B*=2
        record=dict(state=row['id'],move=prior['move'],reference_qualified=prior['reference_qualified'],
            current_accepted=prior['current']['accepted'],baseline_coarse=prior['arms']['coarse']['success'],
            attempts={str(b):dict(t,construction_receipt=None if p is None else p[2]) for b,(p,t) in trials.items()},
            fixed_band_coarse_constructed=trials[fixed_B][0] is not None,
            fixed_band_pair=bool(trials[fixed_B][0] is not None and trials[2*fixed_B][0] is not None),
            success=selected is not None,total_seconds=time.perf_counter()-started,admissibility_checked=False)
        if selected is not None:
            b,coarse,fine,refinement=selected
            reference=complex_array(prior['reference_coefficients'])
            record.update(selected_band=b,coefficients=coarse[0],fine_coefficients=fine[0],
                          working_band_refinement=refinement,error=error(coarse[0]-reference,row),
                          fine_error=error(fine[0]-reference,row))
        records.append(record)
        write(folder/f"{prior['move']['id']}.json",record)
    tangents(row,old,model,folder)
    print('STATE',row['id'],'fixed',sum(r['fixed_band_coarse_constructed'] for r in records),
          'escalated_pairs',sum(r['success'] for r in records),flush=True)


def controls(output):
    results=[]
    for old in read(PRIOR/'controls.json'):
        curve=curve_from(old['curve'])
        result=dict(id=old['id'],attempts=[])
        with no_curve_samples():
            result['certificate']=IntervalGeometry().certify(curve.coefficients)
        for B in (256,512,1024,2048,4096):
            with no_curve_samples():
                obj,timing=measured(lambda:CoefficientGeometry(curve,2,band=B,speed_method='newton'))
            result['attempts'].append(dict(timing,band=B,construction_receipt=None if obj is None else obj.receipt))
            if obj is not None:
                reference=spectral_project(curve,np.zeros(5),curve.band,16384,UNIT)[0]
                result['prepared']=True
                result['base_l1_error_m']=UNIT*float(np.sum(np.abs(obj.base-reference)))
                break
        result.setdefault('prepared',False)
        results.append(result)
        write(output/'controls.json',results)


def summarize(output):
    from collections import Counter
    output=Path(output)
    rows=[read(p) for p in (output/'states').glob('*/*m-d*.json')]
    proofs=read(output/'base_certificates.json')
    successful=[r for r in rows if r['success'] and r['reference_qualified']]
    stats=lambda x:None if not x else dict(count=len(x),median=float(np.median(x)),maximum=float(np.max(x)),sum=float(np.sum(x)))
    tangents=[read(p) for p in (output/'states').glob('*/tangent.json')]
    arms=[a for t in tangents if t['success'] for a in t['arms'].values() if a['timing']['success']]
    def final_reason(r):
        largest=max(map(int,r['attempts']))
        for b in (largest//2,largest):
            attempt=r['attempts'][str(b)]
            if not attempt['success']:
                return attempt.get('base_reason',attempt.get('reason'))
        return 'band_refinement'
    result=dict(trials=len(rows),baseline_coarse_constructed=sum(r['baseline_coarse'] for r in rows),
        newton_fixed_coarse_constructed=sum(r['fixed_band_coarse_constructed'] for r in rows),
        fixed_band_gains=sum(not r['baseline_coarse'] and r['fixed_band_coarse_constructed'] for r in rows),
        fixed_band_regressions=sum(r['baseline_coarse'] and not r['fixed_band_coarse_constructed'] for r in rows),
        newton_fixed_pairs=sum(r['fixed_band_pair'] for r in rows),escalated_pairs=sum(r['success'] for r in rows),
        qualified_references=len(successful),production_accurate=sum(r['error']['l1_relative']<=1e-5 for r in successful),
        tight_accurate=sum(r['error']['l1_relative']<=1e-7 for r in successful),
        l1_error_nm=stats([r['error']['l1_m']*1e9 for r in successful]),
        selected_bands=dict(Counter(r['selected_band'] for r in successful)),
        failure_final_reasons=dict(Counter(final_reason(r) for r in rows if not r['success'])),
        all_attempt_seconds=stats([r['total_seconds'] for r in rows]),
        by_size={str(s):dict(trials=sum(r['move']['size_m']==s for r in rows),
            fixed_constructed=sum(r['move']['size_m']==s and r['fixed_band_coarse_constructed'] for r in rows),
            escalated_pairs=sum(r['move']['size_m']==s and r['success'] for r in rows)) for s in (1e-7,.001,.006)},
        interval_bases=dict(old_valid=sum(p['baseline']['outcome']=='valid' for p in proofs),
            new_valid=sum(p['new']['outcome']=='valid' for p in proofs),
            old_seconds=stats([p['baseline']['seconds'] for p in proofs]),
            new_seconds=stats([p['new']['seconds'] for p in proofs])),
        tangents=dict(states=sum(t['success'] for t in tangents),columns_in_both_bands=sum(len(a['reference_relative']) for a in arms),
            reference_relative=stats([e for a in arms for e in a['reference_relative']]),
            finite_difference_relative=stats([e for a in arms for f in a['finite_difference_relative']
                                              if f['errors'] is not None for e in f['errors']]),
            reference_refinement=stats([e for t in tangents if t['success'] for e in t['reference_refinement']])),
        certified_newton_moves='not measured',physics_calls=0)
    write(output/'report.json',result)
    return result


def run(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    begun=time.perf_counter()
    sources=[Path(__file__),ROOT/'solvers/bem_inverse/coefficient_geometry.py',ROOT/'solvers/bem_inverse/interval_geometry.py',
        ROOT/'pytest/bem_inverse/test_coefficient_geometry.py',ROOT/'docs/iterations/node_free_geometry/NG-002_plan.md',
        ROOT/'docs/iterations/node_free_geometry/NG-001_newton_derivation.md',ROOT/'experiments/benchmark/ng001.py',
        ROOT/'solvers/bem_inverse/analytic_projection.py',ROOT/'solvers/bem_inverse/spectral.py']
    hashes={str(p.relative_to(ROOT)):digest(p) for p in sources}
    manifest=read(PRIOR/'manifest.json')
    write(output/'manifest.json',dict(experiment='NG-002',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_hashes=hashes,prior_manifest_sha256=digest(PRIOR/'manifest.json'),states=manifest['states'],
        frozen_control=True,complete_trial_comparison=False,physics_calls=0))
    for p in sources:
        target=output/'source_snapshot'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(p.read_bytes())
    try:
        controls(output)
        proofs=[]
        for row in manifest['states']:
            curve=curve_from(row['curve'])
            baseline=read(PRIOR/'states'/row['id']/'preparation.json')['base_certificate']
            with no_curve_samples():
                certificate=IntervalGeometry().certify(curve.coefficients)
            proofs.append(dict(state=row['id'],baseline=baseline,new=certificate))
            write(output/'base_certificates.json',proofs)
            state(row,output)
        changed=[p for p,h in hashes.items() if digest(ROOT/p)!=h]
        if changed:
            raise RuntimeError(f'Measured sources changed: {changed}')
        write(output/'completion.json',dict(completed=True,total_seconds=time.perf_counter()-begun,source_changes=changed,
                                           no_curve_sample_guards_passed=True,physics_calls=0))
        print(summarize(output),flush=True)
    except BaseException:
        write(output/'failure.json',dict(traceback=traceback.format_exc(),seconds=time.perf_counter()-begun))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/validation/node_free_geometry/NG-002/run-01')
    parser.add_argument('--report',action='store_true')
    args=parser.parse_args()
    print(summarize(args.output)) if args.report else run(args.output)
