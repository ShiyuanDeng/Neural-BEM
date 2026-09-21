"""First decisive experiment of the 2026-09-18 report, in its literature form.

Question: does the modal Muller matrix inherit predictable compressibility from
the geometry, and does truncation preserve receiver fields *and shape
gradients*?  Fang-Jiang-Su 2024 (arXiv:2408.02199) answers the first half for
their operator with

    |A_mn| <= C exp(-b |m-n|),   any b < b*,

b* the analyticity strip half-width of the boundary, with no wavenumber in the
exponent; and they truncate to ``|m-n| <= q ln N``.

This driver measures the realised rate against b*, sweeps kD = 2, 10, 30 to test
the claimed k-independence, then, for each accuracy target, finds the *smallest*
band that preserves it and records the four errors the report asks for: matrix,
boundary trace, receiver field, shape gradient.  The published rules are scored
as written alongside.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.run_decay --output DIR
"""
import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import scipy

from . import curves as curvelib
from . import decay as decaylib
from .assembler import (FourierGalerkinMuller, point_source_traces,
                        receiver_operator)

CONTRAST = 1 / np.sqrt(2.)   # k_i/k_o from the project's GPR acquisition, eps 6 -> 3
DIRECTIONS = [(2, 1.), (3, 1.), (-2, 1j), (1, 1j)]
TOLERANCES = [1e-2, 1e-4, 1e-6]


def acquisition(count=16, radius=1.5):
    angle = 2 * np.pi * np.arange(count) / count
    sources = np.column_stack((radius * np.cos(angle), radius * np.sin(angle)))
    offset = angle + np.pi / count
    receivers = np.column_stack((radius * np.cos(offset), radius * np.sin(offset)))
    return sources, receivers


def grid_for(cutoff):
    return int(1 << max(8, int(np.ceil(np.log2(8 * cutoff)))))


def forward(coefficients, ko, ki, cutoff, grid, sources, receivers):
    operator = FourierGalerkinMuller(coefficients, grid=grid)
    matrix, _ = operator.assemble(ko, ki, cutoff)
    rhs = point_source_traces(coefficients, sources, ko, cutoff, grid=grid)
    obs = receiver_operator(coefficients, receivers, ko, cutoff, grid=grid)
    return matrix, rhs, obs


