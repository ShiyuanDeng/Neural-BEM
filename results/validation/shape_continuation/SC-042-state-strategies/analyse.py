"""Rebuild comparisons and evidence checks from portable JSON, without solves."""
import importlib.util
from collections import Counter
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sc042_analysis_source', HERE/'run.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    r.verify()
    rows, comparisons, checks, stage_diagnostics = [], [], [], []
    data = {}
    failures = [dict(path=str(p.relative_to(HERE)), **r.sc.read(p))
                for p in sorted((HERE/'runs').glob('*/*/failure.json'))]
    for p in sorted((HERE/'runs').glob('*/*/result.json')):
        result = r.sc.read(p)
        case, arm = result['case'], result['arm']
        data[case, arm] = result
        audit=r.sc.read(p.parent/'audit.json')
        audit_reason=None if audit['passed'] else 'wall_limit' if 'TrialWallLimit' in audit.get('traceback','') else 'exception' if audit.get('traceback') else 'tolerance_disagreement'
        progress = r.sc.read(p.parent/'progress.json')['states']
        rows.append(dict(case=case, arm=arm, outcome=result['outcome'],
            loss=result['stages'][-1]['final_loss'], **result['score'], units=result['total_units'],
            audit_passed=result['audit_passed'],audit_failure_kind=audit_reason))
        checks.append(dict(case=case, arm=arm, check='stage_and_path_budget', passed=bool(
            result['total_units'] == sum(s['work']['work_units'] for s in result['stages'])
            and result['total_units'] <= 3*r.QUOTA
            and all(s['work']['work_units'] <= r.QUOTA for s in result['stages']))))
        for stage in result['stages']:
            accepted = [s for s in progress if s['stage'] == stage['stage']]
            saved=r.sc.read(p.parent/f"{stage['stage']}.json")
            after_last=stage['work']['work_units']-accepted[-1]['stage_units'] if accepted else None
            stage_diagnostics.append(dict(case=case,arm=arm,stage=stage['stage'],M=stage['M'],
                outcome=stage['outcome'],stop=stage['stop'],accepted_steps=sum(s['iteration']>0 for s in accepted),
                work_after_last_accepted_state=after_last,
                trial_status_counts=dict(Counter(t.get('status','interrupted_before_status') for t in saved['trials'])),
                qualification_note='Work after the last accepted state includes derivative and rejected-trial checks; it is not all avoidable work.'))
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
    terminal = set(data) | {(d['case'], d['arm']) for d in failures}
    pending = [dict(case=case, arm=arm) for case in r.CASES for arm in r.ARMS
               if (case, arm) not in terminal]
    aggregate = {}
    for arm in r.ARMS[1:]:
        selected = [row for row in comparisons if row['arm'] == arm]
        if selected:
            gm = float(np.exp(np.mean(np.log([s['ratios']['rms_mm'] for s in selected]))))
            worst = max(v for s in selected for v in s['ratios'].values())
            common_ratios = [max(s['common_scores'][arm]['score']['rms_mm'], .01)/
                             max(s['common_scores']['none']['score']['rms_mm'], .01)
                             for s in selected if s['common_scores'][arm] and s['common_scores']['none']]
            aggregate[arm] = dict(cases=len(selected), rms_geometric_mean_ratio=gm, worst_ratio=worst,
                common_work_rms_geometric_mean_ratio=float(np.exp(np.mean(np.log(common_ratios)))) if common_ratios else None,
                development_gate_passed=len(selected) == 6 and gm <= 1 and worst <= 1.25
                and all(s['audit_passed'] and not s['additional_failure'] for s in selected))
    r.write(HERE/'analysis.json', dict(rows=rows, comparisons=comparisons, aggregate=aggregate,
            failures=failures, pending=pending, planned=24, terminal=len(terminal),stage_diagnostics=stage_diagnostics,
            inverse_units=sum(s['units'] for s in rows), audit_units=sum(d['audit_units'] for d in data.values()),
            checks=checks, checks_passed=all(c['passed'] for c in checks), complete=len(terminal) == 24))
    lines = ['# SC-042 — matched state treatment', '',
             f'Rebuilt by `analyse.py` from JSON. {len(terminal)}/24 terminal paths; {len(failures)} exceptions; {len(pending)} pending.', '',
             '| Case | Arm | RMS mm | Hausdorff mm | Radius mm | Loss | Work | Outcome | Audit |',
             '|---|---|---:|---:|---:|---:|---:|---|---|']
    for row in rows:
        lines.append(f"| {row['case']} | {row['arm']} | {row['rms_mm']:.5g} | {row['hausdorff_mm']:.5g} | "
                     f"{row['tightest_radius_fine_mm']:.5g} | {row['loss']:.4g} | {row['units']} | {row['outcome']} | {row['audit_passed']} |")
    for row in failures:
        lines.append(f"| {row['case']} | {row['arm']} | — | — | — | — | — | EXCEPTION | False |")
    lines += ['', f"Evidence checks: {sum(c['passed'] for c in checks)}/{len(checks)}.", '',
              'The four interventions have the same allowance; actual work can differ. Cleanup can',
              'increase the loss at a stage boundary. Last returned states are scored, not best-truth iterates.',
              'Common-work checkpoints and floored comparisons are in `analysis.json`.', '']
    lines += ['Exceptions remain in the 24-path denominator and prevent an arm from passing its six-case gate.',
              'Geometric means describe available scored pairs; they are provisional until the full denominator is resolved.', '']
    (HERE/'TABLES.md').write_text('\n'.join(lines))
    print({'completed':len(rows), 'checks_passed':all(c['passed'] for c in checks), 'aggregate':aggregate})


if __name__ == '__main__':
    main()
