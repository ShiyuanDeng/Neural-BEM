from pathlib import Path
import subprocess, sys, tarfile
import numpy as np
from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.io import read, write, digest, curve_from
from experiments.cleaned_interface.physics import Execution
from experiments.cleaned_interface.runner import fit
from experiments.cleaned_interface.qualification import compare
out=b.ROOT/'results/validation/cleaned_interfaces/FM-001/phase0'
archive=b.DEFAULT_OUTPUT
sources=sorted(set(b.ROOT.glob('experiments/cleaned_interface/*.py')) | set(b.ROOT.glob('experiments/shape_continuation/*.py')) | set(b.ROOT.glob('solvers/**/*.py')) | {b.ROOT/'experiments/modal_atlas/mie_localize.py'})
plan=b.ROOT/'docs/iterations/cleaned_interfaces/iteration_18/03_plan.md'
with tarfile.open(out/'sources.tar.gz','w:gz') as tar:
    for p in sources: tar.add(p,arcname=b.path_ref(p),recursive=False)
write(out/'seal.json',dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),sources={b.path_ref(p):digest(p) for p in sources},source_archive_sha256=digest(out/'sources.tar.gz'),plan_sha256=digest(plan),environment=b.environment(),control_archive_manifest=digest(archive/'manifest.json')))
with (out/'tests.log').open('w') as log:
    result=subprocess.run([sys.executable,'-m','pytest','-q','experiments/cleaned_interface','experiments/exploratory_continuation/test_maintained_adapter.py','experiments/exploratory_continuation/test_controls.py'],stdout=log,stderr=subprocess.STDOUT)
write(out/'tests.json',dict(returncode=result.returncode,log_sha256=digest(out/'tests.log')))
if result.returncode: raise SystemExit('Phase 0 suite failed')
controls=[]
for case in ['modal__c13.3__development_c','modal__c4__development_c']:
    row=next(r for r in b.descriptors() if r['id']==case)
    folder=out/'runs'/case
    if folder.exists(): raise FileExistsError(folder)
    result=fit(b.fitting_problem(row,archive),execution=Execution(),output=folder,on_event=lambda e: print(case,e['operation']['label'],e['reason'],flush=True))
    metrics=b.score(row,curve_from(result['final_curve']))
    residual=result.get('relative_residual')
    result.update(metrics=metrics,recovered=bool(result['final_audit_passed'] and metrics['rms_mm']<=1 and metrics['hausdorff_upper_mm']<=2 and residual is not None and np.all(residual<=b.residual_limits(row))))
    write(folder/'result.json',result)
    check=compare(folder,archive/'runs'/case)
    controls.append(dict(case=case,comparison=check))
    write(out/'controls.json',dict(controls=controls,passed=all(x['comparison']['quality_pass'] for x in controls)))
    print('CONTROL',case,check,flush=True)
