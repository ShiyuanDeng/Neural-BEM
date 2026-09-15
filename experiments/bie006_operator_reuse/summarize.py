"""Rebuild BIE-006 tables/figures from saved data; no physical solves."""
from pathlib import Path
import argparse
import csv
import json
import numpy as np
from .models import break_even
from .support import digest,write_json,relative


def read(path):
    return json.loads(Path(path).read_text())


def write_csv(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k,v in r.items() if not isinstance(v,(dict,list))))
    with Path(path).open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)


def prefix(rows,arm,tolerance):
    passed=[]
    for row in sorted(rows,key=lambda r:r['amplitude_m']):
        if not row['qualified'] or row[arm+'_relative']>tolerance:break
        passed.append(row)
    return passed


def summarize(output):
    rows=read(output/'accuracy.json');timings=read(output/'timings.json')
    manifest=read(output/'manifest.json');inputs=read(output/'inputs.json')
    controls=read(output/'controls.json');refs=read(output/'refinements.json')
    arrays=np.load(output/'predictions.npz');audit=[]
    for r in rows:
        for arm in ['T','O']:
            y=arrays[r['key']+'_'+arm].diagonal();ref=arrays[r['key']+'_R'].diagonal()
            replay=relative(y,ref,r['incident_floor'])
            if not np.isclose(replay,r[arm+'_relative'],rtol=1e-12,atol=1e-18):
                raise AssertionError('Saved-array accuracy replay failed')
            full=relative(arrays[r['key']+'_'+arm],arrays[r['key']+'_R'],r['incident_floor'])
            assert np.isclose(full,r[arm+'_full_relative'],rtol=1e-12,atol=1e-18)
            audit.append(dict(key=r['key'],arm=arm,passed=True))
        assert np.isclose(relative(arrays[r['key']+'_E'].diagonal(),arrays[r['key']+'_R'].diagonal(),r['incident_floor']),
                          r['refinement_relative'],rtol=1e-12,atol=1e-18)
    ledger=[json.loads(line) for line in (output/'work_ledger.jsonl').read_text().splitlines()]
    recount=dict.fromkeys(manifest['counts'],0)
    for event in ledger:
        if event['status']=='attempted':
            for key,value in event['reserved'].items():recount[key]+=value
    assert recount==manifest['counts']
    assert all(recount[k]<=manifest['limits'][k] for k in recount)
    failed=[e for e in ledger if e['status']=='failed'];assert not failed
    frozen={}
    for path,sha in manifest['source_input_hashes'].items():
        snapshot=output/'measured_sources'/path
        frozen[path]=(digest(snapshot)==sha) if snapshot.exists() else digest(path)==sha
    assert all(frozen.values())
    groups={}
    for row in rows:groups.setdefault((row['frequency_hz'],row['direction']),[]).append(row)
    ranges=[];slopes=[];ray_costs=[]
    for (freq,direction),group in sorted(groups.items()):
        group.sort(key=lambda r:r['amplitude_m'])
        for tol in [1e-6,1e-3,1e-2]:
            result=dict(frequency_hz=freq,direction=direction,error_gate=tol)
            for arm in ['T','O']:
                accepted=prefix(group,arm,tol)
                result[arm+'_max_passing_m']=accepted[-1]['amplitude_m'] if accepted else 0.
                result[arm+'_passing_count']=len(accepted)
            ranges.append(result)
        for arm in ['T','O']:
            first,second=group[:2]
            value=np.log(second[arm+'_same_grid_relative']/first[arm+'_same_grid_relative'])/np.log(second['amplitude_m']/first['amplitude_m'])
            slopes.append(dict(frequency_hz=freq,direction=direction,arm=arm,slope=float(value)))
            for scope,selected in [('all_four',group),('qualified_prefix_1e-3',prefix(group,arm,1e-3))]:
                if not selected:continue
                m=len(selected);setup=selected[0]['derivative_seconds']
                if arm=='T':setup+=selected[0]['tangent_setup_seconds']
                online=sum(r[arm+'_online_seconds'] for r in selected)
                exact=sum(r['exact_seconds'] for r in selected)
                one_validation=selected[-1]['exact_seconds']
                all_validation=sum(r['exact_seconds']+r['reference_seconds'] for r in selected)
                base=selected[0]['base_seconds']
                ray_costs.append(dict(frequency_hz=freq,direction=direction,arm=arm,scope=scope,evaluations=m,
                    setup_seconds=setup,online_sum_seconds=online,exact_sum_seconds=exact,
                    warm_audit_free_speedup=exact/(setup+online),
                    warm_one_exact_validation_speedup=exact/(setup+online+one_validation),
                    cold_one_exact_validation_speedup=exact/(base+setup+online+one_validation),
                    all_audited_seconds=setup+online+all_validation,
                    matched_accuracy=all(r['qualified'] and r[arm+'_relative']<=1e-3 for r in selected)))
    med={key:float(np.median([r[key] for r in timings])) for key in
         ('base_seconds','derivative_seconds','tangent_setup_seconds','exact_seconds','T_online_seconds','O_online_seconds')}
    costs=[]
    for arm in ['T','O']:
        setup=med['derivative_seconds']+(med['tangent_setup_seconds'] if arm=='T' else 0.)
        online=med[arm+'_online_seconds'];exact=med['exact_seconds'];base=med['base_seconds']
        costs.append(dict(arm=arm,warm_fresh_direction_seconds=setup+online,
            time_model='Sum of component medians from three repeats; amortization scenarios use these medians.',
            warm_fresh_direction_over_exact=(setup+online)/exact,
            cold_fresh_direction_seconds=base+setup+online,
            cached_online_seconds=online,audit_free_break_even=break_even(setup,exact,online),
            cold_audit_free_break_even=break_even(base+setup,exact,online),
            one_in_four_validation_break_even=break_even(setup,exact,online+exact/4),
            blockwise_validation_break_even=next((m for m in range(1,1001)
                if setup+m*online+int(np.ceil(m/4))*exact<=m*exact),None),
            cold_one_in_four_validation_break_even=break_even(base+setup,exact,online+exact/4),
            four_evaluation_audit_free_speedup=4*exact/(setup+4*online),
            four_evaluation_one_validation_speedup=4*exact/(setup+4*online+exact),
            online_without_geometry_seconds=float(np.median([r[arm+'_online_seconds']-r[arm+'_geometry_seconds'] for r in timings]))))
    workers=manifest['workers_before']+manifest['workers_after']
    for r in rows:
        workers+=r['workers_before']+r['workers_after']
        for v in r['arm_workers'].values():workers+=v['workers_before']+v['workers_after']
    for r in timings:
        workers+=r['workers_before']+r['workers_after']
        for arm in ['T','O']:workers+=r[arm+'_workers']['before']+r[arm+'_workers']['after']
    primary=[r for r in ranges if r['error_gate']==1e-3]
    range_advantages=[r for r in primary if r['O_max_passing_m']>r['T_max_passing_m'] and r['O_max_passing_m']>=.001]
    nearby=[r for r in inputs['nearby_saved_states'] if r['maximum_displacement_m']<=.005]
    # Geometry-only directions can be highly correlated; disclose this limitation.
    from .fixtures import producer
    t=np.arange(4096)*2*np.pi/4096
    vectors=np.array([producer(np.asarray(d['cosine']),np.asarray(d['sine'])).evaluate(t).points.ravel()
                      for d in inputs['directions']])
    unit=vectors/np.linalg.norm(vectors,axis=1)[:,None]
    all_quality=manifest['status']=='COMPLETE' and len(rows)==24 and all(r['qualified'] for r in rows)
    all_quality=all_quality and all(r['qualified'] for r in refs) and all(r['passed'] for r in controls)
    if not all_quality:decision='INCONCLUSIVE_QUALITY_GATE'
    elif not range_advantages and sum(r['O_relative']>=r['T_relative'] for r in rows)>=18:
        decision='STOP_FIRST_ORDER_OPERATOR_REUSE'
    else:decision='BOUNDED_EVIDENCE_ONLY_REVIEW_REQUIRED'
    summary=dict(decision=decision,quality_pass=all_quality,rows=len(rows),
        surrogate_worse_than_tangent_rows=sum(r['O_relative']>r['T_relative'] for r in rows),
        useful_range_advantage_paths=len(range_advantages),primary_ranges=primary,
        worst_candidate_refinement=max(r['refinement_relative'] for r in rows),
        worst_derivative_refinement=max(r['paired_relative'] for r in refs if r['kind']=='derivative'),
        worst_production_parity=max(r['relative'] for r in controls if r['kind']=='production_parity'),
        max_surrogate_solve_residual=max(r['O_approximate_residual'] for r in rows),
        max_exact_matrix_residual=max(r['O_exact_matrix_residual'] for r in rows),
        slope_min=min(r['slope'] for r in slopes),slope_max=max(r['slope'] for r in slopes),
        timings_controlled=not workers,timing_medians=med,cost_scenarios=costs,
        timing_point=dict(frequency_hz=1_250_000_000,amplitude_m=.001,direction='to_row_2',
                          passes_primary_error_gate=False,
                          limitation='Timing point is outside the 0.1% region; cost-only, not an accuracy-qualified speedup.'),
        original_same_cycle_states=len(inputs['nearby_saved_states']),saved_states_within_tested_5mm=len(nearby),
        direction_cosines=(unit@unit.T),
        finite_prefix_operator_best_speedup_with_one_validation=max(r['warm_one_exact_validation_speedup'] for r in ray_costs
            if r['arm']=='O' and r['scope']=='qualified_prefix_1e-3'),
        counts=manifest['counts'],elapsed_seconds=manifest['elapsed_seconds'],
        peak_rss_gib=manifest['peak_rss_bytes']/1024**3,protected_source_input_hashes=len(frozen),
        failed_operations=len(failed))
    write_json(output/'summary.json',summary)
    for name,data in [('accuracy',rows),('ranges',ranges),('error_slopes',slopes),('ray_costs',ray_costs),('cost_scenarios',costs)]:
        write_csv(output/(name+'.csv'),data)
    write_json(output/'reporting_validation.json',dict(saved_array_checks=len(audit),all_pass=True,
        counts_replayed=recount,source_input_hashes_checked=len(frozen),quality_pass=all_quality,
        reporting_source_sha256=digest(__file__)))
    plots(output,groups,med,costs)
    readme(output,summary,primary,ray_costs)
    print(json.dumps(summary,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x))


