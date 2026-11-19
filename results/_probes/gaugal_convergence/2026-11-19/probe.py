"""Six fixed GauGal convergence probes; no repository or upstream edits."""
import argparse
import fcntl
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


def run_continuation():
    from experiments.comparison import runs as R
    destination=ROOT/'results/gaugal/converged_clean_uc_fc'
    cases=[c for c in R.CASES_20 if c.endswith('__c4') and c!='kite__c4']
    cases += [c for c in R.CASES_20 if c.endswith('__c0.5')]
    assert len(cases)==19 and 'kite__c4' not in cases
    assert (destination/'kite__c4/score.json').exists()
    state_path=destination/'continuation_state.json'
    if state_path.exists():
        raise RuntimeError('continuation runner already attempted; no silent rerun')
    command=[sys.executable,'-u','-m','experiments.comparison','run','gaugal/converged_clean_uc_fc','--cases',*cases]
    available=mem_available();gpu=subprocess.check_output(['nvidia-smi'],text=True)
    state=dict(state='preflight',utc=now(),cases=cases,command=command,
               available_bytes=available,gpu=gpu,runner_count=1,settings='unchanged committed continuation variant',
               code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    write(destination/'continuation_launch.json',state)
    if available<14*1024**3:
        raise RuntimeError('less than 14 GiB available before continuation launch')
    sent=set();started=time.monotonic()
    with (destination/'continuation_runner.log').open('x') as log:
        process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state.update(state='running',started_utc=now(),runner_pid=process.pid,monitor_pid=os.getpid())
        write(state_path,state)
        while True:
            rows=[]
            for case in cases:
                folder=destination/case
                if not (folder/'fit.json').exists() or not (folder/'score.json').exists():
                    continue
                fit=read(folder/'fit.json');scored=read(folder/'score.json');history=fit.get('history') or []
                row=dict(case=case,area_error=scored.get('area_error'),
                         final_mismatch=history[-1].get('weighted_misfit') if history else None,
                         worst_frequency_residual=fit.get('maximum_residual'),seconds=fit.get('case_seconds'),
                         iterations=(fit.get('work') or {}).get('iterations'),stop_reason=fit.get('stop_reason'),
                         outcome=fit.get('outcome'))
                rows.append(row)
                if case not in sent:
                    if row['area_error'] is not None and row['final_mismatch'] is not None:
                        notify(f"Continuation {case}: area {100*row['area_error']:.3f}%, final mismatch {row['final_mismatch']:.6g}, worst frequency residual {row['worst_frequency_residual']:.6g}, {row['seconds']:.1f} s; {row['iterations']} iterations, {row['stop_reason']}.")
                    else:
                        notify(f"Continuation {case}: {row}; see saved fit/score, no rerun.")
                    sent.add(case)
            write(destination/'continuation_table.json',rows)
            state.update(utc=now(),completed=[r['case'] for r in rows],available_bytes=mem_available(),wall_seconds=time.monotonic()-started)
            write(state_path,state)
            code=process.poll()
            if code is not None:
                break
            if state['available_bytes']<14*1024**3:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
                state.update(state='failed',failure='14 GiB host-memory floor crossed',finished_utc=now())
                write(state_path,state)
                notify('Continuation stopped at the 14 GiB memory floor; results kept.')
                return
            time.sleep(2)
    state.update(state='completed' if code==0 else 'failed',returncode=code,finished_utc=now())
    write(state_path,state)
    notify(f"Continuation runner ended with returncode {code}: {len(sent)}/19 case results saved; table at results/gaugal/converged_clean_uc_fc/continuation_table.json.")


def continuation_row(folder):
    fit=read(folder/'fit.json'); scored=read(folder/'score.json')
    stages=fit.get('stages') or []; history=fit.get('history') or []
    source=(fit.get('code_at_start') or {}).get('commit',fit.get('commit'))
    # A recorded restart field is authoritative for the safeguarded implementation.
    guarded=any('restarts' in stage for stage in stages)
    if not guarded and source:
        guarded=subprocess.run(['git','merge-base','--is-ancestor','c20b5dfeb',source],cwd=ROOT,capture_output=True).returncode==0
    diverged=False
    for stage in stages:
        count=stage['frequency_count']
        values=[h['weighted_misfit'] for h in history if h.get('frequency_count')==count]
        initial=stage.get('initial_weighted_mismatch')
        if initial is not None:
            values.append(stage.get('final_weighted_mismatch',initial))
            diverged |= any(not __import__('math').isfinite(v) or v>2*initial for v in values)
    failed=fit.get('outcome') in ('FAILED','EXCEPTION_PARTIAL') or fit.get('stop_reason') in ('exception','restart_limit')
    return dict(case=folder.name,area_error=scored.get('area_error'),
        final_mismatch=history[-1].get('weighted_misfit') if history else None,
        worst_frequency_residual=fit.get('maximum_residual'),seconds=fit.get('case_seconds'),
        iterations=(fit.get('work') or {}).get('iterations'),stop_reason=fit.get('stop_reason'),
        outcome=fit.get('outcome'),code_at_start=source,guarded=guarded,
        final_step_size=stages[-1].get('step_size',fit.get('settings',{}).get('step_size',.2)) if stages else fit.get('settings',{}).get('step_size',.2),
        restarts=sum(stage.get('restarts',0) for stage in stages),
        old_failed=bool(folder.name.endswith('__c0.5') and not guarded and (failed or diverged)))


def attach_continuation():
    """Attach CPU reporting, then archive/retry old failures after the original CLI exits."""
    import shutil
    destination=ROOT/'results/gaugal/converged_clean_uc_fc'
    state=read(destination/'continuation_state.json'); cases=state['cases']
    state.update(monitor_pid=os.getpid(),reporting_revision='step-safeguard',state='running')
    parent=1921378; retry=None
    sent={c:read(destination/c/'fit.json').get('code_at_start') for c in state.get('completed',[])}
    def alive(pid):
        try:
            return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1][0]!='Z'
        except FileNotFoundError:
            return False
    while True:
        rows=[]
        for case in cases:
            folder=destination/case
            if not (folder/'fit.json').exists() or not (folder/'score.json').exists(): continue
            row=continuation_row(folder);rows.append(row)
            fingerprint=read(folder/'fit.json').get('code_at_start')
            if case not in sent or sent[case]!=fingerprint:
                notify(f"Continuation {case}: area {100*row['area_error']:.3f}%, final mismatch {row['final_mismatch']:.6g}, worst frequency residual {row['worst_frequency_residual']:.6g}, {row['seconds']:.1f} s; step {row['final_step_size']}, restarts {row['restarts']}; {row['iterations']} iterations, {row['stop_reason']}; code {row['code_at_start'][:9]}.")
                sent[case]=fingerprint
        write(destination/'continuation_table.json',rows)
        state.update(utc=now(),completed=[r['case'] for r in rows],available_bytes=mem_available(),runner_pid=parent)
        write(destination/'continuation_state.json',state)
        if not alive(parent):
            if retry is None:
                failed=[r['case'] for r in rows if r['old_failed']]
                if failed:
                    archive=BASE/'failed_before_step_safeguard';archive.mkdir(exist_ok=True)
                    moved=[]
                    for case in failed:
                        target=archive/case
                        if target.exists(): raise RuntimeError(f'archive already exists: {target}')
                        shutil.move(str(destination/case),str(target));moved.append(str(target.relative_to(ROOT)))
                    write(archive/'archive.json',dict(utc=now(),cases=failed,original_runner_pid=1921378,
                        original_runner_finished=True,reason='Old-code divergence; approved retry with c20b5dfeb safeguard'))
                    moved.append(str((archive/'archive.json').relative_to(ROOT)))
                    git_lock=(BASE/'publisher.lock').open('a');fcntl.flock(git_lock,fcntl.LOCK_EX)
                    subprocess.run(['git','add','--',*moved],cwd=ROOT,check=True)
                    for case in failed:
                        subprocess.run(['git','add','-f','--',str((archive/case/'fit.npz').relative_to(ROOT))],cwd=ROOT,check=True)
                    subprocess.run(['git','commit','-m','Preserve pre-safeguard GauGal failures','--',*moved],cwd=ROOT,check=True)
                    subprocess.run(['git','push'],cwd=ROOT,check=True)
                    fcntl.flock(git_lock,fcntl.LOCK_UN);git_lock.close()
                    notify('Old-code failures archived and pushed: '+', '.join(failed)+'. Starting the approved safeguarded retry.')
                    available=mem_available();gpu=subprocess.check_output(['nvidia-smi'],text=True)
                    if available<14*1024**3: raise RuntimeError('14 GiB floor before approved retry')
                    command=[sys.executable,'-u','-m','experiments.comparison','run','gaugal/converged_clean_uc_fc','--cases',*failed]
                    log=(destination/'continuation_retry.log').open('x')
                    retry=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    parent=retry.pid
                    write(destination/'continuation_retry_launch.json',dict(utc=now(),pid=parent,command=command,available_bytes=available,gpu=gpu,
                        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
                    for case in failed: sent.pop(case,None)
                    continue
            state.update(state='completed',finished_utc=now(),returncode=retry.poll() if retry else None)
            write(destination/'continuation_state.json',state)
            notify(f"Continuation including approved retries ended: {len(rows)}/19 requested results saved. Other paused work remains paused.")
            return
        time.sleep(3)


def finish_continuation_report(destination):
    """Keep the final report and run-level evidence after all approved work ends."""
    import re
    rows=[continuation_row(destination/c) for c in read(destination/'continuation_launch.json')['cases']
          if (destination/c/'score.json').exists()]
    saved=continuation_row(destination/'kite__c4')
    all_rows=rows+[saved]
    report=ROOT/'docs/iterations/evaluate_our_method/06_make_gaugal_fits_converge/run_report.md'
    text=report.read_text()
    marker='## Continuation completion summary'
    if marker not in text:
        position=text.index('## Evidence')
        counts={contrast:sum(r['area_error']<=.05 for r in all_rows if r['case'].endswith(contrast)) for contrast in ('__c4','__c0.5')}
        archived=BASE/'failed_before_step_safeguard/archive.json'
        failures=read(archived)['cases'] if archived.exists() else []
        body=(marker+'\n\n'+f"Finished {len(rows)}/19 requested cases, plus saved kite__c4. "
              f"Area error <=5%: c4 {counts['__c4']}/10; c0.5 {counts['__c0.5']}/10. "
              "Area is reported only after fitting; it never selected a step or a restart.\n\n"
              +f"Archived old-code failures: {', '.join(failures) or 'none'}. "
              "The approved retries use the same fixed CLI variant and the committed safeguard. "
              "Cap-2000 probes and the simultaneous-frequency campaign remain paused for the coordinator.\n\n"
              +f"Saved kite__c4 source: {saved['code_at_start']}; final step {saved['final_step_size']}; restarts {saved['restarts']}.\n\n")
        text=text[:position]+body+text[position:]
    text=re.sub(r'Runs: .*',f'Runs: 2/4 probes and 2/10 simultaneous cases completed (paused); {len(rows)}/19 continuation cases completed plus saved kite__c4',text)
    text=re.sub(r'Result: exact step 0.2:.*', 'Result: continuation results and exact case start commits are recorded above; all approved retries finished',text)
    text=re.sub(r'Result: exact step 1.0:.*\n','',text)
    text=re.sub(r'Failures: .*','Failures: original circle__c0.5 divergence retained outside canonical run; retry results recorded above',text)
    text=re.sub(r'New unknowns: .*','New unknowns: paused cap-2000 probe statistics and remaining simultaneous-frequency results',text)
    text=re.sub(r'Proposed next activity: .*','Proposed next activity: coordinator decides when to resume retained paused work; needs user decision: resume timing',text)
    report.write_text(text)
    evidence=[destination/name for name in ('continuation_launch.json','continuation_state.json','continuation_table.json',
        'continuation_table.md','continuation_retry_launch.json','continuation_retry.log','continuation_runner.log',
        'continuation_publish_state.json','exclusive_gpu_allocation.json','safeguard_hold.json')]
    evidence+=[report,Path(__file__).resolve()]
    paths=[str(p.relative_to(ROOT)) for p in evidence if p.exists()]
    lock=(BASE/'publisher.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    try:
        subprocess.run(['git','add','--',*paths],cwd=ROOT,check=True)
        subprocess.run(['git','diff','--cached','--check','--',*paths],cwd=ROOT,check=True)
        subprocess.run(['git','commit','-m','Summarize completed GauGal continuation and safeguarded retry','--',*paths],cwd=ROOT,check=True)
        subprocess.run(['git','push'],cwd=ROOT,check=True)
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)
        print('Post-push status (shared/paused files may remain):\n'+status,flush=True)
    finally:
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()


def publish_continuation():
    """Publish completed, immutable case files in small batches; no GPU imports."""
    import re
    import numpy as np
    destination=ROOT/'results/gaugal/converged_clean_uc_fc'
    status_path=destination/'continuation_publish_state.json'
    # Replacement CPU publisher resumes from committed evidence, never from case-name memory.
    cases=read(destination/'continuation_launch.json')['cases']
    published=[]
    for case in cases:
        tracked=subprocess.run(['git','cat-file','-e',f'HEAD:results/gaugal/converged_clean_uc_fc/{case}/fit.npz'],cwd=ROOT,capture_output=True)
        if tracked.returncode==0:
            published.append(case)
    state=dict(state='watching',started_utc=now(),pid=os.getpid(),published=published)
    write(status_path,state)
    def git(command):
        last=None
        for attempt in range(10):
            result=subprocess.run(['git',*command],cwd=ROOT,text=True,capture_output=True)
            with (destination/'continuation_publish.log').open('a') as log:
                log.write(now()+' '+repr(command)+'\n'+result.stdout+result.stderr)
            if result.returncode==0:
                return result.stdout.strip()
            last=result.stdout+result.stderr
            if 'index.lock' not in last and 'another git process' not in last:
                break
            time.sleep(2)
        raise RuntimeError(last)
    try:
        while True:
            runner=read(destination/'continuation_state.json')
            ready=[c for c in runner.get('completed',[]) if c not in published and (destination/c/'score.json').exists() and not continuation_row(destination/c)['old_failed']]
            terminal=runner['state'] in ('completed','failed')
            if len(ready)<2 and not (terminal and ready):
                if terminal and not ready:
                    state.update(state='completed',finished_utc=now(),published=published)
                    write(status_path,state)
                    finish_continuation_report(destination)
                    notify(f"Continuation publishing complete: {len(published)}/19 requested cases committed and pushed. Paused probes and simultaneous-frequency fits were not resumed.")
                    return
                time.sleep(3)
                continue
            # Two cases are about 3 MB together, below the roughly 5 MB policy.
            selected=ready[:2];paths=[];forced=[]
            for case in selected:
                folder=destination/case;fit=read(folder/'fit.json');scored=read(folder/'score.json')
                checks=dict(passed=True,protocol=scored.get('protocol',{}).get('version'))
                try:
                    with np.load(folder/'fit.npz') as arrays:
                        checks['finite_image']=bool(np.isfinite(arrays['image']).all())
                        checks['predictions_shape']=list(arrays['predicted'].shape)
                        checks['saved_inner_arrays_valid']=all(np.isfinite(arrays[k]).all() and float(arrays[k].max())<=1e-4 for k in arrays.files if k.endswith('_relative_residual') and '_rejected_' not in k)
                    all_stats=fit.get('linear_solves') or []
                    stats=[v for v in all_stats if 'rejected_attempt' not in v]
                    checks['rejected_solve_groups']=len(all_stats)-len(stats)
                    checks['worst_inner_relative']=max((v['max_final_relative'] for v in stats),default=None)
                    checks['unconverged']=sum(v['unconverged'] for v in stats)
                    checks['final_frequency_count']=len(fit.get('frequencies_hz') or [])
                    checks['iterations']=(fit.get('work') or {}).get('iterations')
                    checks['source_and_restarts']=continuation_row(folder)
                    checks['passed']=bool(checks['finite_image'] and checks['predictions_shape']==[19,24] and checks['saved_inner_arrays_valid'] and stats and checks['worst_inner_relative']<=1e-4 and checks['unconverged']==0)
                except Exception:
                    checks.update(passed=False,failure=traceback.format_exc())
                write(folder/'output_checks.json',checks)
                write(folder/'manifest.json',{p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in folder.iterdir() if p.is_file() and p.name!='manifest.json'})
                paths.append(str(folder.relative_to(ROOT)))
                if (folder/'fit.npz').exists():
                    forced.append(str((folder/'fit.npz').relative_to(ROOT)))
            rows=[continuation_row(destination/c) for c in runner.get('completed',[]) if (destination/c/'score.json').exists() and not continuation_row(destination/c)['old_failed']]
            lines=['| Case | Area error % | Final mismatch | Worst frequency residual | Seconds | Iterations | Stop | Final step | Restarts | Start commit |','|---|---:|---:|---:|---:|---:|---|---:|---:|---|']
            for r in rows:
                if r.get('area_error') is None or r.get('final_mismatch') is None:
                    lines.append(f"| {r['case']} | null | null | {r.get('worst_frequency_residual')} | {r.get('seconds')} | {r.get('iterations')} | {r.get('stop_reason')} |")
                else:
                    lines.append(f"| {r['case']} | {100*r['area_error']:.4f} | {r['final_mismatch']:.7g} | {r['worst_frequency_residual']:.7g} | {r['seconds']:.3f} | {r['iterations']} | {r['stop_reason']} | {r['final_step_size']} | {r['restarts']} | {r['code_at_start']} |")
            (destination/'continuation_table.md').write_text('\n'.join(lines)+'\n')
            report=ROOT/'docs/iterations/evaluate_our_method/06_make_gaugal_fits_converge/run_report.md'
            text=report.read_text()
            start=text.index('### Continuation results so far');end=text.index('### Continuation receives the GPU',start)
            body='### Continuation results so far\n\n'+'\n'.join(lines)+'\n\nCircle ran under sharing. Peanut began about 26 seconds before the dedicated\nallocation; star and subsequent cases started fully under that allocation.\nCompleted case arrays and checks are committed in pairs. The named converged\nvariant may still stop at its fixed iteration cap; stop reasons are shown.\n\n'
            text=text[:start]+body+text[end:]
            fs_status=read(ROOT/'results/gaugal/converged_clean_uc_fs/low_contrast_state.json')
            text=re.sub(r'Runs: .*',f"Runs: 2/4 probes and {len(fs_status.get('completed',[]))}/10 simultaneous cases completed (paused); {len(rows)}/19 continuation cases saved",text)
            report.write_text(text)
            paths += [str(report.relative_to(ROOT)),str((destination/'continuation_table.md').relative_to(ROOT)),str(Path(__file__).resolve().relative_to(ROOT))]
            git_lock=(BASE/'publisher.lock').open('a');fcntl.flock(git_lock,fcntl.LOCK_EX)
            git(['add','--',*paths])
            if forced:git(['add','-f','--',*forced])
            git(['diff','--cached','--check','--',*paths])
            git(['commit','-m','Record GauGal continuation batch: '+', '.join(selected),'--',*paths])
            git(['push'])
            commit=git(['rev-parse','HEAD'])
            fcntl.flock(git_lock,fcntl.LOCK_UN);git_lock.close()
            published.extend(selected)
            state.update(published=published,last_commit=commit,last_publish_utc=now())
            write(status_path,state)
            notify('Continuation results pushed in '+commit[:9]+': '+', '.join(selected)+'. Arrays, output checks and report table included.')
    except Exception:
        state.update(state='failed',finished_utc=now(),failure=traceback.format_exc(),published=published)
        write(status_path,state)
        notify('Continuation publisher failed: '+state['failure'].splitlines()[-1]+'. Fits continue unchanged; completed files are retained.')
        raise


def run_tv_warm_start():
    """Activity 07: one fixed detached runner, CPU reports, two-case commits."""
    import numpy as np
    destination=ROOT/'results/gaugal/converged_clean_uc_fc'
    archive=BASE/'continuation_before_tv_warm_start'
    activity=ROOT/'docs/iterations/evaluate_our_method/07_refit_gaugal_with_tv_warm_start'
    report=activity/'run_report.md'
    state_path=destination/'tv_warm_start_state.json'
    if state_path.exists(): raise RuntimeError('Activity 07 already launched; no silent rerun')
    shapes=['circle','kite','peanut','star','asymmetric','c_shape','hook','cross','cog','aphex_twin']
    cases=[shape+'__'+contrast for contrast in ('c0.5','c4') for shape in shapes]
    assert all((archive/c/'fit.json').exists() and not (destination/c).exists() for c in cases)
    subprocess.run(['git','merge-base','--is-ancestor','94c39f4c0','HEAD'],cwd=ROOT,check=True)
    available=mem_available();gpu=subprocess.check_output(['nvidia-smi'],text=True)
    if available<14*1024**3: raise RuntimeError('14 GiB memory floor before TV warm-start launch')
    command=[sys.executable,'-u','-m','experiments.comparison','run','gaugal/converged_clean_uc_fc','--cases',*cases]
    state=dict(state='launching',utc=now(),cases=cases,command=command,available_bytes=available,gpu=gpu,
        fixed_numerical_commit='94c39f4c0',source_at_launch=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        monitor_pid=os.getpid(),paused_pids=[1895339,1895343,1903073,2035661,1899688,1899680],published=[])
    write(destination/'tv_warm_start_launch.json',state)
    def git(args):
        for attempt in range(10):
            result=subprocess.run(['git',*args],cwd=ROOT,text=True,capture_output=True)
            with (destination/'tv_warm_start_publish.log').open('a') as log:
                log.write(now()+' '+repr(args)+'\n'+result.stdout+result.stderr)
            if result.returncode==0: return result.stdout.strip()
            if 'index.lock' not in result.stderr: raise RuntimeError(result.stdout+result.stderr)
            time.sleep(2)
        raise RuntimeError(result.stderr)
    def update_report(rows,terminal):
        valid=[r for r in rows if r['outcome'] not in ('FAILED','EXCEPTION_PARTIAL')]
        passed=[r for r in valid if r['area_error']<=.05]
        text=('# GauGal refit with TV warm start — native-run report\n\n19 November 2026, UTC. Fixed numerical code 94c39f4c0. '
              'One detached runner; circle c0.5 first, then the other nine c0.5 cases, then ten c4 cases. '
              'Settings follow plan.md unchanged; there is no time stop.\n\n'
              'The first run is preserved whole under '
              '[continuation_before_tv_warm_start](../../../../results/_probes/gaugal_convergence/2026-11-19/continuation_before_tv_warm_start/). '
              'Its circle c0.5 area value is the separately scored saved image of a FAILED fit. '
              'Truth scores do not select steps or restarts.\n\n'
              '| Case | Area error % | First run area % | Worst frequency residual | Final step | Restarts | Plateau stages | Outcome | Seconds | Start commit |\n'
              '|---|---:|---:|---:|---:|---:|---:|---|---:|---|\n')
        for r in rows:
            text+=f"| {r['case']} | {100*r['area_error']:.4f} | {100*r['first_area_error']:.4f} | {r['worst_frequency_residual']:.7g} | {r['final_step_size']:g} | {r['restarts']} | {r['plateau_stages']} | {r['outcome']} | {r['seconds']:.3f} | {r['code_at_start']} |\n"
        text+=('\nPlateau stages count saved stage stop reasons containing plateau. '
               'STOPPED_EARLY/iteration_limit means the configured cap was reached, not outer convergence. '
               'Failed saved images are scored diagnostically and excluded from successful-fit counts. '
               'Worst frequency residual is an endpoint data residual; inner residuals are checked separately.\n\n'
               'Lower-value probes and simultaneous-frequency fits were paused by the coordinator: '
               'five PIDs at 19:23:14 UTC, star child 2035661 at 19:23:23 UTC. '
               'They remain paused until the coordinator resumes them. '
               'No prior activity pause is subtracted from raw case times.\n\n')
        wall=time.monotonic()-started
        text+=f"```text\nActivity: evaluate_our_method/07_refit_gaugal_with_tv_warm_start, 2026-11-19\nRuns: {len(valid)}/20 nonfailed, {len(rows)-len(valid)} failed, {20-len(rows)} pending; wall time {int(wall//3600)}:{int(wall%3600//60):02d}:{int(wall%60):02d}\nResult: {len(passed)}/20 planned cases have area <=5%; per-case results above\nFailures: "+(', '.join(r['case']+': '+str(r['stop_reason']) for r in rows if r not in valid) or 'none saved')+f"\nUpstream patches: none by native-run\nChanges to our code: none by native-run; scratch reporting helpers only\nNew unknowns: "+('none for this fixed clean pass' if terminal else 'remaining clean case results')+"\nProposed next activity: review with coordinator; needs user decision: none\n```\n"
        report.write_text(text)
    def publish(selected,rows,terminal=False):
        paths=[];forced=[]
        for case in selected:
            folder=destination/case;fit=read(folder/'fit.json');all_stats=fit.get('linear_solves') or []
            stats=[v for v in all_stats if 'rejected_attempt' not in v]
            checks=dict(accepted_solve_groups=len(stats),rejected_solve_groups=len(all_stats)-len(stats),
                worst_inner_relative=max((v['max_final_relative'] for v in stats),default=None),
                unconverged=sum(v['unconverged'] for v in stats),outcome=fit['outcome'])
            with np.load(folder/'fit.npz') as arrays:
                checks.update(finite_image=bool(np.isfinite(arrays['image']).all()),predictions_shape=list(arrays['predicted'].shape),
                    finite_predictions=bool(np.isfinite(arrays['predicted']).all()),
                    accepted_inner_arrays_valid=all(np.isfinite(arrays[k]).all() and float(arrays[k].max())<=1e-4
                        for k in arrays.files if k.endswith('_relative_residual') and '_rejected_' not in k))
            checks['passed']=bool(checks['finite_image'] and checks['finite_predictions'] and checks['predictions_shape']==[19,24]
                and checks['accepted_inner_arrays_valid'] and stats and checks['worst_inner_relative']<=1e-4 and checks['unconverged']==0)
            write(folder/'output_checks.json',checks)
            write(folder/'manifest.json',{p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                for p in folder.iterdir() if p.is_file() and p.name!='manifest.json'})
            paths.append(str(folder.relative_to(ROOT)));forced.append(str((folder/'fit.npz').relative_to(ROOT)))
        update_report(rows,terminal)
        paths += [str(report.relative_to(ROOT)),str(Path(__file__).resolve().relative_to(ROOT)),str((activity/'plan.md').relative_to(ROOT)),
                  str((destination/'tv_warm_start_launch.json').relative_to(ROOT)),str((destination/'tv_warm_start_table.json').relative_to(ROOT))]
        if terminal:
            paths += [str((destination/name).relative_to(ROOT)) for name in ('tv_warm_start_state.json','tv_warm_start_runner.log')]
        lock=(BASE/'publisher.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            git(['add','--',*paths])
            if forced: git(['add','-f','--',*forced])
            git(['diff','--cached','--check','--',*paths])
            git(['commit','-m','Record GauGal TV warm-start '+('final report' if terminal else 'batch: '+', '.join(selected)),'--',*paths])
            git(['push']);commit=git(['rev-parse','HEAD'])
            print('Shared post-push status:\n'+git(['status','--short']),flush=True)
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        state['published'].extend(selected);state['last_publish_commit']=commit;write(state_path,state)
        notify('TV warm-start results pushed in '+commit[:9]+': '+(', '.join(selected) if selected else 'final report')+'.')
    started=time.monotonic();sent=set()
    with (destination/'tv_warm_start_runner.log').open('x') as log:
        process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state.update(state='running',started_utc=now(),runner_pid=process.pid);write(state_path,state)
        update_report([],False)
        notify(f"Activity 07 launched {state['started_utc']}: runner {process.pid}, monitor {os.getpid()}, one fixed 20-case CLI; circle__c0.5 first. Whole first-run folders archived and pushed; six lower-value jobs remain paused.")
        while True:
            rows=[]
            for case in cases:
                folder=destination/case
                if not (folder/'fit.json').exists() or not (folder/'score.json').exists(): continue
                row=continuation_row(folder);fit=read(folder/'fit.json')
                row.update(first_area_error=read(archive/case/'score.json')['area_error'],
                    plateau_stages=sum('plateau' in str(stage.get('stop_reason','')) for stage in fit.get('stages') or []))
                rows.append(row)
                if case not in sent:
                    notify(f"TV warm-start {case}: area {100*row['area_error']:.3f}% (first {100*row['first_area_error']:.3f}%), worst frequency residual {row['worst_frequency_residual']:.6g}; step {row['final_step_size']}, restarts {row['restarts']}, plateau stages {row['plateau_stages']}/6; {row['outcome']}, {row['seconds']:.1f} s; code {row['code_at_start'][:9]}.")
                    sent.add(case)
            write(destination/'tv_warm_start_table.json',rows)
            state.update(utc=now(),saved=[r['case'] for r in rows],available_bytes=mem_available(),wall_seconds=time.monotonic()-started)
            write(state_path,state)
            ready=[r['case'] for r in rows if r['case'] not in state['published']]
            if len(ready)>=2: publish(ready[:2],rows)
            rc=process.poll()
            if rc is not None:
                # Rescan if the CLI wrote its last score between this scan and exit.
                if {r['case'] for r in rows}!={c for c in cases if (destination/c/'score.json').exists()}: continue
                state.update(state='completed' if rc==0 else 'failed',returncode=rc,finished_utc=now());write(state_path,state)
                ready=[r['case'] for r in rows if r['case'] not in state['published']]
                publish(ready,rows,True)
                notify(f"Activity 07 ended: {len(rows)}/20 saved; {sum(r['outcome'] not in ('FAILED','EXCEPTION_PARTIAL') for r in rows)} nonfailed. Report pushed; lower-value jobs remain paused for coordinator.")
                return
            time.sleep(3)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--exact',action='store_true')
    parser.add_argument('--step3-exact',action='store_true')
    parser.add_argument('--run-low-contrast',action='store_true')
    parser.add_argument('--watch-gpu',action='store_true')
    parser.add_argument('--run-continuation',action='store_true')
    parser.add_argument('--publish-continuation',action='store_true')
    parser.add_argument('--attach-continuation',action='store_true')
    parser.add_argument('--run-tv-warm-start',action='store_true')
    parser.add_argument('--collect-step1',action='store_true')
    parser.add_argument('--label');parser.add_argument('--case')
    parser.add_argument('--cap',type=int);parser.add_argument('--step',type=float)
    parser.add_argument('--iterations',type=int)
    args=parser.parse_args()
    if args.watch_gpu:
        destination=ROOT/'results/gaugal/converged_clean_uc_fs'
        with (destination/'gpu_samples.jsonl').open('a') as output:
            while True:
                status=read(destination/'low_contrast_state.json')
                sample=dict(utc=now(),available_bytes=mem_available(),
                            gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free,utilization.gpu','--format=csv,noheader'],text=True).strip())
                output.write(json.dumps(sample)+'\n');output.flush()
                if status['state'] in ('completed','failed'):
                    break
                time.sleep(2)
        return
    if args.worker:
        return worker(args)
    if args.run_low_contrast:
        return run_low_contrast()
    if args.run_continuation:
        return run_continuation()
    if args.run_tv_warm_start:
        return run_tv_warm_start()
    if args.attach_continuation:
        return attach_continuation()
    if args.publish_continuation:
        return publish_continuation()
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
                 step2='skipped by coordinator',step3='completed; low-contrast campaign active')
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
    notify('Step 1 done. '+'; '.join(lines)+'. Step 2 skipped; Step 3 exact probes already completed and committed; low-contrast campaign active.')
    for case in cases:
        score('step1_'+case)
    state.update(state='step1_completed',finished_step1_utc=now())
    write(BASE/'controller.json',state)


if __name__=='__main__':
    main()
