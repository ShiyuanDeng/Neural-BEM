"""Verify final FM-001 evidence and report consistency without rerunning fits."""
from pathlib import Path
import subprocess
import numpy as np
from experiments.cleaned_interface.fm001 import OUTPUT,verify,rows_for
from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.io import read,write,digest
verify(OUTPUT)
assert read(OUTPUT/'orchestration.json')['status']=='complete'
for phase in ('phase0','phase1'):
    assert read(OUTPUT/phase/'controls.json')['passed']
cat=read(OUTPUT/'catalogs.json')
assert cat['passed'] and len(cat['cases'])==36
for path,expected in cat['files'].items():
    assert digest(OUTPUT/path)==expected,path
assert all(q['observed_diagonal_identical'] and q['passed'] for r in cat['cases'] for q in r['catalogs'].values())
counts={}
for arm in ('F','FRr'):
    status=read(OUTPUT/arm/'status.json')
    paths=list((OUTPUT/arm/'runs').glob('*/result.json'))
    assert len(paths)==status['completed']
    assert len(list((OUTPUT/arm/'runs').iterdir()))==len(paths)
    recovered=0
    for p in paths:
        r=read(p)
        assert r['implementation_sha256']==digest(OUTPUT/'implementation.json')
        assert r['catalog_sha256']==digest(OUTPUT/'catalogs'/r['case']/'data.npz')
        m=r['metrics']
        predicate=bool(r['final_audit_passed'] and m['rms_mm']<=1 and m['hausdorff_upper_mm']<=2 and
                       np.all(np.asarray(r['relative_residual'])<=np.asarray(r['residual_limits'])))
        assert predicate==r['recovered']
        recovered+=predicate
    assert recovered==status['recovered']
    counts[arm]=dict(completed=len(paths),recovered=recovered,lost=status['lost'],stopped=status['stopped'])
assert counts['F']==dict(completed=36,recovered=36,lost=[],stopped=False)
assert counts['FRr']['completed']==4 and len(counts['FRr']['lost'])==2 and counts['FRr']['stopped']
paths=[read(p) for p in sorted((OUTPUT/'phase2/paths').glob('*/*.json'))]
assert len(paths)==12 and all(p['complete'] and len(p['points'])==81 for p in paths)
assert all(p['all_points_valid'] and all(q['passed'] for q in p['truth_qualification']) for p in paths)
radius=read(OUTPUT/'phase2/radius.json')
assert radius['complete'] and radius['all_points_valid'] and len(radius['points'])==401
assert all(q['passed'] for q in radius['qualification'])
reports=[b.ROOT/'docs/iterations/cleaned_interfaces/iteration_18/01_results.md',b.ROOT/'docs/reports/overnight_2026-10-03.md']
for p in reports:
    text=p.read_text()
    assert '32/36 unchanged-paired recoveries' in text
    assert '139 distinct pytest cases' in text
    assert 'G2(full)' in text and 'G2(unchanged paired)' in text
    active=False;width=None
    for line in text.splitlines():
        if line.startswith('|'):
            n=len(line.split('|'))
            if not active:width=n
            assert n==width,(p,line)
            active=True
        else:active=False
for name in ('C_endpoints.png','radius_detail.png','phase2/paths.png','phase2/radius.png'):
    assert (OUTPUT/name).stat().st_size>10000
check=subprocess.run(['git','diff','--check'],capture_output=True,text=True)
assert check.returncode==0,check.stdout+check.stderr
receipt=dict(verified=True,branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    plan_sha256=digest(b.ROOT/'docs/iterations/cleaned_interfaces/iteration_18/03_plan.md'),
    implementation_sha256=digest(OUTPUT/'implementation.json'),catalogs=36,arm_results=counts,
    path_checks=12,path_points=972,radius_points=401,tests=read(OUTPUT/'validation_additional.json'),
    reports={str(p.relative_to(b.ROOT)):digest(p) for p in reports},
    reporting_supplement_sha256=digest(OUTPUT/'complete_report.py'),
    results={str(p.relative_to(OUTPUT)):digest(p) for arm in ('F','FRr') for p in sorted((OUTPUT/arm/'runs').glob('*/result.json'))},
    git_status=subprocess.check_output(['git','status','--short'],text=True))
write(OUTPUT/'final_verification.json',receipt)
print('Verified sources, inputs, 36 catalogs, 40 fit results, 12 paths, radius scan, and both reports.')
