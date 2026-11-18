"""Keep shared launch ceilings and an overnight heartbeat; never launch or stop fits."""
import argparse
import datetime as dt
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'results/resource_management/2026-11-18'
POLICY = REPO / 'results/csi/resource_policy.json'
DATA = REPO / 'results/csi/tg002/2026-11-18_five_frequency_data'
CSI = REPO / 'results/csi/tg002/2026-11-18_five_frequency'
BEM = REPO / 'results/bem/baseline_data/csi_five_frequency/2026-11-18'
B1 = REPO / 'results/bem/baseline_data/brg_tg002/2026-11-18'
SHAPES = ('circle', 'kite', 'peanut', 'star', 'asymmetric', 'c_shape', 'hook', 'cross', 'cog', 'aphex_twin')
RESERVE = dict(data=3., csi=6.6, b1=4., bem=4., check=2.)
CORES = dict(data=8, csi=5, b1=1, bem=4, check=1)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(tmp, path)


def process_sample():
    output = subprocess.check_output(
        ['ps', '-u', str(os.getuid()), '-o', 'pid=,ppid=,rss=,comm=,args='], text=True)
    processes = {}
    for line in output.splitlines():
        parts = line.split(None, 4)
        if len(parts) == 5:
            pid, parent, rss, comm, command = parts
            processes[int(pid)] = dict(pid=int(pid), parent=int(parent),
                                       rss_gib=int(rss)/1024**2, comm=comm, command=command)

    def ancestors(pid):
        seen = set()
        while pid in processes and pid not in seen:
            seen.add(pid)
            yield pid
            pid = processes[pid]['parent']

    roots = {}
    for pid, p in processes.items():
        cmd = p['command']
        if 'python' in p['comm']:
            if 'b1_run.py fit --case' in cmd:
                roots[pid] = 'b1'
            elif 'csi_fit.py' in cmd and '--case' in cmd:
                roots[pid] = 'bem' if '--device cuda' in cmd else 'check'
            elif 'csi_forward_check.py' in cmd:
                roots[pid] = 'check'
        elif p['comm'] == 'MATLAB':
            context = ' '.join(processes[a]['command'] for a in ancestors(pid))
            if 'five_frequency_data' in context or 'generate_five_frequency' in context:
                roots[pid] = 'data'
            elif 'campaign_five_frequency' in context or str(CSI) in context:
                roots[pid] = 'csi'
    # Numerical subprocesses and their own children belong to a single root.
    jobs = []
    for pid, kind in roots.items():
        if any(a in roots for a in list(ancestors(pid))[1:]):
            continue
        rss = sum(p['rss_gib'] for child, p in processes.items() if pid in ancestors(child))
        jobs.append(dict(pid=pid, kind=kind, rss_gib=round(rss, 4)))
    launchers = sorted({p['command'].split('experiments/', 1)[-1][:180]
                        for p in processes.values()
                        if 'python' in p['comm'] and any(name in p['command'] for name in
                           ('prepare_five_frequency_data', 'campaign_five_frequency', 'b1_queue.py'))})
    return jobs, launchers


def progress():
    ready = [s for s in SHAPES if (DATA/s/'forward/synthetic_input.txt.sha256').exists()]
    checked = []
    failed_checks = []
    for path in (BEM/'adapter_checks').glob('*.json'):
        record = read(path, {})
        summary = record.get('summary', {})
        if summary.get('adapter_checks_pass') and summary.get('one_percent_rule'):
            checked.append(path.stem)
        elif summary:
            failed_checks.append(path.stem)
    bem_done = sorted({p.relative_to(BEM).parts[0]
                       for p in BEM.glob('*/cuda/attempt_*/metrics.json')})
    b1_done = {tuple(p.relative_to(B1).parts[:2]) for p in B1.glob('*/*/attempt_*/metrics.json')}
    csi_done = {s: read(CSI/s/'outcome.json') for s in SHAPES[3:] if (CSI/s/'outcome.json').exists()}
    return dict(tables_ready=ready, checks_passed=checked, checks_failed=failed_checks,
                bem_outcomes=bem_done, b1_outcomes=len(b1_done), csi_outcomes=csi_done,
                csi_releases=read(CSI/'releases.json', {}).get('releases', []),
                csi_status=read(CSI/'status.json', {}))


def sample():
    mem = {k: int(v.split()[0]) for k, v in
           (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())}
    jobs, launchers = process_sample()
    return dict(utc=now(), available_gib=mem['MemAvailable']/1024**2,
                logical_cpus=os.cpu_count(), load=list(os.getloadavg()),
                jobs=jobs, launchers=launchers, progress=progress())


def allocate(s):
    """Reserve growth of existing workers plus every permitted new worker."""
    p = s['progress']
    targets = dict(data=int(len(p['tables_ready']) < 10), csi=0,
                   b1=int(p['b1_outcomes'] < 40), bem=int(len(p['bem_outcomes']) < 10),
                   check=int(len(p['checks_passed']) + len(p['checks_failed']) < 10))
    jobs = {kind: [j for j in s['jobs'] if j['kind'] == kind] for kind in RESERVE}

    def cost(t):
        growth = sum(max(0., RESERVE[k] - j['rss_gib']) for k in RESERVE for j in jobs[k])
        new = sum(max(0, t[k] - len(jobs[k])) * RESERVE[k] for k in RESERVE)
        cores = sum(max(t[k], len(jobs[k])) * CORES[k] for k in RESERVE)
        return growth + new, cores

    # Stop NEW competing launches first under pressure. Never signal a worker.
    for kind in ('bem', 'data', 'check', 'b1'):
        extra, cores = cost(targets)
        if s['available_gib'] - extra >= 16 and cores <= s['logical_cpus']:
            break
        targets[kind] = 0
    for n in range(min(3, 7-len(p['csi_outcomes'])), -1, -1):
        trial = dict(targets, csi=n)
        extra, cores = cost(trial)
        if s['available_gib'] - extra >= 16 and cores <= s['logical_cpus']:
            targets = trial
            break
    extra, cores = cost(targets)
    return dict(max_data_jobs=targets['data'], max_csi_fits=targets['csi'],
                max_bem_fits=targets['b1']+targets['bem'], max_cpu_checks=targets['check'],
                reserved_growth_and_new_gib=round(extra, 3),
                projected_available_gib=round(s['available_gib']-extra, 3),
                estimated_cores=cores, target_slots=targets)


