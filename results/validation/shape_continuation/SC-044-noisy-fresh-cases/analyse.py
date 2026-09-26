"""Rebuild fresh-case outcomes without loading truth into any fitting decision."""
import importlib.util
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc044_analysis',HERE/'run.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    r.verify()
    rows=[]
    checks=[]
    noise_diagnostics=[]
    for case in r.CASES:
        clean=r.c.sc.read(HERE/'inputs'/case/'clean.json')
        clean=np.array(clean['observed_real'])+1j*np.array(clean['observed_imag'])
        for profile in r.PROFILES:
            if profile=='clean':continue
            data=r.c.sc.read(HERE/'inputs'/case/f'{profile}.json')
            observed=np.array(data['observed_real'])+1j*np.array(data['observed_imag'])
            sigma=np.array(data['sigma_real_imag'])
            raw=(np.linalg.norm(observed,axis=0)/sigma)**2
            expected=observed.size/raw.sum()
            truth_loss=.5*np.sum(abs((observed-clean)/sigma)**2)/raw.sum()
            noise_diagnostics.append(dict(case=case,profile=profile,expected_loss=float(expected),
                truth_noise_loss=float(truth_loss),actual_over_expected=float(truth_loss/expected),
                truth_loss_over_discrepancy=float(truth_loss/(1.1**2*expected))))
    prefixes={}
    failures=[dict(path=str(p.relative_to(HERE)),**r.c.sc.read(p)) for p in sorted((HERE/'runs').glob('*/*/*/failure.json'))]
    for p in sorted((HERE/'runs').glob('*/*/prefix/result.json')):
        d=r.c.sc.read(p)
        prefixes[d['case'],d['profile']]=d
    for p in sorted((HERE/'runs').glob('*/*/*/result.json')):
        d=r.c.sc.read(p)
        if d['arm']=='prefix':continue
        prefix=prefixes.get((d['case'],d['profile']))
        if prefix is None:
            prefix=next((f for f in failures if f['case']==d['case'] and f['profile']==d['profile'] and f['arm']=='prefix'),{'total_units':0})
        last=d.get('stages',[{}])[-1]
        audit=r.c.sc.read(p.parent/'audit.json') if (p.parent/'audit.json').exists() else {}
        audit_reason=None if audit.get('passed') else 'wall_limit' if 'TrialWallLimit' in audit.get('traceback','') else 'exception' if audit.get('traceback') else 'tolerance_disagreement' if audit else 'not_attempted'
        row=dict(case=d['case'],profile=d['profile'],arm=d['arm'],outcome=d['outcome'],score=d.get('score'),
            suffix_units=d['total_units'],prefix_units=prefix['total_units'],
            complete_path_units=prefix['total_units']+d['total_units'],audit_passed=d.get('audit_passed',False),audit_failure_kind=audit_reason,
            loss=last.get('final_loss'),discrepancy_target=last.get('discrepancy_target'))
        rows.append(row)
        if 'stages' in d:
            states=r.c.sc.read(p.parent/'accepted.json')['states']
            config=r.c.sc.read(p.parent/'configuration.json')
            checks.append(dict(case=d['case'],profile=d['profile'],arm=d['arm'],check='last_accepted_state',
                passed=bool(states and states[-1]['curve']==d['curve'])))
            checks.append(dict(case=d['case'],profile=d['profile'],arm=d['arm'],check='shared_prefix_state',
                passed=config['initial']==prefix['curve']))
            for label in dict.fromkeys(s['stage'] for s in states):
                losses=[s['loss'] for s in states if s['stage']==label]
                checks.append(dict(case=d['case'],profile=d['profile'],arm=d['arm'],stage=label,
                    check='within_stage_descent',passed=all(b<=a for a,b in zip(losses,losses[1:]))))
            checks.append(dict(case=d['case'],profile=d['profile'],arm=d['arm'],check='work',passed=bool(
                d['total_units']==sum(s['units'] for s in d['stages']) and all(s['units']<=380 for s in d['stages']))))
            if d['outcome']=='DISCREPANCY_REACHED':
                checks.append(dict(case=d['case'],profile=d['profile'],arm=d['arm'],check='discrepancy',
                                   passed=last['final_loss']<=last['discrepancy_target']))
    index={(s['case'],s['profile'],s['arm']):s for s in rows}
    comparisons=[]
    for case in r.CASES:
        for profile in r.PROFILES:
            baseline=index.get((case,profile,'none'))
            if baseline is None:continue
            for arm in ('boundary','cap'):
                candidate=index.get((case,profile,arm))
                if candidate is None:continue
                valid=bool(baseline['score'] and candidate['score'])
                common=None
                if valid:
                    ceiling=min(baseline['suffix_units'],candidate['suffix_units'])
                    endpoints=[]
                    for label in ('none',arm):
                        states=r.c.sc.read(HERE/'runs'/case/profile/label/'accepted.json')['states']
                        eligible=[s for s in states if s['total_units']<=ceiling]
                        if not eligible:break
                        state=eligible[-1]
                        endpoints.append(dict(arm=label,accepted_at_suffix_units=state['total_units'],
                            score=r.score(case,r.c.ast.curve_from(state['curve']))))
                    if len(endpoints)==2:
                        a,b=[s['score'] for s in endpoints]
                        common=dict(suffix_ceiling=ceiling,complete_path_ceiling=ceiling+baseline['prefix_units'],
                            endpoints=endpoints,rms_ratio=max(b['rms_mm'],.01)/max(a['rms_mm'],.01),
                            hausdorff_ratio=max(b['hausdorff_mm'],.01)/max(a['hausdorff_mm'],.01))
                comparisons.append(dict(case=case,profile=profile,arm=arm,comparable=valid,
                    common_work=common,
                    rms_ratio=max(candidate['score']['rms_mm'],.01)/max(baseline['score']['rms_mm'],.01) if valid else None,
                    hausdorff_ratio=max(candidate['score']['hausdorff_mm'],.01)/max(baseline['score']['hausdorff_mm'],.01) if valid else None,
                    baseline_outcome=baseline['outcome'],candidate_outcome=candidate['outcome'],candidate_audit=candidate['audit_passed']))
    aggregate={}
    successful=('COMPLETED_SCHEDULE','DISCREPANCY_REACHED','LOSS_TOLERANCE_REACHED')
    for arm in ('boundary','cap'):
        selected=[s for s in comparisons if s['arm']==arm and s['comparable']]
        if selected:
            gm=float(np.exp(np.mean(np.log([s['rms_ratio'] for s in selected]))))
            worst=max(max(s['rms_ratio'],s['hausdorff_ratio']) for s in selected)
            extra=sum(s['candidate_outcome'] not in successful and s['baseline_outcome'] in successful for s in selected)
            common=[s['common_work']['rms_ratio'] for s in selected if s['common_work'] is not None]
            aggregate[arm]=dict(datasets=len(selected),distinct_shapes=len({s['case'] for s in selected}),
                rms_gm_ratio=gm,worst_geometry_ratio=worst,additional_failures=extra,
                common_work_rms_gm_ratio=float(np.exp(np.mean(np.log(common)))) if common else None,
                transfer_gate_passed=len(selected)==6 and gm<1 and worst<=1.25 and not extra
                and all(s['candidate_audit'] for s in selected))
    unique_prefix=sum(d['total_units'] for d in prefixes.values())+sum(f['total_units'] for f in failures if f['arm']=='prefix')
    suffix=sum(s['suffix_units'] for s in rows)
    terminal=set(index)|{(f['case'],f['profile'],f['arm']) for f in failures if f['arm']!='prefix'}
    pending=[dict(case=case,profile=profile,arm=arm) for case in r.CASES for profile in r.PROFILES for arm in r.ARMS
             if (case,profile,arm) not in terminal]
    r.c.write(HERE/'analysis.json',dict(rows=rows,noise_diagnostics=noise_diagnostics,
        prefixes=list(prefixes.values()),comparisons=comparisons,aggregate=aggregate,failures=failures,
        pending=pending,terminal=len(terminal),planned=18,
        unique_prefix_units=unique_prefix,suffix_units=suffix,checks=checks,checks_passed=all(s['passed'] for s in checks),
        complete=len(terminal)==18))
    lines=['# SC-044 — fresh shapes and measurement noise','',
           f'{len(terminal)}/18 terminal suffix paths; {len(failures)} prefix/suffix exceptions; {len(pending)} pending.','',
           '| Shape | Data | State strategy | RMS mm | Hausdorff mm | Complete path work | Outcome | Audit |',
           '|---|---|---|---:|---:|---:|---|---|']
    for s in rows:
        scores=s['score']
        rms='—' if not scores else f"{scores['rms_mm']:.5g}"
        hd='—' if not scores else f"{scores['hausdorff_mm']:.5g}"
        lines.append(f"| {s['case']} | {s['profile']} | {s['arm']} | {rms} | {hd} | {s['complete_path_units']} | {s['outcome']} | {s['audit_passed']} |")
    for s in failures:
        lines.append(f"| {s['case']} | {s['profile']} | {s['arm']} | — | — | — | EXCEPTION | False |")
    lines+=['',f'Unique prefix work: {unique_prefix}; suffix work: {suffix}.',
            f"Saved-evidence checks: {sum(s['passed'] for s in checks)}/{len(checks)}.",
            'Each complete path is charged its shared prefix. Two noise draws are repeated measurements of the same two shapes, not additional independent targets.','',
            'The JSON also reports the last accepted states within a common work allowance for each paired comparison. '
            'This post-fit analysis does not select the best truth iterate or change the original endpoint gate. '
            'Intermediate common-work states have the original fitting acceptance checks, not a new endpoint audit.','',
            'Post-fit observation check: the two realized noise losses are '
            +', '.join(f"{s['actual_over_expected']:.4f}× expected ({s['truth_loss_over_discrepancy']:.4f}× the discrepancy threshold)"
                       for s in noise_diagnostics if s['case']==r.CASES[0])
            +'. These ratios match across shapes because standardized draws are shared. '
            'Both truths lie inside the declared discrepancy; these truth residuals never choose the fitting stop.','']
    (HERE/'TABLES.md').write_text('\n'.join(lines))
    print({'completed':len(rows),'failures':len(failures),'unique_prefix_units':unique_prefix,'suffix_units':suffix})


if __name__=='__main__':main()
