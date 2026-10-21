"""Geometry-only replay of one outer iteration at a fixed base boundary.

Given the saved base state (curve, J, g, H_GN, D, damping), run the real LM solve,
step control and geometry update for every damping trial x halving. No loss test.
A wrapper on ``check_geometry`` records intermediate curves, including refused ones.
"""
import pickle
from pathlib import Path

import numpy as np

from bem_inverse import c9_lm, checks
from bem_inverse.checks import step_too_small
from bem_inverse.geometry_update_methods import bind_geometry_update, control_step
from bem_inverse.geometry_selection import make_update
from bem_inverse.physics import Execution
from bem_inverse.errors import UpdateRefused


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
    """Replay the retained certified method on a saved base; return its constructed curves."""
    update = make_update('certified_spectral', length_unit_m, Execution(device='cpu'))
    geometry_update = bind_geometry_update(update)
    space = it["space"]
    config, g, H, D = it['config'], it['g'], it['H'], it['D']
    built = []
    original = update.check_geometry

    def recording_check(space_, coefficients, role, sampled):
        built.append((role, np.array(coefficients, copy=True)))
        return original(space_, coefficients, role, sampled)

    update.check_geometry = recording_check
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
        a_bounded = control_step(a_raw, space, update, config)
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
                candidate, report = geometry_update(a_used, prepared=space)
                row.update(candidate=candidate.coefficients.copy(), report=report)
            except UpdateRefused as exc:
                row.update(status='refused', reason=exc.reason, detail=exc.detail)
            row['curves'] = list(built)
            rows.append(row)
        if lambdas is None:
            lam *= config.damping_increase
    return rows
