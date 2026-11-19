"""Score the 18 round-two TG-002 fits against their matched warm-up controls."""
from math import isclose

from bem_inverse.io import curve_from, digest, read
from experiments.benchmark import campaign
from experiments.comparison.check_stage_stops import curve_region
from experiments.comparison.compare_clean_schedules import OUT, area_score, write_rows

SIX = ('kite', 'peanut', 'asymmetric', 'hook', 'cross', 'cog')
THREE = ('star', 'c_shape', 'aphex_twin')
# Each paired comparison changes either the start rule, the warm-up budget, or the wall.
COMPARISONS = (
    ('two_sided', 'warmup', SIX), ('two_sided_long', 'two_sided', SIX),
    ('warmup_long', 'warmup', THREE), ('warmup_long_wall600', 'warmup_long', THREE),
)
STATE = ('stage', 'accepted_steps', 'initial_loss', 'entry_contrast', 'final_loss', 'contrast', 'curve')


def check_stages(saved, control):
    prefix = 0
    first_difference = None
    for left, right in zip(control['stages'], saved['stages']):
        assert left['stage'] == right['stage']
        changed = {k for k in left['settings'].keys() | right['settings'].keys()
                   if left['settings'].get(k) != right['settings'].get(k)}
        expected = ({'iterations', 'quota'} if left['stage'] == 'warmup_025_real'
                    and saved['arm'] in ('two_sided_long', 'warmup_long') else set())
        assert changed == expected, (saved['case'], left['stage'], changed)
        if first_difference is None:
            if all(left[k] == right[k] for k in STATE):
                prefix += 1
            else:
                first_difference = (left, right)
    left, right = first_difference or ({}, {})
    return dict(exact_prefix_stages=prefix, control_stage_count=len(control['stages']),
                variant_stage_count=len(saved['stages']), first_different_stage=left.get('stage'),
                same_entry_at_difference=(None if not left else all(left[k] == right[k]
                    for k in ('initial_loss', 'entry_contrast'))),
                control_steps_at_difference=left.get('accepted_steps'), variant_steps_at_difference=right.get('accepted_steps'))


def check_sides(saved, warm):
    selection = saved['side_selection']
    if selection is None:
        assert saved['start_rule'] == 'weak' and saved['start_contrast'] == warm['start_contrast']
        return []
    weak, mirror = selection['sides']
    assert (weak['start_contrast'], mirror['start_contrast']) == (warm['start_contrast'], 2-warm['start_contrast'])
    chosen = min((weak, mirror), key=lambda s: s['final_loss'])
    assert saved['start_contrast'] == chosen['start_contrast'] == selection['chosen_start_contrast']
    for k in ('initial_loss', 'final_loss', 'contrast', 'accepted_steps', 'stop', 'area_error'):
        assert saved['stages'][0][k] == chosen[k]
        if saved['arm'] == 'two_sided':
            assert warm['stages'][0][k] == weak[k]
    return [dict(arm=saved['arm'], case=saved['case'], side=side, chosen=(s is chosen), **s)
            for side, s in [('weak', weak), ('mirror', mirror)]]


def main():
    endpoints, sides = [], []
    for arm, reference, names in COMPARISONS:
        assert {p.stem for p in (OUT/arm).glob('*.json')} == {n+'__c13.3' for n in names}
        for name in names:
            case = name+'__c13.3'
            path = case+'.json'
            saved, control, warm = [read(OUT/folder/path) for folder in (arm, reference, 'warmup')]
            for k in ('case', 'baseline_sha256', 'real_data_sha256', 'initial_sha256', 'frequencies_hz', 'material',
                      'solver', 'geometry_update', 'localization', 'work_limit', 'damping', 'execution', 'saved_start_contrast'):
                assert saved[k] == control[k] == warm[k], (arm, case, k)
            row = campaign.row(case)
            for field, source in [('real_data_sha256', row['data']), ('initial_sha256', row['initial']),
                                  ('baseline_sha256', saved['baseline'])]:
                assert saved[field] == digest(campaign.ROOT/source)
            assert saved['weak_start_contrast'] == warm['start_contrast']
            assert (saved['warmup_iterations'], saved['warmup_quota']) == ((44, 600) if arm=='two_sided' else (220, 3000))
            assert saved['seconds_limit'] == (600 if arm=='warmup_long_wall600' else 120)
            assert saved['work_limit'] == 13412
            truth = curve_region(curve_from(read(campaign.ROOT/row['truth'])))
            assert isclose(area_score(saved['stages'][-1]['curve'], truth), saved['area_error'], rel_tol=0, abs_tol=1e-11)
            sides.extend(check_sides(saved, warm))
            stage, end = saved['stages'][0], saved['stages'][-1]
            sel = saved['side_selection'] or {}
            error, before = saved['area_error'], control['area_error']
            endpoints.append(dict(arm=arm, case=case, control=reference, control_error=before, warmup_error=warm['area_error'],
                error=error, change_pp=100*(error-before), passed=error<=.05, control_passed=before<=.05,
                warmup_start=saved['start_contrast'], warmup_steps=stage['accepted_steps'], warmup_loss=stage['final_loss'],
                warmup_contrast=stage['contrast'], warmup_stop=stage['stop'], final_contrast=saved['contrast'],
                final_stage=end['stage'], outcome=saved['outcome'], detail=saved['detail'], seconds=saved['seconds'],
                work=saved['work_units'], selection_extra_work=sel.get('extra_work_units', 0),
                selection_extra_seconds=sel.get('extra_seconds', 0), **check_stages(saved, control)))
    write_rows(OUT/'round_two_endpoints.csv', endpoints)
    write_rows(OUT/'round_two_side_selection.csv', sides)


if __name__ == '__main__':
    main()
