"""Rebuild RB-001 comparison, endpoint figure and artifact verification."""
import argparse
from collections import Counter
from pathlib import Path
import subprocess
from time import time

import numpy as np

from bem_inverse.io import curve_from, digest, read, write
from . import rb001 as a
from .continuation import verify_phase


def report(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    stage_a=read(output/'stage_a.json')
    qualification=read(output/'qualification/result.json')
    continuation=read(output/'continuation.json')
    if continuation['completed']!=4:
        raise ValueError('Final report requires all four declared continuation outcomes')
    rows=[]
    fig,axes=plt.subplots(2,2,figsize=(10,9),layout='constrained')
    for index,(case,arm,label) in enumerate(a.CASES):
        folder=output/'runs'/case/arm
        result=read(folder/'result.json')
        original=read(a.ARCHIVE/'runs'/case/arm/'result.json')
        audit=read(folder/'final_audit.json')
        original_audit=read(folder/'original_resolution_audit.json') if (folder/'original_resolution_audit.json').exists() else audit
        diagnostic=next(r for r in stage_a['rows'] if r['case']==case and r['arm']==arm)
        refinement=read(output/'stage_a'/case/arm/'refinement.json')
        half=read(output/'stage_a'/case/arm/'half_steps.json')['attempts']
        resumed=read(output/'stage_a'/case/arm/'current/resume_state.json')
        statuses=Counter()
        for path in folder.glob('*.json'):
            receipt=read(path)
            for trial in receipt.get('trials', []):
                if receipt['stage']==resumed['stage'] and trial['iteration']<=resumed['iteration']:
                    continue
                statuses[trial.get('status','unrecorded')]+=1
        row=dict(case=case,arm=arm,stage=label,diagnostic_classification=diagnostic['classification'],
            first_qualified_backtrack=next((r['backtrack'] for r in half if r['passed']),None),
            original_rms_mm=original['metrics']['rms_mm'],rms_mm=result['metrics']['rms_mm'],
            hausdorff_upper_mm=result['metrics']['hausdorff_upper_mm'],
            recovered=result['recovered'],paired_recovered=result['paired_recovered'],
            maximum_residual=result['maximum_residual'],outcome=result['outcome'],detail=result['detail'],
            original_resolution_audit_passed=original_audit['passed'],
            final_audit_passed=audit['passed'],audit_resolution=[audit['production_resolution'],audit['refined_resolution']],
            fresh_fit_units=result['fresh_fit_units'],fit_units=result['fit_and_localization_units'],
            historical_units=result['historical_units'],fit_seconds=result['fit_and_localization_seconds'],
            fresh_seconds=result['fresh_seconds'],fresh_fit_seconds=result['fresh_fit_seconds'],
            promoted=result['resolution_promoted'],memory=result['memory'],
            original_candidate_discrepancy=max(refinement['original']['candidate_discrepancy']),
            finer_candidate_discrepancy=max(refinement['finer']['candidate_discrepancy']),
            last_stage=result['stages'][-1]['stage'],last_stop=result['stages'][-1]['stop'],
            new_trial_status_counts=dict(statuses),
            fresh_stages=[s for s in result['stages'] if 'nodes' in s])
        rows.append(row)
        descriptor=next(r for r in a.b.descriptors() if r['id']==case)
        problem,*_=a.inputs(case,arm,label)
        truth=curve_from(read(a.ROOT/descriptor['truth']))
        ax=axes.flat[index]
        for curve,color,style,name in ((truth,'#111111','-','Truth'),
              (curve_from(original['final_curve']),'#888888','--','FM-002 stopped'),
              (curve_from(result['final_curve']),'#1976b8','-','RB-001 endpoint')):
            z=curve.values(2048)*problem.length_unit_m*1000
            z=np.r_[z,z[0]]
            ax.plot(z.real,z.imag,color=color,ls=style,lw=1.7,label=name)
        short='C' if 'development_c' in case else 'Star'
        ax.set_title(f'{short} / {arm}: RMS {row["original_rms_mm"]:.3f} → {row["rms_mm"]:.3f} mm\n'
                     f'{row["outcome"]}; recovery {row["recovered"]}',fontsize=10)
        ax.set_aspect('equal',adjustable='datalim')
        ax.set_xlabel('x (mm)');ax.set_ylabel('y (mm)')
        ax.grid(alpha=.18)
        ax.legend(fontsize=8,loc='best')
    fig.suptitle('RB-001: four resumed FM-002 real-prefix failures\nUnchanged data, accuracy tolerances and recovery thresholds',fontsize=13)
    fig.savefig(output/'endpoints.png',dpi=180)
    plt.close(fig)
    comparison=dict(rows=rows,stage_a_budget=stage_a['budget'],qualification_seconds=qualification['seconds'],
        continuation_seconds=continuation['seconds'],numerical_seconds=continuation['numerical_seconds'],
        recovered=sum(r['recovered'] for r in rows),paired_recovered=sum(r['paired_recovered'] for r in rows),
        scope='Four development tails, resumed from archived accepted states; not new original-initialization runs')
    write(output/'comparison.json',comparison)
    lines=['# RB-001 — accuracy-controlled continuation','',
        'All four FM-002 stops reproduced. Refinement and smaller steps each independently removed every immediate obstruction. '
        'All four tails then continued under the same opt-in response, with historical work/time and stage quotas retained.','',
        '| Case / arm | RMS before → after (mm) | Hausdorff upper (mm) | Full / paired recovery | Audit 512/1024 · 1024/2048 | Outcome |',
        '|---|---:|---:|---|---|---|']
    for r in rows:
        short='C' if 'development_c' in r['case'] else 'Star'
        lines.append(f'| {short} / {r["arm"]} | {r["original_rms_mm"]:.5g} → {r["rms_mm"]:.5g} | '
            f'{r["hausdorff_upper_mm"]:.5g} | {r["recovered"]} / {r["paired_recovered"]} | '
            f'{r["original_resolution_audit_passed"]} · {r["final_audit_passed"]} | {r["outcome"]} |')
    lines+=['','![All four returned endpoints](endpoints.png)','',
        '## Work and execution','',
        '| Case / arm | Historical units | New fit units | Historical + new fit seconds | Fresh total seconds |',
        '|---|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f'| {r["case"]} / {r["arm"]} | {r["historical_units"]} | {r["fresh_fit_units"]} | '
                     f'{r["fit_seconds"]:.2f} | {r["fresh_seconds"]:.2f} |')
    lines+=['',f'Stage A: {stage_a["budget"]["units"]} dispatched units, {stage_a["budget"]["seconds"]:.2f} s. '
        f'Qualification: {qualification["seconds"]:.2f} s. '
        f'Continued fitting, audits and scoring: {continuation["seconds"]:.2f} s. '
        f'Total recorded numerical execution: {continuation["numerical_seconds"]:.2f} s of the 10,800 s ceiling.','',
        'Each continuation retains the 13,412-unit and 1,800-second fitting cap, including archived work and time. '
        'Replay and qualification are separately reported diagnostic overhead. Initial audits are reused as historical evidence; '
        'each endpoint gets a fresh final audit and, after promotion, the original N512/1024 audit as well.','',
        'N512/1024 fitting uses four frequency workers; N1024/2048 fitting uses one. Precision remains double/complex double. '
        'All runs are sequential. Backend timings, solver residuals, peak CUDA memory, process RSS, fallbacks and GPU process '
        'inventories are in each result receipt. These are single-run diagnostic timings, not matched speedup measurements. '
        'The external dispatch monitor counts public evaluation/derivative calls; the fit ledger also charges the frontier’s '
        'internal reciprocal batch. The latter governs the fitting cap.','',
        '## Evidence and reproducibility','',
        '- [Stage-A summary](stage_a.json) and [original archive verification](archive_verification.json).',
        '- [Qualification result](qualification/result.json), [tests](qualification/tests.log), '
        '[qualified source seal](qualification/manifest.json), [source differences](qualification/source_changes.patch).',
        '- [Continuation summary](continuation.json), [comparison](comparison.json), and per-case receipts under `runs/`.',
        '- Source/input/plan archives, full replay fields, reconstructed candidates and exact resume states are retained. '
        'Original FM-001/FM-002 files are unchanged.',
        '- Rebuild the comparison with `python -m experiments.relaxed_bie.report` in the documented EMNerf environment.','',
        'Recovery uses the existing full-matrix and unchanged paired contracts: RMS ≤1 mm, Hausdorff upper ≤2 mm, '
        'per-frequency residual limits and a passed numerical audit. No truth-based iterate selection is used. '
        'A resource or numerical stop is reported by its actual reason.','']
    (output/'README.md').write_text('\n'.join(lines))
    verify_phase(output)
    return comparison


def verify(output):
    phase_manifest=verify_phase(output)
    target=output/'final_verification.json'
    if target.exists():
        previous=read(target)
        for name,expected in previous['artifacts'].items():
            if digest(output/name)!=expected:
                raise ValueError('Changed sealed final artifact: '+name)
        if digest(Path(__file__))!=previous['report_script_sha256']:
            raise ValueError('Changed sealed report script')
        return previous
    assert digest(output/'manifest.json')==phase_manifest['stage_a_manifest_sha256']
    original_seal=read(output/'manifest.json')
    assert digest(output/'sources.tar.gz')==original_seal['source_archive_sha256']
    stage_a=read(output/'stage_a.json')
    qualification=read(output/'qualification/result.json')
    continued=read(output/'continuation.json')
    assert stage_a['completed']==continued['completed']==4
    assert stage_a['budget']['units']<=4000 and stage_a['budget']['seconds']<=1800
    assert qualification['passed'] and qualification['test_returncode']==0
    assert qualification['tests_sha256']==digest(output/'qualification/tests.log')
    assert all(r['passed'] for r in qualification['replays'])
    assert continued['numerical_seconds']<=10800
    # This conservative upper bound also includes engineering/idle time between
    # numerical phases and an allowance for the first short pre-seal checks.
    elapsed_upper_bound=time()-(output/'manifest.json').stat().st_mtime+120
    assert elapsed_upper_bound<=10800
    accounting=[]
    for case,arm,label in a.CASES:
        row=read(output/'runs'/case/arm/'result.json')
        dispatched=sum(r['counts']['evaluation_attempts']+r['counts']['derivative_attempts']
                       for r in row['execution_receipts'].values())
        charged=row['fresh_fit_units']+row['audit_units']
        assert dispatched==charged, (case,arm,dispatched,charged)
        assert row['fit_and_localization_units']<=13412
        for stage in row['stages']:
            work=stage['work']
            assert work['stage_quota'] is None or work['stage_units']<=work['stage_quota']
        expected=bool(row['final_audit_passed'] and row['metrics']['rms_mm']<=1 and
            row['metrics']['hausdorff_upper_mm']<=2 and row['relative_residual'] is not None and
            np.all(np.asarray(row['relative_residual'])<=row['residual_limits']))
        assert row['recovered']==expected
        accounting.append(dict(case=case,arm=arm,dispatched_new_work=dispatched,charged_new_work=charged,
            fitting_units=row['fit_and_localization_units'],fitting_seconds=row['fit_and_localization_seconds'],
            wall_stop=row['outcome']=='TRIAL_WALL_LIMIT',stage_and_global_work_caps_preserved=True))
    paths=sorted(p for p in output.rglob('*') if p.is_file() and p.name not in ('final_verification.json','reporting_verification.json'))
    result=dict(passed=True,artifacts={str(p.relative_to(output)):digest(p) for p in paths},
        report_script_sha256=digest(Path(__file__)),
        qualification_manifest_sha256=digest(output/'qualification/manifest.json'),
        original_archive_verified=True,accounting=accounting,
        numerical_seconds=continued['numerical_seconds'],
        elapsed_including_engineering_upper_bound_seconds=elapsed_upper_bound)
    write(target,result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=a.OUTPUT)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    print(verify(args.output) if args.verify else report(args.output))


if __name__=='__main__':
    main()
