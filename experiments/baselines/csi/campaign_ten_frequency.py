"""Ten frozen-data MF-CC-CSI fits at ten frequencies, started only from coordinator releases.

A copy of campaign_five_frequency.py with the band, the shapes and the folders changed.
The numerical method, the settings and the scoring are the same. Differences:
- ten frequencies, 0.25 to 2.5 GHz, and all ten shapes;
- the number of fits at once comes from this campaign's own ceiling.json, because the
  shared resource monitor has exited and left results/csi/resource_policy.json at zero;
- a new fit starts only if 14 GiB plus a 2 GiB margin stays free after its reservation;
- the live table goes to progress.md; results.md is written by hand after the run.
"""
import argparse
import datetime as dt
import fcntl
import gzip
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time
import traceback

import numpy as np
from scipy.io import loadmat

from experiments.baselines.csi import campaign as base
from experiments.baselines.csi import campaign_low_band as selected

ROOT = base.REPO / 'results/csi/tg002/2026-11-18_ten_frequency'
ACT = base.REPO / 'docs/iterations/csi_adaptation/08_run_cases_at_ten_frequencies'
DATA = base.REPO / 'results/csi/tg002/2026-11-18_ten_frequency_data'
TRUTH = base.REPO / 'results/csi/tg002/2026-11-18_low_band_data'
POLICY = ROOT / 'ceiling.json'  # Owned by the coordinator; re-read before every launch.
SHAPES = ['star', 'hook', 'circle', 'kite', 'asymmetric', 'cross', 'cog', 'c_shape', 'peanut', 'aphex_twin']
FREQUENCIES = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5]
ROWS = 1764 * len(FREQUENCIES)
FIT_RSS = 8 * base.GIB  # Measured: 5.3 GiB at five and 6.5 GiB at eight frequencies.
MARGIN = 2 * base.GIB  # Kept free above the 14 GiB floor when a fit is launched.
TARGET_HOURS = 14  # Information only. Never a reason to stop or stop launching.
OWN_CODE = ['campaign_ten_frequency.py']
RECORD = None
SOURCE = None
EVENT_TIMES = {}


def now():
    return subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%S+00:00'], text=True).strip()


def read(path):
    return json.loads(path.read_text())


def configure():
    base.ROOT = ROOT
    base.ACT = ACT
    base.now = now
    base.STOP = False
    base.FIT_RSS = FIT_RSS
    selected.ROOT = ROOT
    selected.FREQUENCIES = FREQUENCIES
    selected.CURRENT_SOURCE = SOURCE


def ceiling():
    try:
        record = read(POLICY)
    except FileNotFoundError:
        return 0
    value = record['max_csi_fits']
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError('max_csi_fits must be a nonnegative integer')
    return value


def frozen_input(scene):
    if scene not in SHAPES:
        raise ValueError(f'not an approved shape: {scene}')
    path = DATA / scene / 'forward/synthetic_input.txt'
    expected = path.with_suffix('.txt.sha256').read_text().split()[0]
    actual = base.sha(path)
    if actual != expected:
        raise ValueError(f'SHA-256 mismatch: {path}')
    table = np.loadtxt(path)
    if table.shape != (ROWS, 7) or not np.isfinite(table).all():
        raise ValueError(f'expected {ROWS} finite seven-column rows')
    if not np.array_equal(table[:, 2], np.tile(FREQUENCIES, 1764)):
        raise ValueError('column 3 must cycle through the ten ascending frequencies')
    pairs = table[:, :2].reshape(1764, len(FREQUENCIES), 2)
    if not np.all(pairs == pairs[:, :1, :]):
        raise ValueError('source-receiver pair changed inside a ten-row block')
    unique_pairs = pairs[:, 0, :]
    sources, counts = np.unique(unique_pairs[:, 0], return_counts=True)
    if not np.array_equal(sources, np.arange(1, 37)) or not np.all(counts == 49):
        raise ValueError('expected 36 sources with 49 receivers each')
    if len(np.unique(unique_pairs, axis=0)) != 1764:
        raise ValueError('duplicate source-receiver pairs')
    # Same frozen acquisition mask and pair order; this is read-only.
    parent = TRUTH / scene / 'forward/synthetic_input.txt'
    parent_pairs = np.loadtxt(parent, usecols=(0, 1))[::8]
    if not np.array_equal(unique_pairs, parent_pairs):
        raise ValueError('frozen source-receiver mask/order changed')
    return dict(scene=scene, path=str(path), sha256=actual, bytes=path.stat().st_size,
                rows=ROWS, frequencies_GHz=FREQUENCIES, reference_frequency_GHz=FREQUENCIES[-1],
                source_count=36, measured_receivers_per_source=49,
                relative_permittivity=4, inverse_grid=[166, 166], inverse_cell_m=0.00125,
                sign_convention='exp(+j omega t); BEM conjugates once')


