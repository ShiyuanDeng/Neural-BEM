"""Detached, memory-limited native CSI launcher. Never retries a fit."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[4]
CODE = Path(__file__).resolve().parent
UPSTREAM = Path.home() / 'neural_bem_external/CC-CSI'
GIB = 1024**3
LIMIT = 8 * GIB
BEM_GROWTH = 8 * GIB  # Coordinator's explicit 19 November figure.
# Adapter contract: keep the paths and pass fields here.
CHECK_PATHS = ('checks/table_{case}__{data}/check.json',
               'checks/forward_circle__c4__clean/check.json')
PASS_FIELD = 'passed'


def now():
    return subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def resource_sample():
    available = int(re.search(r'^MemAvailable:\s+(\d+)', Path('/proc/meminfo').read_text(), re.M)[1])*1024
    jobs = subprocess.run(['pgrep', '-x', 'MATLAB'], capture_output=True, text=True)
    if jobs.returncode not in (0, 1):
        raise RuntimeError('pgrep failed: ' + jobs.stderr)
    return dict(utc=now(), available_bytes=available, matlab_pids=jobs.stdout.split(),
                limit_bytes=LIMIT, expected_other_growth_bytes=BEM_GROWTH,
                reserve_bytes=16*GIB,
                allowed=available-LIMIT-BEM_GROWTH >= 16*GIB and jobs.returncode == 1)


def check_records(root, case, data):
    paths = [root / name.format(case=case, data=data) for name in CHECK_PATHS]
    paths.append(root / 'checks/run_self_tests/check.json')
    for path in paths:
        record = read(path)
        if record.get(PASS_FIELD) is not True:
            raise RuntimeError(f'check has not passed: {path}')
        if path.parent.name.startswith('table_'):
            manifest = root / 'inputs' / f'{case}__{data}' / 'inputs.json'
            if record.get('inputs_sha256') != sha(manifest):
                raise RuntimeError('table check refers to a different input manifest')
    forward = paths[1].parent
    if read(paths[2]).get('fixture_sha256') != sha(forward/'truth_1.25mm.mat'):
        raise RuntimeError('self-test refers to a different truth fixture')
    if read(paths[2]).get('forward_check_sha256') != sha(paths[1]):
        raise RuntimeError('forward check changed after scoring self-tests')
    return paths


def validate_inputs(inputs):
    from .inputs import pins
    frozen = read(inputs/'inputs.json')
    for name, expected in frozen['sha256'].items():
        if sha(inputs/name) != expected:
            raise RuntimeError(f'frozen input changed: {name}')
    if pins() != frozen['upstream']:
        raise RuntimeError('pinned checkouts changed since adapter input creation')


def pinned_solver():
    source = UPSTREAM / 'functions/CSI.m'
    pinned = subprocess.check_output(['git', '-C', str(UPSTREAM), 'show', '73a64e1:functions/CSI.m'])
    if source.read_bytes() != pinned:
        raise RuntimeError('CSI.m differs from pinned 73a64e1')
    return source


def matlab_command(mode, input_dir, out, iterations):
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    expression = f"addpath({quote(CODE)});native_fit({quote(mode)},{quote(input_dir)},{quote(out)},{iterations})"
    return ['matlab', '-batch', expression]


def scope_supported():
    try:
        probe = subprocess.run(['systemd-run', '--user', '--scope', '-p', 'MemoryMax=8G',
                                '/usr/bin/true'], capture_output=True, text=True, timeout=10)
        return probe.returncode == 0, probe.stdout + probe.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, repr(error)


def process_family(pid):
    """Include descendants even when they start another session."""
    rows = {}
    for folder in Path('/proc').iterdir():
        if not folder.name.isdigit():
            continue
        try:
            status = (folder / 'status').read_text()
            parent = int(re.search(r'^PPid:\s+(\d+)', status, re.M)[1])
            rss = re.search(r'^VmRSS:\s+(\d+)', status, re.M)
            rows[int(folder.name)] = (parent, int(rss[1])*1024 if rss else 0)
        except (OSError, TypeError):
            continue
    family = {pid}
    while True:
        expanded = family | {p for p, (parent, _) in rows.items() if parent in family}
        if expanded == family:
            return {p: rows[p][1] for p in family if p in rows}
        family = expanded


def costs(log):
    result = []
    pattern = r'^\s*(\d+)\s+([\deE+.-]+)\s+([\deE+.-]+)\s+([\deE+.-]+)\s+([\deE+.-]+)'
    for line in log.splitlines():
        match = re.match(pattern, line)
        if match:
            result.append(dict(iteration=int(match[1]), data_cost=float(match[2]),
                               state_cost=float(match[3]), total_cost=float(match[5])))
    return result


def worker(args):
    root = args.run_dir.resolve()
    out = root / 'fits' / f'{args.case}__{args.data}'
    lock_path = root / 'logs/fit.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = dict(state='preflight', utc=now(), worker_pid=os.getpid())
        write(out / 'state.json', state)
        process = None
        started = time.monotonic()
        peak = 0
        try:
            checks = check_records(root, args.case, args.data)
            solver = pinned_solver()
            inputs = root / 'inputs' / f'{args.case}__{args.data}'
            validate_inputs(inputs)
            files = [p for p in inputs.rglob('*') if p.is_file()]
            if not files or not (inputs / 'inputs.json').exists():
                raise RuntimeError('missing adapter inputs')
            write(out / 'input_hashes.json', {str(p): sha(p) for p in files + checks + [solver, CODE/'native_fit.m', CODE/'fit.py']})
            supported, probe = scope_supported()
            sample = resource_sample()  # Last check immediately before MATLAB launch.
            sample.update(scope_supported=supported, scope_probe=probe)
            write(out / 'launch_resources.json', sample)
            if not sample['allowed']:
                raise RuntimeError('MATLAB active or less than 32 GiB available')
            command = matlab_command('fit', inputs, out, args.iterations)
            unit = f'csi-native-{args.case.replace("_", "-")}-{args.data}-{os.getpid()}.scope'
            if supported:
                command = ['systemd-run', '--user', '--scope', '--unit', unit,
                           '-p', 'MemoryMax=8G', '-p', 'MemorySwapMax=0', *command]
            env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='8',
                       MKL_NUM_THREADS='8', OPENBLAS_NUM_THREADS='8')
            with (out / 'matlab.log').open('w') as log:
                process = subprocess.Popen(command, cwd=REPO, env=env, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                state.update(state='running', matlab_parent_pid=process.pid, command=command,
                             started_utc=now(), limit_method='systemd scope' if supported else 'family RSS watcher')
                write(out / 'state.json', state)
                forecast_done = False
                with (out / 'resources.jsonl').open('a') as resources:
                    while True:
                        family = process_family(process.pid)
                        rss = sum(family.values()); peak = max(peak, rss)
                        elapsed = time.monotonic()-started
                        resources.write(json.dumps(dict(utc=now(), elapsed_seconds=elapsed,
                                                        family_rss_bytes=rss, family=family))+'\n')
                        resources.flush()
                        if rss > LIMIT:
                            state['failure'] = '8 GiB process-family memory limit exceeded'
                            if supported:
                                subprocess.run(['systemctl', '--user', 'kill', '--signal=SIGKILL', unit], check=False)
                            for pid in reversed(list(family)):
                                try:
                                    os.kill(pid, signal.SIGKILL)
                                except ProcessLookupError:
                                    pass
                        history = costs((out/'matlab.log').read_text(errors='replace'))
                        if not forecast_done and any(row['iteration'] >= 64 for row in history):
                            forecast = dict(utc=now(), iteration=64, wall_seconds_at_64=elapsed,
                                            projected_total_seconds=elapsed*args.iterations/64,
                                            projected_finish_posix=time.time()+elapsed*(args.iterations/64-1),
                                            includes_configuration_time=True)
                            write(out/'iteration_64_timing.json', forecast)
                            print(json.dumps(forecast), flush=True)
                            forecast_done = True
                        rc = process.poll()
                        if rc is not None:
                            break
                        time.sleep(0.5)
            write(out/'costs.json', dict(rows=costs((out/'matlab.log').read_text(errors='replace')),
                                       note='CSI printed costs are rounded; separate from field residual'))
            state.update(state='completed' if rc == 0 and 'failure' not in state else 'failed', returncode=rc)
        except Exception:
            state.update(state='failed', failure=traceback.format_exc())
            (out/'launcher_failure.txt').write_text(state['failure'])
            if process is not None and process.poll() is None:
                for pid in process_family(process.pid):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait()
        state.update(finished_utc=now(), wall_seconds=time.monotonic()-started, peak_family_rss_bytes=peak)
        write(out/'state.json', state)
        write(out/'manifest.json', {str(p.relative_to(out)): dict(bytes=p.stat().st_size, sha256=sha(p))
                                   for p in out.rglob('*') if p.is_file() and p.name != 'manifest.json'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['circle__c4', 'kite__c4'], required=True)
    parser.add_argument('--data', choices=['clean', 'n1d0'], required=True)
    parser.add_argument('--iterations', type=int, choices=[2048], default=2048)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--check-only', action='store_true', help='sample resources and check records; never launch')
    args = parser.parse_args()
    args.run_dir = args.run_dir.resolve()
    if args.worker:
        worker(args)
        return
    if args.check_only:
        print(json.dumps(resource_sample(), indent=2))
        check_records(args.run_dir, args.case, args.data)
        pinned_solver()
        return
    # Invoked only after the coordinator writes "checks passed, go".
    check_records(args.run_dir, args.case, args.data)
    pinned_solver()
    out = args.run_dir / 'fits' / f'{args.case}__{args.data}'
    out.mkdir(parents=True, exist_ok=False)  # Every attempt is kept; no reruns.
    logs = args.run_dir / 'logs';logs.mkdir(parents=True, exist_ok=True)
    command = ['setsid', 'nohup', sys.executable, '-m', 'experiments.baselines.csi.native_tg002.fit',
               '--case', args.case, '--data', args.data, '--iterations', str(args.iterations),
               '--run-dir', str(args.run_dir), '--worker']
    with (logs/f'{args.case}__{args.data}_launcher.log').open('x') as log:
        process = subprocess.Popen(command, cwd=REPO, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    print(json.dumps(dict(detached_pid=process.pid, state_file=str(out/'state.json'))))


if __name__ == '__main__':
    main()
