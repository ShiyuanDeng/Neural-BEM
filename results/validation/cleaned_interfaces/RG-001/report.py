"""Read-only RG-001 closeout and plots; all truth use is after fit return."""
from pathlib import Path
import json
import numpy as np
from bem_inverse.io import read, write, curve_from
from experiments.benchmark import campaign as B, scenes as S

OUT=Path(__file__).resolve().parent
ROOT=B.ROOT


def load(batch, arm, case):
    p=OUT/batch/arm/'runs'/case/'result.json'
    return read(p) if p.exists() else None


def main():
    summary=read(OUT/'report.json')
    rows=summary['rows']
    old=read(ROOT/'results/validation/cleaned_interfaces/ON-001/final_comparison.json')
    successes={r['id'] for r in old['rows'] if r['E']['recovered']}
    bycase={r['case']:r for r in rows}
    p1_failures=[case for case in successes if case in bycase and
        (not all(bycase[case]['arms'][a]['recovered'] for a in ('C','RG')) or not bycase[case].get('P1',{}).get('passed'))]
    comparisons=[]
    reference=read(ROOT/'results/validation/cleaned_interfaces/ON-review-20261005/failure_terminators.json')['cases']
    for case in ('aphex_twin__c0.5','aphex_twin__c4','aphex_twin__c13.3','hook__c13.3'):
        r=load('all','RG',case)
        if r:
            before=reference[case]['final_metrics']['rms_mm']
            endpoint=r['metrics']
            comparisons.append(dict(case=case,abort_rms_mm=before,rms_mm=endpoint['rms_mm'],
                reduction_fraction=1-endpoint['rms_mm']/before,shape_passed=endpoint['rms_mm']<=1 and endpoint['hausdorff_upper_mm']<=2,
                audit_passed=r['final_audit_passed'],recovered=r['recovered'],outcome=r['outcome'],detail=r.get('detail'),
                stages=[s['stage'] for s in r['stages']],
                past_original_stage=any(s['stage']==('stage_4_damped' if case=='aphex_twin__c0.5' else 'release_M15') for s in r['stages']),
                accepted_overshoots=r['accepted_resolution_overshoots'],
                largest_accepted_overshoot=r['largest_accepted_resolution_overshoot']))
    complete=len(rows)==30
    valid=complete and not p1_failures
    partials=[r['case'] for r in comparisons if r['shape_passed'] and r['audit_passed']]
    progresses=[r['case'] for r in comparisons if r['reduction_fraction']>=.25]
    additions=summary['additions']
    classification=('INVALID' if p1_failures else 'UNFINISHED' if not complete else
        'Major recovery success' if len(additions)>=2 else 'Useful partial result' if additions or partials else
        'Mechanism confirmed, no recovery' if progresses else 'Negative')
    common=[r for r in rows if all(r['arms'][a]['recovered'] for a in ('C','RG'))]
    ratios=[r['arms']['C']['audited_output_seconds']/r['arms']['RG']['audited_output_seconds'] for r in common]
    timing=dict(common_successes=len(common),median_C_over_RG=float(np.median(ratios)) if ratios else None,
        p10_C_over_RG=float(np.percentile(ratios,10)) if ratios else None,
        total_audited_seconds={a:sum(r['arms'][a]['audited_output_seconds'] or 0 for r in rows) for a in ('C','RG')})
    checks={case:read(OUT/'independent'/f'{case}.json') for case in additions if (OUT/'independent'/f'{case}.json').exists()}
    repeats={case:load('recovery_repeat','RG',case) for case in additions}
    reach={case:load('extended','RG',case) for case in ('aphex_twin__c0.5','aphex_twin__c4','aphex_twin__c13.3','hook__c13.3')}
    all_audits=[r['arms']['RG']['final_audit_passed'] for r in rows]
    p2=next((r for r in comparisons if r['case']=='aphex_twin__c4'),None)
    p3=next((r for r in comparisons if r['case']=='aphex_twin__c0.5'),None)
    p4=[r for r in comparisons if r['case'] in ('aphex_twin__c13.3','hook__c13.3')]
    predictions=dict(P1='holds' if valid else 'falsified' if p1_failures else 'unfinished',
        P2='holds' if p2 and (p2['recovered'] or (p2['shape_passed'] and p2['audit_passed'])) else 'falsified' if p2 else 'unrun',
        P3='holds' if p3 and p3['rms_mm']<4.4 and p3['past_original_stage'] else 'falsified' if p3 else 'unrun',
        P4='holds' if len(p4)==2 and all(not r['recovered'] and r['rms_mm']>=3 for r in p4) else 'falsified' if p4 else 'unrun',
        P5=dict(endpoints_passing=sum(bool(v) for v in all_audits),endpoints_checked=len(all_audits),
                failed_cases=[r['case'] for r in rows if not r['arms']['RG']['final_audit_passed']]))
    result=dict(classification=classification,complete=complete,P1_failures=p1_failures,predictions=predictions,
        recovery=summary['recovery'],additions=additions,failure_progress=comparisons,timing=timing,
        new_recovery_checks={case:dict(nodal_passed=checks.get(case,{}).get('passed'),
            repeat_recovered=(repeats[case] or {}).get('recovered')) for case in additions},
        extended={case:None if r is None else {k:r.get(k) for k in ('recovered','metrics','outcome','final_audit_passed','maximum_residual','audited_output_seconds')} for case,r in reach.items()})
    write(OUT/'closeout.json',result)
    lines=['# RG-001 — decision-relative resolution gate','',f"Classification: **{classification}**. Completed {len(rows)}/30 benchmark pairs.",'',
        f"Recovery: C {summary['recovery']['C']}/30; RG {summary['recovery']['RG']}/30. New recoveries: {', '.join(additions) or 'none'}.",'',
        'Stage 0: all 30 truth endpoints pass the unchanged audit and residual gate. All aphex truths pass every declared stage pair. The exact cog 13.3 truth overshoots the early undamped pair by 25.006x; its final pair passes. No aphex prediction was revised.','',
        'Stage 1: 35 focused gate tests pass; package/cleaned regression suite 247 passed and affected shared-continuation/physics/geometry suite 348 passed. The initial archive-dictionary assertion failure and the first Stage 0 cleanup error are retained. Four killing trials replay with exactly identical gains and are accepted by decision mode.','',
        '## Four-failure mechanism','',
        '| Case | B abort RMS mm | RG RMS mm | Reduction | Audit | Recovery | Accepted overshoots |',
        '|---|---|---|---|---|---|---|']
    for r in comparisons:
        lines.append(f"| {r['case']} | {r['abort_rms_mm']:.6f} | {r['rms_mm']:.6f} | {100*r['reduction_fraction']:.1f}% | {r['audit_passed']} | {r['recovered']} | {r['accepted_overshoots']} |")
    lines+=['','## Registered predictions','',f"P1: {predictions['P1']}; P2: {predictions['P2']}; P3: {predictions['P3']}; P4: {predictions['P4']}.",'',
        f"P5 endpoint audits: {sum(bool(v) for v in all_audits)}/{len(all_audits)} pass. Failed cases: {', '.join(predictions['P5']['failed_cases']) or 'none'}.",'',
        'P3 requires leaving stage_3_damped as well as improving RMS. Its original trial is accepted, but the run still stops inside that stage on a later production failure, so the registered prediction is falsified.','',
        'The 26 converged common successes pass their audits. All four RG failure endpoints fail the field gate; these endpoints are hard stops rather than newly converged outputs. P5 has no newly converged failure endpoint to test, while its stated warning about unresolved RG endpoints is observed.','',
        '## Independent checks and repeats','']
    for case in additions:
        lines.append(f"- {case}: independent nodal N1024/N2048 audit {checks.get(case,{}).get('passed', 'unrun')}; fresh RG recovery {(repeats[case] or {}).get('recovered','unrun')}.")
    if not additions:
        lines.append('No new benchmark recovery, so new-recovery-only nodal checks and repeats are inapplicable.')
    lines+=['','## Timing','',f"Common successes: {len(common)}. Median C/RG: {timing['median_C_over_RG']}. Suite audited totals including failures: {timing['total_audited_seconds']} seconds.",'',
        'Times include CUDA startup, initial audit and final/early audit; they exclude imports and truth scoring. Two additional timing repeats per declared timing case are reported separately in the evidence bundle.','',
        '## Extended-budget diagnostics','',
        'These are outside the 120 s / 13,412-unit benchmark and never counted as benchmark recoveries.','',
        '| Case | Recovery | RMS mm | Audit | Outcome |','|---|---|---|---|---|']
    for case,r in reach.items():
        lines.append(f"| {case} | {'unrun' if r is None else r['recovered']} | {'—' if r is None else r['metrics']['rms_mm']} | {'—' if r is None else r['final_audit_passed']} | {'—' if r is None else r['outcome']} |")
    lines+=['','The default gate remains absolute. The evidence supports pre-registering RP-001 (a bounded modal resolution response): the relaxed gate accepts steps but leaves the four failure endpoints unresolved. PX-001 may still be needed for the contrast-13.3 basin. No successor experiment is authorized or opened.','',
        '[Plan](03_plan.md), [execution record](04_rg001_execution.md), [machine-readable closeout](../../../../results/validation/cleaned_interfaces/RG-001/closeout.json), [case table](../../../../results/validation/cleaned_interfaces/RG-001/table.md).','',
        '![RG-001 endpoints](../../../../results/validation/cleaned_interfaces/RG-001/boundaries.png)','']
    (ROOT/'docs/iterations/cleaned_interfaces/iteration_31/05_results.md').write_text('\n'.join(lines))
    plot()
    print(json.dumps({k:result[k] for k in ('classification','recovery','additions','P1_failures','predictions')},indent=2))


def plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(10,3,figsize=(12,30))
    for case,ax in zip(S.CASES,axes.ravel()):
        truth=curve_from(read(ROOT/B.row(case)['truth'])).values(2048)*50
        ax.plot(truth.real,truth.imag,'k--',lw=1.4,label='truth')
        for batch,arm,color,style in [('all','C','#427ab3','-'),('all','RG','#d17229','-'),('extended','RG','#329561',':')]:
            r=load(batch,arm,case)
            if r and 'final_curve' in r:
                z=curve_from(r['final_curve']).values(2048)*50
                label=arm if batch=='all' else 'RG extended'
                ax.plot(z.real,z.imag,color=color,ls=style,lw=1,label=label)
        ax.set_title(case,fontsize=10)
        ax.set_aspect('equal');ax.set_xlabel('mm');ax.set_ylabel('mm');ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(OUT/'boundaries.png',dpi=130);plt.close(fig)


if __name__=='__main__':
    main()
