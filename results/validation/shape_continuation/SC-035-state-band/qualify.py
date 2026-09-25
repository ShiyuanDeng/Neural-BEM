"""SC-035 geometry and full-field checks before any inverse dispatch."""
from pathlib import Path
from dataclasses import replace
import numpy as np
from state_update import ProjectedUpdate, resize
from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import FourierCurve,reparameterize
from experiments.shape_continuation.lm_backend import Ledger,Objective
from experiments.shape_continuation.updates import BorgesUpdate

HERE=Path(__file__).resolve().parent
ledger=Ledger(cap=200,seconds=600,endpoint_reserve=0)
rows=[]
for case,K in [('peanut',8),('circle_to_c',12),('circle_to_star',12),('peanut',192)]:
    truth=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    curve,_=reparameterize(truth,K,tolerance=np.inf)
    stages,config=ast.schedules(ast.catalog_only(case),'baseline')
    stage=replace(stages[0],curve_modes=K)
    update=ProjectedUpdate(sc.LENGTH)
    space=update.prepare(curve,3,K)
    assert np.array_equal(update.trial(space,np.zeros(7))[0].coefficients,curve.coefficients)
    assert np.max(np.abs(resize(curve,192).values(4096)-curve.values(4096)))==0
    half=ProjectedUpdate(sc.LENGTH,derivative_step_m=.5e-7)
    hs=half.prepare(curve,3,K)
    derivative_stability=float(np.linalg.norm(space.derivatives-hs.derivatives)/np.linalg.norm(hs.derivatives))
    obj=Objective(stage,ac.contrast(),config,ledger)
    base=obj.production(curve,'qualification_base')
    jac=obj.jacobian(base,update,space)
    old=BorgesUpdate(sc.LENGTH,projection_tolerance=1e-5)
    old_jac=obj.jacobian(base,old,old.prepare(curve,3,K))
    direction=np.random.default_rng(36035).normal(size=7)
    direction/=np.linalg.norm(direction)
    tests=[]
    for eps in (1e-6,1e-7):
        plus,minus=[obj.production(update.trial(space,s*eps*direction)[0],'qualification_trial').residual
                    for s in (1,-1)]
        fd=(plus-minus)/(2*eps)
        tests.append(dict(step=eps,relative_error=float(np.linalg.norm(fd-jac@direction)/np.linalg.norm(fd))))
    row=dict(case=case,K=K,derivative_stability=derivative_stability,tests=tests,
        old_jacobian_relative_difference=float(np.linalg.norm(jac-old_jac)/np.linalg.norm(jac)))
    if K==192:
        step=1e-4*direction
        p=update.trial(space,step)[0]
        n=old.trial(old.prepare(curve,3,K),step)[0]
        row['borges_max_sample_difference_mm']=50*float(np.max(np.abs(p.values(8192)-n.values(8192))))
        assert row['borges_max_sample_difference_mm']<1e-3
    row['passed']=derivative_stability<1e-3 and max(t['relative_error'] for t in tests)<1e-3
    rows.append(row)
    print(row,flush=True)
    sc.write(HERE/'qualification.json',dict(rows=rows,work=ledger.snapshot()))
passed=all(r['passed'] for r in rows) and max(r['old_jacobian_relative_difference'] for r in rows if r['K']<192)>.001
sc.write(HERE/'qualification.json',dict(rows=rows,passed=passed,work=ledger.snapshot(),
    source_sha256={p.name:sc.digest(p) for p in (Path(__file__),HERE/'state_update.py')}))
assert passed,'SC-035 qualification failed'
