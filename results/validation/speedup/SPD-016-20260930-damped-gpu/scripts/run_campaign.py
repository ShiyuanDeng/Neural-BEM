"""Sequential bounded campaign; no shell, fail-fast and retained logs."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/home/drdeng/Neural_SDF_BEM_AD')
BUNDLE = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
env = os.environ.copy()
env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
           PYTHONPATH='solvers:.', MPLCONFIGDIR='/tmp/spd016-mpl',
           SC_FREQUENCY_THREADS='4', SC_FORWARD_BACKEND='cuda', PYTHONDONTWRITEBYTECODE='1')
started = time.monotonic()
manifest = json.loads((BUNDLE/'reference_manifest.json').read_text())
for p, expected in manifest['sources_and_inputs'].items():
    assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == expected, p
scripts = {str(p.relative_to(BUNDLE)): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in (BUNDLE/'scripts').glob('*.py')}
(BUNDLE/'scripts_manifest.json').write_text(json.dumps(scripts,indent=2)+'\n')
metadata = dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                environment={k:env[k] for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','SC_FREQUENCY_THREADS','SC_FORWARD_BACKEND']},
                gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,utilization.gpu','--format=csv'],text=True),
                load=os.getloadavg(), concurrency='one worker at a time', commands=[])


def run(name, args, seconds):
    remaining = 2700-(time.monotonic()-started)
    if remaining < seconds:
        raise RuntimeError('Insufficient remaining campaign budget for '+name)
    command=[sys.executable,'-u',str(BUNDLE/'scripts'/args[0]),*args[1:]]
    metadata['commands'].append(dict(name=name,command=command,start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    (BUNDLE/'campaign.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('START',name,flush=True)
    with (BUNDLE/'logs'/f'{name}.log').open('x') as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=seconds)
    metadata['commands'][-1].update(returncode=result.returncode,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (BUNDLE/'campaign.json').write_text(json.dumps(metadata,indent=2)+'\n')
    result.check_returncode()
    print('DONE',name,flush=True)


run('qualification',['qualify.py'],600)
for contrast,scene in [('0.5','shifted_star'),('13.3','new_asymmetric')]:
    for mode in ['accelerated','baseline']:
        run(f'{mode}_{contrast}_{scene}',['replay.py',mode,contrast,scene,str(BUNDLE/'runs')],600)
print('CAMPAIGN_COMPLETE',flush=True)
