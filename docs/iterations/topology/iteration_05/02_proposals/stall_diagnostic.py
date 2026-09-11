"""Review diagnostic: why does the final guarded state freeze Jacobian columns? Geometry only."""
import json
import numpy as np
import run_fourier_topology_controller as driver
from sdf_inverse.radial_topology import component_radius_floor, multiradial_geometry_admissible
from sdf_inverse.topology_controller import TopologyControllerConfig, _optimizer_config
from sdf_inverse.geometry import OrderedSDFGeometryError

b = 'results/validation/topology/TOP-007-20260911-refined-feasibility/runs/G/far-ellipse-star/'
state = driver.deserialize_state(json.load(open(b + 'metrics.json'))['final_state'])
solve = driver.baseline.iteration01_solve_config()
production, refined = driver.baseline._geometry_config(64), driver.baseline._geometry_config(128)
spec = json.load(open('config/topology_scenes_v1.json'))
config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True)
opt = _optimizer_config(state, config)

basis = state.gauge_tangent_basis()
steps = opt.resolved_finite_difference_steps(state.parameter_count)
sizes = np.sqrt((basis * basis) @ (steps * steps))
print(f'components: {[(c.component_id, c.maximum_mode) for c in state.components]}')
print(f'parameters {state.parameter_count}, gauge directions {len(basis)}')
counts = dict(retract_failed=0, radius_floor=0, production_inadmissible=0, refined_inadmissible=0, ok=0)
for i, (d, h) in enumerate(zip(basis, sizes)):
    verdicts = []
    for sign in (1, -1):
        try:
            trial = state.incremented(sign * h * d).polar_angle_gauge_fixed()[0]
        except (ValueError, OrderedSDFGeometryError) as exc:
            verdicts.append('retract_failed'); continue
        if any(component_radius_floor(c) < config.minimum_component_radius_m for c in trial.components):
            verdicts.append('radius_floor')
        elif not multiradial_geometry_admissible(trial, production, solve_config=solve):
            verdicts.append('production_inadmissible')
        elif not multiradial_geometry_admissible(trial, refined, solve_config=solve):
            verdicts.append('refined_inadmissible')
        else:
            verdicts.append('ok')
    worst = next((v for v in verdicts if v != 'ok'), 'ok')
    counts[worst] += 1
    if worst != 'ok':
        print(f'  direction {i:3d} step {h:.3e}: {verdicts}')
print('summary:', counts)
