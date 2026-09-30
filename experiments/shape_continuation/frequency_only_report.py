"""SC-051 reference re-scoring, complete comparison, and evidence checks."""
import argparse
from collections import Counter
import csv
import json
import time

import numpy as np

from experiments.shape_continuation import frequency_only as f
from experiments.shape_continuation.forward import solve, ordered_calls


def reference_curve(saved):
    for key in ('final_curve', 'curve', 'final_state'):
        if key in saved:
            return f.restore(saved[key])
    raise KeyError('No reference endpoint')


def audit_receipt(row, saved, source):
    passed = saved.get('final_audit_passed', saved.get('audit_passed', saved.get('audit',{}).get('passed',False)))
    receipt = dict(passed=bool(passed), source=source)
    if not passed:
        follow = f.BASE/'SC-045-timeout-qualification/summary.json'
        for audit in f.sc.read(follow)['rows']:
            if source == str((f.BASE/audit['source']/'result.json').relative_to(f.ROOT)) and audit['passed']:
                receipt = dict(passed=True, original_passed=False, source=f.relative(follow),
                    sha256=f.digest(follow), qualified_endpoint=audit['source'])
    return receipt


def evaluate_references():
    manifest = f.verify()
    for row in manifest['cases']:
        for kind in ('reference', 'adaptive_reference'):
            if kind not in row:
                continue
            path=f.OUT/'references'/f'{row["id"]}__{kind}.json'
            if path.exists():
                continue
            f.set_contrast(row['contrast'])
            saved=f.sc.read(f.ROOT/row[kind])
            curve=reference_curve(saved)
            catalog,_,_=f.data_only(row)
            started=time.perf_counter()
            predictions={}
            for n in (1024,2048):
                with ordered_calls(lambda o: solve(curve,o.wavenumber,row['contrast'],o.acquisition,n).prediction,
                                   catalog) as calls:
                    predictions[n]=np.column_stack([call() for call in calls])
            observed=np.column_stack([o.scattered for o in catalog])
            residual=f.ac.relative(predictions[2048],observed)
            discrepancy=f.ac.relative(predictions[1024],predictions[2048])
            metrics=f.score(row,curve)
            limits,noisy=f.residual_limits(row,catalog)
            audit=audit_receipt(row,saved,row[kind])
            # Use the stricter field threshold at every frequency for this extra scoring check.
            fields_passed=bool(np.all(discrepancy<=1e-7))
            geometry=metrics['rms_mm']<=1 and metrics['hausdorff_upper_mm']<=2
            recovered=bool(audit['passed'] and fields_passed and geometry and np.all(residual<=limits))
            f.write(path,dict(case_id=row['id'],reference_kind=kind,source=row[kind],sha256=f.digest(f.ROOT/row[kind]),
                metrics=metrics,relative_residual=residual,maximum_residual=float(max(residual)),
                fields_passed=fields_passed,refinement_relative=discrepancy,
                saved_audit=audit,recovered=recovered,noisy=noisy,work_units=2*len(catalog),
                seconds=time.perf_counter()-started))
            print('REFERENCE',row['id'],kind,recovered,metrics['rms_mm'],flush=True)


