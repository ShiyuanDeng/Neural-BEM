"""B1-only resource guard and records. Import first, before numerical packages."""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
             'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_key] = '1'
import datetime
import fcntl
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'solvers'), str(ROOT)]
BASE = ROOT/'results/bem/baseline_data/brg_tg002/2026-11-18'
GIB = 1024**3
THREAD_KEYS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
              'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')


def pin_torch():
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    from bem_inverse.io import write as save
    save(path, value)


def provenance():
    status = subprocess.check_output(['git', 'status', '--porcelain', '--', 'solvers/bem_inverse/'], cwd=ROOT, text=True)
    return dict(utc=now(), commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                solver_dirty=bool(status.strip()), solver_status=status,
                solver_hashes={str(p.relative_to(ROOT)): digest(p) for p in sorted((ROOT/'solvers/bem_inverse').rglob('*.py'))},
                wrapper_hashes={str(p.relative_to(ROOT)): digest(p) for p in sorted((ROOT/'experiments/bem_on_baseline_data').glob('b1_*.py'))},
                threads={k: os.environ[k] for k in THREAD_KEYS}, command=sys.argv)


def available():
    return int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024


def bem_jobs():
    rows = []
    for p in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = p.read_bytes().decode().split('\0')
            if int(p.parent.name) == os.getpid() or not args or 'python' not in Path(args[0]).name:
                continue
            if any(Path(a).name in ('csi_fit.py', 'brg_paper.py', 'b1_run.py') for a in args[1:]):
                rows.append(dict(pid=int(p.parent.name), args=args))
        except (OSError, UnicodeError):
            pass
    return rows


def bulk(out):
    return [dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=digest(p))
            for p in sorted((out/'local').rglob('*')) if p.is_file()]


def guarded(command, out, expected_peak=3*GIB):
    """No time stop. Only the child group can be signalled by the memory guard."""
    memory = available()
    launch_memory = memory
    if memory-expected_peak-GIB <= 14*GIB:
        raise RuntimeError(f'Memory blocks launch: {memory/GIB:.3f} GiB available; need >{15+expected_peak/GIB:.3f}.')
    (out/'local').mkdir(parents=True, exist_ok=True)
    begin = provenance()
    started = time.monotonic()
    peak, gpu_peak, minimum = 0, 0, memory
    reason, gpu_seen = None, False
    processes = subprocess.check_output(['ps', '-eo', 'pid,ppid,pcpu,rss,comm'], text=True)
    (out/'local/processes.txt').write_text(processes)
    last_sample = -10.
    with (out/'local/worker.log').open('x') as log, (out/'local/resources.csv').open('x') as samples:
        samples.write('elapsed_seconds,available_bytes,host_high_water_bytes,gpu_peak_sampled_bytes\n')
        child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        while child.poll() is None:
            elapsed = time.monotonic()-started
            memory = available()
            minimum = min(minimum, memory)
            try:
                for line in Path(f'/proc/{child.pid}/status').read_text().splitlines():
                    if line.startswith(('VmRSS:', 'VmHWM:')):
                        peak = max(peak, int(line.split()[1])*1024)
            except FileNotFoundError:
                pass
            # Check reserve before any external resource query.
            if memory < 14*GIB:
                reason = 'MEMORY_REQUEUE'
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            if elapsed-last_sample >= 1:
                last_sample = elapsed
                try:
                    sample = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_gpu_memory', '--format=csv,noheader,nounits'],
                                            capture_output=True, text=True, timeout=.5)
                    for line in sample.stdout.splitlines():
                        pid, used = line.split(',')
                        if int(pid) == child.pid:
                            gpu_seen = True
                            gpu_peak = max(gpu_peak, int(used)*1024**2)
                except (ValueError, subprocess.TimeoutExpired):
                    pass
                samples.write(f'{elapsed:.6f},{memory},{peak},{gpu_peak}\n')
                samples.flush()
            time.sleep(.2)
        code = child.wait()
    end = provenance()
    row = dict(command=command, pid=child.pid, returncode=code, stop_reason=reason,
               seconds=time.monotonic()-started, expected_peak_bytes=expected_peak, margin_bytes=GIB,
               available_at_launch_bytes=launch_memory,
               minimum_available_bytes=minimum, host_peak_bytes=peak,
               gpu_sampled_peak_bytes=gpu_peak if gpu_seen else None, start=begin, end=end,
               solver_unchanged=begin['solver_hashes']==end['solver_hashes'],
               reportable=reason is None and not begin['solver_dirty'] and not end['solver_dirty']
                          and begin['solver_hashes']==end['solver_hashes'])
    row['over_120_seconds'] = row['seconds'] > 120
    row['over_1_hour'] = row['seconds'] > 3600
    write(out/'supervisor.json', row)
    write(out/'bulk_manifest.json', dict(files=bulk(out)))
    return row


@contextmanager
def file_lock(name):
    """B1-owned interprocess lock; wait without touching another agent's lock."""
    folder = BASE/'local'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder/name).open('a') as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(.25)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