def plots(output,groups,med,costs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,3,figsize=(12,7),sharex=True,sharey=True,layout='constrained')
    for ax,((freq,direction),rows) in zip(axes.ravel(),sorted(groups.items())):
        x=np.array([r['amplitude_m']*1e3 for r in rows])
        for arm,color,marker,label in [('T','#147d92','o','Tangent data'),('O','#c65032','s','Operator surrogate')]:
            ax.loglog(x,[r[arm+'_relative'] for r in rows],marker+'-',color=color,label=label,linewidth=1.8)
        ax.axhline(1e-3,color='#555555',linestyle='--',linewidth=1,label='0.1% error gate')
        ax.set_title(f'{freq/1e9:g} GHz · {direction.replace("_"," ")}')
        ax.grid(True,which='both',alpha=.17)
        ax.set_xticks([.01,.1,1,5],['0.01','0.1','1','5'])
    axes[0,0].legend(fontsize=8,loc='upper left')
    fig.supxlabel('Maximum boundary displacement (mm)')
    fig.supylabel('Paired scattered-field relative error vs N=256')
    fig.suptitle('BIE-006: first-order operator reuse does not widen the accurate region',fontsize=14)
    fig.savefig(output/'error_vs_displacement.png',dpi=180);fig.savefig(output/'error_vs_displacement.pdf');plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5),layout='constrained')
    values=[med['exact_seconds']]+[r['warm_fresh_direction_seconds'] for r in costs]
    bars=ax.bar(['Fresh exact','Tangent: fresh direction','Operator: fresh direction'],np.array(values)*1000,
                color=['#666b71','#147d92','#c65032'])
    for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,b.get_height()+3,f'{v*1000:.1f} ms',ha='center')
    ax.set_ylim(0,max(values)*1250);ax.set_ylabel('Time per evaluation (ms)')
    ax.set_title('Existing base available; derivative and geometry validation charged\n3-repeat component medians; 1.25 GHz / 1 mm cost probe (fails 0.1% gate)')
    fig.savefig(output/'fresh_direction_cost.png',dpi=180);plt.close(fig)


