"""Derivative and feasibility diagnostics on saved states; no optimization."""
from pathlib import Path
import argparse
from collections import Counter
import numpy as np
from experiments.shape_continuation import spd_cases as bridge
from experiments.shape_continuation import atlas_cases as cases
from experiments.shape_continuation import atlas_strategy_tests as saved_inputs
from sdf_inverse import radial_topology as rt
from sdf_inverse.analytic_jacobian import cartesian_residual_jacobian
from sdf_inverse.runtime import inverse_runtime
from gpr_bem_kress.execution import execution
from ordered_boundary.validation_cache import geometry_validation

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
OUT=parser.parse_args().output
OUT.mkdir(parents=True,exist_ok=False)
SAVED=bridge.ROOT/'results/validation/shape_continuation/SC-030-spd008-comparison/runs/repeat_0'
inputs=bridge.load(); p=inputs['top025'].p
geometry=p.driver.baseline._geometry_config(512)
refined=p.driver.baseline._geometry_config(1024)
solve=inputs['solve']; floor=inputs['control'].minimum_component_radius_m
rows=[]
def allowed(state,delta):
    try:
        trial=state.incremented(delta).polar_angle_gauge_fixed()[0]
        radius=rt.component_radius_floor(trial.components[0])
        if radius<floor: return False,'radius_floor',radius
        for g in (geometry,refined):
            if not rt.multiradial_geometry_admissible(trial,g,solve_config=solve):
                return False,'geometry',radius
        return True,'allowed',radius
    except Exception as exc:
        return False,str(exc),None

with inverse_runtime('compiled'),execution(kernels='real_bessel',device='cpu'),geometry_validation('certified'):
    for case in ('wrong_circle','circle_to_star'):
        catalog=saved_inputs.catalog_only(case)
        locations=[('start',SAVED/case/'spd008/stage_1/initial_state.json')]
        if case=='circle_to_star':
            locations.append(('failed_endpoint',SAVED/case/'spd008/stage_2/accepted_state.json'))
        for name,path in locations:
            loaded=bridge.read(path)
            state=p.driver.deserialize_state(loaded['state'] if isinstance(loaded,dict) else loaded)
            frequencies=p.TRAIN[:2 if name=='failed_endpoint' else 1]
            observed=np.column_stack([catalog[cases.CATALOG_HZ.index(f)].scattered for f in frequencies])
            data=p.training_data(frequencies,observed)
            basis=state.gauge_tangent_basis()
            jr,pred=cartesian_residual_jacobian(state,data,geometry,solve_config=solve,directions=basis,method='reciprocal')
            jo,_=cartesian_residual_jacobian(state,data,geometry,solve_config=solve,directions=basis,method='operator')
            singular=np.linalg.svd(jr,compute_uv=False)
            points=p.boundary_points(state,8192)[0]
            row=dict(case=case,state=name,source=str(path),frequencies_hz=frequencies,
                     radius_certificate_mm=1000*rt.component_radius_floor(state.components[0]),
                     actual_minimum_radius_mm=1000*np.min(np.linalg.norm(points-state.components[0].center,axis=1)),
                     jacobian_relative_difference=float(np.linalg.norm(jr-jo)/np.linalg.norm(jo)),
                     finite_reciprocal_jacobian=bool(np.isfinite(jr).all()),singular_values=singular,
                     condition_number=float(singular[0]/singular[-1]),stencils=[])
            if name=='failed_endpoint':
                for size in (1e-4,1e-5,1e-6):
                    checks=[(allowed(state,size*d),allowed(state,-size*d)) for d in basis]
                    counts=Counter(('central' if a[0] and b[0] else 'one_sided' if a[0] or b[0] else 'unresolved') for a,b in checks)
                    row['stencils'].append(dict(step_m=size,counts=dict(counts),
                        blocked=[dict(index=i,plus=a,minus=b) for i,(a,b) in enumerate(checks) if not a[0] and not b[0]]))
                jf,_=cartesian_residual_jacobian(state,data,refined,solve_config=solve,directions=basis,method='reciprocal')
                row['jacobian_512_vs_1024_relative']=float(np.linalg.norm(jr-jf)/np.linalg.norm(jf))
            rows.append(row)
            bridge.write(OUT/'derivative_diagnostics.json',rows)
            print({k:v for k,v in row.items() if k not in ('singular_values','source')},flush=True)
