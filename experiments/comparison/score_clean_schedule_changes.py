"""Compare saved schedule interventions with the original clean TG-002 endpoints."""
import csv

import numpy as np

from bem_inverse.io import curve_from, digest, read
from experiments.benchmark import campaign
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.compare_clean_schedules import OUT, area_score, stage_settings, write_rows


def compare(saved, baseline, info, truth):
    arm = saved['arm']
    case = saved['case']
    row = campaign.row(case)
    assert saved['baseline_sha256'] == digest(BASE.folder()/case/'fit.json')
    assert saved['real_data_sha256'] == digest(campaign.ROOT/row['data'])
    assert saved['initial_sha256'] == digest(campaign.ROOT/row['initial'])
    assert saved['start_contrast'] == baseline['contrast_start']['start_contrast']
    assert saved['frequencies_hz'] == baseline['frequencies_hz']
    assert (saved['solver'], saved['geometry_update'], saved['localization'], saved['damping']) == (
        'modal_muller', 'slider', 'none', 'real only')
    assert saved['work_limit'] == 13412 and saved['seconds_limit'] == (240 if arm == 'longer_wall' else 120)
    before = {s['stage']: s for s in baseline['stages']}
    settings = stage_settings(baseline['decisions'])
    prefix = []
    for stage in saved['stages']:
        name = stage['stage']
        if name not in settings:
            continue
        settings_old, settings_new = settings[name], stage['settings']
        changes = {k for k in settings_old.keys() | settings_new.keys() if settings_old.get(k) != settings_new.get(k)}
        changed_cap = arm == 'longer_stage' and name == 'ladder_2_real'
        assert changes == ({'iterations'} if changed_cap else set()), (case, name, changes)
        if changed_cap:
            assert settings_old['iterations'] == 22 and settings_new['iterations'] == 220
        if arm == 'warmup':
            continue
        if arm == 'longer_stage' and name not in ('ladder_1_real', 'ladder_2_real'):
            continue
        old = before[name]
        matched = stage.get('at_saved_step_count')
        prefix.append(dict(arm=arm, case=case, stage=name, baseline_steps=old['accepted_steps'],
                           new_steps=stage['accepted_steps'], baseline_contrast=old['contrast'],
                           baseline_loss=old['final_loss'], new_stage_loss=stage['final_loss'],
                           new_stage_contrast=stage['contrast'], new_stage_area_error=stage['area_error'],
                           common_steps=None if matched is None else matched['steps'],
                           common_step_curve_difference=None if matched is None else matched['relative_curve_difference'],
                           common_step_loss=None if matched is None else matched['loss'],
                           common_step_contrast=None if matched is None else matched['contrast'],
                           common_step_area_error=None if matched is None else matched['area_error']))
    if arm == 'warmup':
        warm = saved['stages'][0]['settings']
        assert warm['frequencies_hz'] == [.25e9] and warm['M'] == 1 and warm['K_geometry'] == 4
        assert warm['iterations'] == 44 and warm['quota'] == 600
    end = saved['stages'][-1]
    err = saved['area_error']
    assert np.isclose(area_score(end['curve'], truth), err, rtol=0, atol=1e-11)
    return dict(arm=arm, case=case, old_error=float(info['area_error']), new_error=err,
                old_pass=info['passed'], new_pass=err <= .05, old_contrast=float(info['final_contrast']),
                new_contrast=saved['contrast'], old_work=info['work_units'], new_work=saved['work_units'],
                old_seconds=info['seconds'], new_seconds=saved['seconds'], old_stage=info['last_stage'],
                new_stage=end['stage'], old_outcome=info['outcome'], new_outcome=saved['outcome'],
                new_stop=end['stop'], detail=saved['detail']), prefix


def main():
    with (OUT/'original_cases.csv').open() as stream:
        cases = {r['case']: r for r in csv.DictReader(stream)}
    outcomes, prefixes = [], []
    for arm in ('warmup', 'longer_stage', 'longer_wall'):
        for path in sorted((OUT/arm).glob('*.json')):
            case = path.stem
            baseline = read(BASE.folder()/case/'fit.json')
            row = campaign.row(case)
            truth = curve_region(curve_from(read(campaign.ROOT/row['truth'])))
            outcome, prefix = compare(read(path), baseline, cases[case], truth)
            outcomes.append(outcome)
            prefixes.extend(prefix)
    write_rows(OUT/'matched_endpoints.csv', outcomes)
    if prefixes:
        write_rows(OUT/'matched_prefixes.csv', prefixes)


if __name__ == '__main__':
    main()
