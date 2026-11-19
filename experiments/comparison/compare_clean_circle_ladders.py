"""Third-round matched tests on clean TG-002: settle the circle on several frequency sets first.

The TG-002 counterpart of ``experiments/bem_on_baseline_data/csi_measured_warmups.py``. Band-1 stages
(update band 1, storage band 4, 600 units, 44 steps, as the 0.25 GHz warm-up) run on the lowest
frequency, then on each set of the default ladder, then on the whole catalog. After them:

  circle_then_default   every stage of the default real-only schedule, unchanged
  circle_then_full      the default full-catalog stages only; the default shape ladder is dropped

Data, centred start, weak contrast estimate, slider and global limits are those of the default fit.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import traceback

from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.real_only_policy import RealOnlyPolicy
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.compare_clean_schedules import OUT, area_score, stage_row, stage_settings
from experiments.comparison.compare_clean_warmups import one_fit
from experiments.comparison.runs import RESULTS

ARMS = ('circle_then_default', 'circle_then_full')


@dataclass(frozen=True)
class Schedule(RealOnlyPolicy):
    arm: str = 'circle_then_default'

    def operations(self, problem, physics):
        default = list(super().operations(problem, physics))
        real = {o.frequency_hz: o for o in problem.real}
        lowest = min(real)
        sets = [(real[lowest],)]
        sets += [tuple(real[f] for f in self.prefix_frequencies_hz[:n])
                 for n in range(1, len(self.prefix_frequencies_hz)+1)]
        circles = [self._fit(problem, physics, f'circle_{number}_real', observations, 1, 4, 600, 44,
                             purpose='Settle the circle on a real frequency set before shape release')
                   for number, observations in enumerate(sets)]
        circles.append(self._fit(problem, physics, 'circle_full_real', problem.real, 1, 4, 600, 44,
                                 purpose='Settle the circle on the whole real catalog before shape release'))
        if self.arm == 'circle_then_full':
            default = [op for op in default if not op.label.startswith('ladder_')]
        return [*circles, *default]


def run(arm, case, seconds):
    row = campaign.row(case)
    reference = BASE.folder() / case / 'fit.json'
    saved = read(reference)
    real, damped = bem.observations(BASE, row, RESULTS)
    initial = curve_from(read(campaign.ROOT / row['initial']))
    solver = bem.solver(BASE)
    truth = curve_region(curve_from(read(campaign.ROOT / row['truth'])))
    contrast, _ = bem.weak_start(initial, real[0], solver, bem.EXECUTION)
    policy = Schedule(arm=arm, fit_seconds=seconds)
    result = one_fit(policy, initial, real, damped, contrast, solver)
    current = stage_settings(result['decisions'])
    stages = [dict(**stage_row(stage, truth), curve=stage['curve'], settings=current[stage['stage']])
              for stage in result['stages']]
    return dict(baseline=str(reference.relative_to(campaign.ROOT)), baseline_sha256=digest(reference),
                real_data_sha256=digest(campaign.ROOT / row['data']), initial_sha256=digest(campaign.ROOT / row['initial']),
                start_contrast=contrast, saved_start_contrast=saved['contrast_start']['start_contrast'],
                frequencies_hz=[o.frequency_hz for o in real], damping='real only', geometry_update=bem.GEOMETRY_UPDATE,
                solver=solver, localization='none', execution=result['physics']['execution'],
                devices=result['physics']['devices'], material=result['material'], work_limit=policy.fit_units,
                seconds_limit=policy.fit_seconds, work_units=result['fit_and_localization_units'],
                seconds=result['fit_and_localization_seconds'], outcome=result['outcome'], detail=result['detail'],
                area_error=area_score(result['final_curve'], truth), contrast=result['final_contrast'], stages=stages)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('arm', choices=ARMS)
    parser.add_argument('case', choices=scenes.CASES)
    parser.add_argument('--seconds', type=float, default=bem.FIT_SECONDS)
    args = parser.parse_args()
    path = OUT / args.arm / f'{args.case}.json'
    if path.exists():
        parser.error(f'Output already exists: {path}')
    header = dict(arm=args.arm, case=args.case, started_utc=datetime.now(timezone.utc).isoformat(),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  driver_sha256=digest(Path(__file__)))
    try:
        result = run(args.arm, args.case, args.seconds)
    except Exception:
        write(path, {**header, 'outcome': 'WORKER_EXCEPTION', 'detail': traceback.format_exc()})
        raise
    write(path, {**header, **result})
    print(args.case, args.arm, result['outcome'], f'{result["area_error"]:.3%}',
          f'contrast {result["contrast"]:.4g}', flush=True)


if __name__ == '__main__':
    main()