def comparisons():
    rows=[]
    for case in f.verify()['cases']:
        path=f.OUT/'runs'/case['id']/'result.json'
        refpath=f.OUT/'references'/f'{case["id"]}__reference.json'
        if not path.exists() or not refpath.exists():
            continue
        result,ref=f.sc.read(path),f.sc.read(refpath)
        saved=f.sc.read(f.ROOT/case['reference'])
        r=dict(id=case['id'],panel=case['panel'],contrast=case['contrast'],noisy=result['noisy'],
            vanilla_rms_mm=result['metrics']['rms_mm'],reference_rms_mm=ref['metrics']['rms_mm'],
            vanilla_hausdorff_upper_mm=result['metrics']['hausdorff_upper_mm'],
            reference_hausdorff_upper_mm=ref['metrics']['hausdorff_upper_mm'],
            vanilla_recovered=result['recovered'],reference_recovered=ref['recovered'],
            vanilla_audit=result['final_audit_passed'],reference_audit=ref['saved_audit']['passed'],
            vanilla_max_residual=result['maximum_residual'],reference_max_residual=ref['maximum_residual'],
            vanilla_outcome=result['outcome'],vanilla_stages=len(result['stages']),
            vanilla_accepted=result['accepted'],vanilla_fit_units=result['fit_work']['work_units'],
            vanilla_fit_seconds=result['fit_seconds'],reference_name=case['reference_name'],
            reference_source=case['reference'],reference_cost_scope=case['cost_scope'],
            reference_recorded_units=saved.get('fit_and_localization_units',saved.get('total_units',saved.get('work',{}).get('work_units'))),
            reference_recorded_seconds=saved.get('fit_and_localization_seconds'),
            vanilla_result=f.relative(path),reference_receipt=f.relative(refpath))
        if 'adaptive_reference' in case:
            ad=f.sc.read(f.OUT/'references'/f'{case["id"]}__adaptive_reference.json')
            r.update(adaptive_rms_mm=ad['metrics']['rms_mm'],adaptive_recovered=ad['recovered'],
                     adaptive_name='SC-043 stagnation')
        rows.append(r)
    return rows


def aggregate(rows):
    return dict(cases=len(rows),vanilla_recovered=sum(r['vanilla_recovered'] for r in rows),
        reference_recovered=sum(r['reference_recovered'] for r in rows),
        vanilla_audits_passed=sum(r['vanilla_audit'] for r in rows),
        vanilla_geometry_pass=sum(r['vanilla_rms_mm']<=1 and r['vanilla_hausdorff_upper_mm']<=2 for r in rows),
        reference_geometry_pass=sum(r['reference_rms_mm']<=1 and r['reference_hausdorff_upper_mm']<=2 for r in rows),
        vanilla_lower_rms=sum(r['vanilla_rms_mm']<r['reference_rms_mm'] for r in rows),
        vanilla_median_rms_mm=float(np.median([r['vanilla_rms_mm'] for r in rows])),
        reference_median_rms_mm=float(np.median([r['reference_rms_mm'] for r in rows])),
        vanilla_fit_units=sum(r['vanilla_fit_units'] for r in rows),
        vanilla_fit_seconds_sum=sum(r['vanilla_fit_seconds'] for r in rows),
        outcomes=dict(Counter(r['vanilla_outcome'] for r in rows)))


def figures(rows,manifest):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(8,6),layout='constrained')
    for panel in dict.fromkeys(r['panel'] for r in rows):
        subset=[r for r in rows if r['panel']==panel]
        ax.scatter([r['reference_rms_mm'] for r in subset], [r['vanilla_rms_mm'] for r in subset],label=panel,s=42,alpha=.85)
    bounds=[1e-4,1e3]
    ax.plot(bounds,bounds,color='.5',linestyle='--',linewidth=1)
    ax.set(xscale='log',yscale='log',xlim=bounds,ylim=bounds,
        xlabel='Established strategy RMS (mm)',ylabel='Frequency-only, full bands RMS (mm)',
        title='SC-051: common endpoint scoring; lower is better')
    ax.legend(loc='lower right'); ax.grid(alpha=.15,which='both')
    fig.savefig(f.OUT/'rms_comparison.png',dpi=180); plt.close(fig)
    lookup={r['id']:r for r in manifest['cases']}
    for panel in dict.fromkeys(r['panel'] for r in rows):
        subset=[r for r in rows if r['panel']==panel]
        cols=2 if panel=='coupled' else min(3,len(subset))
        nr=(len(subset)+cols-1)//cols
        fig,axes=plt.subplots(nr,cols,figsize=(max(5,4*cols),3.7*nr),squeeze=False,layout='constrained')
        for ax,item in zip(axes.flat,subset):
            case=lookup[item['id']]
            vanilla=f.restore(f.sc.read(f.ROOT/item['vanilla_result'])['final_curve'])
            reference=reference_curve(f.sc.read(f.ROOT/case['reference']))
            truth=f.restore(f.sc.read(f.ROOT/case['data'])['truth']) if panel in ('coupled','intrinsic') else f.restore(f.sc.read(f.ROOT/case['truth']))
            _,initial,_=f.data_only(case)
            for curve,label,color,style in ((initial,'Initial','#aaaaaa',':'),(truth,'Truth','#222222','-'),
                    (reference,'Established','#13795b','--'),(vanilla,'Frequency only','#ce4a24','-')):
                components=curve.components if isinstance(curve,f.MultiCurve) else (curve,)
                for j,c in enumerate(components):
                    z=c.values(2048)*f.sc.LENGTH*1000
                    z=np.r_[z,z[0]]
                    ax.plot(z.real,z.imag,color=color,ls=style,lw=1.15,label=label if j==0 else None)
            ax.set_aspect('equal');ax.grid(alpha=.15)
            ax.set_title(item['id'].split('__',1)[1].replace('__',' / ')+'\n'+
                f'RMS: {item["vanilla_rms_mm"]:.3g} vs {item["reference_rms_mm"]:.3g} mm',fontsize=9)
            ax.set_xlabel('x relative to scene center (mm)');ax.set_ylabel('y (mm)')
        for ax in list(axes.flat)[len(subset):]:
            ax.set_visible(False)
        handles,labels=axes.flat[0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='outside lower center',ncols=4,fontsize=9)
        fig.suptitle(f'{panel}: returned endpoints, including numerical stops',fontsize=13)
        fig.savefig(f.OUT/f'boundaries_{panel}.png',dpi=160,bbox_inches='tight');plt.close(fig)


