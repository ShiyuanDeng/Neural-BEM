"""Guard this activity's child process group and retain resource/provenance receipts."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'results/bem/baseline_data/gpu_table_path/2026-11-18'
GIB = 1024**3


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('--estimate-gib', type=float, default=4.)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    assert command
    out = BASE / args.label
    out.mkdir(parents=True, exist_ok=True)
    receipt_path = out / 'resources.json'
    assert not receipt_path.exists(), 'Never overwrite a run.'
    prior = sum(json.loads(p.read_text()).get('wall_seconds', 0.) for p in BASE.glob('*/resources.json'))
    remaining = 3600. - prior
    assert remaining > 180, 'Shared one-hour check budget exhausted.'
    available = psutil.virtual_memory().available
    assert available - args.estimate_gib*GIB >= 16*GIB, 'Memory blocks this run: must leave 16 GiB.'
    idle = [100.-x for x in psutil.cpu_percent(interval=1., percpu=True)]
    dirty = git('status', '--porcelain', '--', 'solvers/bem_inverse')
    record = dict(command=command, started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  commit=git('rev-parse', 'HEAD'), solver_dirty=dirty,
                  available_start_bytes=available, estimated_peak_gib=args.estimate_gib,
                  idle_cpu_equivalents=sum(idle)/100., idle_percent_per_cpu=idle,
                  minimum_available_bytes=available, peak_group_rss_bytes=0,
                  limit_seconds=min(remaining, 3600.), stop_reason=None)
    record['solver_source_hashes'] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT/'solvers/bem_inverse').rglob('*.py'))}
    env = dict(os.environ, PYTHONPATH=str(ROOT/'solvers')+':'+str(ROOT),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    record['gpu_at_start'] = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=name,memory.total,memory.used', '--format=csv'], text=True).strip()
    receipt_path.write_text(json.dumps(record, indent=2)+'\n')
    start = time.monotonic()
    print(json.dumps(record, indent=2), flush=True)
    with (out/'process.log').open('w') as stream:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True,
                                stdout=stream, stderr=subprocess.STDOUT)
        root = psutil.Process(proc.pid)
        while proc.poll() is None:
            available = psutil.virtual_memory().available
            record['minimum_available_bytes'] = min(record['minimum_available_bytes'], available)
            rss = 0
            try:
                family = [root, *root.children(recursive=True)]
                for member in family:
                    try:
                        rss += member.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass
            record['peak_group_rss_bytes'] = max(record['peak_group_rss_bytes'], rss)
            if available < 14*GIB:
                record['stop_reason'] = 'Available memory below 14 GiB'
            elif time.monotonic()-start > record['limit_seconds']:
                record['stop_reason'] = 'Shared check budget / one-hour process limit'
            if record['stop_reason']:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                break
            time.sleep(.5)
        record['returncode'] = proc.wait()
    record.update(wall_seconds=time.monotonic()-start,
                  ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  solver_dirty_end=git('status', '--porcelain', '--', 'solvers/bem_inverse'),
                  child_maxrss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024)
    record['gpu_at_end'] = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=name,memory.total,memory.used', '--format=csv'], text=True).strip()
    record['process_log_sha256'] = hashlib.sha256((out/'process.log').read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2), flush=True)
    sys.exit(record['returncode'] or (1 if record['stop_reason'] else 0))


if __name__ == '__main__':
    main()
