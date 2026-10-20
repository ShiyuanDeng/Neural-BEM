"""NG-004 full nonsampled acceptance of frozen NG-003 paired constructions."""
import argparse
from pathlib import Path
import subprocess
import time
import traceback
from unittest.mock import patch
from collections import Counter

import numpy as np

from bem_inverse.coefficient_geometry import CoefficientGeometry
from bem_inverse.coefficient_validity import certify_pair
from bem_inverse.interval_geometry import IntervalGeometry
from bem_inverse.io import read,write,digest,curve_from
from .ng001 import ROOT,no_curve_samples,measured,complex_array
from .ng003 import OPTIONS

PRIOR=ROOT/'results/validation/node_free_geometry/NG-003/run-01'
CONTROL=ROOT/'results/validation/node_free_geometry/NG-001/run-02'
PROOFS=ROOT/'results/validation/node_free_geometry/NG-002/run-01/base_certificates.json'


def summarize(output):
    output=Path(output)
    rows=[read(p) for p in (output/'states').glob('*/*m-d*.json')]
    stats=lambda x:None if not x else dict(count=len(x),median=float(np.median(x)),maximum=float(np.max(x)),sum=float(np.sum(x)))
    checks=[c for r in rows for c in r.get('validity',{}).get('checks',[])]
    accepted=[r for r in rows if r['accepted']]
    paired=[r for r in rows if 'complete_trial_seconds' in r]
    result=dict(trials=len(rows),current_accepted=sum(r['current_accepted'] for r in rows),
        node_free_accepted=len(accepted),constructed_pairs=sum(r['construction_success'] for r in rows),
        accepted_l1_error_nm=stats([r['error']['l1_m']*1e9 for r in accepted]),
        current_refused_node_free_accepted=sum(r['accepted'] and not r['current_accepted'] for r in rows),
        disagreements=sum(r['accepted']!=r['current_accepted'] for r in rows),
        by_size={str(s):dict(trials=sum(r['move']['size_m']==s for r in rows),
            current_accepted=sum(r['move']['size_m']==s and r['current_accepted'] for r in rows),
            node_free_accepted=sum(r['move']['size_m']==s and r['accepted'] for r in rows)) for s in (1e-7,.001,.006)},
        refused_roles=dict(Counter(r.get('validity',{}).get('reason','construction_failed') for r in rows if not r['accepted'])),
        proof_outcomes=dict(Counter(c['outcome'] for c in checks)),proof_tiers=dict(Counter(c['tier'] for c in checks)),
        proof_unresolved_reasons=dict(Counter(c['reason'] for c in checks if c['outcome']!='valid')),
        trial_proof_seconds=stats([c.get('total_seconds',c['seconds']) for c in checks]),
        complete_trial_seconds=stats([r['complete_trial_seconds'] for r in paired]),
        frozen_current_to_new_ratio=stats([r['current_seconds']/r['complete_trial_seconds'] for r in paired]),
        timed_current_again=False,full_jacobian_comparison=False,physics_calls=0)
    preparations=[read(p) for p in (output/'states').glob('*/preparations.json')]
    result['work_seconds']=dict(new_cached_preparations=sum(v['seconds'] for p in preparations for v in p.values()),
        original_base_proofs=sum(r['new']['seconds'] for r in read(PROOFS)),
        original_adaptive_construction_attempts=read(PRIOR/'report.json')['all_attempt_seconds']['sum'],
        replay_selected_constructions=sum(r.get('construction_seconds',0.) for r in rows),
        all_proof_attempts=sum(c.get('total_seconds',c['seconds']) for c in checks))
    write(output/'report.json',result)
    return result