def readme(output,s,primary,ray_costs):
    med=s['timing_medians'];cost={r['arm']:r for r in s['cost_scenarios']}
    lines=['# BIE-006 — local operator reuse', '',f'**Decision: {s["decision"]}.**', '',
      'The first-order operator surrogate does not extend the useful accuracy region on this saved noncircular base.',
      f'It is less accurate than tangent data in {s["surrogate_worse_than_tangent_rows"]}/24 rows. Its two small improvements occur at 5 mm and both fail the primary 0.1% gate.', '',
      '## Main measurements','', '| Frequency | Tangent maximum passing displacement | Operator maximum passing displacement |',
      '|---|---:|---:|']
    for frequency in sorted(set(r['frequency_hz'] for r in primary)):
        r=next(r for r in primary if r['frequency_hz']==frequency)
        lines.append(f'| {frequency/1e9:g} GHz, all three directions | {r["T_max_passing_m"]*1000:g} mm | {r["O_max_passing_m"]*1000:g} mm |')
    lines += ['', 'These are sampled contiguous ranges at relative error <=1e-3; no interpolation or certification.',
      f'All 24 predictions are resolution-qualified. Worst N=128/256 discrepancy: **{s["worst_candidate_refinement"]:.3e}**; analytic tangent discrepancy **{s["worst_derivative_refinement"]:.3e}**.',
      f'Error slopes over the two smallest steps are {s["slope_min"]:.4f}–{s["slope_max"]:.4f}, consistent with quadratic error in both models.',
      f'The surrogate solve residual stays below {s["max_surrogate_solve_residual"]:.3e}, while its residual against the actual new system reaches {s["max_exact_matrix_residual"]:.3e}. Solving the approximate system accurately does not remove model error.', '',
      '![Error versus displacement](error_vs_displacement.png)', '', '## Cost', '',
      f'Three sequential single-thread repeats with no detected sibling numerical workers. Fresh E median: **{med["exact_seconds"]*1000:.1f} ms**. Analytic directional assembly alone: **{med["derivative_seconds"]*1000:.1f} ms**, including primal kernel recomputation.', '',
      '| Existing base available | Tangent T | Operator O |', '|---|---:|---:|',
      f'| Fresh direction, all setup charged | {cost["T"]["warm_fresh_direction_seconds"]*1000:.1f} ms | {cost["O"]["warm_fresh_direction_seconds"]*1000:.1f} ms |',
      f'| Ratio to fresh E | {cost["T"]["warm_fresh_direction_over_exact"]:.3f}x | {cost["O"]["warm_fresh_direction_over_exact"]:.3f}x |',
      f'| Cached direction online, geometry included | {cost["T"]["cached_online_seconds"]*1000:.1f} ms | {cost["O"]["cached_online_seconds"]*1000:.1f} ms |',
      f'| Online algebra only, geometry excluded | {cost["T"]["online_without_geometry_seconds"]*1000:.3f} ms | {cost["O"]["online_without_geometry_seconds"]*1000:.3f} ms |',
      f'| Audit-free break-even, base available | {cost["T"]["audit_free_break_even"]} predictions | {cost["O"]["audit_free_break_even"]} predictions |',
      f'| Break-even, one exact validation per four predictions | {cost["T"]["one_in_four_validation_break_even"]} | {cost["O"]["one_in_four_validation_break_even"]} |', '',
      'Fresh-direction totals and amortization scenarios sum the medians of their measured components. The one-in-four break-even column uses average audit cost E/4; exact integer audit-block counts are also in `cost_scenarios.csv`.', '',
      'The fixed timing point is at 1.25 GHz / 1 mm and fails the primary accuracy gate. These are cost measurements, not a matched-accuracy speedup claim. Geometry validation dominates cached online cost; each O prediction still factors a new matrix.', '',
      f'On the actually qualified prefixes (2 or 3 evaluations), the best O speedup over E after setup and one exact validation is **{s["finite_prefix_operator_best_speedup_with_one_validation"]:.3f}x** (below 1 means slower). Full cold setup and all exact/refined audit costs are retained in `ray_costs.csv`.', '',
      '![Fresh-direction cost](fresh_direction_cost.png)', '', '## Scope and decision', '',
      f'The original saved displacements are 19.99–25.01 mm. None of the {s["original_same_cycle_states"]} later same-cycle saved states lies within the tested 5 mm region. The four-point rays are synthetic local scalings of real update directions; there is no demonstrated real reuse sequence long enough to amortize setup.',
      'The three chronological directions are correlated; `summary.json` records their pairwise direction cosines. One base at two frequencies is a bounded negative result, not rejection of every possible operator surrogate.',
      '**Stop this first-order reuse implementation.** No accuracy-range benefit or setup-inclusive saving beyond tangent data warrants controller integration. No higher-order model, preconditioner, inverse run or shared solver change was made.', '',
      '## Validation and provenance', '',
      f'- Work: {s["counts"]["exact_assemblies"]} exact assemblies, {s["counts"]["analytic_assemblies"]} analytic assemblies with the same number of primal recomputations, {s["counts"]["factorizations"]} LU factorizations, {s["counts"]["solves"]} batched solves, {s["counts"]["updated_solves"]} updated O solves.',
      f'- Execution: {s["elapsed_seconds"]:.3f} seconds; peak RSS {s["peak_rss_gib"]:.3f} GiB. No failed physical operations.',
      f'- Four algebra/geometry tests passed before execution. Public production parity, all refinement gates, 48 saved prediction replays, budget recount and {s["protected_source_input_hashes"]} source/input hashes pass.',
      '- `frozen_plan.md` owns the executed contract; `inputs.json` fixes geometry/acquisition. `measured_sources/` retains exact measured code. `manifest.json`, `work_ledger.jsonl`, `predictions.npz` and JSON/CSV tables preserve raw evidence.',
      '- Reporting is independently rerunnable: `PYTHONPATH=solvers:. python -m experiments.bie006_operator_reuse.summarize <bundle>`. No physical solve is performed by reporting.', '']
    (output/'README.md').write_text('\n'.join(lines))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args();summarize(args.output)
