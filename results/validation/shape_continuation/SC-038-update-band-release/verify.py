"""Check frozen provenance, matched settings, prefixes and cost accounting."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(path):
    return json.loads(path.read_text())


def main():
    checks = []
    folders = [HERE, HERE / 'dense_kite']
    if (HERE / 'final_m19/completion.json').exists():
        folders.append(HERE / 'final_m19')
    for folder in folders:
        manifest = read(folder / 'manifest.json')
        for section in ('sources', 'inputs'):
            mismatches = [p for p, h in manifest[section].items()
                          if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
            checks.append(dict(bundle=folder.name, kind=section, passed=not mismatches, mismatches=mismatches))
        assert read(folder / 'completion.json')['status'] == 'COMPLETE'
        qualification = folder / 'qualification.json'
        start_passed = read(qualification)['passed'] if qualification.exists() else read(HERE / 'dense_kite/final_audit.json')['passed']
        checks.append(dict(bundle=folder.name, kind='all_numerical_audits',
                           passed=start_passed and read(folder / 'final_audit.json')['passed']))
    for case in ('circle_to_c', 'kite'):
        a, b = [read(HERE / 'runs' / case / arm / 'configuration.json') for arm in ('fixed_m9', 'release_m')]
        equal = all(a[k] == b[k] for k in ('initial', 'backend', 'update', 'frequencies_hz', 'prefix_work'))
        equal &= all({k: v for k, v in sa.items() if k != 'update_modes'} ==
                     {k: v for k, v in sb.items() if k != 'update_modes'} for sa, sb in zip(a['stages'], b['stages']))
        equal &= len(a['frequencies_hz']) == 19
        equal &= [s['update_modes'] for s in a['stages']] == [9, 9, 9]
        equal &= [s['update_modes'] for s in b['stages']] == [11, 15, 19]
        checks.append(dict(case=case, kind='original_arms_only_M_differs', passed=bool(equal)))
    for arm in ('fixed_m9', 'release_m'):
        old = read(HERE / 'runs/kite' / arm / 'configuration.json')
        dense = read(HERE / 'dense_kite/runs' / arm / 'configuration.json')
        start = read(HERE / 'runs/kite' / arm / 'release_1_history.json')['history'][-1]['coefficients']
        equal = start == dense['initial'] and old['backend'] == dense['backend'] and old['update'] == dense['update']
        for a, b in zip(old['stages'][1:], dense['stages']):
            equal &= {k: v for k, v in a.items() if k not in ('label', 'nodes', 'refined_nodes')} == {
                       k: v for k, v in b.items() if k not in ('label', 'nodes', 'refined_nodes')}
            equal &= b['nodes'] == 768 and b['refined_nodes'] == 1536
        checks.append(dict(arm=arm, kind='dense_replay_same_prefix_and_only_resolution_changed', passed=bool(equal)))
    a = read(HERE / 'runs/kite/fixed_m9/result.json')
    b = read(HERE / 'dense_kite/runs/fixed_m9/result.json')
    checks.append(dict(kind='fixed_M9_curve_unchanged_by_resolution', passed=a['curve'] == b['curve']))
    originals = [read(p) for p in sorted((HERE / 'runs').glob('*/*/result.json'))]
    dense = [read(p) for p in sorted((HERE / 'dense_kite/runs').glob('*/result.json'))]
    assert len(originals) == 4 and len(dense) == 2
    extra = [read(p) for p in (HERE / 'final_m19/runs').glob('*/result.json')]
    if extra:
        parent = next(r for r in dense if r['arm'] == 'release_m')
        configuration = read(HERE / 'final_m19/runs/release_m/configuration.json')
        previous_configuration = read(HERE / 'dense_kite/runs/release_m/configuration.json')
        expected = previous_configuration['stages'][-1]
        actual = configuration['stages'][0]
        common = all(expected[k] == actual[k] for k in expected if k not in ('label', 'quota'))
        common &= configuration['backend'] == previous_configuration['backend']
        common &= configuration['update'] == previous_configuration['update']
        checks.append(dict(kind='remaining_M19_same_numerical_settings', passed=bool(common)))
        checks.append(dict(kind='remaining_M19_same_state_and_original_work_ceiling', passed=(
            configuration['initial'] == parent['curve'] and parent['reason'] == 'TRIAL_WALL_LIMIT'
            and parent['work']['work_units'] + extra[0]['work']['work_units'] <= 3000)))
    all_runs = originals + dense + extra
    new_inverse_units = sum(r['work']['work_units'] for r in all_runs)
    audit_units = sum(r['work']['work_units'] for f in folders
                      for name in ('qualification.json', 'final_audit.json') if (f / name).exists() for r in read(f / name)['rows'])
    checks.append(dict(kind='inverse_units_match_completion_records', passed=new_inverse_units == sum(
        read(f / 'completion.json')['new_inverse_units'] for f in folders)))
    report = dict(passed=all(r['passed'] for r in checks), checks=checks,
                  new_inverse_units_including_all_attempts=new_inverse_units,
                  audit_units=audit_units, final_scoring_fields=sum(r['score']['evaluation_field_solves'] for r in all_runs))
    (HERE / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    assert report['passed']


if __name__ == '__main__':
    main()
