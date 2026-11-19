"""Proposed matched control: change only the real warm-up frequency to 0.5 GHz."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import traceback

from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.material import MaterialUnknown
from bem_inverse.problem import Problem
from bem_inverse.runner import fit
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region, revision
from experiments.comparison.compare_clean_schedules import OUT, Schedule, area_score, stage_row, stage_settings


@dataclass(frozen=True)
class HalfGHzWarmup(Schedule):
    arm: str = 'reference'

    def operations(self, problem, physics):
        ladder = super().operations(problem, physics)
        obs = next(o for o in problem.real if o.frequency_hz == .5e9)
        warm = self._fit(problem, physics, 'warmup_050_real', (obs,), 1, 4, 600, 44,
                         purpose='Warm up the prescribed circle on real data')
        return [warm, *ladder]


def run(case, reference):
    row = campaign.row(case)
    real, damped = bem.observations(BASE, row, OUT)
    initial = curve_from(read(campaign.ROOT/row['initial']))
    solver = bem.solver(BASE)
    contrast, _ = bem.weak_start(initial, real[0], solver, bem.EXECUTION)
    assert contrast == reference['start_contrast']
    assert digest(campaign.ROOT/row['initial']) == reference['initial_sha256']
    assert digest(campaign.ROOT/row['data']) == reference['real_data_sha256']
    physics, forward = campaign._physics(solver, bem.EXECUTION)
    result = fit(Problem(initial, real, damped, contrast), solver=solver, execution=bem.EXECUTION,
                 physics=physics, forward_solve=forward, geometry_update=bem.GEOMETRY_UPDATE,
                 policy=HalfGHzWarmup(fit_seconds=bem.FIT_SECONDS), material=MaterialUnknown())
    truth = curve_region(curve_from(read(campaign.ROOT/row['truth'])))
    settings = stage_settings(result['decisions'])
    stages = [dict(**stage_row(s, truth), curve=s['curve'], settings=settings[s['stage']])
              for s in result['stages']]
    # The warm-up label, frequency and derived wavenumber are the only intended differences.
    allowed = {'label', 'frequencies_hz', 'wavenumbers'}
    for a, b in zip(stages, reference['stages']):
        permitted = allowed if a['stage'] == 'warmup_050_real' else set()
        assert all(a['settings'].get(k) == b['settings'].get(k)
                   for k in a['settings'].keys() | b['settings'].keys() if k not in permitted)
    return dict(outcome=result['outcome'], detail=result['detail'], stages=stages,
                start_contrast=contrast, contrast=result['final_contrast'],
                area_error=area_score(result['final_curve'], truth), seconds=result['fit_and_localization_seconds'],
                work_units=result['fit_and_localization_units'], seconds_limit=bem.FIT_SECONDS,
                work_limit=reference['work_limit'], real_data_sha256=reference['real_data_sha256'],
                initial_sha256=reference['initial_sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=scenes.CASES)
    case = parser.parse_args().case
    source = OUT/'warmup'/(case+'.json')
    path = OUT/'warmup_050'/(case+'.json')
    if path.exists():
        parser.error(f'Output already exists: {path}')
    header = dict(case=case, arm='warmup_050', commit=revision(), reference_sha256=digest(source),
                  driver_sha256=digest(Path(__file__)), started_utc=datetime.now(timezone.utc).isoformat())
    try:
        result = run(case, read(source))
    except Exception:
        write(path, dict(**header, outcome='WORKER_EXCEPTION', detail=traceback.format_exc()))
        raise
    write(path, {**header, **result})
    print(case, result['outcome'], f'{result["area_error"]:.3%}')


if __name__ == '__main__':
    main()
