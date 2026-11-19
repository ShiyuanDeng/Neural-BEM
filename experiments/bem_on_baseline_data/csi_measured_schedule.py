"""Run one matched schedule change on the original measured Fresnel cylinder."""
from dataclasses import dataclass, replace
import argparse
from functools import partial

import csi_fit as csi
from bem_inverse.io import digest, portable, read


CONTROL = (csi.ROOT / 'results/bem/baseline_data/csi_adapter/2026-11-18/first_fit'
           / csi.MEASURED_CASE / 'cuda/attempt_01/manifest.json')
OUTPUT = csi.ROOT / 'results/bem/baseline_data/measured_schedule/2026-11-19'


@dataclass(frozen=True)
class MeasuredPolicy(csi.CsiPolicy):
    variant: str = 'warmup'

    def operations(self, problem, physics):
        original = super().operations(problem, physics)
        if self.variant == 'first_cap':
            first = original[0]
            return (replace(first, stage=replace(first.stage, iterations=220)), *original[1:])
        if self.variant == 'warmup':
            warmup = self._fit(problem, physics, 'warmup_1GHz_real', (problem.real[0],),
                               1, 4, 600, 44, purpose='Narrow-band warm-up on the lowest measured frequency')
            return (warmup, *original)
        raise ValueError(self.variant)

    def plan(self, problem, physics):
        record = super().plan(problem, physics)
        saved = read(CONTROL)['settings']['policy']
        original = [op.record() for op in super().operations(problem, physics)]
        if (portable(original) != saved['operations'] or self.fit_seconds != saved['fit_seconds']
                or self.fit_units != saved['fit_units']):
            raise ValueError('The base schedule differs from the saved original GPU schedule.')
        if self.variant == 'warmup':
            record['changes_from_DF'][1] = 'no localization; warm-up at the lowest measured frequency'
        record['matched_comparison'] = dict(variant=self.variant, original=str(CONTROL.relative_to(csi.ROOT)))
        return record


def configure(real, device, variant):
    original = csi.policy_for(real, device)
    saved = read(CONTROL)
    if digest(csi.case_input(csi.MEASURED_CASE)) != saved['input']['sha256']:
        raise ValueError('The original measured input hash changed.')
    return MeasuredPolicy(prefix_frequencies_hz=original.prefix_frequencies_hz,
                          prefix_quotas=original.prefix_quotas,
                          fit_seconds=saved['settings']['policy']['fit_seconds'], variant=variant)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=('warmup', 'first_cap'))
    args = parser.parse_args()
    result = csi.run(csi.MEASURED_CASE, 'cuda', OUTPUT / args.variant,
                     policy_factory=partial(configure, variant=args.variant))
    if result.get('bookkeeping') != 'complete':
        raise SystemExit(result.get('detail', result.get('outcome', 'incomplete')))
