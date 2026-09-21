"""Does one offline basis serve a whole inversion, or only one boundary?

Section 6c priced the affine model `A(k) ~= sum_r theta_r(k) A_r` and found the
break-even one for one with the training set: about 82 online frequencies for a
`1e-6` model.  A Gauss-Newton inversion never reaches that at a *fixed* geometry
-- it solves a few tens of frequencies and then moves the boundary -- so on that
accounting the decomposition is useless for the application it was built for.

That accounting assumes the reconstruction has to be accurate enough to solve
with.  It does not: 6c also showed `LU(A_hat)` preconditions the true operator to
`rtol = 1e-10` in 2 iterations, and still in 4 when `A_hat` is only `1e-4`
accurate.  So the question this driver asks is whether a basis trained on one
boundary `c0` keeps preconditioning as the boundary moves:

    GMRES on the true A(k, c) preconditioned by LU(A_hat(k, c0)),

against two controls -- plain GMRES, and the single anchor factorisation
`LU(A(k_anchor, c0))` of section 6b, which is what you would use if the affine
basis bought nothing.  The comparison against that second control is the whole
experiment: the affine path costs an interpolation and a factorisation per
frequency, and has to beat simply reusing one LU to be worth it.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.run_transfer --output DIR
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse.linalg import LinearOperator

from . import curves as curvelib
from .run_affine import interpolate, iterations, rank_for, snapshot_basis
from .run_decay import CONTRAST, acquisition, forward, grid_for, provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--curves', nargs='+', default=['ellipse', 'kite', 'crescent'])
    parser.add_argument('--low', type=float, default=4.)
    parser.add_argument('--high', type=float, default=24.)
    parser.add_argument('--samples', type=int, default=81)
    parser.add_argument('--tolerance', type=float, default=1e-6)
    parser.add_argument('--shifts', type=float, nargs='+',
                        default=[0., .01, .02, .04, .08])
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f'{args.output} already exists; use a fresh directory.')
    args.output.mkdir(parents=True)

    sources, receivers = acquisition()
    library = curvelib.library()
    waves = np.linspace(args.low, args.high, args.samples)
    spacing = float(waves[1] - waves[0])
    held = waves[np.linspace(2, args.samples - 3, 6).astype(int)] + .5 * spacing
    rows = []

    for name in args.curves:
        base = library[name]
        cutoff = int(2.2 * args.high * .5 + 30)
        grid = grid_for(cutoff)

        def assemble(shape, kd):
            ko = float(kd) / curvelib.diameter(shape)
            return forward(shape, ko, ko * CONTRAST, cutoff, grid, sources, receivers)

        left, theta, values = snapshot_basis([assemble(base, kd)[0] for kd in waves])
        rank = rank_for(values, args.tolerance)
        basis = left[:, :rank]
        predicted = interpolate(waves, theta[:rank], held)
        shape_of = (2 * (2 * cutoff + 1),) * 2

        anchor = float(waves[waves.size // 2])
        anchor_factors = lu_factor(assemble(base, anchor)[0])
        anchor_operator = LinearOperator(
            shape_of, matvec=lambda v: lu_solve(anchor_factors, v), dtype=complex)

        for shift in args.shifts:
            moved = dict(base)
            moved[2] = moved.get(2, 0j) + shift
            for column, kd in enumerate(held):
                matrix, rhs, _ = assemble(moved, kd)
                reconstructed = (basis @ predicted[:, column]).reshape(shape_of)
                factors = lu_factor(reconstructed)
                affine = LinearOperator(
                    shape_of, matvec=lambda v: lu_solve(factors, v), dtype=complex)
                reference = assemble(base, kd)[0]
                rows.append(dict(
                    curve=name, rank=rank, samples=args.samples, shift=float(shift),
                    kd=float(kd), anchor_kd=anchor,
                    geometry_change=float(np.linalg.norm(matrix - reference)
                                          / np.linalg.norm(reference)),
                    reconstruction_error=float(
                        np.linalg.norm(reconstructed - matrix)
                        / np.linalg.norm(matrix)),
                    affine_iterations=iterations(matrix, rhs[:, 0], affine),
                    anchor_iterations=iterations(matrix, rhs[:, 0], anchor_operator),
                    plain_iterations=iterations(matrix, rhs[:, 0])))
            recent = rows[-held.size:]
            print(f'  {name:10s} r={rank:3d} shift={shift:5.3f} '
                  f'|dA|/|A|={np.median([r["geometry_change"] for r in recent]):6.3f} '
                  f'affine={np.median([r["affine_iterations"] for r in recent]):3.0f} '
                  f'anchor={np.median([r["anchor_iterations"] for r in recent]):3.0f} '
                  f'plain={np.median([r["plain_iterations"] for r in recent]):3.0f}',
                  flush=True)

    (args.output / 'transfer.json').write_text(
        json.dumps(rows, indent=2, allow_nan=True) + '\n')
    keys = sorted({k for row in rows for k in row})
    with (args.output / 'transfer.csv').open('w') as stream:
        stream.write(','.join(keys) + '\n')
        for row in rows:
            stream.write(','.join(str(row.get(k, '')) for k in keys) + '\n')
    (args.output / 'provenance.json').write_text(
        json.dumps(provenance(), indent=2) + '\n')
    print(f'wrote {len(rows)} transfer rows to {args.output}')


if __name__ == '__main__':
    main()
