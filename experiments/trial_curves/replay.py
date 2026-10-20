"""Geometry-only replay of one outer iteration at a fixed base boundary.

Given the saved base state (curve, J, g, H_GN, D, damping), run the real C9 solve, C10 step
control and ``update.trial`` for every damping trial x halving. No loss test and no ``validate``.
A wrapper on ``update.check`` only records each curve that C10 builds, including refused ones.
"""
import pickle
from pathlib import Path

import numpy as np

from bem_inverse import c9_lm, c10_geometry_trial, checks
from bem_inverse.checks import step_too_small
from bem_inverse.geometry_selection import make_update
from bem_inverse.physics import Execution
from bem_inverse.continuation.updates import UpdateRefused


def load(path):
    """Proposal events grouped as iterations: consecutive proposals on the same base, plus real trial rows."""
    iterations = []
    for kind, row in pickle.loads(Path(path).read_bytes()):
        if kind == 'proposal':
            same = iterations and iterations[-1]['stage'] == row['stage'] and \
                np.array_equal(iterations[-1]['coefficients'], row['coefficients'])
            if not same:
                iterations.append(dict(row, damping_trials=[], real_trials=[]))
            iterations[-1]['damping_trials'].append(row['damping'])
        else:
            iterations[-1]['real_trials'].append(row)
    return iterations


def replay(it, length_unit_m, scale=1.0, lambdas=None):
    """Every damping trial x halving for one base. Returns one row per attempt, with the curves C10 built."""
    update = make_update('certified_spectral', length_unit_m, Execution(device='cpu'))
    space = it["space"]
    config, g, H, D = it['config'], it['g'], it['H'], it['D']
    built = []
    original = update.check

    def recording_check(space_, coefficients, role, sampled):
        built.append((role, np.array(coefficients, copy=True)))
        return original(space_, coefficients, role, sampled)

    update.check = recording_check
    rows, lam = [], it['damping_trials'][0]
    if lambdas is not None:   # explicit list, e.g. [0.] for a plain Gauss-Newton step
        schedule = list(lambdas)
    for damping_trial in range(config.max_damping_trials if lambdas is None else len(schedule)):
        if lambdas is not None:
            lam = schedule[damping_trial]
        try:
            a_raw = c9_lm.solve_proposal(g, H, D, lam)
        except np.linalg.LinAlgError:
            rows.append(dict(damping_trial=damping_trial, lam=lam, backtrack=None, status='singular'))
            if lambdas is None:
                lam *= config.damping_increase
            continue
        a_bounded = c10_geometry_trial.control_step(a_raw, space, update, config)
        for backtrack in range(config.max_backtracks + 1):
            a_used = 0.5**backtrack*a_bounded
            row = dict(damping_trial=damping_trial, lam=lam, backtrack=backtrack, a=a_used,
                       step_norm=float(np.linalg.norm(a_used)), curves=[], status='valid', reason=None)
            if step_too_small(a_used, scale, config.relative_step_tolerance):
                row.update(status='skipped', reason='step too small (no curve built)')
                rows.append(row)
                continue
            built.clear()
            try:
                candidate, report = update.trial(space, a_used)
                row.update(candidate=candidate.coefficients.copy(), report=report)
            except UpdateRefused as exc:
                row.update(status='refused', reason=exc.reason, detail=exc.detail)
            row['curves'] = list(built)
            rows.append(row)
        if lambdas is None:
            lam *= config.damping_increase
    return rows
