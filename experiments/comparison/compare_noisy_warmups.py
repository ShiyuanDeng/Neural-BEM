"""The real 0.25 GHz warm-up on a frozen 1% noise draw of TG-002.

Reference: the saved default fits of ``bem/default_n1dD_uc_fc`` (no warm-up). One change: the
band-1 stage at 0.25 GHz before the unchanged default schedule, exactly as in
``compare_clean_schedules warmup``. The noisy observations, the declared noise level (loss
weights and discrepancy stop, as in the saved fits), the centred start, the weak contrast
estimate, the slider and the limits are those of the saved run.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import traceback

from bem_inverse.io import curve_from, digest, read, write
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import curve_region
from experiments.comparison.compare_clean_schedules import area_score, stage_row, stage_settings
from experiments.comparison.compare_clean_warmups import Schedule, one_fit
from experiments.comparison.runs import RESULTS, parse

OUT = RESULTS / 'bem/stage_scheduling/2026-11-19/noisy_tg002'


def run(draw, case):
    base = parse(f'bem/default_n1d{draw}_uc_fc')
    row = campaign.row(case)
    reference = base.folder() / case / 'fit.json'
    saved, saved_score = read(reference), read(base.folder() / case / 'score.json')
    real, damped = bem.observations(base, row, RESULTS)
    initial = curve_from(read(campaign.ROOT / row['initial']))
    solver = bem.solver(base)
    truth = curve_region(curve_from(read(campaign.ROOT / row['truth'])))
    contrast, _ = bem.weak_start(initial, real[0], solver, bem.EXECUTION)
    policy = Schedule(fit_seconds=bem.FIT_SECONDS)
    result = one_fit(policy, initial, real, damped, contrast, solver)
    current = stage_settings(result['decisions'])
    stages = [dict(**stage_row(stage, truth), curve=stage['curve'], settings=current[stage['stage']])
              for stage in result['stages']]
    return dict(baseline=str(reference.relative_to(campaign.ROOT)), baseline_sha256=digest(reference),
                baseline_area_error=saved_score['area_error'], baseline_outcome=saved['outcome'],
                noise_draw=draw, noise_sigma_declared=[o.sigma_real_imag for o in real],
                initial_sha256=digest(campaign.ROOT / row['initial']),
                start_contrast=contrast, saved_start_contrast=saved['contrast_start']['start_contrast'],
                frequencies_hz=[o.frequency_hz for o in real], damping='real only', geometry_update=bem.GEOMETRY_UPDATE,
                solver=solver, localization='none', execution=result['physics']['execution'],
                devices=result['physics']['devices'], material=result['material'], work_limit=policy.fit_units,
                seconds_limit=policy.fit_seconds, work_units=result['fit_and_localization_units'],
                seconds=result['fit_and_localization_seconds'], outcome=result['outcome'], detail=result['detail'],
                area_error=area_score(result['final_curve'], truth), contrast=result['final_contrast'], stages=stages)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('case', choices=scenes.CASES)
    parser.add_argument('--draw', type=int, default=0, choices=(0, 1, 2))
    args = parser.parse_args()
    path = OUT / f'warmup_n1d{args.draw}' / f'{args.case}.json'
    if path.exists():
        parser.error(f'Output already exists: {path}')
    header = dict(arm=f'warmup_n1d{args.draw}', case=args.case, started_utc=datetime.now(timezone.utc).isoformat(),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  driver_sha256=digest(Path(__file__)))
    try:
        result = run(args.draw, args.case)
    except Exception:
        write(path, {**header, 'outcome': 'WORKER_EXCEPTION', 'detail': traceback.format_exc()})
        raise
    write(path, {**header, **result})
    print(args.case, f'warmup_n1d{args.draw}', result['outcome'], f'{result["area_error"]:.3%}',
          f'(saved {result["baseline_area_error"]:.3%})', f'contrast {result["contrast"]:.4g}', flush=True)


if __name__ == '__main__':
    main()
