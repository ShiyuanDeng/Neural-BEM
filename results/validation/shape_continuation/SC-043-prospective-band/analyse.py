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
    checks=[]
    failures=[dict(path=str(p.relative_to(HERE)),**r.c.sc.read(p))
              for p in sorted((HERE/'runs').glob('*/*/failure.json'))]
    for p in sorted((HERE/'runs').glob('*/*/result.json')):
        d=r.c.sc.read(p)
        decisions=r.c.sc.read(p.parent/'decisions.json')['rows']
        rows.append(dict(case=d['case'],policy=d['policy'],outcome=d['outcome'],score=d['score'],
            units=d['total_units'],diagnostic_units=sum(s['diagnostic_units'] for s in d['stages']),
            audit_passed=d['audit_passed'],bands=[s['M'] for s in d['stages']],loss=d['stages'][-1]['final_loss']))
        checks.append(dict(case=d['case'],policy=d['policy'],check='charged_diagnostics',passed=bool(
            d['total_units']==sum(s['units']+s['diagnostic_units'] for s in d['stages'])
            and all(s['units']+s['diagnostic_units']<=r.QUOTA for s in d['stages']))))
        for choice,stage in zip(decisions,d['stages']):
            valid=stage['M']==choice['selected']
            if d['policy']=='atlas':
                low,high=choice['low_prediction'],choice['high_prediction']
                valid &= choice['release']==r.choose(low['predicted_decrease'],high['predicted_decrease'],low['initial_loss'])
                valid &= high['predicted_decrease']>=low['predicted_decrease']-1e-12*max(low['initial_loss'],1e-20)
            checks.append(dict(case=d['case'],policy=d['policy'],block=stage['block'],check='frozen_decision',passed=bool(valid)))
    index={(s['case'],s['policy']):s for s in rows}
    comparisons=[]
    for case in r.c.CASES:
        if (case,'atlas') not in index: continue
        a=index[case,'atlas']
        for baseline in ('fixed','stagnation'):
            if (case,baseline) not in index: continue
            b=index[case,baseline]
            comparisons.append(dict(case=case,baseline=baseline,
                rms_ratio=max(a['score']['rms_mm'],.01)/max(b['score']['rms_mm'],.01),
                hausdorff_ratio=max(a['score']['hausdorff_mm'],.01)/max(b['score']['hausdorff_mm'],.01),
                work_ratio=a['units']/b['units'],atlas_audit=a['audit_passed'],
                additional_failure=a['outcome']!='COMPLETED_SCHEDULE' and b['outcome']=='COMPLETED_SCHEDULE'))
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
    diagnostic_failure_units=sum(sum(d['diagnostic_units'] for d in f.get('decisions',[])) for f in failures)
    r.c.write(HERE/'analysis.json',dict(rows=rows,comparisons=comparisons,aggregate=aggregate,
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
            'Reported geometric means use available scored pairs. The superiority gate requires all six cases against both controls.', '']
    (HERE/'TABLES.md').write_text('\n'.join(lines))
    print({'completed':len(rows),'aggregate':aggregate,'checks_passed':all(x['passed'] for x in checks)})


if __name__=='__main__':main()
