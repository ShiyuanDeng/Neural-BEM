"""Geometry correspondences and data-only diagnostic directions stay honest."""
import csv
from dataclasses import replace
import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sdf_inverse.frozen_diagnostics import (
    DiagnosticBudgetExceeded, WorkBudget, field_only_repair, field_quantities,
    connected_tensor_jvp,
    first_order_window, interpolated_parameterization, load_saved_case,
    implicit_normal_correspondence, nearest_target_normal_correction,
    normal_correspondence, normal_mode_basis, polygon_geometry, smooth_normal_correspondence,
    report_geometry, residual_metric_directions, spectrum,
)
from sdf_inverse.geometry import OrderedSDFGeometryConfig
from sdf_inverse.models import SirenImplicitField2D, TorchParameterController, build_siren_parameter_controller


def circle(count=128, radius=.06):
    angle = np.linspace(0, 2 * np.pi, count, endpoint=False)
    normal = np.column_stack([np.cos(angle), np.sin(angle)])
    return .5 + radius * normal, normal


class ScaledDistance(torch.nn.Module):
    def __init__(self, gain=2.0):
        super().__init__()
        self.gain = torch.nn.Parameter(torch.tensor(gain, dtype=torch.float64))

    def forward(self, points):
        return self.gain * (torch.linalg.vector_norm(points - .5, dim=1) - .06)


def test_normal_correspondence_ignores_node_indices_and_phase():
    points, normals = circle()
    candidate, _ = circle(radius=.061)
    delta = normal_correspondence(points, normals, np.roll(candidate, 37, axis=0))
    np.testing.assert_allclose(delta, .001, atol=3e-17)
    inward, _ = circle(radius=.059)
    np.testing.assert_allclose(normal_correspondence(points, normals, inward), -.001, atol=3e-17)


def test_smooth_and_implicit_motion_remove_first_order_polygon_bias():
    class TranslatedCircle(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.center = torch.nn.Parameter(torch.full((2,), .5, dtype=torch.float64))
        def forward(self, points):
            return torch.linalg.vector_norm(points - self.center, dim=1) - .06
    model = TranslatedCircle()
    points, normals = circle(count=64)
    velocity = np.array([1e-5, 2e-5])
    weights = polygon_geometry(points)[1]
    smooth_errors, implicit_errors, polygon_errors = [], [], []
    alphas = np.array([1., .5, .25])
    for alpha in alphas:
        with torch.no_grad():
            model.center.copy_(torch.tensor(.5 + alpha * velocity))
        predicted = alpha * (normals @ velocity)
        exact = predicted + np.sqrt(.06 ** 2 - alpha ** 2 * (velocity @ velocity - (normals @ velocity) ** 2)) - .06
        candidate = points + alpha * velocity
        smooth = smooth_normal_correspondence(points, normals, np.roll(candidate, 13, axis=0))
        implicit = implicit_normal_correspondence(model, points, normals, initial=predicted)
        polygon = normal_correspondence(points, normals, candidate)
        np.testing.assert_allclose(smooth, exact, atol=2e-13)
        np.testing.assert_allclose(implicit, exact, atol=2e-13)
        for errors, actual in ((smooth_errors, smooth), (implicit_errors, implicit), (polygon_errors, polygon)):
            errors.append(np.sqrt(weights @ (actual - predicted) ** 2))
    rms = np.sqrt(weights @ (normals @ velocity) ** 2)
    assert first_order_window(alphas, smooth_errors, rms)["first_order_window_verified"]
    assert first_order_window(alphas, implicit_errors, rms)["first_order_window_verified"]
    assert not first_order_window(alphas, polygon_errors, rms)["first_order_window_verified"]


def test_missing_and_nontransverse_normal_roots_stay_uninterpretable():
    model = ScaledDistance()
    points, _ = circle(count=64)
    reference = np.array([[.7, .5]])
    normals = np.array([[0., 1.]])
    assert np.isnan(implicit_normal_correspondence(model, reference, normals)).all()
    assert np.isnan(smooth_normal_correspondence(reference, normals, points)).all()


def test_nearest_target_score_is_distance_derivative_when_normal_line_misses():
    target = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])
    reference = np.array([[2., .5]])
    normals = np.array([[-1., 1.]]) / np.sqrt(2)
    assert np.isnan(normal_correspondence(reference, normals, target)).all()
    correction = nearest_target_normal_correction(reference, normals, target)
    epsilon = 1e-6
    high = .5 * (reference[0, 0] + epsilon * normals[0, 0] - 1) ** 2
    low = .5 * (reference[0, 0] - epsilon * normals[0, 0] - 1) ** 2
    assert correction[0] == pytest.approx(-(high - low) / (2 * epsilon), rel=1e-9)


