"""Fourth-round matched test on clean TG-002: warm-up schedule with frontier-capped shape bands.

Reference: ``compare_clean_schedules warmup`` (the real 0.25 GHz warm-up, then the default ladder).
One change: before each later stage the observable frontier is measured at the current outline, at
that stage's highest frequency, and the stage's update band is capped at it
(``experiments/comparison/frontier_capped.py``).

  frontier_capped     bands capped
  frontier_measured   the same measurements, no band changed (control: must reproduce the warm-up arm)
"""
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import traceback

from bem_inverse.io import curve_from, digest, read, write
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.compare_clean_schedules import OUT, Schedule, area_score, stage_row, stage_settings
from experiments.comparison.compare_clean_warmups import one_fit
from experiments.comparison.frontier_capped import FrontierCapped
from experiments.comparison.runs import RESULTS

ARMS = dict(frontier_capped=True, frontier_measured=False)


@dataclass(frozen=True)
class CappedSchedule(FrontierCapped, Schedule):
    arm: str = 'warmup'
    cap: bool = True
    state: dict = field(default_factory=dict, compare=False, repr=False)


def frontier_events(decisions):
    rows = []
    for event in decisions:
        operation = event['operation']
        if operation['operation'] == 'frontier' and 'measured' in event:
            rows.append(dict(label=operation['label'], frequency_hz=(operation['details'] or {}).get('frequency_hz'),
                             default_band=(operation['details'] or {}).get('default_band'),
                             frontier=event['measured']['frontier']))
    return rows


def run(arm, case, seconds):
    row = campaign.row(case)
    reference = OUT / 'warmup' / f'{case}.json'
    real, damped = bem.observations(BASE, row, RESULTS)
    initial = curve_from(read(campaign.ROOT / row['initial']))
    solver = bem.solver(BASE)
    truth = curve_region(curve_from(read(campaign.ROOT / row['truth'])))
    contrast, _ = bem.weak_start(initial, real[0], solver, bem.EXECUTION)
    policy = CappedSchedule(cap=ARMS[arm], fit_seconds=seconds)
    result = one_fit(policy, initial, real, damped, contrast, solver)
    current = stage_settings(result['decisions'])
    stages = [dict(**stage_row(stage, truth), curve=stage['curve'], settings=current[stage['stage']])
              for stage in result['stages']]
    return dict(reference=str(reference.relative_to(campaign.ROOT)), reference_sha256=digest(reference),
                real_data_sha256=digest(campaign.ROOT / row['data']), initial_sha256=digest(campaign.ROOT / row['initial']),
                start_contrast=contrast, frequencies_hz=[o.frequency_hz for o in real], damping='real only',
                geometry_update=bem.GEOMETRY_UPDATE, solver=solver, localization='none',
                execution=result['physics']['execution'], devices=result['physics']['devices'],
                material=result['material'], work_limit=policy.fit_units, seconds_limit=policy.fit_seconds,
                work_units=result['fit_and_localization_units'], seconds=result['fit_and_localization_seconds'],
                outcome=result['outcome'], detail=result['detail'],
                area_error=area_score(result['final_curve'], truth), contrast=result['final_contrast'],
                frontiers=frontier_events(result['decisions']), stages=stages)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('arm', choices=tuple(ARMS))
    parser.add_argument('case', choices=scenes.CASES)
    parser.add_argument('--seconds', type=float, default=bem.FIT_SECONDS)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    path = args.out / args.arm / f'{args.case}.json'
    if path.exists():
        parser.error(f'Output already exists: {path}')
    header = dict(arm=args.arm, case=args.case, started_utc=datetime.now(timezone.utc).isoformat(),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  driver_sha256=digest(Path(__file__)),
                  mixin_sha256=digest(Path(__file__).with_name('frontier_capped.py')))
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
