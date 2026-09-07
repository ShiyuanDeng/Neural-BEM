"""Fixed-discretization tests of the actual Kress JVP and conjugate adjoint."""

from dataclasses import replace

import numpy as np
import pytest

from gpr_bem_kress import (
    KressSolveConfig, Material, MullerAssemblyConfig,
    solve_kress_tmz_total_field_batch,
)
from gpr_bem_kress.shape_derivative import (
    KressDirection, build_paired_objective_adjoint, linearize_kress_forward,
)
from ordered_boundary import PeriodicCurve2D


EPS0 = 8.8541878128e-12
MU0 = 4e-7 * np.pi
SOURCES = np.asarray([[0.27, 0.02], [-0.24, 0.11]])
RECEIVERS = np.asarray([[0.04, 0.29], [-0.17, -0.25], [0.22, -0.19]])
STRENGTHS = np.asarray([1.0 + 0.2j, -0.4 + 0.7j])


def _jets(count, period, *, direction=False):
    """Independent finite Fourier curve jets, without re-fit/discrete differencing."""
    theta = np.arange(count) * 2.0 * np.pi / count
    alpha = 2.0 * np.pi / period
    if direction:
        modes = ((1, (0.011, -0.003), (0.002, 0.006)),
                 (3, (0.002, 0.001), (-0.001, 0.0015)))
    else:
        modes = ((1, (0.052, 0.004), (-0.002, 0.046)),
                 (2, (0.003, 0.0), (0.0, -0.003)),
                 (4, (0.003, 0.0), (0.0, 0.003)))
    values = []
    for order in range(4):
        array = np.zeros((count, 2))
        for mode, cosine, sine in modes:
            angle = mode * theta + order * np.pi / 2.0
            array += (mode * alpha)**order * (
                np.cos(angle)[:, None] * cosine + np.sin(angle)[:, None] * sine
            )
        if direction and order == 0:
            array += [0.006, -0.003]
        values.append(array)
    return values


def _curve(count=32, period=2*np.pi, parameter=0.0, *, translation=False):
    values = _jets(count, period)
    direction = _jets(count, period, direction=True)
    if translation:
        direction = [np.broadcast_to([0.013, -0.009], (count, 2))] + [np.zeros((count, 2))]*3
    values = [v + parameter*d for v, d in zip(values, direction)]
    return PeriodicCurve2D("derivative-curve", np.arange(count)*period/count,
                           *values, period=period)


def _direction(count=32, period=2*np.pi, *, kind="mixed"):
    jets = _jets(count, period, direction=True)
    if kind == "translation":
        jets = [np.broadcast_to([0.013, -0.009], (count, 2))] + [np.zeros((count, 2))]*3
    if kind in ("material", "source"):
        jets = [None]*4
    return KressDirection(
        *jets,
        exterior_epsr=0.3 if kind in ("mixed", "material") else 0.0,
        interior_epsr=-0.7 if kind in ("mixed", "material") else 0.0,
        source_strengths=np.asarray([0.1-0.3j, 0.2+0.08j]) if kind in ("mixed", "source") else None,
    )


def _solve(parameter=0.0, *, count=32, period=2*np.pi, kind="mixed",
           exterior=2.0, interior=4.2, frequency=0.9e9, near=0.75, terms=24):
    direction = _direction(count, period, kind=kind)
    curve_parameter = 0.0 if kind in ("material", "source") else parameter
    curve = _curve(count, period, curve_parameter, translation=kind == "translation")
    strengths = STRENGTHS + parameter * (0.0 if direction.source_strengths is None else direction.source_strengths)
    return solve_kress_tmz_total_field_batch(
        curve, SOURCES, RECEIVERS, 2*np.pi*frequency, strengths,
        exterior=Material(exterior + parameter*direction.exterior_epsr),
        interior=Material(interior + parameter*direction.interior_epsr), eps0=EPS0, mu0=MU0,
        config=KressSolveConfig(
            assembly=MullerAssemblyConfig(near_argument=near, series_terms=terms, measure_overlap=False),
            minimum_clearance_in_weights=0.0,
        ),
    )


def _assert_close(actual, expected, *, rtol=2e-6, atol=2e-10):
    assert np.linalg.norm(actual-expected) <= atol + rtol*np.linalg.norm(expected)


