"""Geometry-only checks for SDF-constrained Fourier refinement."""

from __future__ import annotations

from dataclasses import replace
import numpy as np
import pytest
from types import SimpleNamespace

from ordered_boundary import BoundaryValidationConfig
from sdf_to_ordered_boundary import (
    ArcLengthConfig,
    CallableImplicitField2D,
    EllipseLevelSet,
    FrontendConfig,
    MethodBConfig,
    RadialFourierLevelSet,
    fit_method_b,
    prepare_single_component,
)
from sdf_to_ordered_boundary.method_c import (
    MethodCConfig,
    RefinementStage,
    RefinementWeights,
    _basis,
    _coefficient_matrix,
    _loss_and_gradient,
    _run_stage,
    fit_method_c,
)

import sdf_to_ordered_boundary.method_c as method_c_module


def _small_arc_length(sample_count: int) -> ArcLengthConfig:
    return ArcLengthConfig(
        dense_resolution=512,
        refit_sample_count=sample_count,
        validation_resolution=256,
    )


def _small_method_c(sample_count: int) -> MethodCConfig:
    return MethodCConfig(
        dense_sample_count=128,
        validation_sample_count=256,
        checkpoint_interval=4,
        stages=(
            RefinementStage(
                "attach",
                iterations=8,
                relative_learning_rate=8.0e-4,
                weights=RefinementWeights(
                    fidelity=1.0,
                    anchor=5.0e-2,
                    spectral=1.0e-9,
                ),
            ),
            RefinementStage(
                "regularize",
                iterations=6,
                relative_learning_rate=3.0e-4,
                weights=RefinementWeights(
                    fidelity=1.0,
                    anchor=2.0e-2,
                    speed=5.0e-3,
                    regularity=1.0e-2,
                ),
            ),
        ),
        final_stage=RefinementStage(
            "final",
            iterations=4,
            relative_learning_rate=1.0e-4,
            weights=RefinementWeights(fidelity=1.0, anchor=5.0e-2),
        ),
        arc_length=_small_arc_length(sample_count),
    )


def _fit_method_b(field, bounds, *, bandwidth: int = 8, sample_count: int = 96):
    frontend = prepare_single_component(
        field,
        FrontendConfig(
            bounds=bounds,
            grid_shape=(65, 65),
            projected_samples=sample_count,
        ),
    )
    method_b = fit_method_b(
        frontend,
        config=MethodBConfig(
            bandwidth=bandwidth,
            arclength=_small_arc_length(sample_count),
            validation=BoundaryValidationConfig(num_samples_per_component=256),
        ),
    )
    return frontend, method_b