def update_policy(s, allocation):
    policy = read(POLICY, {})
    if policy.get('monitor_enabled') is False:
        return False
    caps = {k: allocation[k] for k in ('max_data_jobs', 'max_csi_fits', 'max_bem_fits', 'max_cpu_checks')}
    changed = any(policy.get(k) != v for k, v in caps.items())
    policy.update(caps, updated=s['utc'], monitor_enabled=True,
                  authority='User delegated overnight resource management in this session; BEM coordinator confirmed shared-file launch control and CPU-only forward checks.',
                  scope='New launches only. Never interrupt, restart or time-stop a fit.',
                  floor_gib=14, margin_gib=2,
                  bem_scope='B1 and simulated-C GPU fits share max_bem_fits; allow one C fit alongside B1 when resources permit. CPU checks use max_cpu_checks, not a GPU slot.',
                  bem_application='BEM coordinator confirmed its runner re-reads this file before every launch.',
                  cpu_check_scope='One CPU-only forward check at a time as tables freeze; reserve 2 GiB and one thread. No GPU wait.',
                  worker_reservation_gib=dict(matlab_data=3, mf_cc_csi_fit=6.6, bem_fit=4, cpu_forward_check=2),
                  monitor=dict(pid=os.getpid(), status_file=str(OUT/'status.json'),
                               heartbeat_seconds=60, resource_recheck_seconds=600),
                  latest_allocation=allocation,
                  latest_sample=dict(utc=s['utc'], available_gib=s['available_gib'], load=s['load'], jobs=s['jobs']),
                  rationale='Reserve outstanding worker growth and future launches above 16 GiB; use at most 24 estimated CPU cores. Up to three CSI fits once preparation and short BEM work free capacity.',
                  recheck='Every ten minutes, on prerequisite completion, or immediately when a lower ceiling is needed.',
                  notification_status='Coordinators read this shared file. Pane notices remain unavailable outside Herdr.')
    write(POLICY, policy)
    if changed:
        with (OUT/'events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(utc=s['utc'], kind='ceilings_changed', **allocation))+'\n')
    return True


def watch():
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT/'monitor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        last_change, last_phase = 0., None
        while not (OUT/'STOP').exists():
            try:
                s = sample()
                a = allocate(s)
                p = s['progress']
                phase = (len(p['tables_ready']), len(p['checks_passed']), len(p['bem_outcomes']), p['b1_outcomes'])
                policy = read(POLICY, {})
                lower = any(a[k] < policy.get(k, 0) for k in
                            ('max_data_jobs', 'max_csi_fits', 'max_bem_fits', 'max_cpu_checks'))
                if lower or phase != last_phase or time.monotonic()-last_change >= 600:
                    if not update_policy(s, a):
                        break
                    last_change, last_phase = time.monotonic(), phase
                complete = len(p['bem_outcomes']) == 10 and p['b1_outcomes'] == 40 and len(p['csi_outcomes']) == 7
                state = 'all_requested_outcomes_saved' if complete else 'watching'
                alerts = []
                if p['checks_failed']:
                    alerts.append('Failed scientific checks remain with coordinators; no threshold changed.')
                if not any('campaign_five_frequency' in v for v in s['launchers']) and len(p['csi_outcomes']) < 7:
                    alerts.append('CSI launcher is not running; coordinator must release and launch it after checks.')
                if len(p['tables_ready']) < 10 and not any('prepare_five_frequency_data' in v for v in s['launchers']):
                    alerts.append('Data preparation is not currently running; coordinator still owns preparation.')
                write(OUT/'status.json', dict(state=state, pid=os.getpid(), **s,
                                            proposed_allocation=a, alerts=alerts))
                if complete:
                    return
            except Exception as error:
                with (OUT/'events.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(utc=now(), kind='monitor_error', detail=repr(error)))+'\n')
                # A transient read or process error must not stop native fits or the monitor.
            time.sleep(60)
        write(OUT/'monitor_stopped.json', dict(utc=now(), reason='monitor STOP or monitor_enabled=false; no fit touched'))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    if args.start:
        OUT.mkdir(parents=True, exist_ok=True)
        if (OUT/'STOP').exists():
            raise SystemExit('Monitor STOP exists; preserved.')
        with (OUT/'monitor.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (OUT/'monitor.log').open('ab') as log, open(os.devnull, 'rb') as empty:
            child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), '--watch'],
                                     cwd=REPO, stdin=empty, stdout=log, stderr=log, start_new_session=True)
        write(OUT/'launch.json', dict(utc=now(), pid=child.pid, command=child.args,
                                    policy=str(POLICY), purpose='Overnight launch ceilings and queue heartbeat'))
        print(json.dumps(read(OUT/'launch.json')))
    elif args.watch:
        watch()
    else:
        s = sample()
        print(json.dumps(dict(sample=s, proposed_allocation=allocate(s)), indent=2))


if __name__ == '__main__':
    main()
