"""Refine a fixed wrong-support witness and test additional measurements.

No parameters are refitted here. Each fitted 10 mm material cell is subdivided
without changing its physical permittivity or conductivity.
"""
from pathlib import Path
import json
import numpy as np
from .layered import Layered
from .layered_screen import grid, truth


def run():
    out = Path('results/experiments/support_certificates_20260916')
    saved = np.load(out / 'layered_data.npz')
    records = json.loads((out / 'broad_material.json').read_text())
    best = min(records, key=lambda r: r['relative_error'])
    parameters = np.asarray(best['parameters'])
    base_eps = parameters[:128].reshape(16, 8)
    eps0, mu0 = 8.8541878128e-12, 1.25663706212e-6
    base_sigma = parameters[128:].reshape(16, 8) * eps0 * 2*np.pi*.75e9
    results = dict(fit=best, refinement=[], additional_measurements=[])

    def predict(n, f, src, rx):
        pts, h = grid(n)
        pts = pts[pts[:, 0] < 0]
        ix = np.minimum(7, np.floor((pts[:, 0]+.08)/.01).astype(int))
        iz = np.minimum(15, np.floor((pts[:, 1]+.24)/.01).astype(int))
        material = base_eps[iz, ix] + 1j*base_sigma[iz, ix]/(eps0*2*np.pi*f)
        bg = 6 + 1j*.02/(eps0*2*np.pi*f)
        ka = 2*np.pi*f*np.sqrt(eps0*mu0)
        layer = Layered(ka, ka*np.sqrt(bg))
        g, e, a = layer.matrices(pts, h*h, src, rx)
        chi = material/bg-1
        p = np.linalg.solve(np.eye(len(pts))-chi[:, None]*g, chi[:, None]*e)
        return a@p, layer

    previous = None
    for n in (16, 32, 48):
        y, _ = predict(n, .75e9, saved['sources'], saved['receivers'])
        row = dict(n=n, relative_error=float(np.linalg.norm(y-saved['y'])/np.linalg.norm(saved['y'])),
                   change_from_previous=None if previous is None else float(np.linalg.norm(y-previous)/np.linalg.norm(saved['y'])))
        results['refinement'].append(row)
        previous = y
        print(row, flush=True)
        (out / 'broad_qualification.json').write_text(json.dumps(results, indent=2))
    cases = [('midpoint_receivers', .75e9, saved['sources'],
              (saved['receivers'][:-1]+saved['receivers'][1:])/2),
             ('third_source', .75e9, np.array([[0., .03]]), saved['receivers']),
             ('lower_frequency', .6e9, saved['sources'], saved['receivers']),
             ('upper_frequency', .9e9, saved['sources'], saved['receivers'])]
    for name, f, src, rx in cases:
        y, layer = predict(48, f, src, rx)
        ref = truth(layer, 56, src, rx)
        row = dict(name=name, frequency=f, n=48,
                   relative_error=float(np.linalg.norm(y-ref)/np.linalg.norm(ref)))
        results['additional_measurements'].append(row)
        print(row, flush=True)
        (out / 'broad_qualification.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    run()
