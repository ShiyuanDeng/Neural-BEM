"""Read saved evidence for the review; never run a solver or modify run bundles.

Run from any directory with Python 3. Writes only the adjacent review JSON.
Exact truth-array counts are not counts modulo rotation/reparameterization.
"""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
import subprocess

ROOT = Path(__file__).resolve().parents[2]
INPUTS = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(relative):
    path = ROOT / relative
    INPUTS[relative] = digest(path)
    return json.loads(path.read_text())


def describe(rows):
    errors = [r['rms_mm'] for r in rows]
    return dict(count=len(rows), recovered=sum(r['recovered'] for r in rows),
                retention_pass=sum(r['status'] == 'PASS' for r in rows),
                rms_mm=dict(min=min(errors), median=median(errors), max=max(errors)),
                total_seconds=sum(r['total_seconds'] for r in rows))


ci_base = 'results/validation/cleaned_interfaces/CI-001'
ci = read(f'{ci_base}/comparison.json')
manifest = read(f'{ci_base}/manifest.json')
rows = ci['rows']
assert len(rows) == 36 and ci['passed'] == 28
assert sum(r['recovered'] for r in rows) == 34
truths = []
for case in manifest['cases']:
    truth = read(case['truth'])
    truths.append(json.dumps({k: truth[k] for k in ('real', 'imag')}, sort_keys=True))
    result = read(f"{ci_base}/runs/{case['id']}/result.json")
    row = next(r for r in rows if r['id'] == case['id'])
    assert result['recovered'] == row['recovered']
    assert result['metrics']['rms_mm'] == row['rms_mm']
assert digest(ROOT / ci_base / 'sources.tar.gz') == manifest['archive_sha256']

nu_base = 'results/validation/cleaned_interfaces/NU-007a-20261003'
nu = read(f'{nu_base}/qualification.json')
assert nu['adoption_ready'] and all(nu['gates'].values())
assert digest(ROOT / nu_base / 'manifest.json') == nu['manifest_sha256']
assert digest(ROOT / nu_base / 'sources.tar.gz') == nu['source_archive_sha256']
core = []
pair_checks = []
for case in nu['cases']:
    cid = case['case']
    times = {'host': [], 'device': []}
    for rep in (1, 2, 3):
        pair = {arm: read(f'{nu_base}/pair_{rep}/{arm}/runs/{cid}/result.json')
                for arm in times}
        a, b = pair['host'], pair['device']
        assert a['final_curve'] == b['final_curve']
        for key in ('outcome', 'recovered', 'comparison_status', 'total_units',
                    'fit_and_localization_units', 'initial_audit_passed', 'final_audit_passed'):
            assert a[key] == b[key], (cid, rep, key)
        assert a['final_audit_passed'] and b['final_audit_passed']
        for arm in times:
            times[arm].append(pair[arm]['total_seconds'])
        pair_checks.append(dict(case=cid, repeat=rep, final_curve_exact=True,
                                units_and_outcomes_equal=True, endpoint_audits=True))
    for arm in times:
        assert math.isclose(median(times[arm]), case['wall_median'][arm], rel_tol=1e-14)
    core.append(dict(case=cid, rms_mm=b['metrics']['rms_mm'], recovered=b['recovered'],
                     retention_status=b['comparison_status'], median_seconds=case['wall_median'],
                     speedup=case['wall_median']['host'] / case['wall_median']['device']))

fm_base = 'results/validation/cleaned_interfaces/FM-001'
fm = read(f'{fm_base}/summary.json')
full = [read(str(p.relative_to(ROOT)))
        for p in sorted((ROOT / fm_base / 'F/runs').glob('*/result.json'))]
assert len(full) == 36
assert sum(r['recovered'] for r in full) == fm['F']['recovered'] == 36
assert sum(r['paired_recovered'] for r in full) == fm['F']['unchanged_paired_recovered'] == 32
assert sum(r['paired_historical_pass'] for r in full) == fm['F']['historical_pass'] == 15

fm2_base = 'results/validation/cleaned_interfaces/FM-002'
fm2 = read(f'{fm2_base}/comparison.json')
for relative, expected in fm2['inputs'].items():
    actual = ROOT / fm2_base / relative
    assert digest(actual) == expected, str(actual)
    INPUTS[str(actual.relative_to(ROOT))] = expected
assert len(fm2['rows']) == 12
for arm, count in [('D0', 3), ('D1', 3), ('R0', 1), ('R1', 1)]:
    assert sum(r['recovered'] for r in fm2['rows'] if r['arm'] == arm) == count

rb = read('results/validation/relaxed_bie/RB-001/comparison.json')
assert len(rb['rows']) == 4 and rb['recovered'] == rb['paired_recovered'] == 0
assert all(r['final_audit_passed'] and not r['original_resolution_audit_passed'] for r in rb['rows'])

report = dict(
    scope='Saved-artifact review only. No numerical experiments or solver tests rerun.',
    reviewed_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
    ci001=dict(all=describe(rows), recovered=describe([r for r in rows if r['recovered']]),
               noisy_by_case_label=describe([r for r in rows if 'noise' in r['id'] or 'noisy' in r['id']]),
               core=describe([r for r in rows if r['panel'] == 'core']),
               panel_counts=dict(Counter(r['panel'] for r in manifest['cases'])),
               contrast_counts=dict(Counter(r['contrast'] for r in manifest['cases'])),
               unique_truth_paths=len({r['truth'] for r in manifest['cases']}),
               unique_exact_truth_arrays=len(set(truths)),
               unrecovered_retention_passes=[r['id'] for r in rows if not r['recovered'] and r['status'] == 'PASS']),
    nu007a=dict(core=core, raw_pair_checks=pair_checks,
                seconds=nu['seconds'], precheck=nu['precheck'], runtime=nu['runtime'],
                wall_speedup=nu['seconds']['wall_median']['host'] / nu['seconds']['wall_median']['device'],
                certificate_speedup=nu['seconds']['certificate_median']['host'] / nu['seconds']['certificate_median']['device']),
    fm001=dict(full_recovered=36, paired_recovered=32, historical_paired_pass=15,
               rms_mm_max=max(r['metrics']['rms_mm'] for r in full),
               total_seconds=sum(r['total_seconds'] for r in full)),
    fm002=dict(totals=fm2['totals'], input_hashes_verified=len(fm2['inputs'])),
    rb001=dict(recovered=rb['recovered'], paired_recovered=rb['paired_recovered'],
               rows=[{k: r[k] for k in ('case', 'arm', 'original_rms_mm', 'rms_mm',
                      'hausdorff_upper_mm', 'maximum_residual', 'recovered', 'paired_recovered',
                      'final_audit_passed', 'original_resolution_audit_passed', 'outcome',
                      'audit_resolution', 'fresh_fit_units', 'fit_units', 'fresh_seconds')}
                     for r in rb['rows']], numerical_seconds=rb['numerical_seconds']),
    external_wavenumber_range=[2 * math.pi * f * math.sqrt(4 * math.pi * 1e-7 * 8.854187817e-12 * 6) * .05
                              for f in (.25e9, 2.5e9)],
    evidence_sha256=INPUTS)
destination = Path(__file__).with_suffix('.json')
destination.write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS: {len(INPUTS)} distinct saved JSON inputs; 18 raw modal pairs; 36 nodal and 36 full-matrix endpoints.')
print(f'Wrote {destination.relative_to(ROOT)}')
