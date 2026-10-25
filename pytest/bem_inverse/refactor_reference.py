"""Small deterministic control-path reference; run with either source tree on PYTHONPATH.

This is a component/stage comparison, not a benchmark campaign. Wall timings and
exception tracebacks are excluded; numerical values, decisions, dispatches, work
charges and callback order are retained. ``python refactor_reference.py <file>``
writes the reference that ``test_refactor_contract`` compares against.
"""
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np

from bem_inverse.errors import Stop
from bem_inverse.fit_stage import fit_stage
from bem_inverse.work import Ledger
from bem_inverse.continuation.geometry import FourierCurve
from test_resolution_resume import ScalarUpdate, scalar_stage


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()
                if 'seconds' not in k and k not in ('traceback', 'candidate_sha256')}
    if isinstance(value, (list, tuple)):
        return [stable(v) for v in value]
    if isinstance(value, np.ndarray):
        return stable(value.tolist())
    if isinstance(value, np.generic):
        return stable(value.item())
    if isinstance(value, complex):
        return dict(real=value.real, imag=value.imag)
    if isinstance(value, float) and not np.isfinite(value):
        return repr(value)
    return value


def stage_record(result):
    return stable({key: getattr(result, key) for key in (
        'outcome', 'stop_reason', 'converged', 'accepted_steps', 'initial_loss',
        'final_loss', 'history', 'trials', 'work', 'geometry_proposals', 'entry_reused')})


def control_paths():
    """Small fixtures exercise optional responses without a physical inverse run."""
    records = {}
    for mode in ('agreement', 'hanke', 'terminal', 'callback_stop', 'quota', 'wall'):
        physics, stage, config, _ = scalar_stage(iterations=2, nodes=16)
        ledger = Ledger(cap=500, seconds=10, endpoint_reserve=0, clock=lambda: 0.)
        ledger.begin_stage(stage.label, 3 if mode == 'quota' else None)
        if mode == 'wall':
            ledger.clock = lambda: 11.
        if mode in ('agreement', 'hanke'):
            config = replace(config, damping_rule=mode)
        if mode == 'terminal':
            config = replace(config, avoid_terminal_linearization=True)
        callbacks = []
        def callback(i, evaluation):
            callbacks.append((i, evaluation.loss))
            if mode == 'callback_stop' and i == 1:
                raise Stop('reference callback stop')
        result = fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(),
                           config, ledger, physics=physics, on_accept=callback)
        records[mode] = dict(result=stage_record(result), calls=stable(physics.calls),
                             derivatives=physics.derivatives, callbacks=callbacks)
    return records


if __name__ == '__main__':
    path, source = Path(sys.argv[1]), sys.argv[2]
    path.write_text(json.dumps(dict(source=source, control_paths=stable(control_paths())), indent=2, sort_keys=True)+'\n')
    print('control paths ->', path)