def releases():
    path = ROOT / 'releases.json'
    record = read(path) if path.exists() else dict(releases=[])
    entries = record['releases']
    names = [entry['scene'] for entry in entries]
    if len(names) != len(set(names)) or any(s not in SHAPES for s in names):
        raise ValueError('release queue has duplicate or unapproved shapes')
    for entry in entries:
        if entry['frequencies_GHz'] != FREQUENCIES or not entry['data_checks_passed']:
            raise ValueError('release must confirm the approved band and all data checks')
    return entries


def release(scene):
    # This command is invoked only by the coordinator after its checks passed.
    data = frozen_input(scene)
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'releases.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        entries = releases()
        existing = next((r for r in entries if r['scene'] == scene), None)
        if existing:
            if existing['sha256'] != data['sha256']:
                raise ValueError('cannot change the hash of a released table')
            return existing
        entry = dict(scene=scene, sha256=data['sha256'], frequencies_GHz=FREQUENCIES,
                     released_utc=now(), data_checks_passed=True,
                     authority='coordinator explicit --release after the frozen-data checks in plan.md')
        entries.append(entry)
        base.write(ROOT / 'releases.json', dict(releases=entries))
        return entry


def event(kind, message):
    key = (kind, message)
    if time.monotonic() - EVENT_TIMES.get(key, -1000) < 30:
        return
    EVENT_TIMES[key] = time.monotonic()
    entry = dict(utc=now(), kind=kind, message=message)
    with (ROOT / 'alerts.jsonl').open('a') as stream:
        stream.write(json.dumps(entry) + '\n')
    print(json.dumps(entry), flush=True)


def stopped():
    return base.STOP or (ROOT / 'STOP').exists()


def received_signal(signum, frame):
    base.STOP = True


def prepare_case(entry):
    scene = entry['scene']
    data = frozen_input(scene)
    if data['sha256'] != entry['sha256']:
        raise ValueError('table hash differs from coordinator release')
    folder = ROOT / scene
    folder.mkdir(exist_ok=True)
    if (folder / 'executed_driver.m').exists() or (folder / 'launch.json').exists():
        raise ValueError('preserve prior execution; never restart a launched fit')
    truth = folder / 'truth'
    truth.mkdir(exist_ok=True)
    truth_hashes = {}
    for name in ['geometry.mat', 'geometry.json']:
        source = TRUTH / scene / 'truth' / name
        target = truth / name
        if target.exists() and base.sha(target) != base.sha(source):
            raise ValueError('existing truth differs from frozen parent')
        if not target.exists():
            shutil.copyfile(source, target)
        assert base.sha(source) == base.sha(target)
        truth_hashes[name] = base.sha(target)
    data.update(release=entry, reused_utc=now(), truth_parent=str(TRUTH / scene / 'truth'),
                truth_sha256=truth_hashes)
    base.write(folder / 'data.json', data)
    return folder


