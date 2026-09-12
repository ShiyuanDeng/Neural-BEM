"""Stage 1: are the directions a promotion adds observable, and do they explain
residual the existing columns cannot?

Reads saved final states and probes them rung by rung. No optimizer, no topology
search, no state is advanced. Every number is a property of the approximation
space and the data, not of a reconstruction.

The ladder, the thresholds and the two states were fixed in the contract before
this ran.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path('/home/drdeng/Neural_SDF_BEM_AD')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from sdf_inverse import MultiRadialFourierState
from sdf_inverse.radial_topology import (
    component_radius_floor, evaluate_multiradial_objective, multiradial_geometry_admissible,
)
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, _optimizer_config, chart_contour_modes,
    component_parameterization, next_bandwidth_rung, zero_padded_component,
)
from sdf_inverse.geometry import OrderedSDFGeometryError

# Observations and saved states come from the qualified TOP-008 bundle; they are
# byte-identical to TOP-007's and TOP-006's.
DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
ARM = 'H'
# Predeclared. A rung's new directions count as observable only if their columns
# are stable to this relative difference between h and h/2 -- the same tolerance
# TOP-008 stage 1 declared -- and if they explain at least this fraction of the
# residual norm beyond the span the existing columns already reach.
STABILITY_TOLERANCE = 0.25
BEYOND_SPAN_FLOOR = 1.0e-3
# The stalled circular case, and a control whose truth really is circular.
STATES = (('far-two-stars', 'stalled, truth is two stars'),
          ('far-two-circles', 'control, truth is two circles'))


def projected_fraction(columns, residual):
    """Fraction of the residual norm reachable inside the span of ``columns``."""
    if not columns:
        return 0.0
    matrix = np.column_stack(columns)
    basis, singular, _ = np.linalg.svd(matrix, full_matrices=False)
    keep = singular > singular[0] * 1.0e-10 if singular[0] > 0 else singular > 0
    basis = basis[:, keep]
    return float(np.linalg.norm(basis.T @ residual) / np.linalg.norm(residual))


def main(output):
    spec = benchmark.read(DATA / 'scene_spec.json')
    solve = driver.baseline.iteration01_solve_config()
    production = driver.baseline._geometry_config(spec['production_nodes'])
    refined = driver.baseline._geometry_config(spec['refined_nodes'])
    config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True,
                                      feasible_fd_jacobian=True, bandwidth_promotion=True)
    cap = chart_contour_modes(config)
    scenes = {s['id']: s for s in spec['scenes']}
    records = []

    def jacobian(state, training, factor=1.0):
        """The optimizer's own stencil: both sides, else the feasible one."""
        basis = state.gauge_tangent_basis()
        steps = _optimizer_config(state, config).resolved_finite_difference_steps(
            state.parameter_count)
        sizes = np.sqrt((basis * basis) @ (steps * steps)) * factor
        base = evaluate_multiradial_objective(state, training, production, solve_config=solve)

        def probe(step):
            try:
                trial = state.incremented(step).polar_angle_gauge_fixed()[0]
            except (ValueError, OrderedSDFGeometryError):
                return None
            if any(component_radius_floor(c) < config.minimum_component_radius_m
                   for c in trial.components):
                return None
            if not multiradial_geometry_admissible(trial, production, solve_config=solve):
                return None
            if not multiradial_geometry_admissible(trial, refined, solve_config=solve):
                return None
            return evaluate_multiradial_objective(
                trial, training, production, solve_config=solve).residual

        columns = []
        for direction, size in zip(basis, sizes):
            plus, minus = probe(size * direction), probe(-size * direction)
            if plus is not None and minus is not None:
                columns.append((plus - minus) / (2.0 * size))
            elif plus is not None:
                columns.append((plus - base.residual) / size)
            elif minus is not None:
                columns.append((base.residual - minus) / size)
            else:
                columns.append(np.zeros_like(base.residual))
        return columns, base

    for scene_id, role in STATES:
        scene = scenes[scene_id]
        training, _ = benchmark.shared_data(DATA, scene, spec)
        state = driver.deserialize_state(
            benchmark.read(DATA / 'runs' / ARM / scene_id / 'metrics.json')['final_state'])
        base_columns, base = jacobian(state, training)
        base_span = projected_fraction(base_columns, base.residual)
        print(f'=== {scene_id} ({role}): modes '
              f'{[c.maximum_mode for c in state.components]}, '
              f'{len(base_columns)} directions, residual explained {base_span:.6f}', flush=True)

        for index, component in enumerate(state.components):
            current = state
            while True:
                promoted_component = current.components[index]
                rung = next_bandwidth_rung(promoted_component, cap)
                if rung is None:
                    break
                padded = MultiRadialFourierState(
                    current.components[:index]
                    + (zero_padded_component(promoted_component, rung),)
                    + current.components[index + 1:])
                # Zero padding must move nothing. Asserted, not trusted.
                before = component_parameterization(promoted_component).discretize(2048).points
                after = component_parameterization(padded.components[index]).discretize(2048).points
                displacement = float(np.abs(after - before).max())
                columns, padded_base = jacobian(padded, training)
                half, _ = jacobian(padded, training, factor=0.5)
                objective_change = float(padded_base.loss - base.loss)
                span = projected_fraction(columns, padded_base.residual)
                previous_span = projected_fraction(base_columns, padded_base.residual)
                beyond = float(np.sqrt(max(0.0, span**2 - previous_span**2)))
                # The columns this rung added, identified by dimension growth.
                added = len(columns) - len(base_columns)
                new_norms = sorted(float(np.linalg.norm(c)) for c in columns)[:max(added, 1)]
                largest = max(float(np.linalg.norm(c)) for c in columns)
                stability = []
                for full, coarse in zip(columns, half):
                    scale = max(np.linalg.norm(full), np.linalg.norm(coarse))
                    if scale > 0:
                        stability.append(float(np.linalg.norm(full - coarse) / scale))
                record = dict(
                    scene=scene_id, role=role, component=promoted_component.component_id,
                    component_index=index, from_mode=promoted_component.maximum_mode,
                    to_mode=rung, directions=len(columns), directions_added=added,
                    padding_boundary_displacement_m=displacement,
                    padding_objective_change=objective_change,
                    residual_explained=span, residual_explained_by_existing=previous_span,
                    residual_explained_beyond_existing=beyond,
                    weakest_new_column_norm=min(new_norms), largest_column_norm=largest,
                    weakest_new_column_relative=min(new_norms) / largest if largest else 0.0,
                    worst_column_stability=max(stability) if stability else None,
                    observable=bool(beyond >= BEYOND_SPAN_FLOOR
                                    and (max(stability) if stability else 1.0) <= STABILITY_TOLERANCE))
                records.append(record)
                print(json.dumps({k: record[k] for k in (
                    'scene', 'component', 'to_mode', 'directions_added',
                    'residual_explained_beyond_existing', 'weakest_new_column_relative',
                    'worst_column_stability', 'observable')}), flush=True)
                current = padded

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    driver.write_json(Path(output), dict(
        data_bundle=str(DATA.relative_to(ROOT)), arm=ARM,
        stability_tolerance=STABILITY_TOLERANCE, beyond_span_floor=BEYOND_SPAN_FLOOR,
        records=records))
    summarize(records)


def summarize(records):
    print('\n=== stage 1 ===')
    for scene_id, role in STATES:
        rows = [r for r in records if r['scene'] == scene_id]
        if not rows:
            continue
        observable = [r for r in rows if r['observable']]
        worst_pad = max(r['padding_boundary_displacement_m'] for r in rows)
        print(f'{scene_id} ({role}): {len(rows)} rungs probed, '
              f'{len(observable)} with observable new directions')
        print(f'  zero padding moved the boundary by at most {worst_pad:.3e} m')
        print(f"  residual explained beyond the existing span: "
              f"max {max(r['residual_explained_beyond_existing'] for r in rows):.6f}, "
              f"floor {BEYOND_SPAN_FLOOR}")
        print(f"  weakest new column, relative to the largest: "
              f"min {min(r['weakest_new_column_relative'] for r in rows):.3e}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE / 'stage1_observability.json')
