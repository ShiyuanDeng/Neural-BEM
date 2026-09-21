"""Where does the local-response route overtake the monolithic Muller solve?

The separation sweep shows the local formulation is exact and its coupling
dimension is 3-7x smaller than the trace dimension, yet at J = 2 objects the
monolithic solve is faster end to end because both pay the same per-object
assembly.  The mechanism that should win is the scaling: monolithic
factorisation is O((J M)^3) while the local route is O(J M^3) plus O((J p)^3)
with p << M, and one moved object costs 1/J of a rebuild.

This driver measures that crossover directly, on a ring of J objects.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.run_scaling --output DIR
"""
import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from . import curves as curvelib
from .assembler import point_source_traces, receiver_operator
from .decay import relative
from .multiobject import LocalResponse, local_solve, monolithic
from .run_decay import CONTRAST, grid_for


def ring(count, coefficients, radius):
    angle = 2 * np.pi * np.arange(count) / count
    placed = []
    for value in angle:
        moved = dict(coefficients)
        moved[0] = radius * np.exp(1j * value)
        placed.append(moved)
    return placed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--counts', type=int, nargs='+', default=[2, 3, 4, 6, 8, 12, 16])
    parser.add_argument('--kd', type=float, default=10.)
    parser.add_argument('--gap', type=float, default=1.)
    parser.add_argument('--order', type=int, default=14)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f'{args.output} already exists; use a fresh directory.')
    args.output.mkdir(parents=True)

    shape = curvelib.library()['ellipse']
    ko = args.kd
    ki = ko * CONTRAST
    wavelength = 2 * np.pi / ko
    bound = float(np.abs(curvelib.evaluate(shape, 2 * np.pi * np.arange(2048) / 2048)
                         - shape.get(0, 0j)).max())
    cutoff = int(max(32, 2.2 * ko * bound + 24))
    grid = grid_for(cutoff)
    rows = []
    for count in args.counts:
        spacing = 2 * bound + args.gap * wavelength
        radius = spacing / (2 * np.sin(np.pi / count))
        objects = ring(count, shape, radius)
        probe = radius + 6 * wavelength + 2 * bound
        angle = 2 * np.pi * np.arange(32) / 32
        sources = np.column_stack((probe * np.cos(angle), probe * np.sin(angle)))
        receivers = np.column_stack((probe * np.cos(angle + .1),
                                     probe * np.sin(angle + .1)))

        started = perf_counter()
        matrix, _ = monolithic(objects, ko, ki, cutoff, grid)
        mono_assemble = perf_counter() - started
        started = perf_counter()
        factors = lu_factor(matrix)
        mono_factor = perf_counter() - started
        rhs = np.concatenate([point_source_traces(o, sources, ko, cutoff, grid=grid)
                              for o in objects], axis=0)
        obs = np.concatenate([receiver_operator(o, receivers, ko, cutoff, grid=grid)
                              for o in objects], axis=1)
        started = perf_counter()
        reference = obs @ lu_solve(factors, rhs)
        mono_solve = perf_counter() - started

        started = perf_counter()
        responses = [LocalResponse(o, ko, ki, cutoff, args.order, grid)
                     for o in objects]
        local_build = perf_counter() - started
        field, coupling_seconds = local_solve(responses, ko, sources, receivers)

        started = perf_counter()
        moved = dict(objects[0])
        moved[0] += .004
        replaced = [LocalResponse(moved, ko, ki, cutoff, args.order, grid)] + responses[1:]
        reuse_build = perf_counter() - started
        _, reuse_solve = local_solve(replaced, ko, sources, receivers)
        started = perf_counter()
        remonolithic, _ = monolithic([moved] + objects[1:], ko, ki, cutoff, grid)
        lu_factor(remonolithic)
        mono_step = perf_counter() - started

        rows.append(dict(
            objects=count, kd=args.kd, gap_wavelengths=args.gap, cutoff=cutoff,
            order=args.order, monolithic_dimension=matrix.shape[0],
            coupling_dimension=count * (2 * args.order + 1),
            agreement=relative(field, reference),
            monolithic_assemble=mono_assemble, monolithic_factor=mono_factor,
            monolithic_solve=mono_solve,
            monolithic_total=mono_assemble + mono_factor + mono_solve,
            local_build=local_build, coupling_solve=coupling_seconds,
            local_total=local_build + coupling_seconds,
            optimisation_step_monolithic=mono_step,
            optimisation_step_local=reuse_build + reuse_solve))
        print(f'  J={count:3d} dim={matrix.shape[0]:5d} agree={rows[-1]["agreement"]:.1e} '
              f'mono={rows[-1]["monolithic_total"]:7.3f}s local={rows[-1]["local_total"]:7.3f}s '
              f'step mono={mono_step:6.3f}s local={rows[-1]["optimisation_step_local"]:6.3f}s',
              flush=True)

    (args.output / 'scaling.json').write_text(json.dumps(rows, indent=2) + '\n')
    keys = sorted({k for row in rows for k in row})
    with (args.output / 'scaling.csv').open('w') as stream:
        stream.write(','.join(keys) + '\n')
        for row in rows:
            stream.write(','.join(str(row.get(k, '')) for k in keys) + '\n')
    print(f'wrote {len(rows)} scaling rows to {args.output}')


if __name__ == '__main__':
    main()