def report(state):
    lines = ['# MF-CC-CSI fits at ten frequencies: live table', '',
             f'Updated {now()}; state: {state}.', '',
             'Frequencies: 0.25 to 2.5 GHz in 0.25 GHz steps. Ten shapes at permittivity 4.',
             '2048 iterations; 166 by 166 cells at 1.25 mm; native back-propagation; eight threads.',
             'One centred start. Times are shared-machine measurements, with no time stop.',
             'Half the signed peak is the main score; 0.3 and 0.7 give sensitivity.', '',
             '| Shape | Iterations | Area error % (0.5) | Area error % (0.3 / 0.7) | Mean permittivity | Centre error mm | Native s |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for scene in SHAPES:
        folder = ROOT / scene
        if (folder / 'scores.json').exists():
            for row in read(folder / 'scores.json')['snapshots']:
                main, lo, hi = row['scores']
                fmt = lambda v: 'null' if v is None else f'{v:.4f}'
                lines.append(f"| {scene} | {row['iterations']} | {100*main['area_error']:.3f} | "
                             f"{100*lo['area_error']:.3f} / {100*hi['area_error']:.3f} | "
                             f"{fmt(main['mean_relative_permittivity'])} | {fmt(main['centroid_mm'])} | "
                             f"{row['native_elapsed_seconds']:.2f} |")
        if (folder / 'outcome.json').exists():
            outcome = read(folder / 'outcome.json')
            lines.extend(['', f"{scene}: {outcome['state']}, {outcome['utc']}. "
                          f"[Evidence]({os.path.relpath(folder, ACT)}/outcome.json).", ''])
    lines.extend(['', 'Each data.json records the exact shared input path, SHA-256 and coordinator release.',
                  'Per-case manifests hash local bulk and committed checkpoints, costs, logs and resources.',
                  'Protocol 1 scoring is unchanged. Raw checkpoints use the final 2.5 GHz image.',
                  'The output-only numerical copy and upstream numerics are unchanged (patch 0003 reused).',
                  'The five-frequency and eight-frequency results are separate and untouched.',
                  'No BEM code or scoring code was edited. No input table was generated or written.',
                  'Failures are kept in each outcome and failure log; no automatic retry.', ''])
    (ACT / 'progress.md').write_text('\n'.join(lines))


def manifest(folder):
    base.manifest(folder)
    record = read(folder / 'manifest.json')
    record.update(source_manifest=str(SOURCE), command=RECORD['latest_command'])
    base.write(folder / 'manifest.json', record)


def publish(scene):
    report(RECORD['state'])
    # Only this agent's exact code files, activity and completed case are staged.
    paths = [str(ACT.relative_to(base.REPO)), str((ROOT / scene).relative_to(base.REPO))]
    paths += [str((base.CODE / name).relative_to(base.REPO)) for name in OWN_CODE]
    paths += [str((ROOT / name).relative_to(base.REPO)) for name in ['.gitignore', '.gitattributes', 'checks']]
    # State may describe live jobs but contains no bulk fields.
    paths += [str(p.relative_to(base.REPO)) for p in ROOT.iterdir()
              if p.is_file() and p.suffix in ('.json', '.jsonl')]
    paths = sorted(set(paths))
    subprocess.run(['git', 'add', '--', *paths], cwd=base.REPO, check=True)
    subprocess.run(['git', 'diff', '--cached', '--check', '--', *paths], cwd=base.REPO, check=True)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet', '--', *paths], cwd=base.REPO).returncode
    if changed:
        subprocess.run(['git', 'commit', '-m', f'CSI ten-frequency fit: {scene}', '-m',
                        'Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>', '--', *paths],
                       cwd=base.REPO, check=True)
    subprocess.run(['git', 'push'], cwd=base.REPO, check=True)
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=base.REPO, text=True).strip()
    remote = subprocess.check_output(['git', 'ls-remote', 'origin', f'refs/heads/{branch}'], cwd=base.REPO, text=True).split()[0]
    local = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=base.REPO, text=True).strip()
    subprocess.run(['git', 'merge-base', '--is-ancestor', local, remote], cwd=base.REPO, check=True)
    print(f'Push confirmed: {local} on origin/{branch}', flush=True)
    subprocess.run(['git', 'status', '--short', '--', *paths], cwd=base.REPO, check=True)


def finalize(job):
    folder = job['folder']
    rc = base.finish(job)
    error = None
    try:
        selected.score(folder)
        base.cost_history(folder)
        if rc == 0:
            raw = loadmat(folder / 'final_contrast.mat', simplify_cells=True)
            assert np.atleast_1d(raw['counts']).tolist() == [256, 512, 1024, 2048]
            assert all(np.isfinite(a).all() for a in raw['snapshots'])
            assert np.atleast_1d(raw['frequencies_GHz']).tolist() == FREQUENCIES
            assert float(raw['reference_frequency_GHz']) == FREQUENCIES[-1]
    except Exception:
        error = traceback.format_exc()
        (folder / 'validation_failure.txt').write_text(error)
    base.write(folder / 'outcome.json', dict(state='completed' if rc == 0 and not error else 'fit failed',
               returncode=rc, utc=now(), validation_failed=bool(error)))
    manifest(folder)
    return job['scene']


