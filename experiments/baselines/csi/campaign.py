"""Detached, budgeted TG-002 campaign; only owned CSI paths are published."""
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import traceback

import numpy as np
import psutil
from scipy.io import loadmat
from shapely.geometry import Polygon
from experiments.baselines.csi.prepare_geometry import prepare
from experiments.baselines.csi.registered_metrics import score_field

REPO=Path(__file__).resolve().parents[3]
CODE=REPO/'experiments/baselines/csi'
UP=Path.home()/'neural_bem_external/CC-CSI'
ACT=REPO/'docs/iterations/csi_adaptation/04_run_simulated_tg002_cases'
ROOT=REPO/'results/csi/tg002/2026-11-17_campaign'
BATCHES=[['circle','kite','peanut'],['star','asymmetric','c_shape'],['hook','cross','cog'],['aphex_twin']]
GIB=1024**3;RESERVE=14*GIB;FIT_RSS=6.6*GIB;BUDGET=9*3600
START=None;STOP=False;CURRENT=[];JOBS=[]


def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def write(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');tmp.replace(path)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def memory():
    return {s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.split(':')[0] in ('MemAvailable','MemFree')}
def stopped():return STOP or (ROOT/'STOP').exists() or time.monotonic()-START>=BUDGET
def handle_stop(signum,frame):
    global STOP
    STOP=True
def live_jobs():
    answer=[]
    for p in psutil.process_iter(['pid','cmdline']):
        try:
            cmd=p.info['cmdline'] or []
            if cmd and cmd[0].endswith('/bin/glnxa64/MATLAB') and '-batch' in cmd:answer.append(dict(pid=p.pid,command=cmd))
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    return answer


def launch(folder,entry,extra):
    folder.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,CSI_REPO=str(REPO),CSI_UPSTREAM=str(UP),CSI_OUT=str(folder),**extra)
    cmd=['matlab','-batch',f"run('{entry}')"]
    log=(folder/'matlab.log').open('w')
    process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    record=dict(started_utc=now(),command=cmd,environment={k:v for k,v in env.items() if k.startswith('CSI_')},
        matlab_pid=process.pid,threads=8,upstream_commit=subprocess.check_output(['git','-C',str(UP),'rev-parse','HEAD'],text=True).strip())
    write(folder/'launch.json',record)
    file=(folder/'resources.csv').open('w');writer=csv.writer(file)
    writer.writerow(['elapsed_seconds','cpu_seconds','rss_bytes','family_rss_bytes','available_bytes','free_bytes'])
    job=dict(process=process,folder=folder,log=log,resource_file=file,writer=writer,start=time.monotonic(),
        record=record,last_sample=-100,min_available=2**63,min_free=2**63,peak_family=0,peak_rss=0,cpu=0)
    JOBS.append(job);return job


def sample(job):
    mem=memory();elapsed=time.monotonic()-job['start']
    job['min_available']=min(job['min_available'],mem['MemAvailable']);job['min_free']=min(job['min_free'],mem['MemFree'])
    try:
        p=psutil.Process(job['process'].pid);times=p.cpu_times();cpu=times.user+times.system;rss=p.memory_info().rss
        family=rss
        for child in p.children(recursive=True):
            try:family+=child.memory_info().rss
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        job.update(cpu=cpu,peak_family=max(job['peak_family'],family),peak_rss=max(job['peak_rss'],rss),family=family)
        if elapsed-job['last_sample']>=10:
            job['writer'].writerow([elapsed,cpu,rss,family,mem['MemAvailable'],mem['MemFree']]);job['resource_file'].flush();job['last_sample']=elapsed
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    return mem


def terminate(job,reason):
    job['record']['stopped_reason']=reason
    if job['process'].poll() is None:
        os.killpg(job['process'].pid,signal.SIGTERM)
        try:job['process'].wait(timeout=15)
        except subprocess.TimeoutExpired:os.killpg(job['process'].pid,signal.SIGKILL)


def finish(job):
    rc=job['process'].wait();job['log'].close();job['resource_file'].close()
    job['record'].update(returncode=rc,finished_utc=now(),wall_seconds=time.monotonic()-job['start'],
        cpu_seconds=job['cpu'],peak_rss_bytes=job['peak_rss'],peak_family_rss_bytes=job['peak_family'],
        minimum_available_bytes=job['min_available'],minimum_free_bytes=job['min_free'])
    write(job['folder']/'launch.json',job['record'])
    source=job['folder']/'matlab.log'
    with source.open('rb') as src,gzip.open(job['folder']/'matlab.log.gz','wb') as dst:shutil.copyfileobj(src,dst)
    if job in JOBS:JOBS.remove(job)
    return rc