def run(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    begun=time.perf_counter()
    names=['experiments/benchmark/ng004.py','experiments/benchmark/ng003.py','experiments/benchmark/ng001.py',
        'solvers/bem_inverse/coefficient_geometry.py','solvers/bem_inverse/coefficient_validity.py',
        'solvers/bem_inverse/interval_geometry.py','pytest/bem_inverse/test_coefficient_geometry.py',
        'docs/iterations/node_free_geometry/NG-004_plan.md']
    hashes={p:digest(ROOT/p) for p in names}
    manifest=read(PRIOR/'manifest.json')
    proof_manifest=read(PROOFS.parent/'manifest.json')
    assert digest(ROOT/'solvers/bem_inverse/interval_geometry.py')==proof_manifest['source_hashes']['solvers/bem_inverse/interval_geometry.py']
    proofs={p['state']:p['new'] for p in read(PROOFS)}
    write(output/'manifest.json',dict(experiment='NG-004',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_hashes=hashes,prior_manifest_sha256=digest(PRIOR/'manifest.json'),base_proofs_sha256=digest(PROOFS),
        frozen_control_sha256=digest(CONTROL/'manifest.json'),states=manifest['states'],physics_calls=0,
        current_control_frozen=True,stop_on_first_unproved=True,full_jacobian_comparison=False))
    for p in names:
        target=output/'source_snapshot'/p
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/p).read_bytes())
    try:
        verifier=IntervalGeometry()
        with patch('bem_inverse.coefficient_geometry.range_enclosure',side_effect=AssertionError('angular range anchor')):
            for row in manifest['states']:
                curve=curve_from(row['curve'])
                base=proofs[row['id']]
                assert base['outcome']=='valid' and base['curve_sha256']==verifier.curve_key(curve.coefficients)
                cached={}
                def model(B):
                    if B not in cached:
                        with no_curve_samples():
                            obj,timing=measured(lambda:CoefficientGeometry(curve,row['M'],band=B,**OPTIONS))
                        if obj is None:
                            raise RuntimeError(f'Frozen constructor no longer prepares: {timing}')
                        cached[B]=(obj,timing)
                        write(output/'states'/row['id']/'preparations.json',{str(b):t for b,(_,t) in cached.items()})
                    return cached[B][0]
                records=[]
                prior_files=sorted((PRIOR/'states'/row['id']).glob('*m-d*.json'),key=lambda p:(read(p)['move']['size_m'],read(p)['move']['direction']))
                for path in prior_files:
                    old=read(path)
                    control=read(CONTROL/'states'/row['id']/path.name)
                    record=dict(state=row['id'],move=old['move'],prior_sha256=digest(path),control_sha256=digest(CONTROL/'states'/row['id']/path.name),
                        current_accepted=control['current']['accepted'],current_seconds=control['current']['seconds'],
                        construction_success=old['success'],accepted=False)
                    if old['success']:
                        B=old['selected_band']
                        a=np.array(old['move']['coefficients'])
                        coarse_model,fine_model=model(B),model(2*B)
                        with no_curve_samples():
                            coarse,c=measured(lambda:coarse_model.trial(a))
                            fine,f=measured(lambda:fine_model.trial(a))
                        if coarse is None or fine is None:
                            raise RuntimeError(f'Frozen trial no longer constructs: {c}, {f}')
                        assert coarse[0].tobytes()==complex_array(old['coefficients']).tobytes()
                        assert fine[0].tobytes()==complex_array(old['fine_coefficients']).tobytes()
                        with no_curve_samples():
                            validity=certify_pair(curve.coefficients,coarse[0],coarse[1],fine[1],base,verifier=verifier)
                        construction=c['seconds']+f['seconds']
                        proof_seconds=sum(p.get('total_seconds',p['seconds']) for p in validity['checks'])
                        record.update(accepted=validity['accepted'],validity=validity,error=old['error'],
                            construction_seconds=construction,complete_trial_seconds=construction+proof_seconds,
                            regenerated_coefficients_identical=True,reference_qualified=old['reference_qualified'],selected_band=B)
                    records.append(record)
                    write(output/'states'/row['id']/path.name,record)
                print('STATE',row['id'],'accepted',sum(r['accepted'] for r in records),flush=True)
        changed=[p for p,h in hashes.items() if digest(ROOT/p)!=h]
        if changed:
            raise RuntimeError(f'Measured sources changed: {changed}')
        write(output/'completion.json',dict(completed=True,total_seconds=time.perf_counter()-begun,source_changes=changed,
            coefficients_regenerated_identically=True,no_curve_sample_guards_passed=True,no_construction_range_anchors=True,physics_calls=0))
        print(summarize(output),flush=True)
    except BaseException:
        write(output/'failure.json',dict(traceback=traceback.format_exc(),seconds=time.perf_counter()-begun))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/validation/node_free_geometry/NG-004/run-01')
    parser.add_argument('--report',action='store_true')
    args=parser.parse_args()
    print(summarize(args.output)) if args.report else run(args.output)
