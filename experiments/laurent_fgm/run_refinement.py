"""The regime the compression papers actually claim: fixed kernel, refined N.

Fang-Jiang-Su 2024 and Jiang-Wang-Yu 2021 hold the integral operator fixed and
send the discretisation N to infinity.  Their claim is that truncating to
``|m-n| <= q ln N`` keeps the convergence order while the nonzero count falls to
O(N ln^2 N), i.e. the retained *fraction* tends to zero.

Inverse scattering does not refine at fixed kernel -- N is set by kD.  So before
scoring those rules against an electrical-size sweep it is only fair to check
that they behave as advertised in their own regime.  This driver does that: one
curve, one kD, N pushed well past the converged cutoff.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.run_refinement --output DIR
"""
import argparse
import json
from pathlib import Path

import numpy as np

from . import curves as curvelib
from . import decay as decaylib
from .run_decay import (CONTRAST, acquisition, forward, grid_for, provenance)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--curves', nargs='+', default=['ellipse', 'kite', 'crescent'])
    parser.add_argument('--kd', type=float, nargs='+', default=[2., 10.])
    parser.add_argument('--cutoffs', type=int, nargs='+',
                        default=[16, 24, 32, 48, 64, 96, 128, 160])
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f'{args.output} already exists; use a fresh directory.')
    args.output.mkdir(parents=True)

    sources, receivers = acquisition()
    library = curvelib.library()
    rows = []
    for name in args.curves:
        coefficients = library[name]
        halfwidth = curvelib.analyticity_halfwidth(coefficients)
        for kd in args.kd:
            ko = float(kd) / curvelib.diameter(coefficients)
            ki = ko * CONTRAST
            reference = None
            for cutoff in sorted(args.cutoffs, reverse=True):
                matrix, rhs, obs = forward(coefficients, ko, ki, cutoff,
                                           grid_for(cutoff), sources, receivers)
                _, y = decaylib.pipeline(matrix, rhs, obs)
                if reference is None:
                    reference = y
                    continue
                order = 2 * cutoff + 1
                for rule, mask in (
                        [(f'fjs_q{q:g}', decaylib.fjs_band(cutoff, q * np.log(order)))
                         for q in (1., 2., 4.)]
                        + [('jwy_mu1.2', decaylib.jwy_mask(cutoff, 1.2))]):
                    kept, stats = decaylib.truncate(matrix, mask)
                    try:
                        _, y_t = decaylib.pipeline(kept, rhs, obs)
                        against_full = decaylib.relative(y_t, y)
                        against_exact = decaylib.relative(y_t, reference)
                    except np.linalg.LinAlgError:
                        against_full = against_exact = float('inf')
                    rows.append(dict(
                        curve=name, kd=float(kd), halfwidth=halfwidth, cutoff=cutoff,
                        order=order, rule=rule, halfband=int(
                            np.abs(np.arange(-cutoff, cutoff + 1)[:, None]
                                   - np.arange(-cutoff, cutoff + 1)[None, :])[
                                mask[:order, :order]].max()),
                        **stats, untruncated_error=decaylib.relative(y, reference),
                        truncated_vs_full=against_full,
                        truncated_vs_reference=against_exact))
                print(f'  {name:10s} kD={kd:5.1f} K={cutoff:4d} done', flush=True)

    (args.output / 'refinement.json').write_text(json.dumps(rows, indent=2) + '\n')
    keys = sorted({k for row in rows for k in row})
    with (args.output / 'refinement.csv').open('w') as stream:
        stream.write(','.join(keys) + '\n')
        for row in rows:
            stream.write(','.join(str(row.get(k, '')) for k in keys) + '\n')
    (args.output / 'provenance.json').write_text(
        json.dumps(provenance(), indent=2) + '\n')
    print(f'wrote {len(rows)} refinement rows to {args.output}')


if __name__ == '__main__':
    main()
