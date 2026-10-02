"""Check that the TOP009 finite-path remainder is not normal-basis truncation.

Run with ``python -m experiments.atlas.review_top009_tangent --output NEW.json``.
This performs one full reciprocal solve and four centered path solves.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from .top009_projection import SAVED, SPEC, driver, benchmark, component_parameterization
from .top009_path import path_curves
from .run_jacobian_spectrum import ROOT, solve, jacobian, execution, write_json


class PathNormalVelocity:
    """Untruncated normal component of the physical-angle interpolation velocity."""
    def __init__(self, reference, endpoint):
        self.reference, self.endpoint = reference, endpoint

    def values(self, parameters):
        before = self.reference.evaluate(parameters)
        after = self.endpoint.evaluate(parameters)
        tangent = before.first_derivatives / np.linalg.norm(before.first_derivatives, axis=1)[:, None]
        normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
        return np.sum((after.points - before.points) * normal, axis=1)[:, None]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--projection-bundle', type=Path,
        default=ROOT / 'results/atlas/top009-polar-20261002/reconstruction_f0.5_M40.npz')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new audit output file.')
    saved, spec = json.loads(SAVED.read_text()), json.loads(SPEC.read_text())
    scene = next(s for s in spec['scenes'] if s['id'] == saved['scene'])
    state = driver.deserialize_state(saved['final_state'])
    reference = tuple(component_parameterization(c) for c in state.components)
    truth_by_id = {c.component_id: c for c in benchmark.truth_curves(scene)}
    matches = {r['recovered_component']: r['truth_component'] for r in saved['final_geometry']['matched_components']}
    truth = tuple(truth_by_id[matches[c.component_id]] for c in state.components)
    problem = driver.baseline._problem(np.array(spec['training_frequencies_hz']), acquisition=spec.get('acquisition'))
    options = dict(epsr=problem.interior.epsr, exterior_epsr=problem.exterior.epsr,
        sources=problem.source_points, receivers=problem.receiver_points,
        strength=complex(np.asarray(problem.source_strengths).reshape(-1)[0]))
    at = path_curves(reference, truth)
    with execution(device='cpu'):
        base = solve(reference, .5, nodes=512, **options)
        full = jacobian(base, tuple(PathNormalVelocity(p, q) for p, q in zip(reference, at(1))))
        ids = np.arange(len(problem.source_points))
        full = np.sum(full[ids, ids], axis=1)
        with np.load(args.projection_bundle) as bundle:
            truncated, actual = bundle['linearized_difference'], bundle['actual_field_difference']
        steps = []
        for step in [1e-3, 3e-4]:
            plus = np.diag(solve(at(step), .5, nodes=256, **options).Y)
            minus = np.diag(solve(at(-step), .5, nodes=256, **options).Y)
            fd = (plus - minus) / (2 * step)
            steps.append(dict(step=step, full_tangent_fd_relative=float(np.linalg.norm(full - fd) / np.linalg.norm(full))))
    result = dict(full_tangent_norm=float(np.linalg.norm(full)),
        truncated_tangent_norm=float(np.linalg.norm(truncated)),
        relative_truncation_error=float(np.linalg.norm(full - truncated) / np.linalg.norm(full)),
        full_tangent_vs_finite_path_remainder=float(np.linalg.norm(full - actual) / np.linalg.norm(actual)),
        fd_checks=steps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