def report():
    manifest=f.verify();rows=comparisons()
    panels={panel:aggregate([r for r in rows if r['panel']==panel]) for panel in dict.fromkeys(r['panel'] for r in rows)}
    summary=dict(completed=len(rows),planned=len(manifest['cases']),aggregate=aggregate(rows) if rows else {},panels=panels,rows=rows)
    singles=[r for r in rows if r['panel'] not in ('coupled','intrinsic')]
    if singles:
        summary['single_object']=aggregate(singles)
    f.write(f.OUT/'summary.json',summary)
    if not rows:
        return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (f.OUT/'comparison.csv').open('w',newline='') as fp:
        writer=csv.DictWriter(fp,keys);writer.writeheader();writer.writerows(rows)
    a=summary['aggregate']
    text=['# SC-051: frequency-only continuation with full Fourier bands','',
        f'Completed {len(rows)}/{len(manifest["cases"])} configurations. Vanilla recovery: **{a["vanilla_recovered"]}/{len(rows)}**; '+
        f'established strategies: **{a["reference_recovered"]}/{len(rows)}**, using the stated common endpoint gates. '+
        f'Vanilla has lower RMS on {a["vanilla_lower_rms"]}/{len(rows)} configurations.','',
        f'For the {len(singles)} single-object configurations, recovery is '+
        f'**{summary["single_object"]["vanilla_recovered"]}/{len(singles)} versus '+
        f'{summary["single_object"]["reference_recovered"]}/{len(singles)}**. '+
        'The two reference misses are the original and opposite-start C at contrast 13.3. '+
        'The five coupled cases are local refinement comparisons; their established endpoints '+
        'improve geometry but do not meet the common strict residual gate.','',
        'Vanilla fixes **M=K=255 from the first frequency**, the full non-Nyquist Fourier band of the 512-node mesh. '+
        'It advances through cumulative real-frequency data from 0.25 to 2.5 GHz (four available frequencies for coupled scenes). '+
        'There is no band ladder, localization, state cleanup, adaptive selection, or complex-frequency damping. '+
        'The unchanged projected update and LM step controls remain; every candidate must pass 512/1024 numerical acceptance. '+
        'This is finite discretization without a policy band cap, not literally infinite M/K.','',
        '| Panel | Cases | Vanilla recovery | Established recovery | Median RMS vanilla / established (mm) |',
        '|---|---:|---:|---:|---:|']
    for panel,p in panels.items():
        text.append(f'| {panel} | {p["cases"]} | {p["vanilla_recovered"]} | {p["reference_recovered"]} | {p["vanilla_median_rms_mm"]:.4g} / {p["reference_median_rms_mm"]:.4g} |')
    text += ['', '![RMS comparison](rms_comparison.png)','',
        '## Per-scene results','',
        '| Scene | Contrast | Vanilla RMS mm | Established RMS mm | Vanilla audit | Vanilla stop |',
        '|---|---:|---:|---:|---|---|']
    for r in rows:
        text.append(f'| {r["id"]} | {r["contrast"]:g} | {r["vanilla_rms_mm"]:.5g} | {r["reference_rms_mm"]:.5g} | '+
            f'{"PASS" if r["vanilla_audit"] else "FAIL"} | {r["vanilla_outcome"]} after {r["vanilla_stages"]} stages |')
    core_adaptive=[r for r in rows if 'adaptive_rms_mm' in r]
    if core_adaptive:
        text += ['', 'The explicit adaptive SC-043 stagnation comparator gives:', '',
            '| Original scene | Vanilla RMS mm | Adaptive stagnation RMS mm |',
            '|---|---:|---:|']
        for r in core_adaptive:
            text.append(f'| {r["id"].removeprefix("core__")} | {r["vanilla_rms_mm"]:.5g} | {r["adaptive_rms_mm"]:.5g} |')
    text += ['', '## Comparison and interpretation','',
        'The references were chosen before fitting: SC-043 fixed release (best aggregate control), SC-044 recurrent cleanup, '+
        'SC-050 localization plus warm-up, MA-005 damped initialization plus adaptive frontier release, SC-047 joint M3→M5, '+
        'and SC-048 compact M5. There is no single adaptive policy established as best on every panel. '+
        'SC-043 stagnation, the stronger tested adaptive control, is also re-scored in the CSV. '+
        'These are end-to-end strategy comparisons: initialization, spectral controls and—in MA-005—damped data differ. '+
        'They do not isolate the causal effect of M/K alone.','',
        'The full-band arm also exercises the existing projected-update geometry derivative at M=255, '+
        'beyond the bands used by the established reconstruction policies. Its finite-difference geometry '+
        'settings are unchanged. Numerical refusals are outcomes of this particular implementation and '+
        'discretization, not evidence that an ideally resolved infinite-band inverse must fail. '+
        'The doubled-resolution controls and separate geometry scores limit that interpretation.','',
        'At the first frequency, each single-object fit has 24 complex measurements (48 real rows) '+
        'and 511 normal-update coordinates. Its linearized Jacobian therefore has at least 463 null directions. '+
        'LM damping remains active, but removing the band restriction exposes a large underdetermined update space '+
        'before higher-frequency data enter. This dimensional bound describes the experiment; it is not a proof '+
        'that every numerical stop has the same mechanism.','',
        'The reference endpoints were re-scored on identical stored observations at 1024 and 2048 nodes. '+
        'Their original derivative-audit receipts remain authoritative; the SC-045 unchanged-endpoint follow-up is used '+
        'for the SC-044 noisy-asymmetric audit timeout. Vanilla endpoints are independently audited over all active '+
        'Jacobian columns and a full-trial finite difference. Near-zero high-mode columns can fail a relative-only '+
        'Jacobian gate; raw norms and errors are saved so this can be distinguished from meaningful field error. '+
        'Neither a failed audit nor an early numerical stop is counted as recovery.','',
        f'Ignoring residual and numerical-audit gates, vanilla passes the geometry thresholds on '+
        f'{a["vanilla_geometry_pass"]}/{len(rows)} configurations, versus '+
        f'{a["reference_geometry_pass"]}/{len(rows)} for the references. '+
        f'{a["vanilla_audits_passed"]}/{len(rows)} vanilla endpoints pass their numerical audits, '+
        'so the lack of recovery cannot be attributed solely to audit rejection. '+
        'The comparison therefore also exposes geometric progress independently of the stricter full-band audit.','',
        'Recovery requires RMS <=1 mm, Hausdorff upper bound <=2 mm, maximum per-frequency residual <=0.003 '+
        '(or max(0.003, 3×realized noise)), and passing numerical checks. Coupled RMS is the worst object. '+
        'Cases are a finite correlated test panel, not independent statistical trials: opposite C starts share data, '+
        'noise draws share targets, and contrast variants share geometry. The three MA development cases at contrast '+
        '0.5 were deduplicated against SC-050. Historical plane-wave paper-replication and insertion-only diagnostics '+
        'are outside this current paired-source inverse benchmark.','',
        f'Vanilla fitting used {a["vanilla_fit_units"]:,} work units and {a["vanilla_fit_seconds_sum"]:.1f} summed worker seconds. '+
        'Audit/scoring work is separate in each receipt. Equal work units do not imply equal runtime at different '+
        'bands or grids. SC-043/044 reference costs describe suffixes only; old runtime versions and host load also differ. '+
        '**No wall-time speedup is inferred from the archived comparisons.**','',
        '## Evidence and reproduction','',
        '[Frozen plan](plan.md), [manifest](manifest.json), [machine-readable comparison](comparison.csv), '+
        '[summary](summary.json). Per-stage histories, rejected trials, accepted curves, numerical stops, and '+
        'audits are under `runs/`; reference scoring receipts are under `references/`.','',
        '```bash',
        'export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1',
        'export SC_FREQUENCY_THREADS=4 SC_FORWARD_BACKEND=cuda MPLCONFIGDIR=/tmp/sc051-mpl',
        'python -m experiments.shape_continuation.frequency_only verify',
        'python -m experiments.shape_continuation.frequency_only run --workers 3',
        'python -m experiments.shape_continuation.frequency_only_report references',
        'python -m experiments.shape_continuation.frequency_only_resolution run --workers 1',
        'python -m experiments.shape_continuation.frequency_only_report verify',
        'python -m experiments.shape_continuation.frequency_only_report report','```','']
    control=[]
    for case in manifest['cases']:
        path=f.OUT/'resolution_1024/runs'/case['id']/'result.json'
        if path.exists():
            d=f.sc.read(path)
            control.append(dict(case=case['id'],rms_mm=d['metrics']['rms_mm'],
                recovered=d['recovered'],audit_passed=d['final_audit_passed'],
                outcome=d['outcome'],stages=len(d['stages']),fit_units=d['fit_work']['work_units'],
                fit_seconds=d['fit_seconds'],audit_units=d['audit_units'],
                audit_recovery=d.get('audit_recovery')))
    if control:
        summary['resolution_control']=control
        text += ['## Doubling forward resolution at unchanged M/K','',
            'The six original cases are repeated at N=1024/2048 with M=K=255 and identical fitting budgets. '+
            'This follow-up was frozen after observing the primary numerical stops; all outcomes are retained. '+
            '[Control plan](resolution_1024/plan.md).','',
            '| Scene | RMS mm | Audit | Recovered | Stop |', '|---|---:|---|---|---|']
        for r in control:
            text.append(f'| {r["case"]} | {r["rms_mm"]:.5g} | {r["audit_passed"]} | {r["recovered"]} | {r["outcome"]} |')
        text += ['',
            f'{len(control)}/6 controls completed; {sum(r["recovered"] for r in control)} recover. '+
            'The star reaches its fitting wall limit while still accepting steps; this is a budget-limited '+
            'outcome, not a converged solution. Wall limits are checked between evaluations and can overrun '+
            'by one in-flight evaluation. Its final accepted step is present in the trial, acceptance and '+
            'checkpoint receipts; the timeout precedes the next gradient/history row. The returned endpoint '+
            'is that accepted checkpoint, not the preceding history row.','',
            'The two-worker control pool terminated abruptly during the kite endpoint audit. '+
            'The root cause is unestablished. Its saved fitting endpoint was hash-checked and audited again '+
            'without rerunning fitting or changing coefficients; the last two controls ran sequentially. '+
            'The lost audit cost is unknown and bounded by 126 work units, in addition to recorded work. '+
            'Its total elapsed time is left unknown. '+
            '[Recovery receipt](resolution_1024/runs/core__kite/audit_recovery.json) and '+
            '[execution details](execution.json) preserve the interruption.','']
    accounting=dict(primary_fit_units=a['vanilla_fit_units'],
        primary_audit_units=sum(f.sc.read(f.ROOT/r['vanilla_result'])['audit_units'] for r in rows),
        reference_scoring_units=sum(f.sc.read(p)['work_units'] for p in (f.OUT/'references').glob('*.json')),
        resolution_fit_units=sum(r['fit_units'] for r in control),
        resolution_audit_units=sum(r['audit_units'] for r in control),
        interrupted_audit_units_upper_bound=sum(
            r['audit_recovery']['unknown_interrupted_audit_work_units_upper_bound']
            for r in control if r['audit_recovery']))
    accounting['recorded_total_units']=sum(v for k,v in accounting.items() if k!='interrupted_audit_units_upper_bound')
    summary['accounting']=accounting
    f.write(f.OUT/'summary.json',summary)
    text += ['## Physical work accounting','',
        '| Component | Recorded work units |','|---|---:|',
        f'| Primary fitting | {accounting["primary_fit_units"]:,} |',
        f'| Primary endpoint audits | {accounting["primary_audit_units"]:,} |',
        f'| Reference endpoint scoring (47 receipts) | {accounting["reference_scoring_units"]:,} |',
        f'| Resolution-control fitting | {accounting["resolution_fit_units"]:,} |',
        f'| Resolution-control endpoint audits | {accounting["resolution_audit_units"]:,} |',
        f'| Recorded total | {accounting["recorded_total_units"]:,} |','',
        f'Additional interrupted-audit work is unknown, bounded above by '+
        f'{accounting["interrupted_audit_units_upper_bound"]} units. Historical reference fitting '+
        'and input generation are not new work and are excluded from this table. '+
        'A work unit counts one physical frequency/RHS block; dense geometry algebra is not priced '+
        'by that count, so these totals do not establish a computational speed advantage.','']
    for panel in panels:
        text.extend([f'### {panel} returned boundaries','',f'![{panel}](boundaries_{panel}.png)',''])
    (f.OUT/'README.md').write_text('\n'.join(text))
    if len(rows)==len(manifest['cases']):
        figures(rows,manifest)
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))


