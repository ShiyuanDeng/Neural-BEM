"""Third and fourth experiments of the 2026-09-18 report.

Third: broadband low rank *without writing a ROM*.  Sample A(k) over a band and
measure three ranks separately, as the report insists:

    operator rank in k,   solution-manifold rank in k,   joint (k, c) rank,

then actually test a reduced basis on held-out frequencies, scoring the
receiver field *and* the shape gradient, since the report states that gradient
fidelity, not field error, is the metric that matters for inversion.

Fourth: the cheap diagnostic -- reuse the LU at (k_n, c_n) as a preconditioner
for solves at (k_{n+1}, c_n) and (k_n, c_{n+1}), recording GMRES iterations
against dk and ||dc||.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.run_broadband --output DIR
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import lu_factor, lu_solve, svd
from scipy.sparse.linalg import LinearOperator, gmres

from . import curves as curvelib
from .decay import relative
from .run_decay import (CONTRAST, DIRECTIONS, acquisition, forward, grid_for)
from .run_decay import provenance

STEP = 1e-5


def band(low, high, count):
    return np.linspace(low, high, count)


def snapshots(coefficients, waves, cutoff, grid, sources, receivers):
    systems = {}
    for kd in waves:
        ko = float(kd) / curvelib.diameter(coefficients)
        systems[float(kd)] = forward(coefficients, ko, ko * CONTRAST, cutoff,
                                     grid, sources, receivers)
    return systems


def spectrum_of(columns):
    values = svd(np.asarray(columns).T, compute_uv=False)
    return values / values[0]


def rank_for(values, tolerance):
    below = np.flatnonzero(values < tolerance)
    return int(below[0]) if below.size else int(values.size)


def reduced_solve(basis, matrix, rhs, receiver):
    reduced = basis.conj().T @ matrix @ basis
    return receiver @ (basis @ np.linalg.solve(reduced, basis.conj().T @ rhs))


def perturbed(coefficients, mode, direction, amount):
    moved = dict(coefficients)
    moved[mode] = moved.get(mode, 0j) + amount * direction
    return moved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--curves', nargs='+', default=['ellipse', 'kite', 'crescent'])
    parser.add_argument('--low', type=float, default=4.)
    parser.add_argument('--high', type=float, default=24.)
    parser.add_argument('--count', type=int, default=41)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f'{args.output} already exists; use a fresh directory.')
    args.output.mkdir(parents=True)

    sources, receivers = acquisition()
    library = curvelib.library()
    ranks, held, reuse = [], [], []

    for name in args.curves:
        coefficients = library[name]
        cutoff = int(2.2 * args.high * .5 + 30)
        grid = grid_for(cutoff)
        waves = band(args.low, args.high, args.count)
        train, test = waves[::2], waves[1::2]
        systems = snapshots(coefficients, waves, cutoff, grid, sources, receivers)

        operators, solutions = [], []
        for kd in train:
            matrix, rhs, obs = systems[float(kd)]
            operators.append(matrix.ravel())
            solutions.append(lu_solve(lu_factor(matrix), rhs).T)
        operator_values = spectrum_of(operators)
        solution_values = spectrum_of(np.concatenate(solutions, axis=0))

        joint_operators, joint_solutions = list(operators), list(
            np.concatenate(solutions, axis=0))
        shifts = [.0, .01, -.01, .02]
        for amount in shifts[1:]:
            moved = perturbed(coefficients, 2, 1., amount)
            for kd in train[::3]:
                ko = float(kd) / curvelib.diameter(moved)
                matrix, rhs, obs = forward(moved, ko, ko * CONTRAST, cutoff,
                                           grid, sources, receivers)
                joint_operators.append(matrix.ravel())
                joint_solutions.extend(lu_solve(lu_factor(matrix), rhs).T)
        ranks.append(dict(
            curve=name, cutoff=cutoff, dimension=2 * (2 * cutoff + 1),
            band=[args.low, args.high], samples=int(train.size),
            operator_singular=operator_values[:40].tolist(),
            solution_singular=solution_values[:40].tolist(),
            joint_operator_singular=spectrum_of(joint_operators)[:40].tolist(),
            joint_solution_singular=spectrum_of(joint_solutions)[:40].tolist(),
            **{f'operator_rank_{t:g}': rank_for(operator_values, t)
               for t in (1e-3, 1e-6, 1e-9)},
            **{f'solution_rank_{t:g}': rank_for(solution_values, t)
               for t in (1e-3, 1e-6, 1e-9)},
            **{f'joint_solution_rank_{t:g}':
               rank_for(spectrum_of(joint_solutions), t)
               for t in (1e-3, 1e-6, 1e-9)}))

        stack = np.concatenate(solutions, axis=0).T
        left, _, _ = svd(stack, full_matrices=False)
        for rank in (5, 10, 20, 40, 80):
            if rank > left.shape[1]:
                continue
            basis = left[:, :rank]
            for kd in test[::4]:
                matrix, rhs, obs = systems[float(kd)]
                truth = obs @ lu_solve(lu_factor(matrix), rhs)
                estimate = reduced_solve(basis, matrix, rhs, obs)
                gradients = []
                for tag, mask in (('full', None), ('reduced', basis)):
                    columns = []
                    for mode, direction in DIRECTIONS:
                        values = []
                        for sign in (1, -1):
                            moved = perturbed(coefficients, mode, direction,
                                              sign * STEP)
                            ko = float(kd) / curvelib.diameter(moved)
                            m, r, c = forward(moved, ko, ko * CONTRAST, cutoff,
                                              grid, sources, receivers)
                            values.append(c @ lu_solve(lu_factor(m), r) if mask is None
                                          else reduced_solve(mask, m, r, c))
                        columns.append(((values[0] - values[1]) / (2 * STEP)).ravel())
                    gradients.append(np.array(columns))
                held.append(dict(curve=name, rank=rank, kd=float(kd),
                                 field_error=relative(estimate, truth),
                                 gradient_error=relative(gradients[1], gradients[0])))
                print(f'  {name:10s} rank={rank:3d} kD={kd:5.1f} '
                      f'field={held[-1]["field_error"]:.2e} '
                      f'grad={held[-1]["gradient_error"]:.2e}', flush=True)

        anchor = float(train[train.size // 2])
        matrix, rhs, obs = systems[anchor]
        factors = lu_factor(matrix)
        precondition = LinearOperator(matrix.shape, matvec=lambda v:
                                      lu_solve(factors, v), dtype=complex)
        for delta in (0., .25, .5, 1., 2., 4.):
            for axis in ('frequency', 'geometry'):
                if axis == 'frequency':
                    kd, shape = anchor + delta, coefficients
                else:
                    kd, shape = anchor, perturbed(coefficients, 2, 1., delta * .01)
                ko = float(kd) / curvelib.diameter(shape)
                target, target_rhs, _ = forward(shape, ko, ko * CONTRAST, cutoff,
                                                grid, sources, receivers)
                count = [0]
                gmres(target, target_rhs[:, 0], M=precondition, rtol=1e-10,
                      restart=60, maxiter=400,
                      callback=lambda _: count.__setitem__(0, count[0] + 1))
                plain = [0]
                gmres(target, target_rhs[:, 0], rtol=1e-10, restart=60,
                      maxiter=400,
                      callback=lambda _: plain.__setitem__(0, plain[0] + 1))
                reuse.append(dict(curve=name, axis=axis, delta=float(delta),
                                  anchor_kd=anchor,
                                  change=float(np.linalg.norm(target - matrix)
                                               / np.linalg.norm(matrix)),
                                  preconditioned_iterations=count[0],
                                  unpreconditioned_iterations=plain[0]))

    for tag, payload in (('ranks', ranks), ('heldout', held), ('reuse', reuse)):
        (args.output / f'{tag}.json').write_text(
            json.dumps(payload, indent=2, allow_nan=True) + '\n')
        if tag == 'ranks':
            continue
        keys = sorted({k for row in payload for k in row})
        with (args.output / f'{tag}.csv').open('w') as stream:
            stream.write(','.join(keys) + '\n')
            for row in payload:
                stream.write(','.join(str(row.get(k, '')) for k in keys) + '\n')
    (args.output / 'provenance.json').write_text(
        json.dumps(provenance(), indent=2) + '\n')
    print(f'wrote {len(held)} held-out rows and {len(reuse)} reuse rows')


if __name__ == '__main__':
    main()
