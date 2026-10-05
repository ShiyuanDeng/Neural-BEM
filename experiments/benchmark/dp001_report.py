"""Read-only DP-001 receipt analysis; no geometry replay or numerical solve."""
from collections import Counter
import numpy as np
from bem_inverse.io import read, write, digest
from . import dp001 as d


def summarize():
    d.verify()
    value=d.report()
    if len(value['paired']) != 30:
        raise ValueError('A final comparison requires all 30 pairs')
    arms={}
    for arm in ('E','F'):
        rows=value[arm]
        paths={k:d.c.ROOT/r['result'] for k,r in rows.items()}
        raw={k:read(p) for k,p in paths.items()}
        history=[]
        for k,r in raw.items():
            for stage in r.get('stages',[]):
                history.extend(read(paths[k].parent/(stage['stage']+'.json'))['history'])
        succeeded=[k for k,r in rows.items() if r['recovered']]
        failed=[k for k,r in rows.items() if not r['recovered']]
        phases={}
        if arm=='F':
            for key in ('initial_audit','fit_and_localization','early_audits','terminal_audits'):
                phases[key]=sum(r['exclusive_wall_seconds'][key] for r in rows.values())
            phases['remaining_setup_and_output']=value['summed_output_seconds'][arm]-sum(phases.values())
        arms[arm]=dict(recovered=len(succeeded), failed_cases=failed,
            successful_output_seconds=sum(rows[k]['audited_output_seconds'] for k in succeeded),
            failed_output_seconds=sum(rows[k]['audited_output_seconds'] for k in failed),
            all_output_seconds=value['summed_output_seconds'][arm],
            exclusive_wall_seconds=phases,
            minimum_recorded_damping=min(r['damping'] for r in history),
            maximum_recovered_rms_mm=max(rows[k]['metrics']['rms_mm'] for k in succeeded),
            maximum_recovered_hausdorff_upper_mm=max(rows[k]['metrics']['hausdorff_upper_mm'] for k in succeeded),
            maximum_recovered_residual=max(rows[k]['maximum_residual'] for k in succeeded),
            geometry_proposals=sum(r['geometry_proposals'] for r in rows.values()),
            geometry_refusals=sum(r['geometry_refusals'] for r in rows.values()),
            geometry_refusal_seconds=sum(r['geometry_refusal_seconds'] for r in rows.values()),
            all_outcomes=dict(Counter(r['outcome'] for r in rows.values())),
            physics_exception_count=sum(len(r['physics_failures']) for r in rows.values()),
            failed_details={k:dict(detail=raw[k].get('detail'), metrics=rows[k]['metrics'],
                maximum_residual=rows[k]['maximum_residual'], output_seconds=rows[k]['audited_output_seconds']) for k in failed})
    speeds=list(value['paired_success_speedups'].values())
    final=dict(experiment='DP-001', complete=True, arms=arms,
        recovery_regressions=value['recovery_regressions'], new_recoveries=value['new_recoveries'],
        median_success_speedup=value['median_success_speedup'], p10_success_speedup=float(np.percentile(speeds,10)),
        successful_cases_faster=sum(s>1 for s in speeds), common_successes=len(speeds),
        summed_output_reduction_fraction=1-arms['F']['all_output_seconds']/arms['E']['all_output_seconds'],
        paired_success_speedups=value['paired_success_speedups'],
        result_sha256={arm:{k:digest(d.c.ROOT/r['result']) for k,r in value[arm].items()} for arm in ('E','F')},
        postprocessing_source_sha256=digest(__file__),
        classification=('recovery regression; do not promote' if value['recovery_regressions'] else
                        'recovery retained; speed comparison is one execution per pair'),
        caveats=['Summed case times are not elapsed campaign time.',
                 'Nested geometry/physics timers overlap frequency threads and audits.',
                 'No new recovery or GGB case-8 competitiveness is demonstrated.'])
    write(d.OUTPUT/'final_comparison.json',final)
    lines=['# DP-001: damping feedback and repeated-work repairs', '',
        'Approved and completed 2026-10-05. [Pre-registration](DP-001_plan.md), '
        '[implementation and validation](DP-001_implementation.md), '
        '[complete receipts](../../../results/validation/cleaned_interfaces/DP-001/final_comparison.json).', '',
        f"E recovered **{arms['E']['recovered']}/30** and F recovered **{arms['F']['recovered']}/30** TG-002 cases. "
        f"There were {len(final['recovery_regressions'])} recovery regressions and "
        f"{len(final['new_recoveries'])} new recoveries. Median paired successful-output "
        f"speedup was **{final['median_success_speedup']:.3f}×** "
        f"(p10 {final['p10_success_speedup']:.3f}×; {final['successful_cases_faster']}/{len(speeds)} faster).", '',
        '| Audited output boundary | Frozen E | Fixed F |', '|---|---:|---:|']
    for label,key in [('Recovered cases, summed seconds','successful_output_seconds'),
                      ('Failed cases, summed seconds','failed_output_seconds'),
                      ('All cases, summed seconds','all_output_seconds'),
                      ('Largest recovered RMS, mm','maximum_recovered_rms_mm'),
                      ('Largest recovered Hausdorff upper bound, mm','maximum_recovered_hausdorff_upper_mm'),
                      ('Largest recovered per-frequency residual','maximum_recovered_residual'),
                      ('Minimum recorded damping','minimum_recorded_damping')]:
        lines.append(f"| {label} | {arms['E'][key]:.6g} | {arms['F'][key]:.6g} |")
    lines.extend(['', f"The summed output boundary fell by {100*final['summed_output_reduction_fraction']:.1f}%. "
        'These are sums of single-case measurements, not campaign elapsed time. '
        'Truth scoring is outside this boundary; interpreter import overhead is outside both arms, '
        'while initial CUDA startup and all numerical audits are included. The experiment used '
        'one worker, four frequency threads and single-thread BLAS. No warm-up was excluded.', '',
        '## Failures and controller evidence', '',
        'Failed cases and outcomes are retained in the complete comparison. The four screen '
        'failures stop at the unchanged numerical-resolution gate. The damping floor prevents '
        'the tiny schedule values, but it does not establish a resolution response or solve '
        'the difficult inverse cases. Aphex 13.3 advances farther with F; its error remains '
        'above the recovery gates, and its failed-run time increases.', '',
        '| Failed case | E RMS mm / output s | F RMS mm / output s |', '|---|---:|---:|'])
    for case in arms['E']['failed_cases']:
        e,f=arms['E']['failed_details'][case],arms['F']['failed_details'].get(case)
        if f is not None:
            lines.append(f"| {case} | {e['metrics']['rms_mm']:.4f} / {e['output_seconds']:.2f} | "
                         f"{f['metrics']['rms_mm']:.4f} / {f['output_seconds']:.2f} |")
    lines.extend(['', '## Accounting and limits', '',
        'F records the following disjoint wall components. Remaining setup/output is the '
        'difference from the measured audited-output boundary. Geometry and physics '
        'cumulative timers are nested and must not be added to this table.', '',
        '| F wall component | Summed seconds |', '|---|---:|'])
    for key,seconds in arms['F']['exclusive_wall_seconds'].items():
        lines.append(f'| {key} | {seconds:.3f} |')
    lines.extend(['', 'This comparison qualifies the combined repairs; it does not isolate '
        'each cache, audit batch or damping change. Single executions do not establish '
        'timing confidence intervals or identical endpoint shape accuracy. All 30 pairs '
        'use the unchanged declared gates. Source/input/import checks and per-batch validation '
        'receipts passed. Earlier seals and source archives were preserved.', '',
        'The agreement controller and audit batching remain explicit options; legacy '
        'defaults are unchanged. The report\'s next numerical research priority is '
        'accuracy-selected modal resolution with bounded promotion, followed by adaptive '
        'refinement qualification. Rigid translation remains conditional. Neither was '
        'silently included in this experiment; no far-start or case-8 rerun occurred.'])
    (d.c.ROOT/'docs/iterations/CI-SPD/DP-001_results.md').write_text('\n'.join(lines)+'\n')
    return final


if __name__=='__main__':
    value=summarize()
    print(value['classification'], value['median_success_speedup'])
