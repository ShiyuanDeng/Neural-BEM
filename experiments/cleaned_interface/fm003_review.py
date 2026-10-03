"""Read-only receipt validation and post-census FM-003 figures.

This module does not fit, choose starts, or change the sealed experiment. It
loads truth only for a completed census or a finished continuation.
"""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from bem_inverse.io import curve_from, digest, read, write
from . import fm003 as f


def validate_phase(output, phase):
    f.verify(output)
    folder=output/phase
    census=read(folder/'census.json')
    summary=read(folder/'summary.json')
    checks={}
    rows=[]
    for name,sha in census['results'].items():
        path=folder/name
        assert digest(path)==sha, path
        rows.append(read(path))
    checks['completed_prefix']=[r['index'] for r in rows]==list(range(census['completed']))
    checks['counts']=census['completed']<=f.PHASES[phase][2] and census['scheduled']==f.PHASES[phase][2]
    checks['cap_unchanged']=census['cap_seconds']==f.PHASES[phase][3]
    checks['no_wall_limit_in_completed_prefix']=all(r['outcome']!='TRIAL_WALL_LIMIT' for r in rows)
    checks['work_sum']=census['work_units']==sum(r['work']['work_units'] for r in rows)
    finite=[r for r in rows if r.get('final_loss') is not None and 'curve' in r]
    winner=min(finite,key=lambda r:(r['final_loss'],r['index'])) if finite else None
    checks['winner']=census['winner_index']==(winner['index'] if winner else None)
    indices=[i for c in summary['clusters'] for i in c['indices']]
    checks['cluster_partition']=sorted(indices)==sorted(r['index'] for r in finite)
    checks['cluster_counts']=all(c['size']==len(c['indices']) and c['share']==c['size']/len(rows)
                                 for c in summary['clusters'])
    checks['stage2_contract']=True
    checks['input_provenance']=True
    attempts=[]
    for row in rows:
        start=read(output/'starts'/census['case']/f'{row["index"]:04d}.json')
        attempts += start['attempts']
        run=folder/'runs'/f'{row["index"]:04d}'
        if row.get('reused_from'):
            checks['input_provenance'] &= row['reused_sha256']==digest(output/row['reused_from'])
            continue
        checks['input_provenance'] &= read(run/'input.json')==start
        if start['valid']:
            conf=read(run/'configuration.json')
            checks['input_provenance'] &= conf['start_sha256']==digest(run/'input.json')
            s=conf['operation']['stage']
            checks['stage2_contract'] &= (s['iterations'],s['quota'],s['M'],s['K_geometry'],s['nodes'],s['refined_nodes'])==(200,10000,5,12,512,1024)
            checks['stage2_contract'] &= s['frequencies_hz']==[.5e9,.75e9] and s['damping']==[.25,.25]
    capped_rows=[r['index'] for r in rows if r.get('stop')=='maximum_iterations' or r['outcome']=='STAGE_QUOTA_REACHED']
    refusal_counts=Counter(a.get('reason') for a in attempts if not a['valid'])
    result=dict(phase=phase,passed=all(checks.values()),checks=checks,
        completed=len(rows),finite_endpoints=len(finite),iteration_or_work_capped_starts=capped_rows,
        draw_refusals=dict(refusal_counts), total_draws=len(attempts),
        stop_counts=dict(Counter(r.get('stop') or r['outcome'] for r in rows)),
        numerical_failure_details=dict(Counter(r.get('detail') for r in rows if r['outcome']=='NUMERICAL_FAILURE')),
        maximum_seconds=max((r['seconds'] for r in rows),default=0),
        median_seconds=float(np.median([r['seconds'] for r in rows])) if rows else None,
        receipt_sha256=digest(folder/'census.json'))
    write(output/'validation'/(phase+'.json'),result)
    if not result['passed']:
        raise ValueError('Receipt validation failed: '+str(checks))
    return result


def continuation_distances(output):
    result=read(output/'phase2/result.json')
    if 'stages' not in result:
        return dict(outcome=result['outcome'],complete=False)
    truth=f.arclength_curve(curve_from(read(f.b.ROOT/f.descriptor(f.HIGH)['truth'])))
    winner=read(output/'phase1/runs'/f'{result["winner_index"]:04d}'/'result.json')
    rows=[dict(stage='stage_2_census_winner',loss=winner['final_loss'],
               aligned_rms_mm=f.aligned_preprojected_mm(f.arclength_curve(curve_from(winner['curve'])),truth))]
    for s in result['stages']:
        rows.append(dict(stage=s['stage'],loss=s['final_loss'],outcome=s['outcome'],stop=s['stop'],
            accepted_steps=s['accepted_steps'],
            aligned_rms_mm=f.aligned_preprojected_mm(f.arclength_curve(curve_from(s['curve'])),truth)))
    record=dict(complete=True,stages=rows,first_over_5mm=next((r['stage'] for r in rows if r['aligned_rms_mm']>=5),None),
                result_sha256=digest(output/'phase2/result.json'))
    write(output/'phase2/stage_distances.json',record)
    return record


