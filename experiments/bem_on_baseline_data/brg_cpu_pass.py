"""One CPU pass on the qualified BRG prefixes, bounded by idle cores and memory."""
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from brg_paper import (BASE, CASES, GIB, ROOT, available_memory, fixed_resolution,
                       fit_case, now, solver_state, write)

DOCS = ROOT/'docs/iterations/adapt_bem_to_baseline_data/02_fit_brg_paper_cases'


def idle_cores():
    def sample():
        row = Path('/proc/stat').read_text().splitlines()[0].split()[1:]
        values = [int(v) for v in row[:8]]
        return sum(values), values[3]+values[4]
    total, idle = sample()
    time.sleep(1)
    total2, idle2 = sample()
    cores = len([line for line in Path('/proc/stat').read_text().splitlines() if line.startswith('cpu')])-1
    return cores * (idle2-idle)/max(1, total2-total)


def save_commit(case, metrics):
    report = DOCS/'cpu_pass_progress.md'
    with report.open('a') as stream:
        stream.write(f'\n## {case}, {now()}\n\n')
        stream.write(f'Outcome: {metrics.get("outcome")}; last active k: {metrics.get("final_active_k")}; '
                     f'area error: {metrics.get("area_error")}; '
                     f'supervisor stop: {metrics.get("supervisor_stop")}.\n')
    paths = [str(report.relative_to(ROOT)), str((BASE/case/'cpu_fit').relative_to(ROOT))]
    subprocess.run(['git', 'add', '--', *paths], cwd=ROOT, check=True)
    subprocess.run(['git', 'commit', '-m', f'Record BRG {case} CPU pass endpoint', '--', *paths], cwd=ROOT, check=True)
    subprocess.run(['git', 'push', 'origin', 'organised'], cwd=ROOT, check=True)


def main():
    selection = fixed_resolution()
    record_path = BASE/'cpu_pass.json'
    assert not record_path.exists(), 'Keep the first CPU pass; no tuning reruns.'
    report = DOCS/'cpu_pass_progress.md'
    assert not report.exists(), 'Keep the first CPU pass progress.'
    report.write_text('# BRG paper cases: CPU pass\n\nOne pass at the fixed dataset resolution; timings are indicative.\n')
    record = dict(started=now(), solver_start=solver_state(), fixed_K=selection['fixed_K'],
                  expected_peak_bytes=selection['expected_fit_peak_bytes'], launches=[], completed=[])
    write(record_path, record)
    expected = selection['expected_fit_peak_bytes']
    pending = list(CASES)
    active = {}
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(CASES)) as workers:
        while pending or active:
            idle = idle_cores()
            available = available_memory()
            # Measure the first fit before admitting parallel workers.
            slots = max(0, int(math.floor(idle)))
            if not record['completed']:
                slots = min(slots, 1-len(active))
            reservation = sum(max(0, expected-item['rss']) for item in active.values())
            while pending and slots > 0 and available-reservation-expected >= 16*GIB:
                case = pending.pop(0)
                record['launches'].append(dict(case=case, started=now(), idle_cores=idle,
                      available_bytes=available, expected_peak_bytes=expected, active_cases=list(active)))
                future = workers.submit(fit_case, case, 'cpu')
                active[case] = dict(future=future, rss=0)
                reservation += expected
                slots -= 1
                print(f'LAUNCH {case}: idle={idle:.2f} available={available/GIB:.2f} GiB expected={expected/GIB:.2f} GiB', flush=True)
                write(record_path, record)
            if not active and pending:
                record.update(stop_reason='No idle CPU core or memory for next fit', pending=pending,
                              idle_cores=idle, available_bytes=available)
                write(record_path, record)
                raise RuntimeError(record['stop_reason'])
            done = []
            for case, item in active.items():
                # Read RSS of the numerical child via its manifest command only for reservation.
                # Observed memory availability remains the launch/stop authority.
                supervisor = BASE/case/'cpu_fit/supervisor.json'
                if item['future'].done():
                    item['future'].result()
                    receipt = json.loads(supervisor.read_text())
                    metrics_path = BASE/case/'cpu_fit/metrics.json'
                    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else dict(outcome='SCORING_FAILURE')
                    # Replace the conservative first-fit estimate with measured
                    # fit/forward peaks, retaining 20% headroom for later cases.
                    forward_peak = max(v['peak_rss_bytes'] for v in selection['cases'].values())
                    observed = [v['supervisor'].get('peak_rss_bytes', 0) for v in record['completed']]
                    expected = 1.2*max(forward_peak, receipt.get('peak_rss_bytes', 0), *observed)
                    record['completed'].append(dict(case=case, metrics=metrics, supervisor=receipt))
                    record['expected_peak_bytes'] = expected
                    write(record_path, record)
                    save_commit(case, metrics)
                    done.append(case)
            for case in done:
                del active[case]
            # Account for resident children before reserving their remaining expected peak.
            if active:
                processes = subprocess.run(['ps', '-eo', 'rss,args'], capture_output=True, text=True, check=True).stdout.splitlines()
                for case, item in active.items():
                    item['rss'] = sum(int(line.split(None, 1)[0])*1024 for line in processes
                                      if 'brg_paper.py _fit' in line and f'--case {case} ' in line)
            time.sleep(.5)
    record.update(ended=now(), wall_seconds=time.monotonic()-started, solver_end=solver_state(), status='complete')
    write(record_path, record)
    print(f'CPU PASS COMPLETE: {len(record["completed"])} cases in {record["wall_seconds"]:.1f} s', flush=True)


if __name__ == '__main__':
    main()
