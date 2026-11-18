"""Detached no-curvature control; read activity-04 data and never generate it."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from run_tg002 import available, file_sha256, now
from run_paper import write_json, matlab_processes
from log_tg002_rejections import summarize_case

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'results/brg/tg002_shapes/2026-11-17'
BASE = ROOT/'results/brg/tg002_no_curvature/2026-11-18'
UPSTREAM = Path.home()/'neural_bem_external/inverse-obstacle-scattering2d'
PILOT = 'kite__c0.5'
ROW = 'control'
CASE_BASE = BASE

def configure(row):
    global ROW, BASE, CASE_BASE
    ROW = row
    BASE = ROOT/('results/brg/tg002_completion/2026-11-18' if row=='shipped' else 'results/brg/tg002_no_curvature/2026-11-18')
    CASE_BASE = SOURCE if row=='shipped' else BASE



def require_source_ended():
    state = json.loads((SOURCE/'campaign.json').read_text())
    assert state['status'] in ('complete','stopped') and not state['active'] and not state['pending'], 'Wait for activity 04 to end by itself.'
    # Lock proves the detached 04 supervisor has actually exited its queue.
    with (SOURCE/'local/campaign.lock').open('r') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return state


def preserve_cut_attempt(out):
    for name in ['summary.json','metrics.json','fit.json','bulk_manifest.json',
                 'saved_output_check.json','rejection_counts.json','settings.json']:
        source=out/name
        saved=out/(source.stem+'_after_attempt_01'+source.suffix)
        if source.exists() and not saved.exists():
            saved.write_bytes(source.read_bytes())
    figures=ROOT/'docs/iterations/brg_adaptation/04_run_brg_on_tg002_shapes/figures'
    image=figures/(out.name+'.png')
    saved=figures/(out.name+'_after_attempt_01.png')
    if image.exists() and not saved.exists():saved.write_bytes(image.read_bytes())


def prepare_shipped(state):
    assert not (BASE/'campaign.json').exists(), 'Do not reset the continuation queue.'
    cut='c_shape__c0.5'
    order=[cut]+[c for c in state['cases'] if not (SOURCE/c/'metrics.json').exists()]
    expected=[f'{shape}__c{eta}' for shape in ['cross','cog','aphex_twin'] for eta in ['0.5','4']]
    assert order==[cut]+expected, 'Unexpected incomplete cases; coordinator review needed.'
    BASE.mkdir(parents=True,exist_ok=True);(BASE/'local').mkdir(exist_ok=True)
    for case in order:(SOURCE/case/'local').mkdir(parents=True,exist_ok=True)
    manifest=json.loads((SOURCE/cut/'bulk_manifest.json').read_text())
    files=[f for f in manifest['files'] if Path(f['path']).name.startswith('data_') and f['path'].endswith('.mat')]
    assert len(files)==37
    geometry=SOURCE/'local/c_shape.mat'
    write_json(SOURCE/cut/'data_reuse.json',dict(case=cut,source_activity='04 attempt 01',files=files,
        geometry=dict(path=str(geometry.relative_to(ROOT)),sha256=file_sha256(geometry))))
    verify_reuse(SOURCE/cut)
    preserve_cut_attempt(SOURCE/cut)
    write_json(BASE/'order.json',dict(cases=order,pilot=None,rule='resume the capped C-shape; then the six unstarted cases',
        authority='Coordinator 18 November 01:24 UTC: continue saved state as attempt 02; shipped settings; no time cap'))
    names=['run_tg002_control.py','run_tg002_control_case.m','score_tg002_control.py','check_tg002_outputs.py','log_tg002_rejections.py','tg002_geometry.m']
    snapshots=BASE/'local/source_snapshot';snapshots.mkdir(exist_ok=True)
    hashes={}
    for name in names:
        path=ROOT/'experiments/baselines/brg'/name
        (snapshots/name).write_bytes(path.read_bytes());hashes[str(path.relative_to(ROOT))]=file_sha256(path)
    write_json(BASE/'provenance.json',dict(prepared_at=now(),source_sha256=hashes,
        original_campaign=state,only_control_change='remove wall-time cutoffs; inverse settings unchanged',
        cut_case=cut,first_attempt_returncode=124,first_attempt_last_saved_frequency=34,
        continuation_check=str((BASE/'saved_state_restart_check.json').relative_to(ROOT)),no_bem_run=True))
    assert (BASE/'saved_state_restart_check.json').exists(), 'Check saved-state restart before launch.'
    print('Prepared shipped-limit continuation:',order,'; no MATLAB launched.',flush=True)


def prepare():
    state = require_source_ended()
    if ROW == 'shipped':
        return prepare_shipped(state)
    assert not (BASE/'campaign.json').exists(), 'Do not reset an existing campaign.'
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE/'local').mkdir(exist_ok=True)
    prior = []
    stalled = []
    for case in state['cases']:
        metrics = json.loads((SOURCE/case/'metrics.json').read_text())
        assert metrics['status']=='complete' and metrics['completed_frequencies']==37, 'Finish all 20 shipped-limit cases first.'
        assert len(json.loads((SOURCE/case/'data_summary.json').read_text())) == 37, 'All 37 original data files are required.'
        path = SOURCE/case/'rejection_counts.json'
        r = json.loads(path.read_text())
        final_exit = r['frequencies'][-1]['exit_flag']
        if final_exit == -1:
            stalled.append(case)
        prior.append(dict(case=case, area_error=metrics['area_error'],
                          final_frequency_exit_flag=final_exit,
                          terminal_ier_minus5=r['final_iteration_ier_counts'].get('-5', 0)))
    circles = [c for c in state['cases'] if c.startswith('circle__')]
    order = [PILOT]+[c for c in stalled if c != PILOT and c not in circles]
    order += [c for c in state['cases'] if c not in order and c not in circles]+circles
    assert len(order) == len(set(order)) == 20
    for case in order:
        out = CASE_BASE/case
        (out/'local').mkdir(parents=True, exist_ok=True)
        manifest = json.loads((SOURCE/case/'bulk_manifest.json').read_text())
        files = [f for f in manifest['files'] if Path(f['path']).name.startswith('data_') and f['path'].endswith('.mat')]
        assert len(files) == 37
        for item in files:
            path = ROOT/item['path']
            assert path.stat().st_size == item['bytes'] and file_sha256(path) == item['sha256'], str(path)
        shape = case.split('__c')[0]
        geometry = SOURCE/'local'/f'{shape}.mat'
        receipt = dict(case=case, source_activity='04_run_brg_on_tg002_shapes', verified_at=now(),
                       data_generation='none; read original files in place', files=files,
                       geometry=dict(path=str(geometry.relative_to(ROOT)), sha256=file_sha256(geometry)),
                       source_manifest_sha256=file_sha256(SOURCE/case/'bulk_manifest.json'))
        write_json(out/'data_reuse.json', receipt)
    write_json(BASE/'order.json', dict(cases=order, pilot=PILOT, grouping=prior,
                                     rule='pilot alone; cases ending 04 with final-frequency exit -1 in 04 order; rest; circle last'))
    files = ['run_tg002_control.py', 'run_tg002_control_case.m', 'score_tg002_control.py',
             'report_tg002_control.py', 'check_tg002_outputs.py', 'log_tg002_rejections.py', 'tg002_geometry.m']
    snapshots = BASE/'local/source_snapshot'
    snapshots.mkdir(exist_ok=True)
    hashes = {}
    for name in files:
        path = ROOT/'experiments/baselines/brg'/name
        (snapshots/name).write_bytes(path.read_bytes())
        hashes[str(path.relative_to(ROOT))] = file_sha256(path)
    write_json(BASE/'provenance.json', dict(prepared_at=now(), source_sha256=hashes,
        prior_provenance=json.loads((SOURCE/'provenance.json').read_text()),
        data_request_sha256=file_sha256(SOURCE/'data_request.json'), only_inverse_change='eps_curv unset (public default)',
        upstream_patches='same approved patches 03/04; no new upstream patch', no_bem_run=True))
    print('Prepared', len(order), 'cases; no MATLAB launched. Order:', ', '.join(order), flush=True)


def verify_reuse(out):
    record = json.loads((out/'data_reuse.json').read_text())
    for item in record['files']+[record['geometry']]:
        path = ROOT/item['path']
        assert file_sha256(path) == item['sha256'], 'Data/input hash changed: '+str(path)


def run_case(case):
    out = CASE_BASE/case
    local = out/'local'
    with (local/'runner.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempts=sorted(out.glob('attempt_*.json'))
        if attempts:
            assert ROW=='shipped' and case=='c_shape__c0.5' and len(attempts)==1 and json.loads(attempts[0].read_text())['returncode']==124, 'Only the authorized cut-case continuation is allowed.'
            preserve_cut_attempt(out)
        number=len(attempts)+1
        prior=sum(json.loads(p.read_text()).get('case_wall_seconds',0) for p in attempts)
        start = time.monotonic()
        receipt = out/f'attempt_{number:02d}.json'
        log = local/f'matlab_{number:02d}.log'
        command = ['matlab', '-batch', f"addpath('{ROOT}/experiments/baselines/brg'); run_tg002_control_case"]
        record = dict(case=case, started=now(), status='checking_data', target_seconds=3600, time_policy='record overruns; never stop on time',
                      data_status='provisional', curvature='shipped' if ROW=='shipped' else 'default', command=command,
                      prior_case_wall_seconds=prior, continuation_from_frequency=len(list(out.glob('frequency_*.mat'))),
                      log=str(log.relative_to(ROOT)), other_matlab_at_start=matlab_processes())
        write_json(receipt, record)
        code = 1
        try:
            if (out/'data_reuse.json').exists():
                verify_reuse(out)
            else:
                assert ROW=='shipped' and number==1, 'Control data must be reused by hash.'
            record['data_hash_check_seconds'] = time.monotonic()-start
            assert not (BASE/'STOP').exists(), 'STOP requested before MATLAB launch.'
            shape, eta = case.split('__c')
            env = os.environ.copy()
            env.update(BRG_TG002_CASE=case, BRG_SHAPE=shape, BRG_ETA=eta,
                       BRG_CURVATURE='shipped' if ROW=='shipped' else 'default', BRG_TG002_ROW=ROW,
                       BRG_TG002_OUTPUT_BASE=str(CASE_BASE), BRG_TG002_STOP=str(BASE/'STOP'))
            with log.open('w') as stream:
                process = subprocess.Popen(command, cwd=UPSTREAM, env=env, stdout=stream,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                record.update(matlab_pid=process.pid, status='running')
                write_json(receipt, record)
                matlab_start = time.monotonic()
                code = process.wait()
                record['wall_seconds'] = time.monotonic()-matlab_start
            record.update(returncode=code, ended=now(), other_matlab_at_end=matlab_processes())
            write_json(receipt, record)
            (out/f'progress_{number:02d}.log').write_text('\n'.join(l for l in log.read_text(errors='replace').splitlines() if l.startswith('BRG '))+'\n')
            with (local/f'scoring_{number:02d}.log').open('w') as stream:
                score = subprocess.run([sys.executable, str(ROOT/'experiments/baselines/brg/score_tg002_control.py'), '--case', case],
                    cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
            if score.returncode:
                record['scoring_failure'] = f'See local/scoring_{number:02d}.log'
                code = code or score.returncode
            elif json.loads((out/'metrics.json').read_text())['status'] != 'complete':
                code = code or 1
            summarize_case(out)
        except Exception as error:
            record['supervisor_failure'] = repr(error)
            code = code or 1
        record.update(returncode=code, status='finished' if code == 0 else 'failed_or_user_stopped',
                      case_wall_seconds=time.monotonic()-start, case_ended=now())
        write_json(receipt, record)
        manifest = []
        for path in sorted(local.iterdir()):
            if path.is_file() and path.name != 'runner.lock':
                manifest.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=file_sha256(path)))
        write_json(out/'bulk_manifest.json', dict(command='python experiments/baselines/brg/run_tg002_control.py --row '+ROW+' --campaign --detach', files=manifest))
        record.update(case_wall_seconds=time.monotonic()-start, case_ended=now(),
                      case_target_exceeded=(prior+time.monotonic()-start)>3600,
                      total_case_wall_seconds=prior+time.monotonic()-start)
        write_json(receipt, record)
        print(json.dumps(record), flush=True)
        return code


def worker_reserve(case):
    receipts=sorted((CASE_BASE/case).glob('attempt_*.json'))
    receipt=receipts[-1] if receipts else CASE_BASE/case/'attempt_01.json'
    rss = 0
    if receipt.exists():
        pid = json.loads(receipt.read_text()).get('matlab_pid')
        try:
            rss = int(next(l.split()[1] for l in Path(f'/proc/{pid}/status').read_text().splitlines() if l.startswith('VmRSS:')))*1024
        except (FileNotFoundError, StopIteration):
            pass
    return max(0, 4*1024**3-rss)


def campaign():
    require_source_ended()
    with (BASE/'local/campaign.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not (BASE/'campaign.json').exists(), 'Do not relaunch or reset the campaign.'
        order = json.loads((BASE/'order.json').read_text())['cases']
        queue_start = time.time()
        state = dict(started=now(), status='running', cases=order,
                     case_target_seconds=3600, queue_target_seconds=18000,
                     time_policy='targets only; never stop on elapsed time',
                     supervisor_pid=os.getpid(), active=[], pending=order.copy(), maximum_workers=2,
                     row=ROW, pilot=PILOT if ROW=='control' else None, pilot_complete=(ROW=='shipped'), reserve_gib=14,
                     case_target_exceeded={}, failed_cases=[],
                     stop_file=str((BASE/'STOP').relative_to(ROOT)))
        write_json(BASE/'campaign.json', state)
        active, launched = {}, {}
        pending = order.copy()
        stop_reason = None
        while pending or active:
            for case, process in list(active.items()):
                receipts=sorted((CASE_BASE/case).glob('attempt_*.json'))
                path=receipts[-1] if receipts else CASE_BASE/case/'attempt_01.json'
                receipt=json.loads(path.read_text()) if path.exists() else {}
                elapsed = time.time()-launched[case]+receipt.get('prior_case_wall_seconds',0)
                if elapsed>3600 and case not in state['case_target_exceeded']:
                    state['case_target_exceeded'][case] = now()
                    print('TIME TARGET EXCEEDED', case, elapsed, 'seconds; continuing', flush=True)
                if process.poll() is not None:
                    del active[case]
                    if process.returncode:
                        state['failed_cases'].append(dict(case=case, returncode=process.returncode))
                    if ROW=='control' and case == PILOT:
                        state['pilot_complete'] = True
                        state['pilot_wall_seconds'] = receipt.get('case_wall_seconds',elapsed)
                        print('PILOT ENDED', state['pilot_wall_seconds'], 'seconds; return code',process.returncode,flush=True)
            if time.time()-queue_start>18000 and 'queue_target_exceeded_at' not in state:
                state['queue_target_exceeded_at'] = now()
                print('QUEUE TIME TARGET EXCEEDED; continuing', flush=True)
            if (BASE/'STOP').exists():
                stop_reason = 'user-requested STOP file'
                state['stop_reason'] = stop_reason
                state.setdefault('unrun_cases', pending.copy())
                pending = []
            memory = available()
            with (BASE/'resources.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(utc=now(), available_gib=memory/1024**3,
                    active=list(active), reserve_ok=memory>=14*1024**3))+'\n')
            reserve = sum(worker_reserve(c) for c in active)
            if pending and not stop_reason and len(active)<2 and (state['pilot_complete'] or not active) and memory-reserve-4*1024**3>=14*1024**3:
                case = pending.pop(0)
                with (BASE/'local'/f'{case}_supervisor.log').open('w') as stream:
                    active[case] = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--row', ROW, '--case', case],
                        cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
                launched[case] = time.time()
            state.update(active=list(active), pending=pending.copy(), updated=now(),
                         elapsed_seconds=time.time()-queue_start)
            write_json(BASE/'campaign.json', state)
            if pending or active:
                time.sleep(5)
        state.update(status='stopped' if stop_reason else 'complete', ended=now(), active=[], pending=[])
        write_json(BASE/'campaign.json', state)
        if stop_reason:
            write_json(BASE/'STOPPED.json', dict(ended=state['ended'], reason=stop_reason,
                                               unrun_cases=state.get('unrun_cases', [])))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--row',choices=['shipped','control'],default='control')
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--campaign', action='store_true')
    parser.add_argument('--detach', action='store_true')
    parser.add_argument('--case')
    args = parser.parse_args()
    configure(args.row)
    if args.prepare:
        prepare()
    elif args.detach:
        assert args.campaign and not args.case
        require_source_ended()
        assert (BASE/'order.json').exists() and not (BASE/'campaign.json').exists()
        with (BASE/'local/launcher.log').open('a') as stream:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--row', ROW, '--campaign'], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(BASE/'launcher.json', dict(pid=child.pid, launched=now(), command='--campaign'))
        print('Detached control supervisor', child.pid, flush=True)
    elif args.campaign:
        campaign()
    elif args.case:
        assert args.case in json.loads((BASE/'order.json').read_text())['cases']
        raise SystemExit(run_case(args.case))
    else:
        parser.error('Choose --prepare, --campaign or --case.')


if __name__ == '__main__':
    main()