def test_weighted_modes_parseval_and_signed_modal_effect():
    # Nonuniform sampling requires genuine arc weights, not node averages.
    t = np.linspace(0, 2 * np.pi, 201, endpoint=False)
    t += .2 * np.sin(t)
    points = .5 + .06 * np.column_stack([np.cos(t), np.sin(t)])
    basis, weights, orders = normal_mode_basis(points, 20)
    np.testing.assert_allclose(basis.T @ (weights[:, None] * basis), np.eye(41), atol=2e-15)
    values = .002 * basis[:, 9] - .003 * basis[:, 13]
    record = spectrum(values, points, 20, target_correction=-values)
    assert record["energy_0_5"] == pytest.approx(4e-6)
    assert record["energy_6_10"] == pytest.approx(9e-6)
    assert record["unresolved_energy"] < 1e-34
    assert record["signed_effect_by_mode"]["5"] < 0
    assert record["signed_effect_by_mode"]["7"] < 0


def test_field_jvp_separates_unclipped_numerator_and_denominator():
    model = ScaledDistance(gain=1e-8)
    points, _ = circle(radius=.061)
    result = field_quantities(model, points, np.array([3.0]))
    np.testing.assert_allclose(result["G"], 1e-8, rtol=1e-14)
    np.testing.assert_allclose(result["inverse_G"], 1e8, rtol=1e-14)
    np.testing.assert_allclose(result["N"], .003, atol=1e-15)
    np.testing.assert_allclose(result["V"], -3e5, atol=1e-7)


def test_connected_branch_graph_jvp_matches_analytic_nonlinear_map():
    parameters = torch.tensor([.3, -.2], dtype=torch.float64, requires_grad=True)
    output = torch.stack([parameters[0] ** 2, torch.sin(parameters[1]), parameters.prod()])
    actual = connected_tensor_jvp(output, (parameters,), np.array([2., 3.]))
    expected = np.array([1.2, 3 * np.cos(-.2), 2 * -.2 + 3 * .3])
    np.testing.assert_allclose(actual, expected, atol=1e-15)


