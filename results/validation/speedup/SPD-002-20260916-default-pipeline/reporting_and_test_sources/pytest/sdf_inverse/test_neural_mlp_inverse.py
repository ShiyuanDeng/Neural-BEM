"""Focused contracts for the alternating full-MLP inverse path."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sdf_inverse import (
    AlternatingNeuralInverseConfig,
    ComplexScatteredData,
    MaterialSpec,
    NeuralRedistanceConfig,
    NeuralRedistanceResult,
    OrderedSDFGeometryConfig,
    OrderedSDFGeometryError,
    PairedForwardProblem,
    PairedForwardResult,
    SmoothMLPSDF2D,
    SmoothNormalModeUpdate2D,
    StarLevelSet2D,
    build_ordered_sdf_geometry,
    redistance_neural_sdf_to_curve,
    run_alternating_neural_inverse,
    signed_distance_to_curve_polygon,
)


@pytest.fixture(scope="module")
def cheap_geometry() -> OrderedSDFGeometryConfig:
    return OrderedSDFGeometryConfig(
        bounds=((0.30, 0.30), (0.70, 0.70)),
        grid_shape=(65, 65),
        projected_samples=48,
        bandwidth=8,
        num_nodes=32,
        arclength_dense_resolution=256,
        validation_resolution=192,
    )


def _wrong_circle_mlp(bounds) -> SmoothMLPSDF2D:
    return SmoothMLPSDF2D(
        bounds=bounds,
        hidden_features=32,
        hidden_layers=2,
        seed=23,
        geometric_center=(0.48, 0.52),
        geometric_radius=0.065,
        dtype=torch.float64,
    )


def test_polygon_distance_and_smooth_modal_field_are_regular(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    star = StarLevelSet2D(
        center=(0.5, 0.5),
        mean_radius=0.05,
        amplitude=0.20,
        lobes=5,
        dtype=torch.float64,
    )
    curve = build_ordered_sdf_geometry(star, cheap_geometry).curve
    probes = np.vstack((np.array([[0.5, 0.5], [0.65, 0.65]]), curve.points[:5]))
    first = signed_distance_to_curve_polygon(probes, curve, chunk_size=2)
    second = signed_distance_to_curve_polygon(probes, curve, chunk_size=100)
    np.testing.assert_array_equal(first, second)
    assert first[0] < 0.0 < first[1]
    assert np.max(np.abs(first[2:])) < 1.0e-14

    model = _wrong_circle_mlp(cheap_geometry.bounds)
    coefficients = np.zeros(11)
    update = SmoothNormalModeUpdate2D(
        model,
        center=(0.48, 0.52),
        radius_scale=0.065,
        maximum_mode=5,
        coefficients=coefficients,
    )
    points = torch.tensor([[0.48, 0.52], [0.545, 0.52]], dtype=torch.float64).requires_grad_(True)
    values = update(points)
    gradients = torch.autograd.grad(values.sum(), points)[0]
    assert torch.isfinite(values).all() and torch.isfinite(gradients).all()
    torch.testing.assert_close(values, model(points), rtol=0.0, atol=0.0)


def test_redistance_boundary_samples_are_uniform_in_polygon_arclength() -> None:
    from ordered_boundary import ellipse
    from sdf_inverse.neural import _dense_arclength_boundary_samples

    curve = ellipse((0.5, 0.5), 0.08, 0.03).discretize(16, require_even=True)
    points, normals = _dense_arclength_boundary_samples(curve, 4)
    assert points.shape == normals.shape == (4 * curve.num_nodes, 2)
    np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1.0, atol=1.0e-14)
    assert np.max(np.abs(signed_distance_to_curve_polygon(points, curve))) < 1.0e-14

    polygon = np.asarray(curve.points)
    edges = np.roll(polygon, -1, axis=0) - polygon
    lengths = np.linalg.norm(edges, axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    coordinates = []
    for point in points:
        displacement = point[None, :] - polygon
        fractions = np.sum(displacement * edges, axis=1) / lengths**2
        fractions = np.clip(fractions, 0.0, 1.0)
        closest = polygon + fractions[:, None] * edges
        edge_index = int(np.argmin(np.linalg.norm(closest - point[None, :], axis=1)))
        coordinate = cumulative[edge_index] + fractions[edge_index] * lengths[edge_index]
        coordinates.append(coordinate % cumulative[-1])
    ordered = np.sort(np.asarray(coordinates))
    gaps = np.diff(np.concatenate((ordered, ordered[:1] + cumulative[-1])))
    np.testing.assert_allclose(
        gaps,
        cumulative[-1] / points.shape[0],
        rtol=0.0,
        atol=1.0e-13,
    )


def test_random_hidden_mlp_redistances_to_a_non_circular_contour(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    torch.manual_seed(8675309)
    rng_state = torch.random.get_rng_state().clone()
    model = _wrong_circle_mlp(cheap_geometry.bounds)
    assert torch.equal(torch.random.get_rng_state(), rng_state)
    duplicate = _wrong_circle_mlp(cheap_geometry.bounds)
    for first, second in zip(model.state_dict().values(), duplicate.state_dict().values()):
        torch.testing.assert_close(first, second, rtol=0.0, atol=0.0)
    assert sum(parameter.numel() for parameter in model.parameters()) > 32

    target = StarLevelSet2D(
        center=(0.48, 0.52),
        mean_radius=0.065,
        amplitude=0.05,
        lobes=5,
        dtype=torch.float64,
    )
    target_curve = build_ordered_sdf_geometry(target, cheap_geometry).curve
    fit = redistance_neural_sdf_to_curve(
        model,
        target_curve,
        NeuralRedistanceConfig(
            bounds=cheap_geometry.bounds,
            max_steps=300,
            minimum_steps=60,
            warmup_steps=50,
            sample_count=512,
            heldout_sample_count=128,
            check_interval=20,
            patience_checks=20,
            seed=1023,
        ),
    )
    assert fit.converged, fit
    assert fit.final_boundary_max_abs_m < 1.0e-3
    assert fit.final_eikonal_rms < 0.2
    assert fit.diagnostics["boundary_sample_count"] == pytest.approx(
        4.0 * target_curve.num_nodes
    )
    assert fit.diagnostics["normal_offset_sample_count"] == pytest.approx(
        8.0 * target_curve.num_nodes
    )
    recovered = build_ordered_sdf_geometry(model, cheap_geometry).curve.points
    delta = recovered - np.array([0.48, 0.52])
    angles = np.arctan2(delta[:, 1], delta[:, 0])
    expected_radii = 0.065 * (1.0 + 0.05 * np.cos(5.0 * angles))
    assert np.max(np.abs(np.linalg.norm(delta, axis=1) - expected_radii)) < 1.0e-3
    assert model.claims_signed_distance is False
    assert model.trained_against_signed_distance is True


def test_terminal_redistance_state_is_checked_off_interval(
    monkeypatch,
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    import sdf_inverse.neural as neural_module

    audit_calls = 0

    def metrics_fail_until_terminal(*args, **kwargs):
        nonlocal audit_calls
        del args, kwargs
        audit_calls += 1
        value = 10.0 if audit_calls <= 4 else 0.0
        return (value, value, value, value)

    # The pre-Adam audit and the scheduled step-2 audit must fail so this
    # continues to exercise the off-interval terminal audit at step 3.
    monkeypatch.setattr(neural_module, "_quality_metrics", metrics_fail_until_terminal)
    target = StarLevelSet2D(
        center=(0.48, 0.52),
        mean_radius=0.065,
        amplitude=0.03,
        lobes=5,
        dtype=torch.float64,
    )
    curve = build_ordered_sdf_geometry(target, cheap_geometry).curve
    result = redistance_neural_sdf_to_curve(
        _wrong_circle_mlp(cheap_geometry.bounds),
        curve,
        NeuralRedistanceConfig(
            bounds=cheap_geometry.bounds,
            max_steps=3,
            minimum_steps=2,
            warmup_steps=1,
            sample_count=32,
            heldout_sample_count=32,
            distance_rms_tolerance_m=1.0,
            boundary_max_tolerance_m=1.0,
            eikonal_rms_tolerance=10.0,
            check_interval=2,
            seed=8,
        ),
    )
    assert result.converged
    assert result.stop_reason.endswith("at_final_state")
    assert result.steps == 3
    assert np.isfinite(result.final_total_loss)


def test_method_b_validation_is_an_infeasible_geometry(monkeypatch, cheap_geometry) -> None:
    import sdf_inverse.geometry as geometry_module
    from ordered_boundary import OrderedBoundaryValidationError

    def reject_fit(*args, **kwargs):
        raise OrderedBoundaryValidationError(
            SimpleNamespace(issues=("forced invalid fitted contour",))
        )

    monkeypatch.setattr(geometry_module, "fit_method_b", reject_fit)
    with pytest.raises(OrderedSDFGeometryError, match="forced invalid fitted contour"):
        build_ordered_sdf_geometry(_wrong_circle_mlp(cheap_geometry.bounds), cheap_geometry)


def test_already_converged_initial_state_stops_without_modal_probes(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    problem = PairedForwardProblem(
        source_points=np.array([[0.10, 0.10]]),
        receiver_points=np.array([[0.20, 0.20]]),
        angular_frequencies=2.0 * np.pi * np.array([1.0e8, 2.0e8]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )
    response = np.array([[1.0 + 0.5j, 0.75 - 0.25j]])
    calls = 0

    def constant_predictor(model, forward_problem, geometry_config, *, solver):
        nonlocal calls
        calls += 1
        assert model.training is False
        geometry = build_ordered_sdf_geometry(model, geometry_config)
        return PairedForwardResult(
            solver=solver,
            geometry_build=geometry,
            scattered_response=response,
            total_response=response,
            linear_system_relative_residuals=np.full(2, 0.02),
            geometry_seconds=0.0,
            forward_seconds=0.0,
            total_seconds=0.0,
        )

    model = _wrong_circle_mlp(cheap_geometry.bounds)
    result = run_alternating_neural_inverse(
        model,
        ComplexScatteredData(problem, response),
        cheap_geometry,
        solver="mod",
        config=AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(
                bounds=cheap_geometry.bounds,
                eikonal_rms_tolerance=5.0e-2,
                max_steps=2,
                minimum_steps=1,
                warmup_steps=1,
                sample_count=32,
                heldout_sample_count=32,
            ),
            max_iterations=1,
            maximum_mode=1,
        ),
        forward_predictor=constant_predictor,
    )
    assert result.converged
    assert (
        result.stop_reason
        == "initial_data_representation_and_eikonal_tolerances"
    )
    assert len(result.iterations) == 1
    assert result.total_evaluation_count == calls == 1
    assert result.maximum_system_residual == pytest.approx(0.02)
    assert model.training is True


def test_direct_probes_keep_the_canonical_curve_out_of_the_mlp_projection_loop(
    monkeypatch, cheap_geometry: OrderedSDFGeometryConfig
) -> None:
    """Every Jacobian probe is a curve solve; MLP extraction is audit-only."""

    import sdf_inverse.neural_optimization as optimization_module

    problem = PairedForwardProblem(
        source_points=np.array([[0.10, 0.10]]),
        receiver_points=np.array([[0.20, 0.20]]),
        angular_frequencies=2.0 * np.pi * np.array([1.0e8]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )
    model = _wrong_circle_mlp(cheap_geometry.bounds)
    initial_curve = build_ordered_sdf_geometry(model, cheap_geometry).curve
    curve_calls: list[object] = []
    validation_levels: list[bool] = []
    arclength_levels: list[bool] = []
    real_curve_update = optimization_module.apply_normal_mode_update

    def recording_curve_update(*args, **kwargs):
        validation_levels.append(bool(kwargs["full_validation"]))
        arclength_levels.append(bool(kwargs.get("reparameterize_arclength", False)))
        return real_curve_update(*args, **kwargs)

    def forbidden_model_predictor(*args, **kwargs):
        del args, kwargs
        raise AssertionError("model forward predictor entered the direct probe loop")

    def radius_predictor(curve, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config
        curve_calls.append(curve)
        radius = np.sqrt(curve.signed_area / np.pi)
        response = np.array([[radius + 0.0j]])
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=response,
            linear_system_relative_residuals=np.array([0.0]),
        )

    def accept_without_training(candidate, curve, config):
        del candidate, curve, config
        return NeuralRedistanceResult(
            converged=True,
            steps=1,
            stop_reason="test_distillation",
            initial_total_loss=1.0,
            final_total_loss=0.5,
            final_distance_rms_m=0.0,
            final_heldout_distance_rms_m=0.0,
            final_boundary_max_abs_m=0.0,
            final_eikonal_rms=0.0,
            final_eikonal_maximum_deviation=0.0,
            loss_history=np.array([0.5]),
            diagnostics={},
        )

    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", accept_without_training
    )
    monkeypatch.setattr(
        optimization_module, "apply_normal_mode_update", recording_curve_update
    )
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )
    monkeypatch.setattr(
        optimization_module,
        "_bounded_modal_step",
        lambda normal_matrix, gradient, scaling, curvature, basis, damping, config: (
            np.array([-1.0e-3, 0.0, 0.0]),
            damping,
        ),
    )

    initial_radius = np.sqrt(initial_curve.signed_area / np.pi)
    result = run_alternating_neural_inverse(
        model,
        ComplexScatteredData(problem, np.array([[initial_radius - 5.0e-3 + 0.0j]])),
        cheap_geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=_cheap_redistance(cheap_geometry.bounds),
            max_iterations=1,
            maximum_mode=1,
            max_damping_trials=1,
            max_backtracks=0,
            maximum_redistance_curve_drift_m=1.0e-2,
            maximum_spectral_tail_growth_m=1.0e-2,
        ),
        initial_curve=initial_curve,
        forward_predictor=forbidden_model_predictor,
        curve_forward_predictor=radius_predictor,
    )

    # Initial + six central-FD probes + one phase-preserving line-search trial
    # + one authoritative solve of the remeshed selected candidate.
    assert len(curve_calls) == result.total_evaluation_count == 9
    assert validation_levels.count(False) == 7
    assert validation_levels.count(True) == 1
    assert arclength_levels == [False] * 7 + [True]
    assert result.total_curve_update_seconds > 0.0
    assert result.total_forward_seconds >= result.total_bem_seconds >= 0.0
    assert result.total_geometry_audit_seconds > 0.0
    assert result.redistance_attempt_count == 1
    assert result.total_redistance_step_count == 1
    assert len(result.iterations) == 2
    assert result.final_iteration.loss < result.initial_iteration.loss
    assert result.final_curve is curve_calls[-1]
    np.testing.assert_array_equal(
        result.final_iteration.geometry_points, result.final_curve.points
    )
    assert np.sqrt(result.final_curve.signed_area / np.pi) < initial_radius
    # The fake fit left the MLP unchanged.  Its extracted audit can differ,
    # but that difference is not fed back into the canonical direct contour.
    assert result.final_representation_curve is not result.final_curve
    assert result.final_iteration.redistance_curve_drift_m > 0.0


@pytest.mark.parametrize(
    ("failure_kind", "expected_reason", "expected_counts"),
    (
        (
            "redistance",
            "retained_previous_representation_after_redistance_test_failure",
            (2, 0, 0),
        ),
        (
            "extraction",
            "retained_previous_representation_after_representation_extraction_failure",
            (0, 1, 0),
        ),
        (
            "drift",
            "retained_previous_representation_after_representation_drift_rejection",
            (0, 0, 1),
        ),
    ),
)
def test_material_direct_descent_can_retain_the_previous_audited_representation(
    monkeypatch,
    cheap_geometry: OrderedSDFGeometryConfig,
    failure_kind: str,
    expected_reason: str,
    expected_counts: tuple[int, int, int],
) -> None:
    """A transient MLP failure must not erase a valid canonical descent."""

    import sdf_inverse.neural_optimization as optimization_module

    problem = PairedForwardProblem(
        source_points=np.array([[0.10, 0.10]]),
        receiver_points=np.array([[0.20, 0.20]]),
        angular_frequencies=2.0 * np.pi * np.array([1.0e8]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )
    model = _wrong_circle_mlp(cheap_geometry.bounds)
    initial_curve = build_ordered_sdf_geometry(model, cheap_geometry).curve
    initial_radius = np.sqrt(initial_curve.signed_area / np.pi)
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    latest_direct_curve = initial_curve
    expected_updates = 2 if failure_kind == "redistance" else 1
    modal_step_m = -2.5e-4 if failure_kind == "redistance" else -5.0e-4

    def forbidden_model_predictor(*args, **kwargs):
        del args, kwargs
        raise AssertionError("the direct curve path must not call the model predictor")

    def radius_predictor(curve, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config, solver
        radius = np.sqrt(curve.signed_area / np.pi)
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[radius + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    def failed_redistance(candidate, direct_curve, config):
        nonlocal latest_direct_curve
        del candidate, config
        latest_direct_curve = direct_curve
        return NeuralRedistanceResult(
            converged=failure_kind != "redistance",
            steps=1,
            stop_reason=("test_failure" if failure_kind == "redistance" else "test_fit"),
            initial_total_loss=1.0,
            final_total_loss=0.5,
            final_distance_rms_m=0.0,
            final_heldout_distance_rms_m=0.0,
            final_boundary_max_abs_m=0.0,
            final_eikonal_rms=0.0,
            final_eikonal_maximum_deviation=0.0,
            loss_history=np.array([0.5]),
            diagnostics={},
        )

    def failed_representation_geometry(candidate, geometry_config):
        del candidate, geometry_config
        if failure_kind == "extraction":
            raise OrderedSDFGeometryError("forced representation extraction failure")
        if failure_kind != "drift":
            raise AssertionError("a failed redistance must skip representation extraction")
        return SimpleNamespace(
            curve=replace(
                latest_direct_curve,
                points=(
                    np.asarray(latest_direct_curve.points)
                    + np.array([2.0e-2, 0.0])[None, :]
                ),
            )
        )

    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", failed_redistance
    )
    monkeypatch.setattr(
        optimization_module, "build_ordered_sdf_geometry", failed_representation_geometry
    )
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )
    monkeypatch.setattr(
        optimization_module,
        "_bounded_modal_step",
        lambda normal_matrix, gradient, scaling, curvature, basis, damping, config: (
            np.array([modal_step_m, 0.0, 0.0]),
            damping,
        ),
    )

    result = run_alternating_neural_inverse(
        model,
        ComplexScatteredData(
            problem,
            np.array([[initial_radius - 5.0e-3 + 0.0j]]),
        ),
        cheap_geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=_cheap_redistance(cheap_geometry.bounds),
            max_iterations=expected_updates,
            maximum_mode=1,
            max_damping_trials=1,
            max_backtracks=0,
            maximum_redistance_curve_drift_m=1.0e-3,
        ),
        initial_curve=initial_curve,
        initial_representation_curve=initial_curve,
        forward_predictor=forbidden_model_predictor,
        curve_forward_predictor=radius_predictor,
    )

    assert not result.converged
    assert result.stop_reason == "maximum_iterations"
    assert len(result.iterations) == expected_updates + 1
    assert result.final_iteration.loss < result.initial_iteration.loss
    assert result.final_curve is not initial_curve
    assert result.final_representation_curve is initial_curve
    assert result.final_iteration.redistance_stop_reason == expected_reason
    assert 0.0 < result.final_iteration.redistance_curve_drift_m <= 1.0e-3
    # A retained representation is not treated as a successful distillation:
    # the next canonical iteration retries neural re-distancing.
    assert result.redistance_attempt_count == expected_updates
    assert (
        result.redistance_failure_count,
        result.representation_extraction_failure_count,
        result.representation_drift_rejection_count,
    ) == expected_counts
    # A rejected candidate MLP never becomes hidden optimizer state.
    for name, value in model.state_dict().items():
        torch.testing.assert_close(value, before[name], rtol=0.0, atol=0.0)


def test_previous_representation_cannot_be_retained_beyond_the_drift_gate(
    monkeypatch, cheap_geometry: OrderedSDFGeometryConfig
) -> None:
    """Canonical-only resilience is bounded by the existing physical audit."""

    import sdf_inverse.neural_optimization as optimization_module

    problem = PairedForwardProblem(
        source_points=np.array([[0.10, 0.10]]),
        receiver_points=np.array([[0.20, 0.20]]),
        angular_frequencies=2.0 * np.pi * np.array([1.0e8]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )
    model = _wrong_circle_mlp(cheap_geometry.bounds)
    initial_curve = build_ordered_sdf_geometry(model, cheap_geometry).curve
    initial_radius = np.sqrt(initial_curve.signed_area / np.pi)

    def radius_predictor(curve, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config, solver
        radius = np.sqrt(curve.signed_area / np.pi)
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[radius + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    def failed_redistance(candidate, direct_curve, config):
        del candidate, direct_curve, config
        return NeuralRedistanceResult(
            converged=False,
            steps=1,
            stop_reason="test_failure",
            initial_total_loss=1.0,
            final_total_loss=0.5,
            final_distance_rms_m=1.0,
            final_heldout_distance_rms_m=1.0,
            final_boundary_max_abs_m=1.0,
            final_eikonal_rms=1.0,
            final_eikonal_maximum_deviation=1.0,
            loss_history=np.array([0.5]),
            diagnostics={},
        )

    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", failed_redistance
    )
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )
    monkeypatch.setattr(
        optimization_module,
        "_bounded_modal_step",
        lambda normal_matrix, gradient, scaling, curvature, basis, damping, config: (
            np.array([-5.0e-4, 0.0, 0.0]),
            damping,
        ),
    )

    result = run_alternating_neural_inverse(
        model,
        ComplexScatteredData(
            problem,
            np.array([[initial_radius - 5.0e-3 + 0.0j]]),
        ),
        cheap_geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=_cheap_redistance(cheap_geometry.bounds),
            max_iterations=1,
            maximum_mode=1,
            max_damping_trials=1,
            max_backtracks=0,
            maximum_redistance_curve_drift_m=1.0e-5,
        ),
        initial_curve=initial_curve,
        initial_representation_curve=initial_curve,
        forward_predictor=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("the direct curve path must not call the model predictor")
        ),
        curve_forward_predictor=radius_predictor,
    )

    assert not result.converged
    assert result.stop_reason == "no_acceptable_mlp_distillation"
    assert len(result.iterations) == 1
    assert result.final_curve is initial_curve
    assert result.final_representation_curve is initial_curve
    assert result.redistance_attempt_count == result.redistance_failure_count == 1


def test_dense_curve_rejection_is_not_reported_as_mlp_failure(
    monkeypatch, cheap_geometry: OrderedSDFGeometryConfig
) -> None:
    """A selected direct step can fail before neural distillation is attempted."""

    import sdf_inverse.neural_optimization as optimization_module

    problem = PairedForwardProblem(
        source_points=np.array([[0.10, 0.10]]),
        receiver_points=np.array([[0.20, 0.20]]),
        angular_frequencies=2.0 * np.pi * np.array([1.0e8]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )
    model = _wrong_circle_mlp(cheap_geometry.bounds)
    initial_curve = build_ordered_sdf_geometry(model, cheap_geometry).curve
    initial_radius = np.sqrt(initial_curve.signed_area / np.pi)
    real_curve_update = optimization_module.apply_normal_mode_update

    def reject_only_dense_validation(*args, **kwargs):
        if kwargs["full_validation"]:
            raise OrderedSDFGeometryError("forced dense-validation rejection")
        return real_curve_update(*args, **kwargs)

    def radius_predictor(curve, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config, solver
        radius = np.sqrt(curve.signed_area / np.pi)
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[radius + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    def forbidden_model_predictor(*args, **kwargs):
        del args, kwargs
        raise AssertionError("the direct curve path must not call the model predictor")

    def forbidden_redistance(*args, **kwargs):
        del args, kwargs
        raise AssertionError("dense validation must precede neural re-distancing")

    monkeypatch.setattr(
        optimization_module, "apply_normal_mode_update", reject_only_dense_validation
    )
    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", forbidden_redistance
    )
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )
    monkeypatch.setattr(
        optimization_module,
        "_bounded_modal_step",
        lambda normal_matrix, gradient, scaling, curvature, basis, damping, config: (
            np.array([-1.0e-3, 0.0, 0.0]),
            damping,
        ),
    )

    result = run_alternating_neural_inverse(
        model,
        ComplexScatteredData(
            problem, np.array([[initial_radius - 5.0e-3 + 0.0j]])
        ),
        cheap_geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=_cheap_redistance(cheap_geometry.bounds),
            max_iterations=1,
            maximum_mode=1,
            max_damping_trials=1,
            max_backtracks=0,
        ),
        initial_curve=initial_curve,
        forward_predictor=forbidden_model_predictor,
        curve_forward_predictor=radius_predictor,
    )

    assert not result.converged
    assert result.stop_reason == "no_fully_valid_geometry"
    assert len(result.iterations) == 1
    assert result.full_validation_rejection_count == 1
    assert result.redistance_attempt_count == 0
    assert result.redistance_failure_count == 0
    assert result.representation_extraction_failure_count == 0
    assert result.representation_drift_rejection_count == 0
    assert result.infeasible_evaluation_count == 0
    with pytest.raises(ValueError, match="post-redistance rejection"):
        replace(result, redistance_failure_count=1)
    with pytest.raises(ValueError, match="infeasible_evaluation_count"):
        replace(
            result,
            infeasible_evaluation_count=result.total_evaluation_count + 1,
        )


def test_remeshed_candidate_is_resolved_and_must_repass_armijo(
    monkeypatch, cheap_geometry: OrderedSDFGeometryConfig
) -> None:
    """A decreasing phase probe cannot authorize a non-decreasing remesh."""

    import sdf_inverse.neural_optimization as optimization_module

    problem = PairedForwardProblem(
        source_points=np.array([[0.10, 0.10]]),
        receiver_points=np.array([[0.20, 0.20]]),
        angular_frequencies=2.0 * np.pi * np.array([1.0e8]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )
    model = _wrong_circle_mlp(cheap_geometry.bounds)
    initial_curve = build_ordered_sdf_geometry(model, cheap_geometry).curve
    initial_radius = np.sqrt(initial_curve.signed_area / np.pi)
    remeshed_curve_ids: set[int] = set()
    remeshed_solve_count = 0
    predictor_calls = 0
    real_curve_update = optimization_module.apply_normal_mode_update

    def record_remeshed_update(*args, **kwargs):
        update = real_curve_update(*args, **kwargs)
        if kwargs.get("reparameterize_arclength", False):
            remeshed_curve_ids.add(id(update.curve))
        return update

    def radius_predictor(curve, forward_problem, geometry_config, *, solver):
        nonlocal predictor_calls, remeshed_solve_count
        del forward_problem, geometry_config, solver
        predictor_calls += 1
        radius = np.sqrt(curve.signed_area / np.pi)
        if id(curve) in remeshed_curve_ids:
            remeshed_solve_count += 1
            # The cheap phase-preserving probe decreases toward the smaller
            # observed radius.  Force only the authoritative remeshed solve to
            # increase so acceptance proves it uses this fresh response.
            radius = initial_radius + 1.0e-2
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[radius + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    def forbidden_model_predictor(*args, **kwargs):
        del args, kwargs
        raise AssertionError("the direct curve path must not call the model predictor")

    def forbidden_redistance(*args, **kwargs):
        del args, kwargs
        raise AssertionError("a remeshed Armijo failure must precede MLP training")

    monkeypatch.setattr(
        optimization_module, "apply_normal_mode_update", record_remeshed_update
    )
    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", forbidden_redistance
    )
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )
    monkeypatch.setattr(
        optimization_module,
        "_bounded_modal_step",
        lambda normal_matrix, gradient, scaling, curvature, basis, damping, config: (
            np.array([-1.0e-3, 0.0, 0.0]),
            damping,
        ),
    )

    result = run_alternating_neural_inverse(
        model,
        ComplexScatteredData(
            problem, np.array([[initial_radius - 5.0e-3 + 0.0j]])
        ),
        cheap_geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=_cheap_redistance(cheap_geometry.bounds),
            max_iterations=1,
            maximum_mode=1,
            max_damping_trials=1,
            max_backtracks=0,
            maximum_spectral_tail_growth_m=1.0e-2,
        ),
        initial_curve=initial_curve,
        forward_predictor=forbidden_model_predictor,
        curve_forward_predictor=radius_predictor,
    )

    assert not result.converged
    assert result.stop_reason == "no_decreasing_modal_step"
    assert remeshed_solve_count == 1
    assert predictor_calls == result.total_evaluation_count == 9
    assert len(result.iterations) == 1
    assert result.final_curve is initial_curve
    assert result.redistance_attempt_count == 0
    assert result.full_validation_rejection_count == 0


def test_model_only_predictor_compatibility_requires_post_distillation_decrease(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    problem = PairedForwardProblem(
        source_points=np.array([[0.10, 0.10]]),
        receiver_points=np.array([[0.20, 0.20]]),
        angular_frequencies=2.0 * np.pi * np.array([1.0e8, 2.0e8]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )

    def geometry_observable(model, forward_problem, geometry_config, *, solver):
        assert model.training is False
        geometry = build_ordered_sdf_geometry(model, geometry_config)
        center = np.mean(geometry.curve.points, axis=0)
        radius = np.sqrt(geometry.curve.signed_area / np.pi)
        response = np.array([[center[0] + 1j * center[1], radius + 0.0j]])
        return PairedForwardResult(
            solver=solver,
            geometry_build=geometry,
            scattered_response=response,
            total_response=response,
            linear_system_relative_residuals=np.full(
                2, 0.25 if isinstance(model, SmoothNormalModeUpdate2D) else 0.01
            ),
            geometry_seconds=0.0,
            forward_seconds=0.0,
            total_seconds=0.0,
        )

    model = _wrong_circle_mlp(cheap_geometry.bounds)
    data = ComplexScatteredData(
        problem,
        np.array([[0.50 + 0.50j, 0.050 + 0.0j]]),
    )
    result = run_alternating_neural_inverse(
        model,
        data,
        cheap_geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(
                bounds=cheap_geometry.bounds,
                eikonal_rms_tolerance=5.0e-2,
                max_steps=400,
                minimum_steps=60,
                warmup_steps=50,
                sample_count=512,
                heldout_sample_count=128,
                check_interval=20,
                patience_checks=20,
                seed=4,
            ),
            max_iterations=1,
            maximum_mode=1,
        ),
        forward_predictor=geometry_observable,
    )
    assert len(result.iterations) == 2
    assert result.final_iteration.loss < result.initial_iteration.loss
    assert result.final_iteration.redistance_steps > 0
    assert result.final_iteration.redistance_curve_drift_m <= 1.5e-3
    assert result.maximum_system_residual == pytest.approx(0.25)
    assert result.final_iteration.maximum_system_residual == pytest.approx(0.25)
    assert result.infeasible_evaluation_count == 0
    assert model.training is True


def test_redistance_curve_drift_rejects_and_rolls_back(
    monkeypatch, cheap_geometry: OrderedSDFGeometryConfig
) -> None:
    import sdf_inverse.neural_optimization as optimization_module

    problem = PairedForwardProblem(
        source_points=np.array([[0.10, 0.10]]),
        receiver_points=np.array([[0.20, 0.20]]),
        angular_frequencies=2.0 * np.pi * np.array([1.0e8, 2.0e8]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )

    def geometry_observable(model, forward_problem, geometry_config, *, solver):
        geometry = build_ordered_sdf_geometry(model, geometry_config)
        center = np.mean(geometry.curve.points, axis=0)
        radius = np.sqrt(geometry.curve.signed_area / np.pi)
        response = np.array([[center[0] + 1j * center[1], radius + 0.0j]])
        return PairedForwardResult(
            solver=solver,
            geometry_build=geometry,
            scattered_response=response,
            total_response=response,
            linear_system_relative_residuals=np.zeros(2),
            geometry_seconds=0.0,
            forward_seconds=0.0,
            total_seconds=0.0,
        )

    def shifted_redistance(candidate, curve, config):
        with torch.no_grad():
            candidate.geometric_center[0].add_(0.02)
        return NeuralRedistanceResult(
            converged=True,
            steps=1,
            stop_reason="test_shift",
            initial_total_loss=1.0,
            final_total_loss=0.5,
            final_distance_rms_m=0.0,
            final_heldout_distance_rms_m=0.0,
            final_boundary_max_abs_m=0.0,
            final_eikonal_rms=0.0,
            final_eikonal_maximum_deviation=0.0,
            loss_history=np.array([0.5]),
            diagnostics={},
        )

    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", shifted_redistance
    )
    model = _wrong_circle_mlp(cheap_geometry.bounds)
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    result = run_alternating_neural_inverse(
        model,
        ComplexScatteredData(
            problem,
            np.array([[0.50 + 0.50j, 0.050 + 0.0j]]),
        ),
        cheap_geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(
                bounds=cheap_geometry.bounds,
                eikonal_rms_tolerance=5.0e-2,
                max_steps=2,
                minimum_steps=1,
                warmup_steps=1,
                sample_count=32,
                heldout_sample_count=32,
            ),
            max_iterations=1,
            maximum_mode=1,
            max_damping_trials=1,
            max_backtracks=0,
        ),
        forward_predictor=geometry_observable,
    )
    assert not result.converged
    assert result.stop_reason == "no_acceptable_mlp_distillation"
    assert len(result.iterations) == 1
    assert result.redistance_attempt_count == 1
    assert result.total_redistance_step_count == 1
    assert result.representation_drift_rejection_count == 1
    assert result.redistance_failure_count == 0
    assert result.representation_extraction_failure_count == 0
    for name, value in model.state_dict().items():
        torch.testing.assert_close(value, before[name], rtol=0.0, atol=0.0)


def _cheap_redistance(bounds) -> NeuralRedistanceConfig:
    return NeuralRedistanceConfig(
        bounds=bounds,
        eikonal_rms_tolerance=5.0e-2,
        max_steps=2,
        minimum_steps=1,
        warmup_steps=1,
        sample_count=32,
        heldout_sample_count=32,
    )


def test_inner_eikonal_tolerance_may_not_exceed_the_outer_gate(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    # The inner fit stopping at 0.2 while the outer loop demands 0.15 is not a
    # tuning preference: it makes the convergence test unreachable, so every
    # run can only ever end at maximum_iterations.
    with pytest.raises(ValueError, match="eikonal_rms_tolerance"):
        AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(
                bounds=cheap_geometry.bounds, eikonal_rms_tolerance=2.0e-1
            ),
            eikonal_rms_tolerance=1.5e-1,
        )


@pytest.mark.parametrize(
    "overrides, message",
    (
        ({"minimum_damping": 1.0e-2, "initial_damping": 1.0e-3}, "minimum_damping"),
        ({"armijo_coefficient": 1.0}, "armijo_coefficient"),
        ({"curvature_penalty_weight": -1.0}, "curvature_penalty_weight"),
    ),
)
def test_step_regularization_bounds_are_validated(
    cheap_geometry: OrderedSDFGeometryConfig, overrides: dict, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        AlternatingNeuralInverseConfig(
            redistance=_cheap_redistance(cheap_geometry.bounds), **overrides
        )


def test_curvature_penalty_prices_a_mode_by_its_bending_energy(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    from sdf_inverse.neural_optimization import _curvature_penalty, _mode_orders

    config = AlternatingNeuralInverseConfig(
        redistance=_cheap_redistance(cheap_geometry.bounds),
        maximum_mode=5,
        curvature_penalty_weight=1.0e-4,
    )
    normal_matrix = np.diag(np.full(11, 4.0))
    penalty = _curvature_penalty(normal_matrix, config)

    np.testing.assert_array_equal(
        _mode_orders(5), np.array([0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5], dtype=np.float64)
    )
    assert penalty.shape == (11,)
    assert penalty[0] == 0.0
    assert penalty[-1] == pytest.approx(1.0e-4 * 4.0 * 5.0**4)
    # The prior must be negligible where the data is informative and dominant
    # where it is not; a flat ridge would suppress both equally.
    assert penalty[1] < 1.0e-3 * float(np.max(np.diag(normal_matrix)))
    assert penalty[-1] > 10.0 * penalty[3]

    disabled = AlternatingNeuralInverseConfig(
        redistance=_cheap_redistance(cheap_geometry.bounds),
        maximum_mode=5,
        curvature_penalty_weight=0.0,
    )
    np.testing.assert_array_equal(
        _curvature_penalty(normal_matrix, disabled), np.zeros(11)
    )


def test_trust_region_rotates_the_step_instead_of_rescaling_it(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    from sdf_inverse.neural_optimization import _bounded_modal_step

    # Two modes: a well-determined one and a near-null one that the data can
    # barely see.  Undamped Gauss-Newton inverts the small singular value and
    # the step comes out dominated by the mode nothing measured.
    jacobian = np.array([[1.0, 0.0], [0.0, 1.0e-3]])
    residual = np.array([1.0, 1.0])
    normal_matrix = jacobian.T @ jacobian
    gradient = jacobian.T @ residual
    scaling = np.maximum(np.diag(normal_matrix), 1.0)
    basis_at_curve = np.array([[1.0, 1.0], [1.0, -1.0]])
    config = AlternatingNeuralInverseConfig(
        redistance=_cheap_redistance(cheap_geometry.bounds),
        maximum_mode=1,
        maximum_modal_field_update_m=4.0e-3,
        max_trust_region_solves=20,
    )

    undamped = np.linalg.solve(normal_matrix + 1.0e-10 * np.diag(scaling), -gradient)
    assert abs(undamped[1]) > 100.0 * abs(undamped[0])

    step, used_damping = _bounded_modal_step(
        normal_matrix,
        gradient,
        scaling,
        np.zeros(2),
        basis_at_curve,
        1.0e-10,
        config,
    )
    assert float(np.max(np.abs(basis_at_curve @ step))) <= config.maximum_modal_field_update_m
    assert float(np.max(np.abs(basis_at_curve @ step))) >= (
        0.95 * config.maximum_modal_field_update_m
    )
    assert used_damping > 1.0e-10
    # Rescaling preserves the ratio, so the near-null mode stays dominant and
    # the resolvable one keeps its vanishing share.  Raising the damping
    # rotates the step, which is the whole point of the region.
    assert abs(step[0]) > 100.0 * abs(step[1])
    rescaled = undamped * (
        config.maximum_modal_field_update_m
        / float(np.max(np.abs(basis_at_curve @ undamped)))
    )
    assert abs(rescaled[1]) > 100.0 * abs(rescaled[0])
    assert abs(step[0]) > 100.0 * abs(rescaled[0])


def test_trust_region_leaves_an_already_small_step_alone(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    from sdf_inverse.neural_optimization import _bounded_modal_step

    normal_matrix = np.diag([1.0, 1.0])
    gradient = np.array([1.0e-6, 1.0e-6])
    config = AlternatingNeuralInverseConfig(
        redistance=_cheap_redistance(cheap_geometry.bounds), maximum_mode=1
    )
    step, used_damping = _bounded_modal_step(
        normal_matrix,
        gradient,
        np.ones(2),
        np.zeros(2),
        np.eye(2),
        1.0e-3,
        config,
    )
    assert used_damping == pytest.approx(1.0e-3)
    np.testing.assert_allclose(step, -gradient / (1.0 + 1.0e-3), rtol=1.0e-12)


def test_armijo_rejects_a_negligible_fraction_of_the_predicted_decrease(
    cheap_geometry: OrderedSDFGeometryConfig,
) -> None:
    from sdf_inverse.neural_optimization import _sufficient_decrease

    config = AlternatingNeuralInverseConfig(
        redistance=_cheap_redistance(cheap_geometry.bounds), armijo_coefficient=1.0e-4
    )
    # A step whose direction promised 1.0 but delivered 1e-9 is how a
    # data-invisible ripple survives: it does decrease the loss.
    assert not _sufficient_decrease(1.0 - 1.0e-9, 1.0, -1.0, config)
    assert _sufficient_decrease(0.9, 1.0, -1.0, config)
    assert not _sufficient_decrease(1.0, 1.0, -1.0, config)
    # Without a descent direction in the model there is nothing to compare a
    # realised decrease against, so a strict decrease is the whole test.
    assert _sufficient_decrease(1.0 - 1.0e-9, 1.0, 0.0, config)


def test_resolvable_maximum_mode_follows_ka() -> None:
    from sdf_inverse import resolvable_maximum_mode

    # 0.5 GHz in eps_r 6 on a 50 mm scatterer is ka ~ 1.28: a five-lobed
    # ripple there is not something the measurement can resolve.
    low = resolvable_maximum_mode(25.66, 0.050)
    high = resolvable_maximum_mode(76.99, 0.055)
    assert low < 5 <= high
    assert resolvable_maximum_mode(1.0e-6, 1.0e-6) == 1
    assert resolvable_maximum_mode(1.0e6, 1.0, maximum=8) == 8
    for bad in ((0.0, 1.0), (1.0, -1.0), (float("nan"), 1.0)):
        with pytest.raises(ValueError):
            resolvable_maximum_mode(*bad)
