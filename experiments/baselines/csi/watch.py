"""Observe an orphaned CSI MATLAB process without restarting its inversion."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import signal
import time


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--pid', required=True, type=int)
    args = parser.parse_args()
    launch_path = args.run / 'launch.json'
    launch = json.loads(launch_path.read_text())
    start = dt.datetime.fromisoformat(launch['started_utc']).timestamp()
    elapsed = time.time() - start
    log = (args.run / 'matlab.log').read_text()
    summary_path = args.run / 'matlab_summary.json'
    complete = summary_path.exists() and 'CSI wrapper: outputs saved' in log
    pid_path = Path(f'/proc/{args.pid}/cmdline')
    alive = pid_path.exists() and b'run_example.m' in pid_path.read_bytes()
    if complete:
        summary = json.loads(summary_path.read_text())
        end = summary['completed_posix_seconds']
        launch.update(returncode=None, launcher_returncode=143, matlab_exit_code=None,
                      completion_status='MATLAB outputs saved; original launcher was interrupted',
                      wall_seconds=end-start, finished_utc=dt.datetime.fromtimestamp(end, dt.timezone.utc).isoformat(),
                      wall_time_basis='launch to final MATLAB output export, not observed process exit',
                      adopted_matlab_pid=args.pid)
        launch_path.write_text(json.dumps(launch, indent=2) + '\n')
    elif alive and elapsed > launch['timeout_seconds']:
        os.killpg(args.pid, signal.SIGTERM)
        launch.update(timed_out=True, wall_seconds=elapsed, adopted_matlab_pid=args.pid,
                      completion_status='observer stopped MATLAB at the original wall limit')
        launch_path.write_text(json.dumps(launch, indent=2) + '\n')
    record = dict(checked_utc=dt.datetime.now(dt.timezone.utc).isoformat(), matlab_pid=args.pid,
                  matlab_alive=alive, outputs_saved=complete, elapsed_seconds=elapsed,
                  original_launcher_returncode=143)
    (args.run / 'observer.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    print(log.splitlines()[-1])


if __name__ == '__main__':
    main()
