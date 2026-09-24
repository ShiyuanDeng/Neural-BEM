"""Evaluation-only bridge audit; run with PYTHONPATH=solvers:. from repo root."""
import json
from pathlib import Path
import numpy as np
from experiments.shape_continuation.legacy_cases import load_shape, observations, write
from experiments.shape_continuation.forward import solve, shape_jacobian
from experiments.shape_continuation.geometry import normal_basis, displaced, reparameterize

ROOT = Path(__file__).resolve().parent
rows = []
# The cached observations came from the independent old Mie/Nystrom oracles.
for target in ('circle', 'star'):
    data = json.loads((ROOT/'inputs'/f'circle-to-{target}'/'input.json').read_text())
    truth = load_shape(data['truth'])
    for obs in observations(data):
        value = solve(truth, obs.wavenumber, data['contrast'], obs.acquisition, 512).prediction
        error = float(np.linalg.norm(value-obs.scattered)/np.linalg.norm(obs.scattered))
        rows.append(dict(check='independent_truth', target=target, k=obs.wavenumber, relative_error=error))
# Check the new paired-source derivative at each noncircular start, at all training frequencies.
for initial in ('circle', 'ellipse', 'star'):
    data = json.loads((ROOT/'inputs'/f'{initial}-to-circle'/'input.json').read_text())
    shape, projection = reparameterize(load_shape(data['initial']), 128)
    direction = np.random.default_rng(812).normal(size=11)
    direction /= np.linalg.norm(direction)
    step = 1e-5
    plus = displaced(shape, step*direction, 128).shape
    minus = displaced(shape, -step*direction, 128).shape
    for obs in observations(data)[:3]:
        state = solve(shape, obs.wavenumber, data['contrast'], obs.acquisition, 512)
        analytic = shape_jacobian(state, normal_basis(state.curve, 5)) @ direction
        fp = solve(plus, obs.wavenumber, data['contrast'], obs.acquisition, 512).prediction
        fm = solve(minus, obs.wavenumber, data['contrast'], obs.acquisition, 512).prediction
        fd = (fp-fm)/(2*step)
        error = float(np.linalg.norm(fd-analytic)/np.linalg.norm(fd))
        rows.append(dict(check='directional_derivative', initial=initial, k=obs.wavenumber,
                         step=step, nodes=512, update_band=5, relative_error=error))
write(ROOT/'bridge_audit.json', rows)
for kind, tolerance in (('independent_truth', 1e-7), ('directional_derivative', 1e-5)):
    worst = max(r['relative_error'] for r in rows if r['check']==kind)
    print(kind, worst, 'PASS' if worst < tolerance else 'FAIL', flush=True)
    assert worst < tolerance
