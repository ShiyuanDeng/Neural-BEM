from dataclasses import replace

import numpy as np
import pytest

from .run import full_indicators, frozen, solve
from gpr_bem_kress import Material
from ordered_boundary import circle
from sdf_inverse import ComplexScatteredData
from sdf_inverse.radial_topology import evaluate_current_domain_topological_derivative


def test_full_matrix_td_matches_existing_cartesian_pair_expansion():
    """Independently check source/receiver orientation, strength and scaling."""
    problem = frozen.driver.baseline._problem(np.array([.5e9]))
    sources, receivers = problem.source_points[::6], problem.receiver_points[::6]
    strength = 2 + .5j
    base = solve((circle(center=(.51, .49), radius=.03),), .5,
        problem.interior.epsr, 64, sources, receivers,
        exterior_epsr=problem.exterior.epsr, strength=strength)
    ke = Material(problem.exterior.epsr).wavenumber(problem.angular_frequencies[0], problem.eps0, problem.mu0)
    ki = Material(problem.interior.epsr).wavenumber(problem.angular_frequencies[0], problem.eps0, problem.mu0)
    x, y = np.meshgrid(np.linspace(.45, .55, 5), np.linspace(.45, .55, 4))
    points = np.stack((x, y), axis=-1)
    _, actual = full_indicators(base.Y, sources, receivers, points, ke, ki, strength)
    expanded = replace(problem, source_points=np.repeat(sources, len(receivers), axis=0),
        receiver_points=np.tile(receivers, (len(sources), 1)), source_strengths=strength)
    data = ComplexScatteredData(expanded, base.Y.reshape(-1, 1))
    expected = evaluate_current_domain_topological_derivative(None, data, points.reshape(-1, 2)).values
    np.testing.assert_allclose(actual.ravel(), expected.ravel(), rtol=2e-12, atol=1e-12)


def test_frozen_paired_data_cannot_be_used_for_lsm(tmp_path):
    from .benchmark_adapter import initialize
    from experiments.exploratory_continuation.run import REFERENCE, ROOT
    spec = frozen.read(ROOT/'config/topology_scenes_v1.json')
    data, _ = frozen.shared_data(REFERENCE, spec['scenes'][0], spec)
    with pytest.raises(ValueError, match='full-matrix'):
        initialize(data, frozen.controller_config(spec, 'H'), method='lsm')
    destination = tmp_path/'ineligible'
    with pytest.raises(ValueError, match='full matrices'):
        frozen.prepare(destination, ROOT/'config/topology_scenes_v1.json', initializer='lsm')
    assert not destination.exists()