def snapshot_status(active, entries, limit):
    elapsed = time.monotonic() - base.START
    record = dict(state=RECORD['state'], utc=now(), launcher_pid=os.getpid(), elapsed_seconds=elapsed,
                  active=[j['scene'] for j in active], released=[r['scene'] for r in entries],
                  unreleased=[s for s in SHAPES if s not in {r['scene'] for r in entries}],
                  max_csi_fits=limit, memory=base.memory(), matlab=base.live_jobs(),
                  target_hours=TARGET_HOURS, time_target_is_informational=True,
                  time_target_exceeded=elapsed > TARGET_HOURS * 3600)
    base.write(ROOT / 'status.json', record)
    with (ROOT / 'overlap.jsonl').open('a') as stream:
        stream.write(json.dumps(record) + '\n')
    base.write(ROOT / 'campaign.json', RECORD)
    print(json.dumps(record), flush=True)


def inspect(resume=False):
    blockers = []
    if (ROOT / 'STOP').exists():
        blockers.append('STOP exists and is preserved')
    if selected.active_workers():
        blockers.append('same-campaign MATLAB workers alive; refuse resume/duplicate launch')
    if (ROOT / 'campaign.json').exists() != resume:
        blockers.append('existing campaign requires --resume; a fresh campaign forbids --resume')
    try:
        limit = ceiling()
        entries = releases()
        for entry in entries:
            if frozen_input(entry['scene'])['sha256'] != entry['sha256']:
                raise ValueError('released table hash changed')
    except (OSError, ValueError, KeyError) as error:
        blockers.append(repr(error))
        entries, limit = [], None
    return dict(ready=not blockers, blocked_reasons=blockers, frequencies_GHz=FREQUENCIES,
                shapes=SHAPES, released=[r['scene'] for r in entries], max_csi_fits=limit,
                waits_for_new_releases=True, no_fit_started=True)