def test_stage_restores_earlier_valid_checkpoint_after_later_invalid_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A numerically better invalid iterate must never replace valid geometry."""

    validated_matrices: list[np.ndarray] = []

    def fake_boundary_from_matrix(_template, matrix):
        return matrix.copy()

    def fake_validate(_field, candidate, *, config):
        del config
        validated_matrices.append(candidate.copy())
        valid = len(validated_matrices) < 3
        report = SimpleNamespace(valid=valid, issues=() if valid else ("synthetic fold",))
        return valid, report, {"synthetic_valid": valid}

    def fake_loss_and_gradient(matrix, **_kwargs):
        loss = -float(np.sum(matrix))
        return loss, -np.ones_like(matrix), {"total": loss}

    monkeypatch.setattr(
        method_c_module, "_boundary_from_matrix", fake_boundary_from_matrix
    )
    monkeypatch.setattr(method_c_module, "_validate_candidate", fake_validate)
    monkeypatch.setattr(
        method_c_module, "_loss_and_gradient", fake_loss_and_gradient
    )

    initial = np.zeros((2, 3), dtype=np.float64)
    history: list[dict] = []
    selected, selected_score = _run_stage(
        initial,
        template=None,
        field=None,
        stage=RefinementStage(
            "restore-valid",
            iterations=3,
            relative_learning_rate=1.0e-2,
            weights=RefinementWeights(fidelity=1.0),
        ),
        dense_basis=np.empty((0, 0)),
        dense_derivative_basis=np.empty((0, 0)),
        anchor_basis=np.empty((0, 0)),
        anchor_points=np.empty((0, 2)),
        geometry_scale=1.0,
        config=replace(_small_method_c(64), checkpoint_interval=1),
        normalized_fidelity=False,
        history=history,
    )

    assert len(validated_matrices) == 3  # initializer, valid step, invalid step
    np.testing.assert_allclose(selected, validated_matrices[1])
    assert selected_score == pytest.approx(-float(np.sum(validated_matrices[1])))
    checkpoint_results = [
        entry["checkpoint_result"]
        for entry in history
        if entry.get("checkpoint_result") is not None
    ]
    assert checkpoint_results[0]["valid"] is True
    assert checkpoint_results[0]["selected"] is True
    assert checkpoint_results[1]["valid"] is False
    assert checkpoint_results[1]["selected"] is False
    assert len(checkpoint_results) == 2  # optimization stops at the invalid checkpoint


@pytest.mark.parametrize(
    ("field", "bounds"),
    (
        (
            EllipseLevelSet((0.1, -0.1), 1.2, 0.6, rotation=0.3),
            ((-1.5, -1.2), (1.7, 1.0)),
        ),
        (
            RadialFourierLevelSet.star(
                (0.0, 0.0), 1.0, 0.16, 5, rotation=0.2
            ),
            ((-1.4, -1.4), (1.4, 1.4)),
        ),
    ),
)
def test_method_c_refines_generic_closed_fields_from_exact_method_b_coefficients(
    field,
    bounds,
) -> None:
    frontend, method_b = _fit_method_b(field, bounds)
    assert method_b.succeeded

    result = fit_method_c(
        field,
        frontend,
        method_b,
        config=_small_method_c(frontend.parameters.size),
    )

    assert result.status == "success"
    assert result.parameterization is not None
    assert result.validation is not None and result.validation.valid
    expected_initializer = _coefficient_matrix(method_b.representation)
    np.testing.assert_allclose(
        np.asarray(result.diagnostics["initial_coefficients"]),
        expected_initializer,
        rtol=0.0,
        atol=0.0,
    )
    baseline = result.diagnostics["baseline_fidelity"]
    final = result.diagnostics["final_fidelity"]
    assert final["normalized_max"] <= baseline["normalized_max"] * 1.001
    assert final["minimum_speed_to_mean"] > 1.0e-3
    assert result.diagnostics["relative_area_change_from_method_b"] < 5.0e-2
    assert result.diagnostics["relative_perimeter_change_from_method_b"] < 5.0e-2
    assert result.diagnostics["component_anchor_set"]["symmetric_rms"] < 0.25 * 1.2
    history = result.diagnostics["history"]
    optimizer_steps = [entry for entry in history if entry["event"] == "optimizer_step"]
    assert len(optimizer_steps) == 8 + 6 + 4
    assert all("components_before_update" in entry for entry in optimizer_steps)
    stage_starts = {
        entry["stage"]: entry["components"]["total"]
        for entry in history
        if entry["event"] == "stage_start"
    }
    for selection in result.diagnostics["pre_arc_stage_selection"]:
        assert selection["selection_metric"] == "weighted_stage_total"
        assert selection["selected_score"] <= stage_starts[selection["stage"]] + 1.0e-15
    assert result.diagnostics["final_best_score"] <= stage_starts["final"] + 1.0e-15
    assert result.parameterization.discretize(64, require_even=True).num_nodes == 64


def test_method_c_analytic_coefficient_gradient_matches_finite_differences() -> None:
    field = EllipseLevelSet((0.0, 0.0), 1.1, 0.7, rotation=0.2)
    frontend, method_b = _fit_method_b(
        field,
        ((-1.4, -1.1), (1.4, 1.1)),
        bandwidth=3,
        sample_count=64,
    )
    matrix = _coefficient_matrix(method_b.representation)
    dense_parameters = 2.0 * np.pi * np.arange(64, dtype=np.float64) / 64
    dense_basis, dense_derivative = _basis(dense_parameters, 3)
    anchor_basis, _ = _basis(frontend.parameters, 3)
    weights = RefinementWeights(
        fidelity=1.0,
        anchor=0.03,
        spectral=1.0e-8,
        speed=0.02,
        regularity=0.01,
    )
    config = _small_method_c(frontend.parameters.size)
    geometry_scale = 1.1
    _, analytic, _ = _loss_and_gradient(
        matrix,
        field=field,
        dense_basis=dense_basis,
        dense_derivative_basis=dense_derivative,
        anchor_basis=anchor_basis,
        anchor_points=frontend.projected_points,
        geometry_scale=geometry_scale,
        weights=weights,
        config=config,
        # The normalized proxy deliberately uses a frozen gradient-norm
        # denominator because only F and grad(F), not a Hessian, are required.
        normalized_fidelity=False,
    )

    numerical = np.empty_like(matrix)
    step = 2.0e-7
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            plus = matrix.copy()
            minus = matrix.copy()
            plus[row, column] += step
            minus[row, column] -= step
            plus_loss = _loss_and_gradient(
                plus,
                field=field,
                dense_basis=dense_basis,
                dense_derivative_basis=dense_derivative,
                anchor_basis=anchor_basis,
                anchor_points=frontend.projected_points,
                geometry_scale=geometry_scale,
                weights=weights,
                config=config,
                normalized_fidelity=False,
            )[0]
            minus_loss = _loss_and_gradient(
                minus,
                field=field,
                dense_basis=dense_basis,
                dense_derivative_basis=dense_derivative,
                anchor_basis=anchor_basis,
                anchor_points=frontend.projected_points,
                geometry_scale=geometry_scale,
                weights=weights,
                config=config,
                normalized_fidelity=False,
            )[0]
            numerical[row, column] = (plus_loss - minus_loss) / (2.0 * step)

    np.testing.assert_allclose(analytic, numerical, rtol=2.0e-5, atol=2.0e-7)


def test_generic_normalized_fidelity_search_direction_is_field_scale_invariant() -> None:
    field = EllipseLevelSet((0.0, 0.0), 1.1, 0.7, rotation=0.2)
    frontend, method_b = _fit_method_b(
        field,
        ((-1.4, -1.1), (1.4, 1.1)),
        bandwidth=3,
        sample_count=64,
    )
    scale = 7.5
    scaled_field = CallableImplicitField2D(
        lambda points: scale * field.value(points),
        lambda points: scale * field.gradient(points),
        name="scaled_ellipse_level_set",
        is_signed_distance=False,
    )
    matrix = _coefficient_matrix(method_b.representation)
    dense_parameters = 2.0 * np.pi * np.arange(64, dtype=np.float64) / 64
    dense_basis, dense_derivative = _basis(dense_parameters, 3)
    anchor_basis, _ = _basis(frontend.parameters, 3)
    weights = RefinementWeights(fidelity=1.0)
    config = replace(_small_method_c(frontend.parameters.size), gradient_epsilon=1.0e-14)

    common = dict(
        dense_basis=dense_basis,
        dense_derivative_basis=dense_derivative,
        anchor_basis=anchor_basis,
        anchor_points=frontend.projected_points,
        geometry_scale=1.1,
        weights=weights,
        config=config,
        normalized_fidelity=True,
    )
    loss, gradient, _ = _loss_and_gradient(matrix, field=field, **common)
    scaled_loss, scaled_gradient, _ = _loss_and_gradient(
        matrix,
        field=scaled_field,
        **common,
    )

    assert scaled_loss == pytest.approx(loss, rel=2.0e-13, abs=2.0e-15)
    np.testing.assert_allclose(
        scaled_gradient,
        gradient,
        rtol=3.0e-13,
        atol=3.0e-15,
    )


def test_method_c_returns_the_valid_method_b_curve_on_refinement_failure() -> None:
    field = EllipseLevelSet((0.0, 0.0), 1.1, 0.65, rotation=0.15)
    frontend, method_b = _fit_method_b(
        field,
        ((-1.4, -1.0), (1.4, 1.0)),
        bandwidth=6,
        sample_count=72,
    )

    class _FailAfterBaseline:
        is_signed_distance = field.is_signed_distance
        sign_convention = field.sign_convention

        def __init__(self) -> None:
            self.value_calls = 0

        def value(self, points):
            self.value_calls += 1
            if self.value_calls > 1:
                raise RuntimeError("intentional optimizer field failure")
            return field.value(points)

        def gradient(self, points):
            return field.gradient(points)

    result = fit_method_c(
        _FailAfterBaseline(),
        frontend,
        method_b,
        config=_small_method_c(frontend.parameters.size),
    )

    assert result.status == "fallback"
    assert "intentional optimizer field failure" in result.failure_reason
    assert result.parameterization is method_b.parameterization
    assert result.representation is method_b.representation
    assert result.validation is method_b.validation
    assert result.arc_length is method_b.arc_length