def generate(scene,folder):
    prepare(scene,folder/'truth')
    forward=folder/'forward';forward.mkdir()
    if scene=='circle':
        original=REPO/'results/csi/preparation/2026-11-17_generate'
        shutil.copyfile(original/'synthetic_input.txt',forward/'synthetic_input.txt')
        shutil.copyfile(original/'forward_summary.json',forward/'forward_summary.json')
        write(forward/'reuse.json',dict(source=str(original),sha256=sha(forward/'synthetic_input.txt'),reused_utc=now()))
    else:
        while memory()['MemAvailable']<RESERVE+3*GIB:
            if stopped():return False
            time.sleep(2)
        job=launch(forward,CODE/'generate_synthetic.m',dict(CSI_GEOMETRY=str(folder/'truth/geometry.mat'),CSI_CASE=f'tg002_{scene}_c4_TM'))
        while job['process'].poll() is None:
            if sample(job)['MemAvailable']<RESERVE:terminate(job,'memory reserve')
            if stopped():terminate(job,'user stop or nine-hour budget')
            time.sleep(1)
        if finish(job):return False
    table=np.loadtxt(forward/'synthetic_input.txt')
    template=np.loadtxt(next(UP.rglob('dielTM_dec8f.txt')))
    assert table.shape==(14112,7) and np.isfinite(table).all() and np.array_equal(table[:,:3],template[:,:3])
    write(folder/'data.json',dict(scene=scene,relative_permittivity=4,path=str(forward/'synthetic_input.txt'),
        sha256=sha(forward/'synthetic_input.txt'),bytes=(forward/'synthetic_input.txt').stat().st_size,
        rows=14112,source_count=36,measured_receivers_per_source=49,frequencies_GHz=list(range(1,9)),
        forward_grid=[332,332],inverse_grid=[166,166],mask_exact=True))
    return True


def inversion(scene,folder):
    driver=(UP/'Inv_Fresnel_I.m').read_text()
    old="str = 'uTM_shaped'; para.pt = PT.TM; centre = [0, 0, 0]; xs = 70; ys = 70; para.m_unit = 1.5e-3; fre = 2 : 2 : 16;"
    assert driver.count(old)==1
    driver=driver.replace(old,f"str = 'tg002_{scene}_c4_TM'; para.pt = PT.TM; centre = [0, 0, 0]; xs = 103.75; ys = 103.75; para.m_unit = 1.25e-3; fre = 1 : 8;")
    driver=driver.replace('= 16;                   % set iteration number','= 2048;                 % set iteration number')
    driver=driver[:driver.index("pars.recstr\t= ['RecMF' str '_MRCSI'];")]
    driver=driver.replace("rawdat          = load([str '.txt']);",f"rawdat          = load('{folder/'forward/synthetic_input.txt'}');")
    driver=driver.replace('[mchi1, time1, chi1, vJ1, eTot1] = CC_CSI_Brent(',
        "run(fullfile(getenv('CSI_REPO'),'experiments/baselines/csi/init_campaign_record.m'));\n[mchi1, time1, chi1, vJ1, eTot1] = CC_CSI_Brent_recorded(")
    path=folder/'executed_driver.m';path.write_text(driver)
    job=launch(folder,CODE/'campaign_case.m',dict(CSI_SCRIPT=str(path)))
    job['scene']=scene;job['record']['driver_sha256']=sha(path);write(folder/'launch.json',job['record'])
    return job


