"""Read completed SPD-015 receipts; never rerun or rewrite numerical evidence."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

def read(path):
    return json.loads(path.read_text())

def strip_timing(value):
    if isinstance(value, dict):
        return {k:strip_timing(v) for k,v in value.items() if k != 'seconds'}
    if isinstance(value, list):
        return [strip_timing(v) for v in value]
    return value

report = dict(scope='Six saved SC-043 continuation suffixes, not full circle-start reconstructions',
    controls=dict(reference='SC_GEOMETRY_RUNTIME=reference', default='SC_GEOMETRY_RUNTIME unset',
                  forward='cuda', frequency_threads=4, blas_threads=1, concurrency='sequential workers on shared host'),
    geometry=read(HERE/'geometry/result.json'),
    source_count=len(read(HERE/'manifest.json')['sources']),
    input_count=len(read(HERE/'manifest.json')['inputs']), phases={})
for phase in ('batches','inverse','video'):
    data = read(HERE/phase/'result.json')
    rows = data['rows']
    totals = {arm:sum(row['seconds'] for row in rows if row['arm']==arm)
              for arm in sorted({row['arm'] for row in rows})}
    cases = {}
    for case in sorted({row['case'] for row in rows}):
        times = {arm:sum(row['seconds'] for row in rows if row['case']==case and row['arm']==arm)
                 for arm in totals}
        cases[case] = dict(seconds=times, reduction=1-times['both']/times['reference'])
    counts = {arm:{key:sum(row['checks'][key]['calls'] for row in rows if row['arm']==arm)
                   for key in rows[0]['checks']} for arm in totals}
    comparisons = ([row['identical'] for row in rows] if phase=='batches' else
                   [read(HERE/phase/case/'comparison.json')['passed'] for case in cases])
    physical = {arm:sum((row['work']['attempted']+row['work']['jacobians'] if phase=='batches' else row['units'])
                        for row in rows if row['arm']==arm) for arm in totals}
    report['phases'][phase] = dict(passed=data['passed'] and all(comparisons), seconds=totals,
        reduction=1-totals['both']/totals['reference'], speedup=totals['reference']/totals['both'],
        cases=cases, executed_geometry_checks=counts, physical_units=physical,
        exact_comparisons=len(comparisons), harness_seconds=data['seconds'])

# A historical reference cross-check is numerical only; source archives retain
# their own provenance and original timing receipts.
archive = ROOT/'results/validation/speedup/SPD-014-20260927-geometry/inverse'
comparison = {}
for case in report['phases']['inverse']['cases']:
    latest = HERE/'inverse'/case/'reference'/'runs'/case/'fixed'
    old = archive/case/'reference'/'runs'/case/'fixed'
    comparison[case] = {name.name:strip_timing(read(name)) == strip_timing(read(old/name.name))
                        for name in latest.glob('*.json') if (old/name.name).exists()}
report['prior_reference_numeric_comparison'] = comparison
report['passed'] = report['geometry']['passed'] and all(p['passed'] for p in report['phases'].values())
(HERE/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
for name, data in report['phases'].items():
    print(name, data['passed'], data['seconds'], 'reduction',data['reduction'], 'physical_units',data['physical_units'])
print('prior-reference files',sum(len(c) for c in comparison.values()),'all exact',all(all(c.values()) for c in comparison.values()))
