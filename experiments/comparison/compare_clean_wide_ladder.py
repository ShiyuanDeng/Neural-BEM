"""Fifth-round matched test on clean TG-002: the 0.25 GHz warm-up with wider early shape bands.

Reference: ``compare_clean_schedules warmup``. One change: each ladder stage's update band is two
higher (5, 7, 9, 11 instead of 3, 5, 7, 9), built exactly as the ``wider`` arm of
``check_stage_stops`` on 18 November (stage band replaced; storage, quota, cap and optimizer unchanged).
"""
import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import traceback

from bem_inverse.io import curve_from, digest, read, write
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.compare_clean_schedules import OUT, area_score, stage_row, stage_settings
from experiments.comparison.compare_clean_warmups import Schedule, one_fit
from experiments.comparison.runs import RESULTS

ARM = 'warmup_wide'


@dataclass(frozen=True)
class WideLadder(Schedule):
    def operations(self, problem, physics):
        return [replace(op, stage=replace(op.stage, update_modes=op.stage.update_modes+2))
                if op.kind == 'fit' and op.label.startswith('ladder_') else op
                for op in super().operations(problem, physics)]


def run(case):
    row = campaign.row(case)
    reference = OUT / 'warmup' / f'{case}.json'
    real, damped = bem.observations(BASE, row, RESULTS)
    initial = curve_from(read(campaign.ROOT / row['initial']))
    solver = bem.solver(BASE)
    truth = curve_region(curve_from(read(campaign.ROOT / row['truth'])))
    contrast, _ = bem.weak_start(initial, real[0], solver, bem.EXECUTION)
    policy = WideLadder(fit_seconds=bem.FIT_SECONDS)
    result = one_fit(policy, initial, real, damped, contrast, solver)
    current = stage_settings(result['decisions'])
    stages = [dict(**stage_row(stage, truth), curve=stage['curve'], settings=current[stage['stage']])
              for stage in result['stages']]
    return dict(reference=str(reference.relative_to(campaign.ROOT)), reference_sha256=digest(reference),
                reference_area_error=read(reference)['area_error'],
                real_data_sha256=digest(campaign.ROOT / row['data']), initial_sha256=digest(campaign.ROOT / row['initial']),
                start_contrast=contrast, frequencies_hz=[o.frequency_hz for o in real], damping='real only',
                geometry_update=bem.GEOMETRY_UPDATE, solver=solver, localization='none',
                execution=result['physics']['execution'], devices=result['physics']['devices'],
                material=result['material'], work_limit=policy.fit_units, seconds_limit=policy.fit_seconds,
                work_units=result['fit_and_localization_units'], seconds=result['fit_and_localization_seconds'],
                outcome=result['outcome'], detail=result['detail'],
                area_error=area_score(result['final_curve'], truth), contrast=result['final_contrast'], stages=stages)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('case', choices=scenes.CASES)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    path = args.out / ARM / f'{args.case}.json'
    if path.exists():
        parser.error(f'Output already exists: {path}')
    header = dict(arm=ARM, case=args.case, started_utc=datetime.now(timezone.utc).isoformat(),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  driver_sha256=digest(Path(__file__)))
    try:
        result = run(args.case)
    except Exception:
        write(path, {**header, 'outcome': 'WORKER_EXCEPTION', 'detail': traceback.format_exc()})
        raise
    write(path, {**header, **result})
    print(args.case, ARM, result['outcome'], f'{result["area_error"]:.3%}',
          f'(warm-up arm {result["reference_area_error"]:.3%})', f'contrast {result["contrast"]:.4g}', flush=True)


if __name__ == '__main__':
    main()
