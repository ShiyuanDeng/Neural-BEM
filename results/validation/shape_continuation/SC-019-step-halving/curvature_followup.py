"""Exploratory second factor: existing 10% curvature default, with/without halving."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from time import perf_counter

from experiments.shape_continuation.continuation import run_adaptive
from experiments.shape_continuation.forward import BudgetExceeded, Work
from experiments.shape_continuation.geometry import curvature_tail, reparameterize
from experiments.shape_continuation.inverse import FitConfig
from experiments.shape_continuation.legacy_cases import (
    LegacyCatalogPolicy, load_shape, observations, score, shape_record,
    source_hashes, write,
)

HERE = Path(__file__).resolve().parent


def audit(output, data):
    truth = load_shape(data['truth'])
    refit, projection = reparameterize(truth, 256)
    rows = [dict(curvature_band=band, polar_curve_tail=curvature_tail(truth, band),
                 arclength_curve_tail=curvature_tail(refit, band), original_gate=.01,
                 default_gate=FitConfig().curvature_tail_tolerance)
            for band in (19, 20, 23, 24, 25, 26, 30, 40, 60)]
    write(output/'truth-curvature-audit.json', dict(
        note='Post-run evaluation only; truth is not supplied to the optimizer. The follow-up is motivated by this audit.',
        refit_projection_error=projection, rows=rows))


def run(output, backtracks):
    parent = json.loads((output/'manifest.json').read_text())
    assert source_hashes() == parent['source_sha256']
    assert hashlib.sha256((output/'input.json').read_bytes()).hexdigest() == parent['input_sha256']
    data = json.loads((output/'input.json').read_text())
    audit(output, data)
    base = FitConfig(**parent['base_config'])
    config = replace(base, backtracks=backtracks,
                     curvature_tail_tolerance=FitConfig().curvature_tail_tolerance)
    changes = {k:v for k,v in asdict(config).items() if v != asdict(base)[k]}
    expected = dict(curvature_tail_tolerance=.1)
    if backtracks: expected['backtracks'] = backtracks
    assert changes == expected
    name = f'curvature10-halving{backtracks}'
    directory = output/name
    directory.mkdir()
    write(directory/'manifest.json', dict(
        source_sha256=parent['source_sha256'], input_sha256=parent['input_sha256'],
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        config=asdict(config), changed_settings=changes,
        max_forwards=parent['max_forwards'], max_seconds=parent['max_seconds'],
        max_decisions=parent['max_decisions'],
        motivation='Exploratory follow-up: original 1% gate rejects the true star; test the existing 10% FitConfig default.',
    ))
    work = Work(max_forwards=parent['max_forwards'], max_seconds=parent['max_seconds'])
    obs = observations(data)[:3]
    policy = LegacyCatalogPolicy(obs, data['contrast'], work, mode='fixed', config=config)
    shape, records = load_shape(data['initial']), []

    def checkpoint(record):
        nonlocal shape
        if record.committed: shape = record.result.shape
        row = dict(index=record.index, stage=asdict(record.decision.stage),
                   stop=record.result.stop_reason, committed=record.committed,
                   shape=shape_record(shape), residual=record.result.relative_residual,
                   forwards=work.attempted, seconds=perf_counter()-work.started,
                   accepted_steps=len(record.result.states)-1,
                   history=record.result.history, trials=record.result.trials,
                   states=[shape_record(s) for s in record.result.states])
        records.append(row)
        write(directory/f'decision-{record.index:02d}.json',row)
        print(json.dumps({k:row[k] for k in ('index','stop','residual','forwards','accepted_steps')}),flush=True)

    try:
        result = run_adaptive(shape,obs,data['contrast'],policy,work=work,
                              max_decisions=parent['max_decisions'],on_decision=checkpoint)
        shape,stop,failure = result.shape,result.stop_reason,None
    except BudgetExceeded:
        stop,failure = 'budget_exhausted',None
    except Exception as exc:
        stop,failure = 'failed',f'{type(exc).__name__}: {exc}'
    row = dict(arm=name,config=asdict(config),changed_settings=changes,
               input_sha256=parent['input_sha256'],shape=shape_record(shape),
               stop=stop,failure=failure,forwards=work.attempted,
               elapsed_seconds=perf_counter()-work.started,work=work.summary(),
               accepted_steps=sum(r['accepted_steps'] for r in records),
               accepted_halved_steps=sum(h.get('step',1.) < 1. for r in records
                                        for h in r['history'] if 'direction' in h),
               trial_status_counts=dict(Counter(t.get('status','unknown')
                                               for r in records for t in r['trials'])))
    write(directory/'result.json',row)
    try:
        scores = score(data,shape)
        gate = parent['gates']
        row.update(scores=scores,passed=(failure is None
            and scores['boundary_upper_m'] <= gate['boundary_upper_m']
            and scores['train_relative'] <= gate['train_relative']
            and scores['worst_holdout_relative'] <= gate['holdout_relative']
            and scores['endpoint_field_refinement'] <= gate['endpoint_field_refinement']))
    except Exception as exc:
        row.update(passed=False,evaluation_failure=f'{type(exc).__name__}: {exc}')
    write(directory/'result.json',row)
    print(json.dumps({k:row.get(k) for k in ('arm','stop','forwards','passed','scores')}),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE)
    parser.add_argument('--backtracks',type=int,choices=(0,6),required=True)
    args = parser.parse_args()
    run(args.output,args.backtracks)
