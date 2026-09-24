"""Check smaller versions of the saved numerically refused circle trial."""
import json
import argparse
from pathlib import Path
import numpy as np
from experiments.shape_continuation import spd_cases as bridge
from experiments.shape_continuation import atlas_cases as cases
from experiments.shape_continuation import atlas_strategy_tests as saved_inputs
from sdf_inverse import radial_topology as rt
from sdf_inverse.analytic_jacobian import cartesian_residual_jacobian
from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
from sdf_inverse.runtime import inverse_runtime
from gpr_bem_kress.execution import execution
from ordered_boundary.validation_cache import geometry_validation

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
output=parser.parse_args().output
output.mkdir(parents=True,exist_ok=False)
inputs=bridge.load();p=inputs['top025'].p
catalog=saved_inputs.catalog_only('wrong_circle')
data=p.training_data(p.TRAIN[:1],catalog[cases.CATALOG_HZ.index(.5e9)].scattered[:,None])
record=bridge.read(bridge.ROOT/'results/validation/shape_continuation/SC-030-spd008-comparison/runs/repeat_0/wrong_circle/spd008/stage_1/numerical_failure.json')
base=p.driver.deserialize_state(record['production_base']['state'])
candidate=p.driver.deserialize_state(record['production_candidate']['state'])
delta=candidate.parameter_vector()-base.parameter_vector()
rows=[]
with inverse_runtime('compiled'),execution(kernels='real_bessel',device='cpu'),geometry_validation('certified'):
    for scale in (0.,.5,1.):
        state=base.incremented(scale*delta).polar_angle_gauge_fixed()[0]
        low=rt.evaluate_multiradial_objective(state,data,p.driver.baseline._geometry_config(512),solve_config=inputs['solve'])
        high=rt.evaluate_multiradial_objective(state,data,p.driver.baseline._geometry_config(1024),solve_config=inputs['solve'])
        rows.append(dict(step_fraction=scale,production_loss=low.loss,refined_loss=high.loss,
            discrepancy=cases.relative(low.prediction,high.prediction),
            feasible=p.feasible(state,(512,1024),inputs['solve'],inputs['control'].minimum_component_radius_m)))
    initial=rt.MultiRadialFourierState((circle_cartesian_fourier_state(cases.START['center'],cases.START['radius'],'comparison.circle',maximum_mode=4),))
    matrix,_=cartesian_residual_jacobian(initial,data,p.driver.baseline._geometry_config(512),solve_config=inputs['solve'],directions=initial.gauge_tangent_basis(),method='reciprocal')
    singular=np.linalg.svd(matrix,compute_uv=False)
    for row in rows[1:]:
        row['acceptance']=inputs['top025'].m.old.acceptance(rows[0]['production_loss'],row['production_loss'],rows[0]['refined_loss'],row['refined_loss'])
    result=dict(trial_scales=rows,K4_initial_singular_values=singular,K4_initial_condition_number=singular[0]/singular[-1])
    bridge.write(output/'rejected_step_diagnostics.json',result)
    print(json.dumps(result,default=lambda x:x.tolist()),flush=True)
