"""TOP-010 stage B: does continued local optimization use the descent direction?

Stage A found a feasible descent direction at the saved K=9 state, at the
optimizer's own trust bounds and damping ladder, decreasing both resolutions past
the acceptance margin. One detail in that probe matters: it restarts the damping
ladder at ``initial_damping``, whereas the run that produced the state had let
damping decay with every accepted step.

So the cheapest possible intervention is tested first, and it needs **no source
change of any kind**: restart the unmodified optimizer from the saved state,
under the recorded stopping rules, and see whether it descends again. Repeat
until a restart makes no further progress.

This is the control the review asks for before any optimizer option is written.
If a plain restart recovers progress, the stopping rule and the damping state --
not the geometry -- explain the halt, and no new option is needed to show it.

Truth and holdout are not read until every training decision is final. Nothing
here can select a direction or a step. Budgets are the plan's, enforced at
solver-call boundaries.
"""
import json
import sys
from pathlib import Path
from time import perf_counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from sdf_inverse.radial_topology import evaluate_multiradial_objective, run_multiradial_fd_inverse
from sdf_inverse.topology_controller import TopologyControllerConfig, _optimizer_config

DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
SOURCE = ROOT / 'results/validation/topology/TOP-009-20260912-bandwidth-capacity'
SCENE = 'far-two-stars'
# Declared in the plan: 2500 solves for the continuations, inside the 600 s total
# of which stage A spent 21.
SOLVE_CAP = 2500
SECONDS_CEILING = 540.0
MAX_RESTARTS = 12


def main():
    spec = benchmark.read(DATA / 'scene_spec.json')
    scene = {s['id']: s for s in spec['scenes']}[SCENE]
    solve = driver.baseline.iteration01_solve_config()
    production = driver.baseline._geometry_config(spec['production_nodes'])
    refined = driver.baseline._geometry_config(spec['refined_nodes'])
    training, _ = benchmark.shared_data(DATA, scene, spec)
    state = driver.deserialize_state(
        benchmark.read(SOURCE / 'stage4_uncapped_ladder.json')['final_state'])
    config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True,
                                      feasible_fd_jacobian=True, bandwidth_promotion=True)
    optimizer = _optimizer_config(state, config)

    def refined_loss(candidate):
        return float(evaluate_multiradial_objective(
            candidate, training, refined, solve_config=solve).loss)

    base = evaluate_multiradial_objective(state, training, production, solve_config=solve)
    base_refined = refined_loss(state)
    margin = (config.acceptance_absolute_margin
              + config.acceptance_relative_margin * base.loss)
    started = perf_counter()
    solves = 2
    print(f'saved state: production {base.loss:.6e} refined {base_refined:.6e} '
          f'margin {margin:.3e} · optimizer unmodified, damping restarts at '
          f'{optimizer.initial_damping:g}', flush=True)

    restarts = []
    current, current_loss, current_refined = state, float(base.loss), base_refined
    stop = 'no_further_progress'
    for index in range(MAX_RESTARTS):
        if solves >= SOLVE_CAP:
            stop = 'solve_cap'
            break
        if perf_counter() - started >= SECONDS_CEILING:
            stop = 'seconds_ceiling'
            break
        result = run_multiradial_fd_inverse(
            current, training, production, solve_config=solve, config=optimizer,
            minimum_component_radius_m=config.minimum_component_radius_m,
            cartesian_gauge=True, feasibility_geometry_configs=(refined,),
            feasible_fd_jacobian=True)
        solves += result.evaluation_count
        after = float(result.iterations[-1].loss)
        after_refined = refined_loss(result.final_state)
        solves += 1
        row = dict(restart=index, iterations=len(result.iterations) - 1,
                   stop_reason=result.stop_reason, converged=bool(result.converged),
                   evaluation_count=result.evaluation_count,
                   production_before=current_loss, production_after=after,
                   refined_before=current_refined, refined_after=after_refined,
                   production_delta=current_loss - after,
                   refined_delta=current_refined - after_refined,
                   relative_decrease=(current_loss - after) / current_loss if current_loss else 0.0,
                   one_sided_jacobian_columns=result.one_sided_jacobian_column_count,
                   unresolved_jacobian_columns=result.unresolved_jacobian_column_count)
        restarts.append(row)
        print(json.dumps(row), flush=True)
        if row['production_delta'] <= margin or row['refined_delta'] <= margin:
            stop = 'no_further_progress'
            break
        current, current_loss, current_refined = result.final_state, after, after_refined

    seconds = perf_counter() - started
    # Scored only after every training decision above is final.
    start_geometry = benchmark.geometry_metrics(state, scene, spec)
    geometry = benchmark.geometry_metrics(current, scene, spec)
    record = dict(
        scene=SCENE, data_bundle=str(DATA.relative_to(ROOT)),
        source_bundle=str(SOURCE.relative_to(ROOT)),
        optimizer_unmodified=True, source_change_required=False,
        solve_cap=SOLVE_CAP, seconds_ceiling=SECONDS_CEILING,
        margin=float(margin), stop_reason=stop, solves=solves, seconds=seconds,
        within_solve_cap=solves <= SOLVE_CAP,
        restarts_run=len(restarts), restarts=restarts,
        start_production_loss=float(base.loss), start_refined_loss=base_refined,
        final_production_loss=current_loss, final_refined_loss=current_refined,
        total_relative_decrease=(float(base.loss) - current_loss) / float(base.loss),
        improvement_factor=float(base.loss) / current_loss if current_loss > 0 else None,
        start_geometry=start_geometry, final_geometry=geometry,
        final_state=driver.serialize_state(current))
    driver.write_json(HERE / 'stageB_restart_continuation.json', record)

    print('\n=== stage B ===')
    print(f'{len(restarts)} restarts, stop {stop}, {solves} solves (cap {SOLVE_CAP}), '
          f'{seconds:.0f} s')
    print(f'production {base.loss:.6e} -> {current_loss:.6e} '
          f"({record['improvement_factor']:.1f}x better, unmodified optimizer)")
    print(f"matched error {start_geometry['maximum_matched_hausdorff_m']*1e3:.3f} -> "
          f"{geometry['maximum_matched_hausdorff_m']*1e3:.3f} mm, "
          f"IoU {start_geometry['union_iou']:.4f} -> {geometry['union_iou']:.4f}")


if __name__ == '__main__':
    main()
