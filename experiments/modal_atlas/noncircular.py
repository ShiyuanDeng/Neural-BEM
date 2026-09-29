"""MA-001 part B: wavefield-pair structure of real noncircular sensitivities.

For each declared state and catalog frequency, solve the qualified nodal
Müller/Kress forward and reciprocal problems (exactly as SC-039 does), take
normalized-arclength Fourier coefficients of the Dirichlet traces,

    U_n = (1/L) sum_x w(x) u(x) exp(-i n theta(x)),

and rebuild the paired sensitivity to h = exp(i p theta) as the pair sum

    J_p = (ki^2 - k^2) L sum_n U_n V_{-p-n}.

Stored per state/frequency: trace spectra (|n| <= NMAX), the modal and nodal
J_p, the production `shape_jacobian` on the arclength cos/sin basis, and the
data. Run from the repository root:

PYTHONPATH=solvers:. python -m experiments.modal_atlas.noncircular --output <dir>
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import time

import numpy as np

NMAX, PMAX = 160, 80
GRIDS = (512, 1024)


def states():
    from experiments.shape_continuation import trajectory_atlas as ta
    out = {f'truth/{case}': curve for case, curve in ta.truth_shots().items() if case != 'wrong_circle'}
    wanted = ('A_hybrid/kite', 'G_fixed_m9/kite', 'F_released_m/kite', 'F_released_m/circle_to_c',
              'A_hybrid/circle_to_star', 'E_wider_ladder/circle_to_star')
    for t in ta.trajectories():
        if t.id in wanted:
            last = t.steps[-1]
            out[f'end/{t.id}'] = last.curve
            out[f'end/{t.id}'.replace('end/', 'meta/')] = dict(update_modes=last.update_modes, nodes=last.nodes,
                                                               curve_band=last.curve_band, steps=len(t.steps))
    return out


def spectrum(values, weights, angles, length):
    n = np.arange(-NMAX, NMAX + 1)
    return (np.exp(-1j * np.outer(n, angles)) @ (weights[:, None] * values)).T / length   # (columns, n)


def pair_sum(U, V, p):
    """sum_n U_n V_{-p-n} row by row (paired columns)."""
    n = np.arange(-NMAX, NMAX + 1)
    j = -p - n
    keep = np.abs(j) <= NMAX
    return U[:, keep] * V[:, j[keep] + NMAX]


def compute(job):
    name, coefficients, output = job
    from experiments.shape_continuation import atlas_cases as ac, trajectory_atlas as ta
    from experiments.shape_continuation.forward import PointSourceAcquisition, shape_jacobian, solve
    from experiments.shape_continuation.geometry import FourierCurve, arclength_angles, normal_basis
    curve = FourierCurve(np.asarray(coefficients))
    observations, _ = ta.catalog()
    contrast = ac.contrast()
    arrays, started = {}, time.perf_counter()
    for nodes in GRIDS:
        U_all, V_all, Jm, Jn, Jp, data = [], [], [], [], [], []
        for obs in observations:
            acq = obs.acquisition
            full = PointSourceAcquisition(acq.sources, acq.receivers, acq.strength, paired=False)
            state = solve(curve, obs.wavenumber, contrast, full, nodes)
            reciprocal, _ = ta.reciprocal_traces(state)
            u, v = state.traces[:nodes], reciprocal[:nodes]
            angles, length = arclength_angles(state.curve)
            w = state.curve.arc_length_weights
            U, V = spectrum(u, w, angles, length), spectrum(v, w, angles, length)
            delta = state.interior_wavenumber ** 2 - state.wavenumber ** 2
            P = np.arange(-PMAX, PMAX + 1)
            modal = np.array([delta * length * pair_sum(U, V, p).sum(axis=1) for p in P])          # (P, pairs)
            nodal = delta * np.exp(1j * np.outer(P, angles)) @ (w[:, None] * u * v)                  # (P, pairs)
            paired = PointSourceAcquisition(acq.sources, acq.receivers, acq.strength, paired=True)
            U_all.append(U); V_all.append(V); Jm.append(modal); Jn.append(nodal)
            data.append(np.diag(state.prediction))
            if nodes == GRIDS[0]:
                ps = solve(curve, obs.wavenumber, contrast, paired, nodes)
                Jp.append(shape_jacobian(ps, normal_basis(ps.curve, PMAX)))                      # (pairs, 1+2P)
        tag = str(nodes)
        arrays[f'U_{tag}'], arrays[f'V_{tag}'] = np.stack(U_all), np.stack(V_all)
        arrays[f'modal_{tag}'], arrays[f'nodal_{tag}'] = np.stack(Jm), np.stack(Jn)
        arrays[f'data_{tag}'] = np.stack(data)
        arrays[f'length_{tag}'] = np.array(length)
        if Jp:
            arrays['production_512'] = np.stack(Jp)
    arrays['wavenumbers'] = np.array([o.wavenumber for o in observations])
    arrays['contrast'] = np.array(contrast)
    arrays['coefficients'] = curve.coefficients
    path = Path(output) / (name.replace('/', '__') + '.npz')
    np.savez_compressed(path, **arrays)
    return name, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    table = states()
    meta = {k.replace('meta/', ''): v for k, v in table.items() if k.startswith('meta/')}
    jobs = [(k, v.coefficients, str(out)) for k, v in table.items() if not k.startswith('meta/')]
    (out / 'states.json').write_text(json.dumps(dict(states=[j[0] for j in jobs], endpoints=meta), indent=1))
    with ProcessPoolExecutor(args.workers) as pool:
        for name, seconds in pool.map(compute, jobs):
            print(f'{name}: {seconds:.1f} s', flush=True)


if __name__ == '__main__':
    main()
