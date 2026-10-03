"""Qualify completed TR-003 numerics after an unrelated reporting-source edit.

The original broad source seal and its failure remain unchanged. This explicit
post-run review accepts exactly one changed, unused FM-003 reporting module;
it never excuses changed solver, diagnostic, observation, or endpoint bytes.
"""
import sys
import tarfile
from .common import *
from . import folds


def run():
    folder=OUTPUT/'TR-003-branches'
    manifest=read(folder/'manifest.json')
    changed={name:dict(original=sha,current=digest(ROOT/name)) for name,sha in manifest['sources'].items()
             if digest(ROOT/name)!=sha}
    allowed='experiments/cleaned_interface/fm003_review.py'
    if set(changed)!={allowed}:
        raise ValueError('Unexpected source changes: '+str(changed))
    assert all(digest(ROOT/name)==sha for name,sha in manifest['inputs'].items())
    assert digest(folder/'sources.tar.gz')==manifest['source_archive_sha256']
    failure=read(folder/'failure.json')
    assert 'verify(folder)' in failure['traceback'] and allowed in failure['traceback']
    parent=read(folder/'parent.json')
    assert all(digest(ROOT/name)==sha for name,sha in parent['files'].items())
    endpoints=[read(p) for p in sorted((folder/'endpoints').glob('*.json'))]
    branches=[read(p) for p in sorted((folder/'branches').glob('*.json'))]
    assert len(endpoints)==4 and all(r['numerical_qualification'] for r in endpoints)
    assert len(branches)==2 and all(r['complete'] for r in branches)
    assert all(max(p['gradient_inf'] for p in r['path'])<=1e-8 for r in branches)
    total_seconds=parent['work']['seconds']+failure['work']['seconds']
    total_solves=parent['work']['frequency_solves_attempted']+failure['work']['frequency_solves_attempted']
    assert total_seconds<=3600 and total_solves<=20000
    # Re-exercise only input loading/imports, without running any forward solve.
    for case in CASES[1:3]:
        op_problem(case,False,'stage_2_damped')
    assert 'experiments.cleaned_interface.fm003_review' not in sys.modules
    dependencies={}
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path and Path(path).suffix=='.py' and str(Path(path).resolve()).startswith(str(ROOT)+'/'):
            relative=b.path_ref(Path(path).resolve())
            if relative in manifest['sources']:
                assert digest(Path(path))==manifest['sources'][relative]
                dependencies[name]=relative
    with tarfile.open(folder/'sources.tar.gz') as archive:
        before=archive.extractfile(allowed).read()
    (folder/'fm003_review_before.txt').write_bytes(before)
    (folder/'fm003_review_after.txt').write_bytes((ROOT/allowed).read_bytes())
    record=dict(numerical_evidence_qualified=True, original_completion_guard_passed=False,
        source_exception=changed, explanation='Only an unused, concurrent FM-003 reporting module changed; all solver, TR numerical source, input and parent bytes match the original seal.',
        checked_loaded_modules=dependencies, source_sha256=digest(Path(__file__)),
        original_failure_sha256=digest(folder/'failure.json'),
        combined_seconds=total_seconds, combined_frequency_solves=total_solves,
        total_derivative_batches=parent['work']['derivatives']+failure['work']['derivatives'],
        endpoints=[{k:r[k] for k in ('case','full','numerical_qualification','stationary_at_declared_tolerance',
                                    'curvature','archived_loss_relative_error')} for r in endpoints],branches=[])
    for r in branches:
        target=r.get('endpoint_correction')
        # Post-run scoring only; truth has not entered tracking or selection.
        metrics=(b.score(descriptor(r['case']),curve_from(target['curve']))
                 if target and target['converged'] else None)
        record['branches'].append(dict(case=r['case'],accepted_steps=len(r['path'])-1,stop=r['stop'],
            final_t=r['path'][-1]['x'][-1]/5,fold_candidates=r['fold_candidates'],
            confirmed_turning_brackets=sum(x['confirmed'] for x in r['fold_confirmations']),
            target_converged=bool(target and target['converged']),
            target_loss=target.get('loss') if target else None, post_run_truth_metrics=metrics))
    fmroot=ROOT/'results/validation/cleaned_interfaces/FM-003'
    census_path,result_path=fmroot/'phase1/census.json',fmroot/'phase2/result.json'
    census,result=read(census_path),read(result_path)
    assert census['completed']==census['scheduled']==512
    record['independent_fm003_context']=dict(inputs={b.path_ref(p):digest(p) for p in (census_path,result_path)},
        completed_starts=census['completed'],winner_index=census['winner_index'],
        recovered=result['recovered'],metrics=result['metrics'],maximum_residual=result['maximum_residual'],
        scope='Completed concurrent experiment; not a TR reconstruction or a uniqueness proof')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True,sharey=True)
    for ax,r in zip(axes,branches):
        points=np.asarray([p['x'] for p in r['path']])
        arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        ax.plot(arc,points[:,-1]/5,'o-',ms=3)
        for bracket in r['fold_confirmations']:
            i=bracket['index']
            ax.scatter(arc[i],points[i,-1]/5,marker='s',s=60,color='tab:red',zorder=4)
        ax.axhline(1,color='black',ls='--',lw=1)
        ax.set(title=r['case'].replace('modal__',''),xlabel='Arclength in scaled continuation coordinates',
               ylabel='Data-homotopy parameter t',ylim=(-.03,1.2))
        ax.grid(alpha=.2)
    fig.suptitle('Real stationary paths; squares mark confirmed turning brackets')
    fig.savefig(folder/'branches.png',dpi=150)
    plt.close(fig)
    lines=['# TR-003 qualified numerical closeout', '',
        f'Four endpoint audits and both bounded stationary paths completed. Combined numerical '
        f'cost, including the first adapter failure: **{total_seconds:.2f} s**, '
        f'**{total_solves} forward frequency solves**, **{record["total_derivative_batches"]} derivative batches**.', '',
        'All four endpoint Hessians have resolved positive curvature. Only the full-data contrast-4 '
        'endpoint meets the declared gradient tolerance of 1e-8 per mm; the others are near stationary '
        'but do not meet that threshold. The paired archives retain positive-gain trials rejected '
        'by their acceptance margins. No fold is demonstrated at those stalled endpoints.', '',
        '| Case | Accepted steps | Observed t at stop | Confirmed turning brackets | Outcome |',
        '|---|---:|---:|---:|---|']
    for r in record['branches']:
        lines.append(f'| {r["case"]} | {r["accepted_steps"]} | {r["final_t"]:.5f} | {r["confirmed_turning_brackets"]} | {r["stop"]} |')
    high=next(r for r in record['branches'] if r['case']==CASES[2])
    lines += ['', 'The contrast-4 branch has two N1024-confirmed turning brackets, near t≈0.77 and '
        't≈0.60. Its Hessian changes inertia across each bracket. Real pseudo-arclength passes both, '
        'then the declared 15 mm fixed-chart bound stops it before t=1. The high-contrast branch '
        'reaches t=1 after the final fixed-t correction without an observed turning point.', '',
        f'The high-contrast corrected endpoint has loss {high["target_loss"]:.9g} and post-run '
        f'boundary RMS error {high["post_run_truth_metrics"]["rms_mm"]:.5g} mm. It is a wrong-shape '
        'stationary endpoint, not a recovery. Truth was loaded only for this final scoring. '
        'The fixed affine chart differs from the production moving-chart frequency ladder; '
        'these paths neither prove global absence of folds nor demonstrate that complex geometry '
        'would recover the hard case.', '',
        '![Stationary paths](branches.png)', '',
        'The concurrently completed FM-003 512-start paired census independently recovers the '
        'high-contrast C after ordinary continuation. Its geometry RMS is '
        f'{result["metrics"]["rms_mm"]:.6g} mm, with maximum residual '
        f'{result["maximum_residual"]:.6g}. This is separate evidence for useful alternative starts, '
        'not a TR recovery or an identifiability theorem.', '',
        '## Preserved failures and provenance qualification', '',
        'The first TR-003 attempt completed the endpoint audits, then refused an unpadded stage-1 '
        'curve before branch execution. The repair zero-pads without changing its physical shape; '
        '24 tests pass. The endpoint audits were reused byte-for-byte under recorded parent hashes.', '',
        'The resumed numerics completed, but the final broad source guard failed because '
        '`experiments/cleaned_interface/fm003_review.py` changed concurrently. That file is a '
        'reporting module unused by this experiment. The original manifest, archive and failure '
        'receipt are unchanged. This explicit post-run review verifies that this is the **only** '
        'changed source, every numerical source and input matches, the loaded experiment dependency '
        'modules match, all four endpoint audits qualify, both branch records are complete and '
        'the original combined budgets hold. Before/after copies of the unrelated file are retained.', '',
        'The numerical evidence is qualified by this scoped provenance review; the original '
        'completion guard is still recorded as failed. See `qualification.json`, `parent.json`, '
        '`failure.json`, and the unchanged original TR-003 failure bundle.', '']
    (folder/'QUALIFIED_REPORT.md').write_text('\n'.join(lines)+'\n')
    record['artifacts']={str(p.relative_to(folder)):digest(p) for p in sorted(folder.rglob('*'))
                         if p.is_file() and p.name!='qualification.json'}
    write(folder/'qualification.json',record)
    print({k:record[k] for k in ('numerical_evidence_qualified','combined_seconds','combined_frequency_solves','branches')})


if __name__=='__main__':
    run()