def score(folder):
    path=folder/'final_contrast.mat'
    if not path.exists():return
    complete=folder/'matlab_summary.json'
    signature=(path.stat().st_mtime_ns,path.stat().st_size,complete.stat().st_mtime_ns if complete.exists() else 0)
    previous=folder/'scores.json'
    if previous.exists() and json.loads(previous.read_text()).get('file_signature')==list(signature):return
    data=loadmat(path,simplify_cells=True);geometry=loadmat(folder/'truth/geometry.mat',simplify_cells=True)
    boundary=geometry['boundary'];truth=Polygon(np.column_stack([boundary.real,boundary.imag]))
    counts=np.atleast_1d(data['counts']).astype(int);snapshots=data['snapshots'] if len(counts)>1 else [data['snapshots']]
    times=np.atleast_1d(data['native_elapsed_seconds']);rows=[]
    for count,values,seconds in zip(counts,snapshots,times):
        assert np.isfinite(values).all()
        scores,_=score_field(values,(166,166),data['grid_x_primary_m'],data['grid_y_primary_m'],truth)
        for s in scores:
            s['relative_contrast_error']=None if s['mean_relative_permittivity'] is None else abs(s['mean_relative_permittivity']/4-1)
            s['support_area_relative_bias']=s['area_mm2']/s['true_area_mm2']-1
        reported=json.loads(complete.read_text())['time_seconds'] if count==2048 and complete.exists() else float(seconds)
        rows.append(dict(iterations=int(count),checkpoint_elapsed_seconds=float(seconds),native_elapsed_seconds=reported,scores=scores))
    write(previous,dict(scene=folder.name,protocol_version=1,truth_relative_permittivity=4,raw_unmasked=True,
        reference_frequency_GHz=8,real_part_shared_all_frequencies=True,file_signature=list(signature),snapshots=rows))


def cost_history(folder):
    rows=[]
    for line in (folder/'matlab.log').read_text(errors='replace').splitlines():
        if re.match(r'^\s+\d+\s+[-\d.]+e[+-]\d+',line):
            v=[float(s) for s in line.split()]
            rows.append([int(v[0]),*v[1:5]])
    with (folder/'cost_history.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['iteration','FS','FD','FC','reported_cost']);w.writerows(rows)


def manifest(folder):
    paths=[p for p in folder.rglob('*') if p.is_file() and p.name!='manifest.json']
    entries=[]
    for p in sorted(paths):
        ignored=subprocess.run(['git','check-ignore','-q',str(p)],cwd=REPO).returncode==0
        entries.append(dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size,sha256=sha(p),storage='local, git-ignored' if ignored else 'git'))
    write(folder/'manifest.json',dict(files=entries,git_bytes=sum(e['bytes'] for e in entries if e['storage']=='git'),
        command=['env','PYTHONPATH=solvers:.',str(Path(os.sys.executable)),'-m','experiments.baselines.csi.campaign'],
        source_manifest=str(ROOT/'sources.json')))