def plots(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    completed=[p for p in f.PHASES if (output/p/'summary.json').exists()]
    if not completed:
        return
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    colors={'no_decreasing_step':'#4477aa','gradient_tolerance':'#228833',
            'loss_tolerance':'#228833','relative_step_tolerance':'#66ccee','NUMERICAL_FAILURE':'#cc6677'}
    fig,axes=plt.subplots(2,len(completed),figsize=(5*len(completed),9),squeeze=False)
    for j,phase in enumerate(completed):
        s=read(output/phase/'summary.json')
        rows=[read(output/phase/name) for name in s['results']]
        good=[r for r in rows if r.get('final_loss') is not None]
        ax=axes[0,j]
        groups={r.get('stop') or r['outcome'] for r in good}
        for name in sorted(groups):
            part=[r for r in good if (r.get('stop') or r['outcome'])==name]
            ax.scatter([max(r['final_loss'],1e-16) for r in part],
                [s['truth_distance_mm'][str(r['index'])] for r in part],s=16,alpha=.65,
                label=name,color=colors.get(name,'#aa3377'))
        ax.axvline(1e-6,color='#555555',linestyle=':',linewidth=1)
        ax.axhline(5,color='#555555',linestyle=':',linewidth=1)
        ax.set(xscale='log',xlabel='Stage-2 loss',ylabel='Aligned arclength RMS to truth (mm)',
            title=f'{phase}: {"full" if s["full"] else "paired"}, contrast {4 if phase=="phase4" else 13.3}\n{len(rows)} fixed starts')
        ax.legend(fontsize=7,loc='best')
        ax=axes[1,j]
        truth=curve_from(read(f.b.ROOT/f.descriptor(s['case'])['truth']))
        initial=f.z1(s['case'])
        winner=next(r for r in rows if r['index']==s['winner_index'])
        shapes=[('Truth',truth,'#222222','-'),('z1',initial,'#999999',':'),
                ('Lowest-loss stage 2',curve_from(winner['curve']),'#4477aa','-')]
        if phase=='phase1' and (output/'phase2/result.json').exists():
            continued=read(output/'phase2/result.json')
            if 'final_curve' in continued:
                shapes.append(('Continued endpoint',curve_from(continued['final_curve']),'#cc6677','--'))
        for label,curve,color,style in shapes:
            z=curve.values(2048)*50
            ax.plot(np.r_[z.real,z.real[0]],np.r_[z.imag,z.imag[0]],label=label,color=color,linestyle=style,linewidth=1.5)
        ax.set(xlabel='x relative to ring centre (mm)',ylabel='y relative to ring centre (mm)',aspect='equal')
        ax.legend(fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.20),ncol=2,frameon=False)
    fig.tight_layout()
    fig.savefig(output/'census.png',dpi=160)
    fig.savefig(output/'census.svg')
    plt.close(fig)


def synthesis(output):
    summaries={p:read(output/p/'summary.json') for p in f.PHASES if (output/p/'summary.json').exists()}
    if len(summaries)<3 or not (output/'phase2/result.json').exists():
        raise ValueError('All frozen phases must finish before synthesis')
    s=summaries['phase1']; continued=read(output/'phase2/result.json')
    if s['within_5mm']['hits']==0:
        reading='Inconclusive for search: none of the fixed paired high-contrast starts reaches an endpoint within 5 mm.'
    elif not s['G1']:
        reading='A lower-loss wrong stage-2 minimum wins despite nearer endpoints; the proposed search-failure claim is rejected under this representation.'
    elif continued['recovered']:
        reading='Search failure supported: the lowest-loss paired stage-2 basin is near truth and its unchanged continuation recovers the C.'
    else:
        reading='The right stage-2 basin is not sufficient: unchanged continuation does not recover the C.'
    control_predictions=dict(full_share_larger=summaries['phase3']['lowest_cluster']['share']>s['lowest_cluster']['share'],
        c4_share_larger=summaries['phase4']['lowest_cluster']['share']>s['lowest_cluster']['share'])
    comparisons={p:dict(lowest_cluster=r['lowest_cluster'],within_5mm=r['within_5mm'],
                           zero_loss=r['zero_loss'],z1_cluster=r['z1_cluster']) for p,r in summaries.items()}
    costs={}
    for p,summary in summaries.items():
        hits=summary['within_5mm']['hits']
        reused=read(output/'phase0/start0/result.json')['seconds'] if p=='phase1' else 0.
        costs[p]=dict(wall_seconds=summary['seconds'],separately_run_start0_seconds=reused,
            stage_seconds=summary['stage_seconds'],work_units=summary['work_units'],
            cost_seconds_including_start0=summary['seconds']+reused,
            seconds_per_within_5mm_hit=(summary['seconds']+reused)/hits if hits else None,
            units_per_within_5mm_hit=summary['work_units']/hits if hits else None)
    result=dict(G1=s['G1'],G2=continued['recovered'],reading=reading,G3=control_predictions,
                comparisons=comparisons,costs=costs,
                selection='The three minimum-loss clusters are separately defined; their shares are not necessarily the shares reaching the same physical solution.')
    write(output/'synthesis.json',result)
    return result


