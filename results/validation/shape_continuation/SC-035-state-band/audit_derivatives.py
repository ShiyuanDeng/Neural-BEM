"""Post-pilot derivative refinement audit at all accepted endpoints (no fitting)."""
from pathlib import Path
from dataclasses import replace
import numpy as np
from state_update import ProjectedUpdate
from experiments.shape_continuation import atlas_cases as ac,atlas_strategy_tests as ast,spd_cases as sc
from experiments.shape_continuation.lm_backend import Objective,Ledger

HERE=Path(__file__).resolve().parent
ledger=Ledger(cap=150,seconds=900,endpoint_reserve=0)
rows=[]
for case in ('peanut','circle_to_c','circle_to_star','kite'):
    for arm in ('low','high'):
        saved=sc.read(HERE/'runs'/case/arm/'pilot.json')
        curve=ast.curve_from(saved['curve'])
        stages,config=ast.schedules(ast.catalog_only(case),'baseline')
        stage=replace(stages[0],curve_modes=curve.band)
        update=ProjectedUpdate(sc.LENGTH)
        space=update.prepare(curve,stage.update_modes,curve.band)
        coarse=Objective(stage,ac.contrast(),config,ledger)
        fine=Objective(replace(stage,nodes=1024,refined_nodes=2048),ac.contrast(),config,ledger)
        a=coarse.production(curve,'pilot_refinement');b=fine.production(curve,'pilot_refinement')
        ja=coarse.jacobian(a,update,space);jb=fine.jacobian(b,update,space)
        relative=np.linalg.norm(ja-jb,axis=0)/np.maximum(np.linalg.norm(jb,axis=0),1e-30)
        direction=np.random.default_rng(35036).normal(size=ja.shape[1]);direction/=np.linalg.norm(direction)
        eps=1e-7
        try:
            plus,minus=[fine.production(update.trial(space,s*eps*direction)[0],'pilot_fd').residual for s in (1,-1)]
            fd=(plus-minus)/(2*eps)
            difference=float(np.linalg.norm(fd-jb@direction)/np.linalg.norm(fd))
            failure=None
        except ValueError as exc:
            difference=None;failure=str(exc)
        row=dict(case=case,arm=arm,refinement_relative=relative,
            full_trial_fd_relative=difference,fd_refusal=failure,
            passed=bool(max(relative)<=1e-3 and difference is not None and difference<=1e-3))
        rows.append(row)
        print(case,arm,'refinement',max(relative),'FD',difference,'pass',row['passed'],flush=True)
        sc.write(HERE/'pilot_derivative_audit.json',dict(rows=rows,passed=all(r['passed'] for r in rows),work=ledger.snapshot()))
