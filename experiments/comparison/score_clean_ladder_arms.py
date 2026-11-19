"""Compare the two round-three circle schedules and round-five wider ladder with warmup."""
from collections import Counter
from math import isclose

from bem_inverse.io import curve_from, digest, read
from experiments.benchmark import campaign, scenes
from experiments.comparison.check_stage_stops import curve_region
from experiments.comparison.compare_clean_schedules import OUT, area_score, write_rows

ARMS = ('circle_then_default', 'circle_then_full', 'warmup_wide')
CIRCLE_LABELS = [f'circle_{n}_real' for n in range(5)] + ['circle_full_real']
SHARED_FIELDS = ('case', 'real_data_sha256', 'initial_sha256', 'start_contrast', 'frequencies_hz',
                 'damping', 'geometry_update', 'solver', 'localization', 'execution', 'material',
                 'work_limit', 'seconds_limit')
STAGE_STATE = ('accepted_steps', 'curve', 'initial_loss', 'final_loss', 'entry_contrast', 'contrast')


def check_schedule(arm, fit, control):
    stages = fit['stages']
    assert all(fit[k] == control[k] for k in SHARED_FIELDS)
    assert all(stages[0][k] == control['stages'][0][k] for k in STAGE_STATE)
    warm_settings = dict(control['stages'][0]['settings'], label=stages[0]['stage'])
    assert stages[0]['settings'] == warm_settings
    expected = {s['stage']: s['settings'] for s in control['stages']}
    if arm == 'warmup_wide':
        assert fit['reference_area_error'] == control['area_error']
        shape_index = 1
    else:
        assert [s['stage'] for s in stages[:6]] == CIRCLE_LABELS
        prefix = [.5e9, .75e9, 1.e9, 1.25e9]
        catalogs = [[.25e9], *(prefix[:i] for i in range(1, 5)), fit['frequencies_hz']]
        for stage, catalog in zip(stages, catalogs):
            cfg = stage['settings']
            assert cfg['frequencies_hz'] == catalog
            assert (cfg['M'], cfg['K_geometry'], cfg['quota'], cfg['iterations']) == (1, 4, 600, 44)
        shape_index = 6
    shape = stages[shape_index] if len(stages) > shape_index else None
    if shape is not None:
        assert shape['stage'] == ('full_1_M11' if arm == 'circle_then_full' else 'ladder_1_real')
    for stage in stages:
        name = stage['stage']
        if name not in expected:
            continue
        cfg = dict(expected[name])
        if arm == 'warmup_wide' and name.startswith('ladder_'):
            cfg['M'] += 2
            cfg['update_modes'] += 2
        assert stage['settings'] == cfg, (arm, fit['case'], name)
    return stages[shape_index-1], shape


def score(arm, case, fit, control, truth):
    preceding, shape = check_schedule(arm, fit, control)
    end = fit['stages'][-1]
    control_error, error = control['area_error'], fit['area_error']
    assert isclose(area_score(end['curve'], truth), error, rel_tol=0, abs_tol=1.e-11)
    control_pass, passed = control_error <= .05, error <= .05
    change = {(True, True): 'retained pass', (True, False): 'lost pass',
              (False, True): 'gained pass', (False, False): 'remained a miss'}[control_pass, passed]
    longest = max(fit['stages'], key=lambda s: s['seconds'])
    return dict(case=case, arm=arm, true_contrast=float(case.split('__c')[1]),
                warmup_error_pct=100*control_error, arm_error_pct=100*error,
                change_percentage_points=100*(error-control_error), warmup_pass=control_pass, arm_pass=passed,
                result=change, warmup_final_contrast=control['contrast'], final_contrast=fit['contrast'],
                last_pre_shape_stage=preceding['stage'], pre_shape_error_pct=100*preceding['area_error'],
                first_shape_stage=shape['stage'] if shape else None, first_shape_steps=shape['accepted_steps'] if shape else None,
                first_shape_error_pct=100*shape['area_error'] if shape else None,
                first_shape_entry_loss=shape['initial_loss'] if shape else None,
                first_shape_exit_loss=shape['final_loss'] if shape else None,
                warmup_outcome=control['outcome'], outcome=fit['outcome'], final_stage=end['stage'],
                stop_detail=fit['detail'], work_units=fit['work_units'], fit_seconds=fit['seconds'],
                longest_stage=longest['stage'], longest_stage_seconds=longest['seconds'])


def main():
    cases = sorted(scenes.CASES, key=lambda c: (float(c.split('__c')[1]), c))
    tables = {arm: [] for arm in ARMS}
    for arm in ARMS:
        assert {p.stem for p in (OUT/arm).glob('*.json')} == set(cases)
    for case in cases:
        name = case+'.json'
        ref = OUT/'warmup'/name
        control = read(ref)
        source = campaign.row(case)
        assert control['real_data_sha256'] == digest(campaign.ROOT/source['data'])
        assert control['initial_sha256'] == digest(campaign.ROOT/source['initial'])
        truth = curve_region(curve_from(read(campaign.ROOT/source['truth'])))
        assert isclose(area_score(control['stages'][-1]['curve'], truth), control['area_error'], rel_tol=0, abs_tol=1.e-11)
        fits = {arm: read(OUT/arm/name) for arm in ARMS}
        assert fits['warmup_wide']['reference_sha256'] == digest(ref)
        for arm in ARMS[:2]:
            assert fits[arm]['baseline_sha256'] == control['baseline_sha256']
        for a, b in zip(fits['circle_then_default']['stages'][:6], fits['circle_then_full']['stages'][:6]):
            assert all(a[k] == b[k] for k in ('settings', *STAGE_STATE)), case
        for arm, fit in fits.items():
            assert (fit['arm'], fit['case']) == (arm, case)
            tables[arm].append(score(arm, case, fit, control, truth))
    for arm, rows in tables.items():
        write_rows(OUT/arm/'comparison.csv', rows)
        totals = Counter(row['true_contrast'] for row in rows if row['arm_pass'])
        changes = Counter(row['result'] for row in rows)
        print(arm, sum(totals.values()), 'passes', dict(totals), dict(changes))


if __name__ == '__main__':
    main()
