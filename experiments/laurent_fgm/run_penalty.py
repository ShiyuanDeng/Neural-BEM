"""How much wider than the field's band does the shape gradient need?

The decay screen differentiated four fixed Laurent directions, so it measured
the band penalty at a single value of the shape-parameterisation mode content.
That is one point, and the rule read off it (`Q_grad >= max(Q_field, p_max)`)
is only testable by varying `p_max`.  This driver does that.

It also re-fits the decay exponent on the post-knee window alone, because a
single exponential fitted across the plateau *and* the decay returns a blend of
the two and drifts with kD for that reason rather than a physical one.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.run_penalty --output DIR
"""
import argparse
import json
from pathlib import Path

import numpy as np

from . import curves as curvelib
from . import decay as decaylib
from . import run_decay as driver

FAMILIES = [[(1, 1.), (2, 1.)],
            [(2, 1.), (3, 1.), (-2, 1j), (1, 1j)],
            [(5, 1.), (6, 1j)],
            [(9, 1.), (10, 1j)],
            [(14, 1.), (15, 1j)]]


def post_knee_rate(offset, peak, level=1e-1, floor=1e-13):
    """Exponential rate fitted only where the envelope is actually decaying."""
    envelope = np.maximum.accumulate(np.asarray(peak)[::-1])[::-1]
    envelope = envelope / envelope[0]
    knee = int(np.argmax(envelope < level)) if (envelope < level).any() else 1
    usable = (offset >= max(knee, 1)) & (envelope > floor)
    if usable.sum() < 5:
        return dict(rate=float('nan'), knee=knee, points=int(usable.sum()))
    slope, intercept = np.polyfit(offset[usable], np.log(envelope[usable]), 1)
    residual = np.log(envelope[usable]) - (slope * offset[usable] + intercept)
    total = np.log(envelope[usable]) - np.log(envelope[usable]).mean()
    return dict(rate=float(-slope), knee=knee, points=int(usable.sum()),
                r2=1. - float(residual @ residual) / float(total @ total))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--curves', nargs='+', default=['ellipse', 'kite', 'crescent'])
    parser.add_argument('--kd', type=float, nargs='+', default=[10., 30.])
    parser.add_argument('--tolerance', type=float, default=1e-6)
    parser.add_argument('--step', type=float, default=1e-5)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f'{args.output} already exists; use a fresh directory.')
    args.output.mkdir(parents=True)

    sources, receivers = driver.acquisition()
    library = curvelib.library()
    penalties, rates = [], []
    original = list(driver.DIRECTIONS)
    try:
        for name in args.curves:
            coefficients = library[name]
            for kd in args.kd:
                ko = float(kd) / curvelib.diameter(coefficients)
                ki = ko * driver.CONTRAST
                cutoff, _ = driver.choose_cutoff(coefficients, ko, ki,
                                                 sources, receivers)
                grid = driver.grid_for(cutoff)
                matrix, rhs, obs = driver.forward(coefficients, ko, ki, cutoff,
                                                  grid, sources, receivers)
                state, y = decaylib.pipeline(matrix, rhs, obs)
                order = 2 * cutoff + 1
                profile = decaylib.band_profile(matrix[:order, order:])
                rates.append(dict(curve=name, kd=float(kd), cutoff=cutoff,
                                  halfwidth=curvelib.analyticity_halfwidth(coefficients),
                                  whole_range=decaylib.decay_rate(
                                      profile['offset'], profile['peak'])['rate'],
                                  **post_knee_rate(profile['offset'], profile['peak'])))
                field_band = -1
                for halfband in range(0, 2 * cutoff + 1):
                    mask = decaylib.fjs_band(cutoff, halfband)
                    _, candidate = decaylib.pipeline(matrix * mask, rhs, obs)
                    if decaylib.relative(candidate, y) <= args.tolerance:
                        field_band = halfband
                        break
                for family in FAMILIES:
                    driver.DIRECTIONS[:] = family
                    systems = driver.perturbed_systems(coefficients, ko, ki, cutoff,
                                                       grid, sources, receivers,
                                                       args.step)
                    truth = driver.jacobian(systems, None, args.step)
                    gradient_band = -1
                    for halfband in range(max(field_band, 0), 2 * cutoff + 1):
                        mask = decaylib.fjs_band(cutoff, halfband)
                        if decaylib.relative(driver.jacobian(systems, mask, args.step),
                                             truth) <= args.tolerance:
                            gradient_band = halfband
                            break
                    penalties.append(dict(
                        curve=name, kd=float(kd), cutoff=cutoff,
                        tolerance=args.tolerance,
                        direction_modes=[int(m) for m, _ in family],
                        max_mode=max(abs(m) for m, _ in family),
                        field_halfband=field_band, gradient_halfband=gradient_band,
                        penalty=gradient_band - field_band))
                    print(f'  {name:10s} kD={kd:5.1f} p_max='
                          f'{penalties[-1]["max_mode"]:3d} Q_field={field_band:3d} '
                          f'Q_grad={gradient_band:3d} penalty='
                          f'{penalties[-1]["penalty"]:3d}', flush=True)
    finally:
        driver.DIRECTIONS[:] = original

    for tag, payload in (('penalty', penalties), ('post_knee_rates', rates)):
        (args.output / f'{tag}.json').write_text(
            json.dumps(payload, indent=2, allow_nan=True) + '\n')
        keys = sorted({k for row in payload for k in row})
        with (args.output / f'{tag}.csv').open('w') as stream:
            stream.write(','.join(keys) + '\n')
            for row in payload:
                stream.write(','.join(str(row.get(k, '')) for k in keys) + '\n')
    (args.output / 'provenance.json').write_text(
        json.dumps(driver.provenance(), indent=2) + '\n')
    print(f'wrote {len(penalties)} penalty rows to {args.output}')


if __name__ == '__main__':
    main()