def choose_cutoff(coefficients, ko, ki, sources, receivers, tolerance=1e-10,
                  start=16, limit=176):
    """Smallest cutoff whose receiver data is converged, by stepped refinement."""
    previous, cutoff = None, start
    while cutoff <= limit:
        matrix, rhs, obs = forward(coefficients, ko, ki, cutoff, grid_for(cutoff),
                                   sources, receivers)
        _, y = decaylib.pipeline(matrix, rhs, obs)
        if previous is not None and decaylib.relative(previous, y) < tolerance:
            return cutoff, float(decaylib.relative(previous, y))
        previous, cutoff = y, cutoff + max(8, cutoff // 2)
    return min(cutoff, limit), float('nan')


def perturbed_systems(coefficients, ko, ki, cutoff, grid, sources, receivers, step):
    """Assemble the +/- systems once; every mask then reuses them."""
    systems = []
    for mode, direction in DIRECTIONS:
        pair = []
        for sign in (1, -1):
            moved = dict(coefficients)
            moved[mode] = moved.get(mode, 0j) + sign * step * direction
            pair.append(forward(moved, ko, ki, cutoff, grid, sources, receivers))
        systems.append(pair)
    return systems


def jacobian(systems, mask, step):
    columns = []
    for pair in systems:
        values = []
        for matrix, rhs, obs in pair:
            _, y = decaylib.pipeline(matrix if mask is None else matrix * mask,
                                     rhs, obs)
            values.append(y)
        columns.append(((values[0] - values[1]) / (2 * step)).ravel())
    return np.array(columns)


def scan_bands(matrix, rhs, obs, state, y, cutoff, systems, truth, step):
    """All four report errors for every band half-width 0 .. 2*cutoff."""
    rows = []
    for halfband in range(0, 2 * cutoff + 1):
        mask = decaylib.fjs_band(cutoff, halfband)
        kept, stats = decaylib.truncate(matrix, mask)
        try:
            state_t, y_t = decaylib.pipeline(kept, rhs, obs)
            trace_error = decaylib.relative(state_t, state)
            field_error = decaylib.relative(y_t, y)
            gradient_error = decaylib.relative(jacobian(systems, mask, step), truth)
        except np.linalg.LinAlgError:
            trace_error = field_error = gradient_error = float('inf')
        rows.append(dict(halfband=halfband, **stats, trace_error=trace_error,
                         field_error=field_error, gradient_error=gradient_error))
    return rows


def smallest(rows, key, tolerance):
    ok = [r for r in rows if r[key] <= tolerance]
    return min(ok, key=lambda r: r['halfband']) if ok else None


def provenance():
    files = sorted(Path('experiments/laurent_fgm').glob('*.py'))
    digest = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    run = lambda *c: subprocess.run(c, capture_output=True, text=True).stdout.strip()
    return dict(sources=digest, revision=run('git', 'rev-parse', 'HEAD'),
                working_tree_dirty=bool(run('git', 'status', '--porcelain')),
                numpy=np.__version__, scipy=scipy.__version__,
                python=platform.python_version())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--kd', type=float, nargs='+', default=[2., 10., 30.])
    parser.add_argument('--step', type=float, default=1e-5)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f'{args.output} already exists; use a fresh directory.')
    args.output.mkdir(parents=True)

    sources, receivers = acquisition()
    library = curvelib.library()
    geometry = {name: dict(
        halfwidth=curvelib.analyticity_halfwidth(c),
        simple=curvelib.is_simple(c), star_defect=curvelib.star_shaped_defect(c),
        modes=sorted(int(j) for j in c if j != 0),
        max_mode=max(abs(int(j)) for j in c if j != 0),
        coefficients={str(j): [float(v.real), float(v.imag)] for j, v in c.items()})
        for name, c in library.items()}
    (args.output / 'geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')

    profiles, scans, selected, published = [], [], [], []
    for name, coefficients in library.items():
        for kd in args.kd:
            ko = float(kd) / curvelib.diameter(coefficients)
            ki = ko * CONTRAST
            cutoff, converged = choose_cutoff(coefficients, ko, ki, sources, receivers)
            grid = grid_for(cutoff)
            matrix, rhs, obs = forward(coefficients, ko, ki, cutoff, grid,
                                       sources, receivers)
            state, y = decaylib.pipeline(matrix, rhs, obs)
            order = 2 * cutoff + 1
            base = dict(curve=name, kd=float(kd), ko=ko, cutoff=cutoff, order=order,
                        grid=grid, cutoff_converged=converged,
                        halfwidth=geometry[name]['halfwidth'],
                        max_mode=geometry[name]['max_mode'])

            blocks = dict(V=matrix[:order, order:],
                          K=np.eye(order) - matrix[:order, :order],
                          T=-matrix[order:, :order],
                          Kp=matrix[order:, order:] - np.eye(order))
            for label, block in blocks.items():
                profile = decaylib.band_profile(block)
                fit = decaylib.decay_rate(profile['offset'], profile['peak'])
                base[f'rate_{label}'] = fit['rate']
                base[f'r2_{label}'] = fit['r2']
                profiles.append(dict(curve=name, kd=float(kd), block=label,
                                     offset=profile['offset'].tolist(),
                                     peak=profile['peak'].tolist(),
                                     rms=profile['rms'].tolist()))
            envelope = decaylib.band_profile(np.maximum.reduce(
                [np.abs(b) / np.abs(b).max() for b in blocks.values()]))
            base['rate_envelope'] = decaylib.decay_rate(
                envelope['offset'], envelope['peak'])['rate']
            for level in (1e-1, 1e-3, 1e-6):
                below = envelope['peak'] / envelope['peak'].max() < level
                base[f'knee_{level:g}'] = int(np.argmax(below)) if below.any() else -1
            profiles.append(dict(curve=name, kd=float(kd), block='envelope',
                                 offset=envelope['offset'].tolist(),
                                 peak=envelope['peak'].tolist(),
                                 rms=envelope['rms'].tolist()))

            systems = perturbed_systems(coefficients, ko, ki, cutoff, grid,
                                        sources, receivers, args.step)
            truth = jacobian(systems, None, args.step)
            base['gradient_step_consistency'] = decaylib.relative(
                jacobian(perturbed_systems(coefficients, ko, ki, cutoff, grid,
                                           sources, receivers, args.step * 4),
                         None, args.step * 4), truth)

            rows = scan_bands(matrix, rhs, obs, state, y, cutoff, systems, truth,
                              args.step)
            for row in rows:
                scans.append(dict(base, **row))
            for tolerance in TOLERANCES:
                field = smallest(rows, 'field_error', tolerance)
                grad = smallest(rows, 'gradient_error', tolerance)
                entry = dict(base, tolerance=tolerance,
                             shape_direction_modes=max(abs(m) for m, _ in DIRECTIONS),
                             field_halfband=field['halfband'] if field else -1,
                             gradient_halfband=grad['halfband'] if grad else -1)
                if field:
                    entry.update({f'field_{k}': v for k, v in field.items()})
                    entry['field_band_over_kd'] = field['halfband'] / float(kd)
                    entry['field_q_equivalent'] = field['halfband'] / np.log(order)
                if grad:
                    entry.update({f'gradient_{k}': v for k, v in grad.items()})
                    entry['gradient_band_over_kd'] = grad['halfband'] / float(kd)
                    entry['gradient_q_equivalent'] = grad['halfband'] / np.log(order)
                if field and grad:
                    entry['band_penalty'] = grad['halfband'] - field['halfband']
                selected.append(entry)
            for label, mask, parameter in (
                    [(f'fjs_q{q:g}', decaylib.fjs_band(cutoff, q * np.log(order)), q)
                     for q in (1., 2., 4.)]
                    + [('jwy_mu1.2', decaylib.jwy_mask(cutoff, 1.2), 1.2)]):
                kept, stats = decaylib.truncate(matrix, mask)
                try:
                    state_t, y_t = decaylib.pipeline(kept, rhs, obs)
                    entry = dict(trace_error=decaylib.relative(state_t, state),
                                 field_error=decaylib.relative(y_t, y),
                                 gradient_error=decaylib.relative(
                                     jacobian(systems, mask, args.step), truth))
                except np.linalg.LinAlgError:
                    entry = dict(trace_error=float('inf'), field_error=float('inf'),
                                 gradient_error=float('inf'))
                published.append(dict(base, rule=label, parameter=parameter,
                                      **stats, **entry))
            print(f'  {name:11s} kD={kd:5.1f} K={cutoff:3d} done', flush=True)

    for name, payload in (('profiles', profiles), ('scan', scans),
                          ('selected', selected), ('published', published)):
        (args.output / f'{name}.json').write_text(
            json.dumps(payload, indent=None if name == 'profiles' else 2,
                       allow_nan=True) + '\n')
        if name == 'profiles':
            continue
        keys = sorted({k for row in payload for k in row})
        with (args.output / f'{name}.csv').open('w') as stream:
            stream.write(','.join(keys) + '\n')
            for row in payload:
                stream.write(','.join(str(row.get(k, '')) for k in keys) + '\n')
    (args.output / 'provenance.json').write_text(
        json.dumps(provenance(), indent=2) + '\n')
    print(f'wrote {len(scans)} scan rows and {len(selected)} selections to {args.output}')


if __name__ == '__main__':
    main()
