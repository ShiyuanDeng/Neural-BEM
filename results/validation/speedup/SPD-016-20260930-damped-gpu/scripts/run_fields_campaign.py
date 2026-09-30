"""Conditional final field arm; share SPD-016's total 45-minute numerical budget."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/home/drdeng/Neural_SDF_BEM_AD')
BUNDLE=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
comparisons=json.loads((BUNDLE/'comparison.json').read_text())
assert len(comparisons)==2 and all(r['quality_pass'] and r['cost_pass'] for r in comparisons)
assert all(r['passed'] for r in json.loads((BUNDLE/'qualification.json').read_text()))
manifest=json.loads((BUNDLE/'reference_manifest.json').read_text())
for p,expected in manifest['sources_and_inputs'].items():
    assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==expected,p
env=os.environ.copy()
env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
           PYTHONPATH='solvers:.',MPLCONFIGDIR='/tmp/spd016-mpl',SC_FREQUENCY_THREADS='4',
           SC_FORWARD_BACKEND='cuda',PYTHONDONTWRITEBYTECODE='1')
previous=json.loads((BUNDLE/'campaign.json').read_text())
used=sum((datetime.datetime.fromisoformat(c['end_utc'])-datetime.datetime.fromisoformat(c['start_utc'])).total_seconds()
         for c in previous['commands'])
metadata=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              prior_numerical_seconds=used,commands=[],load=os.getloadavg(),
              gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,utilization.gpu','--format=csv'],text=True))
started=time.monotonic()
(BUNDLE/'fields_scripts_manifest.json').write_text(json.dumps({str(p.relative_to(BUNDLE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (BUNDLE/'scripts').glob('*.py')},indent=2)+'\n')


def run(name,args,ceiling):
    if 2700-used-(time.monotonic()-started)<ceiling:
        raise RuntimeError('Insufficient remaining SPD-016 budget')
    cmd=[sys.executable,'-u',str(BUNDLE/'scripts'/args[0]),*args[1:]]
    metadata['commands'].append(dict(name=name,command=cmd,start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    (BUNDLE/'fields_campaign.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('START',name,flush=True)
    with (BUNDLE/'logs'/f'{name}.log').open('x') as log:
        result=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=ceiling)
    metadata['commands'][-1].update(returncode=result.returncode,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (BUNDLE/'fields_campaign.json').write_text(json.dumps(metadata,indent=2)+'\n')
    result.check_returncode()
    print('DONE',name,flush=True)


run('field_qualification',['qualify_fields.py'],300)
for contrast,scene in [('0.5','shifted_star'),('13.3','new_asymmetric')]:
    run(f'fields_{contrast}_{scene}',['replay_fields.py',contrast,scene,str(BUNDLE/'runs')],600)
print('FIELD_CAMPAIGN_COMPLETE',flush=True)
