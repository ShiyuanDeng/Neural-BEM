#!/usr/bin/env python3
"""TOP-005 qualification of selective lowest-dimension candidate refinement."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

for _variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_variable, '1')

import numpy as np
import run_fourier_topology_controller as driver
import run_topology_allocation_experiment as replay
from sdf_inverse import ComplexScatteredData
from sdf_inverse.experiment_record import source_provenance
from sdf_inverse.work_accounting import accounted_call, collect_work

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'results/validation/topology'
SPLIT_CONTROL = BASE / 'TOP-001-20260911-comparison'
CONTROLLER_CONTROL = BASE / 'TOP-001E-controller-20260911/A'
REFERENCE_ROOT = BASE / 'TOP-001-20260911-B0-qualification'


def configure_references():
    for chart in replay.REFERENCES:
        replay.REFERENCES[chart] = REFERENCE_ROOT / chart / 'split'
    replay.ARMS['F'] = (1, 3)


def qualify_controller(output, case):
    args = SimpleNamespace(chart='cartesian', profile='full', demonstration='original', skip_video=True,
        candidates_refined_per_group=1, candidate_refinement_iterations=3, include_simplest_candidate=True)
    metric = driver.run_case(case, output / 'controller/F', args)
    baseline = json.loads((CONTROLLER_CONTROL / case / 'metrics.json').read_text())
    baseline_holdout = json.loads((CONTROLLER_CONTROL / case / 'holdout.json').read_text())
    saved_data = json.loads((CONTROLLER_CONTROL / case / 'holdout_observations.json').read_text())
    problem = replay.baseline._problem(replay.HOLDOUT_HZ)
    np.testing.assert_array_equal(problem.source_points, saved_data['problem']['source_points'])
    np.testing.assert_array_equal(problem.receiver_points, saved_data['problem']['receiver_points'])
    observed = np.asarray(saved_data['observed_real']) + 1j*np.asarray(saved_data['observed_imag'])
    data = ComplexScatteredData(problem, observed)
    with collect_work() as audit:
        loss, relative = accounted_call('holdout', driver.topology_objective,
            driver.deserialize_state(metric['final_state']), data, replay.baseline._geometry_config(128),
            replay.baseline.iteration01_solve_config())
    path = output / 'controller/F' / case
    driver.write_json(path / 'holdout_observations.json', saved_data)
    holdout = dict(holdout_relative_error=relative, holdout_loss=loss, work=audit.snapshot(),
                   oracle=baseline_holdout['oracle'])
    driver.write_json(path / 'holdout.json', holdout)
    gates = dict(recovered=metric['stop_reason']=='recovered',
        correct_count=len(metric['final_state'])==baseline_holdout['truth_component_count'],
        geometry=bool(metric['hausdorff_m']<=max(1.1*baseline['hausdorff_m'],1e-6)),
        training=bool(metric['final_relative_error']<=max(1.1*baseline['final_relative_error'],1e-6)),
        holdout=bool(relative<=max(1.1*baseline_holdout['holdout_relative_error'],1e-5)))
    trajectory=json.loads((path/'trajectory.json').read_text())
    baseline_trajectory=json.loads((CONTROLLER_CONTROL/case/'trajectory.json').read_text())
    result=dict(case=case, baseline=baseline, selective=metric, holdout=holdout,
        baseline_holdout=baseline_holdout, gates=gates, passed=all(gates.values()),
        exact_baseline_trajectory=trajectory==baseline_trajectory,
        extra_refined_candidates=sum(row.get('candidate_refinement_selection')=='lowest_dimension'
            for stage in json.loads((path/'topology_passes.json').read_text()) for row in stage['trials']))
    driver.write_json(output/f'controller/{case}_comparison.json',result)
    print(json.dumps(dict(case=case,gates=gates,baseline_cost=baseline['work']['totals']['bie_frequency_solve_count'],
                         selective_cost=metric['work']['totals']['bie_frequency_solve_count'])),flush=True)
    return result


def execute_job(payload):
    output, job, provenance, deadline = payload
    if perf_counter()>deadline:
        raise TimeoutError('TOP-005 one-hour wall ceiling reached.')
    configure_references()
    if job[0]=='controller':
        return qualify_controller(output,job[1])
    _, chart, magnitude, seed=job
    return replay.run_replay(output,chart,'F',magnitude,seed,provenance=provenance,
                             include_simplest=True,experiment_id='TOP-005')


def summarize(output):
    rows=[json.loads(p.read_text()) for p in sorted((output/'comparison').glob('*/*/*/metrics.json'))]
    cases=[json.loads(p.read_text()) for p in sorted((output/'controller').glob('*_comparison.json'))]
    pairs=[]
    for row in rows:
        suffix=Path(row['chart'])/'A'/f"m{row['magnitude']:g}-s{row['seed'] if row['magnitude'] else 0}"
        a=json.loads((SPLIT_CONTROL/'comparison'/suffix/'metrics.json').read_text())
        costs=[r['work']['totals']['bie_frequency_solve_count']for r in (a,row)]
        f_path=output/row['path']
        a_path=SPLIT_CONTROL/'comparison'/suffix
        identical_inputs=(json.loads((f_path/'manifest.json').read_text())['initial_state']==
                          json.loads((a_path/'manifest.json').read_text())['initial_state'] and
                          (f_path/'observations.json').read_text()==(a_path/'observations.json').read_text())
        pairs.append(dict(chart=row['chart'],magnitude=row['magnitude'],seed=row['seed'],paired_inputs=identical_inputs,
            baseline_cost=costs[0],selective_cost=costs[1],baseline_hausdorff_m=a['hausdorff_m'],
            selective_hausdorff_m=row['hausdorff_m'],baseline_holdout=a['holdout_relative_error'],
            selective_holdout=row['holdout_relative_error'],
            exact_baseline_trajectory=json.loads((f_path/'trajectory.json').read_text())==
                                      json.loads((a_path/'trajectory.json').read_text())))
    controller_cost={name:sum(r[key]['work']['totals']['bie_frequency_solve_count']for r in cases)
                     for name,key in [('A','baseline'),('F','selective')]}
    split_cost={chart:{name:sum(r[key]for r in pairs if r['chart']==chart)
                      for name,key in [('A','baseline_cost'),('F','selective_cost')]}for chart in replay.REFERENCES}
    complete=len(rows)==20 and len(cases)==5
    passed=complete and all(c['passed']for c in cases) and all(p['paired_inputs']for p in pairs)
    passed=passed and controller_cost['F']<=controller_cost['A'] and all(c['F']<=c['A']for c in split_cost.values())
    result=dict(complete=complete,passed=passed,split_pairs=pairs,controller_cases=cases,
                controller_total_bie=controller_cost,split_total_bie=split_cost)
    driver.write_json(output/'qualification.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--summary-only',action='store_true')
    args=parser.parse_args()
    if args.summary_only:
        return 0 if summarize(args.output)['passed'] else 1
    if not 1<=args.workers<=6:
        parser.error('workers must be between one and six')
    args.output.mkdir(parents=True,exist_ok=False)
    configure_references()
    provenance=source_provenance(ROOT)
    driver.write_json(args.output/'manifest.json',dict(experiment_id='TOP-005',created_utc=datetime.now(timezone.utc).isoformat(),
        source_provenance=provenance,baseline_commit='746c9fb',workers=args.workers,maximum_seconds=3600,
        split_control=str(SPLIT_CONTROL.relative_to(ROOT)),controller_control=str(CONTROLLER_CONTROL.relative_to(ROOT)),
        thread_environment={name:os.environ.get(name)for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}))
    deadline=perf_counter()+3600
    for chart in replay.REFERENCES:
        result=replay.run_replay(args.output,chart,'A',0.,replay.SEEDS[0],historical=True,provenance=provenance,
                                 experiment_id='TOP-005')
        if not result['historical_event_match']:
            return 2
    jobs=[('replay',chart,magnitude,seed)for chart in replay.REFERENCES for magnitude in replay.MAGNITUDES
          for seed in ((replay.SEEDS[0],)if magnitude==0 else replay.SEEDS)]
    jobs += [('controller',case)for case in driver.CASES]
    with ProcessPoolExecutor(max_workers=args.workers)as pool:
        for _ in pool.map(execute_job,[(args.output,job,provenance,deadline)for job in jobs]):
            pass
    result=summarize(args.output)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
