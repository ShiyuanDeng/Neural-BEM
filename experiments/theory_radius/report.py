"""Rebuild TR summaries and validate saved evidence without repeating solves."""
import argparse
from collections import Counter
import numpy as np
from .common import *


def compact(value):
    return '—' if value is None else f'{value:.4g}'


def report(phase):
    folder = OUTPUT/phase
    verify(folder)
    completed = (folder/'completion.json').exists()
    receipt = read(folder/('completion.json' if completed else 'failure.json'))
    lines = [f'# {phase}: theory diagnostic evidence', '',
             'Empirical finite-dimensional diagnostics. No certified convergence radius or new recovery claim.', '',
             f'Execution complete: **{completed}**. Numerical wall time: **{receipt["work"]["seconds"]:.1f} s**. '
             f'Forward frequency solves: **{receipt["work"]["frequency_solves_completed"]}**; '
             f'derivative batches: **{receipt["work"]["derivatives"]}**.', '',
             'Source/input hashes, source archive, execution settings and concurrent processes are in '
             '[manifest.json](manifest.json). Timings with other campaign activity are not matched benchmarks.', '']
    metrics = dict(phase=phase, complete=completed, work=receipt['work'])
    if phase == 'TR-001':
        rows_ = [read(p) for p in sorted((folder/'rows').glob('*.json'))]
        qualified = [r for r in rows_ if r['qualification']['passed'] and r.get('complete')]
        metrics.update(rows=len(rows_), qualified=len(qualified), expected=40,
                       refusals=sum('refused' in p for r in rows_ for p in r['probes']))
        lines += [f'Qualified band/catalog rows: **{len(qualified)}/{len(rows_)}**, expected 40.', '',
            'L_sample is a finite sample estimate of a supremum, not an upper bound. '
            'The displayed radii therefore have no certification status. Directions and radii are fixed '
            'in the plan; coefficients measure physical RMS mm in the fixed chart.', '',
            'Four-frequency (0.5–1.25 GHz) results:', '',
            '| Case | Catalog | M | Paired radius (mm) | Full radius (mm) | Full/paired |',
            '|---|---|---:|---:|---:|---:|']
        pairs=[]
        for r in qualified:
            p = next(e for e in r['estimates'] if e['frequencies']==4 and e['paired'])
            f = next(e for e in r['estimates'] if e['frequencies']==4 and not e['paired'])
            ratio=f['rho_sample_mm']/p['rho_sample_mm'] if p['rho_sample_mm'] else None
            lines.append(f'| {r["case"]} | {r["catalog"]} | {r["M"]} | {compact(p["rho_sample_mm"])} | {compact(f["rho_sample_mm"])} | {compact(ratio)} |')
            pairs.append(dict(case=r['case'],catalog=r['catalog'],M=r['M'],paired=p,full=f,ratio=ratio))
        checks=[p for r in qualified for p in r['radius_checks'] if 'tcc' in p]
        metrics.update(four_frequency=pairs, radius_checks=len(checks),
                       tcc_exceeds_half=sum(p['tcc']>.5 for p in checks),
                       max_checked_tcc=max((p['tcc'] for p in checks),default=None),
                       unresolved_sigma=sum(not e['sigma_resolved'] for r in qualified for e in r['estimates']))
        lines += ['',f'Additional radius probes: {len(checks)}; ratios above 1/2: {metrics["tcc_exceeds_half"]}. '
                  'Passing sampled probes does not establish a uniform TCC. Baseline spectra include '
                  'the 19-frequency stack; nonlinear probes use only the four early frequencies.', '',
                  'Per-band qualification, refusals, individual probes and weak directions are under `rows/`. '
                  'Compressed per-frequency Gram matrices and baseline spectra are retained separately.', '']
        if pairs:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
            for ax, case in zip(axes.flat, CASES):
                for catalog, style in (('real', '-'), ('damped', '--')):
                    rr=[r for r in pairs if r['case']==case and r['catalog']==catalog]
                    rr.sort(key=lambda r:r['M'])
                    for acq, color in (('paired','tab:blue'),('full','tab:orange')):
                        ax.semilogy([r['M'] for r in rr],[r[acq]['rho_sample_mm'] for r in rr],
                                    style+'o',color=color,label=catalog+' '+acq)
                ax.set(title=case.replace('modal__',''),xlabel='Normal update band M',ylabel='Empirical radius (RMS mm)')
                ax.grid(alpha=.2)
            axes[0,0].legend(fontsize=8)
            fig.suptitle('Sampled local-radius diagnostics — not certificates')
            fig.savefig(folder/'radius.png',dpi=150)
            plt.close(fig)
            lines += ['![Empirical radius](radius.png)', '']
        valid = completed and len(rows_)==40
    elif phase == 'TR-002':
        rows_=[read(p) for p in sorted((folder/'rows').glob('*.json'))]
        metrics.update(rows=len(rows_), graph_valid=sum(r['normal_graph']['valid'] for r in rows_),
            applicable=sum(r['applicable'] for r in rows_), passed=sum(r.get('indicator_pass',False) for r in rows_),
            reasons=dict(Counter(r['reason'] for r in rows_)))
        lines += ['| Case | Full data | Transition | Graph valid | Applicable | Indicator passes |',
                  '|---|---|---|---|---|---|']
        for r in rows_:
            lines.append(f'| {r["case"]} | {r["full"]} | {r["first"]} → {r["second"]} | {r["normal_graph"]["valid"]} | {r["applicable"]} | {r.get("indicator_pass", "—")} |')
        lines += ['', 'Inapplicable is not a failed recovery prediction: the sufficient local argument '
                  'does not apply to that endpoint. These retrospective numbers use truth and cannot '
                  'be an online scheduling rule. Sampled chart tests and truncation measurements are '
                  'not continuum bounds.', '']
        valid=completed and len(rows_)==24
    else:
        endpoints=[read(p) for p in sorted((folder/'endpoints').glob('*.json'))]
        branches=[read(p) for p in sorted((folder/'branches').glob('*.json'))]
        metrics.update(endpoints=[{k:r[k] for k in ('case','full','archive_stop','numerical_qualification',
            'stationary_at_declared_tolerance','curvature','hessian_error_relative')} for r in endpoints],
            branches=[dict(case=r['case'],stop=r.get('stop'),complete=r.get('complete'),
                           fold_candidates=r.get('fold_candidates'),fold_claim=r.get('fold_claim')) for r in branches])
        lines += ['| Case | Full data | Qualified | Stationary at 1e-8/mm | Curvature |',
                  '|---|---|---|---|---|']
        for r in endpoints:
            lines.append(f'| {r["case"]} | {r["full"]} | {r["numerical_qualification"]} | {r["stationary_at_declared_tolerance"]} | {r["curvature"]} |')
        lines += ['', 'The Hessian includes residual curvature in the affine production-tangent chart. '
                  'Actual finite production trials and their acceptance margins are recorded separately.', '',
                  '| Case | Branch stop | Accepted steps | Fold candidates | Interpretation |',
                  '|---|---|---:|---:|---|']
        for r in branches:
            lines.append(f'| {r["case"]} | {r.get("stop")} | {len(r["path"])-1} | {r.get("fold_candidates")} | {r.get("fold_claim")} |')
        lines += ['', 'These are bounded, truth-free data-homotopy paths in a fixed low-band chart, '
                  'not the moving-chart production frequency ladder. Their limits do not establish '
                  'absence of folds elsewhere or justify complex continuation by themselves.', '']
        if phase == 'TR-003-branches':
            parent=read(folder/'parent.json')
            for name, value in parent['files'].items():
                if digest(ROOT/name) != value:
                    raise ValueError('Retained endpoint evidence changed: '+name)
            metrics['parent_work']=parent['work']
            metrics['combined_seconds']=parent['work']['seconds']+receipt['work']['seconds']
            metrics['combined_frequency_solves']=parent['work']['frequency_solves_completed']+receipt['work']['frequency_solves_completed']
            lines += ['The four endpoint audits above are reused unchanged from the preserved '
                      'TR-003 attempt; only the two branches were executed in this continuation. '
                      f'Combined numerical wall time: {metrics["combined_seconds"]:.1f} s; '
                      f'combined forward frequency solves: {metrics["combined_frequency_solves"]}. '
                      'Parent hashes and consumed budget are in `parent.json`.', '']
        valid=completed and len(endpoints)==4 and len(branches)==2 and all(r.get('complete') for r in branches)
    metrics['artifact_validation_passed']=valid
    write(folder/'summary.json',metrics)
    (folder/'README.md').write_text('\n'.join(lines)+'\n')
    write(folder/'validation.json',dict(passed=valid, files={str(p.relative_to(folder)):digest(p)
        for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='validation.json'}))
    print(phase, 'validation', valid, 'seconds',receipt['work']['seconds'],flush=True)
    if not valid:
        raise SystemExit(1)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('phase', choices=('TR-001','TR-002','TR-003','TR-003-branches'))
    report(parser.parse_args().phase)
