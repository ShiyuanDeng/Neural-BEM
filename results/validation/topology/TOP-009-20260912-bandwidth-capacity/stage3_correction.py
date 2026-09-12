"""Correction to the stage-2 reading: is the climb overfitting, or stuck?

Stage 2 recorded that training loss fell 248x while boundary error, IoU and
holdout error all worsened, and that was first read as overfitting on an
under-determined acquisition. This script tests that reading directly and
refutes it. Four measurements, none of which needs a new inversion:

1. What the objective is at the *true* geometry. If the truth fits far better
   than the climb's answer, the data determines the shape and the optimizer is
   in a local minimum -- the opposite of an acquisition limit.
2. Whether the mis-fit is rotational phase, by minimising boundary error over
   rigid rotations of each reconstructed component.
3. Aggregate shape quality -- perimeter, area, isoperimetric ratio -- which is
   blind to phase where matched Hausdorff and IoU are not.
4. Whether the ladder actually finished, or stopped on its declared solve cap.
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
from sdf_inverse import MultiRadialFourierState
from sdf_inverse.curve_updates import fit_cartesian_fourier_curve_state
from sdf_inverse.radial_topology import (
    _minimum_polygon_distance, evaluate_multiradial_objective,
)
from sdf_inverse.topology_controller import component_parameterization

DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
CLIMB = HERE / 'stage2_climb.json'
SCENE = 'far-two-stars'
SAMPLES = 512
TRUTH_FIT_MODES = 9


def hausdorff(a, b):
    return float(max(_minimum_polygon_distance(a, b).max(),
                     _minimum_polygon_distance(b, a).max()))


def rotated(points, angle):
    center = points.mean(axis=0)
    rotation = np.array([[np.cos(angle), -np.sin(angle)],
                         [np.sin(angle), np.cos(angle)]])
    return (points - center) @ rotation.T + center


def shape_properties(points):
    edges = np.diff(np.vstack([points, points[:1]]), axis=0)
    perimeter = float(np.linalg.norm(edges, axis=1).sum())
    x, y = points[:, 0], points[:, 1]
    area = float(abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)) / 2)
    return dict(perimeter_m=perimeter, area_m2=area,
                isoperimetric_ratio=perimeter**2 / (4 * np.pi * area))


def main():
    spec = benchmark.read(DATA / 'scene_spec.json')
    scene = {s['id']: s for s in spec['scenes']}[SCENE]
    training, _ = benchmark.shared_data(DATA, scene, spec)
    solve = driver.baseline.iteration01_solve_config()
    production = driver.baseline._geometry_config(spec['production_nodes'])
    climb = benchmark.read(CLIMB)
    arm = [a for a in climb['arms'] if a['arm'] == 'promotion'][0]
    final = driver.deserialize_state(arm['final_state'])

    # 1. The objective at the true geometry, in the reconstruction's own chart.
    components = []
    for curve in benchmark.truth_curves(scene):
        points = curve.discretize(4096).points
        components.append(fit_cartesian_fourier_curve_state(
            points, maximum_mode=TRUTH_FIT_MODES, center=points.mean(axis=0),
            component_id=curve.component_id))
    truth_state = MultiRadialFourierState(tuple(components)).polar_angle_gauge_fixed()[0]
    truth_evaluation = evaluate_multiradial_objective(
        truth_state, training, production, solve_config=solve)

    # 2 and 3. Phase, and phase-blind shape quality.
    truth_points = {c.component_id: c.discretize(SAMPLES).points
                    for c in benchmark.truth_curves(scene)}
    angles = np.linspace(0.0, 2.0 * np.pi, 181)
    pairings = []
    for component in final.components:
        points = component_parameterization(component).discretize(SAMPLES).points
        for truth_id, target in truth_points.items():
            best = min((hausdorff(rotated(points, a), target), float(a)) for a in angles)
            pairings.append(dict(
                component=component.component_id, maximum_mode=component.maximum_mode,
                truth=truth_id, hausdorff_m=hausdorff(points, target),
                best_rotated_hausdorff_m=best[0], best_rotation_deg=float(np.degrees(best[1]))))

    shapes = dict(
        truth={c.component_id: shape_properties(c.discretize(4096).points)
               for c in benchmark.truth_curves(scene)},
        final={c.component_id: shape_properties(
            component_parameterization(c).discretize(4096).points)
            for c in final.components})

    record = dict(
        scene=SCENE, data_bundle=str(DATA.relative_to(ROOT)),
        truth_fit_modes=TRUTH_FIT_MODES,
        truth_production_loss=float(truth_evaluation.loss),
        truth_relative_l2_error=float(truth_evaluation.relative_l2_error),
        start_production_loss=climb['start_production_loss'],
        final_production_loss=arm['production_loss'],
        final_over_truth_loss_ratio=float(arm['production_loss'] / truth_evaluation.loss),
        ladder_stop_reason=arm['stop_reason'],
        ladder_finished=arm['stop_reason'] != 'solve_cap',
        solves_used=arm['solves'], solve_cap=climb['solve_cap'],
        final_modes=arm['final_modes'],
        # A radial m-lobe harmonic needs Cartesian bandwidth m + 1.
        bandwidth_required={'truth.star5': 6, 'truth.star7': 8},
        pairings=pairings, shape_properties=shapes)
    driver.write_json(HERE / 'stage3_correction.json', record)

    print('=== what the data can actually do ===')
    print(f"truth geometry      loss {record['truth_production_loss']:.4e}  "
          f"rel_l2 {record['truth_relative_l2_error']:.4e}")
    print(f"climb start [1, 1]  loss {record['start_production_loss']:.4e}")
    print(f"climb final {record['final_modes']}  loss {record['final_production_loss']:.4e}  "
          f"= {record['final_over_truth_loss_ratio']:.0f}x worse than the truth")
    print(f"\nladder finished: {record['ladder_finished']} "
          f"({record['solves_used']} solves against a {record['solve_cap']} cap)")
    print('\n=== phase ===')
    for p in pairings:
        print(f"  {p['component']} K={p['maximum_mode']} vs {p['truth']}: "
              f"{p['hausdorff_m']*1e3:8.3f} mm, best over rotation "
              f"{p['best_rotated_hausdorff_m']*1e3:8.3f} mm at {p['best_rotation_deg']:6.1f} deg")
    print('\n=== phase-blind shape quality ===')
    for group, entries in shapes.items():
        for name, value in entries.items():
            print(f"  {group:>5s} {name:<14s} perimeter {value['perimeter_m']*1e3:7.2f} mm  "
                  f"area {value['area_m2']*1e6:7.1f} mm2  "
                  f"isoperimetric {value['isoperimetric_ratio']:.4f}")


if __name__ == '__main__':
    main()
