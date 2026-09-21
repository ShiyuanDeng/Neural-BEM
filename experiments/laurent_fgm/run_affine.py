"""Is the low operator rank in k an affine decomposition you can actually use?

The broadband screen measured `rank(A(k)) = 7 / 11 / 14` at 1e-3 / 1e-6 / 1e-9
over kD in [4, 24].  That is only half of what an affine reduced model

    A(k) ~= sum_r theta_r(k) A_r

needs.  The other half is that the coefficients `theta_r(k)` are recoverable at
a frequency that was never assembled.  Nothing in a singular value spectrum
says they are: the spectrum is computed *from* the snapshots it is asked to
represent, so a rank that small is compatible with coefficients that oscillate
too fast to interpolate from any affordable set of them.

This driver separates the two error sources at held-out frequencies:

    projection    ||(I - P_r) vec A(k)|| / ||vec A(k)||      basis, best case
    interpolation ||A_hat(k) - A(k)||_F  / ||A(k)||_F        basis + spline

`projection` is the floor the rank promises.  `interpolation` is what you
actually get.  The gap between them is the part the rank number does not cover.

It then prices the result three ways, because "rank 11" is a statement about
assembly, not about solving:

  * reconstruct-and-solve   -- factor A_hat(k) and use its solution directly;
  * reconstruct-and-precondition -- factor A_hat(k), GMRES on the true A(k),
    which needs no assembly at the new frequency and is exact at convergence;
  * break-even              -- the offline cost is `n_train` assemblies, so the
    online band has to be wider than that before anything is saved.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.run_affine --output DIR
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse.linalg import LinearOperator, gmres

from . import curves as curvelib
from .decay import relative
from .run_decay import CONTRAST, acquisition, forward, grid_for, provenance

TOLERANCES = (1e-3, 1e-6, 1e-9)


def snapshot_basis(matrices):
    """Q, theta with vec A(k_j) = Q @ theta[:, j]; Q orthonormal, theta ordered."""
    stack = np.array([m.ravel() for m in matrices]).T
    left, values, right = np.linalg.svd(stack, full_matrices=False)
    return left, values[:, None] * right, values / values[0]


def rank_for(values, tolerance):
    below = np.flatnonzero(values < tolerance)
    return int(below[0]) if below.size else int(values.size)


def interpolate(waves, theta, targets):
    """Cubic spline of each coefficient across frequency, real and imaginary."""
    real = CubicSpline(waves, theta.real, axis=1)(targets)
    imaginary = CubicSpline(waves, theta.imag, axis=1)(targets)
    return real + 1j * imaginary


def iterations(matrix, rhs, preconditioner=None):
    count = [0]
    gmres(matrix, rhs, M=preconditioner, rtol=1e-10, restart=60, maxiter=400,
          callback=lambda _: count.__setitem__(0, count[0] + 1))
    return count[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--curves', nargs='+', default=['ellipse', 'kite', 'crescent'])
    parser.add_argument('--low', type=float, default=4.)
    parser.add_argument('--high', type=float, default=24.)
    parser.add_argument('--finest', type=int, default=161)
    parser.add_argument('--strides', type=int, nargs='+', default=[16, 8, 4, 2, 1])
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f'{args.output} already exists; use a fresh directory.')
    args.output.mkdir(parents=True)

    sources, receivers = acquisition()
    library = curvelib.library()
    master = np.linspace(args.low, args.high, args.finest)
    spacing = float(master[1] - master[0])
    # Held-out frequencies at fine-grid midpoints: never a node of any stride,
    # and the furthest a target can sit from the densest training set.
    picks = np.unique(np.linspace(2, args.finest - 3, 8).astype(int))
    held = master[picks] + .5 * spacing
    assert np.abs(held[:, None] - master[None, :]).min() > .49 * spacing

    spectra, accuracy, timing = [], [], []
    for name in args.curves:
        coefficients = library[name]
        cutoff = int(2.2 * args.high * .5 + 30)
        grid = grid_for(cutoff)
        diameter = curvelib.diameter(coefficients)

        def system(kd):
            ko = float(kd) / diameter
            return forward(coefficients, ko, ko * CONTRAST, cutoff, grid,
                           sources, receivers)

        clock = time.perf_counter()
        trained = [system(kd)[0] for kd in master]
        assembly_seconds = (time.perf_counter() - clock) / args.finest
        exact = {float(kd): system(kd) for kd in held}
        shape = trained[0].shape

        for stride in args.strides:
            waves = master[::stride]
            clock = time.perf_counter()
            left, theta, values = snapshot_basis(trained[::stride])
            decomposition_seconds = time.perf_counter() - clock
            ranks = {t: rank_for(values, t) for t in TOLERANCES}
            spectra.append(dict(curve=name, stride=int(stride),
                                spacing=spacing * stride, samples=int(waves.size),
                                singular=values[:40].tolist(),
                                **{f'rank_{t:g}': ranks[t] for t in TOLERANCES}))

            for tolerance, rank in ranks.items():
                if rank >= waves.size:
                    continue
                basis = left[:, :rank]
                predicted = interpolate(waves, theta[:rank], held)
                for column, kd in enumerate(held):
                    matrix, rhs, obs = exact[float(kd)]
                    vector = matrix.ravel()
                    norm = np.linalg.norm(vector)
                    optimal = basis.conj().T @ vector
                    clock = time.perf_counter()
                    estimate = (basis @ predicted[:, column]).reshape(shape)
                    reconstruct_seconds = time.perf_counter() - clock

                    truth = obs @ lu_solve(lu_factor(matrix), rhs)
                    clock = time.perf_counter()
                    factors = lu_factor(estimate)
                    factor_seconds = time.perf_counter() - clock
                    direct = obs @ lu_solve(factors, rhs)
                    precondition = LinearOperator(
                        shape, matvec=lambda v: lu_solve(factors, v), dtype=complex)
                    clock = time.perf_counter()
                    steps = iterations(matrix, rhs[:, 0], precondition)
                    gmres_seconds = time.perf_counter() - clock

                    accuracy.append(dict(
                        curve=name, stride=int(stride), spacing=spacing * stride,
                        samples=int(waves.size), tolerance=tolerance, rank=rank,
                        kd=float(kd),
                        projection_error=float(
                            np.linalg.norm(vector - basis @ optimal) / norm),
                        interpolation_error=float(
                            np.linalg.norm(vector - basis @ predicted[:, column])
                            / norm),
                        coefficient_error=float(
                            np.linalg.norm(predicted[:, column] - optimal)
                            / np.linalg.norm(optimal)),
                        field_error=relative(direct, truth),
                        preconditioned_iterations=steps,
                        plain_iterations=iterations(matrix, rhs[:, 0]),
                        reconstruct_seconds=reconstruct_seconds,
                        factor_seconds=factor_seconds,
                        gmres_seconds=gmres_seconds))
                print(f'  {name:10s} n={waves.size:4d} dk={spacing*stride:5.3f} '
                      f'tol={tolerance:.0e} r={rank:3d} '
                      f'proj={np.median([a["projection_error"] for a in accuracy[-held.size:]]):.2e} '
                      f'interp={np.median([a["interpolation_error"] for a in accuracy[-held.size:]]):.2e} '
                      f'gmres={np.median([a["preconditioned_iterations"] for a in accuracy[-held.size:]]):.0f}',
                      flush=True)

            timing.append(dict(curve=name, stride=int(stride),
                               samples=int(waves.size),
                               assembly_seconds=assembly_seconds,
                               offline_seconds=assembly_seconds * waves.size
                               + decomposition_seconds,
                               decomposition_seconds=decomposition_seconds))
        del trained, exact

    for tag, payload in (('spectra', spectra), ('accuracy', accuracy),
                         ('timing', timing)):
        (args.output / f'{tag}.json').write_text(
            json.dumps(payload, indent=2, allow_nan=True) + '\n')
        if tag == 'spectra':
            continue
        keys = sorted({k for row in payload for k in row})
        with (args.output / f'{tag}.csv').open('w') as stream:
            stream.write(','.join(keys) + '\n')
            for row in payload:
                stream.write(','.join(str(row.get(k, '')) for k in keys) + '\n')
    (args.output / 'provenance.json').write_text(
        json.dumps(provenance(), indent=2) + '\n')
    print(f'wrote {len(accuracy)} held-out rows to {args.output}')


if __name__ == '__main__':
    main()
