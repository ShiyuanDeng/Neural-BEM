"""Same physical directions through the normal atlas and directly (SC-036 B).

Geometry-only weighted projection; Jacobians at fixed truth control shapes.
This is diagnostic evidence, not an inverse or an atlas-driven policy.
"""
from pathlib import Path
from dataclasses import replace
import numpy as np
from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import normal_basis
from experiments.shape_continuation.updates import BorgesUpdate
from experiments.shape_continuation.forward import shape_jacobian
from experiments.shape_continuation.lm_backend import Objective, Ledger, normalize

HERE=Path(__file__).resolve().parent
ledger=Ledger(cap=100,seconds=600,endpoint_reserve=0)
rows=[]
for case in ('peanut','circle_to_star','circle_to_c'):
    catalog=ast.catalog_only(case)
    stages,config=ast.schedules(catalog,'baseline')
    stage=replace(stages[0],nodes=1024,refined_nodes=2048)
    curve,_=BorgesUpdate(sc.LENGTH,projection_tolerance=1e-5).regauge(
        ast.curve_from(sc.read(ast.source_folder(case)/'truth.json')),192)
    objective=Objective(stage,ac.contrast(),config,ledger)
    evaluation=objective.production(curve,'coordinate_control')
    forward=evaluation.forwards[0]
    nodes=forward.curve
    z=nodes.points @ np.array([1,1j])-curve.coefficients[curve.band]
    n=nodes.normals @ np.array([1,1j])
    weights=nodes.arc_length_weights/nodes.perimeter
    if case=='circle_to_c':
        alternative=np.column_stack((n.real,n.imag,(z*np.conj(n)).real,
            (z.real*np.conj(n)).real,(1j*z.imag*np.conj(n)).real,
            ((z.imag+1j*z.real)*np.conj(n)).real,
            (1j*z*np.conj(n)).real))
        kind='translations_scale_affine_rotation'
    else:
        theta=np.angle(z)
        cos=(z/np.abs(z)*np.conj(n)).real
        alternative=np.column_stack((n.real,n.imag,cos,cos*np.cos(2*theta),
            cos*np.cos(3*theta),cos*np.sin(2*theta),cos*np.sin(3*theta)))
        kind='spd_radial_and_translation'
    ledger.reserve(1);ledger.charge('reciprocal','direct_alternative')
    direct=shape_jacobian(forward,alternative/sc.LENGTH)
    for band in (24,48,96):
        basis=normal_basis(nodes,band)
        gram=basis.T@(weights[:,None]*basis)
        B=np.linalg.solve(gram,basis.T@(weights[:,None]*alternative))
        represented=basis@B
        ledger.reserve(1);ledger.charge('reciprocal','normal_atlas')
        normal=shape_jacobian(forward,basis/sc.LENGTH)
        prediction=normal@B
        actual_metric=alternative.T@(weights[:,None]*alternative)
        pulled_metric=B.T@gram@B
        row=dict(case=case,kind=kind,band=band,
            motion_relative_error=np.sqrt(np.sum(weights[:,None]*(represented-alternative)**2,axis=0)
               /np.sum(weights[:,None]*alternative**2,axis=0)),
            data_relative_error=np.linalg.norm(prediction-direct,axis=0)/np.linalg.norm(direct,axis=0),
            metric_relative_error=float(np.linalg.norm(actual_metric-pulled_metric)/np.linalg.norm(actual_metric)))
        rows.append(row)
        print(case,band,'motion',max(row['motion_relative_error']),'data',max(row['data_relative_error']),
              'metric',row['metric_relative_error'],flush=True)
sc.write(HERE/'chain_rule.json',dict(rows=rows,work=ledger.snapshot()))
