"""Continue only after catalogs complete; retain every process failure and report it."""
import os
from pathlib import Path
import subprocess
import sys
import time
from experiments.cleaned_interface.fm001 import OUTPUT, verify
from experiments.cleaned_interface.io import read, write, digest

verify(OUTPUT)
if not read(OUTPUT/'phase1/gates.json')['full_matrix_passed']:
    raise SystemExit('Full-matrix gates failed')
if not read(OUTPUT/'phase1/controls.json')['passed']:
    raise SystemExit('Paired compatibility gate failed')
# The independently logged catalog job is already running. No campaign is
# started until its complete, qualified receipt exists.
catalog_pid=int(sys.argv[1])
while not (OUTPUT/'catalogs.json').exists():
    try:
        os.kill(catalog_pid,0)
    except ProcessLookupError:
        write(OUTPUT/'orchestration.json',dict(status='catalog process exited without complete qualification'))
        raise SystemExit('Catalog process ended without a qualification receipt')
    time.sleep(5)
if not read(OUTPUT/'catalogs.json')['passed']:
    raise SystemExit('Catalog qualification failed')
steps=[]
def run(name, arguments, required=True):
    started=time.time()
    log=OUTPUT/(name+'.log')
    if log.exists():
        raise FileExistsError(log)
    with log.open('w') as handle:
        process=subprocess.run([sys.executable,'-m','experiments.cleaned_interface.fm001',*arguments],stdout=handle,stderr=subprocess.STDOUT)
    row=dict(step=name,arguments=arguments,returncode=process.returncode,seconds=time.time()-started,log_sha256=digest(log))
    steps.append(row)
    write(OUTPUT/'orchestration.json',dict(status='running',steps=steps))
    print(row,flush=True)
    if required and process.returncode:
        write(OUTPUT/'orchestration.json',dict(status='stopped on required step failure',steps=steps))
        raise SystemExit(process.returncode)
    return process.returncode
run('phase2', ['paths'],required=False)
run('arm_F', ['arm','--arm','F'])
if read(OUTPUT/'phase1/gates.json')['relaxation_passed']:
    run('arm_FRr', ['arm','--arm','FRr'])
# Fallback is evaluation-only and cannot tune or restart either arm.
run('preliminary_report', ['report'])
summary=read(OUTPUT/'summary.json')
if not summary['F']['G1'] or not summary['F']['G2'] or not summary['FRr']['G1'] or not summary['FRr']['G2']:
    run('phase2_fallback', ['paths','--fallback'],required=False)
run('final_report', ['report'])
verify(OUTPUT)
write(OUTPUT/'orchestration.json',dict(status='complete',steps=steps))
