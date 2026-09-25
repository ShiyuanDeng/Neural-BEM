"""SC-035 final active-space field/derivative audit. No fitting or selection."""
from pathlib import Path
from dataclasses import replace
import numpy as np
from state_update import ProjectedUpdate
from experiments.shape_continuation import atlas_cases as ac,atlas_strategy_tests as ast,spd_cases as sc
from experiments.shape_continuation.lm_backend import Objective,Ledger,relative_columns

HERE=Path(__file__).resolve().parent
ledger=Ledger(cap=124,seconds=900,endpoint_reserve=0)
rows=[]
for case in ('peanut','circle_to_c','circle_to_star','kite'):
    record=sc.read(HERE/'runs'/case/'low/continue.json')
    curve=ast.curve_from(record['curve'])
    stages,config=ast.schedules(ast.catalog_only(case),'baseline')
    stage=replace(stages[-1],curve_modes=curve.band)
    update=ProjectedUpdate(sc.LENGTH)
    space=update.prepare(curve,stage.update_modes,curve.band)
    coarse=Objective(stage,ac.contrast(),config,ledger)
    fine=Objective(replace(stage,nodes=1024,refined_nodes=2048),ac.contrast(),config,ledger)
    a=coarse.production(curve,'final_refinement');b=fine.production(curve,'final_refinement')
    ja=coarse.jacobian(a,update,space);jb=fine.jacobian(b,update,space)
    relative=np.linalg.norm(ja-jb,axis=0)/np.maximum(np.linalg.norm(jb,axis=0),1e-30)
    fields=relative_columns(a.prediction,b.prediction)
    direction=np.random.default_rng(35037).normal(size=ja.shape[1]);direction/=np.linalg.norm(direction)
    eps=1e-7
    try:
        plus,minus=[fine.production(update.trial(space,s*eps*direction)[0],'final_fd').residual for s in (1,-1)]
        fd=(plus-minus)/(2*eps)
        difference=float(np.linalg.norm(fd-jb@direction)/np.linalg.norm(fd));failure=None
    except ValueError as exc:
        difference=None;failure=str(exc)
    row=dict(case=case,field_refinement_relative=fields,jacobian_refinement_relative=relative,
             full_trial_fd_relative=difference,fd_refusal=failure,
             passed=bool(np.all(fields<=stage.discrepancy_tolerances) and max(relative)<=1e-3
                         and difference is not None and difference<=1e-3))
    rows.append(row)
    print(case,'field',max(fields),'J',max(relative),'FD',difference,'pass',row['passed'],flush=True)
    sc.write(HERE/'final_derivative_audit.json',dict(rows=rows,passed=all(r['passed'] for r in rows),work=ledger.snapshot()))
assert all(r['passed'] for r in rows),'Final numerical audit failed'
