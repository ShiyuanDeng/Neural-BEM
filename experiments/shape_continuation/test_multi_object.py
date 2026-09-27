"""Coupled physics, component isolation and physically scaled information."""
from dataclasses import replace

import numpy as np
import pytest

from .forward import solve, shape_jacobian
from .geometry import FourierCurve
from .multi_object import MultiCurve, MultiUpdate, conditional_information
from .test_lm_backend import acquisition
from .updates import BorgesUpdate


def pair():
    update = BorgesUpdate(.05, projection_tolerance=1e-5)
    curves = tuple(update.regauge(FourierCurve.circle(r, c), 16)[0]
                   for r, c in ((.6, -1.1), (.5, 1.1)))
    return MultiCurve(curves, ("left", "right")), MultiUpdate(update)


def test_single_component_equivalence_and_paired_only_selection():
    scene, _ = pair()
    scan = acquisition(8)
    curve = scene.components[0]
    single = solve(curve, 1.3, .4, scan, 96)
    coupled = solve(MultiCurve((curve,), ("left",)), 1.3, .4, scan, 96)
    np.testing.assert_allclose(single.prediction, coupled.prediction, rtol=1e-12, atol=1e-14)
    full = solve(scene, 1.3, .4, replace(scan, paired=False), 96)
    paired = solve(scene, 1.3, .4, scan, 96)
    np.testing.assert_allclose(paired.prediction, np.diag(full.prediction), rtol=1e-13)


def test_component_permutation_and_complete_trial_derivatives():
    scene, update = pair()
    scan = acquisition(8)
    base = solve(scene, 1.3, .4, scan, 128)
    reverse = MultiCurve(scene.components[::-1], scene.ids[::-1])
    np.testing.assert_allclose(solve(reverse, 1.3, .4, scan, 128).prediction,
                               base.prediction, rtol=1e-12, atol=1e-14)
    space = update.prepare(scene, 2, 16)
    jac = shape_jacobian(base, update.velocities(space, base.curve))
    for active in ((0,), (1,), (0, 1)):
        direction = np.zeros(10)
        for j in active:
            direction[j * 5:(j + 1) * 5] = [.1, .4, -.3, .2, .1]
        eps = 1e-7
        predictions = [solve(update.trial(space, sign * eps * direction)[0],
                             1.3, .4, scan, 128).prediction for sign in (1, -1)]
        fd = (predictions[0] - predictions[1]) / (2 * eps)
        assert np.linalg.norm(fd - jac @ direction) / np.linalg.norm(fd) < 1e-5


def test_freezing_keeps_geometry_but_not_scattering_and_rejects_overlap():
    scene, wrapper = pair()
    update = MultiUpdate(wrapper.base, active=(1,))
    space = update.prepare(scene, 1, 16)
    candidate, _ = update.trial(space, np.array([1e-4, 0., 0.]))
    np.testing.assert_array_equal(candidate.components[0].coefficients, scene.components[0].coefficients)
    base = solve(scene, 1.3, .4, acquisition(8), 96)
    alone = solve(scene.components[1], 1.3, .4, acquisition(8), 96)
    assert np.linalg.norm(base.prediction - alone.prediction) > 1e-4
    overlapping = MultiCurve((scene.components[0], scene.components[0]), scene.ids)
    with pytest.raises(ValueError):
        solve(overlapping, 1.3, .4, acquisition(8), 96)
    with pytest.raises(ValueError):
        MultiCurve(scene.components, ("same", "same"))


def test_conditional_information_projection_identity_and_covariance():
    rng = np.random.default_rng(47)
    j1 = rng.normal(size=(30, 5))
    j2 = rng.normal(size=(30, 4))
    g1, g2 = np.diag([1., 2., 3., 4., 5.]), np.eye(4)
    result = conditional_information((j1, j2), (g1, g2))
    x = rng.normal(size=5)
    a = j1 / np.sqrt(np.diag(g1))
    b = -np.linalg.lstsq(j2, a @ x, rcond=1e-10)[0]
    np.testing.assert_allclose(x @ result[0]["conditional_gram"] @ x,
                               np.linalg.norm(a @ x + j2 @ b)**2, rtol=1e-12)
    assert np.linalg.eigvalsh(a.T @ a - result[0]["conditional_gram"]).min() > -1e-11
    scale = np.diag([2., .3, 4., .7, 5.])
    changed = conditional_information((j1 @ scale, j2), (scale.T @ g1 @ scale, g2))
    np.testing.assert_allclose(result[0]["conditional_singular_values"],
                               changed[0]["conditional_singular_values"], rtol=1e-12)
