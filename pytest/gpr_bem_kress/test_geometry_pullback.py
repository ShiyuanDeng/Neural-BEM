"""Reverse Kress covectors agree with analytic jets and rebuilt objectives."""

from dataclasses import replace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from gpr_bem_kress import (
    KressSolveConfig, Material, MullerAssemblyConfig,
    solve_kress_tmz_total_field_batch,
)
from gpr_bem_kress.geometry_pullback import build_kress_geometry_pullback
from gpr_bem_kress.shape_derivative import KressDirection, build_paired_objective_adjoint
from ordered_boundary import PeriodicCurve2D


def _curve(parameter=0.0, period=2*np.pi, count=24):
    theta = np.arange(count) * 2*np.pi/count
    alpha = 2*np.pi/period
    jets, directions = [], []
    for order in range(4):
        angle = theta + order*np.pi/2
        mode3 = 3*theta + order*np.pi/2
        base = alpha**order * np.column_stack((0.056*np.cos(angle), 0.045*np.sin(angle)))
        base += (3*alpha)**order * np.column_stack((0.002*np.cos(mode3), 0.001*np.sin(mode3)))
        direction = alpha**order * np.column_stack((0.009*np.cos(angle), -0.004*np.sin(angle)))
        direction += (3*alpha)**order * np.column_stack((0.001*np.sin(mode3), -0.002*np.cos(mode3)))
        if order == 0:
            direction += [0.006, -0.004]
        jets.append(base + parameter*direction)
        directions.append(direction)
    return (PeriodicCurve2D("pullback", np.arange(count)*period/count, *jets, period=period),
            KressDirection(*directions))


def _solve(parameter=0.0, *, near=0.75, period=2*np.pi, frequency=0.9e9, interior=4.2):
    curve, _ = _curve(parameter, period)
    return solve_kress_tmz_total_field_batch(
        curve, [[0.27, 0.02], [-0.24, 0.11]],
        [[0.04, 0.29], [-0.17, -0.25], [0.22, -0.19]],
        2*np.pi*frequency, [1+0.2j, -0.4+0.7j],
        exterior=Material(2.0), interior=Material(interior),
        eps0=8.8541878128e-12, mu0=4e-7*np.pi,
        config=KressSolveConfig(
            assembly=MullerAssemblyConfig(near_argument=near, series_terms=24, measure_overlap=False),
            minimum_clearance_in_weights=0.0,
        ),
    )


def _objective(bases, observable="scattered"):
    rng = np.random.default_rng(321)
    count = len(bases)
    observed = 0.02*(rng.normal(size=(4, count)) + 1j*rng.normal(size=(4, count)))
    transform = rng.normal(size=(9, 8*count))
    return build_paired_objective_adjoint(
        bases, observed, [0, 1, 0, 0], [2, 1, 2, 0],
        residual_transform=transform, observable=observable,
    )


@pytest.mark.parametrize("near", [0.04, 0.75, 8.0])
@pytest.mark.parametrize("observable", ["scattered", "total"])
def test_reverse_matches_independent_analytic_jets_without_additional_solve(near, observable, monkeypatch):
    objective = _objective([_solve(near=near, frequency=f) for f in (0.7e9, 1.2e9)], observable)
    rng = np.random.default_rng(673)
    # Independent point/first directions test both covectors, including normal
    # and speed variation; coherent construction is imposed by the caller.
    direction = KressDirection(0.01*rng.normal(size=(24, 2)), 0.03*rng.normal(size=(24, 2)))
    expected = objective.directional_derivative(direction)
    def unexpected_solve(*args, **kwargs):
        raise AssertionError("Pullback must reuse the supplied adjoint and forward states.")
    monkeypatch.setattr(np.linalg, "solve", unexpected_solve)
    monkeypatch.setattr(torch.linalg, "solve", unexpected_solve)
    pullback = build_kress_geometry_pullback(objective)
    actual = pullback.contract(direction.points, direction.first_derivatives)
    np.testing.assert_allclose(actual, expected, rtol=2e-10, atol=2e-12)
    assert pullback.diagnostics["reverse_pass_count"] == 2
    for key in ("adjoint_solve_count", "tangent_solve_count", "finite_difference_probes"):
        assert pullback.diagnostics[key] == 0
    for diagnostics in pullback.diagnostics["frequency_diagnostics"]:
        for key, value in diagnostics.items():
            if key.startswith("primal_"):
                assert value < 1e-12
    assert not pullback.points.flags.writeable
    assert not pullback.first_derivatives.flags.writeable


@pytest.mark.parametrize("period", [1.0, 2*np.pi])
@pytest.mark.parametrize("interior", [2.0, 4.2])
def test_coherent_reverse_agrees_with_rebuilt_production_objective(period, interior):
    base = _solve(period=period, interior=interior)
    objective = _objective([base])
    pullback = build_kress_geometry_pullback(objective)
    _, direction = _curve(period=period)
    actual = pullback.contract(direction.points, direction.first_derivatives)
    step = 2e-5
    high = _objective([_solve(step, period=period, interior=interior)]).loss
    low = _objective([_solve(-step, period=period, interior=interior)]).loss
    np.testing.assert_allclose(actual, (high-low)/(2*step), rtol=2e-7, atol=3e-12)


def test_pullback_rejects_drift_mismatched_geometry_and_invalid_direction():
    base = _solve()
    objective = _objective([base])
    stale = replace(base, right_hand_side=base.right_hand_side*(1+1e-6))
    with pytest.raises(ValueError, match="right_hand_side no longer matches"):
        build_kress_geometry_pullback(replace(objective, base_results=(stale,)))
    with pytest.raises(ValueError, match="identical native geometry"):
        build_kress_geometry_pullback(_objective([base, _solve(1e-4)]))
    pullback = build_kress_geometry_pullback(objective)
    with pytest.raises(ValueError, match="shape"):
        pullback.contract(np.zeros((12, 2)), np.zeros((24, 2)))
    with pytest.raises(ValueError, match="real-valued"):
        pullback.contract(np.zeros((24, 2), dtype=complex), np.zeros((24, 2)))


def test_zero_residual_weights_return_zero_covectors():
    base = _solve()
    objective = build_paired_objective_adjoint(
        [base], np.zeros((1, 1)), [0], [0], residual_transform=np.zeros((1, 2)),
    )
    pullback = build_kress_geometry_pullback(objective)
    np.testing.assert_array_equal(pullback.points, 0.0)
    np.testing.assert_array_equal(pullback.first_derivatives, 0.0)
