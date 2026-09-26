"""Summarize terminal records and physical solve accounting, without PDE calls."""
from collections import Counter
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
STUDIES=('SC-042-state-strategies','SC-043-prospective-band','SC-044-noisy-fresh-cases')
GOOD={'COMPLETED_SCHEDULE','DISCREPANCY_REACHED','LOSS_TOLERANCE_REACHED'}


def read(path):
    return json.loads(path.read_text())


def main():
    studies=[]
    for name in STUDIES:
        folder=ROOT/name
        records=[dict(path=str(p.relative_to(ROOT)),**read(p)) for p in sorted((folder/'runs').rglob('result.json'))]
        exceptions=[dict(path=str(p.relative_to(ROOT)),**read(p)) for p in sorted((folder/'runs').rglob('failure.json'))]
        prefixes=[d for d in records if d.get('arm')=='prefix']
        paths=[d for d in records if d.get('arm')!='prefix']
        path_exceptions=[d for d in exceptions if d.get('arm')!='prefix']
        planned=24 if name.startswith('SC-042') else 18
        terminal_keys={(d['case'],d.get('profile'),d.get('arm',d.get('policy'))) for d in paths+path_exceptions}
        analysis=read(folder/'analysis.json') if (folder/'analysis.json').exists() else {}
        work=sum(d.get('total_units',0) for d in records+exceptions)
        audits=sum(d.get('audit_units',0) for d in records)
        failures=[dict(path=d['path'],outcome=d['outcome'],audit_passed=d.get('audit_passed',False))
                  for d in paths+path_exceptions if d['outcome'] not in GOOD or not d.get('audit_passed',False)]
        studies.append(dict(study=name,planned_paths=planned,terminal_paths=len(terminal_keys),
            scored_paths=sum('score' in d for d in paths),qualified_paths=sum(d.get('audit_passed',False) for d in paths),
            outcome_counts=dict(Counter(d['outcome'] for d in paths+path_exceptions)),
            complete=len(terminal_keys)==planned,unique_inverse_and_diagnostic_units=work,audit_units=audits,
            shared_prefix_count=len(prefixes),shared_prefix_inverse_units=sum(d['total_units'] for d in prefixes),
            shared_prefix_audit_units=sum(d['audit_units'] for d in prefixes),failures=failures,
            failure_cost_note='Exception costs include only recorded units; an interrupted call may have additional unrecorded work.',
            frozen_gate_results=analysis.get('aggregate',{})))
    inputs=ROOT/STUDIES[-1]/'inputs'
    data_units=sum(read(p)['work_units'] for p in inputs.glob('*/observations.json'))
    followup=ROOT/'SC-045-timeout-qualification'
    replay_rows=[dict(path=str(p.relative_to(ROOT)),**read(p)) for p in sorted((followup/'audits').glob('*.json'))]
    replay=dict(planned=5,returned=len(replay_rows),passed=sum(d['passed'] for d in replay_rows),
        complete=len(replay_rows)==5,additional_units=sum(d['work']['work_units'] for d in replay_rows),
        unrecorded_units_upper_bound=sum(d['work'].get('unrecorded_work_units_upper_bound',0) for d in replay_rows),rows=replay_rows)
    recovery_path=ROOT/'SC-046-lost-audit-recovery/result.json'
    recovered=read(recovery_path) if recovery_path.exists() else None
    recovery=dict(complete=recovered is not None,passed=recovered['passed'] if recovered else None,
        additional_units=recovered['work']['work_units'] if recovered else 0,
        path=str(recovery_path.relative_to(ROOT)),row=recovered)
    later_passed={d['source'] for d in replay_rows if d['passed']}
    if recovered and recovered['passed']:later_passed.add(recovered['source'])
    for study in studies:
        extra={str(Path(d['path']).parent) for d in study['failures']
               if not d['audit_passed'] and str(Path(d['path']).parent) in later_passed}
        study['qualified_endpoints_including_separate_followups']=study['qualified_paths']+len(extra)
    result=dict(studies=studies,data_generation_units=data_units,
        independent_timeout_qualification=replay,
        lost_audit_recovery=recovery,
        total_recorded_unique_work_units=data_units+replay['additional_units']+recovery['additional_units']+sum(d['unique_inverse_and_diagnostic_units']+d['audit_units'] for d in studies),
        unrecorded_work_units_upper_bound=replay['unrecorded_units_upper_bound'],
        complete=all(d['complete'] for d in studies) and replay['complete'] and recovery['complete'],
        accounting='A work unit is one frequency forward evaluation or reciprocal batch. Shared fresh-case prefixes are counted once here and charged to every complete path in SC-044 comparisons. Grid sizes vary by case; elapsed time is not a controlled speed benchmark.')
    (ROOT/'strategy_campaign_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Strategy campaign — status and solve accounting','',
           '**COMPLETE**' if result['complete'] else '**RUNNING — incomplete comparisons are provisional.**','',
           '| Study | Terminal paths | Original endpoint audit passes | Fitting + diagnostics, unique | Endpoint audits |',
           '|---|---:|---:|---:|---:|']
    for d in studies:
        lines.append(f"| [{d['study']}]({d['study']}/README.md) | {d['terminal_paths']}/{d['planned_paths']} | {d['qualified_paths']} | {d['unique_inverse_and_diagnostic_units']} | {d['audit_units']} |")
    lines.append(f"| [SC-045 independent timeout qualifications](SC-045-timeout-qualification/README.md) | {replay['returned']}/5 audits | {replay['passed']} | 0 | {replay['additional_units']} |")
    lines.append(f"| [SC-046 lost-result recovery](SC-046-lost-audit-recovery/README.md) | {int(recovery['complete'])}/1 audit | {int(bool(recovery['passed']))} | 0 | {recovery['additional_units']} |")
    lines+=['',f"Data generation: {data_units} fields. Total recorded work for terminal records: {result['total_recorded_unique_work_units']} units.",
            f"The lost SC-045 ledger contributes up to {replay['unrecorded_units_upper_bound']} additional unrecorded units. Its stored zero denotes missing accounting, not free computation.",
            'Work in running paths is omitted from this snapshot. Interrupted-call costs may be only partially recorded.',
            'SC-044 includes six shared prefix paths; each method is charged its full prefix in complete-path comparisons.',
            'Field and reciprocal units are a declared accounting convention, not identical floating-point cost. Numerical grids vary by case; host timing is uncontrolled.','',
            f"Including separate unchanged-endpoint qualifications, {sum(d['qualified_endpoints_including_separate_followups'] for d in studies)} "
            f"of {sum(d['scored_paths'] for d in studies)} returned scored endpoints have passing numerical evidence. "
            'This count does not alter original flags or any frozen strategy gate.','',
            '[Reviewer constraints on novelty](../../../docs/iterations/shape_frequency_continuation/iteration_24/02_claims_review.md).',
            '[Conditions for a useful next iteration](../../../docs/iterations/shape_frequency_continuation/iteration_24/03_next_decisions.md).',
            '[Environment](strategy_campaign_environment.json). [Machine-readable summary](strategy_campaign_summary.json).','',
            'Post-fit checks: [doubled metric sampling](strategy_metric_refinement.json), '
            '[fresh-case local errors and intrinsic curvature](strategy_feature_errors.json), '
            '[development-case regularity](SC-042-state-strategies/regularity.json). '
            'These descriptive diagnostics do not replace the frozen gates.','',
            '## Retained stopped or unqualified paths','']
    failures=[f for d in studies for f in d['failures']]
    for f in failures:
        match=next((r for r in replay_rows if r['source']==str(Path(f['path']).parent)),None)
        extra='' if match is None else f" Independent [SC-045 qualification]({match['path']}): {match['passed']} (original flag unchanged)."
        if recovered and recovered['source']==str(Path(f['path']).parent):
            extra+=f" Separate [SC-046 lost-result recovery]({recovery['path']}): {recovery['passed']}."
        lines.append(f"- [{f['path']}]({f['path']}): {f['outcome']}; original endpoint audit {f['audit_passed']}.{extra}")
    if not failures:lines.append('None among returned paths.')
    (ROOT/'STRATEGY_CAMPAIGN.md').write_text('\n'.join(lines)+'\n')
    print({k:result[k] for k in ('complete','total_recorded_unique_work_units')})


if __name__=='__main__':main()
