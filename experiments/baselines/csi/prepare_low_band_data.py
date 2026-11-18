"""Prepare frozen eight-frequency parents early for CSI and BEM; no inversions."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import traceback

from experiments.baselines.csi import campaign as base
from experiments.baselines.csi import campaign_low_band as band

ROOT=base.REPO/'results/csi/tg002/2026-11-18_low_band_data'
PARENT=base.REPO/'results/csi/tg002/2026-11-17_campaign'
ACT=band.ACT


def data_note():
    lines=['# Frozen 1–3 GHz data for the BEM side','',
        'All full parent tables use the unchanged 0.625 mm generator, contrast 4, eight frequencies.',
        'Fixed parent pattern: results/csi/tg002/2026-11-18_low_band_data/{shape}/forward/synthetic_input.txt.',
        'A .sha256 sidecar is beside every parent table. The BEM side reads only.',
        'The main comparison uses column 3 in {1,2,3}: one-based parent rows 8*j+f, j=0..1763, f=1,2,3.',
        'These 5292 rows are interleaved, 1764 per frequency; they are not the first 5292 rows.',
        'Selected files retain exact parent line bytes. Their SHA-256 and parent SHA-256 are recorded below.',
        'Fields use exp(+j omega t); BEM conjugates once. Sources, pair order and 49-per-source mask are unchanged.',
        'CSI will read these full parents with native fre=1:3. It will never regenerate a table.',
        'BEM independently checks every true shape on these exact data; the circle check covers the circle only.','']
    count=0
    for scene in [s for b in base.BATCHES for s in b]:
        path=ROOT/scene/'data.json'
        if not path.exists():continue
        record=json.loads(path.read_text())
        if 'selected_table_sha256' not in record:continue
        count+=1
        lines.extend([f'## {scene}','',f"Parent: `{record['path']}`.",f"Parent SHA-256: `{record['sha256']}`.",
            f"Selected: `{record['selected_table_path']}`.",f"Selected SHA-256: `{record['selected_table_sha256']}`.",''])
    lines.insert(2,f'Available: {count}/10 complete parent tables. Updated {base.now()}.')
    (ACT/'data_note.md').write_text('\n'.join(lines)+'\n')


def publish(scene):
    data_note()
    paths=[str(ROOT.relative_to(base.REPO)),str((ACT/'data_note.md').relative_to(base.REPO)),
           str((ACT/'plan.md').relative_to(base.REPO)),'experiments/baselines/csi/prepare_low_band_data.py']
    subprocess.run(['git','add',*paths],cwd=base.REPO,check=True)
    subprocess.run(['git','commit','-m',f'Freeze CSI/BEM simulated table: {scene}','--',*paths],cwd=base.REPO,check=True)
    subprocess.run(['git','push'],cwd=base.REPO,check=True)
    subprocess.run(['git','status','--short','--',*paths],cwd=base.REPO,check=True)


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    if (ROOT/'prefetch.json').exists():raise RuntimeError('prefetch already exists; do not overwrite or rerun it')
    original=json.loads((PARENT/'sources.json').read_text())
    for entry in original['files']:
        assert base.sha(base.REPO/entry['path'])==entry['sha256'],entry['path']
    source=dict(utc=base.now(),original_source_manifest=str(PARENT/'sources.json'),
                verified_original_files=original['files'],wrapper_sha256=base.sha(Path(__file__)),
                selection_helper_sha256=base.sha(Path(band.__file__)))
    base.write(ROOT/'sources.json',source)
    record=dict(started_utc=base.now(),pid=os.getpid(),state='running',completed=[],
                command=['env','PYTHONPATH=solvers:.',os.sys.executable,'-B','-m','experiments.baselines.csi.prepare_low_band_data'],
                source_manifest=str(ROOT/'sources.json'),nice=10,threads=8,time_stop=False)
    base.write(ROOT/'prefetch.json',record)
    os.nice(10)  # Yield CPU scheduling priority to the existing batch-1 fits.
    base.ROOT=ROOT;base.START=time.monotonic();base.STOP=False
    base.stopped=lambda:base.STOP or (ROOT/'STOP').exists()
    signal.signal(signal.SIGTERM,base.handle_stop);signal.signal(signal.SIGINT,base.handle_stop)
    for scene in [s for b in base.BATCHES for s in b]:
        if base.stopped():record['state']='user stopped';break
        folder=ROOT/scene
        folder.mkdir(exist_ok=False)
        try:
            if scene in base.BATCHES[0]:
                old=PARENT/scene;data=json.loads((old/'data.json').read_text())
                parent=Path(data['path']);assert base.sha(parent)==data['sha256']
                (folder/'truth').mkdir();(folder/'forward').mkdir()
                for name in ['geometry.mat','geometry.json']:shutil.copyfile(old/'truth'/name,folder/'truth'/name)
                shutil.copyfile(parent,folder/'forward/synthetic_input.txt')
                shutil.copyfile(old/'forward/forward_summary.json',folder/'forward/forward_summary.json')
                data.update(path=str(folder/'forward/synthetic_input.txt'),reused_parent_path=str(parent),reused_parent_sha256=data['sha256'])
                base.write(folder/'data.json',data);okay=True
            else:
                # This executes the exact original source verified above, one MATLAB at a time.
                okay=base.generate(scene,folder)
            if not okay:raise RuntimeError('original generator failed or user stopped; preserve outputs')
            band.select_data(folder)
            data=json.loads((folder/'data.json').read_text())
            for key in ['path','selected_table_path']:
                table=Path(data[key]);table.with_suffix(table.suffix+'.sha256').write_text(f'{base.sha(table)}  {table.name}\n')
            base.write(folder/'outcome.json',dict(state='reused frozen input' if scene in base.BATCHES[0] else 'generated',utc=base.now()))
            record['completed'].append(scene)
        except BaseException:
            (folder/'failure.txt').write_text(traceback.format_exc())
            base.write(folder/'outcome.json',dict(state='failed; evidence preserved',utc=base.now()))
            record['state']='failed; evidence preserved'
            base.write(ROOT/'prefetch.json',record);publish(scene+' failed');raise
        base.write(ROOT/'prefetch.json',record)
        publish(scene)
        print(json.dumps(dict(utc=base.now(),scene=scene,path=data['path'],sha256=data['sha256'],available=base.memory()['MemAvailable'])),flush=True)
    if len(record['completed'])==10:record['state']='all ten tables frozen'
    record['finished_utc']=base.now();base.write(ROOT/'prefetch.json',record);publish(record['state'])


if __name__=='__main__':main()
