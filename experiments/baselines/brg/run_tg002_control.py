"""Detached no-curvature control; read activity-04 data and never generate it."""
import argparse
import datetime
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from run_tg002 import available, file_sha256, now
from run_paper import write_json, matlab_processes
from log_tg002_rejections import summarize_case

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'results/brg/tg002_shapes/2026-11-17'
BASE = ROOT/'results/brg/tg002_no_curvature/2026-11-18'
UPSTREAM = Path.home()/'neural_bem_external/inverse-obstacle-scattering2d'
PILOT = 'kite__c0.5'


def require_source_complete():
    state = json.loads((SOURCE/'campaign.json').read_text())
    assert state['status'] == 'complete' and not state['active'] and not state['pending'], 'Wait for activity 04 to finish by itself.'
    # Lock proves the detached 04 supervisor has actually exited its queue.
    with (SOURCE/'local/campaign.lock').open('r') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return state


def prepare():
    state = require_source_complete()
    assert not (BASE/'campaign.json').exists(), 'Do not reset an existing campaign.'
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE/'local').mkdir(exist_ok=True)
    prior = []
    stalled = []
    for case in state['cases']:
        metrics = json.loads((SOURCE/case/'metrics.json').read_text())
        assert metrics['completed_frequencies'] == 37 and metrics['status'] == 'complete'
        path = SOURCE/case/'rejection_counts.json'
        r = json.loads(path.read_text())
        final_exit = r['frequencies'][-1]['exit_flag']
        if final_exit == -1:
            stalled.append(case)
        prior.append(dict(case=case, area_error=metrics['area_error'],
                          final_frequency_exit_flag=final_exit,
                          terminal_ier_minus5=r['final_iteration_ier_counts'].get('-5', 0)))
    circles = [c for c in state['cases'] if c.startswith('circle__')]
    order = [PILOT]+[c for c in stalled if c != PILOT and c not in circles]
    order += [c for c in state['cases'] if c not in order and c not in circles]+circles
    assert len(order) == len(set(order)) == 20
    for case in order:
        out = BASE/case
        (out/'local').mkdir(parents=True, exist_ok=True)
        manifest = json.loads((SOURCE/case/'bulk_manifest.json').read_text())
        files = [f for f in manifest['files'] if Path(f['path']).name.startswith('data_') and f['path'].endswith('.mat')]
        assert len(files) == 37
        for item in files:
            path = ROOT/item['path']
            assert path.stat().st_size == item['bytes'] and file_sha256(path) == item['sha256'], str(path)
        shape = case.split('__c')[0]
        geometry = SOURCE/'local'/f'{shape}.mat'
        receipt = dict(case=case, source_activity='04_run_brg_on_tg002_shapes', verified_at=now(),
                       data_generation='none; read original files in place', files=files,
                       geometry=dict(path=str(geometry.relative_to(ROOT)), sha256=file_sha256(geometry)),
                       source_manifest_sha256=file_sha256(SOURCE/case/'bulk_manifest.json'))
        write_json(out/'data_reuse.json', receipt)
    write_json(BASE/'order.json', dict(cases=order, pilot=PILOT, grouping=prior,
                                     rule='pilot alone; cases ending 04 with final-frequency exit -1 in 04 order; rest; circle last'))
    files = ['run_tg002_control.py', 'run_tg002_control_case.m', 'score_tg002_control.py',
             'report_tg002_control.py', 'check_tg002_outputs.py', 'log_tg002_rejections.py', 'tg002_geometry.m']
    snapshots = BASE/'local/source_snapshot'
    snapshots.mkdir(exist_ok=True)
    hashes = {}
    for name in files:
        path = ROOT/'experiments/baselines/brg'/name
        (snapshots/name).write_bytes(path.read_bytes())
        hashes[str(path.relative_to(ROOT))] = file_sha256(path)
    write_json(BASE/'provenance.json', dict(prepared_at=now(), source_sha256=hashes,
        prior_provenance=json.loads((SOURCE/'provenance.json').read_text()),
        data_request_sha256=file_sha256(SOURCE/'data_request.json'), only_inverse_change='eps_curv unset (public default)',
        upstream_patches='same approved patches 03/04; no new upstream patch', no_bem_run=True))
    print('Prepared', len(order), 'cases; no MATLAB launched. Order:', ', '.join(order), flush=True)


