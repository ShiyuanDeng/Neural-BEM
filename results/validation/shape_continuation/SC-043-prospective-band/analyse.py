"""No-solve audit of prospective decisions and comparison with both simple rules."""
import importlib.util
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc043_analysis',HERE/'run.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    r.verify()
    rows=[]
    blocks=[]
    checks=[]
    trajectories={}
    initial_curves={}
    failures=[dict(path=str(p.relative_to(HERE)),**r.c.sc.read(p))
              for p in sorted((HERE/'runs').glob('*/*/failure.json'))]
    for p in sorted((HERE/'runs').glob('*/*/result.json')):
        d=r.c.sc.read(p)
        decisions=r.c.sc.read(p.parent/'decisions.json')['rows']
        audit=r.c.sc.read(p.parent/'audit.json')
        progress=r.c.sc.read(p.parent/'progress.json')['states']
        trajectories[d['case'],d['policy']]=progress
        initial_curves[d['case'],d['policy']]=decisions[0]['curve_before_fit']
        audit_reason=None if audit.get('passed') else 'wall_limit' if 'TrialWallLimit' in audit.get('traceback','') else 'exception' if audit.get('traceback') else 'tolerance_disagreement'
        rows.append(dict(case=d['case'],policy=d['policy'],outcome=d['outcome'],score=d['score'],
            units=d['total_units'],diagnostic_units=sum(s['diagnostic_units'] for s in d['stages']),
            audit_passed=d['audit_passed'],audit_failure_kind=audit_reason,
            bands=[s['M'] for s in d['stages']],loss=d['stages'][-1]['final_loss']))
        checks.append(dict(case=d['case'],policy=d['policy'],check='charged_diagnostics',passed=bool(
            d['total_units']==sum(s['units']+s['diagnostic_units'] for s in d['stages'])
            and all(s['units']+s['diagnostic_units']<=r.QUOTA for s in d['stages']))))
        checks.append(dict(case=d['case'],policy=d['policy'],check='complete_stage_records',passed=bool(
            len(decisions)==len(d['stages']) and
            (d['outcome']!='COMPLETED_SCHEDULE' or len(d['stages'])==3))))
        checks.append(dict(case=d['case'],policy=d['policy'],check='last_accepted_endpoint',passed=bool(
            progress and progress[-1]['curve']==d['curve'])))
        previous_total=0
        previous_m=None
        prior_stagnated=r.initial_stagnated(d['case'])
        for choice,stage in zip(decisions,d['stages']):
            accepted=[s for s in progress if s['block']==stage['block']]
            initial,final=stage['initial_loss'],stage['final_loss']
            blocks.append(dict(case=d['case'],policy=d['policy'],block=stage['block'],
                low=choice['low'],high=choice['high'],selected=choice['selected'],
                release=choice['release'],incremental_predicted_fraction=choice.get('incremental_fraction'),
                prior_stagnated=choice.get('prior_stagnated'),
                diagnostic_qualified=choice.get('qualification',{}).get('passed'),
                diagnostic_units=stage['diagnostic_units'],fit_units=stage['units'],
                initial_loss=initial,final_loss=final,
                actual_fractional_decrease=(initial-final)/initial if initial else 0.,
                outcome=stage['outcome'],stop=stage['stop']))
            valid=(stage['M']==choice['selected'] and choice['high']==choice['low']+6
                   and choice['selected']==(choice['high'] if choice['release'] else choice['low'])
                   and (previous_m is None or choice['low']==previous_m))
            if d['policy']=='atlas':
                low,high=choice['low_prediction'],choice['high_prediction']
                valid &= choice['release']==r.choose(low['predicted_decrease'],high['predicted_decrease'],low['initial_loss'])
                valid &= high['predicted_decrease']>=low['predicted_decrease']-1e-12*max(low['initial_loss'],1e-20)
                valid &= choice['qualification']['passed'] and choice['diagnostic_units']==76
            else:
                valid &= choice['diagnostic_units']==0 and choice['prior_stagnated']==prior_stagnated
                valid &= choice['release']==(d['policy']=='fixed' or prior_stagnated)
            checks.append(dict(case=d['case'],policy=d['policy'],block=stage['block'],check='frozen_decision',passed=bool(valid)))
            checks.append(dict(case=d['case'],policy=d['policy'],block=stage['block'],check='stage_receipt',passed=bool(
                accepted and accepted[0]['curve']==choice['curve_before_fit']
                and accepted[0]['loss']==initial and accepted[-1]['loss']==final
                and choice['total_units_before']==previous_total
                and stage['total_units']==previous_total+stage['units']+stage['diagnostic_units']
                and all(previous_total+stage['diagnostic_units']<=s['total_units']<=stage['total_units'] for s in accepted))))
            checks.append(dict(case=d['case'],policy=d['policy'],block=stage['block'],check='within_stage_decrease',passed=bool(
                all(b['loss']<a['loss'] for a,b in zip(accepted,accepted[1:])))))
            prior_stagnated=r.stagnation_flag([s['loss'] for s in accepted],stage['stop'])
            previous_total=stage['total_units']
            previous_m=stage['M']
    index={(s['case'],s['policy']):s for s in rows}
    comparisons=[]
    for case in r.c.CASES:
        if (case,'atlas') not in index: continue
        a=index[case,'atlas']
        for baseline in ('fixed','stagnation'):
            if (case,baseline) not in index: continue
            b=index[case,baseline]
            common=min(a['units'],b['units'])
            common_states={}
            for policy in ('atlas',baseline):
                eligible=[s for s in trajectories[case,policy] if s['total_units']<=common]
                common_states[policy]=None if not eligible else dict(
                    units=eligible[-1]['total_units'],score=eligible[-1]['score'])
            comparisons.append(dict(case=case,baseline=baseline,
                rms_ratio=max(a['score']['rms_mm'],.01)/max(b['score']['rms_mm'],.01),
                hausdorff_ratio=max(a['score']['hausdorff_mm'],.01)/max(b['score']['hausdorff_mm'],.01),
                work_ratio=a['units']/b['units'],atlas_audit=a['audit_passed'],
                common_work_allowance=common,common_work_states=common_states,
                additional_failure=a['outcome']!='COMPLETED_SCHEDULE' and b['outcome']=='COMPLETED_SCHEDULE'))
        if all((case,policy) in initial_curves for policy in r.POLICIES):
            checks.append(dict(case=case,check='identical_policy_starts',passed=all(
                initial_curves[case,policy]==initial_curves[case,'fixed'] for policy in r.POLICIES)))
    terminal=set(index)|{(s['case'],s['policy']) for s in failures}
    pending=[dict(case=case,policy=policy) for case in r.c.CASES for policy in r.POLICIES
             if (case,policy) not in terminal]
    aggregate={}
    for baseline in ('fixed','stagnation'):
        subset=[s for s in comparisons if s['baseline']==baseline]
        if subset:
            gm=float(np.exp(np.mean(np.log([s['rms_ratio'] for s in subset]))))
            worst=max(max(s['rms_ratio'],s['hausdorff_ratio']) for s in subset)
            additional=sum(s['additional_failure'] for s in subset)
            aggregate[baseline]=dict(cases=len(subset),rms_gm_ratio=gm,
                worst_geometry_ratio=worst,additional_failures=additional,
                gate_passed=len(subset)==6 and gm<=.8 and worst<=1.25 and not additional
                and all(s['atlas_audit'] for s in subset))
            common_ratios=[max(s['common_work_states']['atlas']['score']['rms_mm'],.01)/
                           max(s['common_work_states'][baseline]['score']['rms_mm'],.01)
                           for s in subset if all(s['common_work_states'].values())]
            aggregate[baseline]['common_work_rms_gm_ratio']=float(np.exp(np.mean(np.log(common_ratios)))) if common_ratios else None
    diagnostic_failure_units=sum(sum(d['diagnostic_units'] for d in f.get('decisions',[])) for f in failures)
    r.c.write(HERE/'analysis.json',dict(rows=rows,blocks=blocks,comparisons=comparisons,aggregate=aggregate,
        failures=failures,pending=pending,terminal=len(terminal),planned=18,
        recorded_failure_units=sum(f.get('total_units',0) for f in failures),
        diagnostic_failure_units=diagnostic_failure_units,
        superior_rule_gate_passed=len(aggregate)==2 and all(s['gate_passed'] for s in aggregate.values()),
        checks=checks,checks_passed=all(x['passed'] for x in checks),complete=len(terminal)==18))
    lines=['# SC-043 — prospective band decisions','',
           f'{len(terminal)}/18 terminal paths; {len(failures)} exceptions; {len(pending)} pending.','',
           '| Case | Rule | Bands | RMS mm | Hausdorff mm | Work (diagnostic) | Outcome | Audit |',
           '|---|---|---|---:|---:|---:|---|---|']
    for s in rows:
        lines.append(f"| {s['case']} | {s['policy']} | {s['bands']} | {s['score']['rms_mm']:.5g} | {s['score']['hausdorff_mm']:.5g} | {s['units']} ({s['diagnostic_units']}) | {s['outcome']} | {s['audit_passed']} |")
    for s in failures:
        diagnostic=sum(d['diagnostic_units'] for d in s.get('decisions',[]))
        lines.append(f"| {s['case']} | {s['policy']} | — | — | — | {s.get('total_units',0)} ({diagnostic}) | EXCEPTION | False |")
    lines+=['',f"Evidence checks: {sum(x['passed'] for x in checks)}/{len(checks)}.",'']
    lines+=['Exceptions remain in the 18-path denominator. An unqualified diagnostic blocks that policy; it is not a missing successful replicate.',
            'Reported geometric means use available scored pairs. The superiority gate requires all six cases against both controls.',
            'Supplementary common-work comparisons use the last accepted state affordable at the smaller actual path cost, with diagnostics charged. '
            'These checkpoints passed fitting acceptance but do not receive new endpoint audits. They do not replace the frozen terminal-state gate.', '']
    lines+=['## Decisions and subsequent fitting','',
            '| Case | Rule | Block | Choice | Extra predicted gain / loss | Fitting loss decrease | Diagnostic / fitting work | Stop |',
            '|---|---|---:|---|---:|---:|---:|---|']
    for s in blocks:
        gain=s['incremental_predicted_fraction']
        predicted='—' if gain is None else f'{gain:.3%}'
        lines.append(f"| {s['case']} | {s['policy']} | {s['block']} | {s['low']}→{s['selected']} | {predicted} | {s['actual_fractional_decrease']:.3%} | {s['diagnostic_units']} / {s['fit_units']} | {s['stop']} |")
    lines+=['', 'The forecast compares two optimal linearized directions at the declared test radius. '
            'The subsequent fit runs multiple damped LM steps, so its total decrease is not a calibration test of that single forecast. '
            'A retained band followed by poor improvement is evidence about this decision rule, not proof that all higher modes are unobservable.', '']
    (HERE/'TABLES.md').write_text('\n'.join(lines))
    print({'completed':len(rows),'aggregate':aggregate,'checks_passed':all(x['passed'] for x in checks)})


if __name__=='__main__':main()
