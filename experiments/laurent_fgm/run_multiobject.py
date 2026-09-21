"""Second decisive experiment of the 2026-09-18 report.

Build local responses S_j for two objects, check them against the analytic
cylindrical-wave benchmark and against the monolithic Muller solve, sweep the
separation from several wavelengths down toward near-touching, and record the
required local modal order, assembly/factorisation/repeated-source cost, and
the selective-reuse saving when only one object moves.

Success criterion (report): local orders stay much smaller than the full global
trace dimension over the intended separation range, and selective reuse gives a
compelling many-source or optimisation-step speedup.
Kill criterion (report): useful accuracy needs a local order comparable to the
full boundary discretisation at ordinary separations, or the near-field fix is
so elaborate that a monolithic BIE is simpler and equally fast.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.run_multiobject --output DIR
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
from .multiobject import (LocalResponse, local_solve, mie_response, monolithic)
from .run_decay import CONTRAST, grid_for, provenance

TOLERANCES = [1e-3, 1e-6, 1e-9]


def bounding_radius(coefficients):
    t = 2 * np.pi * np.arange(4096) / 4096
    return float(np.abs(curvelib.evaluate(coefficients, t)
                        - coefficients.get(0, 0j)).max())


def placed(coefficients, centre):
    moved = dict(coefficients)
    moved[0] = complex(centre)
    return moved


def monolithic_data(objects, ko, ki, cutoff, grid, sources, receivers):
    matrix, assemble_seconds = monolithic(objects, ko, ki, cutoff, grid)
    started = perf_counter()
    factors = lu_factor(matrix)
    factor_seconds = perf_counter() - started
    rhs = np.concatenate([point_source_traces(o, sources, ko, cutoff, grid=grid)
                          for o in objects], axis=0)
    obs = np.concatenate([receiver_operator(o, receivers, ko, cutoff, grid=grid)
                          for o in objects], axis=1)
    started = perf_counter()
    y = obs @ lu_solve(factors, rhs)
    return y, dict(monolithic_assemble=assemble_seconds,
                   monolithic_factor=factor_seconds,
                   monolithic_solve=perf_counter() - started,
                   monolithic_dimension=matrix.shape[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--kd', type=float, nargs='+', default=[10., 30.])
    parser.add_argument('--gaps', type=float, nargs='+',
                        default=[3., 2., 1., .5, .25, .12, .06, .03])
    parser.add_argument('--cutoff', type=int, default=0)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f'{args.output} already exists; use a fresh directory.')
    args.output.mkdir(parents=True)

    library = curvelib.library()
    pairs = {'two_circles': (library['circle'], library['circle']),
             'ellipse_crescent': (library['ellipse'], library['crescent'])}
    angle = 2 * np.pi * np.arange(24) / 24
    rows, reuse_rows = [], []

    for pair_name, (first, second) in pairs.items():
        for kd in args.kd:
            ko = float(kd)            # unit-diameter curves, so k = kD
            ki = ko * CONTRAST
            wavelength = 2 * np.pi / ko
            radii = (bounding_radius(first), bounding_radius(second))
            cutoff = args.cutoff or int(max(32, 2.2 * ko * max(radii) + 24))
            grid = grid_for(cutoff)
            for gap in args.gaps:
                separation = radii[0] + radii[1] + gap * wavelength
                objects = [placed(first, -separation / 2),
                           placed(second, separation / 2)]
                probe = 3 * separation + 6 * wavelength
                sources = np.column_stack((probe * np.cos(angle),
                                           probe * np.sin(angle)))
                receivers = np.column_stack((probe * np.cos(angle + .13),
                                             probe * np.sin(angle + .13)))
                reference, timings = monolithic_data(objects, ko, ki, cutoff,
                                                     grid, sources, receivers)
                refined, _ = monolithic_data(objects, ko, ki, cutoff, 2 * grid,
                                             sources, receivers)
                control = relative(refined, reference)

                built, per_object = [], []
                for obj in objects:
                    started = perf_counter()
                    response = LocalResponse(obj, ko, ki, cutoff,
                                             order=int(2.4 * ko * max(radii) + 40),
                                             grid=grid)
                    per_object.append(dict(response.seconds,
                                           wall=perf_counter() - started))
                    built.append(response)
                mie_error = float('nan')
                if pair_name == 'two_circles':
                    mie_error = relative(built[0].s,
                                         mie_response(radii[0], ko, ki,
                                                      built[0].order))
                full_order = built[0].order
                errors = {}
                for order in range(2, full_order + 1, 2):
                    trimmed = []
                    for response in built:
                        clone = object.__new__(LocalResponse)
                        clone.__dict__.update(response.__dict__)
                        keep = slice(full_order - order, full_order + order + 1)
                        clone.s = response.s[keep, keep]
                        clone.order = order
                        trimmed.append(clone)
                    field, seconds = local_solve(trimmed, ko, sources, receivers)
                    errors[order] = (relative(field, reference), seconds)
                row = dict(pair=pair_name, kd=float(kd), gap_wavelengths=float(gap),
                           separation=separation, gap_absolute=gap * wavelength,
                           cutoff=cutoff, grid=grid, trace_dimension=2 * (2 * cutoff + 1),
                           bounding_radii=list(radii), mie_error=mie_error,
                           monolithic_grid_control=control,
                           local_assemble=sum(p['assemble'] for p in per_object),
                           local_factor=sum(p['factor'] for p in per_object),
                           local_respond=sum(p['respond'] for p in per_object),
                           local_total=sum(p['wall'] for p in per_object),
                           **timings)
                for tolerance in TOLERANCES:
                    ok = [o for o, (e, _) in errors.items() if e <= tolerance]
                    row[f'order_{tolerance:g}'] = min(ok) if ok else -1
                    row[f'coupling_dimension_{tolerance:g}'] = (
                        2 * min(ok) + 1 if ok else -1)
                    if ok:
                        row[f'coupling_solve_{tolerance:g}'] = errors[min(ok)][1]
                row['best_error'] = min(e for e, _ in errors.values())
                rows.append(row)
                print(f'  {pair_name:17s} kD={kd:5.1f} gap={gap:5.2f}lam '
                      f'K={cutoff} order(1e-6)={row["order_1e-06"]} '
                      f'best={row["best_error"]:.1e} ctl={control:.1e}', flush=True)

                if gap in (1., .12):
                    moved = [placed(first, -separation / 2 + .004),
                             placed(second, separation / 2)]
                    started = perf_counter()
                    rebuilt = [LocalResponse(o, ko, ki, cutoff,
                                             order=full_order, grid=grid)
                               for o in moved]
                    rebuild_all = perf_counter() - started
                    started = perf_counter()
                    partial = [LocalResponse(moved[0], ko, ki, cutoff,
                                             order=full_order, grid=grid), built[1]]
                    rebuild_one = perf_counter() - started
                    field_all, solve_all = local_solve(rebuilt, ko, sources, receivers)
                    field_one, _ = local_solve(partial, ko, sources, receivers)
                    mono_started = perf_counter()
                    monolithic_data(moved, ko, ki, cutoff, grid, sources, receivers)
                    reuse_rows.append(dict(
                        pair=pair_name, kd=float(kd), gap_wavelengths=float(gap),
                        rebuild_all=rebuild_all, rebuild_moved_only=rebuild_one,
                        monolithic_rebuild=perf_counter() - mono_started,
                        coupling_solve=solve_all,
                        agreement=relative(field_one, field_all)))

    for name, payload in (('separation', rows), ('reuse', reuse_rows)):
        (args.output / f'{name}.json').write_text(
            json.dumps(payload, indent=2, allow_nan=True) + '\n')
        keys = sorted({k for row in payload for k in row})
        with (args.output / f'{name}.csv').open('w') as stream:
            stream.write(','.join(keys) + '\n')
            for row in payload:
                stream.write(','.join(str(row.get(k, '')) for k in keys) + '\n')
    (args.output / 'provenance.json').write_text(
        json.dumps(provenance(), indent=2) + '\n')
    print(f'wrote {len(rows)} separation rows to {args.output}')


if __name__ == '__main__':
    main()