def verify_results(require_controls=True):
    manifest=f.verify()
    checks=0;diagnoses=[]
    control_manifest=f.sc.read(f.OUT/'resolution_1024/manifest.json')
    assert control_manifest['parent_manifest']==f.digest(f.OUT/'manifest.json')
    checks+=1
    for mapping in ('sources','inputs'):
        for path,expected in control_manifest[mapping].items():
            assert f.digest(f.ROOT/path)==expected,path
            checks+=1
    for case in manifest['cases']:
        folder=f.OUT/'runs'/case['id']
        result=f.sc.read(folder/'result.json')
        config=f.sc.read(folder/'configuration.json')
        assert result['case']==case
        assert f.restore(result['final_curve']).band==255
        assert result['fit_work']['work_units']<=f.CAP
        assert result['accepted']==sum(r['accepted'] for r in result['stages'])
        checks+=4
        for i,stage in enumerate(config['schedule']):
            settings=stage['stage']
            assert settings['update_modes']==settings['curve_modes']==255
            assert settings['nodes']==512 and settings['refined_nodes']==1024
            checks+=2
        ref=f.sc.read(f.OUT/'references'/f'{case["id"]}__reference.json')
        assert ref['source']==case['reference'] and ref['sha256']==f.digest(f.ROOT/case['reference'])
        assert len(ref['relative_residual'])==len(config['schedule'])
        checks+=2
        if 'adaptive_reference' in case:
            ad=f.sc.read(f.OUT/'references'/f'{case["id"]}__adaptive_reference.json')
            assert ad['source']==case['adaptive_reference']
            assert ad['sha256']==f.digest(f.ROOT/case['adaptive_reference'])
            checks+=2
        audit=f.sc.read(folder/'final_audit.json')
        assert result['final_audit_passed']==audit['passed']
        checks+=1
        refusals=Counter()
        for stage in result['stages']:
            d=f.sc.read(folder/f'{stage["stage"]}.json')
            assert d['accepted']==sum(r['iteration']>0 for r in d['history'])
            assert all(len(r['step_m'])==(1022 if case['panel'] in ('coupled','intrinsic') else 511) for r in d['history'])
            checks+=2
            refusals.update(r.get('reason',r.get('status','unknown')) for r in d['trials'])
        norms=np.array(audit.get('jacobian_column_norm',[]))
        errors=np.array(audit.get('jacobian_relative',[]))
        strong=norms>=.01*norms.max() if len(norms) else np.array([],dtype=bool)
        diagnoses.append(dict(case=case['id'],refusals=dict(refusals),
            maximum_field_discrepancy=max(audit.get('field_relative',[float('nan')])),
            maximum_jacobian_relative=max(errors,default=None),
            maximum_jacobian_relative_strong_columns=float(max(errors[strong])) if np.any(strong) else None,
            full_trial_fd_relative=audit.get('full_trial_fd_relative')))
    controls=[];terminal_history_gaps=[]
    for case in manifest['cases']:
        if case['panel']!='core':
            continue
        folder=f.OUT/'resolution_1024/runs'/case['id']
        if not require_controls and not (folder/'result.json').exists():
            continue
        d=f.sc.read(folder/'result.json')
        conf=f.sc.read(folder/'configuration.json')
        assert all(r['stage']['update_modes']==r['stage']['curve_modes']==255 and
                   r['stage']['nodes']==1024 and r['stage']['refined_nodes']==2048 for r in conf['schedule'])
        assert f.restore(d['final_curve']).band==255
        assert d['fit_work']['work_units']<=f.CAP
        assert d['accepted']==sum(r['accepted'] for r in d['stages'])
        audit=f.sc.read(folder/'final_audit.json')
        assert d['final_audit_passed']==audit['passed']
        checks+=5;controls.append(case['id'])
        for stage in d['stages']:
            saved=f.sc.read(folder/f'{stage["stage"]}.json')
            history_count=sum(r['iteration']>0 for r in saved['history'])
            assert saved['accepted']==sum(r.get('status')=='accepted' for r in saved['trials'])
            if saved['accepted']!=history_count:
                # fit_stage checkpoints an accepted state before constructing its next gradient.
                assert saved['outcome']=='TRIAL_WALL_LIMIT' and saved['accepted']==history_count+1
                checkpoints=f.sc.read(folder/'accepted.json')['states']
                last=checkpoints[-1]
                assert last['stage']==stage['stage'] and last['iteration']==saved['accepted']
                assert last['curve']==d['final_curve'] and saved['checks'][-1]['accepted']
                terminal_history_gaps.append(dict(case=case['id'],stage=stage['stage'],
                    accepted=saved['accepted'],history_rows=history_count,
                    last_accepted_checkpoint_matches_endpoint=True))
                checks+=3
            else:
                assert saved['accepted']==history_count
            assert all(len(r['step_m'])==511 for r in saved['history'])
            checks+=3
        if d.get('audit_recovery'):
            recovery=d['audit_recovery']
            assert recovery['endpoint_sha256']==f.digest(folder/'unscored.json')
            assert recovery['source_sha256']==f.digest(f.ROOT/'experiments/shape_continuation/frequency_only_recover_audit.py')
            assert d['final_curve']==f.sc.read(folder/'unscored.json')['final_curve']
            checks+=3
    name='verification.json' if require_controls else 'primary_verification.json'
    f.write(f.OUT/name,dict(passed=True,checks=checks,cases=len(manifest['cases']),
        controls=controls,source_and_input_hashes_verified=True,
        terminal_history_gaps=terminal_history_gaps,
        report_source_sha256=f.digest(f.ROOT/'experiments/shape_continuation/frequency_only_report.py'),
        targeted_tests='15 passed: test_lm_backend.py + test_multi_object.py'))
    f.write(f.OUT/'diagnosis.json',diagnoses)
    print('VERIFIED',checks,'evidence assertions;',len(manifest['cases']),'cases;',len(controls),'controls')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('references','report','verify','verify-primary'))
    args=p.parse_args()
    {'references':evaluate_references,'report':report,'verify':verify_results,
     'verify-primary':lambda:verify_results(False)}[args.mode]()
