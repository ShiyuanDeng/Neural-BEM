"""Continue batches 2--4 once the original CSI launcher has published and exited.

Use --dry-run for a read-only check. Never call campaign.main() here.
"""
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

import psutil
from scipy.io import loadmat
import numpy as np

from experiments.baselines.csi import campaign as base

RESUME_STATE = base.ROOT / 'resume_campaign.json'
RESUME_STATUS = base.ROOT / 'resume_status.json'
RESUME_SOURCES = base.ROOT / 'resume_sources.json'
ORIGINAL_REPORT = base.report


def read(path):
    return json.loads(path.read_text())


def budget_hours():
    hours = float((base.ROOT / 'resume_budget_hours.txt').read_text().strip())
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError('resume budget must be a finite positive number of hours')
    return hours


def inspect():
    """Read prerequisites without writing files or starting/stopping workers."""
    original = read(base.ROOT / 'campaign.json')
    started = dt.datetime.fromisoformat(original['started_utc'])
    hours = budget_hours()
    deadline = started + dt.timedelta(hours=hours)
    reasons = []
    pid = original['launcher_pid']
    if psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE:
        reasons.append(f'original launcher PID {pid} is still alive')
    if not original.get('finished_utc') or not original['state'].startswith('awaiting coordinator:'):
        reasons.append('original launcher has not finished in awaiting-coordinator state')
    if (base.ROOT / 'STOP').exists():
        reasons.append('existing STOP file is set; it will never be removed')
    if (base.ROOT / 'resume.lock').exists() or RESUME_STATE.exists():
        reasons.append('a resume has already claimed this campaign')
    for entry in read(base.ROOT / 'sources.json')['files']:
        if base.sha(base.REPO / entry['path']) != entry['sha256']:
            reasons.append(f"original source changed: {entry['path']}")
    for scene in base.BATCHES[0]:
        folder = base.ROOT / scene
        if not (folder / 'outcome.json').exists():
            reasons.append(f'batch-1 outcome pending: {scene}')
        elif read(folder / 'outcome.json')['state'] == 'completed':
            try:
                assert read(folder / 'launch.json')['returncode'] == 0
                assert read(folder / 'matlab_summary.json')['iterations'] == 2048
                counts = np.atleast_1d(loadmat(folder / 'final_contrast.mat', variable_names=['counts'])['counts'])
                assert counts.ravel().tolist() == [256, 512, 1024, 2048]
                assert [s['iterations'] for s in read(folder / 'scores.json')['snapshots']] == [256, 512, 1024, 2048]
            except (OSError, KeyError, AssertionError) as error:
                reasons.append(f'incomplete batch-1 evidence for {scene}: {error!r}')
    planned, skipped = [], []
    for batch, scenes in enumerate(base.BATCHES[1:], 2):
        for scene in scenes:
            folder = base.ROOT / scene
            if folder.exists():
                if (folder / 'outcome.json').exists():
                    skipped.append(scene)
                else:
                    reasons.append(f'existing unfinished directory will not be overwritten: {scene}')
            else:
                planned.append(dict(batch=batch, scene=scene))
    for process in psutil.process_iter(['pid', 'cmdline']):
        try:
            if 'MATLAB' not in Path((process.info['cmdline'] or [''])[0]).name:
                continue
            output = process.environ().get('CSI_OUT', '')
            if output and Path(output).is_relative_to(base.ROOT):
                reasons.append(f'CSI worker PID {process.pid} is still alive')
        except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
            continue
    return dict(original_started_utc=started.isoformat(), target_utc=deadline.isoformat(),
                budget_hours=hours, budget_seconds=hours * 3600, time_target_is_informational=True,planned=planned, preserved_outcomes=skipped,
                ready=not reasons, blocked_reasons=reasons)


def report(state):
    ORIGINAL_REPORT(state)
    path = base.ACT / 'results.md'
    record = read(RESUME_STATE)
    text = path.read_text().replace('Nine-hour budget.', f"{record['budget_hours']:g}-hour informational target on the original campaign clock.")
    text += ('\n## Resume after batch 1\n\n'
             f"Original start: {record['original_started_utc']}. Target time: {record['target_utc']}.\n"
             'The first-batch forecast above retains its original nine-hour check.\n'
             'The coordinator extended the total budget to twelve hours on 18 November; '
             'resume_budget_hours.txt is read at every stop check.\n'
             'Batches, settings, three-fit ceiling and the 14 GiB reserve are unchanged.\n'
             'Original campaign.json, status.json and STOP are preserved.\n'
             'Resume state, resource overlap and source hashes are in resume_campaign.json, '
             'resume_status.json, resume_overlap.jsonl and resume_sources.json.\n'
             'Each changed budget value used is recorded in resume_budget_history.jsonl.\n')
    text += 'The current user rule forbids time-based stops. Target overruns are recorded and workers continue.\n'
    path.write_text(text)