def verify_reuse(out):
    record = json.loads((out/'data_reuse.json').read_text())
    for item in record['files']+[record['geometry']]:
        path = ROOT/item['path']
        assert file_sha256(path) == item['sha256'], 'Data/input hash changed: '+str(path)


def run_case(case, deadline):
    out = BASE/case
    local = out/'local'
    with (local/'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not list(out.glob('attempt_*.json')), 'Retries require another coordinator decision.'
        start = time.monotonic()
        remaining = math.floor(min(3600, deadline-time.time()))
        assert remaining > 10, 'Case/campaign budget exhausted.'
        receipt = out/'attempt_01.json'
        log = local/'matlab_01.log'
        command = ['matlab', '-batch', f"addpath('{ROOT}/experiments/baselines/brg'); run_tg002_control_case"]
        record = dict(case=case, started=now(), status='checking_data', remaining_seconds=remaining,
                      data_status='provisional', curvature='default', command=command,
                      log=str(log.relative_to(ROOT)), other_matlab_at_start=matlab_processes())
        write_json(receipt, record)
        code = 1
        try:
            verify_reuse(out)
            record['data_hash_check_seconds'] = time.monotonic()-start
            assert not (BASE/'STOP').exists(), 'STOP requested before MATLAB launch.'
            shape, eta = case.split('__c')
            env = os.environ.copy()
            env.update(BRG_TG002_CASE=case, BRG_SHAPE=shape, BRG_ETA=eta, BRG_CURVATURE='default',
                       BRG_REMAINING_SECONDS=str(max(1, remaining-int(time.monotonic()-start)-10)))
            with log.open('w') as stream:
                process = subprocess.Popen(command, cwd=UPSTREAM, env=env, stdout=stream,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                record.update(matlab_pid=process.pid, status='running')
                write_json(receipt, record)
                matlab_start = time.monotonic()
                try:
                    code = process.wait(timeout=max(1, remaining-(time.monotonic()-start)-8))
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    code = 124
                record['wall_seconds'] = time.monotonic()-matlab_start
            record.update(returncode=code, ended=now(), other_matlab_at_end=matlab_processes())
            write_json(receipt, record)
            (out/'progress_01.log').write_text('\n'.join(l for l in log.read_text(errors='replace').splitlines() if l.startswith('BRG '))+'\n')
            with (local/'scoring.log').open('w') as stream:
                score = subprocess.run([sys.executable, str(ROOT/'experiments/baselines/brg/score_tg002_control.py'), '--case', case],
                    cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                    timeout=max(1, remaining-(time.monotonic()-start)-2))
            if score.returncode:
                record['scoring_failure'] = 'See local/scoring.log'
                code = code or score.returncode
            elif json.loads((out/'metrics.json').read_text())['status'] != 'complete':
                code = code or 1
            summarize_case(out)
        except Exception as error:
            record['supervisor_failure'] = repr(error)
            code = code or 1
        record.update(returncode=code, status='finished' if code == 0 else 'failed_or_capped',
                      case_wall_seconds=time.monotonic()-start, case_ended=now())
        write_json(receipt, record)
        manifest = []
        for path in sorted(local.iterdir()):
            if path.is_file() and path.name != 'runner.lock':
                manifest.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=file_sha256(path)))
        write_json(out/'bulk_manifest.json', dict(command='python experiments/baselines/brg/run_tg002_control.py --campaign --detach', files=manifest))
        record.update(case_wall_seconds=time.monotonic()-start, case_ended=now())
        write_json(receipt, record)
        print(json.dumps(record), flush=True)
        return code


def worker_reserve(case):
    receipt = BASE/case/'attempt_01.json'
    rss = 0
    if receipt.exists():
        pid = json.loads(receipt.read_text()).get('matlab_pid')
        try:
            rss = int(next(l.split()[1] for l in Path(f'/proc/{pid}/status').read_text().splitlines() if l.startswith('VmRSS:')))*1024
        except (FileNotFoundError, StopIteration):
            pass
    return max(0, 4*1024**3-rss)


