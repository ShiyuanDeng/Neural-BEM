"""SC-039's stored traces must rebuild the backend Jacobian in any coordinates."""
import numpy as np

from .forward import PointSourceAcquisition, shape_jacobian, solve
from .geometry import FourierCurve
from .test_lm_backend import observations
from .trajectory_atlas import cartesian_velocities, compute, jacobian, normal_velocities


def shot_arrays(curve, grids=(96, 192)):
    obs = observations(FourierCurve.circle(1.05), (1.2, 1.7), .5)
    arrays, record = compute(curve, grids, obs, .5)
    return arrays, record, obs


def test_contraction_matches_shape_jacobian_paired_and_full():
    curve = FourierCurve(np.array([.08j, .2, 0, 1.1, .05j]))  # modes -2..2: an off-centre, non-circular curve
    shot, record, obs = shot_arrays(curve)
    for f, o in enumerate(obs):
        state = solve(curve, o.wavenumber, .5, o.acquisition, 96)
        assert np.array_equal(np.diag(shot['prediction_96'][f]), state.prediction)
        for basis in (normal_velocities(shot, 96, 5), cartesian_velocities(shot, 96, 6)[0]):
            reference = shape_jacobian(state, basis)
            assert np.linalg.norm(jacobian(shot, f, 96, basis) - reference) < 1e-12 * np.linalg.norm(reference)
        full = PointSourceAcquisition(o.acquisition.sources, o.acquisition.receivers, o.acquisition.strength, paired=False)
        reference = shape_jacobian(solve(curve, o.wavenumber, .5, full, 96), normal_velocities(shot, 96, 3))
        stored = jacobian(shot, f, 96, normal_velocities(shot, 96, 3), paired=False)
        assert np.linalg.norm(stored - reference) < 1e-12 * np.linalg.norm(reference)
    assert record['forward_solves'] == 4 and len(record['paired_grid_discrepancy']) == 2


def test_cartesian_coefficients_on_a_circle_move_normal_harmonic_p_minus_1():
    """z = R e^{it}: Re c_p moves the boundary by cos((p-1)t), so p and 2-p coincide."""
    shot, _, _ = shot_arrays(FourierCurve.circle(1.0))
    velocities, orders = cartesian_velocities(shot, 96, 4)
    t, count = shot['parameters_96'], len(orders)
    for i, p in enumerate(orders):
        assert np.allclose(velocities[:, i] * shot['length_unit_m'], np.cos((p - 1) * t), atol=1e-12)
        mirror = list(orders).index(2 - p) if abs(2 - p) <= 4 else None
        if mirror is not None:
            assert np.allclose(velocities[:, i], velocities[:, mirror], atol=1e-12)
    rotation = velocities[:, count + list(orders).index(1)]  # Im c_1: a rigid rotation
    assert np.max(np.abs(rotation)) < 1e-12
