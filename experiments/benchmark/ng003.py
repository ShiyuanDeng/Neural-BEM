"""NG-003 coefficient-only speed bootstrap and observable error budget."""
import argparse
from pathlib import Path
import subprocess
import time
import traceback
from unittest.mock import patch

import numpy as np

from bem_inverse.coefficient_geometry import CoefficientGeometry
from bem_inverse.interval_geometry import IntervalGeometry
from bem_inverse.io import read,write,digest,curve_from
from bem_inverse.spectral import spectral_project
from . import ng002
from .ng001 import ROOT,UNIT,no_curve_samples,measured

PRIOR=ng002.PRIOR
OPTIONS=dict(speed_method='residual_newton',accuracy_mode='coefficients')


def controls(output):
    results=[]
    for old in read(PRIOR/'controls.json'):
        curve=curve_from(old['curve'])
        result=dict(id=old['id'],attempts=[])
        with no_curve_samples():
            result['certificate']=IntervalGeometry().certify(curve.coefficients)
        for B in (256,512,1024,2048,4096,8192):
            with no_curve_samples():
                obj,timing=measured(lambda:CoefficientGeometry(curve,2,band=B,**OPTIONS))
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
    output=Path(output)
    result=ng002.summarize(output)
    result['constructor']='residual_newton + coefficient error budget'
    result['interval_base_results_reused']=result.pop('interval_bases')
    rows=[read(p) for p in (output/'states').glob('*/*m-d*.json')]
    previous=ROOT/'results/validation/node_free_geometry/NG-002/run-01'
    old={(r['state'],r['move']['id']):r for p in (previous/'states').glob('*/*m-d*.json') for r in [read(p)]}
    result.update(previous_escalated_pairs=sum(r['success'] for r in old.values()),
        gains_over_previous=sum(r['success'] and not old[(r['state'],r['move']['id'])]['success'] for r in rows),
        regressions_over_previous=sum(not r['success'] and old[(r['state'],r['move']['id'])]['success'] for r in rows))
    write(output/'report.json',result)
    return result


def run(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    begun=time.perf_counter()
    source_names=['experiments/benchmark/ng003.py','experiments/benchmark/ng002.py','experiments/benchmark/ng001.py',
        'solvers/bem_inverse/coefficient_geometry.py','solvers/bem_inverse/interval_geometry.py',
        'solvers/bem_inverse/analytic_projection.py','solvers/bem_inverse/spectral.py',
        'pytest/bem_inverse/test_coefficient_geometry.py','docs/iterations/node_free_geometry/NG-003_plan.md']
    hashes={p:digest(ROOT/p) for p in source_names}
    manifest=read(PRIOR/'manifest.json')
    proof_path=ROOT/'results/validation/node_free_geometry/NG-002/run-01/base_certificates.json'
    write(output/'manifest.json',dict(experiment='NG-003',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_hashes=hashes,states=manifest['states'],prior_manifest_sha256=digest(PRIOR/'manifest.json'),
        reused_base_proofs_sha256=digest(proof_path),options=OPTIONS,frozen_control=True,
        complete_trial_comparison=False,physics_calls=0))
    write(output/'base_certificates.json',read(proof_path))
    for p in source_names:
        target=output/'source_snapshot'/p
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/p).read_bytes())
    try:
        with patch('bem_inverse.coefficient_geometry.range_enclosure',side_effect=AssertionError('construction used angular anchors')):
            controls(output)
            for row in manifest['states']:
                ng002.state(row,output,engine_kwargs=OPTIONS,coarse_limit=4096)
        changed=[p for p,h in hashes.items() if digest(ROOT/p)!=h]
        if changed:
            raise RuntimeError(f'Measured sources changed: {changed}')
        write(output/'completion.json',dict(completed=True,total_seconds=time.perf_counter()-begun,
            source_changes=changed,no_curve_sample_guards_passed=True,no_construction_range_anchors=True,physics_calls=0))
        print(summarize(output),flush=True)
    except BaseException:
        write(output/'failure.json',dict(traceback=traceback.format_exc(),seconds=time.perf_counter()-begun))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/validation/node_free_geometry/NG-003/run-01')
    parser.add_argument('--report',action='store_true')
    args=parser.parse_args()
    print(summarize(args.output)) if args.report else run(args.output)
