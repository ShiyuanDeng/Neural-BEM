"""Conditional final M=19 opportunity using the unspent dense-path budget."""
from dataclasses import asdict, replace
from pathlib import Path
import importlib.util
import sys
import time
from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation.lm_backend import Ledger, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sc038_dense', HERE / 'resolve_kite.py')
dense = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dense)
base, sc, ast, ac = dense.base, dense.sc, dense.ast, dense.ac
OUT = HERE / 'final_m19'
PLAN = sc.ROOT / 'docs/iterations/shape_frequency_continuation/iteration_19/05_remaining_m19.md'


def hashes():
    return dict(dense.hashes(), **{str(p.relative_to(sc.ROOT)): sc.digest(p)
                for p in (Path(__file__).resolve(), PLAN)})


def main():
    parent = HERE / 'dense_kite/runs/release_m/result.json'
    previous = sc.read(parent)
    reached = any(s['stage'] == 'dense_3' and s['accepted_steps'] > 0 for s in previous['stages'])
    eligible = previous['reason'] == 'TRIAL_WALL_LIMIT' and not reached
    if not eligible:
        sc.write(HERE / 'remaining_m19_decision.json', dict(dispatched=False,
                 reason='No time-limited absence of an accepted M=19 step', previous_reason=previous['reason'],
                 accepted_M19_step=reached))
        print('Remaining M19 withheld: condition not met', flush=True)
        return
    assert sc.read(HERE / 'dense_kite/final_audit.json')['passed']
    cap = min(1500, 3000 - previous['work']['work_units'])
    assert cap > 0
    OUT.mkdir(exist_ok=False)
    folder = OUT / 'runs/release_m'
    folder.mkdir(parents=True)
    stages, config, catalog = dense.schedules('release_m')
    stage = replace(stages[-1], label='remaining_m19', quota=cap)
    update = base.ProjectedUpdate(sc.LENGTH)
    curve = ast.curve_from(previous['curve'])
    ledger = Ledger(cap=cap, seconds=900)
    frozen = hashes()
    inputs = [parent, HERE / 'dense_kite/manifest.json', HERE / 'dense_kite/final_audit.json']
    sc.write(OUT / 'manifest.json', dict(experiment='SC-038-remaining-M19', sources=frozen,
             inputs={str(p.relative_to(sc.ROOT)): sc.digest(p) for p in inputs}, command=sys.argv,
             inverse_cap=cap, seconds=900, audit_units=42, scoring_fields=19,
             original_dense_units=previous['work']['work_units'], callback='checkpoint only; no fit decisions'))
    sc.write(HERE / 'remaining_m19_decision.json', dict(dispatched=True, reason='Time limit before an accepted M=19 step',
             available_units=cap, previous_dense_units=previous['work']['work_units']))
    sc.write(folder / 'configuration.json', dict(stages=[stage_record(stage)], backend=asdict(config),
             update=update.settings(), initial=ast.curve_record(curve), prefix_units=previous['complete_path_units']))

    def checkpoint(iteration, evaluation):
        sc.write(folder / 'accepted_checkpoint.json', dict(iteration=iteration, loss=evaluation.loss,
                 curve=ast.curve_record(evaluation.curve), work=ledger.snapshot()))
        print('M19 ACCEPT', iteration, evaluation.loss, ledger.units, flush=True)

    started = time.perf_counter()
    with geometry_validation('cache'):
        ledger.begin_stage(stage.label, stage.quota)
        record = fit_stage(curve, stage, ac.contrast(), update, config, ledger, on_accept=checkpoint)
    row = dict(stage=stage.label, outcome=record.outcome, stop=record.stop_reason,
               accepted_steps=record.accepted_steps, initial_loss=record.initial_loss, final_loss=record.final_loss,
               work=record.work, seconds=record.seconds)
    sc.write(folder / f'{stage.label}_history.json', dict(history=record.history, trials=record.trials,
             acceptance_checks=record.acceptance_checks))
    normal = record.outcome in (NORMAL_RETURN, STAGE_QUOTA)
    result = dict(case='kite', arm='release_m', curve=ast.curve_record(record.curve), stages=[row],
                  status='COMPLETED_SCHEDULE' if normal else 'HARD_STOP', reason=None if normal else record.outcome,
                  work=ledger.snapshot(), seconds=time.perf_counter() - started,
                  prefix_units=previous['complete_path_units'],
                  complete_path_units=previous['complete_path_units'] + ledger.units,
                  geometry_work=update.counts, score=ast.score('kite', record.curve, catalog))
    sc.write(folder / 'result.json', result)
    print('M19 DONE', result['status'], result['reason'], result['score']['symmetric_rms_mm'], ledger.units, flush=True)
    dense.OUT = OUT  # Audit the new output with the same numerical audit implementation.
    audit = dense.audit('release_m', final=True)
    sc.write(OUT / 'final_audit.json', dict(rows=[audit], passed=audit['passed']))
    assert hashes() == frozen
    assert previous['work']['work_units'] + ledger.units <= 3000
    sc.write(OUT / 'completion.json', dict(status='COMPLETE', audits_passed=audit['passed'], sources_unchanged=True,
             new_inverse_units=ledger.units, audit_units=audit['work']['work_units']))


if __name__ == '__main__':
    main()
