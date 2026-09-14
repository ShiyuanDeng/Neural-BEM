"""Stage 1: is a one-sided derivative estimate at the floor trustworthy?

Reads two saved final states and probes them directly. No topology search, no
optimizer, no state is advanced. Every number here is a property of the
derivative model, not of a reconstruction.

The declared step sequence and the agreement tolerance below were fixed in the
contract before this ran.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from sdf_inverse.radial_topology import (
    component_radius_floor, evaluate_multiradial_objective, multiradial_geometry_admissible,
)
from sdf_inverse.topology_controller import TopologyControllerConfig, _optimizer_config
from sdf_inverse.geometry import OrderedSDFGeometryError

SOURCE = ROOT / 'results/validation/topology/TOP-007-20260911-refined-feasibility'
# Predeclared: the configured step, halved and doubled. Reducing h indefinitely
# is not evidence and is not done.
STEP_FACTORS = (0.5, 1.0, 2.0)
# Predeclared: two estimates of the same column agree if their relative L2
# difference is at most this. Generous on purpose -- the question is whether a
# one-sided column is usable in a least-squares model, not whether it matches a
# central one to plotting accuracy.
AGREEMENT_TOLERANCE = 0.25
# Pinned by the constraint, and an interior control with no active constraint.
STATES = (('far-ellipse-star', 'pinned'), ('far-two-stars', 'interior control'))


def relative_difference(a, b):
    scale = max(float(np.linalg.norm(a)), float(np.linalg.norm(b)))
    return float(np.linalg.norm(a - b) / scale) if scale > 0 else 0.0


def main():
    spec = benchmark.read(HERE / 'scene_spec.json')
    solve = driver.baseline.iteration01_solve_config()
    production = driver.baseline._geometry_config(64)
    refined = driver.baseline._geometry_config(128)
    config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True,
                                      feasible_fd_jacobian=True)
    scenes = {scene['id']: scene for scene in spec['scenes']}
    records = []

    for scene_id, role in STATES:
        saved = benchmark.read(SOURCE / 'runs' / 'G' / scene_id / 'metrics.json')
        state = driver.deserialize_state(saved['final_state'])
        training, _ = benchmark.shared_data(HERE, scenes[scene_id], spec)
        basis = state.gauge_tangent_basis()
        steps = _optimizer_config(state, config).resolved_finite_difference_steps(
            state.parameter_count)
        sizes = np.sqrt((basis * basis) @ (steps * steps))
        base = evaluate_multiradial_objective(state, training, production, solve_config=solve)

        def probe(step):
            """One side: its verdict, and its residual when the verdict is ok."""
            try:
                trial = state.incremented(step).polar_angle_gauge_fixed()[0]
            except (ValueError, OrderedSDFGeometryError):
                return 'retract_failed', None
            if any(component_radius_floor(c) < config.minimum_component_radius_m
                   for c in trial.components):
                return 'radius_floor', None
            if not multiradial_geometry_admissible(trial, production, solve_config=solve):
                return 'production_inadmissible', None
            if not multiradial_geometry_admissible(trial, refined, solve_config=solve):
                return 'refined_inadmissible', None
            return 'ok', evaluate_multiradial_objective(
                trial, training, production, solve_config=solve).residual

        for index, (direction, size) in enumerate(zip(basis, sizes)):
            estimates = {}
            row = dict(scene=scene_id, role=role, direction=index, sides={}, columns={})
            for factor in STEP_FACTORS:
                step_size = float(size * factor)
                plus_verdict, plus = probe(step_size * direction)
                minus_verdict, minus = probe(-step_size * direction)
                entry = dict(step_m=step_size, plus=plus_verdict, minus=minus_verdict)
                columns = {}
                if plus is not None:
                    columns['forward'] = (plus - base.residual) / step_size
                if minus is not None:
                    columns['backward'] = (base.residual - minus) / step_size
                if plus is not None and minus is not None:
                    columns['central'] = (plus - minus) / (2.0 * step_size)
                # What the optimizer would actually use at this step.
                entry['stencil'] = ('central' if 'central' in columns else
                                    'forward' if 'forward' in columns else
                                    'backward' if 'backward' in columns else 'unresolved')
                entry['norm'] = (float(np.linalg.norm(columns[entry['stencil']]))
                                 if entry['stencil'] != 'unresolved' else None)
                # At an unconstrained point all three exist, so the one-sided
                # penalty can be measured directly rather than assumed.
                if 'central' in columns:
                    entry['forward_vs_central'] = relative_difference(
                        columns['forward'], columns['central'])
                    entry['backward_vs_central'] = relative_difference(
                        columns['backward'], columns['central'])
                row['sides'][f'{factor:g}h'] = entry
                if entry['stencil'] != 'unresolved':
                    estimates[factor] = columns[entry['stencil']]
            # Stability across the declared sequence, using what the optimizer
            # would use at each step.
            row['stability'] = {
                f'{a:g}h_vs_{b:g}h': relative_difference(estimates[a], estimates[b])
                for a, b in ((0.5, 1.0), (1.0, 2.0))
                if a in estimates and b in estimates}
            row['stencils'] = [row['sides'][f'{f:g}h']['stencil'] for f in STEP_FACTORS]
            records.append(row)
            print(json.dumps(dict(scene=scene_id, direction=index, stencils=row['stencils'],
                                  stability=row['stability'])), flush=True)

    driver.write_json(HERE / 'stage1_derivative_probe.json', dict(
        step_factors=list(STEP_FACTORS), agreement_tolerance=AGREEMENT_TOLERANCE,
        source_bundle=str(SOURCE.relative_to(ROOT)), records=records))
    summarize(records)


def summarize(records):
    print('\n=== stage 1 ===')
    for scene_id, role in STATES:
        rows = [r for r in records if r['scene'] == scene_id]
        one_sided = [r for r in rows if 'central' not in r['stencils']]
        unresolved = [r for r in rows if 'unresolved' in r['stencils']]
        stability = [v for r in rows for v in r['stability'].values()]
        penalties = [e[k] for r in rows for e in r['sides'].values()
                     for k in ('forward_vs_central', 'backward_vs_central') if k in e]
        print(f'{scene_id} ({role}): {len(rows)} directions, '
              f'{len(one_sided)} one-sided, {len(unresolved)} with an unresolved step')
        if stability:
            print(f'  stability across the declared sequence: max {max(stability):.6f}, '
                  f'median {np.median(stability):.6f} (tolerance {AGREEMENT_TOLERANCE})')
        if penalties:
            print(f'  one-sided vs central where both exist: max {max(penalties):.6f}, '
                  f'median {np.median(penalties):.6f}')
        worst = max(stability) if stability else 0.0
        print(f'  verdict: {"STABLE" if worst <= AGREEMENT_TOLERANCE else "NOT STABLE"}')


if __name__ == '__main__':
    main()
