"""Measured Fresnel cylinder: the 1 GHz warm-up schedule with frontier-capped shape bands.

Reference: ``csi_measured_schedule.py warmup`` (band-1 warm-up at 1 GHz, then every original stage).
One change: before each later stage the observable frontier is measured at the current outline, at
that stage's highest frequency, and the stage's update band is capped at it
(``experiments/comparison/frontier_capped.py``). Same input, start, limits and checks as the reference.

  frontier_capped     bands capped
  frontier_measured   the same measurements, no band changed (control)
"""
from dataclasses import dataclass, field
from functools import partial
import argparse

import csi_fit as csi
import csi_measured_schedule as matched
from experiments.comparison.frontier_capped import FrontierCapped

VARIANTS = dict(frontier_capped=True, frontier_measured=False)


@dataclass(frozen=True)
class CappedMeasuredPolicy(FrontierCapped, matched.MeasuredPolicy):
    variant: str = 'warmup'
    cap: bool = True
    state: dict = field(default_factory=dict, compare=False, repr=False)


def configure(real, device, cap):
    original = matched.configure(real, device, 'warmup')      # input-hash check, saved limits
    return CappedMeasuredPolicy(prefix_frequencies_hz=original.prefix_frequencies_hz,
                                prefix_quotas=original.prefix_quotas, fit_seconds=original.fit_seconds,
                                fit_units=original.fit_units, cap=cap)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('variant', choices=tuple(VARIANTS))
    args = parser.parse_args()
    result = csi.run(csi.MEASURED_CASE, 'cuda', matched.OUTPUT / args.variant,
                     policy_factory=partial(configure, cap=VARIANTS[args.variant]))
    if result.get('bookkeeping') != 'complete':
        raise SystemExit(result.get('detail', result.get('outcome', 'incomplete')))
