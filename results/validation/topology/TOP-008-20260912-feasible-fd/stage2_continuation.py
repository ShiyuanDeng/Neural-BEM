"""Stage 2: does a measured Jacobian produce a feasible decrease at the floor?

One bounded fixed-topology continuation from the saved guarded `far-ellipse-star`
final state, run twice: once with the frozen-column stencil and once with the
feasible one. No topology event, no candidate, no new observation. The budgets
below are the contract's, declared before execution.

A change of stop reason is not the result. The result is whether the objective
decreases at *both* resolutions under the existing margin convention, and
whether the pinned component actually moves.
"""
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from sdf_inverse.radial_topology import (
    component_radius_floor, evaluate_multiradial_objective, run_multiradial_fd_inverse,
)
from sdf_inverse.topology_controller import TopologyControllerConfig, _optimizer_config

SOURCE = ROOT / 'results/validation/topology/TOP-007-20260911-refined-feasibility'
SCENE = 'far-ellipse-star'
# Contract budgets, declared before execution.
SECONDS_CEILING = 600.0
SOLVE_CAP = 1200
# The existing acceptance convention, read from the controller defaults rather
# than restated, so this stage cannot quietly use a friendlier margin.
DEFAULTS = TopologyControllerConfig(chart='cartesian')


def main():
    spec = benchmark.read(HERE / 'scene_spec.json')
    scene = {s['id']: s for s in spec['scenes']}[SCENE]
    solve = driver.baseline.iteration01_solve_config()
    production = driver.baseline._geometry_config(spec['production_nodes'])
    refined = driver.baseline._geometry_config(spec['refined_nodes'])
    training, holdout = benchmark.shared_data(HERE, scene, spec)
    start = driver.deserialize_state(
        benchmark.read(SOURCE / 'runs' / 'G' / SCENE / 'metrics.json')['final_state'])

    base_production = evaluate_multiradial_objective(
        start, training, production, solve_config=solve)
    base_refined = evaluate_multiradial_objective(start, training, refined, solve_config=solve)
    margin = (DEFAULTS.acceptance_absolute_margin
              + DEFAULTS.acceptance_relative_margin * base_production.loss)
    print(f'start: production {base_production.loss:.6e}, refined {base_refined.loss:.6e}, '
          f'margin {margin:.3e}')

    config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True)
    optimizer = _optimizer_config(start, config)
    records = []
    for label, feasible_fd in (('frozen', False), ('feasible', True)):
        started = perf_counter()
        result = run_multiradial_fd_inverse(
            start, training, production, solve_config=solve, config=optimizer,
            minimum_component_radius_m=config.minimum_component_radius_m,
            cartesian_gauge=True, feasibility_geometry_configs=(refined,),
            feasible_fd_jacobian=feasible_fd)
        seconds = perf_counter() - started
        final_refined = evaluate_multiradial_objective(
            result.final_state, training, refined, solve_config=solve)
        moved = [dict(
            component_id=before.component_id,
            maximum_mode=before.maximum_mode,
            radius_floor_before_m=float(component_radius_floor(before)),
            radius_floor_after_m=float(component_radius_floor(after)),
            displacement_m=float(np.linalg.norm(
                np.asarray(after.center) - np.asarray(before.center))))
            for before, after in zip(start.components, result.final_state.components)]
        geometry = benchmark.geometry_metrics(result.final_state, scene, spec)
        production_delta = base_production.loss - result.iterations[-1].loss
        refined_delta = base_refined.loss - final_refined.loss
        record = dict(
            arm=label, feasible_fd_jacobian=feasible_fd,
            stop_reason=result.stop_reason, converged=result.converged,
            iterations=len(result.iterations) - 1,
            evaluation_count=result.evaluation_count,
            infeasible_trial_count=result.infeasible_trial_count,
            feasibility_rejected_trial_count=result.feasibility_rejected_trial_count,
            one_sided_jacobian_columns=result.one_sided_jacobian_column_count,
            unresolved_jacobian_columns=result.unresolved_jacobian_column_count,
            seconds=seconds,
            production_loss=float(result.iterations[-1].loss),
            refined_loss=float(final_refined.loss),
            production_delta=float(production_delta), refined_delta=float(refined_delta),
            refined_relative_error=float(final_refined.relative_l2_error),
            components=moved, geometry=geometry,
            within_seconds_ceiling=seconds <= SECONDS_CEILING,
            within_solve_cap=result.evaluation_count <= SOLVE_CAP,
            # The hypothesis, stated as a predicate rather than a narrative: a
            # real decrease at both resolutions, not merely a different stop.
            decreased_at_both_resolutions=bool(
                production_delta > margin and refined_delta > margin))
        records.append(record)
        print(json.dumps({k: v for k, v in record.items()
                          if k not in ('components', 'geometry')}, indent=1), flush=True)
        for item in moved:
            print(f"  {item['component_id']} mode {item['maximum_mode']}: floor "
                  f"{item['radius_floor_before_m']*1e3:.3f} -> "
                  f"{item['radius_floor_after_m']*1e3:.3f} mm, "
                  f"centre moved {item['displacement_m']*1e3:.3f} mm")

    driver.write_json(HERE / 'stage2_continuation.json', dict(
        scene=SCENE, source_bundle=str(SOURCE.relative_to(ROOT)),
        seconds_ceiling=SECONDS_CEILING, solve_cap=SOLVE_CAP, margin=float(margin),
        start_production_loss=float(base_production.loss),
        start_refined_loss=float(base_refined.loss),
        start_geometry=benchmark.geometry_metrics(start, scene, spec), arms=records))

    print('\n=== stage 2 ===')
    for record in records:
        print(f"{record['arm']:9s} stop={record['stop_reason']:22s} "
              f"production {record['production_loss']:.6e} refined {record['refined_loss']:.6e} "
              f"decrease_at_both={record['decreased_at_both_resolutions']} "
              f"hausdorff={record['geometry']['maximum_matched_hausdorff_m']*1e3:.3f} mm")


if __name__ == '__main__':
    main()