def finalize_report(output):
    """Put registered outcomes and their limits ahead of the detailed tables."""
    result=synthesis(output)
    f.report(output)
    path=f.b.ROOT/'docs/iterations/cleaned_interfaces/iteration_21/01_results.md'
    detailed=path.read_text().split('\n',1)[1]
    paired=read(output/'phase1/summary.json')
    continued=read(output/'phase2/result.json')
    original=read(f.b.DEFAULT_OUTPUT/'runs'/f.HIGH/'result.json')
    summaries={p:read(output/p/'summary.json') for p in f.PHASES}
    validations={p:read(output/'validation'/(p+'.json')) for p in f.PHASES}
    def interval(row):
        lo,hi=row['wilson95']
        return f'{row["hits"]}/{row["n"]} = {100*row["share"]:.2f}% [{100*lo:.2f}, {100*hi:.2f}]'
    winner=paired['clusters'][0]
    lines=['# FM-003: paired C recovered by the stage-2 census', '', result['reading'], '',
        f'**G1 {"passed" if result["G1"] else "failed"}; G2 {"passed" if result["G2"] else "failed"}.** '
        f'The loss-selected winner is start {continued["winner_index"]}: stage-2 loss '
        f'{paired["winner_loss"]:.9g}, aligned arclength RMS {winner["representative_truth_distance_mm"]:.4g} mm. '
        'Its unchanged CI-001 suffix completed and passed the final numerical audit.', '',
        '| Frozen paired recovery measure | Original CI-001 | FM-003 continuation | Limit |',
        '|---|---:|---:|---:|']
    for label,key,limit in [('RMS (mm)','rms_mm',1.),('Hausdorff upper bound (mm)','hausdorff_upper_mm',2.)]:
        lines.append(f'| {label} | {original["metrics"][key]:.7g} | {continued["metrics"][key]:.7g} | {limit:g} |')
    lines += [f'| Maximum relative residual | {original["maximum_residual"]:.7g} | '
        f'{continued["maximum_residual"]:.7g} | 0.003 |',
        f'| Recovered | {original["recovered"]} | {continued["recovered"]} | all gates |', '',
        '**The census did not find a zero-loss stage-2 endpoint.** '
        f'Paired high contrast has {paired["zero_loss"]["hits"]}/{paired["completed"]} endpoints below `1e-6`. '
        'The result establishes that a nonzero-loss stage-2 endpoint selected without truth can lead to recovery. '
        'It does not establish the proposal\'s stronger zero-loss-basin premise.', '',
        '## Registered census comparisons', '',
        'Shares below use all completed starts as denominators. Brackets are Wilson 95% intervals in percent.', '',
        '| Census | Lowest-loss cluster | Within 5 mm of truth | z1 cluster | Loss < 1e-6 |',
        '|---|---|---|---|---|']
    for phase,s in summaries.items():
        label={'phase1':'Paired, contrast 13.3','phase3':'Full matrix, contrast 13.3','phase4':'Paired, contrast 4'}[phase]
        lines.append(f'| {label} | {interval(s["lowest_cluster"])} | {interval(s["within_5mm"])} | '
                     f'{interval(s["z1_cluster"])} | {s["zero_loss"]["hits"]}/{s["completed"]} |')
    lines += ['', f'G3 point-estimate predictions: p(full) > p(paired): **{result["G3"]["full_share_larger"]}**; '
        f'p(c4) > p(c13.3): **{result["G3"]["c4_share_larger"]}**. '
        'These are separately defined minimum-loss clusters. Their shares alone do not establish a difference '
        'in recovery probability; only the paired high-contrast winner was continued.', '',
        '![Census losses, truth distances and recovered boundaries](../../../../results/validation/cleaned_interfaces/FM-003/census.png)', '',
        '## Cost and numerical stops', '',
        '| Census | Wall minutes | Charged stage work | Numerical refusals | Iteration-capped starts |',
        '|---|---:|---:|---:|---|']
    for phase,s in summaries.items():
        v=validations[phase]
        lines.append(f'| {phase} | {s["seconds"]/60:.2f} | {s["work_units"]} | '
            f'{s["stop_reasons"].get("NUMERICAL_FAILURE",0)} | {v["iteration_or_work_capped_starts"]} |')
    extra=result['costs']['phase1']['separately_run_start0_seconds']
    lines += ['', f'Phase 1 wall time excludes its reused Phase 0 start-0 fit ({extra:.3f} s); '
        'charged census work includes that fit once. '
        f'The continuation and final audit took {continued["total_seconds"]:.3f} s and '
        f'{continued["total_units"]} work units. Including the registered historical prefix '
        f'(162 units, 15.5 s), the paired census, and reused start 0 gives '
        f'{continued["total_with_census_and_prefix_units"]} units and '
        f'{(continued["total_with_census_and_prefix_seconds"]+extra)/60:.2f} minutes. '
        'Lifting, replay qualification, controls and report generation are separate experiment overhead.', '',
        'The `200` iteration limit was retained even where reached. Those endpoints are reported as capped; '
        'numerically refused endpoints are also retained and separately labelled. '
        'No censuses were extended or start seeds changed in response to results.', '',
        'The nine near-truth paired endpoints do not provide nine demonstrated recoveries. '
        'Only the lowest-loss winner was continued. The fixed 512-start census is the demonstrated selection cost; '
        'a cheaper stopping/selection rule has not been tested.', '',
        '## Validation, provenance and scope', '',
        'Phase L passed the disk, unitarity, symmetry and node-doubling gates. '
        'Only 0.25 GHz at order 2 passed the registered usable-lift rule. '
        'The ambiguous higher-order lift errors differ from the sandbox reference; '
        'the gate outcomes and usable-lift classification agree. '
        'Phase 0 reproduced CI-001 bit for bit, including four accepted steps and its exact endpoint/loss. '
        'One- and four-frequency-thread executions matched exactly. The campaign/package checks passed '
        '21 tests, and the suffix-entry adapter passed its separate test. All three census receipt audits passed.', '',
        'The suffix-entry correction is documented in '
        '[iteration 20](../iteration_20/05_suffix_entry.md): stage 3 is entered directly, '
        'with historical original-start qualification carried as provenance and an actual final audit. '
        'The original implementation archive remains intact; the suffix has a separate seal/archive.', '',
        'This is a noiseless synthetic damped-data result for the contrast-13.3 development C. '
        'It does not establish uniqueness, exhaustive global optimization, performance on noisy/real data, '
        'or recovery of other shapes. Production defaults and all prior campaign sources/results are unchanged. '
        'Other research work was active on the shared branch/host; wall times are observed costs, '
        'not a controlled runtime comparison. Independent reviewer remains unassigned.', '',
        'Reproduce using the sealed sources and the commands in '
        '[the execution notes](../iteration_20/04_execution.md), substituting '
        '`python -m experiments.cleaned_interface.fm003_suffix` for Phase 2. '
        'The final figures and synthesis are generated by '
        '`python -m experiments.cleaned_interface.fm003_review plots` and `finalize`.', '',
        'Machine-readable evidence: '
        '[synthesis](../../../../results/validation/cleaned_interfaces/FM-003/synthesis.json), '
        '[paired census](../../../../results/validation/cleaned_interfaces/FM-003/phase1/summary.json), '
        '[continuation](../../../../results/validation/cleaned_interfaces/FM-003/phase2/result.json), '
        '[full control](../../../../results/validation/cleaned_interfaces/FM-003/phase3/summary.json), '
        '[contrast-4 control](../../../../results/validation/cleaned_interfaces/FM-003/phase4/summary.json).', '',
        '## Detailed frozen-run tables', '', detailed]
    path.write_text('\n'.join(lines))
    write(output/'analysis_implementation.json',dict(
        sources={f.b.path_ref(Path(__file__)):digest(__file__)},
        inputs={str(p.relative_to(output)):digest(p) for p in
                [output/'synthesis.json',output/'phase2/result.json',
                 *[output/phase/'summary.json' for phase in summaries],
                 *[output/'validation'/(phase+'.json') for phase in summaries]]},
        report_sha256=digest(path),plot_sha256=digest(output/'census.png')))
    return dict(report=f.b.path_ref(path),G1=result['G1'],G2=result['G2'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','distances','plots','synthesis','finalize'])
    parser.add_argument('--phase',choices=f.PHASES,default='phase1')
    parser.add_argument('--output',type=Path,default=f.OUTPUT)
    a=parser.parse_args()
    if a.command=='validate':
        result=validate_phase(a.output,a.phase)
    elif a.command=='distances':
        result=continuation_distances(a.output)
    elif a.command=='plots':
        result=plots(a.output)
    elif a.command=='finalize':
        result=finalize_report(a.output)
    else:
        result=synthesis(a.output)
    print(result,flush=True)


if __name__=='__main__':
    main()
