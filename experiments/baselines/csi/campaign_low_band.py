"""Detached 1--3 GHz CSI campaign, with original-clock resume and live budget."""
import argparse
import datetime as dt
import fcntl
import json
import math
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

from experiments.baselines.csi import campaign as base

ROOT = base.REPO / 'results/csi/tg002/2026-11-18_low_band'
ACT = base.REPO / 'docs/iterations/csi_adaptation/05_run_simulated_tg002_cases_at_1_to_3_ghz'
PARENT = base.REPO / 'results/csi/tg002/2026-11-17_campaign'
ORIGINAL_REPORT = base.report
FREQUENCIES = [1, 2, 3]
CURRENT_SOURCE = None
RECORD = None
LAST_BUDGET = None


def read(path):
    return json.loads(path.read_text())


def hours(initial=False):
    path = ROOT / 'budget_hours.txt'
    value = 6. if initial and not path.exists() else float(path.read_text().strip())
    if not math.isfinite(value) or value <= 0:
        raise ValueError('budget_hours.txt must contain finite positive hours')
    return value


def active_workers():
    found = []
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            if 'MATLAB' not in Path((p.info['cmdline'] or [''])[0]).name:
                continue
            output = p.environ().get('CSI_OUT', '')
            if output and Path(output).is_relative_to(ROOT):
                found.append(p.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
            pass
    return found


def inspect(resume=False):
    reasons = []
    parent = read(PARENT / 'campaign.json')
    pid = parent['launcher_pid']
    try:
        if psutil.Process(pid).status() != psutil.STATUS_ZOMBIE:
            reasons.append(f'old launcher PID {pid} is still alive')
    except psutil.NoSuchProcess:
        pass
    if not parent.get('finished_utc'):
        reasons.append('old campaign has not written its finished state')
    for scene in base.BATCHES[0]:
        if not (PARENT / scene / 'outcome.json').exists():
            reasons.append(f'old first-batch outcome is pending: {scene}')
    if (ROOT / 'STOP').exists():
        reasons.append('STOP exists; it will not be removed')
    workers = active_workers()
    if workers:
        reasons.append(f'same-campaign MATLAB workers still alive: {workers}')
    own = ROOT / 'campaign.json'
    if own.exists() and not resume:
        reasons.append('campaign already exists; use explicit --resume')
    if resume and not own.exists():
        reasons.append('no campaign exists to resume')
    selected = []
    for batch, scenes in enumerate(base.BATCHES, 1):
        for scene in scenes:
            p = ROOT / scene
            state = 'recorded; preserve' if (p/'outcome.json').exists() else ('interrupted; preserve' if (p/'launch.json').exists() else 'not started')
            selected.append(dict(batch=batch, scene=scene, state=state))
    limit = hours(initial=True)
    if own.exists():
        start = dt.datetime.fromisoformat(read(own)['started_utc'])
        deadline = start + dt.timedelta(hours=limit)
        if dt.datetime.now(dt.timezone.utc) >= deadline:
            reasons.append('original campaign clock has reached its budget')
    else:
        deadline = None
    return dict(ready=not reasons, blocked_reasons=reasons, frequencies_GHz=FREQUENCIES,
                budget_hours=limit, hard_stop_utc=None if deadline is None else deadline.isoformat(), cases=selected)


def stopped():
    global LAST_BUDGET
    try:
        limit = hours()
    except (OSError, ValueError) as error:
        with (ROOT/'budget_history.jsonl').open('a') as f:
            f.write(json.dumps(dict(utc=base.now(), error=repr(error), action='stop'))+'\n')
        base.STOP = True
        return True
    start = dt.datetime.fromisoformat(RECORD['started_utc']).timestamp()
    if limit != LAST_BUDGET:
        deadline = dt.datetime.fromtimestamp(start+3600*limit, dt.timezone.utc).isoformat()
        entry = dict(utc=base.now(), budget_hours=limit, hard_stop_utc=deadline,
                     elapsed_seconds=time.monotonic()-base.START)
        with (ROOT/'budget_history.jsonl').open('a') as f:
            f.write(json.dumps(entry)+'\n')
        RECORD.update(budget_hours=limit, hard_stop_utc=deadline)
        base.write(ROOT/'campaign.json', RECORD)
        LAST_BUDGET = limit
    return (base.STOP or (ROOT/'STOP').exists() or time.monotonic()-base.START >= limit*3600
            or time.time() >= start+limit*3600)


def select_data(folder):
    record = read(folder/'data.json')
    parent = Path(record['path'])
    assert base.sha(parent) == record['sha256']
    table = np.loadtxt(parent)
    assert table.shape == (14112, 7) and np.isfinite(table).all()
    assert np.array_equal(table[:,2], np.tile(np.arange(1,9),1764))
    selected = np.isin(table[:,2], FREQUENCIES)
    subset = folder/'selected'; subset.mkdir(exist_ok=True)
    path = subset/'synthetic_input.txt'
    # Preserve parent line bytes exactly, without float reserialization.
    content = b''.join(line for line, keep in zip(parent.read_bytes().splitlines(keepends=True), selected) if keep)
    if path.exists():
        assert path.read_bytes() == content
    else:
        path.write_bytes(content)
    record.update(selected_frequencies_GHz=FREQUENCIES, selected_rows=5292,
        selection='column 3 in {1,2,3}; one-based rows 8*j+f, j=0..1763, f=1,2,3',
        selected_table_path=str(path), selected_table_sha256=base.sha(path),
        selection_method_for_CSI='native fre=1:3 on the full unchanged parent table',
        sign_convention='exp(+j omega t); BEM conjugates once', reference_frequency_GHz=3)
    base.write(folder/'data.json', record)


def prepare_case(scene, folder):
    folder.mkdir(exist_ok=True)
    if (folder/'data.json').exists():
        select_data(folder)
        return True
    if scene in base.BATCHES[0]:
        original = PARENT/scene
        data = read(original/'data.json')
        assert base.sha(Path(data['path'])) == data['sha256']
        truth = folder/'truth'; truth.mkdir(exist_ok=False)
        for name in ['geometry.mat','geometry.json']:
            shutil.copyfile(original/'truth'/name, truth/name)
        data.update(reused_from=str(original), reused_utc=base.now())
        base.write(folder/'data.json', data)
        okay = True
    else:
        # Unchanged original eight-frequency forward generator and 0.625-mm grid.
        okay = base.generate(scene, folder)
    if okay:
        select_data(folder)
    return okay


def inversion(scene, folder):
    driver = (base.UP/'Inv_Fresnel_I.m').read_text()
    old = "str = 'uTM_shaped'; para.pt = PT.TM; centre = [0, 0, 0]; xs = 70; ys = 70; para.m_unit = 1.5e-3; fre = 2 : 2 : 16;"
    assert driver.count(old) == 1
    driver = driver.replace(old, f"str = 'tg002_{scene}_c4_low_band_TM'; para.pt = PT.TM; centre = [0, 0, 0]; xs = 103.75; ys = 103.75; para.m_unit = 1.25e-3; fre = 1 : 3;")
    assert driver.count('= 16;                   % set iteration number') == 1
    driver = driver.replace('= 16;                   % set iteration number','= 2048;                 % set iteration number')
    driver = driver[:driver.index("pars.recstr\t= ['RecMF' str '_MRCSI'];")]
    path = read(folder/'data.json')['path']
    driver = driver.replace("rawdat          = load([str '.txt']);", f"rawdat          = load('{path}');")
    driver = driver.replace('[mchi1, time1, chi1, vJ1, eTot1] = CC_CSI_Brent(',
        "run(fullfile(getenv('CSI_REPO'),'experiments/baselines/csi/init_campaign_record.m'));\n[mchi1, time1, chi1, vJ1, eTot1] = CC_CSI_Brent_recorded(")
    executed = folder/'executed_driver.m'
    if executed.exists():
        raise RuntimeError(f'refusing to overwrite an executed driver: {executed}')
    executed.write_text(driver)
    job = base.launch(folder, base.CODE/'campaign_case.m', dict(CSI_SCRIPT=str(executed)))
    job['scene'] = scene
    job['record'].update(driver_sha256=base.sha(executed), source_manifest=str(CURRENT_SOURCE),
                         frequencies_GHz=FREQUENCIES, reference_frequency_GHz=3)
    base.write(folder/'launch.json',job['record'])
    return job


def score(folder):
    base.score(folder)
    path = folder/'scores.json'
    if path.exists():
        record = read(path)
        if record['reference_frequency_GHz'] != 3:
            record.update(reference_frequency_GHz=3, frequencies_GHz=FREQUENCIES)
            base.write(path, record)


def manifest(folder):
    base.manifest(folder)
    path = folder/'manifest.json'; record = read(path)
    record.update(source_manifest=str(CURRENT_SOURCE), command=RECORD['latest_command'])
    base.write(path,record)


def iteration_timing(job):
    lines = (job['folder']/'matlab.log').read_text(errors='replace').splitlines()
    counts = [int(line.split()[0]) for line in lines if re.match(r'^\s+\d+\s+[-\d.]+e[+-]\d+',line)]
    if not counts:
        return
    count = counts[-1]; elapsed = time.monotonic()-job['start']
    if 'first_iteration_seen' not in job:
        job['first_iteration_seen'] = (count,elapsed)
    first, begin = job['first_iteration_seen']
    if count >= 100 and count > first and not job.get('early_timing_saved'):
        record = dict(utc=base.now(), first_observed_iteration=first, last_observed_iteration=count,
                      elapsed_between_observations_seconds=elapsed-begin,
                      observed_seconds_per_iteration=(elapsed-begin)/(count-first),
                      basis='wall-clock progress between first observed numerical log row and approximately iteration 100; startup excluded')
        base.write(job['folder']/'early_iteration_timing.json',record)
        print(json.dumps(dict(scene=job['scene'],early_iteration_timing=record)),flush=True)
        job['early_timing_saved'] = True


def report(state):
    ORIGINAL_REPORT(state)
    path = ACT/'results.md'
    text = path.read_text().replace('Nine-hour budget.',f"{RECORD['budget_hours']:g}-hour live budget on this campaign's original clock.")
    text += ('\n## Frequency selection and clock\n\n'
             'Only 1, 2 and 3 GHz enter native configuration, back-propagation and inversion.\n'
             'The native last-frequency raw image is at 3 GHz; conductivity normalization remains at 1 GHz.\n'
             f"Start: {RECORD['started_utc']}. Current hard stop: {RECORD['hard_stop_utc']}.\n"
             'budget_hours.txt is read at every stop check; changed values are in budget_history.jsonl.\n'
             'The first-batch forecast is information only and never causes an exit.\n'
             'See [data_note.md](data_note.md) for parent and selected-row hashes for BEM.\n')
    path.write_text(text)
    lines = ['# Frozen 1–3 GHz data for the BEM side','',
             'Parent tables keep all eight frequencies. CSI uses native fre=1:3.',
             'Select column 3 in {1,2,3}; one-based parent rows 8*j+f for j=0..1763 and f=1,2,3.',
             'There are 5292 selected rows, 1764 per frequency. Columns and pair order are unchanged.',
             'Fields use exp(+j omega t); BEM must conjugate once. Receiver mask is the same 49 per each of 36 sources.',
             'Selected tables preserve parent line bytes exactly. They stay local and ignored, with SHA-256 below.',
             'BEM checks every true shape independently; the circle check does not check other shapes.','']
    for scenes in base.BATCHES:
        for scene in scenes:
            p=ROOT/scene/'data.json'
            if not p.exists():continue
            data=read(p)
            if 'selected_table_sha256' not in data:continue
            lines.extend([f'## {scene}','',f"Parent: `{data['path']}`.",f"Parent SHA-256: `{data['sha256']}`.",
                          f"Selected: `{data['selected_table_path']}`.",f"Selected SHA-256: `{data['selected_table_sha256']}`.",''])
    (ACT/'data_note.md').write_text('\n'.join(lines)+'\n')


def status(state,batch,active=(),pending=()):
    record=dict(state=state,batch=batch,utc=base.now(),elapsed_seconds=time.monotonic()-base.START,
                active=[j['scene'] for j in active],pending=[s for s,_ in pending],memory=base.memory(),
                matlab=base.live_jobs(),budget_hours=RECORD['budget_hours'],hard_stop_utc=RECORD['hard_stop_utc'])
    base.write(ROOT/'status.json',record)
    with (ROOT/'overlap.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    report(state);print(json.dumps(record),flush=True)


def publish(label):
    report(label)
    os.environ.setdefault('MPLCONFIGDIR','/tmp/csi-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figures=ACT/'figures';figures.mkdir(exist_ok=True)
    for batch,scenes in enumerate(base.BATCHES,1):
        available=[s for s in scenes if (ROOT/s/'final_contrast.mat').exists()]
        if not available:continue
        fig,axes=plt.subplots(1,len(available),figsize=(4*len(available),3.6),squeeze=False)
        for ax,scene in zip(axes[0],available):
            folder=ROOT/scene;data=loadmat(folder/'final_contrast.mat',simplify_cells=True)
            counts=np.atleast_1d(data['counts']);values=data['snapshots'][-1] if len(counts)>1 else data['snapshots']
            geometry=loadmat(folder/'truth/geometry.mat',simplify_cells=True);b=geometry['boundary']
            truth=base.Polygon(np.column_stack([b.real,b.imag]))
            _,image=base.score_field(values,(166,166),data['grid_x_primary_m'],data['grid_y_primary_m'],truth)
            im=ax.imshow(image,extent=[-100,100,-100,100],origin='upper',vmin=0,vmax=3,cmap='turbo')
            ax.plot(b.real*1000,b.imag*1000,'k--',lw=.8)
            ax.set(title=f'{scene}, {int(counts[-1])} iterations',xlabel='numerical x (mm)',ylabel='numerical y (mm)')
            fig.colorbar(im,ax=ax,label='Re susceptibility',shrink=.8)
        fig.tight_layout();fig.savefig(figures/f'batch_{batch}.png',dpi=130);plt.close(fig)
    paths=[str(ACT.relative_to(base.REPO)),'experiments/baselines/csi','external/patches/cc-csi',
           'results/csi/.gitignore',str(ROOT.relative_to(base.REPO))]
    subprocess.run(['git','add',*paths],cwd=base.REPO,check=True)
    subprocess.run(['git','commit','-m',f'CSI 1-3 GHz: {label}','--',*paths],cwd=base.REPO,check=True)
    subprocess.run(['git','push'],cwd=base.REPO,check=True)
    subprocess.run(['git','status','--short','--',*paths],cwd=base.REPO,check=True)


def verify_parent_push(commit):
    if not commit:
        raise RuntimeError('--parent-commit is required after confirming the old batch-1 push')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=base.REPO,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin',f'refs/heads/{branch}'],cwd=base.REPO,text=True).split()[0]
    subprocess.run(['git','merge-base','--is-ancestor',commit,remote],cwd=base.REPO,check=True)
    for scene in base.BATCHES[0]:
        path=str((PARENT/scene/'outcome.json').relative_to(base.REPO))
        subprocess.run(['git','cat-file','-e',f'{commit}:{path}'],cwd=base.REPO,check=True)
    return remote


def interrupted(folder):
    # A process cannot be reconstructed from a contrast checkpoint. Preserve
    # its failure; a resume only starts fits which never had a launch record.
    if (folder/'launch.json').exists() and not (folder/'outcome.json').exists():
        score(folder)
        if (folder/'matlab.log').exists():
            base.cost_history(folder)
            import gzip
            with (folder/'matlab.log').open('rb') as src,gzip.open(folder/'matlab.log.gz','wb') as dst:
                shutil.copyfileobj(src,dst)
        base.write(folder/'outcome.json',dict(state='interrupted fit; available snapshots preserved',
                   returncode=read(folder/'launch.json').get('returncode'),utc=base.now()))
        manifest(folder)


def run(resume=False,parent_commit=None):
    global RECORD,CURRENT_SOURCE,LAST_BUDGET
    check=inspect(resume)
    if not check['ready']:raise RuntimeError(json.dumps(check,indent=2))
    if resume:parent_commit=read(ROOT/'campaign.json')['parent_batch_commit']
    remote=verify_parent_push(parent_commit)
    ROOT.mkdir(parents=True,exist_ok=True)
    # Kernel lock releases on exit; the lock file and all state remain.
    lock=(ROOT/'launcher.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if not (ROOT/'budget_hours.txt').exists():
        with (ROOT/'budget_hours.txt').open('x') as f:f.write('6\n')
    if resume:
        RECORD=read(ROOT/'campaign.json')
    else:
        RECORD=dict(started_utc=base.now(),parent_batch_commit=parent_commit,batches=base.BATCHES,
                    frequencies_GHz=FREQUENCIES,reference_frequency_GHz=3,initial_budget_hours=6,
                    memory_reserve_bytes=base.RESERVE,stop_file=str(ROOT/'STOP'),invocations=[])
    command=['env','PYTHONPATH=solvers:.',os.sys.executable,'-B','-m','experiments.baselines.csi.campaign_low_band']
    command+=['--resume'] if resume else ['--parent-commit',parent_commit]
    RECORD.update(state='running',launcher_pid=os.getpid(),latest_command=command,remote_commit_at_launch=remote,
                  resumed_utc=base.now() if resume else None)
    RECORD['invocations'].append(dict(utc=base.now(),pid=os.getpid(),command=command))
    number=len(RECORD['invocations']);CURRENT_SOURCE=ROOT/f'sources_run_{number:03d}.json'
    source_paths=[p for p in base.CODE.rglob('*') if p.suffix in ('.py','.m')]
    source_paths+=list((base.REPO/'external/patches/cc-csi').glob('*.patch'))
    sources=dict(utc=base.now(),command=command,files=[dict(path=str(p.relative_to(base.REPO)),sha256=base.sha(p)) for p in sorted(source_paths)],
                 upstream_commit=subprocess.check_output(['git','-C',str(base.UP),'rev-parse','HEAD'],text=True).strip())
    base.write(CURRENT_SOURCE,sources)
    if not (ROOT/'sources.json').exists():base.write(ROOT/'sources.json',sources)
    base.ROOT=ROOT;base.ACT=ACT;base.report=report;base.stopped=stopped;base.STOP=False
    started=dt.datetime.fromisoformat(RECORD['started_utc']).timestamp()
    base.START=time.monotonic()-(time.time()-started)
    LAST_BUDGET=None
    base.write(ROOT/'campaign.json',RECORD)
    signal.signal(signal.SIGTERM,base.handle_stop);signal.signal(signal.SIGINT,base.handle_stop)
    stopped()
    overall='running';max_workers=RECORD.get('max_workers',3);batch=1
    try:
        if resume:
            for scenes in base.BATCHES:
                for scene in scenes:
                    folder=ROOT/scene
                    if folder.exists():interrupted(folder)
        for batch,scenes in enumerate(base.BATCHES,1):
            if stopped():overall='stopped before batch; available evidence preserved';break
            pending=[];active=[];owned=[]
            for scene in scenes:
                folder=ROOT/scene
                if (folder/'outcome.json').exists():continue
                if stopped():overall='stopped; available evidence preserved';break
                if folder.exists() and any(folder.iterdir()) and not (folder/'data.json').exists():
                    base.write(folder/'outcome.json',dict(state='interrupted preparation; evidence preserved',utc=base.now()))
                    owned.append(folder);continue
                try:okay=prepare_case(scene,folder)
                except Exception as error:
                    folder.mkdir(exist_ok=True)
                    (folder/'preparation_failure.txt').write_text(traceback.format_exc());okay=False
                owned.append(folder)
                if okay:pending.append((scene,folder))
                else:base.write(folder/'outcome.json',dict(state='data generation failed or stopped',utc=base.now()))
            if stopped():overall='stopped; available evidence preserved'
            last_progress=-100
            while pending or active:
                if stopped():
                    for job in active:base.terminate(job,'STOP, signal or original-clock budget')
                    pending.clear();overall='stopped; available snapshots preserved'
                if active and base.memory()['MemAvailable']<base.RESERVE:
                    max_workers=min(max_workers,2);RECORD['max_workers']=max_workers
                    base.terminate(active[-1],'memory reserve; worker limit reduced to two')
                while pending and len(active)<max_workers and not stopped():
                    current=sum(j.get('family',0) for j in active)
                    if base.memory()['MemAvailable']+current<base.RESERVE+(len(active)+1)*base.FIT_RSS:break
                    scene,folder=pending.pop(0);active.append(inversion(scene,folder))
                for job in list(active):
                    base.sample(job);iteration_timing(job)
                    try:score(job['folder'])
                    except (OSError,ValueError) as error:
                        (job['folder']/'scoring_retry.txt').write_text(repr(error)+'\n')
                    if job['process'].poll() is not None:
                        rc=base.finish(job);score(job['folder']);base.cost_history(job['folder'])
                        if rc==0:
                            raw=loadmat(job['folder']/'final_contrast.mat',simplify_cells=True)
                            assert np.atleast_1d(raw['counts']).tolist()==[256,512,1024,2048]
                            assert all(np.isfinite(a).all() for a in raw['snapshots'])
                            assert np.atleast_1d(raw['frequencies_GHz']).tolist()==FREQUENCIES
                            assert int(raw['reference_frequency_GHz'])==3
                        base.write(job['folder']/'outcome.json',dict(state='completed' if rc==0 else 'fit failed',returncode=rc,utc=base.now()))
                        manifest(job['folder']);active.remove(job)
                elapsed=time.monotonic()-base.START
                if elapsed-last_progress>=30:
                    status(overall,batch,active,pending);last_progress=elapsed
                if pending or active:time.sleep(1)
            for folder in owned:manifest(folder)
            if batch==1 and not (ROOT/'first_batch_forecast.json').exists():
                walls=[];rates=[]
                for scene in scenes:
                    folder=ROOT/scene
                    if (folder/'matlab_summary.json').exists():
                        rates.append(read(folder/'matlab_summary.json')['time_seconds']/2048)
                        launch=read(folder/'launch.json')
                        if 'wall_seconds' in launch:walls.append(launch['wall_seconds'])
                elapsed=time.monotonic()-base.START
                total=None if not walls else (elapsed+3*max(walls)+7*43)/3600
                base.write(ROOT/'first_batch_forecast.json',dict(utc=base.now(),observed_seconds_per_iteration=rates,
                    elapsed_seconds=elapsed,total_forecast_hours=total,budget_hours=RECORD['budget_hours'],
                    exceeds_current_budget=None if total is None else total>RECORD['budget_hours'],
                    forecast_is_informational=True,method='elapsed + three remaining batches at slowest completed first-batch wall + seven forward generations at 43 s'))
            RECORD.update(state=overall,max_workers=max_workers);base.write(ROOT/'campaign.json',RECORD)
            status(overall,batch);publish(f'batch {batch} {overall}')
            if overall!='running':break
        if overall=='running':overall='completed all ten recorded outcomes'
    except BaseException:
        overall='launcher failed; evidence preserved'
        (ROOT/'launcher_failure.txt').write_text(traceback.format_exc())
        for job in list(base.JOBS):
            try:
                base.terminate(job,'low-band launcher exception');rc=base.finish(job)
                score(job['folder']);base.cost_history(job['folder'])
                base.write(job['folder']/'outcome.json',dict(state='fit failed',returncode=rc,utc=base.now()))
                manifest(job['folder'])
            except Exception:
                with (ROOT/'launcher_failure.txt').open('a') as f:f.write(traceback.format_exc())
        raise
    finally:
        RECORD.update(state=overall,finished_utc=base.now(),wall_seconds=time.monotonic()-base.START,max_workers=max_workers)
        base.write(ROOT/'campaign.json',RECORD);status(overall,batch)
        publish(overall)
        lock.close()


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--parent-commit')
    args=parser.parse_args()
    if args.dry_run:print(json.dumps(inspect(args.resume),indent=2))
    else:run(args.resume,args.parent_commit)


if __name__=='__main__':main()
