"""Stage 4: let the ladder finish.

Stage 2 stopped on its declared 2500-solve cap at modes [6, 5], leaving one
component three rungs below the bandwidth its seven-lobed truth requires, so no
statement about the *full* ladder was ever earned. This runs the same climb from
the same saved state with a budget large enough to exhaust it.

Budgets below are declared before execution and are the only thing that differs
from stage 2. The promotion rule is unchanged and still training-only: geometry,
phase and holdout are recorded at every rung as diagnostics and take no part in
any decision.

Phase is recorded explicitly. Stage 3 showed a component can acquire the right
shape and sit rotated out of alignment, which the matched-Hausdorff gate scores
worse than the circle it replaced, so a climb that improves shape while the gate
worsens must be distinguishable from one that simply goes wrong.
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
from sdf_inverse import MultiRadialFourierState
from sdf_inverse.radial_topology import (
    _minimum_polygon_distance, evaluate_multiradial_objective, run_multiradial_fd_inverse,
)
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, _optimizer_config, chart_contour_modes,
    component_parameterization, next_bandwidth_rung, zero_padded_component,
)

DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
ARM, SCENE = 'H', 'far-two-stars'
# Declared before execution. Large enough to exhaust the ladder: the stage-2
# climb spent 3127 solves reaching [6, 5], and the remaining rungs cost more per
# rung because each adds two gauge directions per component.
SOLVE_CAP = 40000
SECONDS_CEILING = 3600.0
SAMPLES = 512
ROTATIONS = np.linspace(0.0, 2.0 * np.pi, 181)
DEFAULTS = TopologyControllerConfig(chart='cartesian')


def hausdorff(a, b):
    return float(max(_minimum_polygon_distance(a, b).max(),
                     _minimum_polygon_distance(b, a).max()))


def rotated(points, angle):
    center = points.mean(axis=0)
    rotation = np.array([[np.cos(angle), -np.sin(angle)],
                         [np.sin(angle), np.cos(angle)]])
    return (points - center) @ rotation.T + center


def main():
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
    truth_points = {c.component_id: c.discretize(SAMPLES).points
                    for c in benchmark.truth_curves(scene)}

    def production_loss(state):
        return float(evaluate_multiradial_objective(
            state, training, production, solve_config=solve).loss)

    def refined_loss(state):
        return float(evaluate_multiradial_objective(
            state, training, refined, solve_config=solve).loss)

    def holdout_worst(state):
        return max(float(evaluate_multiradial_objective(
            state, benchmark.ComplexScatteredData(
                driver.baseline._problem(np.array([f])),
                holdout.observed_scattered_response[:, [i]]),
            refined, solve_config=solve).relative_l2_error)
            for i, f in enumerate(spec['holdout_frequencies_hz']))

    def phase_report(state):
        """Matched error, and what it would be with the phase corrected."""
        rows = []
        for component in state.components:
            points = component_parameterization(component).discretize(SAMPLES).points
            best_id, best_raw, best_rot, best_angle = None, np.inf, np.inf, 0.0
            for truth_id, target in truth_points.items():
                raw = hausdorff(points, target)
                if raw < best_raw:
                    rotation = min((hausdorff(rotated(points, a), target), float(a))
                                   for a in ROTATIONS)
                    best_id, best_raw, best_rot, best_angle = truth_id, raw, rotation[0], rotation[1]
            rows.append(dict(component=component.component_id,
                             maximum_mode=component.maximum_mode, truth=best_id,
                             hausdorff_m=best_raw, phase_corrected_hausdorff_m=best_rot,
                             rotation_deg=float(np.degrees(best_angle))))
        return rows

    def refine(state):
        return run_multiradial_fd_inverse(
            state, training, production, solve_config=solve,
            config=_optimizer_config(state, config),
            minimum_component_radius_m=config.minimum_component_radius_m,
            cartesian_gauge=True, feasibility_geometry_configs=(refined,),
            feasible_fd_jacobian=True)

    base_production = production_loss(start)
    base_refined = refined_loss(start)
    margin = (DEFAULTS.acceptance_absolute_margin
              + DEFAULTS.acceptance_relative_margin * base_production)
    print(f'start modes {[c.maximum_mode for c in start.components]} '
          f'production {base_production:.6e} margin {margin:.3e}', flush=True)

    started = perf_counter()
    state, solves, rungs = start, 0, []
    current_production, current_refined = base_production, base_refined
    blocked = set()
    stop = 'ladder_exhausted'
    while True:
        if solves >= SOLVE_CAP:
            stop = 'solve_cap'
            break
        if perf_counter() - started >= SECONDS_CEILING:
            stop = 'seconds_ceiling'
            break
        order = sorted((i for i, c in enumerate(state.components)
                        if c.component_id not in blocked),
                       key=lambda i: (state.components[i].maximum_mode,
                                      state.components[i].component_id))
        if not order:
            break
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
            after_refined = refined_loss(result.final_state)
            solves += 1
            record.update(production_after=after_production, refined_after=after_refined,
                          optimizer_stop_reason=result.stop_reason,
                          one_sided_jacobian_columns=result.one_sided_jacobian_column_count)
            if (current_production - after_production > margin
                    and current_refined - after_refined > margin):
                record['retained'] = True
                state = result.final_state
                current_production, current_refined = after_production, after_refined
                promoted_any = True
                geometry = benchmark.geometry_metrics(state, scene, spec)
                record.update(matched_hausdorff_m=geometry['maximum_matched_hausdorff_m'],
                              union_iou=geometry['union_iou'],
                              worst_holdout_relative_error=holdout_worst(state),
                              phase=phase_report(state),
                              modes=[c.maximum_mode for c in state.components])
            else:
                record['reason'] = 'no_decrease_at_both_resolutions'
                blocked.add(component.component_id)
            rungs.append(record)
            print(json.dumps({k: v for k, v in record.items() if k != 'phase'}), flush=True)
            break
        if not promoted_any and all(c.component_id in blocked for c in state.components):
            break

    seconds = perf_counter() - started
    geometry = benchmark.geometry_metrics(state, scene, spec)
    driver.write_json(HERE / 'stage4_uncapped_ladder.json', dict(
        scene=SCENE, data_bundle=str(DATA.relative_to(ROOT)), arm=ARM,
        solve_cap=SOLVE_CAP, seconds_ceiling=SECONDS_CEILING, margin=float(margin),
        start_production_loss=base_production, start_refined_loss=base_refined,
        start_modes=[c.maximum_mode for c in start.components],
        start_geometry=benchmark.geometry_metrics(start, scene, spec),
        start_phase=phase_report(start),
        stop_reason=stop, ladder_finished=stop == 'ladder_exhausted',
        solves=solves, seconds=seconds,
        rungs_attempted=sum(1 for r in rungs if r.get('to_mode') is not None),
        rungs_retained=sum(1 for r in rungs if r['retained']),
        final_modes=[c.maximum_mode for c in state.components],
        final_production_loss=current_production, final_refined_loss=current_refined,
        final_geometry=geometry, final_phase=phase_report(state),
        final_worst_holdout_relative_error=holdout_worst(state),
        final_state=driver.serialize_state(state), rungs=rungs))

    print(f'\n=== stage 4 ===')
    print(f'stop {stop}  modes {[c.maximum_mode for c in state.components]}  '
          f'{solves} solves  {seconds:.0f} s')
    print(f'production {base_production:.4e} -> {current_production:.4e}')
    print(f"matched error {benchmark.geometry_metrics(start, scene, spec)['maximum_matched_hausdorff_m']*1e3:.3f}"
          f" -> {geometry['maximum_matched_hausdorff_m']*1e3:.3f} mm, IoU {geometry['union_iou']:.4f}")
    for row in phase_report(state):
        print(f"  {row['component']} K={row['maximum_mode']} vs {row['truth']}: "
              f"{row['hausdorff_m']*1e3:7.3f} mm, phase-corrected "
              f"{row['phase_corrected_hausdorff_m']*1e3:7.3f} mm at {row['rotation_deg']:6.1f} deg")


if __name__ == '__main__':
    main()