def test_connected_method_b_motion_matches_finite_reextraction():
    from sdf_inverse.geometry import build_ordered_sdf_geometry
    from sdf_inverse.method_b_pullback import build_method_b_pullback
    class RadiusField(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.radius = torch.nn.Parameter(torch.tensor(.0607, dtype=torch.float64))
        def forward(self, points):
            return torch.linalg.vector_norm(points - torch.tensor([.5003, .5017]), dim=1) - self.radius
    model = RadiusField()
    config = OrderedSDFGeometryConfig(bounds=((.3, .3), (.7, .7)), grid_shape=(35, 37),
        projected_samples=32, bandwidth=5, num_nodes=32, arclength_dense_resolution=128,
        validation_resolution=128)
    base = build_ordered_sdf_geometry(model, config)
    graph = build_method_b_pullback(model, config, reference_curve=base.curve)
    derivative = connected_tensor_jvp(graph.points, (model.radius,), np.array([1.]))
    original = float(model.radius.detach())
    points = []
    try:
        for sign in (1, -1):
            with torch.no_grad():
                model.radius.fill_(original + sign * 1e-7)
            points.append(build_ordered_sdf_geometry(model, config).curve.points)
    finally:
        with torch.no_grad():
            model.radius.fill_(original)
    np.testing.assert_allclose(derivative, (points[0] - points[1]) / 2e-7, atol=3e-6, rtol=2e-5)


def test_curve_gn_uses_only_residual_and_singular_value_cutoff():
    matrix = np.diag([4., 2., 1e-9])
    residual = np.array([1., -2., 3.])
    directions, info = residual_metric_directions(matrix, residual, damping=.01, tsvd_cutoff=1e-3)
    np.testing.assert_allclose(directions["steepest_descent"], -matrix.T @ residual)
    np.testing.assert_allclose(directions["damped_gn"], np.linalg.solve(matrix.T @ matrix + info["damping_mu"] * np.eye(3), -matrix.T @ residual))
    np.testing.assert_allclose(directions["tsvd_gn"], [-.25, 1., 0.])
    assert info["tsvd_retained_rank"] == 2


def test_first_order_window_rejects_plateau_and_accepts_quadratic_error():
    alphas = np.array([1., .5, .25])
    good = first_order_window(alphas, 1e-7 * alphas ** 2, 1e-5)
    assert good["first_order_window_verified"]
    assert not first_order_window(alphas, np.full(3, 1e-7), 1e-5)["first_order_window_verified"]


def test_fourier_interpolant_preserves_nodes_and_derivatives():
    points, normals = circle()
    parameterization = interpolated_parameterization(points)
    curve = parameterization.discretize(len(points))
    np.testing.assert_allclose(curve.points, points, atol=3e-16)
    np.testing.assert_allclose(curve.normals, normals, atol=1e-12)


def test_actual_weight_loader_checks_terminal_checkpoint(tmp_path):
    model = SirenImplicitField2D(bounds=((.3, .3), (.7, .7)), hidden_features=4, hidden_layers=1, random_seed=2, dtype=torch.float64)
    controller = build_siren_parameter_controller(model)
    weights = controller.parameter_vector()
    torch.save({"constructor": {"bounds": ((.3, .3), (.7, .7)), "hidden_features": 4,
                               "hidden_layers": 1, "random_seed": 2},
                "state_dict": model.state_dict(), "geometry_config": {"bounds": ((.3, .3), (.7, .7))},
                "optimizer_config": {}, "accepted_iteration": 0}, tmp_path / "kress_model.pt")
    def write(vector):
        with (tmp_path / "kress_trajectory.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["iteration", *["raw_" + name for name in controller.names]])
            writer.writerow([0, *vector])
    write(weights)
    (tmp_path / "metrics.json").write_text("{}")
    np.savez(tmp_path / "kress_responses.npz", geometry_trajectory=np.ones((1, 8, 2)))
    loaded = load_saved_case(tmp_path)
    np.testing.assert_array_equal(loaded["states"][0], weights)
    corrupt = weights.copy()
    corrupt[0] += 1e-5
    write(corrupt)
    with pytest.raises(ValueError, match="Terminal CSV weights"):
        load_saved_case(tmp_path)


def test_work_cap_never_starts_extra_evaluation():
    budget = WorkBudget(max_evaluations=1, max_wall_seconds=10)
    budget.check("once", evaluation=True)
    with pytest.raises(DiagnosticBudgetExceeded, match="candidate_evaluation_cap"):
        budget.check("forbidden", evaluation=True)
    assert budget.operations == {"once": 1}


def test_field_repair_has_no_bem_and_restores_weights(monkeypatch):
    import sdf_inverse.forward as forward
    def forbidden(*args, **kwargs):
        raise AssertionError("Field-only repair must not evaluate BEM.")
    monkeypatch.setattr(forward, "predict_paired_response", forbidden)
    monkeypatch.setattr(forward, "predict_paired_curve_response", forbidden)
    model = ScaledDistance()
    controller = TorchParameterController(model, lower_bounds=-5, upper_bounds=5, max_parameters=1)
    original = controller.parameter_vector().copy()
    config = OrderedSDFGeometryConfig(bounds=((.3, .3), (.7, .7)), grid_shape=(33, 33),
        projected_samples=64, bandwidth=8, num_nodes=64, arclength_dense_resolution=128,
        validation_resolution=128, conversion_tolerance_m=2e-4,
        conversion_audit_grid_shape=(33, 33), conversion_audit_samples=64)
    result = field_only_repair(model, controller, config, WorkBudget(8, 30),
                              steps=3, learning_rate=.01, samples=32, maximum_mode=5)
    np.testing.assert_array_equal(controller.parameter_vector(), original)
    assert result["data_evaluations"] == result["kress_evaluations"] == 0
    assert result["after"]["field_gradient"]["maximum"] < result["before"]["field_gradient"]["maximum"]
    assert result["raw_maximum_set_movement_m"] < 1e-8


def test_field_repair_budget_failure_also_restores_weights(monkeypatch):
    import sdf_inverse.frozen_diagnostics as diagnostic
    model = ScaledDistance()
    controller = TorchParameterController(model, lower_bounds=-5, upper_bounds=5, max_parameters=1)
    original = controller.parameter_vector().copy()
    points, _ = circle()
    def fake_report(model, config, budget, **kwargs):
        q = field_quantities(model, points)
        return {"raw_zero_contour_m": points}, None, q
    monkeypatch.setattr(diagnostic, "report_geometry", fake_report)
    budget = WorkBudget(1, 30)
    original_check = budget.check
    count = 0
    def interrupt(operation=None, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise DiagnosticBudgetExceeded("test interruption")
        return original_check(operation, **kwargs)
    monkeypatch.setattr(budget, "check", interrupt)
    with pytest.raises(DiagnosticBudgetExceeded):
        field_only_repair(model, controller, None, budget, steps=3, samples=32)
    np.testing.assert_array_equal(controller.parameter_vector(), original)