def manifest(folder):
    base.manifest(folder)
    path = folder / 'manifest.json'
    record = read(path)
    record['resume_source_manifest'] = str(RESUME_SOURCES)
    record['resume_command'] = read(RESUME_STATE)['command']
    base.write(path, record)


def status(state, batch, active=(), pending=()):
    record = dict(state=state, batch=batch, utc=base.now(),
                  elapsed_seconds=time.monotonic() - base.START,
                  active=[job['scene'] for job in active], pending=[s for s, _ in pending],
                  memory=base.memory(), matlab=base.live_jobs())
    campaign = read(RESUME_STATE)
    record.update(budget_hours=campaign['budget_hours'], target_utc=campaign['target_utc'])
    base.write(RESUME_STATUS, record)
    with (base.ROOT / 'resume_overlap.jsonl').open('a') as stream:
        stream.write(json.dumps(record) + '\n')
    report(state)
    print(json.dumps(record), flush=True)


def run(batch_one_commit):
    check = inspect()
    if not check['ready']:
        raise RuntimeError(json.dumps(check, indent=2))
    # The operator supplies the batch-1 commit only after checking the push.
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=base.REPO, text=True).strip()
    remote = subprocess.check_output(['git', 'ls-remote', 'origin', f'refs/heads/{branch}'], cwd=base.REPO, text=True).split()[0]
    subprocess.run(['git', 'merge-base', '--is-ancestor', batch_one_commit, remote], cwd=base.REPO, check=True)
    for scene in base.BATCHES[0]:
        path = str((base.ROOT / scene / 'outcome.json').relative_to(base.REPO))
        subprocess.run(['git', 'cat-file', '-e', f'{batch_one_commit}:{path}'], cwd=base.REPO, check=True)
    # Exclusive, permanent claim: a second invocation cannot rerun any case.
    with (base.ROOT / 'resume.lock').open('x') as stream:
        stream.write(f'{os.getpid()}\n')
    started = dt.datetime.fromisoformat(check['original_started_utc']).timestamp()
    base.START = time.monotonic() - (time.time() - started)
    signal.signal(signal.SIGTERM, base.handle_stop)
    signal.signal(signal.SIGINT, base.handle_stop)
    record = dict(**check, state='running', resumed_utc=base.now(), launcher_pid=os.getpid(),
                  command=['env', 'PYTHONPATH=solvers:.', os.sys.executable, '-B', '-m',
                           'experiments.baselines.csi.resume_campaign', '--batch-one-commit', batch_one_commit],
                  batch_one_commit=batch_one_commit, remote_commit_at_launch=remote,
                  memory_reserve_bytes=base.RESERVE, threads=8, max_workers=3)
    base.write(RESUME_STATE, record)
    last_budget = None
    target_notified = False

    def stopped():
        nonlocal last_budget,target_notified
        # Read the coordinator's small text file at EVERY stop check.
        # Invalid target text keeps the last valid target; it cannot end fits.
        try:
            hours = budget_hours()
        except (OSError, ValueError) as error:
            with (base.ROOT / 'resume_budget_history.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(utc=base.now(), error=repr(error), action='keep running')) + '\n')
            hours = last_budget if last_budget is not None else check['budget_hours']
        if hours != last_budget:
            deadline = dt.datetime.fromtimestamp(started + hours * 3600, dt.timezone.utc).isoformat()
            with (base.ROOT / 'resume_budget_history.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(utc=base.now(), budget_hours=hours, target_utc=deadline,
                    time_target_is_informational=True,elapsed_seconds=time.monotonic() - base.START)) + '\n')
            record.update(budget_hours=hours, budget_seconds=hours * 3600, target_utc=deadline)
            base.write(RESUME_STATE, record)
            last_budget = hours
            target_notified=False
        if (time.monotonic()-base.START>=hours*3600 or time.time()>=started+hours*3600) and not target_notified:
            event=dict(utc=base.now(),state='time target exceeded; workers continue',budget_hours=hours)
            with (base.ROOT/'resume_budget_history.jsonl').open('a') as stream:stream.write(json.dumps(event)+'\n')
            print(json.dumps(event),flush=True);target_notified=True
        return base.STOP or (base.ROOT / 'STOP').exists()

    base.stopped = stopped
    stopped()  # Record the first value used before any worker starts.
    source_paths = [p for p in base.CODE.rglob('*') if p.suffix in ('.py', '.m')]
    source_paths += list((base.REPO / 'external/patches/cc-csi').glob('*.patch'))
    base.write(RESUME_SOURCES, dict(utc=base.now(), original_source_manifest=str(base.ROOT / 'sources.json'),
               files=[dict(path=str(p.relative_to(base.REPO)), sha256=base.sha(p)) for p in sorted(source_paths)]))
    base.report = report
    overall = 'running'; max_workers = 3; batch = 1
    try:
        for batch, scenes in enumerate(base.BATCHES[1:], 2):
            if base.stopped():
                overall = 'stopped before batch; available snapshots preserved'; break
            pending = []; active = []
            for scene in scenes:
                folder = base.ROOT / scene
                if folder.exists():
                    if (folder / 'outcome.json').exists():
                        continue
                    raise RuntimeError(f'refusing existing unfinished case: {folder}')
                if base.stopped():
                    overall = 'stopped; available snapshots preserved'; break
                folder.mkdir(exist_ok=False)
                try:
                    okay = base.generate(scene, folder)
                except Exception as error:
                    (folder / 'preparation_failure.txt').write_text(repr(error) + '\n'); okay = False
                if okay:
                    pending.append((scene, folder))
                else:
                    base.write(folder / 'outcome.json', dict(state='data generation failed or stopped', utc=base.now()))
            if base.stopped():
                overall = 'stopped; available snapshots preserved'
            last_progress = -100
            while pending or active:
                if base.stopped():
                    for job in active:
                        base.terminate(job, 'user-requested stop or signal')
                    for scene, folder in pending:
                        base.write(folder / 'outcome.json', dict(state='not started before stop', utc=base.now()))
                    pending.clear(); overall = 'stopped; available snapshots preserved'
                if active and base.memory()['MemAvailable'] < base.RESERVE:
                    max_workers = min(max_workers, 2)
                    base.terminate(active[-1], 'memory reserve; worker limit reduced to two')
                while pending and len(active) < max_workers and not base.stopped():
                    current = sum(j.get('family', 0) for j in active)
                    if base.memory()['MemAvailable'] + current < base.RESERVE + (len(active) + 1) * base.FIT_RSS:
                        break
                    scene, folder = pending.pop(0)
                    job = base.inversion(scene, folder); active.append(job)
                    job['record']['resume_source_manifest'] = str(RESUME_SOURCES)
                    base.write(folder / 'launch.json', job['record'])
                for job in list(active):
                    base.sample(job)
                    try:
                        base.score(job['folder'])
                    except (OSError, ValueError) as error:
                        (job['folder'] / 'scoring_retry.txt').write_text(repr(error) + '\n')
                    if job['process'].poll() is not None:
                        rc = base.finish(job); base.score(job['folder']); base.cost_history(job['folder'])
                        base.write(job['folder'] / 'outcome.json', dict(state='completed' if rc == 0 else 'fit failed', returncode=rc, utc=base.now()))
                        manifest(job['folder']); active.remove(job)
                elapsed = time.monotonic() - base.START
                if elapsed - last_progress >= 30:
                    status(overall, batch, active, pending); last_progress = elapsed
                if pending or active:
                    time.sleep(1)
            for scene in scenes:
                folder = base.ROOT / scene
                if folder.exists() and scene not in check['preserved_outcomes']:
                    manifest(folder)
            status(overall, batch)
            base.publish(f'resume batch {batch} {overall}')
            if overall != 'running':
                break
        if overall == 'running':
            overall = 'completed all ten outcomes'
    except BaseException:
        import traceback
        overall = 'resume failed; evidence preserved'
        (base.ROOT / 'resume_failure.txt').write_text(traceback.format_exc())
        for job in list(base.JOBS):
            try:
                base.terminate(job, 'resume exception'); rc = base.finish(job)
                base.score(job['folder']); base.cost_history(job['folder'])
                base.write(job['folder'] / 'outcome.json', dict(state='fit failed', returncode=rc, utc=base.now()))
                manifest(job['folder'])
            except Exception:
                with (base.ROOT / 'resume_failure.txt').open('a') as stream:
                    stream.write(traceback.format_exc())
        raise
    finally:
        record.update(state=overall, finished_utc=base.now(), wall_seconds=time.monotonic() - base.START)
        base.write(RESUME_STATE, record)
        status(overall, batch)
        base.publish(overall)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--batch-one-commit')
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps(inspect(), indent=2))
    elif not args.batch_one_commit:
        parser.error('--batch-one-commit is required after confirming the batch-1 push')
    else:
        run(args.batch_one_commit)


if __name__ == '__main__':
    main()
