"""Reported BRG GPU queue, with one allowed retry after a host-memory kill."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

from brg_paper import (BASE, CASES, GIB, LADDER, ROOT, available_memory, bulk_manifest,
                       fit_case, fixed_resolution, now, solver_state, write, score_endpoint)

DOCS = ROOT/'docs/iterations/adapt_bem_to_baseline_data/02_fit_brg_paper_cases'
CODE = [ROOT/'experiments/bem_on_baseline_data/brg_paper.py', Path(__file__).resolve()]
MEMORY_STOP = 'memory reserve below 14 GiB'
REPORTED_CASES = ('glider_033', 'glider_10', 'star_full', 'star_limited')
SKIP_REASON = "skipped by the user's decision: the series limit refuses the true shape above k = 8"


def short_reason(metrics, supervisor):
    if supervisor.get('stop_reason'):
        return supervisor['stop_reason']
    detail = str(metrics.get('detail') or '')
    if 'cancellation' in detail:
        return metrics.get('outcome', 'failure')+' (series cancellation)'
    return metrics.get('outcome', 'missing endpoint')


def compare_cpu(case, out):
    """Score saved accepted states only; no additional fit or forward solve."""
    import numpy as np
    from bem_inverse.io import curve_from
    from experiments.baselines.brg.brg_data import true_curve
    from brg_paper import shape_info
    from experiments.comparison.scoring import region, region_scores
    cpu_path = BASE/case/'cpu_fit/local/accepted.json'
    gpu_path = out/'local/accepted.json'
    if not cpu_path.exists() or not gpu_path.exists():
        write(out/'cpu_comparison.json', dict(available=False, reason='Missing accepted states'))
        return
    cpu = json.loads(cpu_path.read_text())['states']
    gpu = json.loads(gpu_path.read_text())['states']
    common = sorted({r['active_frequency_count'] for r in cpu} & {r['active_frequency_count'] for r in gpu})
    if not common:
        write(out/'cpu_comparison.json', dict(available=False, reason='No shared accepted frequency stage'))
        return
    count = common[-1]
    c = [r for r in cpu if r['active_frequency_count'] == count][-1]
    g = [r for r in gpu if r['active_frequency_count'] == count][-1]
    cc, gc = curve_from(c['curve']), curve_from(g['curve'])
    truth = true_curve(shape_info(case)['shape'])
    actual, _ = region([truth.values(16384)])
    cp, _ = region([cc.values(16384)])
    gp, _ = region([gc.values(16384)])
    cs, gs = region_scores(cp, actual), region_scores(gp, actual)
    relative = region_scores(gp, cp)
    record = dict(available=True, common_k=LADDER[count-1],
          cpu_iteration=c['iteration'], gpu_stage_endpoint_iteration=g['iteration'],
          cpu_stage_was_cut_by_time=count == cpu[-1]['active_frequency_count'],
          cpu_area_error=cs['area_error'], gpu_area_error=gs['area_error'],
          delta_area_error=gs['area_error']-cs['area_error'],
          cpu_residual=c['maximum_stage_residual'], gpu_residual=g['maximum_stage_residual'],
          gpu_vs_cpu_area_error_normalized_by_cpu_area=relative['area_error'],
          cpu_accepted_work_units=c['units'], gpu_accepted_work_units=g['units'],
          raw_cpu_scores=cs, raw_gpu_scores=gs, raw_gpu_vs_cpu_scores=relative)
    matching = [r for r in gpu if r['active_frequency_count'] == count and r['iteration'] == c['iteration']]
    if matching:
        matched = matching[-1]
        z, w = cc.values(1024), curve_from(matched['curve']).values(1024)
        record['same_iteration'] = dict(iteration=c['iteration'],
              relative_curve_difference=float(np.linalg.norm(w-z)/np.linalg.norm(z)),
              maximum_point_difference=float(abs(w-z).max()),
              cpu_residual=c['maximum_stage_residual'], gpu_residual=matched['maximum_stage_residual'],
              cpu_accepted_work_units=c['units'], gpu_accepted_work_units=matched['units'])
    write(out/'cpu_comparison.json', record)


def commit_attempt(case, out, record):
    progress = DOCS/'gpu_pass_progress.md'
    paths = [*CODE, DOCS/'plan.md', DOCS/'results.md', progress, BASE/'gpu_pass.json', BASE/'gpu_skips.json', BASE/case/'cuda_fit']
    relative = [str(p.relative_to(ROOT)) for p in paths]
    subprocess.run(['git', 'add', '--', *relative], cwd=ROOT, check=True)
    subprocess.run(['git', 'diff', '--cached', '--check', '--', *relative], cwd=ROOT, check=True)
    subprocess.run(['git', 'commit', '-q', '-m', f'Record BRG {case} GPU {out.name}', '--', *relative], cwd=ROOT, check=True)
    subprocess.run(['git', 'push', 'origin', 'organised'], cwd=ROOT, check=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    record['commits'].append(dict(case=case, attempt=out.name, commit=commit))
    write(BASE/'gpu_pass.json', record)


def finish_attempt(record, case, out, elapsed):
    supervisor = json.loads((out/'supervisor.json').read_text())
    if not (out/'metrics.json').exists():
        score_endpoint(case, out)
    metrics = json.loads((out/'metrics.json').read_text()) if (out/'metrics.json').exists() else dict(outcome='SCORING_FAILURE')
    number = int(out.name.split('_')[-1])
    memory_killed = supervisor.get('stop_reason') == MEMORY_STOP
    started_fit = supervisor.get('returncode') is not None
    if started_fit:
        record['launched_fits'][case] += 1
    reportable = supervisor.get('reportable', False) and not memory_killed
    try:
        compare_cpu(case, out)
    except Exception as error:
        write(out/'comparison_failure.json', dict(exception=repr(error)))
    metrics.update(reported_result=reportable, memory_killed_not_a_result=memory_killed,
                   stop_reason=short_reason(metrics, supervisor), attempt=number)
    if case.startswith('star') and 'cancellation' in str(metrics.get('detail') or ''):
        metrics['series_refusal_pending_user_decision'] = True
    write(out/'metrics.json', metrics)
    write(out/'bulk_manifest.json', dict(files=bulk_manifest(out)))
    item = dict(case=case, attempt=number, path=str(out.relative_to(ROOT)), metrics=metrics,
                supervisor=supervisor, memory_killed_not_a_result=memory_killed)
    record['attempts'].append(item)
    if not started_fit:
        record['queue'].insert(0, case)
    elif memory_killed and record['memory_retries'][case] == 0:
        record['memory_retries'][case] += 1
        record['queue'].append(case)
    else:
        record['completed'][case] = item
        write(BASE/case/'cuda_fit/reported_attempt.json', dict(attempt=number, reported_result=reportable,
              path=str(out.relative_to(ROOT)), stop_reason=metrics['stop_reason']))
    record['active'] = None
    record['wall_seconds'] = elapsed
    write(BASE/'gpu_pass.json', record)
    area = metrics.get('area_error')
    area_text = f'{100*area:.6g}%' if area is not None else 'none'
    summary = (f'{case}: last k={metrics.get("final_active_k")}; stop={metrics["stop_reason"]}; '
               f'area error={area_text}; time={supervisor["wall_seconds"]:.3f}s')
    print(summary, flush=True)
    with (DOCS/'gpu_pass_progress.md').open('a') as stream:
        stream.write(f'\n## {case}, {out.name}, {now()}\n\n{summary}\n\n')
        stream.write(f'Reported result: {reportable}; memory-killed attempts are not results.\n')
    commit_attempt(case, out, record)


def main():
    selection = fixed_resolution()
    assert selection['fixed_K'] == 192
    subprocess.run(['git', 'merge-base', '--is-ancestor', '3612f5195', 'HEAD'], cwd=ROOT, check=True)
    path = BASE/'gpu_pass.json'
    progress = DOCS/'gpu_pass_progress.md'
    if path.exists():
        record = json.loads(path.read_text())
        if record.get('status') == 'complete':
            raise RuntimeError('Reported queue is already complete; do not rerun it.')
        old_pid = record['pid']
        try:
            os.kill(old_pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError(f'Old queue supervisor {old_pid} is still alive; do not duplicate it.')
        record.setdefault('queue_handoffs', []).append(dict(previous_pid=old_pid, resumed=now(),
              reason='Apply user cavity skips between numerical fits; no fit rerun.'))
        record['pid'] = os.getpid()
    else:
        assert not progress.exists()
        progress.write_text('# BRG paper cases: reported GPU pass\n\nFixed K=192; sequential queue; timings are indicative with GPU sharing.\n')
        record = dict(started=now(), pid=os.getpid(), solver_start=solver_state(), fixed_K=192,
              scientific_settings='Identical to CPU pass; cuda execution and 3600 s ceiling.',
              queue=list(REPORTED_CASES), completed={}, attempts=[], memory_retries={case: 0 for case in REPORTED_CASES},
              launched_fits={case: 0 for case in REPORTED_CASES}, commits=[], active=None,
              launch_rule=dict(expected_fit_bytes=1.5*GIB, minimum_remaining_bytes=14.5*GIB,
                               kill_below_available_bytes=14*GIB), status='running')
    record['queue'] = [case for case in record['queue'] if case in REPORTED_CASES]
    record['skipped'] = {case: dict(status='SKIPPED_BY_USER', reason=SKIP_REASON,
                                  reported_score=None, decision='18 November 2026, about 01:05 UTC')
                         for case in ('cavity_09', 'cavity_2')}
    write(BASE/'gpu_skips.json', record['skipped'])
    write(path, record)
    def elapsed():
        return (datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(record['started'])).total_seconds()
    if record['active']:
        case = record['active']['case']
        out = ROOT/record['active']['directory']
        assert (out/'supervisor.json').exists(), 'Active native fit has not returned; never restart it.'
        finish_attempt(record, case, out, elapsed())
    last_wait_notice = -60.
    while record['queue']:
        case = record['queue'][0]
        available = available_memory()
        state = solver_state()
        if available-1.5*GIB < 14.5*GIB or state['solver_dirty']:
            if time.monotonic()-last_wait_notice >= 30:
                last_wait_notice = time.monotonic()
                record['waiting'] = dict(case=case, since=now(), available_bytes=available,
                                          solver_dirty=state['solver_dirty'])
                write(path, record)
                print(f'WAIT {case}: available={available/GIB:.3f} GiB; solver_dirty={state["solver_dirty"]}', flush=True)
            time.sleep(2)
            continue
        record.pop('waiting', None)
        record['queue'].pop(0)
        number = len(list((BASE/case/'cuda_fit').glob('attempt_*')))+1
        out = BASE/case/'cuda_fit'/f'attempt_{number:02d}'
        record['active'] = dict(case=case, directory=str(out.relative_to(ROOT)),
              started=now(), available_bytes=available, solver_start=state)
        write(path, record)
        print(f'LAUNCH {case} {out.name}: available={available/GIB:.3f} GiB', flush=True)
        out = fit_case(case, 'cuda', attempt=number)
        finish_attempt(record, case, out, elapsed())
    record.update(status='complete', ended=now(), wall_seconds=elapsed(), solver_end=solver_state())
    write(path, record)
    print(f'GPU QUEUE COMPLETE: {len(record["completed"])} cases, {len(record["attempts"])} attempts, {record["wall_seconds"]:.3f}s', flush=True)


if __name__ == '__main__':
    main()