def campaign():
    require_source_complete()
    with (BASE/'local/campaign.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not (BASE/'campaign.json').exists(), 'Do not relaunch or reset the campaign.'
        order = json.loads((BASE/'order.json').read_text())['cases']
        state = dict(started=now(), deadline_unix=time.time()+18000, status='running', cases=order,
                     supervisor_pid=os.getpid(), active=[], pending=order.copy(), maximum_workers=2,
                     pilot=PILOT, pilot_complete=False, reserve_gib=14, stop_file=str((BASE/'STOP').relative_to(ROOT)))
        write_json(BASE/'campaign.json', state)
        active = {}
        pending = order.copy()
        stop_reason = None
        while pending or active:
            for case, process in list(active.items()):
                if process.poll() is not None:
                    del active[case]
                    receipt = json.loads((BASE/case/'attempt_01.json').read_text())
                    if process.returncode:
                        stop_reason = f'{case} failed or capped; coordinator review required'
                    elif case == PILOT:
                        state['pilot_complete'] = True
                        state['pilot_wall_seconds'] = receipt['case_wall_seconds']
                        print('PILOT COMPLETE', receipt['case_wall_seconds'], 'seconds', flush=True)
            if (BASE/'STOP').exists():
                stop_reason = stop_reason or 'STOP requested'
            if time.time() >= state['deadline_unix']:
                stop_reason = stop_reason or 'five-hour queue limit'
            memory = available()
            if memory < 14*1024**3:
                stop_reason = stop_reason or 'memory below 14 GiB reserve'
                # Relieve pressure promptly; only this queue's newest worker.
                if active:
                    newest = list(active)[-1]
                    receipt_path = BASE/newest/'attempt_01.json'
                    if receipt_path.exists():
                        pid = json.loads(receipt_path.read_text()).get('matlab_pid')
                        try:
                            command_line = Path(f'/proc/{pid}/cmdline').read_bytes()
                        except FileNotFoundError:
                            command_line = b''
                        if pid and b'run_tg002_control_case' in command_line:
                            try:
                                os.killpg(pid, signal.SIGTERM)
                            except ProcessLookupError:
                                pass
                            state['resource_stop'] = dict(case=newest, utc=now())
            if stop_reason:
                if not (BASE/'STOP').exists():
                    (BASE/'STOP').write_text(stop_reason+'\n')
                state['stop_reason'] = stop_reason
                state.setdefault('unrun_cases', pending.copy())
                pending = []
            with (BASE/'resources.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(utc=now(), available_gib=memory/1024**3,
                    active=list(active), reserve_ok=memory>=14*1024**3))+'\n')
            reserve = sum(worker_reserve(c) for c in active)
            if pending and not stop_reason and len(active)<2 and (state['pilot_complete'] or not active) and memory-reserve-4*1024**3>=14*1024**3:
                case = pending.pop(0)
                with (BASE/'local'/f'{case}_supervisor.log').open('w') as stream:
                    active[case] = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--case', case,
                        '--deadline', str(state['deadline_unix'])], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            state.update(active=list(active), pending=pending.copy(), updated=now())
            write_json(BASE/'campaign.json', state)
            if pending or active:
                time.sleep(5)
        state.update(status='stopped' if stop_reason else 'complete', ended=now(), active=[], pending=[])
        write_json(BASE/'campaign.json', state)
        if stop_reason:
            write_json(BASE/'STOPPED.json', dict(ended=state['ended'], reason=stop_reason,
                                               unrun_cases=state.get('unrun_cases', [])))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--campaign', action='store_true')
    parser.add_argument('--detach', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--deadline', type=float)
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.detach:
        assert args.campaign and not args.case
        require_source_complete()
        assert (BASE/'order.json').exists() and not (BASE/'campaign.json').exists()
        with (BASE/'local/launcher.log').open('a') as stream:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--campaign'], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(BASE/'launcher.json', dict(pid=child.pid, launched=now(), command='--campaign'))
        print('Detached control supervisor', child.pid, flush=True)
    elif args.campaign:
        campaign()
    elif args.case:
        assert args.deadline is not None and args.case in json.loads((BASE/'order.json').read_text())['cases']
        raise SystemExit(run_case(args.case, args.deadline))
    else:
        parser.error('Choose --prepare, --campaign or --case.')


if __name__ == '__main__':
    main()