@pytest.mark.parametrize("kind", ["geometry", "translation", "material", "source", "mixed"])
@pytest.mark.parametrize("near,terms", [(0.75, 24), (0.04, 8), (8.0, 24)])
def test_all_actual_operator_and_solved_prediction_jvps(kind, near, terms):
    options = dict(kind=kind, near=near, terms=terms)
    base = _solve(**options)
    derivative = linearize_kress_forward(base, _direction(kind=kind))
    step = 2e-5
    plus, minus = _solve(step, **options), _solve(-step, **options)
    comparisons = (
        (derivative.d_system_matrix, plus.system.system_matrix, minus.system.system_matrix),
        (derivative.d_right_hand_side, plus.right_hand_side, minus.right_hand_side),
        (derivative.d_receiver_matrix, plus.receiver_operator.state_rows, minus.receiver_operator.state_rows),
        (derivative.d_solution, plus.solution, minus.solution),
        (derivative.d_incident_receiver, plus.incident_receiver, minus.incident_receiver),
        (derivative.d_scattered_receiver, plus.scattered_receiver, minus.scattered_receiver),
        (derivative.d_total_receiver, plus.total_receiver, minus.total_receiver),
    )
    for index, (actual, high, low) in enumerate(comparisons):
        # Rigid translation has exactly zero dA; FD subtraction leaves an
        # O(eps*||A||/step) floor, checked separately from exact invariance below.
        atol = 1e-9 if kind == "translation" and index == 0 else 2e-10
        _assert_close(actual, (high-low)/(2*step), atol=atol)
    assert derivative.diagnostics["finite_difference_probes"] == 0
    assert derivative.diagnostics["tangent_solve_count"] == 1
    assert derivative.diagnostics["near_argument"] == near
    assert derivative.diagnostics["series_terms"] == terms
    for key, value in derivative.diagnostics.items():
        if key.startswith("primal_"):
            assert value < 1e-12
    if kind == "translation":
        np.testing.assert_array_equal(derivative.d_system_matrix, 0.0)
        assert np.linalg.norm(derivative.d_right_hand_side) > 0.0
        assert np.linalg.norm(derivative.d_receiver_matrix) > 0.0


def test_native_period_changes_neither_primal_nor_directional_physics():
    angular = _solve(period=2*np.pi)
    unit = _solve(period=1.0)
    ja = linearize_kress_forward(angular, _direction(period=2*np.pi))
    ju = linearize_kress_forward(unit, _direction(period=1.0))
    _assert_close(angular.system.system_matrix, unit.system.system_matrix, rtol=2e-14)
    for name in ("d_system_matrix", "d_right_hand_side", "d_receiver_matrix", "d_total_receiver"):
        _assert_close(getattr(ja, name), getattr(ju, name), rtol=2e-12)
    step = 2e-5
    high, low = _solve(step, period=1), _solve(-step, period=1)
    _assert_close(ju.d_total_receiver, (high.total_receiver-low.total_receiver)/(2*step))


def test_material_tangent_is_not_zeroed_by_zero_contrast_shortcut():
    base = _solve(kind="material", exterior=2.0, interior=2.0)
    jvp = linearize_kress_forward(base, _direction(kind="material"))
    assert jvp.diagnostics["zero_contrast_base"] is True
    assert np.linalg.norm(jvp.d_system_matrix) > 0.1
    step = 2e-5
    high = _solve(step, kind="material", exterior=2.0, interior=2.0)
    low = _solve(-step, kind="material", exterior=2.0, interior=2.0)
    _assert_close(jvp.d_system_matrix, (high.system.system_matrix-low.system.system_matrix)/(2*step))
    _assert_close(jvp.d_scattered_receiver, (high.scattered_receiver-low.scattered_receiver)/(2*step))
    geometry = linearize_kress_forward(base, _direction(kind="geometry"))
    np.testing.assert_array_equal(geometry.d_system_matrix, 0.0)
    # Do not force the discrete incident representation leak to zero.
    high = _solve(step, kind="geometry", exterior=2.0, interior=2.0)
    low = _solve(-step, kind="geometry", exterior=2.0, interior=2.0)
    _assert_close(geometry.d_scattered_receiver, (high.scattered_receiver-low.scattered_receiver)/(2*step))


