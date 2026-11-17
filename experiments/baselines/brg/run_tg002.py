"""Baseline-only BRG campaign with per-frequency resume and hard time limits."""
import argparse,datetime,fcntl,hashlib,json,math,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_paper import write_json,matlab_processes
BASE=ROOT/'results/brg/tg002_shapes/2026-11-17'
UPSTREAM=Path.home()/'neural_bem_external/inverse-obstacle-scattering2d'
SCENES=['asymmetric','circle','kite','peanut','star','c_shape','hook','cross','cog','aphex_twin']
CASES=['asymmetric__c4']+[f'{s}__c{eta}' for s in SCENES for eta in ['0.5','4'] if (s,eta)!=('asymmetric','4')]

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def file_sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def available():return int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))*1024

def run_case(case,deadline):
    out=BASE/case;local=out/'local';local.mkdir(parents=True,exist_ok=True)
    with (local/'runner.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        attempts=[json.loads(p.read_text()) for p in out.glob('attempt_*.json')]
        used=sum(a.get('case_wall_seconds',a.get('wall_seconds',0)) for a in attempts)
        remaining=math.floor(min(3600-used,deadline-time.time()))
        if remaining<=5:raise RuntimeError('Case or campaign time limit exhausted')
        number=len(attempts)+1;receipt=out/f'attempt_{number:02d}.json';log=local/f'matlab_{number:02d}.log'
        shape,eta=case.split('__c');env=os.environ.copy();env.update(BRG_TG002_CASE=case,BRG_SHAPE=shape,BRG_ETA=eta,BRG_REMAINING_SECONDS=str(remaining-5))
        command=['matlab','-batch',f"addpath('{ROOT}/experiments/baselines/brg'); run_tg002_case"]
        record=dict(case=case,started=now(),status='running',remaining_seconds=remaining,other_matlab_at_start=matlab_processes(),
                    data_status='provisional',command=command,log=str(log.relative_to(ROOT)))
        write_json(receipt,record);start=time.monotonic()
        with log.open('w') as stream:
            process=subprocess.Popen(command,cwd=UPSTREAM,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            record['matlab_pid']=process.pid;write_json(receipt,record)
            try:code=process.wait(timeout=remaining-3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait();code=124
        record.update(wall_seconds=time.monotonic()-start,returncode=code,ended=now(),other_matlab_at_end=matlab_processes(),status='finished' if code==0 else 'failed_or_capped')
        write_json(receipt,record)
        lines=[l for l in log.read_text(errors='replace').splitlines() if l.startswith('BRG ')];(out/f'progress_{number:02d}.log').write_text('\n'.join(lines)+'\n')
        try:
            score_limit=max(1,math.floor(remaining-(time.monotonic()-start)))
            with (local/'scoring.log').open('w') as stream:
                score=subprocess.run([sys.executable,str(ROOT/'experiments/baselines/brg/score_tg002.py'),'--case',case],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=score_limit)
            if score.returncode:raise RuntimeError(f'Scoring return code {score.returncode}; see local/scoring.log')
        except Exception as error:
            record['scoring_failure']=repr(error);code=code or 1
        record.update(case_wall_seconds=time.monotonic()-start,case_ended=now());write_json(receipt,record)
        manifest=[]
        for p in sorted(local.glob('*')):
            if p.is_file() and p.name!='runner.lock':
                sha=file_sha256(p)
                manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha))
        write_json(out/'bulk_manifest.json',dict(command=f'python experiments/baselines/brg/run_tg002.py --case {case}',files=manifest))
        record.update(case_wall_seconds=time.monotonic()-start,case_ended=now());write_json(receipt,record)
        print(json.dumps(record),flush=True);return code

def campaign():
    local=BASE/'local';local.mkdir(exist_ok=True)
    with (local/'campaign.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        path=BASE/'campaign.json'
        state=json.loads(path.read_text()) if path.exists() else dict(started=now(),deadline_unix=time.time()+14400,cases=CASES,status='running')
        write_json(path,state);deadline=state['deadline_unix'];active={};pending=[]
        for c in CASES:
            m=BASE/c/'metrics.json'
            if not m.exists():pending.append(c)
        stop_reason=None
        while pending or active:
            for c,p in list(active.items()):
                if p.poll() is not None:
                    del active[c]
                    receipt=json.loads(sorted((BASE/c).glob('attempt_*.json'))[-1].read_text())
                    if c==CASES[0] and (receipt.get('case_wall_seconds',float('inf'))>900 or p.returncode):stop_reason='pilot over 15 minutes or failed'
                    if p.returncode and not stop_reason:stop_reason='case failed or capped; review required'
            if stop_reason or time.time()>=deadline:
                pending=[];state['stop_reason']=stop_reason or 'four-hour campaign limit'
            memory=available();reserve=0
            for c in active:
                receipts=sorted((BASE/c).glob('attempt_*.json'))
                a=json.loads(receipts[-1].read_text()) if receipts else {}
                pid=a.get('matlab_pid');rss=0
                try:rss=int(next(l.split()[1] for l in Path(f'/proc/{pid}/status').read_text().splitlines() if l.startswith('VmRSS:')))*1024
                except (FileNotFoundError,StopIteration):pass
                reserve+=max(0,4*1024**3-rss)
            with (BASE/'resources.jsonl').open('a') as f:f.write(json.dumps(dict(utc=now(),available_gib=memory/1024**3,active=list(active),reserve_ok=memory>=14*1024**3))+'\n')
            if memory<14*1024**3 and active:
                c=list(active)[-1];a=json.loads(sorted((BASE/c).glob('attempt_*.json'))[-1].read_text());pid=a.get('matlab_pid')
                if pid:
                    try:os.killpg(pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                    state['resource_stop']=dict(case=c,utc=now());stop_reason='memory reserve reached; saved checkpoints retained'
            pilot_receipts=sorted((BASE/CASES[0]).glob('attempt_*.json'))
            pilot_record=json.loads(pilot_receipts[-1].read_text()) if pilot_receipts else {}
            pilot_done=bool(pilot_record.get('case_wall_seconds',901)<=900 and pilot_record.get('returncode')==0 and not pilot_record.get('scoring_failure'))
            if pending and not stop_reason and len(active)<3 and (pilot_done or not active) and memory-reserve-4*1024**3>=14*1024**3:
                c=pending.pop(0);log=open(local/f'{c}_supervisor.log','a')
                p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--case',c,'--deadline',str(deadline)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT);log.close();active[c]=p
                time.sleep(3)
            state.update(active=list(active),pending=pending,updated=now());write_json(path,state)
            if pending or active:time.sleep(5)
        state.update(status='stopped' if state.get('stop_reason') else 'complete',ended=now(),active=[],pending=[]);write_json(path,state)

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=CASES);p.add_argument('--campaign',action='store_true');p.add_argument('--detach',action='store_true');p.add_argument('--deadline',type=float,default=None);a=p.parse_args()
    BASE.mkdir(parents=True,exist_ok=True);(BASE/'local').mkdir(exist_ok=True)
    if a.detach:
        args=[sys.executable,str(Path(__file__).resolve()),'--campaign'] if a.campaign else [sys.executable,str(Path(__file__).resolve()),'--case',a.case]
        with (BASE/'local/launcher.log').open('a') as f:child=subprocess.Popen(args,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        print('Detached supervisor',child.pid);return
    if a.campaign:campaign()
    elif a.case:raise SystemExit(run_case(a.case,a.deadline or time.time()+3600))
    else:p.error('Choose --case or --campaign')

if __name__=='__main__':main()
