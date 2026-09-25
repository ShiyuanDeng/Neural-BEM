"""Physical, rather than coefficient-only, checks for SC-036's finite paths."""
import numpy as np
import pytest

from .finite_paths import RayUpdate
from .geometry import FourierCurve, grid_size, normal_basis
from .updates import BorgesUpdate, UpdateRefused
from .test_lm_backend import observations, stage
from .lm_backend import BackendConfig, Ledger, Objective


def test_circle_paths_coincide_for_nonuniform_displacement():
    normal, ray = BorgesUpdate(.05, projection_tolerance=1e-5), RayUpdate(.05)
    curve, _ = normal.regauge(FourierCurve.circle(1.2, .2+.1j), 64)
    space = normal.prepare(curve, 3, 64)
    step = np.array([.001, .002, -.001, .0003, .0004, -.0002, .0001])
    a, b = normal.trial(space, step)[0], ray.trial(space, step)[0]
    assert np.max(np.abs(a.values(2048)-b.values(2048))) < 1e-12


def test_ray_has_same_normal_velocity_without_band_truncation():
    normal, ray = BorgesUpdate(.05, projection_tolerance=1e-5), RayUpdate(.05)
    curve, _ = normal.regauge(FourierCurve(np.array([.25, 0, 1.])), 64)
    space = normal.prepare(curve, 3, 64)
    nodes, z, direction, radius, cosine = ray.frame(space, 4096)
    h = normal_basis(nodes, 3) @ np.arange(1, 8) * .0001 / .05
    velocity = h / cosine * direction
    unit_normal = nodes.normals @ np.array([1, 1j])
    assert np.max(np.abs((velocity*np.conj(unit_normal)).real-h)) < 1e-15
    assert np.array_equal(normal.velocities(space, nodes), ray.velocities(space, nodes))
    assert np.max(np.abs(velocity-h*unit_normal)) > .01


def test_actual_ray_trial_field_derivative():
    update = RayUpdate(.05)
    curve, _ = update.regauge(FourierCurve(np.array([.25, 0, 1.1])), 64)
    obs = observations(FourierCurve.circle(1.05), (1.2,), .5)
    fit = stage(obs, modes=3, curve_modes=64, nodes=256)
    objective = Objective(fit, .5, BackendConfig(), Ledger())
    base = objective.production(curve, "test")
    space = update.prepare(curve, 3, 64)
    direction = np.arange(1, 8, dtype=float)
    direction /= np.linalg.norm(direction)
    analytic = objective.jacobian(base, update, space) @ direction
    eps = 1e-7
    plus = objective.production(update.trial(space, eps*direction)[0], "test").residual
    minus = objective.production(update.trial(space, -eps*direction)[0], "test").residual
    assert np.linalg.norm((plus-minus)/(2*eps)-analytic) / np.linalg.norm(analytic) < 1e-5


def test_nonstar_chart_is_explicit_and_optional_fallback_is_exact():
    from .atlas_cases import c_shape_curve
    normal, ray = BorgesUpdate(.05, projection_tolerance=1e-5), RayUpdate(.05)
    curve, _ = normal.regauge(c_shape_curve(), 192)
    space = normal.prepare(curve, 3, 192)
    step = np.array([1e-6, 0, 0, 0, 0, 0, 0])
    with pytest.raises(UpdateRefused, match="ray_chart_unavailable"):
        ray.trial(space, step)
    candidate, record = RayUpdate(.05, fallback=True).trial(space, step)
    assert record["finite_path"] == "normal_chart_fallback"
    assert np.array_equal(candidate.coefficients, normal.trial(space, step)[0].coefficients)


def test_crossing_centre_never_falls_back_to_another_path():
    ray = RayUpdate(.05, fallback=True)
    curve, _ = ray.regauge(FourierCurve.circle(), 32)
    space = ray.prepare(curve, 0, 32)
    with pytest.raises(UpdateRefused, match="nonpositive_ray_radius"):
        ray.trial(space, np.array([-.06]))
