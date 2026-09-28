from pathlib import Path
import json, os, shutil, subprocess, sys, time
root = Path('/home/drdeng/Neural_SDF_BEM_AD')
folder = root/'results/validation/speedup/SPD-015-20260928-native-geometry'
env = dict(os.environ, SC_FORWARD_BACKEND='cuda', SC_FREQUENCY_THREADS='4', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', PYTHONPATH='solvers:.')
env.pop('SC_GEOMETRY_RUNTIME', None)
commands=[]
for phase, cap in [('freeze',180), ('geometry',900), ('batches',1200), ('inverse',3600), ('video',3600), ('verify',180)]:
    command=[sys.executable,'-m','experiments.spd015_default_geometry.run',phase,str(folder)]
    log=Path('/tmp/spd015-freeze.log') if phase=='freeze' else folder/(phase+'.log')
    start=time.time()
    print('START',phase,flush=True)
    with log.open('w') as stream:
        result=subprocess.run(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=cap)
    commands.append(dict(phase=phase,command=command,start=start,seconds=time.time()-start,returncode=result.returncode,timeout_seconds=cap))
    if folder.exists():
        (folder/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print('DONE',phase,result.returncode,round(time.time()-start,2),flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    if phase=='freeze':
        for source,dest in [('/tmp/spd015-regression.log','regression.log'),('/tmp/spd015-cpu.log','cpu_tests.log'),('/tmp/spd015-freeze.log','freeze.log'),(__file__,'campaign.py')]:
            shutil.copyfile(source,folder/dest)
    if phase in ('geometry','batches','inverse','video'):
        data=json.loads((folder/phase/'result.json').read_text())
        if not data['passed']:
            raise SystemExit('Qualification failed: '+phase)
