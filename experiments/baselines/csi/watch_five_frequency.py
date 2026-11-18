"""Read-only data/BEM checks, authorized CSI releases, and detached monitoring."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import time
import traceback

import psutil
from experiments.baselines.csi import campaign_five_frequency as c

BEM = c.base.REPO / 'results/bem/baseline_data/csi_five_frequency/2026-11-18/adapter_checks'
STATE = c.ROOT / 'watch.json'
EVENTS = c.ROOT / 'watch_events.jsonl'


def emit(kind, **details):
    record = dict(utc=c.now(), kind=kind, **details)
    with EVENTS.open('a') as stream:
        stream.write(json.dumps(record, allow_nan=False) + '\n')
    print(json.dumps(record), flush=True)


def check(scene):
    folder = c.DATA / scene
    manifest_path, checks_path = folder / 'manifest.json', folder / 'checks.json'
    bem_path = BEM / f'{scene}__c4.json'
    # Missing files mean preparation/checking has not finished, not failure.
    manifest = c.read(manifest_path) if manifest_path.exists() else None
    checks = c.read(checks_path) if checks_path.exists() else None
    if ((manifest and manifest['state'] != 'frozen') or
            (checks and checks['state'] != 'passed')):
        raise ValueError(f'data states: manifest={manifest}, checks={checks}')
    if manifest is None or checks is None:
        return None
    if manifest['state'] != 'frozen' or checks['state'] != 'passed':
        raise ValueError(f"data states: manifest={manifest['state']}, checks={checks['state']}")
    data = c.frozen_input(scene)
    digest = data['sha256']
    if manifest['table']['sha256'] != digest:
        raise ValueError('manifest hash differs from table and sidecar')
    if c.base.sha(checks_path) != manifest['checks']['sha256']:
        raise ValueError('checks.json hash differs from frozen manifest')
    if not bem_path.exists():
        return None
    bem = c.read(bem_path)
    if bem['frozen_sha256_verified'] != digest:
        raise ValueError('BEM checked a different SHA-256')
    summary = bem['summary']
    rows = bem['mismatch']['per_frequency']
    values = {f: [r['relative_mismatch'] for r in rows if r['frequency_ghz'] == f]
              for f in c.FREQUENCIES}
    checks_ok = all(v and all(math.isfinite(x) and 0 <= x <= .01 for x in v)
                    for v in values.values())
    numbers = {str(f): [100 * x for x in v] for f, v in values.items()}
    if (summary['one_percent_rule'] is not True or summary['adapter_checks_pass'] is not True
            or summary['rule_frequencies_ghz'] != c.FREQUENCIES or not checks_ok):
        raise ValueError(f'BEM check fails: summary={summary}; mismatch_percent={numbers}')
    return dict(utc=c.now(), scene=scene, sha256=digest,
                check_1=dict(manifest_state=manifest['state'], checks_state=checks['state'],
                    reproduction=checks.get('reproduction'),
                    manifest_sha256=c.base.sha(manifest_path), checks_sha256=c.base.sha(checks_path)),
                check_2=dict(table_sha256=digest, sidecar_sha256_verified=True),
                check_3=dict(frozen_sha256_verified=bem['frozen_sha256_verified'],
                    one_percent_rule=summary['one_percent_rule'],
                    adapter_checks_pass=summary['adapter_checks_pass'],
                    rule_frequencies_ghz=summary['rule_frequencies_ghz'],
                    mismatch_percent_by_frequency=numbers, file=str(bem_path),
                    file_sha256=c.base.sha(bem_path)),
                watcher_sha256=c.base.sha(Path(__file__)))


def record_release(evidence, entry):
    evidence['released_utc'] = entry['released_utc']
    with (c.ACT / 'releases.jsonl').open('a') as stream:
        stream.write(json.dumps(evidence, allow_nan=False) + '\n')
    lines = ['# Authorized shape releases', '',
             'Standing release rule delegated by the coordinator on 18 November 2026.',
             'BEM and data evidence is read only. The JSONL records all three checks and hashes.', '',
             '| UTC release | Shape | Table SHA-256 | Data states | SHA check | BEM maximum % |',
             '|---|---|---|---|---|---:|']
    for line in (c.ACT / 'releases.jsonl').read_text().splitlines():
        row = json.loads(line)
        worst = max(x for v in row['check_3']['mismatch_percent_by_frequency'].values() for x in v)
        lines.append(f"| {row['released_utc']} | {row['scene']} | {row['sha256']} | frozen / passed | matched | {worst:.6f} |")
    (c.ACT / 'releases.md').write_text('\n'.join(lines) + '\n')


def alive(pid):
    try:
        process = psutil.Process(pid)
        return process.status() != psutil.STATUS_ZOMBIE and 'campaign_five_frequency' in ' '.join(process.cmdline())
    except psutil.NoSuchProcess:
        return False


def poll(state):
    campaign = c.read(c.ROOT / 'campaign.json')
    pid = campaign['launcher_pid']
    running = alive(pid)
    status = c.read(c.ROOT / 'status.json')
    if running and not campaign.get('finished_utc'):
        existing = {r['scene']: r for r in c.releases()}
        for scene in c.SHAPES:
            if scene in existing or scene in state['blocked']:
                continue
            try:
                evidence = check(scene)
                if evidence is None:
                    continue
                command = [os.sys.executable, '-B', '-m',
                           'experiments.baselines.csi.campaign_five_frequency', '--release', scene]
                output = subprocess.check_output(command, cwd=c.base.REPO, text=True)
                entry = json.loads(output)
                if entry['sha256'] != evidence['sha256']:
                    raise ValueError('release hash differs from checked evidence')
                record_release(evidence, entry)
                emit('released', scene=scene, sha256=entry['sha256'],
                     mismatch_percent_by_frequency=evidence['check_3']['mismatch_percent_by_frequency'])
            except json.JSONDecodeError:
                # BEM writes its check file in place; a partial read waits.
                continue
            except Exception as error:
                state['blocked'][scene] = dict(utc=c.now(), error=repr(error))
                emit('release_failed', scene=scene, error=repr(error))
    for scene in c.SHAPES:
        folder = c.ROOT / scene
        timing = folder / 'early_iteration_timing.json'
        if timing.exists() and scene not in state['timings_reported']:
            emit('early_timing', scene=scene, timing=c.read(timing))
            state['timings_reported'].append(scene)
        outcome = folder / 'outcome.json'
        if outcome.exists() and scene not in state['outcomes_reported']:
            emit('outcome', scene=scene, outcome=c.read(outcome))
            state['outcomes_reported'].append(scene)
    if not running and not campaign.get('finished_utc') and not state.get('launcher_failure_reported'):
        emit('launcher_failed', pid=pid, status=status)
        state['launcher_failure_reported'] = True
    if not running and campaign.get('finished_utc'):
        emit('launcher_finished', pid=pid, state=campaign['state'])
        state['finished_utc'] = c.now()
    state.update(utc=c.now(), launcher_pid=pid, launcher_alive=running,
                 launcher_status=status, watch_pid=os.getpid())
    c.base.write(STATE, state)
    return state.get('finished_utc') or state.get('launcher_failure_reported')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    c.configure()
    lock = (c.ROOT / 'watch.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = c.read(STATE) if STATE.exists() else dict(blocked={}, timings_reported=[], outcomes_reported=[])
    while True:
        try:
            done = poll(state)
        except Exception:
            emit('watch_error', error=traceback.format_exc())
            done = False
        if args.once or done:
            break
        time.sleep(60)


if __name__ == '__main__':
    main()
