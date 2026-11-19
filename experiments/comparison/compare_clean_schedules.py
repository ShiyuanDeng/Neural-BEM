"""Inspect the original 30 clean TG-002 fits and run one matched schedule change."""
import argparse
import csv
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import traceback

import numpy as np

from bem_inverse.io import curve_from, digest, portable, read, write
from bem_inverse.material import MaterialUnknown
from bem_inverse.problem import Problem
from bem_inverse.real_only_policy import RealOnlyPolicy
from bem_inverse.runner import fit
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.runs import RESULTS
from experiments.comparison.scoring import region_scores

OUT = RESULTS / 'bem/stage_scheduling/2026-11-19/clean_tg002'
ARMS = ('reference', 'warmup', 'longer_stage', 'longer_wall')


@dataclass(frozen=True)
class Schedule(RealOnlyPolicy):
    arm: str = 'reference'

    def operations(self, problem, physics):
        operations = list(super().operations(problem, physics))
        if self.arm == 'warmup':
            low = next(o for o in problem.real if o.frequency_hz == .25e9)
            warmup = self._fit(problem, physics, 'warmup_025_real', (low,),
                               1, 4, 600, 44, purpose='Warm up the prescribed circle on real data')
            operations.insert(0, warmup)
        if self.arm == 'longer_stage':
            index = next(i for i, op in enumerate(operations) if op.label == 'ladder_2_real')
            op = operations[index]
            operations[index] = replace(op, stage=replace(op.stage, iterations=220))
        return operations


def area_score(curve_record, truth):
    return region_scores(curve_region(curve_from(curve_record)), truth)['area_error']


def stage_row(stage, truth):
    keys = ('stage', 'M', 'K_geometry', 'nodes', 'accepted_steps', 'initial_loss', 'final_loss',
            'entry_contrast', 'contrast', 'seconds', 'outcome', 'stop', 'detail')
    return {**{k: stage[k] for k in keys}, 'work_units': stage['work']['stage_units'],
            'stage_quota': stage['work']['stage_quota'], 'area_error': area_score(stage['curve'], truth),
            'physics_refusal': '|'.join(sorted({f['message'] for f in stage['physics_failures']}))}


def write_rows(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def inventory():
    cases, stages = [], []
    for case in scenes.CASES:
        row = campaign.row(case)
        directory = BASE.folder() / case
        result, score = read(directory / 'fit.json'), read(directory / 'score.json')
        truth = curve_region(curve_from(read(campaign.ROOT / row['truth'])))
        passed = score['area_error'] <= .05
        cases.append(dict(case=case, passed=passed, area_error=score['area_error'],
                          initial_area_error=area_score(read(campaign.ROOT / row['initial']), truth),
                          true_contrast=score['contrast_true'], start_contrast=result['contrast_start']['start_contrast'],
                          clipped=result['contrast_start']['clipped'], final_contrast=result['contrast'],
                          outcome=result['outcome'], last_stage=result['final_stage']['label'],
                          work_units=result['work']['units'], seconds=result['fit_seconds']))
        for number, stage in enumerate(result['stages'], 1):
            stages.append(dict(case=case, passed=passed, number=number, **stage_row(stage, truth)))
        if not np.isclose(area_score(result['final_curve'], truth), score['area_error'], rtol=0, atol=1e-12):
            raise ValueError(f'Final area disagrees with saved score for {case}')
    OUT.mkdir(parents=True, exist_ok=True)
    write_rows(OUT / 'original_cases.csv', cases)
    write_rows(OUT / 'original_stages.csv', stages)
    print(f'{len(cases)} cases, {len(stages)} stages, {sum(row["passed"] for row in cases)} passed')


def stage_settings(decisions):
    return {event['operation']['label']: portable(event['operation']['stage']) for event in decisions
            if event['reason'] == 'resolved stage entered'}


def compare_curve(found, saved):
    a, b = curve_from(found).coefficients, curve_from(saved).coefficients
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def run(arm, case):
    row = campaign.row(case)
    reference = BASE.folder() / case / 'fit.json'
    saved = read(reference)
    baseline = {stage['stage']: stage for stage in saved['stages']}
    real, damped = bem.observations(BASE, row, RESULTS)
    initial = curve_from(read(campaign.ROOT / row['initial']))
    solver = bem.solver(BASE)
    contrast, _ = bem.weak_start(initial, real[0], solver, bem.EXECUTION)
    physics, forward = campaign._physics(solver, bem.EXECUTION)
    policy = Schedule(arm=arm, fit_seconds=240. if arm == 'longer_wall' else bem.FIT_SECONDS)
    checkpoints = {}

    def observe(kind, payload):
        if kind != 'accepted_history':
            return
        point = payload['row']
        label = point['work']['stage']
        if label in baseline and point['iteration'] == baseline[label]['accepted_steps']:
            checkpoints[label] = (point['coefficients'], point['contrast'], point['loss'])

    physics.observer = observe
    result = fit(Problem(initial, real, damped, contrast), solver=solver, execution=bem.EXECUTION,
                 physics=physics, forward_solve=forward, geometry_update=bem.GEOMETRY_UPDATE,
                 policy=policy, material=MaterialUnknown())
    truth = curve_region(curve_from(read(campaign.ROOT / row['truth'])))
    old_settings = stage_settings(saved['decisions'])
    current_settings = stage_settings(result['decisions'])
    stages = []
    for stage in result['stages']:
        label = stage['stage']
        entry = dict(**stage_row(stage, truth), curve=stage['curve'], settings=current_settings[label])
        if label in baseline:
            entry['settings_changes_from_saved'] = {
                k: dict(old=v, new=current_settings[label].get(k)) for k, v in old_settings[label].items()
                if current_settings[label].get(k) != v}
            if label in checkpoints:
                curve, q, loss = checkpoints[label]
                entry['at_saved_step_count'] = dict(steps=baseline[label]['accepted_steps'], contrast=q,
                    loss=loss, area_error=area_score(curve, truth),
                    relative_curve_difference=compare_curve(curve, baseline[label]['curve']))
        stages.append(entry)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arm', choices=('inventory', *ARMS))
    parser.add_argument('case', nargs='?', choices=scenes.CASES)
    args = parser.parse_args()
    if args.arm == 'inventory':
        return inventory()
    if not args.case:
        parser.error('A fit needs a case')
    path = OUT / args.arm / f'{args.case}.json'
    if path.exists():
        parser.error(f'Output already exists: {path}')
    header = dict(arm=args.arm, case=args.case, started_utc=datetime.now(timezone.utc).isoformat(),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  driver_sha256=digest(Path(__file__)))
    try:
        result = run(args.arm, args.case)
    except Exception:
        write(path, {**header, 'outcome': 'WORKER_EXCEPTION', 'detail': traceback.format_exc()})
        raise
    write(path, {**header, **result})
    print(args.case, args.arm, result['outcome'], f'{result["area_error"]:.3%}', flush=True)


if __name__ == '__main__':
    main()
