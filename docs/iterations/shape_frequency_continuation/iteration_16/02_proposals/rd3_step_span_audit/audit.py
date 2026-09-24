"""RD-3: can each method's step space express the way back to the truth? Saved states only, zero solves.

EVALUATION ONLY (truth is the target of the diagnostic, never an optimizer input).
At every accepted stage-1 state, h = the signed move along the current normals that reaches the truth
(`atlas_survey` normal-ray construction). Its arclength-weighted L2 fraction captured by a 7-direction step
space is reported for
  * the hybrid's space: normal harmonics 0..3 in current arclength (`normal_basis`, M = 3);
  * SPD-L's space: the normal components of its 7 polar-gauge K4 directions (SPD-L states only).
Also: SC-029's M=2 first-band prefixes against M=3, in RD-2's out-of-band bending-energy measure.
Run from the repository root: PYTHONPATH=solvers:. python <this file>
"""
import json
from pathlib import Path
import sys

import numpy as np
from matplotlib.path import Path as Polygon

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import normal_basis
from experiments.shape_continuation.metrics import points_to_polygon_distance
from sdf_inverse.radial_topology import MultiRadialFourierState, gauge_normal_displacement_operator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'rd2_band_energy_audit'))
import audit as rd2  # noqa: E402

R0 = sc.ROOT / 'results/validation/shape_continuation/SC-029-atlas-strategies/runs'
SPDL = sc.ROOT / 'results/validation/shape_continuation/SC-034-spd-legacy-controls/runs/L'
N, L = 4096, sc.LENGTH


def ray_move(nodes, truth):
    """Signed move along each normal to the nearest truth crossing (closest-distance proxy if missed)."""
    p, n = nodes.points, nodes.normals
    polygon = np.column_stack((truth.real, truth.imag))
    edge = np.roll(polygon, -1, axis=0) - polygon
    closest = points_to_polygon_distance(p, polygon)
    proxy = np.where(Polygon(polygon).contains_points(p), closest, -closest)
    ray = np.full(len(p), np.nan)
    for start in range(0, len(p), 64):
        q, m = p[start:start + 64, None, :], n[start:start + 64, None, :]
        offset = polygon[None] - q
        den = m[..., 0] * edge[None, :, 1] - m[..., 1] * edge[None, :, 0]
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (offset[..., 0] * edge[None, :, 1] - offset[..., 1] * edge[None, :, 0]) / den
            u = (offset[..., 0] * m[..., 1] - offset[..., 1] * m[..., 0]) / den
        t = np.where((den != 0) & (u >= 0) & (u < 1), t, np.inf)
        best = t[np.arange(t.shape[0]), np.argmin(np.abs(t), axis=1)]
        ray[start:start + 64] = np.where(np.isfinite(best), best, np.nan)
    return np.where(np.isfinite(ray), ray, proxy)


def captured(h, columns, weights):
    gram = columns.T @ (weights[:, None] * columns)
    fit = columns @ np.linalg.lstsq(gram, columns.T @ (weights * h), rcond=None)[0]
    total = float(np.sum(weights * h ** 2))
    return 1.0 - float(np.sum(weights * (h - fit) ** 2)) / total if total > 0 else 1.0


def row(curve, truth, spd_state=None):
    nodes = curve.nodes(N)
    h, w = ray_move(nodes, truth), nodes.arc_length_weights
    out = dict(error_rms_mm=float(1e3 * L * np.sqrt(np.sum(w * h ** 2) / np.sum(w))),
               radius_mm=float(1e3 * L / np.max(np.abs(nodes.curvatures))),
               hybrid_span=captured(h, normal_basis(nodes, 3), w))
    if spd_state is not None:
        basis = spd_state.gauge_tangent_basis()
        columns = gauge_normal_displacement_operator(spd_state, basis, N) / L
        assert columns.shape[0] == N
        out['spd_span'] = captured(h, columns, w)
    return out


def truth_points(case):
    return ast.curve_from(json.loads((ast.source_folder(case) / 'truth.json').read_text())).values(8192)


def main():
    p = sc.spd_modules()[0].p
    result, lines = {}, []
    for case in ('peanut', 'kite', 'circle_to_c', 'circle_to_star'):
        truth = truth_points(case)
        hybrid = [row(ast.curve_from(item['coefficients']), truth) for item in
                  json.loads((R0 / 'baseline' / case / 'none' / 'stage_1_history.json').read_text())['history']]
        spd = []
        for line in (SPDL / case / 'stage_1' / 'trajectory.jsonl').read_text().splitlines():
            state = p.driver.deserialize_state(json.loads(line)['state'])
            curve = sc.from_cartesian(state.components[0])
            assert np.allclose(curve.values(N) * L + sc.CENTER, complex(1) * (
                p.boundary_points(state, N)[0] @ np.array([1, 1j])), atol=1e-9), 'sample alignment'
            spd.append(row(curve, truth, state))
        result[case] = dict(hybrid_r0=hybrid, spd_l=spd)
        fmt = lambda rows, key: ' '.join(f"{r[key]:.2f}" for r in rows)
        lines += [f"{case}", f"  hybrid R0  radius mm: {fmt(hybrid, 'radius_mm')}",
                  f"             error mm : {fmt(hybrid, 'error_rms_mm')}",
                  f"             own span : {fmt(hybrid, 'hybrid_span')}",
                  f"  SPD-L      radius mm: {fmt(spd, 'radius_mm')}",
                  f"             error mm : {fmt(spd, 'error_rms_mm')}",
                  f"             own span : {fmt(spd, 'spd_span')}",
                  f"        hybrid-type span: {fmt(spd, 'hybrid_span')}"]
    # SC-029: first band M=2 ('protect') against M=3 ('baseline'), RD-2 measure at the stage band.
    bands = dict(baseline=(3, 5, 7, 9), protect=(2, 5, 7, 9))
    strategy = {}
    for prefix in ('baseline', 'protect'):
        for case in ast.CASES:
            folder = R0 / prefix / case / 'none'
            stage_1 = [rd2.measure(ast.curve_from(i['coefficients']), bands[prefix][0]) for i in
                       json.loads((folder / 'stage_1_history.json').read_text())['history']]
            final = json.loads((folder / 'result.json').read_text())
            strategy[f'{prefix}:{case}'] = dict(stage_1_max_tail=max(r['tail'] for r in stage_1),
                stage_1_max_energy=max(r['energy_ratio'] for r in stage_1),
                stage_1_min_radius_mm=min(r['radius_mm'] for r in stage_1),
                final_rms_mm=final['score']['symmetric_rms_mm'] if 'score' in final else None)
    result['sc029_first_band'] = strategy
    lines.append('SC-029 first band (stage-1 max energy ratio, min radius mm -> final RMS mm)')
    for case in ast.CASES:
        a, b = strategy[f'baseline:{case}'], strategy[f'protect:{case}']
        lines.append(f"  {case:15s} M=3: {a['stage_1_max_energy']:.2f}, {a['stage_1_min_radius_mm']:.2f} -> {a['final_rms_mm']}"
                     f" | M=2: {b['stage_1_max_energy']:.2f}, {b['stage_1_min_radius_mm']:.2f} -> {b['final_rms_mm']}")
    (HERE / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    (HERE / 'audit.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
