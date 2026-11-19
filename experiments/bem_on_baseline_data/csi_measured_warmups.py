"""Settle circle-scale geometry on measured frequency prefixes before shape release.

Use --dry-check to print and check both plans without any forward solve or fit.
"""
from dataclasses import dataclass
from functools import partial
import argparse
import json

import csi_fit as csi
import csi_measured_schedule as matched
from bem_inverse.io import portable, read

VARIANTS = ('circle_ladder', 'circle_then_ladder')


@dataclass(frozen=True)
class CircleWarmupPolicy(csi.CsiPolicy):
    variant: str = 'circle_ladder'

    def operations(self, problem, physics):
        original = tuple(super().operations(problem, physics))
        if self.variant not in VARIANTS:
            raise ValueError(self.variant)
        ladders = tuple(op for op in original if op.label.startswith('ladder_'))
        if tuple(op.label for op in ladders) != tuple(f'ladder_{i}_real' for i in range(1, 5)):
            raise ValueError('Expected the original four measured ladder stages.')
        warmups = tuple(self._fit(problem, physics, f'circle_{i}_real', op.stage.observations,
                                 1, 4, 600, 44, purpose='Settle circle-scale geometry on a real frequency prefix')
                        for i, op in enumerate(ladders, 1))
        full = self._fit(problem, physics, 'circle_full_real', problem.real, 1, 4, 600, 44,
                         purpose='Settle circle-scale geometry on the full real catalog before shape release')
        retained = original if self.variant == 'circle_then_ladder' else tuple(
            op for op in original if not op.label.startswith('ladder_'))
        return (*warmups, full, *retained)

    def plan(self, problem, physics):
        saved = read(matched.CONTROL)['settings']['policy']
        original = portable([op.record() for op in csi.CsiPolicy.operations(self, problem, physics)])
        if (original != saved['operations'] or self.fit_seconds != saved['fit_seconds']
                or self.fit_units != saved['fit_units']):
            raise ValueError('The base schedule or global limits differ from the saved original GPU schedule.')
        record = super().plan(problem, physics)
        retained = saved['operations'] if self.variant == 'circle_then_ladder' else [
            op for op in saved['operations'] if not op['label'].startswith('ladder_')]
        if portable(record['operations'][5:]) != retained:
            raise ValueError('A retained original operation changed.')
        record['changes_from_DF'][1] = 'no localization; five band-1 real-data stages before shape release'
        record['matched_comparison'] = dict(variant=self.variant,
            original=str(matched.CONTROL.relative_to(csi.ROOT)),
            original_ladder_retained=self.variant == 'circle_then_ladder')
        return record


def configure(real, device, variant):
    # Reuse the existing input-hash check and saved-wall-limit configuration.
    original = matched.configure(real, device, 'warmup')
    return CircleWarmupPolicy(prefix_frequencies_hz=original.prefix_frequencies_hz,
                              prefix_quotas=original.prefix_quotas,
                              fit_seconds=original.fit_seconds, fit_units=original.fit_units,
                              variant=variant)


def dry_check():
    from bem_inverse import Execution, FourierCurve, Problem
    from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings
    import csi_data as data

    saved = read(matched.CONTROL)
    real, _, _ = data.observations(data.MEASURED)
    problem = Problem(FourierCurve.circle(csi.START_RADIUS_M/data.LENGTH_M), real, None,
                      saved['settings']['start_contrast'], length_unit_m=data.LENGTH_M,
                      origin_m=0j, bounds_m=csi.BOUNDS_M)
    physics = ModalMuller(Execution(device='cpu', frequency_threads=1), ModalSettings(table_mode=True))
    try:
        for variant in VARIANTS:
            policy = configure(real, 'cuda', variant)
            plan = policy.plan(problem, physics)
            operations = policy.operations(problem, physics)
            expected = [(f'circle_{i}_real', list(range(1, i+1))) for i in range(1, 5)]
            expected.append(('circle_full_real', list(range(1, 9))))
            for op, (label, ghz) in zip(operations[:5], expected):
                stage = op.stage
                actual = [obs.frequency_hz/1e9 for obs in stage.observations]
                if (op.label != label or actual != ghz or stage.update_modes != 1
                        or stage.curve_modes != 4 or stage.quota != 600 or stage.iterations != 44):
                    raise ValueError(f'Incorrect circle stage: {op.label}')
            print(f'{variant}: fit_units={plan["fit_units"]}, fit_seconds={plan["fit_seconds"]}; '
                  'input hash, original schedule, retained operations and global limits checked')
            for op in operations:
                if getattr(op, 'stage', None) is None:
                    print(op.label, '(unchanged non-fit operation)')
                    continue
                stage = op.stage
                print(json.dumps(dict(label=op.label,
                    ghz=[obs.frequency_hz/1e9 for obs in stage.observations],
                    update_band=stage.update_modes, storage_band=stage.curve_modes,
                    quota=stage.quota, iterations=stage.iterations)))
    finally:
        if hasattr(physics, 'close'):
            physics.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=VARIANTS, nargs='?')
    parser.add_argument('--dry-check', action='store_true')
    args = parser.parse_args()
    if args.dry_check:
        return dry_check()
    if args.variant is None:
        parser.error('Supply a variant or --dry-check.')
    result = csi.run(csi.MEASURED_CASE, 'cuda', matched.OUTPUT/args.variant,
                     policy_factory=partial(configure, variant=args.variant))
    if result.get('bookkeeping') != 'complete':
        raise SystemExit(result.get('detail', result.get('outcome', 'incomplete')))


if __name__ == '__main__':
    main()
