"""Rebuild comparisons and evidence checks from portable JSON, without solves."""
import importlib.util
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sc042_analysis_source', HERE/'run.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    r.verify()
    rows, comparisons, checks = [], [], []
    data = {}
    for p in sorted((HERE/'runs').glob('*/*/result.json')):
        result = r.sc.read(p)
        case, arm = result['case'], result['arm']
        data[case, arm] = result
        progress = r.sc.read(p.parent/'progress.json')['states']
        rows.append(dict(case=case, arm=arm, outcome=result['outcome'],
            loss=result['stages'][-1]['final_loss'], **result['score'], units=result['total_units'],
            audit_passed=result['audit_passed']))
        checks.append(dict(case=case, arm=arm, check='stage_and_path_budget', passed=bool(
            result['total_units'] == sum(s['work']['work_units'] for s in result['stages'])
            and result['total_units'] <= 3*r.QUOTA
            and all(s['work']['work_units'] <= r.QUOTA for s in result['stages']))))
        for stage in result['stages']:
            accepted = [s for s in progress if s['stage'] == stage['stage']]
            checks.append(dict(case=case, arm=arm, stage=stage['stage'], check='within_stage_decrease',
                passed=all(b['loss'] < a['loss'] for a, b in zip(accepted, accepted[1:]))))
        checks.append(dict(case=case, arm=arm, check='last_accepted_endpoint', passed=bool(
            np.array_equal(r.ast.curve_from(progress[-1]['curve']).coefficients,
                           r.ast.curve_from(result['curve']).coefficients))))
    for case in r.CASES:
        if not all((case, arm) in data for arm in r.ARMS):
            continue
        base = data[case, 'none']
        common = min(data[case, arm]['total_units'] for arm in r.ARMS)
        at_common = {}
        for arm in r.ARMS:
            progress = r.sc.read(HERE/'runs'/case/arm/'progress.json')['states']
            eligible = [s for s in progress if s['total_units'] <= common]
            at_common[arm] = eligible[-1] if eligible else None
        for arm in r.ARMS[1:]:
            candidate = data[case, arm]
            ratios = {metric: max(candidate['score'][metric], .01)/max(base['score'][metric], .01)
                      for metric in ('rms_mm', 'hausdorff_mm')}
            comparisons.append(dict(case=case, arm=arm, ratios=ratios, common_inverse_units=common,
                common_scores={a: None if s is None else dict(units=s['total_units'], loss=s['loss'], score=s['score'])
                               for a, s in at_common.items()},
                additional_failure=candidate['outcome'] != 'COMPLETED_SCHEDULE' and base['outcome'] == 'COMPLETED_SCHEDULE',
                audit_passed=candidate['audit_passed']))
        once = r.sc.read(HERE/'runs'/case/'once'/'accepted.json')['states']
        boundary = r.sc.read(HERE/'runs'/case/'boundary'/'accepted.json')['states']
        a, b = [[s for s in states if s['stage'] == states[0]['stage']] for states in (once, boundary)]
        checks.append(dict(case=case, check='once_boundary_first_stage_identical',
            passed=len(a) == len(b) and all(x['loss'] == y['loss'] and x['curve'] == y['curve'] for x, y in zip(a, b))))
    aggregate = {}
    for arm in r.ARMS[1:]:
        selected = [row for row in comparisons if row['arm'] == arm]
        if selected:
            gm = float(np.exp(np.mean(np.log([s['ratios']['rms_mm'] for s in selected]))))
            worst = max(v for s in selected for v in s['ratios'].values())
            aggregate[arm] = dict(cases=len(selected), rms_geometric_mean_ratio=gm, worst_ratio=worst,
                development_gate_passed=len(selected) == 6 and gm <= 1 and worst <= 1.25
                and all(s['audit_passed'] and not s['additional_failure'] for s in selected))
    r.write(HERE/'analysis.json', dict(rows=rows, comparisons=comparisons, aggregate=aggregate,
            checks=checks, checks_passed=all(c['passed'] for c in checks), complete=len(rows) == 24))
    lines = ['# SC-042 — matched state treatment', '',
             'Rebuilt by `analyse.py` from JSON. Partial until all 24 paths return.', '',
             '| Case | Arm | RMS mm | Hausdorff mm | Radius mm | Loss | Work | Outcome | Audit |',
             '|---|---|---:|---:|---:|---:|---:|---|---|']
    for row in rows:
        lines.append(f"| {row['case']} | {row['arm']} | {row['rms_mm']:.5g} | {row['hausdorff_mm']:.5g} | "
                     f"{row['tightest_radius_fine_mm']:.5g} | {row['loss']:.4g} | {row['units']} | {row['outcome']} | {row['audit_passed']} |")
    lines += ['', f"Evidence checks: {sum(c['passed'] for c in checks)}/{len(checks)}.", '',
              'The four interventions have the same allowance; actual work can differ. Cleanup can',
              'increase the loss at a stage boundary. Last returned states are scored, not best-truth iterates.',
              'Common-work checkpoints and floored comparisons are in `analysis.json`.', '']
    (HERE/'TABLES.md').write_text('\n'.join(lines))
    print({'completed':len(rows), 'checks_passed':all(c['passed'] for c in checks), 'aggregate':aggregate})


if __name__ == '__main__':
    main()
