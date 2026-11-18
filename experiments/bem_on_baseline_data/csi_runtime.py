"""Shared start-up for the CSI adapter scripts: thread pins, solver path, provenance.

``CSI_SOLVER_ROOT`` may point at a clean ``git archive`` of ``solvers/`` when the
checkout's solver is being edited by its lock holder; the receipt says which was used.
"""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import datetime
import resource
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOLVERS = Path(os.environ.get('CSI_SOLVER_ROOT', ROOT/'solvers')).resolve()
sys.path[:0] = [str(SOLVERS), str(ROOT)]


def _run(*args):
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT).stdout.strip()


def memory_available_gib():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1])/1024**2
    return float('nan')


def provenance():
    snapshot = SOLVERS != (ROOT/'solvers').resolve()
    marker = SOLVERS.parent/'SNAPSHOT_COMMIT'
    return dict(
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        commit=_run('git', 'rev-parse', 'HEAD'),
        solver_source=(f'git archive snapshot at {SOLVERS}' if snapshot else 'checkout solvers/'),
        solver_snapshot_commit=marker.read_text().strip() if snapshot and marker.exists() else None,
        checkout_solver_dirty=bool(_run('git', 'status', '--porcelain', '--', 'solvers/bem_inverse')),
        solver_used_dirty=False if snapshot else bool(_run('git', 'status', '--porcelain', '--', 'solvers/bem_inverse')),
        command=' '.join([sys.executable, *sys.argv]),
        memory_available_gib=memory_available_gib(),
        load_average=os.getloadavg(),
        matlab_processes=len(_run('pgrep', '-f', 'MATLAB').split()) if _run('pgrep', '-f', 'MATLAB') else 0)


def peak_memory_gib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2