def run(resume=False):
    global RECORD, SOURCE
    check = inspect(resume)
    if not check['ready']:
        raise RuntimeError(json.dumps(check, indent=2))
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'launcher.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        RECORD = read(ROOT / 'campaign.json') if resume else dict(started_utc=now(), invocations=[])
        if RECORD.get('frequencies_GHz', FREQUENCIES) != FREQUENCIES or RECORD.get('shapes', SHAPES) != SHAPES:
            raise ValueError('resume must preserve the original shapes and frequencies')
        command = ['env', 'PYTHONPATH=solvers:.', os.sys.executable, '-B', '-m',
                   'experiments.baselines.csi.campaign_ten_frequency'] + (['--resume'] if resume else [])
        RECORD.update(state='running', launcher_pid=os.getpid(), frequencies_GHz=FREQUENCIES,
                      shapes=SHAPES, target_hours=TARGET_HOURS, time_target_is_informational=True,
                      stop_file=str(ROOT / 'STOP'), memory_reserve_bytes=base.RESERVE,
                      latest_command=command)
        RECORD.pop('finished_utc', None)
        RECORD['invocations'].append(dict(utc=now(), pid=os.getpid(), command=command))
        SOURCE = ROOT / f"sources_run_{len(RECORD['invocations']):03d}.json"
        sources = [base.CODE / name for name in OWN_CODE]
        sources += [base.CODE / name for name in ['campaign.py', 'campaign_low_band.py', 'campaign_case.m',
                    'init_campaign_record.m', 'csi_record_snapshot.m', 'registered_metrics.py', 'recorded/CC_CSI_Brent_recorded.m']]
        sources += [base.UP / name for name in ['Inv_Fresnel_I.m', 'functions/ReadFreData.m',
                    'functions/Pre_InvFresnel_Conf.m', 'functions/get_chiMF.m',
                    'functions/CC_CSI_Brent.m', 'show_InitGuess.m']]
        base.write(SOURCE, dict(utc=now(), command=command,
                   upstream_commit=subprocess.check_output(['git', '-C', str(base.UP), 'rev-parse', 'HEAD'], text=True).strip(),
                   files=[dict(path=str(p), sha256=base.sha(p)) for p in sources]))
        configure()
        base.START = time.monotonic() - (time.time() - dt.datetime.fromisoformat(RECORD['started_utc']).timestamp())
        signal.signal(signal.SIGTERM, received_signal)
        signal.signal(signal.SIGINT, received_signal)
        base.write(ROOT / 'campaign.json', RECORD)
        unpublished = []
        if resume:
            for scene in SHAPES:
                folder = ROOT / scene
                if not (folder / 'outcome.json').exists() and ((folder / 'launch.json').exists() or (folder / 'executed_driver.m').exists()):
                    selected.score(folder)
                    if (folder / 'matlab.log').exists():
                        base.cost_history(folder)
                        with (folder / 'matlab.log').open('rb') as src, gzip.open(folder / 'matlab.log.gz', 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                    base.write(folder / 'outcome.json', dict(state='interrupted fit; snapshots preserved; never restarted', utc=now()))
                    manifest(folder)
                    unpublished.append(scene)
        active = []
        last_status = -100
        limit = 0
        controller_failed = False
        while True:
            # Catch control errors and keep watching any live native fits.
            try:
                # Even a metadata-write error after Popen must not orphan a fit.
                for job in base.JOBS:
                    if job not in active and Path(job['folder']).is_relative_to(ROOT):
                        job.setdefault('scene', Path(job['folder']).name)
                        active.append(job)
                try:
                    entries = releases()
                except (OSError, ValueError, KeyError) as error:
                    entries = []
                    event('invalid_release_queue', repr(error))
                try:
                    limit = ceiling()
                except (OSError, ValueError, KeyError) as error:
                    limit = 0
                    event('invalid_resource_policy', repr(error))
                if stopped():
                    RECORD['state'] = 'stopped; available evidence preserved'
                    for job in active:
                        base.terminate(job, 'explicit STOP or controller signal')
                if active and base.memory()['MemAvailable'] < base.RESERVE:
                    base.terminate(active[-1], 'urgent 14 GiB memory reserve breach')
                    event('memory_guard', f"stopped newest owned fit: {active[-1]['scene']}")
                for job in list(active):
                    base.sample(job)
                    selected.iteration_timing(job)
                    if job['process'].poll() is not None:
                        unpublished.append(finalize(job))
                        active.remove(job)
                # A completed/failed fit is published before the next one starts.
                for scene in list(unpublished):
                    try:
                        publish(scene)
                        unpublished.remove(scene)
                    except Exception as error:
                        event('publish_retry', repr(error))
                        break
                if not controller_failed and not stopped() and not unpublished:
                    for entry in entries:
                        # Deliberately re-read immediately before EVERY launch.
                        try:
                            limit = ceiling()
                        except (OSError, ValueError, KeyError) as error:
                            limit = 0
                            event('invalid_resource_policy', repr(error))
                        if len(active) >= limit:
                            break
                        folder = ROOT / entry['scene']
                        if (folder / 'outcome.json').exists() or (folder / 'launch.json').exists():
                            continue
                        current = sum(j.get('family', 0) for j in active)
                        if base.memory()['MemAvailable'] + current < base.RESERVE + MARGIN + (len(active) + 1) * FIT_RSS:
                            break
                        try:
                            folder = prepare_case(entry)
                            active.append(selected.inversion(entry['scene'], folder))
                        except Exception:
                            folder.mkdir(parents=True, exist_ok=True)
                            (folder / 'preparation_failure.txt').write_text(traceback.format_exc())
                            base.write(folder / 'outcome.json', dict(state='preparation/launch failed; evidence preserved', utc=now()))
                            manifest(folder)
                            unpublished.append(entry['scene'])
                            break
                elapsed = time.monotonic() - base.START
                if elapsed - last_status >= 30:
                    snapshot_status(active, entries, limit)
                    last_status = elapsed
                all_done = all((ROOT / s / 'outcome.json').exists() for s in SHAPES)
                if not active and not unpublished and (all_done or stopped() or controller_failed):
                    if all_done:
                        RECORD['state'] = 'completed all outcomes'
                    break
            except BaseException:
                controller_failed = True
                RECORD['state'] = 'controller failed; native workers kept running'
                with (ROOT / 'launcher_failure.txt').open('a') as stream:
                    stream.write(traceback.format_exc())
                event('controller_error', 'no worker stopped or restarted; continue monitoring')
            time.sleep(1)
        RECORD.update(finished_utc=now(), wall_seconds=time.monotonic() - base.START)
        snapshot_status([], releases(), limit)
        report(RECORD['state'])
        # Publish the final state after every fit has its own preserved outcome.
        completed = [s for s in SHAPES if (ROOT / s / 'outcome.json').exists()]
        if completed:
            publish(completed[-1])


def main():
    parser = argparse.ArgumentParser(__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--dry-run', action='store_true')
    group.add_argument('--release', choices=SHAPES)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    configure()
    if args.release:
        if args.resume:
            parser.error('--release cannot be combined with --resume')
        print(json.dumps(release(args.release), indent=2))
    elif args.dry_run:
        print(json.dumps(inspect(args.resume), indent=2))
    else:
        run(args.resume)


if __name__ == '__main__':
    main()
