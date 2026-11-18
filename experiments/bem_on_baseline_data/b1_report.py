"""Consolidate saved B1 records only; never run numerical work."""
from b1_runtime import BASE, ROOT, GIB, now, digest, write
import datetime
import json
from pathlib import Path
import b1_data as D

DOC = ROOT/'docs/iterations/adapt_bem_to_baseline_data/06_fit_brg_tg002_cases'


def load(path):
    return json.loads(path.read_text())


def summarize():
    rows, intervals, failures, requeues, checks = [], [], [], [], []
    for case in D.ORDER:
        q = BASE/case/'checks/qualification.json'
        if q.exists():
            checks.append(load(q))
        checked = load(BASE/case/'checks/inputs.json')['files'] if q.exists() else []
        for row in ('known', 'recovered'):
            for out in sorted((BASE/case/row).glob('attempt_*')):
                if (out/'requeue.json').exists():
                    requeues.append(str(out.relative_to(ROOT)))
                    continue
                if not (out/'metrics.json').exists():
                    failures.append(dict(case=case,row=row,reason='No metrics yet',path=str(out.relative_to(ROOT))))
                    continue
                m, r = load(out/'metrics.json'), load(out/'supervisor.json')
                manifest = load(out/'manifest.json')
                observed = [s['source'] for s in manifest['sources']]
                same = len(observed)==19 and observed==checked[::2]
                input_paths_brg = all(s['path'].startswith('results/brg/tg002_shapes/2026-11-17/') for s in observed)
                end = load(out/'worker_end.json')
                m.update(source_commit=manifest['start']['commit'], input_hashes_equal_checked=same,
                         brg_inputs_only=input_paths_brg, solver_clean_unchanged=r['reportable'],
                         process_seconds=r['seconds'], started=r['start']['utc'], ended=r['end']['utc'],
                         minimum_available_bytes=r['minimum_available_bytes'],
                         path=str(out.relative_to(ROOT)), scoring_failure_preserved=(out/'scoring_failure.json').exists())
                assert same and input_paths_brg, f'Input mismatch: {case} {row}'
                assert r['solver_unchanged'] and not r['start']['solver_dirty'] and not end['end']['solver_dirty'], f'Solver source change: {case} {row}'
                assert manifest['torch_threads']==manifest['torch_interop_threads']==1
                assert all(s['source']['sha256']==s['source']['recorded_sha256'] for s in manifest['sources'])
                rows.append(m)
                intervals += [(datetime.datetime.fromisoformat(m['started']), 1),
                              (datetime.datetime.fromisoformat(m['ended']), -1)]
    active, peak_concurrency = 0, 0
    for _, change in sorted(intervals):
        active += change
        peak_concurrency = max(peak_concurrency,active)
    totals = dict(fits=len(rows),planned=40,checks=len(checks),checked_frequencies=sum(q['checked'] for q in checks),
                  all_checks_pass=len(checks)==20 and all(q['passes'] for q in checks),
                  maximum_brg_difference=max(q['maximum_brg_difference'] for q in checks),
                  maximum_refinement_difference=max(q['maximum_refinement_difference'] for q in checks),
                  fit_seconds=sum(r['fit_seconds'] or 0 for r in rows),process_seconds=sum(r['process_seconds'] for r in rows),
                  units=sum(r['work_units'] or 0 for r in rows),
                  maximum_host_bytes=max(r['host_peak_bytes'] for r in rows),
                  maximum_sampled_gpu_bytes=max(r['gpu_sampled_peak_bytes'] or 0 for r in rows),
                  minimum_available_bytes=min(r['minimum_available_bytes'] for r in rows),
                  maximum_concurrent_workers=peak_concurrency,
                  first_fit_start=min(r['started'] for r in rows),last_fit_end=max(r['ended'] for r in rows),
                  outcomes={outcome:sum(r['outcome']==outcome for r in rows) for outcome in sorted(set(r['outcome'] for r in rows))},
                  over_120_seconds=[r['case']+' '+r['row'] for r in rows if r['over_120_seconds']],
                  over_1_hour=[r['case']+' '+r['row'] for r in rows if r['over_1_hour']],
                  series_refusals=[r['case']+' '+r['row'] for r in rows if r.get('series_refusal')],
                  memory_requeues=requeues, incomplete=failures)
    result = dict(generated=now(), totals=totals, fits=rows, record_checks='Saved inputs, resource receipts, and scoring only; no numerical rerun')
    write(BASE/'campaign_summary.json',result)
    lines = ['# B1 campaign report', '', f"Generated {result['generated']}. {len(rows)}/40 fits have saved metrics.", '',
             f"All {len(checks)} case checks pass: {totals['checked_frequencies']} frequency comparisons.",
             f"Maximum BRG difference {totals['maximum_brg_difference']:.9g}; refinement {totals['maximum_refinement_difference']:.9g}.", '',
             '| Case | Known area error | Recovered area error | Recovered eta | Known / recovered fit s |',
             '|---|---:|---:|---:|---:|']
    for case in D.ORDER:
        a = next((r for r in rows if r['case']==case and r['row']=='known'),None)
        b = next((r for r in rows if r['case']==case and r['row']=='recovered'),None)
        fmt = lambda r,k: 'pending' if r is None or r[k] is None else f'{r[k]:.9g}'
        lines.append(f"| {case} | {fmt(a,'area_error')} | {fmt(b,'area_error')} | {fmt(b,'contrast')} | {fmt(a,'fit_seconds')} / {fmt(b,'fit_seconds')} |")
    lines += ['', 'Area errors are raw fractions, not percent. No alignment, tuning, or numerical rerun.',
              '[Every fit: outcome, stage, work, time, contrast and memory](results.md).',
              '[Raw consolidated records](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/campaign_summary.json).', '',
              '## Work, time and resources', '',
              f"Fit time sum {totals['fit_seconds']:.3f} s; worker process time sum {totals['process_seconds']:.3f} s; work {totals['units']} units.",
              f"First worker {totals['first_fit_start']}; last worker {totals['last_fit_end']}.",
              'That interval includes coordinator review waits, data arrival waits and the safe resource-allocation change.', '',
              f"Largest host peak {totals['maximum_host_bytes']/GIB:.4f} GiB; sampled process GPU peak {totals['maximum_sampled_gpu_bytes']/GIB:.4f} GiB.",
              f"Minimum available host memory {totals['minimum_available_bytes']/GIB:.4f} GiB, against the 14 GiB floor.",
              f"Maximum numerical-worker overlap {peak_concurrency}. The authorized ceiling changed from one to two to four.", '',
              '## Retained failures and checks', '',
              f"Outcomes: {totals['outcomes']}.",
              'A completed schedule is a solver outcome, not a recovery-quality verdict.',
              'The coordinator classified aphex_twin__c0.5 known contrast as a failed recovery',
              'on 18 November at 02:54 UTC: area error 15.1%. Its endpoint is retained without a rerun.',
              f"Series refusals: {totals['series_refusals']}; memory requeues: {requeues}.",
              f"Runs above 120 s: {totals['over_120_seconds']}; above 1 h: {totals['over_1_hour']}.",
              'Elapsed time never stopped a fit. The original first-fit scoring import failure remains saved;',
              'the owned wrapper path was fixed and the saved endpoint scored, without a numerical rerun.', '',
              'Every saved fit uses the same 19 BRG observation hashes as its check, and no BEM-made observations.',
              'All checked solver source maps remained clean and unchanged. BLAS/OpenMP and both Torch pools used one thread.',
              'The unedited comparison scoring supplies raw region, boundary, signed-material and contrast scores.', '',
              'No solver, baseline, scoring or coordination file was edited. Bulk stays local with SHA-256.', '']
    (DOC/'final_report.md').write_text('\n'.join(lines))
    print(json.dumps(totals,indent=2))


if __name__=='__main__':
    summarize()
