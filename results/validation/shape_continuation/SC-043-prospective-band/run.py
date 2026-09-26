"""Prospective band decisions with all diagnostic work charged to the policy.

No runs are released until prepare freezes a selected state treatment and plan.
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import importlib.util
from pathlib import Path
import time
import traceback
import numpy as np

from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation.action_atlas import predict
from experiments.shape_continuation.lm_backend import Ledger, Objective, fit_stage, NORMAL_RETURN, STAGE_QUOTA

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sc043_common', HERE.parent/'SC-042-state-strategies/run.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
POLICIES = ('fixed', 'stagnation', 'atlas')
QUOTA = 304
PLAN = HERE/'plan.md'


def columns(low, high):
    """Complete normal-coordinate order: constant, all cos, then all sin."""
    return np.r_[np.arange(low+1), np.arange(high+1, high+low+1)]


def choose(low_gain, high_gain, loss):
    return bool(high_gain-low_gain >= .10*loss and loss > 1e-14)


def sources():
    return dict(c.sources(), **{str(p.relative_to(c.sc.ROOT)):c.sc.digest(p) for p in (Path(__file__), PLAN)})


def verify():
    m = c.sc.read(HERE/'manifest.json')
    assert sources() == m['sources']
    assert all(c.sc.digest(c.sc.ROOT/p) == h for p,h in m['inputs'].items())


def prepare(state_arm):
    if (HERE/'manifest.json').exists():
        verify()
        return
    if not PLAN.exists():
        raise RuntimeError('Freeze the decision contract first')
    c.verify()
    parent = c.sc.read(c.HERE/'manifest.json')
    c.write(HERE/'manifest.json', dict(experiment='SC-043', sources=sources(), inputs=parent['inputs'],
        cases=c.CASES, policies=POLICIES, state_arm=state_arm, quota=QUOTA, blocks=3,
        threshold=.10, increment=6, diagnostic_radius='0.12/k_max, test radius only',
        prepared=time.strftime('%Y-%m-%dT%H:%M:%S%z')))


def initial_stagnated(case):
    curve, path, _, _ = c.start_record(case)
    data = c.sc.read(path)
    if 'stop' in data:
        return data['stop'] in ('gradient_tolerance', 'relative_step_tolerance', 'no_decreasing_step')
    history = data['history']
    if len(history) < 2:
        return True
    a,b = history[-2:]
    return (a['loss']-b['loss'])/max(a['loss'], 1e-30) < .05


def forecast(curve, stage, config, low, ledger):
    high = low+6
    update = c.reference.ProjectedUpdate(c.sc.LENGTH)
    high_stage = replace(stage, update_modes=high)
    objective = Objective(high_stage, c.ac.contrast(), config, ledger)
    base = objective.production(curve, 'policy_diagnostic')
    if base is None:
        raise ValueError('Diagnostic state not solver ready')
    space = update.prepare(curve, high, stage.curve_modes)
    jacobian = objective.jacobian(base, update, space)
    metric = update.metric(space, 'mass')
    radius = .12/max(o.wavenumber for o in stage.observations)*c.sc.LENGTH
    subset = columns(low, high)
    a = predict(jacobian[:,subset], base.residual, metric[np.ix_(subset,subset)], radius)
    b = predict(jacobian, base.residual, metric, radius)
    release = choose(a.predicted_decrease, b.predicted_decrease, base.loss)
    return dict(low=low, high=high, low_prediction=a.record(), high_prediction=b.record(),
        incremental_fraction=(b.predicted_decrease-a.predicted_decrease)/base.loss if base.loss else 0.,
        release=release, selected=high if release else low, diagnostic_units=ledger.units)


def worker(job):
    case, policy = job
    folder = HERE/'runs'/case/policy
    folder.mkdir(parents=True, exist_ok=False)
    stages, decisions, accepted = [], [], []
    started = time.perf_counter()
    total = 0
    try:
        verify()
        manifest = c.sc.read(HERE/'manifest.json')
        state_arm = manifest['state_arm']
        curve, template, config, parent, _ = c.stages_for(case, state_arm)
        initial = curve
        m = template[0].update_modes
        stagnated = initial_stagnated(case)
        outcome = 'COMPLETED_SCHEDULE'
        last_stage = template[0]
        for block in range(3):
            curve, cleanup = c.treatment(curve, state_arm, block)
            curve.validate()
            stage = replace(template[0], label=f'block_{block+1}', iterations=22, quota=QUOTA)
            diagnostic = Ledger(cap=50, seconds=900, endpoint_reserve=0)
            if policy == 'atlas':
                with geometry_validation('cache'):
                    decision = forecast(curve, stage, config, m, diagnostic)
            else:
                release = policy == 'fixed' or stagnated
                decision = dict(low=m, high=m+6, release=release, selected=m+6 if release else m,
                                diagnostic_units=0, prior_stagnated=stagnated)
            decision.update(block=block+1, policy=policy, cleanup=cleanup,
                            curve_before_fit=c.ast.curve_record(curve), total_units_before=total)
            decisions.append(decision)
            # Persist the decision before any inverse call or truth scoring.
            c.write(folder/'decisions.json', dict(rows=decisions))
            total += decision['diagnostic_units']
            m = decision['selected']
            available = QUOTA-decision['diagnostic_units']
            stage = replace(stage, update_modes=m, quota=available)
            ledger = Ledger(cap=available+1, seconds=3600)
            ledger.begin_stage(stage.label, available)
            base_total = total
            update = c.reference.ProjectedUpdate(c.sc.LENGTH)
            def checkpoint(i, value):
                accepted.append(dict(block=block+1, M=m, iteration=i, loss=value.loss,
                    total_units=base_total+ledger.units, curve=c.ast.curve_record(value.curve)))
                c.write(folder/'accepted.json', dict(states=accepted))
            with geometry_validation('cache'):
                result = fit_stage(curve, stage, c.ac.contrast(), update, config, ledger, on_accept=checkpoint)
            curve = result.curve
            last_stage = stage
            total += ledger.units
            decrease = (result.initial_loss-result.final_loss)/max(result.initial_loss, 1e-30)
            stagnated = decrease < .05 or result.stop_reason in ('gradient_tolerance', 'relative_step_tolerance', 'no_decreasing_step')
            row = dict(block=block+1, M=m, outcome=result.outcome, stop=result.stop_reason,
                initial_loss=result.initial_loss, final_loss=result.final_loss, units=ledger.units,
                diagnostic_units=decision['diagnostic_units'], total_units=total, detail=result.detail)
            stages.append(row)
            c.write(folder/f'block_{block+1}.json', dict(row, history=result.history, trials=result.trials,
                                                      acceptance_checks=result.acceptance_checks))
            c.write(folder/'checkpoint.json', dict(stages=stages, curve=c.ast.curve_record(curve), total_units=total))
            print('STAGE', case, policy, row, flush=True)
            if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                outcome = result.outcome
                break
        audit = c.audit(curve, last_stage, config)
        c.write(folder/'audit.json', audit)
        row = dict(case=case, policy=policy, outcome=outcome, stages=stages, total_units=total,
            score=c.reference.geometry_score(case, curve), initial_score=c.reference.geometry_score(case, initial),
            curve=c.ast.curve_record(curve), audit_passed=audit['passed'], audit_units=audit['work']['work_units'],
            seconds=time.perf_counter()-started)
        verify()
        c.write(folder/'result.json', row)
        c.write(folder/'progress.json', dict(states=[dict(s, score=c.reference.geometry_score(case, c.ast.curve_from(s['curve']))) for s in accepted]))
        print('DONE', case, policy, row['score'], row['audit_passed'], flush=True)
        return row
    except Exception:
        row = dict(case=case, policy=policy, outcome='EXCEPTION', traceback=traceback.format_exc(),
                   total_units=total, stages=stages, decisions=decisions)
        c.write(folder/'failure.json', row)
        print('FAILED', case, policy, row['traceback'], flush=True)
        return row


def summarize():
    rows = []
    for p in sorted((HERE/'runs').glob('*/*/result.json')):
        d = c.sc.read(p)
        rows.append({k:d[k] for k in ('case','policy','outcome','score','total_units','audit_passed','audit_units','stages')})
    c.write(HERE/'summary.json', dict(rows=rows, failures=[c.sc.read(p) for p in sorted((HERE/'runs').glob('*/*/failure.json'))]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('prepare','run','summarize'))
    p.add_argument('--state-arm', choices=c.ARMS, default='once')
    p.add_argument('--cases', nargs='+', choices=c.CASES, default=c.CASES)
    p.add_argument('--workers', type=int, default=6)
    a = p.parse_args()
    if a.mode == 'prepare':
        prepare(a.state_arm)
    elif a.mode == 'summarize':
        summarize()
    else:
        assert 1 <= a.workers <= 6
        verify()
        jobs = [(case, policy) for case in a.cases for policy in POLICIES if not (HERE/'runs'/case/policy).exists()]
        with ProcessPoolExecutor(a.workers) as pool:
            for f in as_completed([pool.submit(worker,j) for j in jobs]):
                f.result()
                summarize()


if __name__ == '__main__':
    main()
