"""One authorized preparation run, with CPU/memory monitoring and no campaign loop."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import psutil

REPO=Path(__file__).resolve().parents[3]
UP=Path.home()/'neural_bem_external/CC-CSI'
ACT=REPO/'docs/iterations/csi_adaptation/03_prepare_simulated_tg002_cases'


def memory():
    d={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.split(':')[0] in ('MemAvailable','MemFree')}
    return d


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['snapshots','generate','probe'])
    args=parser.parse_args()
    out=REPO/f'results/csi/preparation/2026-11-17_{args.mode}'
    out.mkdir(parents=True,exist_ok=False)
    if memory()['MemAvailable']<18*1024**3:
        (out/'memory_refusal.json').write_text(json.dumps(memory(),indent=2)+'\n')
        raise SystemExit('Less than 18 GiB available before start; preserving 14 GiB reserve')
    env=dict(os.environ,CSI_REPO=str(REPO),CSI_UPSTREAM=str(UP),CSI_OUT=str(out),CSI_MODE=args.mode)
    if args.mode=='generate':
        entry=REPO/'experiments/baselines/csi/generate_synthetic.m'
        limit=1800
    else:
        original=(UP/'Inv_Fresnel_I.m').read_text()
        script=original
        old="str = 'uTM_shaped'; para.pt = PT.TM; centre = [0, 0, 0]; xs = 70; ys = 70; para.m_unit = 1.5e-3; fre = 2 : 2 : 16;"
        width=70 if args.mode=='snapshots' else 103.75
        name='dielTM_dec8f' if args.mode=='snapshots' else 'tg002_circle_c4_TM'
        script=script.replace(old,f"str = '{name}'; para.pt = PT.TM; centre = [0, 0, 0]; xs = {width}; ys = {width}; para.m_unit = 1.25e-3; fre = 1 : 8;")
        iterations=2048 if args.mode=='snapshots' else 64
        script=script.replace('= 16;                   % set iteration number',f'= {iterations};                 % set iteration number')
        script=script.replace('pars.recflag        = false;', 'pars.recflag        = true;')
        marker="pars.recstr\t= ['RecMF' str '_MRCSI'];"
        assert marker in script
        script=script[:script.index(marker)]
        script=script.replace('[mchi1, time1, chi1, vJ1, eTot1] = CC_CSI_Brent',
            "pars.str=fullfile(getenv('CSI_OUT'),'upstream_diary');\n[mchi1, time1, chi1, vJ1, eTot1] = CC_CSI_Brent")
        if args.mode=='probe':
            raw=REPO/'results/csi/preparation/2026-11-17_generate/synthetic_input.txt'
            assert raw.exists()
            script=script.replace("rawdat          = load([str '.txt']);",f"rawdat          = load('{raw}');")
        driver=out/'executed_driver.m';driver.write_text(script)
        (out/'upstream_driver.m').write_text(original)
        env['CSI_SCRIPT']=str(driver)
        entry=REPO/'experiments/baselines/csi/preparation_cc.m'
        limit=7200 if args.mode=='snapshots' else 900
    cmd=['matlab','-batch',f"run('{entry}')"]
    record=dict(mode=args.mode,step=args.mode,activity=str(ACT.relative_to(REPO)),command=cmd,
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),timeout_seconds=limit,
        minimum_available_bytes=14*1024**3,upstream_commit=subprocess.check_output(['git','-C',str(UP),'rev-parse','HEAD'],text=True).strip())
    if 'CSI_SCRIPT' in env: record['driver_sha256']=hashlib.sha256(Path(env['CSI_SCRIPT']).read_bytes()).hexdigest()
    start=time.monotonic()
    with (out/'matlab.log').open('w') as log,(out/'resources.csv').open('w') as file:
        child=subprocess.Popen(cmd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        record.update(matlab_pid=child.pid,launcher_pid=os.getpid())
        (out/'launch.json').write_text(json.dumps(record,indent=2)+'\n')
        writer=csv.DictWriter(file,fieldnames=['elapsed_seconds','cpu_seconds','equivalent_cores','rss_bytes','family_rss_bytes','host_busy_cores','available_bytes','free_bytes'])
        writer.writeheader(); previous=None
        host_previous=None
        while child.poll() is None:
            elapsed=time.monotonic()-start; mem=memory()
            try:
                fields=Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()
                cpu=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
                rss=int(fields[21])*os.sysconf('SC_PAGE_SIZE')
                cores=0 if previous is None else (cpu-previous[1])/(elapsed-previous[0])
                descendants=psutil.Process(child.pid).children(recursive=True)
                family=rss+sum(p.memory_info().rss for p in descendants if p.is_running())
                host=[int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
                busy=0 if host_previous is None else ((sum(host[:8])-host[3]-host[4])-(sum(host_previous[1][:8])-host_previous[1][3]-host_previous[1][4]))/os.sysconf('SC_CLK_TCK')/(elapsed-host_previous[0])
                host_previous=(elapsed,host)
                writer.writerow(dict(elapsed_seconds=elapsed,cpu_seconds=cpu,equivalent_cores=cores,rss_bytes=rss,family_rss_bytes=family,host_busy_cores=busy,
                    available_bytes=mem['MemAvailable'],free_bytes=mem['MemFree']))
                file.flush();previous=(elapsed,cpu)
            except (FileNotFoundError,psutil.NoSuchProcess,psutil.AccessDenied): pass
            if mem['MemAvailable']<14*1024**3 or elapsed>limit:
                record['stopped_reason']='memory reserve' if mem['MemAvailable']<14*1024**3 else 'wall limit'
                os.killpg(child.pid,signal.SIGTERM);break
            time.sleep(1)
        record['returncode']=child.wait(timeout=30)
    record.update(wall_seconds=time.monotonic()-start,finished_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    (out/'launch.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
    raise SystemExit(record['returncode'])


if __name__=='__main__':main()
