"""Launch exactly one bounded pair, preserving worker exits and logs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top024 import run as r


def dispatch(output):
    r.verify(output)
    r.require(not (output/'campaign.json').exists() and not (output/'runs').exists(), 'pair already dispatched')
    started = time.monotonic()
    campaign = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(), workers=[])
    r.write(output/'campaign.json', campaign)
    env = {**os.environ, **{k: '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')}}
    def worker(arm):
        command = ['timeout', '--signal=TERM', '--kill-after=10s', '3900s', sys.executable,
                   str(Path(r.__file__)), 'arm', '--output', str(output), '--arm', arm]
        t = time.monotonic()
        with (output/f'{arm}.log').open('w') as log:
            completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        return dict(arm=arm, command=command, exit_code=completed.returncode, elapsed_seconds=time.monotonic()-t)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, arm) for arm in ('A', 'B')]
        campaign['workers'] = [future.result() for future in futures]
    campaign.update(status='COMPLETED', elapsed_seconds=time.monotonic()-started)
    r.write(output/'campaign.json', campaign)
    return campaign


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(dispatch(parser.parse_args().output.resolve())), flush=True)
