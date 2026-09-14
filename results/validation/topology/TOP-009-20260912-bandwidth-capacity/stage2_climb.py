"""Stage 2: does climbing the ladder actually reduce the objective?

One bounded fixed-topology continuation from the saved `far-two-stars` final
state, run with the promotion rule and without it. No topology event, no
candidate, no new observation. Budgets are the contract's, declared before
execution.

Reaching a higher mode count is not the result. The result is the objective at
both resolutions and the boundary error, and a run that climbs and reverts
everything is a clean negative.
"""
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path('/home/drdeng/Neural_SDF_BEM_AD')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from sdf_inverse import MultiRadialFourierState
from sdf_inverse.radial_topology import (
    evaluate_multiradial_objective, run_multiradial_fd_inverse,
)
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, _optimizer_config, chart_contour_modes,
    component_parameterization, next_bandwidth_rung, zero_padded_component,
)

DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
ARM, SCENE = 'H', 'far-two-stars'
SECONDS_CEILING = 600.0
SOLVE_CAP = 2500
DEFAULTS = TopologyControllerConfig(chart='cartesian')


def main(output):
    spec = benchmark.read(DATA / 'scene_spec.json')
    scene = {s['id']: s for s in spec['scenes']}[SCENE]
    solve = driver.baseline.iteration01_solve_config()
    production = driver.baseline._geometry_config(spec['production_nodes'])
    refined = driver.baseline._geometry_config(spec['refined_nodes'])
    training, holdout = benchmark.shared_data(DATA, scene, spec)
    start = driver.deserialize_state(
        benchmark.read(DATA / 'runs' / ARM / SCENE / 'metrics.json')['final_state'])
    config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True,
                                      feasible_fd_jacobian=True, bandwidth_promotion=True)
    cap = chart_contour_modes(config)

    def production_loss(state):
        return float(evaluate_multiradial_objective(
            state, training, production, solve_config=solve).loss)

    def refined_evaluation(state):
        return evaluate_multiradial_objective(state, training, refined, solve_config=solve)

    def holdout_errors(state):
        """Evaluation-only frequencies. Nothing here ever enters the fit."""
        return [float(evaluate_multiradial_objective(
            state, benchmark.ComplexScatteredData(
                driver.baseline._problem(np.array([f])),
                holdout.observed_scattered_response[:, [i]]),
            refined, solve_config=solve).relative_l2_error)
            for i, f in enumerate(spec['holdout_frequencies_hz'])]

    def refine(state):
        return run_multiradial_fd_inverse(
            state, training, production, solve_config=solve,
            config=_optimizer_config(state, config),
            minimum_component_radius_m=config.minimum_component_radius_m,
            cartesian_gauge=True, feasibility_geometry_configs=(refined,),
            feasible_fd_jacobian=True)

    base_production = production_loss(start)
    base_refined = refined_evaluation(start)
    margin = (DEFAULTS.acceptance_absolute_margin
              + DEFAULTS.acceptance_relative_margin * base_production)
    print(f'start: modes {[c.maximum_mode for c in start.components]}, '
          f'production {base_production:.6e}, refined {base_refined.loss:.6e}, '
          f'margin {margin:.3e}', flush=True)

    arms = []

    # --- without promotion: refine the state it already stopped at ---------
    started = perf_counter()
    plain = refine(start)
    plain_refined = refined_evaluation(plain.final_state)
    arms.append(dict(arm='no_promotion', solves=plain.evaluation_count,
        seconds=perf_counter() - started, stop_reason=plain.stop_reason,
        production_loss=float(plain.iterations[-1].loss),
        refined_loss=float(plain_refined.loss),
        refined_relative_error=float(plain_refined.relative_l2_error),
        final_modes=[c.maximum_mode for c in plain.final_state.components],
        holdout_relative_errors=holdout_errors(plain.final_state),
        final_state=driver.serialize_state(plain.final_state),
        geometry=benchmark.geometry_metrics(plain.final_state, scene, spec), rungs=[]))

    # --- with promotion: climb until nothing is retained ------------------
    started = perf_counter()
    state, solves, rungs = start, 0, []
    current_production, current_refined = base_production, base_refined.loss
    blocked = set()
    while solves < SOLVE_CAP and perf_counter() - started < SECONDS_CEILING:
        order = sorted((i for i, c in enumerate(state.components)
                        if c.component_id not in blocked),
                       key=lambda i: (state.components[i].maximum_mode,
                                      state.components[i].component_id))
        promoted_any = False
        for index in order:
            component = state.components[index]
            rung = next_bandwidth_rung(component, cap)
            record = dict(component=component.component_id, from_mode=component.maximum_mode,
                          to_mode=rung, retained=False)
            if rung is None:
                record['reason'] = 'at_bandwidth_cap'
                blocked.add(component.component_id)
                rungs.append(record)
                continue
            padded = MultiRadialFourierState(
                state.components[:index]
                + (zero_padded_component(component, rung),)
                + state.components[index + 1:])
            before = component_parameterization(component).discretize(2048).points
            after = component_parameterization(padded.components[index]).discretize(2048).points
            record['padding_boundary_displacement_m'] = float(np.abs(after - before).max())
            padded_loss = production_loss(padded)
            solves += 1
            record['padding_objective_change'] = float(padded_loss - current_production)
            if abs(padded_loss - current_production) > margin:
                record['reason'] = 'padding_changed_the_objective'
                blocked.add(component.component_id)
                rungs.append(record)
                continue
            result = refine(padded)
            solves += result.evaluation_count
            after_production = float(result.iterations[-1].loss)
            after_refined_evaluation = refined_evaluation(result.final_state)
            solves += 1
            record.update(production_after=after_production,
                          refined_after=float(after_refined_evaluation.loss),
                          optimizer_stop_reason=result.stop_reason,
                          one_sided_jacobian_columns=result.one_sided_jacobian_column_count)
            if (current_production - after_production > margin
                    and current_refined - after_refined_evaluation.loss > margin):
                record['retained'] = True
                state = result.final_state
                current_production, current_refined = after_production, after_refined_evaluation.loss
                promoted_any = True
                # Geometry and holdout at every retained rung, so "it overfits"
                # can be located rather than only asserted. Neither quantity
                # takes any part in the promotion decision above.
                rung_geometry = benchmark.geometry_metrics(state, scene, spec)
                record.update(
                    matched_hausdorff_m=rung_geometry['maximum_matched_hausdorff_m'],
                    union_iou=rung_geometry['union_iou'],
                    worst_holdout_relative_error=max(holdout_errors(state)))
            else:
                record['reason'] = 'no_decrease_at_both_resolutions'
                blocked.add(component.component_id)
            rungs.append(record)
            print(json.dumps(record), flush=True)
            break
        if not promoted_any and all(c.component_id in blocked for c in state.components):
            break
        if not promoted_any and not order:
            break
    seconds = perf_counter() - started
    final_refined = refined_evaluation(state)
    arms.append(dict(arm='promotion', solves=solves, seconds=seconds,
        stop_reason='ladder_exhausted' if solves < SOLVE_CAP else 'solve_cap',
        production_loss=float(current_production), refined_loss=float(final_refined.loss),
        refined_relative_error=float(final_refined.relative_l2_error),
        final_modes=[c.maximum_mode for c in state.components],
        holdout_relative_errors=holdout_errors(state),
        final_state=driver.serialize_state(state),
        geometry=benchmark.geometry_metrics(state, scene, spec),
        rungs=rungs, within_seconds_ceiling=seconds <= SECONDS_CEILING,
        within_solve_cap=solves <= SOLVE_CAP,
        rungs_attempted=sum(1 for r in rungs if r.get('to_mode') is not None),
        rungs_retained=sum(1 for r in rungs if r['retained'])))

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    driver.write_json(Path(output), dict(
        scene=SCENE, data_bundle=str(DATA.relative_to(ROOT)), arm=ARM,
        seconds_ceiling=SECONDS_CEILING, solve_cap=SOLVE_CAP, margin=float(margin),
        start_production_loss=base_production, start_refined_loss=float(base_refined.loss),
        start_modes=[c.maximum_mode for c in start.components],
        start_geometry=benchmark.geometry_metrics(start, scene, spec), arms=arms))

    print('\n=== stage 2 ===')
    for a in arms:
        print(f"{a['arm']:13s} modes={a['final_modes']} production={a['production_loss']:.6e} "
              f"refined={a['refined_loss']:.6e} "
              f"hausdorff={a['geometry']['maximum_matched_hausdorff_m']*1e3:.3f} mm "
              f"IoU={a['geometry']['union_iou']:.4f} "
              f"worst_holdout={max(a['holdout_relative_errors']):.4g} "
              f"solves={a['solves']} seconds={a['seconds']:.1f}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE / 'stage2_climb.json')
