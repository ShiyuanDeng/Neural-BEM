"""Check the 24 native readings through the pinned CSI configuration."""
import os
from pathlib import Path
import signal
import subprocess
import time

import psutil

from .inputs import arguments, digest, pins, read, write_json

CODE = Path(__file__).resolve().parent
GIB = 1024**3


def utc():
    return subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()


def launch_check(run_dir, case, data, kind, matlab_function, prepare=None):
    """Record the guarded MATLAB launch and the metrics beside its log."""
    inputs = (run_dir / 'inputs' / f'{case}__{data}').resolve()
    frozen = read(inputs/'inputs.json')
    for name, expected in frozen['sha256'].items():
        if digest(inputs / name) != expected:
            raise ValueError(f'frozen {name} changed')
    if pins() != frozen['upstream']:
        raise ValueError('upstream checkout changed since inputs were frozen')
    folder = (run_dir / 'checks' / f'{kind}_{case}__{data}').resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'launch.json').exists():
        raise FileExistsError(f'check already launched at {folder}')
    if prepare:
        prepare(folder, inputs)
    matlab_pids = subprocess.run(['pgrep', '-x', 'MATLAB'], capture_output=True, text=True)
    if matlab_pids.returncode not in (0, 1):
        raise RuntimeError(matlab_pids.stderr)
    available = int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines()
                         if s.startswith('MemAvailable:'))) * 1024
    can_launch = matlab_pids.returncode == 1 and available >= 32 * GIB
    sample = dict(utc=utc(), available_bytes=available, expected_other_growth_bytes=8*GIB,
                  family_limit_bytes=8*GIB, reserve_bytes=16*GIB,
                  matlab_pids=matlab_pids.stdout.split(), launch_allowed=can_launch)
    if not can_launch:
        write_json(folder / ('wait_' + str(time.time_ns()) + '.json'), sample)
        raise SystemExit(f'waiting for MATLAB slot and 32 GiB available: {sample}')
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='8', MKL_NUM_THREADS='8',
               OPENBLAS_NUM_THREADS='8', CSI_ADAPTER=str(CODE), CSI_INPUT=str(inputs),
               CSI_CHECK=str(folder))
    command = ['matlab', '-batch', "maxNumCompThreads(8); addpath(getenv('CSI_ADAPTER')); " +
               matlab_function + "(getenv('CSI_INPUT'),getenv('CSI_CHECK'))"]
    record = dict(sample, command=command, cpu_only=True, threads=8,
                  input_manifest_sha256=digest(inputs/'inputs.json'))
    write_json(folder/'launch.json', record)
    start = time.monotonic()
    peak = 0
    min_available = available
    reason = None
    with (folder/'matlab.log').open('w') as log:
        proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        parent = psutil.Process(proc.pid)
        while proc.poll() is None:
            rss = 0
            try:
                for member in [parent] + parent.children(recursive=True):
                    try:
                        rss += member.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass
            peak = max(peak, rss)
            min_available = min(min_available, psutil.virtual_memory().available)
            if rss > 8*GIB:
                reason = 'MATLAB process family exceeded 8 GiB'
                os.killpg(proc.pid, signal.SIGKILL)
                break
            time.sleep(.25)
        rc = proc.wait()
    metrics = read(folder/'metrics.json') if (folder/'metrics.json').exists() else {}
    result = dict(metrics, passed=(rc == 0 and metrics.get('passed') is True),
                  inputs_sha256=record['input_manifest_sha256'], finished_utc=utc(),
                  returncode=rc, stop_reason=reason, seconds=time.monotonic()-start,
                  peak_family_bytes=peak, minimum_available_bytes=min_available)
    write_json(folder/'check.json', result)
    print(folder/'check.json', result, flush=True)
    if not result['passed']:
        raise SystemExit(1)
    return result


if __name__ == '__main__':
    args = arguments(__doc__)
    launch_check(args.run_dir, args.case, args.data, 'table', 'native_table_check')