def report(state):
    lines=['# MF-CC-CSI simulated TG-002 campaign','',f'Updated {now()}. State: **{state}**.',
        '','Nine-hour budget. Ten shapes, contrast 4, 2048 iterations, native back-propagation start.',
        'Grid 166-by-166 at 1.25 mm; native forward 332-by-332 at 0.625 mm. No settings shortened.',
        '','Snapshot scores use unchanged protocol-1 image helpers. Area error is symmetric difference over true area.',
        'Contrast error is relative error of mean epsilon_r in the half-peak support against 4.',
        '','| Case | Iterations | Area error % | Support mm2 | Mean epsilon_r | Contrast error % | Centre error mm | Native elapsed s |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    csvrows=[]
    for scene in [s for b in BATCHES for s in b]:
        folder=ROOT/scene
        if not folder.exists():continue
        scores=folder/'scores.json'
        if scores.exists():
            for row in json.loads(scores.read_text())['snapshots']:
                s=row['scores'][0];mean=s['mean_relative_permittivity'];err=s['relative_contrast_error'];cent=s['centroid_mm']
                fmt=lambda x:'null' if x is None else f'{x:.4f}'
                lines.append(f"| {scene} | {row['iterations']} | {100*s['area_error']:.3f} | {s['area_mm2']:.3f} | {fmt(mean)} | {fmt(None if err is None else 100*err)} | {fmt(cent)} | {row['native_elapsed_seconds']:.3f} |")
                csvrows.append(dict(case=scene,iterations=row['iterations'],area_error=s['area_error'],support_area_mm2=s['area_mm2'],
                    mean_relative_permittivity=mean,relative_contrast_error=err,centroid_error_mm=cent,native_elapsed_seconds=row['native_elapsed_seconds']))
        if (folder/'outcome.json').exists():lines.extend(['',f"{scene}: {json.loads((folder/'outcome.json').read_text())['state']}.",''])
    lines.extend(['','The measured-cylinder nominal registration is not used for these simulated truths.',
        'For that measured case, registered area error, support size and centre offset remain separate; its nominal position is only about 30 mm.',
        '','Raw data, full histories and native logs stay local and ignored. Per-case manifests give SHA-256.',
        'Raw checkpoint arrays, compressed logs, costs, timing/resources and all sensitivity scores are committed.',
        '','The output-only owned copy differs by a function rename and one snapshot callback (patch 0003).',
        'The upstream numerical function, objective, projection, line search and settings are unchanged.',
        'Native timers include the small snapshot writes; checkpoint_writes.csv records that I/O separately.',
        '','The BEM side must check the exact hashed simulated data on each true boundary later.',
        'Timings overlap other MATLAB work and are not isolated final-comparison timings.'])
    forecast=ROOT/'first_batch_forecast.json'
    if forecast.exists():lines.extend(['','## First-batch time check','',f"```json\n{forecast.read_text().strip()}\n```"])
    (ACT/'results.md').write_text('\n'.join(lines)+'\n')
    if csvrows:
        with (ROOT/'snapshot_scores.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)


def publish(label):
    report(label)
    # Scientific report figures; raw arrays remain the scoring evidence.
    os.environ.setdefault('MPLCONFIGDIR','/tmp/csi-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figures=ACT/'figures';figures.mkdir(exist_ok=True)
    for batch,scenes in enumerate(BATCHES,1):
        available=[s for s in scenes if (ROOT/s/'final_contrast.mat').exists()]
        if not available:continue
        fig,axes=plt.subplots(1,len(available),figsize=(4*len(available),3.6),squeeze=False)
        for ax,scene in zip(axes[0],available):
            folder=ROOT/scene;data=loadmat(folder/'final_contrast.mat',simplify_cells=True)
            counts=np.atleast_1d(data['counts']);values=data['snapshots'][-1] if len(counts)>1 else data['snapshots']
            geo=loadmat(folder/'truth/geometry.mat',simplify_cells=True);b=geo['boundary'];truth=Polygon(np.column_stack([b.real,b.imag]))
            _,image=score_field(values,(166,166),data['grid_x_primary_m'],data['grid_y_primary_m'],truth)
            im=ax.imshow(image,extent=[-100,100,-100,100],origin='upper',vmin=0,vmax=3,cmap='turbo')
            ax.plot(b.real*1000,b.imag*1000,'k--',lw=.8);ax.set(title=f'{scene}, {int(counts[-1])} iterations',xlabel='numerical x (mm)',ylabel='numerical y (mm)')
            fig.colorbar(im,ax=ax,label='Re susceptibility',shrink=.8)
        fig.tight_layout();fig.savefig(figures/f'batch_{batch}.png',dpi=130);plt.close(fig)
    paths=['docs/iterations/csi_adaptation/04_run_simulated_tg002_cases','experiments/baselines/csi',
           'external/patches/cc-csi','results/csi/.gitignore',str(ROOT.relative_to(REPO))]
    subprocess.run(['git','add',*paths],cwd=REPO,check=True)
    subprocess.run(['git','commit','-m',f'CSI campaign: {label}','--',*paths],cwd=REPO,check=True)
    subprocess.run(['git','push'],cwd=REPO,check=True)
    subprocess.run(['git','status','--short','--',*paths],cwd=REPO,check=True)


def main():
    global START,CURRENT
    signal.signal(signal.SIGTERM,handle_stop);signal.signal(signal.SIGINT,handle_stop)
    ROOT.mkdir(parents=True,exist_ok=False);START=time.monotonic()
    write(ROOT/'campaign.json',dict(state='starting',started_utc=now(),launcher_pid=os.getpid(),budget_seconds=BUDGET,
        command=[os.sys.executable,'-m','experiments.baselines.csi.campaign'],batches=BATCHES,
        stop_command=f'touch {ROOT}/STOP',memory_reserve_bytes=RESERVE))
    source_paths=[p for p in CODE.rglob('*') if p.suffix in ('.py','.m')]+list((REPO/'external/patches/cc-csi').glob('*.patch'))
    write(ROOT/'sources.json',dict(files=[dict(path=str(p.relative_to(REPO)),sha256=sha(p)) for p in sorted(source_paths)],
        upstream_commit=subprocess.check_output(['git','-C',str(UP),'rev-parse','HEAD'],text=True).strip()))
    overall='running';max_workers=3
    for batch_index,scenes in enumerate(BATCHES,1):
        if stopped():overall='stopped before batch';break
        pending=[];active=[];CURRENT=active
        for scene in scenes:
            folder=ROOT/scene;folder.mkdir()
            try:
                okay=generate(scene,folder)
            except Exception as error:
                (folder/'preparation_failure.txt').write_text(repr(error)+'\n');okay=False
            if okay:pending.append((scene,folder))
            else:write(folder/'outcome.json',dict(state='data generation failed or stopped',utc=now()))
        last_progress=-100
        while pending or active:
            if stopped():
                for job in active:terminate(job,'user stop or nine-hour budget')
                pending.clear();overall='stopped; available snapshots preserved'
            if active and memory()['MemAvailable']<RESERVE:
                max_workers=min(max_workers,2)
                terminate(active[-1],'memory reserve; worker limit reduced to two')
            while pending and len(active)<max_workers and not stopped():
                # Reserve room for all active workers' eventual peaks.
                current=sum(j.get('family',0) for j in active)
                if memory()['MemAvailable']+current<RESERVE+(len(active)+1)*FIT_RSS:break
                scene,folder=pending.pop(0);job=inversion(scene,folder);active.append(job)
            for job in list(active):
                sample(job)
                try:score(job['folder'])
                except (OSError,ValueError) as error:
                    (job['folder']/'scoring_retry.txt').write_text(repr(error)+'\n')
                if job['process'].poll() is not None:
                    rc=finish(job);score(job['folder']);cost_history(job['folder'])
                    write(job['folder']/'outcome.json',dict(state='completed' if rc==0 else 'fit failed',returncode=rc,utc=now()))
                    manifest(job['folder']);active.remove(job)
            elapsed=time.monotonic()-START
            if elapsed-last_progress>=30:
                status=dict(state=overall,batch=batch_index,utc=now(),elapsed_seconds=elapsed,active=[j['scene'] for j in active],
                    pending=[s for s,_ in pending],memory=memory(),matlab=live_jobs())
                with (ROOT/'overlap.jsonl').open('a') as f:f.write(json.dumps(status)+'\n')
                write(ROOT/'status.json',status);report(overall);print(json.dumps(status),flush=True);last_progress=elapsed
            if pending or active:time.sleep(1)
        for scene in scenes:
            folder=ROOT/scene
            if folder.exists():manifest(folder)
        if batch_index==1 and overall=='running':
            rates=[];walls=[]
            for scene in scenes:
                folder=ROOT/scene
                if (folder/'matlab_summary.json').exists():
                    s=json.loads((folder/'matlab_summary.json').read_text());rates.append(s['time_seconds']/2048)
                    walls.append(json.loads((folder/'launch.json').read_text())['wall_seconds'])
            if rates:
                elapsed=time.monotonic()-START
                remaining=3*max(walls)+7*43
                forecast=dict(utc=now(),observed_seconds_per_iteration=rates,conservative_rate=max(rates),
                    elapsed_seconds=elapsed,remaining_forecast_seconds=remaining,total_forecast_hours=(elapsed+remaining)/3600,
                    budget_hours=9,method='elapsed + three remaining batches at slowest completed first-batch wall + seven forward generations at 43 s',
                    exceeds_budget=elapsed+remaining>BUDGET)
                write(ROOT/'first_batch_forecast.json',forecast)
                if forecast['exceeds_budget']:overall='awaiting coordinator: first-batch forecast exceeds nine hours'
            else:overall='awaiting coordinator: no successful first-batch timing'
        write(ROOT/'status.json',dict(state=overall,batch=batch_index,utc=now(),elapsed_seconds=time.monotonic()-START,memory=memory()))
        publish(f'batch {batch_index} {overall}')
        if overall!='running':break
    if overall=='running':overall='completed all ten outcomes'
    campaign=json.loads((ROOT/'campaign.json').read_text());campaign.update(state=overall,finished_utc=now(),wall_seconds=time.monotonic()-START)
    write(ROOT/'campaign.json',campaign);write(ROOT/'status.json',dict(state=overall,utc=now(),elapsed_seconds=time.monotonic()-START,memory=memory()))
    publish(overall)
    print(json.dumps(campaign),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        for job in list(JOBS):
            try:terminate(job,'launcher exception');finish(job)
            except Exception:pass
        if ROOT.exists():
            (ROOT/'launcher_failure.txt').write_text(traceback.format_exc())
            write(ROOT/'status.json',dict(state='launcher failed; active workers stopped',utc=now()))
            for folder in ROOT.iterdir():
                if folder.is_dir():
                    try:score(folder);manifest(folder)
                    except Exception:pass
            try:publish('launcher failed; evidence preserved')
            except Exception:pass
        raise
