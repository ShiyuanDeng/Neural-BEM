"""Second-round matched tests on clean TG-002: variants of the real 0.25 GHz warm-up.

Every arm keeps the default real-only ladder, data, centred start, slider and limits of
``compare_clean_schedules warmup``. One arm changes only what its options name:

  --warmup-iterations / --warmup-quota   a longer warm-up stage (default 44 steps, 600 units)
  --start two_sided                      warm up from the weak contrast estimate s and from its mirror
                                         image 2 - s (same strength, other side of the background),
                                         keep the side whose warm-up ends at the lower 0.25 GHz loss
  --seconds                              the nominal whole-fit wall limit (default 120 s)

The two-sided choice uses the fit's own loss only; truth enters after the fit, for scoring.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import traceback

from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.material import MaterialUnknown
from bem_inverse.problem import Problem
from bem_inverse.real_only_policy import RealOnlyPolicy
from bem_inverse.runner import fit
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.compare_clean_schedules import OUT, area_score, stage_row, stage_settings
from experiments.comparison.runs import RESULTS


@dataclass(frozen=True)
class Schedule(RealOnlyPolicy):
    warmup_iterations: int = 44
    warmup_quota: int = 600
    warmup_only: bool = False

    def operations(self, problem, physics):
        low = next(o for o in problem.real if o.frequency_hz == .25e9)
        warmup = self._fit(problem, physics, 'warmup_025_real', (low,), 1, 4, self.warmup_quota,
                           self.warmup_iterations, purpose='Warm up the prescribed circle on real data')
        if self.warmup_only:
            return [warmup]
        return [warmup, *super().operations(problem, physics)]


def one_fit(policy, initial, real, damped, contrast, solver):
    physics, forward = campaign._physics(solver, bem.EXECUTION)
    try:
        return fit(Problem(initial, real, damped, contrast), solver=solver, execution=bem.EXECUTION,
                   physics=physics, forward_solve=forward, geometry_update=bem.GEOMETRY_UPDATE,
                   policy=policy, material=MaterialUnknown())
    finally:
        if hasattr(physics, 'close'):
            physics.close()


def run(case, start, warmup_iterations, warmup_quota, seconds):
    row = campaign.row(case)
    reference = BASE.folder() / case / 'fit.json'
    saved = read(reference)
    real, damped = bem.observations(BASE, row, RESULTS)
    initial = curve_from(read(campaign.ROOT / row['initial']))
    solver = bem.solver(BASE)
    truth = curve_region(curve_from(read(campaign.ROOT / row['truth'])))
    weak, _ = bem.weak_start(initial, real[0], solver, bem.EXECUTION)
    settings = dict(warmup_iterations=warmup_iterations, warmup_quota=warmup_quota)
    contrast, selection = weak, None
    if start == 'two_sided':
        sides = []
        for candidate in (weak, 2.-weak):
            result = one_fit(Schedule(warmup_only=True, fit_seconds=seconds, **settings),
                             initial, real, damped, candidate, solver)
            stage = result['stages'][0]
            sides.append(dict(start_contrast=candidate, final_loss=stage['final_loss'],
                              initial_loss=stage['initial_loss'], contrast=stage['contrast'],
                              accepted_steps=stage['accepted_steps'], stop=stage['stop'],
                              area_error=area_score(stage['curve'], truth),
                              work_units=result['fit_and_localization_units'],
                              seconds=result['fit_and_localization_seconds']))
        chosen = min(sides, key=lambda side: side['final_loss'])
        contrast = chosen['start_contrast']
        selection = dict(rule='lower 0.25 GHz loss at the end of a warm-up from s and from 2 - s',
                         sides=sides, chosen_start_contrast=contrast,
                         extra_work_units=sum(side['work_units'] for side in sides),
                         extra_seconds=sum(side['seconds'] for side in sides))
    policy = Schedule(fit_seconds=seconds, **settings)
    result = one_fit(policy, initial, real, damped, contrast, solver)
    current = stage_settings(result['decisions'])
    stages = [dict(**stage_row(stage, truth), curve=stage['curve'], settings=current[stage['stage']])
              for stage in result['stages']]
    return dict(baseline=str(reference.relative_to(campaign.ROOT)), baseline_sha256=digest(reference),
                real_data_sha256=digest(campaign.ROOT / row['data']), initial_sha256=digest(campaign.ROOT / row['initial']),
                weak_start_contrast=weak, saved_start_contrast=saved['contrast_start']['start_contrast'],
                start_rule=start, start_contrast=contrast, side_selection=selection, **settings,
                frequencies_hz=[o.frequency_hz for o in real], damping='real only', geometry_update=bem.GEOMETRY_UPDATE,
                solver=solver, localization='none', execution=result['physics']['execution'],
                devices=result['physics']['devices'], material=result['material'], work_limit=policy.fit_units,
                seconds_limit=policy.fit_seconds, work_units=result['fit_and_localization_units'],
                seconds=result['fit_and_localization_seconds'], outcome=result['outcome'], detail=result['detail'],
                area_error=area_score(result['final_curve'], truth), contrast=result['final_contrast'], stages=stages)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('tag', help='output folder name under the 2026-11-19 clean_tg002 results')
    parser.add_argument('case', choices=scenes.CASES)
    parser.add_argument('--start', choices=('weak', 'two_sided'), default='weak')
    parser.add_argument('--warmup-iterations', type=int, default=44)
    parser.add_argument('--warmup-quota', type=int, default=600)
    parser.add_argument('--seconds', type=float, default=bem.FIT_SECONDS)
    args = parser.parse_args()
    path = OUT / args.tag / f'{args.case}.json'
    if path.exists():
        parser.error(f'Output already exists: {path}')
    header = dict(arm=args.tag, case=args.case, started_utc=datetime.now(timezone.utc).isoformat(),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  driver_sha256=digest(Path(__file__)))
    try:
        result = run(args.case, args.start, args.warmup_iterations, args.warmup_quota, args.seconds)
    except Exception:
        write(path, {**header, 'outcome': 'WORKER_EXCEPTION', 'detail': traceback.format_exc()})
        raise
    write(path, {**header, **result})
    print(args.case, args.tag, result['outcome'], f'{result["area_error"]:.3%}',
          f'contrast {result["contrast"]:.4g}', flush=True)


if __name__ == '__main__':
    main()
