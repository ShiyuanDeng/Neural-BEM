"""Two-fit B1 queue; data checks remain in the independent read-only watcher."""
from b1_runtime import ROOT, BASE, GIB, available, now, file_lock, write, digest
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import b1_data as D

DOC = ROOT/'docs/iterations/adapt_bem_to_baseline_data/06_fit_brg_tg002_cases'
RUNNER = ROOT/'experiments/bem_on_baseline_data/b1_run.py'
CONCURRENCY = 2  # Coordinator allocation; only the coordinator raises this.


def metric(case, row):
    paths = sorted((BASE/case/row).glob('attempt_*/metrics.json'))
    return json.loads(paths[-1].read_text()) if paths else None


def attempts(case, row):
    return sorted((BASE/case/row).glob('attempt_*'))


def peak():
    paths = [p for pattern in ('*/*/attempt_*/supervisor.json', '*/*/attempt_*/worker_end.json') for p in BASE.glob(pattern)]
    return max([3*GIB]+[json.loads(p.read_text())['host_peak_bytes'] for p in paths])


def pending_reserve(active):
    reserved = 0
    for task in active.values():
        used = 0
        try:
            children = Path(f'/proc/{task["process"].pid}/task/{task["process"].pid}/children').read_text().split()
            for pid in children:
                command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
                if b'_fit' not in command:
                    continue
                for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                    if line.startswith('VmRSS:'):
                        used += int(line.split()[1])*1024
        except OSError:
            pass
        reserved += max(0, task['expected']-used)
    return reserved


def table(fits):
    lines = ['| Case | Outcome | Last stage | Units | Seconds | Area error | Host / GPU GiB |',
             '|---|---|---|---:|---:|---:|---:|']
    for f in fits:
        host = f['host_peak_bytes']/GIB
        gpu = f.get('gpu_sampled_peak_bytes')
        gpu = '—' if gpu is None else f'{gpu/GIB:.3f}'
        lines.append(f"| {f['case']} | {f['outcome']} | {(f.get('last_stage') or {}).get('label')} | {f['work_units']} | {f['fit_seconds']} | {f['area_error']:.8g} | {host:.3f} / {gpu} |")
    return '\n'.join(lines)


def run():
    started = now()
    phase, active, completed = 'known', {}, []
    blocked = None
    (BASE/'local').mkdir(exist_ok=True)
    with file_lock('queue.lock'):
        while True:
            checks = {}
            for case in D.ORDER:
                p = BASE/case/'checks/qualification.json'
                if p.exists():
                    checks[case] = json.loads(p.read_text())
            failed = [c for c,q in checks.items() if not q['passes']]
            if failed:
                blocked = 'Failed data check: '+', '.join(failed)
            for key, task in list(active.items()):
                code = task['process'].poll()
                if code is None:
                    continue
                task['stream'].close()
                del active[key]
                case, row = key
                m = metric(case, row)
                old = attempts(case, row)
                stopped = [p for p in old if (p/'requeue.json').exists()]
                if code == 75:
                    print(now(), 'Capacity wait:', case, row, flush=True)
                elif len(stopped) >= 2 and m is None:
                    blocked = f'Repeated memory requeue: {case} {row}'
                elif stopped and m is None and code == 0:
                    print(now(), 'Memory requeue, first occurrence:', case, row, flush=True)
                elif code != 0 or m is None:
                    blocked = f'Worker/bookkeeping exit {code}: {case} {row}; inspect {task["log"]}'
                else:
                    completed.append(dict(case=case, row=row, utc=now(), outcome=m['outcome']))
                    print(now(), 'FINISHED', case, row, m['outcome'], 'units', m['work_units'], 'seconds', m['fit_seconds'], 'area', m['area_error'], flush=True)
                    if m['outcome'] in ('EXCEPTION', 'WORKER_FAILURE'):
                        blocked = f'Crash needs review: {case} {row}'
                    if m.get('series_refusal'):
                        print('SERIES REFUSAL retained:', case, row, flush=True)
            ready = [c for c in D.ORDER if c in checks and checks[c]['passes']]
            missing_known = [(c,'known') for c in ready if metric(c,'known') is None and (c,'known') not in active]
            active_known = any(row=='known' for _,row in active)
            if phase=='known' and not missing_known and not active_known and not blocked:
                fits = [metric(c,'known') for c in ready]
                text = table(fits)
                print('\nKNOWN ROW ON CHECKED CASES COMPLETE\n'+text+'\nContinuing directly to recovered contrast.\n', flush=True)
                (DOC/'known_row_table.md').write_text('# Known row on checked cases\n\n'+now()+'\n\n'+text+'\n')
                phase = 'recovered'
            candidates = missing_known
            if phase=='recovered':
                candidates += [(c,'recovered') for c in ready if metric(c,'known') is not None and metric(c,'recovered') is None and (c,'recovered') not in active]
            if not blocked:
                for case, row in candidates:
                    if len(active) >= CONCURRENCY:
                        break
                    expected = peak()
                    reserve = pending_reserve(active)
                    memory = available()
                    if memory-expected-GIB-reserve <= 14*GIB:
                        break
                    count = len(attempts(case,row))+1
                    log = BASE/'local'/f'queue_{case}_{row}_{count:02d}_{time.time_ns()}.log'
                    stream = log.open('x')
                    child = subprocess.Popen([sys.executable, str(RUNNER), 'fit', '--case', case, '--row', row], cwd=ROOT,
                                             stdout=stream, stderr=subprocess.STDOUT)
                    active[(case,row)] = dict(process=child, stream=stream, expected=expected, log=str(log.relative_to(ROOT)))
                    with (BASE/'local/queue_launches.jsonl').open('a') as journal:
                        journal.write(json.dumps(dict(utc=now(),case=case,row=row,pid=child.pid,available_bytes=memory,
                                                      expected_peak_bytes=expected,unconsumed_reservation_bytes=reserve,
                                                      margin_bytes=GIB,floor_bytes=14*GIB))+'\n')
                    print(now(), 'LAUNCH', case, row, 'pid', child.pid, 'available GiB', round(memory/GIB,3), flush=True)
                    time.sleep(.5)
            done = sum(metric(c,r) is not None for c in D.CASES for r in ('known','recovered'))
            state = dict(started=started, updated=now(), pid=os.getpid(), phase=phase, concurrency=CONCURRENCY,
                         completed_count=done, planned=40, active=[dict(case=c,row=r,pid=t['process'].pid) for (c,r),t in active.items()],
                         completed_this_queue=completed, pending_inputs=[c for c in D.CASES if c not in ready],
                         blocked=blocked, status='blocked' if blocked else 'complete' if done==40 else 'running')
            write(BASE/'queue.json',state)
            if not active and (blocked or done==40):
                print(now(), 'QUEUE STOP', json.dumps(state), flush=True)
                return 2 if blocked else 0
            time.sleep(2.)


if __name__=='__main__':
    raise SystemExit(run())
