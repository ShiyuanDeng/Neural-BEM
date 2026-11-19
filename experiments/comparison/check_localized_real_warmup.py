"""Run the disk-start comparison only when called by the coordinator on the GPU host."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import traceback

from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.io import curve_from, digest, read, write
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region, revision
from experiments.comparison.compare_clean_schedules import OUT, area_score, stage_row, stage_settings
from experiments.comparison.compare_clean_warmups import Schedule, one_fit
from experiments.comparison.localize_clean_real_disks import DIR, MM


def run(case, starts):
    row = campaign.row(case)
    start = next(s for s in starts['starts'] if s['case'] == case)
    control = read(OUT/'warmup'/(case+'.json'))
    data_hash = digest(campaign.ROOT/row['data'])
    assert data_hash == start['data_sha256'] == control['real_data_sha256']
    real, damped = bem.observations(BASE, row, OUT)
    initial = FourierCurve.circle(start['radius_mm']/MM, complex(start['x_mm'],start['y_mm'])/MM)
    policy = Schedule(fit_seconds=bem.FIT_SECONDS)
    assert policy.fit_units == control['work_limit'] and policy.fit_seconds == control['seconds_limit']
    result = one_fit(policy, initial, real, damped, start['contrast'], bem.solver(BASE))
    truth = curve_region(curve_from(read(campaign.ROOT/row['truth'])))
    settings = stage_settings(result['decisions'])
    for stage in control['stages']:
        if stage['stage'] in settings:
            assert settings[stage['stage']] == stage['settings']
    stages = [dict(**stage_row(s, truth), curve=s['curve'], settings=settings[s['stage']]) for s in result['stages']]
    return dict(start=start, control_sha256=digest(OUT/'warmup'/(case+'.json')), data_sha256=data_hash,
                warmup_reference_area_error=control['area_error'], area_error=area_score(result['final_curve'],truth),
                contrast=result['final_contrast'], seconds=result['fit_and_localization_seconds'],
                work_units=result['fit_and_localization_units'], seconds_limit=policy.fit_seconds,
                work_limit=policy.fit_units, outcome=result['outcome'], detail=result['detail'], stages=stages,
                preprocessing='shared CPU real-disk localization, outside fit work and wall limits',
                preprocessing_batch_seconds=starts['seconds'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=scenes.CASES)
    case = parser.parse_args().case
    path = OUT/'localized_real_warmup'/(case+'.json')
    if path.exists():
        parser.error(f'Output already exists: {path}')
    source = DIR/'joint_starts.json'
    header = dict(case=case, arm='localized_real_warmup', commit=revision(), driver_sha256=digest(Path(__file__)),
                  start_file_sha256=digest(source), started_utc=datetime.now(timezone.utc).isoformat())
    try:
        result = run(case, read(source))
    except Exception:
        write(path, dict(**header, outcome='WORKER_EXCEPTION', detail=traceback.format_exc()))
        raise
    write(path, {**header, **result})
    print(case, result['outcome'], f'{result["area_error"]:.3%}')


if __name__ == '__main__':
    main()
