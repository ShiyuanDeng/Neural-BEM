"""Six fixed GauGal convergence probes; no repository or upstream edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[name] = '1'
sys.path[:0] = [str(ROOT), str(ROOT/'solvers'), str(Path.home()/'Gau-Gal/src')]


def now():
    return subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()


def write(path, value):
    path = Path(path)
    temp = path.with_name(path.name+'.tmp')
    def encode(value):
        return value.tolist() if hasattr(value, 'tolist') else str(value)
    temp.write_text(json.dumps(value, indent=2, default=encode)+'\n')
    temp.replace(path)


def read(path):
    return json.loads(Path(path).read_text())


def mem_available():
    return int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                    if line.startswith('MemAvailable:')))*1024


def notify(message):
    print(message, flush=True)
    result = subprocess.run(['herdr', 'agent', 'prompt', 'w5:p1', 'native-run: '+message],
                            text=True, capture_output=True)
    with (BASE/'coordinator_notices.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(utc=now(), message=message, returncode=result.returncode,
                                     response=result.stdout+result.stderr))+'\n')


def worker(args):
    import numpy as np
    import torch
    from gaugal.paper2d.settings import SolverControls
    from experiments.comparison import gaugal as adapter, runs as R
    from experiments.gaugal_comparison import gaugal_arm as A
    torch.set_num_threads(1)
    out = BASE/args.label
    out.mkdir(exist_ok=False)
    started = time.monotonic()
    state = dict(state='building', started_utc=now(), pid=os.getpid(), exact=args.exact, case=args.case,
                 cap=args.cap, step=args.step, iterations=args.iterations, max_seconds=None)
    write(out/'state.json', state)
    try:
        run = R.Run('gaugal', 'converged' if args.exact else 'probe', 'clean', 'uc', 'fs')
        worst = [0.]; solve_count = [0]; last_mismatch = [19.]
        if args.exact:
            original_check = A.check_direct_solve
            def observe_check(collocation, applied, rhs, kind, tolerance):
                result = original_check(collocation, applied, rhs, kind, tolerance)
                worst[0] = max(worst[0], collocation.linear_solve_stats[-1]['final_rel'])
                solve_count[0] += 1
                return result
            A.check_direct_solve = observe_check
            write(out/'exact_source.json', dict(utc=now(), commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                convergence=adapter.CONVERGENCE,
                hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                        [ROOT/'experiments/gaugal_comparison/gaugal_arm.py',ROOT/'experiments/comparison/gaugal.py']}))
        blind = adapter.blind_case(run, args.case, ROOT/'results')
        chosen = A.settings(51, sigma_scale=.7, lambda_scale=.5, step_size=args.step,
                            contrast_max=15., num_iter=args.iterations)
        def checkpoint(fit):
            row = fit['history'][-1]
            event = dict(utc=now(), iteration=fit['iterations'], weighted_misfit=row['weighted_misfit'],
                         optimize_seconds=fit['optimize_seconds'])
            if args.exact:
                event.update(worst_inner_relative=worst[0], checked_solves=solve_count[0],
                             seconds_per_iteration=fit['optimize_seconds']/fit['iterations'])
                if fit['iterations'] % 20 == 0:
                    trend = 'falling' if row['weighted_misfit'] < last_mismatch[0] else 'rising'
                    notify(f"Step 3 step {args.step}, iteration {fit['iterations']}: weighted mismatch {row['weighted_misfit']:.6g} ({trend}, previous report {last_mismatch[0]:.6g}); {event['seconds_per_iteration']:.3f} s/iter; worst inner residual {worst[0]:.3g}.")
                    last_mismatch[0] = row['weighted_misfit']
            with (out/'mismatch.jsonl').open('a') as stream:
                stream.write(json.dumps(event)+'\n')
            state.update(state='running', latest=event)
            write(out/'state.json', state)
            np.savez_compressed(out/'checkpoint.npz', image=fit['image'], coefficients=fit['coefficients'],
                                predictions=fit['predictions'])
        fit = A.reconstruct(blind, chosen, controls=SolverControls(pcg_max_iter=args.cap),
                            verbose=True, max_seconds=None, checkpoint=checkpoint,
                            **(dict(convergence=adapter.CONVERGENCE) if args.exact else {}))
        record, arrays = adapter.record_from(args.case, run, fit, blind.observed)
        record.update(pcg_max_iter=args.cap, requested_iterations=args.iterations,
                      seconds_per_iteration=fit['optimize_seconds']/max(1,fit['iterations']),
                      history=fit['history'])
        calls=sum(row['calls'] for row in fit['linear_solves'])
        record.update(unconverged_share=sum(row['unconverged'] for row in fit['linear_solves'])/max(calls,1),
                      worst_final_relative=max(row['max_final_relative'] for row in fit['linear_solves']))
        np.savez_compressed(out/'fit.npz', **arrays)
        write(out/'fit.json', record)
        state.update(state='completed', finished_utc=now(), wall_seconds=time.monotonic()-started)
    except Exception:
        state.update(state='failed', finished_utc=now(), failure=traceback.format_exc(),
                     wall_seconds=time.monotonic()-started)
        (out/'failure.txt').write_text(state['failure'])
        raise
    finally:
        write(out/'state.json', state)


def launch(jobs):
    processes=[]
    for job in jobs:
        gpu=subprocess.check_output(['nvidia-smi'],text=True)
        available=mem_available()
        launch_record=dict(utc=now(), memory_available_bytes=available, gpu=gpu, job=job)
        write(BASE/(job['label']+'_launch.json'),launch_record)
        if available<14*1024**3:
            raise RuntimeError('less than 14 GiB memory available before launch')
        command=[sys.executable, str(Path(__file__).resolve()), '--worker']
        for key,value in job.items():
            if key == 'exact':
                if value: command += ['--exact']
                continue
            command += ['--'+key.replace('_','-'),str(value)]
        log=(BASE/(job['label']+'.log')).open('x')
        process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                 start_new_session=True)
        processes.append((process,log,job))
    while any(p.poll() is None for p,_,_ in processes):
        available=mem_available()
        if available<14*1024**3:
            for process,_,job in processes:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGKILL)
                    write(BASE/(job['label']+'_memory_stop.json'),dict(utc=now(), available_bytes=available))
            raise RuntimeError('14 GiB memory floor crossed; owned probes stopped')
        write(BASE/'active.json',dict(utc=now(),available_bytes=available,
                                    jobs=[dict(label=j['label'],pid=p.pid,returncode=p.poll()) for p,_,j in processes]))
        time.sleep(2)
    for process,log,job in processes:
        log.close()
        if process.returncode:
            raise RuntimeError(f"probe failed: {job['label']}, returncode {process.returncode}; see its log")


def score(label):
    import numpy as np
    from experiments.comparison import scoring as G, runs as R
    folder=BASE/label
    fit=read(folder/'fit.json')
    with np.load(folder/'fit.npz') as saved:
        arrays={key:saved[key] for key in saved.files}
    result=G.score(R.Run('gaugal','probe','clean','uc','fs'),fit['case'],fit,arrays,ROOT/'results')
    write(folder/'score.json',result)
    return result['area_error']


def saved(case):
    fit=read(ROOT/'results/gaugal/default_clean_uc_fs'/case/'fit.json')
    stats=fit['linear_solves'];calls=sum(s['calls'] for s in stats)
    return dict(seconds_per_iteration=fit['fit_seconds']/fit['work']['iterations'],
                unconverged_share=sum(s['unconverged'] for s in stats)/calls,
                worst_final_relative=max(s['max_final_relative'] for s in stats),
                iterations=fit['work']['iterations'],history=fit['history'])


def summary_fit(label):
    fit=read(BASE/label/'fit.json');history=fit['history']
    end=history[-1]['weighted_misfit'];prior=history[-min(20,len(history))]['weighted_misfit']
    return dict(label=label,case=fit['case'],cap=fit['pcg_max_iter'],iterations=fit['work']['iterations'],
                seconds_per_iteration=fit['seconds_per_iteration'],unconverged_share=fit['unconverged_share'],
                worst_final_relative=fit['worst_final_relative'],mismatch_start=history[0]['weighted_misfit'],
                mismatch_end=end,mismatch_prior20=prior,still_falling=end<prior,
                per_frequency_residual=fit['residual'],max_residual=fit['maximum_residual'])


def run_low_contrast():
    from experiments.comparison import runs as R
    destination=ROOT/'results/gaugal/converged_clean_uc_fs'
    cases=[case for case in R.CASES_20 if case.endswith('__c0.5')]
    assert len(cases)==10
    state_path=destination/'low_contrast_state.json'
    if state_path.exists():
        raise RuntimeError('low-contrast runner already attempted; no silent rerun')
    available=mem_available()
    gpu=subprocess.check_output(['nvidia-smi'],text=True)
    command=[sys.executable,'-u','-m','experiments.comparison','run',
             'gaugal/converged_clean_uc_fs','--cases',*cases]
    record=dict(state='preflight',utc=now(),cases=cases,command=command,
                available_bytes=available,gpu=gpu,runner_count=1,
                reason_one_runner='metrics.csv is written directly without a lock; run.json exists and is read-only on matching settings')
    write(destination/'low_contrast_launch.json',record)
    if available<14*1024**3:
        raise RuntimeError('less than 14 GiB available before campaign launch')
    started=time.monotonic();forecast_sent=False
    with (destination/'low_contrast_runner.log').open('x') as log:
        process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        record.update(state='running',started_utc=now(),runner_pid=process.pid,monitor_pid=os.getpid())
        write(state_path,record)
        while True:
            finished=[case for case in cases if (destination/case/'fit.json').exists()]
            available=mem_available()
            record.update(utc=now(),completed=finished,available_bytes=available,wall_seconds=time.monotonic()-started)
            write(state_path,record)
            if finished and not forecast_sent:
                first=read(destination/finished[0]/'fit.json')
                seconds=first.get('case_seconds') or record['wall_seconds']
                forecast=dict(utc=now(),first_case=finished[0],first_case_seconds=seconds,
                              first_elapsed_seconds=record['wall_seconds'],remaining_cases=10-len(finished),
                              projected_total_seconds=seconds*10,
                              projected_remaining_seconds=seconds*(10-len(finished)),
                              first_outcome=first.get('outcome'),gpu_sharing=True)
                write(destination/'first_case_forecast.json',forecast)
                notify(f"Contrast-0.5 first case {finished[0]} ended: {seconds:.1f} s, {first.get('work',{}).get('iterations')} iterations, {first.get('stop_reason')}; simple ten-case forecast {10*seconds/60:.1f} min total, {(10-len(finished))*seconds/60:.1f} min remaining with current GPU sharing.")
                forecast_sent=True
            rc=process.poll()
            if rc is not None:
                break
            if available<14*1024**3:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
                record.update(state='failed',failure='14 GiB host-memory floor crossed',finished_utc=now())
                write(state_path,record)
                notify('Contrast-0.5 campaign stopped at the 14 GiB memory floor; all evidence kept.')
                return
            time.sleep(2)
    rows=[]
    for case in cases:
        directory=destination/case
        if not (directory/'fit.json').exists():
            rows.append(dict(case=case,failure='fit missing'));continue
        fit=read(directory/'fit.json');scored=read(directory/'score.json') if (directory/'score.json').exists() else {}
        history=fit.get('history') or []
        rows.append(dict(case=case,area_error=scored.get('area_error'),
                         final_mismatch=history[-1].get('weighted_misfit') if history else None,
                         iterations=(fit.get('work') or {}).get('iterations'),stop_reason=fit.get('stop_reason'),
                         case_seconds=fit.get('case_seconds'),outcome=fit.get('outcome'),
                         worst_inner_relative=max((r.get('max_final_relative',0.) for r in fit.get('linear_solves') or []),default=None)))
    write(destination/'low_contrast_table.json',rows)
    lines=['| Case | Area error % | Final weighted mismatch | Iterations | Stop |',
           '|---|---:|---:|---:|---|']
    for row in rows:
        area=row.get('area_error');misfit=row.get('final_mismatch')
        lines.append(f"| {row['case']} | {100*area if area is not None else 'null'} | {misfit} | {row.get('iterations')} | {row.get('stop_reason',row.get('failure'))} |")
    (destination/'low_contrast_table.md').write_text('\n'.join(lines)+'\n')
    record.update(state='completed' if rc==0 else 'failed',returncode=rc,finished_utc=now(),
                  wall_seconds=time.monotonic()-started,rows=rows)
    write(state_path,record)
    notify('Contrast-0.5 campaign ended. '+'; '.join(f"{r['case']}: area {100*r['area_error']:.2f}%, mismatch {r['final_mismatch']:.4g}, iterations {r['iterations']}, {r['stop_reason']}" if r.get('area_error') is not None and r.get('final_mismatch') is not None else f"{r['case']}: {r}" for r in rows)+'. Table saved; preparing commit and push.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--exact',action='store_true')
    parser.add_argument('--step3-exact',action='store_true')
    parser.add_argument('--run-low-contrast',action='store_true')
    parser.add_argument('--collect-step1',action='store_true')
    parser.add_argument('--label');parser.add_argument('--case')
    parser.add_argument('--cap',type=int);parser.add_argument('--step',type=float)
    parser.add_argument('--iterations',type=int)
    args=parser.parse_args()
    if args.worker:
        return worker(args)
    if args.run_low_contrast:
        return run_low_contrast()
    if args.step3_exact:
        path=BASE/'step3_controller.json'
        if path.exists():
            raise RuntimeError('Step 3 already attempted; do not silently rerun')
        state=dict(state='running',started_utc=now(),pid=os.getpid(),commit='86232abe1',
                   steps=[.2,1.],iterations=200,truth_scoring=False)
        write(path,state)
        try:
            launch([dict(label='step3_exact_step'+str(step),case='kite__c4',cap=100,
                         step=step,iterations=200,exact=True) for step in [.2,1.]])
            results=[summary_fit('step3_exact_step'+str(step)) for step in [.2,1.]]
            write(BASE/'step3.json',results)
            notify('Step 3 done. '+'; '.join(f"{r['label']}: {r['iterations']} iterations, mismatch {r['mismatch_start']:.4g}->{r['mismatch_end']:.4g}, {r['seconds_per_iteration']:.3f}s/iter, worst inner {r['worst_final_relative']:.3g}" for r in results)+'. No truth scores used. Part 2 waits for go.')
            state.update(state='completed',finished_utc=now())
        except Exception:
            state.update(state='failed',finished_utc=now(),failure=traceback.format_exc())
            notify('Step 3 failed: '+state['failure'].splitlines()[-1]+'. Outputs retained; no rerun.')
            raise
        finally:
            write(path,state)
        return
    if not args.collect_step1:
        raise RuntimeError('Step 2 cancelled; Step 3 waits for exact-solve commit and coordinator instruction')
    state=read(BASE/'controller.json')
    state.update(state='step1_collecting',controller_replaced_utc=now(),pid=os.getpid(),
                 step2='skipped by coordinator',step3='hold for exact-solve commit')
    write(BASE/'controller.json',state)
    cases=['kite__c4','kite__c0.5']
    while True:
        states=[read(BASE/('step1_'+c)/'state.json') for c in cases]
        if all(row['state'] in ('completed','failed') for row in states):
            break
        if mem_available()<14*1024**3:
            for row in states:
                if row['state'] not in ('completed','failed'):
                    os.killpg(row['pid'],signal.SIGKILL)
            state.update(state='failed',failure='14 GiB memory floor crossed',finished_utc=now())
            write(BASE/'controller.json',state)
            notify('Step 1 stopped at the 14 GiB host-memory floor; outputs preserved.')
            return
        time.sleep(2)
    if any(row['state']=='failed' for row in states):
        state.update(state='failed',finished_utc=now())
        write(BASE/'controller.json',state)
        notify('Step 1 worker failed; see retained state and logs. No rerun.')
        return
    comparison=[];lines=[]
    for case in cases:
        measured=summary_fit('step1_'+case);reference=saved(case)
        comparison.append(dict(case=case,cap2000=measured,saved_cap100=reference))
        lines.append(f"{case}: cap2000 {100*measured['unconverged_share']:.1f}% unconverged, worst {measured['worst_final_relative']:.3g}, {measured['seconds_per_iteration']:.2f}s/iter; saved cap100 {100*reference['unconverged_share']:.1f}%, worst {reference['worst_final_relative']:.3g}, {reference['seconds_per_iteration']:.2f}s/iter")
    write(BASE/'step1.json',comparison)
    notify('Step 1 done. '+'; '.join(lines)+'. Step 2 skipped; Step 3 held for exact-solve commit.')
    for case in cases:
        score('step1_'+case)
    state.update(state='step1_completed_step3_held',finished_step1_utc=now())
    write(BASE/'controller.json',state)


if __name__=='__main__':
    main()