@pytest.mark.parametrize("observable", ["scattered", "total"])
def test_conjugate_adjoint_repeated_selection_and_full_real_transform(observable):
    bases = [_solve(frequency=f) for f in (0.7e9, 1.2e9)]
    sources, receivers = [0, 1, 0, 1, 0], [2, 0, 2, 1, 0]
    rng = np.random.default_rng(912)
    observed = 0.02*(rng.normal(size=(5, 2)) + 1j*rng.normal(size=(5, 2)))
    observed[:, 1] = 0.0  # No hidden observed-normalization singularity.
    transform = rng.normal(size=(13, 20))
    transform[0] = 0.0
    objective = build_paired_objective_adjoint(
        bases, observed, sources, receivers, residual_transform=transform, observable=observable,
    )
    expected = np.column_stack([getattr(b, f"{observable}_receiver")[sources, receivers] for b in bases])
    np.testing.assert_array_equal(objective.prediction, expected)
    delta = expected-observed
    residual = transform @ np.concatenate([delta.real.ravel(), delta.imag.ravel()])
    np.testing.assert_allclose(objective.loss, 0.5*np.dot(residual, residual), rtol=1e-15)
    derivative = objective.directional_derivative(_direction())
    jvps = [linearize_kress_forward(base, _direction()) for base in bases]
    dz = np.column_stack([getattr(j, f"d_{observable}_receiver")[sources, receivers] for j in jvps])
    direct_contraction = np.dot(residual, transform @ np.concatenate([dz.real.ravel(), dz.imag.ravel()]))
    np.testing.assert_allclose(derivative, direct_contraction, rtol=1e-12, atol=1e-15)
    step = 2e-5
    losses = []
    for parameter in (step, -step):
        perturbed = [_solve(parameter, frequency=f) for f in (0.7e9, 1.2e9)]
        losses.append(build_paired_objective_adjoint(
            perturbed, observed, sources, receivers, residual_transform=transform, observable=observable,
        ).loss)
    np.testing.assert_allclose(derivative, (losses[0]-losses[1])/(2*step), rtol=2e-7, atol=1e-12)
    assert objective.diagnostics["adjoint_solve_count"] == 2
    assert objective.diagnostics["tangent_solve_count"] == 0
    for dual in objective.adjoints:
        assert not dual.flags.writeable


def test_zero_weight_frequency_and_per_frequency_directions():
    bases = [_solve(frequency=f) for f in (0.7e9, 1.2e9)]
    weights = np.diag([1, 0, 1, 0, 1, 0, 1, 0])
    objective = build_paired_objective_adjoint(bases, np.zeros((2, 2)), [0, 1], [1, 0], residual_transform=weights)
    directions = [_direction(), KressDirection(interior_epsr=10000)]
    result = objective.directional_derivative(directions)
    np.testing.assert_array_equal(objective.adjoints[1], 0.0)
    assert result == objective.directional_derivative([_direction(), KressDirection()])
    zero = build_paired_objective_adjoint(bases, np.zeros((2, 2)), [0, 1], [1, 0], residual_transform=np.zeros((3, 8)))
    assert zero.loss == zero.directional_derivative(directions) == 0.0


def test_invalid_directions_and_objectives_are_rejected():
    with pytest.raises(ValueError, match="supplied together"):
        KressDirection(points=np.zeros((32, 2)))
    with pytest.raises(ValueError, match="real-valued"):
        KressDirection(exterior_epsr=1j)
    base = _solve()
    with pytest.raises(ValueError, match="shape"):
        linearize_kress_forward(base, KressDirection(np.zeros((8, 2)), np.zeros((8, 2))))
    with pytest.raises(ValueError, match="one value per source"):
        linearize_kress_forward(base, KressDirection(source_strengths=[1, 2, 3]))
    with pytest.raises(ValueError, match="lossless"):
        linearize_kress_forward(replace(base, interior_material=Material(4.2, sigma=1)), KressDirection())
    with pytest.raises(ValueError, match="real-valued"):
        build_paired_objective_adjoint([base], np.zeros((1, 1)), [0], [0], residual_transform=np.eye(2)*1j)
    with pytest.raises(ValueError, match="integer"):
        build_paired_objective_adjoint([base], np.zeros((1, 1)), [0.0], [0])
    with pytest.raises(ValueError, match="outside"):
        build_paired_objective_adjoint([base], np.zeros((1, 1)), [2], [0])
    with pytest.raises(ValueError, match="integer range"):
        build_paired_objective_adjoint([base], np.zeros((1, 1)), np.asarray([2**64-1], dtype=np.uint64), [0])
    with pytest.raises(ValueError, match="no longer matches"):
        linearize_kress_forward(replace(base, right_hand_side=base.right_hand_side*2), _direction())


def test_primal_drift_guard_does_not_hide_small_strength_relative_errors():
    base = _solve()
    scale = 1e-7
    tiny = solve_kress_tmz_total_field_batch(
        base.system.geometry, SOURCES, RECEIVERS, base.system.angular_frequency,
        STRENGTHS*scale, exterior=base.exterior_material, interior=base.interior_material,
        eps0=EPS0, mu0=MU0, config=base.solve_config,
    )
    linearize_kress_forward(tiny, KressDirection())
    with pytest.raises(ValueError, match="right_hand_side no longer matches"):
        linearize_kress_forward(replace(tiny, right_hand_side=tiny.right_hand_side*(1+1e-6)), KressDirection())


def test_adjoint_contraction_reuses_build_solves_without_tangent_solves(monkeypatch):
    base = _solve()
    objective = build_paired_objective_adjoint([base], np.zeros((1, 1)), [0], [1])
    def unexpected_solve(*args, **kwargs):
        raise AssertionError("Directional contraction must not perform another solve.")
    monkeypatch.setattr(np.linalg, "solve", unexpected_solve)
    assert np.isfinite(objective.directional_derivative(_direction()))
