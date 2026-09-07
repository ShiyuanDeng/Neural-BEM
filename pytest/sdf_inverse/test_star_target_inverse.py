"""Checks for the star target, its Nystrom observations, and its inverse seam.

The star is the first target in this pipeline whose observations cannot come
from a closed-form series.  These tests therefore cover three separate claims:
that the implicit model, the parameterization the oracle integrates, and the
reported geometry error all describe one curve; that the oracle is resolved
well enough to be treated as truth; and that the same solver-neutral inverse
recovers a wrong star.

Runtime is kept low deliberately: the resolutions here are smaller than the
driver's, so these are contract tests, not the accuracy evidence.  That lives
in the checked ``results/inverse_solver_comparison`` bundles.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import config.star_config as cfg
from nystrom_ref import star_parameterization
from sdf_inverse.forward import (
    MaterialSpec,
    PairedForwardProblem,
    predict_paired_response,
)
from sdf_inverse.geometry import OrderedSDFGeometryConfig, build_ordered_sdf_geometry
from sdf_inverse.models import (
    StarLevelSet2D,
    build_siren_parameter_controller,
    build_star_parameter_controller,
)
from sdf_inverse.nystrom_oracle import (
    nystrom_paired_response,
    nystrom_self_convergence,
)
from sdf_inverse.optimization import (
    ComplexScatteredData,
    ParameterFDConfig,
    run_parameter_fd_inverse,
)
from sdf_inverse.targets import StarShape
from run_sdf_inverse_comparison import (
    DEFAULT_STAR_AMPLITUDE_BOUNDS,
    DEFAULT_STAR_CENTER_BOUNDS,
    DEFAULT_STAR_MEAN_RADIUS_BOUNDS,
    DEFAULT_STAR_ROTATION_BOUNDS,
    CircleTarget,
    StarTarget,
    _build_initial_model,
    _contour_shape_summary,
    _build_target,
    _inverse_config_for_controller,
    _parse_args,
)


TARGET_CENTER = (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y))
TARGET_MEAN_RADIUS = float(cfg.TARGET_MEAN_RADIUS)
TARGET_AMPLITUDE = float(cfg.TARGET_STAR_AMPLITUDE)
TARGET_LOBES = int(cfg.TARGET_STAR_LOBES)


@pytest.fixture(scope="module")
def target_shape() -> StarShape:
    return StarShape(
        center=TARGET_CENTER,
        mean_radius=TARGET_MEAN_RADIUS,
        amplitude=TARGET_AMPLITUDE,
        lobes=TARGET_LOBES,
    )


@pytest.fixture(scope="module")
def star_problem() -> PairedForwardProblem:
    """Six paired ring observations at the driver's two training frequencies."""

    angles = np.linspace(0.0, 2.0 * np.pi, 6, endpoint=False, dtype=np.float64)
    standoff = 0.30
    separation = float(cfg.TX_RX_OFFSET) / standoff
    sources = np.column_stack(
        (
            TARGET_CENTER[0] + standoff * np.cos(angles),
            TARGET_CENTER[1] + standoff * np.sin(angles),
        )
    )
    receivers = np.column_stack(
        (
            TARGET_CENTER[0] + standoff * np.cos(angles + separation),
            TARGET_CENTER[1] + standoff * np.sin(angles + separation),
        )
    )
    return PairedForwardProblem(
        source_points=sources,
        receiver_points=receivers,
        angular_frequencies=2.0 * np.pi * np.array([0.5e9, 1.5e9]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA),
        interior=MaterialSpec(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA),
        eps0=float(cfg.EPS0),
        mu0=float(cfg.MU0),
    )


@pytest.fixture(scope="module")
def coarse_geometry_config() -> OrderedSDFGeometryConfig:
    """A cheap star fit: enough bandwidth to be a star, not enough to be exact."""

    # The validation resolution is not merely the ``2 * bandwidth + 2``
    # minimum the config enforces: Method B's derivative-consistency check
    # needs roughly twenty samples per retained Fourier mode, and a
    # bandwidth-24 star fit is rejected outright at 256 samples.
    return OrderedSDFGeometryConfig(
        bounds=((0.30, 0.30), (0.70, 0.70)),
        grid_shape=(129, 129),
        projected_samples=64,
        bandwidth=24,
        num_nodes=64,
        arclength_dense_resolution=1024,
        validation_resolution=512,
    )


def test_star_level_set_matches_the_analytic_contour_and_stays_total() -> None:
    rotation = 0.3
    model = StarLevelSet2D(
        center=TARGET_CENTER,
        mean_radius=TARGET_MEAN_RADIUS,
        amplitude=TARGET_AMPLITUDE,
        lobes=TARGET_LOBES,
        rotation_radians=rotation,
        dtype=torch.float64,
    )
    angles = np.linspace(0.0, 2.0 * np.pi, 97, dtype=np.float64)
    radii = TARGET_MEAN_RADIUS * (
        1.0 + TARGET_AMPLITUDE * np.cos(TARGET_LOBES * (angles - rotation))
    )
    contour = np.column_stack(
        (
            TARGET_CENTER[0] + radii * np.cos(angles),
            TARGET_CENTER[1] + radii * np.sin(angles),
        )
    )
    values = model(torch.as_tensor(contour)).detach().numpy().reshape(-1)
    assert np.max(np.abs(values)) < 1.0e-15

    inside = model(torch.as_tensor(np.array([TARGET_CENTER]))).item()
    assert inside < 0.0

    # The extraction grid can contain the exact center, so the field and its
    # point gradient must both be finite there.
    probes = torch.as_tensor(
        np.vstack((np.array([TARGET_CENTER]), contour[:8])), dtype=torch.float64
    ).requires_grad_(True)
    gradients = torch.autograd.grad(model(probes).sum(), probes)[0]
    assert torch.isfinite(gradients).all()

    contour_probes = torch.as_tensor(contour, dtype=torch.float64).requires_grad_(True)
    contour_gradients = torch.autograd.grad(model(contour_probes).sum(), contour_probes)[0]
    norms = contour_gradients.detach().numpy()
    norms = np.linalg.norm(norms, axis=1)
    # A star level set is not a signed distance; the pipeline must not assume it is.
    assert np.max(np.abs(norms - 1.0)) > 5.0e-2
    assert model.claims_signed_distance is False


def test_star_shape_is_the_oracle_curve_and_measures_exact_distance(
    target_shape: StarShape,
) -> None:
    parameters = np.linspace(0.0, 2.0 * np.pi, 512, endpoint=False)
    points, tangents = target_shape.boundary(parameters)
    oracle_points, oracle_tangents = star_parameterization(
        TARGET_CENTER, TARGET_MEAN_RADIUS, TARGET_AMPLITUDE, TARGET_LOBES
    )(parameters)
    # Bit-for-bit, so the inverse target and the forward study's target are one
    # curve rather than two independently coded formulas.
    np.testing.assert_array_equal(points, oracle_points)
    np.testing.assert_array_equal(tangents, oracle_tangents)

    assert np.max(target_shape.distance_to_boundary(points[::7])) < 1.0e-12

    normals = np.column_stack((tangents[:, 1], -tangents[:, 0]))
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    for offset in (1.0e-4, 1.0e-3, 5.0e-3):
        distances = target_shape.distance_to_boundary(
            points[::7] + offset * normals[::7]
        )
        assert np.max(np.abs(distances - offset)) < 1.0e-12

    # The amplitude -> 0 limit must reproduce the analytic circle distance.
    nearly_circular = StarShape(
        center=TARGET_CENTER,
        mean_radius=TARGET_MEAN_RADIUS,
        amplitude=1.0e-12,
        lobes=TARGET_LOBES,
    )
    probes = np.array([[0.5, 0.57], [0.53, 0.53], [0.5, 0.5]])
    expected = np.abs(
        np.linalg.norm(probes - np.asarray(TARGET_CENTER), axis=1) - TARGET_MEAN_RADIUS
    )
    np.testing.assert_allclose(
        nearly_circular.distance_to_boundary(probes), expected, atol=1.0e-12
    )

    model_values = (
        target_shape.implicit_model()(torch.as_tensor(points[::7])).detach().numpy()
    )
    assert np.max(np.abs(model_values)) < 1.0e-15


def test_star_controller_bounds_reject_unidentifiable_configurations() -> None:
    model = StarLevelSet2D(
        center=(0.48, 0.52),
        mean_radius=0.06,
        amplitude=0.12,
        lobes=TARGET_LOBES,
        rotation_radians=0.25,
        dtype=torch.float64,
    )
    controller = build_star_parameter_controller(
        model,
        center_bounds=DEFAULT_STAR_CENTER_BOUNDS,
        mean_radius_bounds=DEFAULT_STAR_MEAN_RADIUS_BOUNDS,
        amplitude_bounds=DEFAULT_STAR_AMPLITUDE_BOUNDS,
        rotation_bounds=DEFAULT_STAR_ROTATION_BOUNDS,
    )
    assert controller.names == (
        "center_x",
        "center_y",
        "log_mean_radius",
        "amplitude",
        "rotation",
    )
    np.testing.assert_allclose(
        controller.parameter_vector(),
        np.array([0.48, 0.52, math.log(0.06), 0.12, 0.25]),
        rtol=0.0,
        atol=1.0e-15,
    )
    controller.assign(np.array([0.5, 0.5, math.log(0.05), 0.25, 0.0]))
    physical = controller.physical_parameter_dict()
    assert physical["amplitude"] == pytest.approx(0.25)
    assert physical["rotation_radians"] == pytest.approx(0.0)
    assert physical["radius"] == pytest.approx(physical["mean_radius"])

    with pytest.raises(ValueError, match="identifiable"):
        build_star_parameter_controller(
            model,
            center_bounds=DEFAULT_STAR_CENTER_BOUNDS,
            mean_radius_bounds=DEFAULT_STAR_MEAN_RADIUS_BOUNDS,
            amplitude_bounds=(0.0, 0.35),
            rotation_bounds=DEFAULT_STAR_ROTATION_BOUNDS,
        )
    with pytest.raises(ValueError, match="symmetry period"):
        build_star_parameter_controller(
            model,
            center_bounds=DEFAULT_STAR_CENTER_BOUNDS,
            mean_radius_bounds=DEFAULT_STAR_MEAN_RADIUS_BOUNDS,
            amplitude_bounds=DEFAULT_STAR_AMPLITUDE_BOUNDS,
            rotation_bounds=(-0.7, 0.7),
        )


def test_nystrom_observations_are_resolved_and_linear_in_the_source(
    star_problem: PairedForwardProblem, target_shape: StarShape
) -> None:
    convergence = nystrom_self_convergence(
        star_problem, target_shape.parameterization(), num_nodes=256
    )
    assert convergence["coarse_num_nodes"] == 128
    assert convergence["maximum_relative_difference"] < 1.0e-8
    assert convergence["fine"]["maximum_linear_system_relative_residual"] < 1.0e-10
    assert convergence["fine"]["maximum_incident_consistency"] < 1.0e-10

    unit = nystrom_paired_response(
        star_problem, target_shape.parameterization(), num_nodes=128
    )
    assert unit.scattered_response.shape == (star_problem.num_pairs, 2)
    scaled_problem = PairedForwardProblem(
        source_points=star_problem.source_points,
        receiver_points=star_problem.receiver_points,
        angular_frequencies=star_problem.angular_frequencies,
        source_strengths=np.array([2.0e-6 + 0.0j, -1.0e-6 + 3.0e-6j]),
        exterior=star_problem.exterior,
        interior=star_problem.interior,
        eps0=star_problem.eps0,
        mu0=star_problem.mu0,
    )
    scaled = nystrom_paired_response(
        scaled_problem, target_shape.parameterization(), num_nodes=128
    )
    expected = unit.scattered_response * np.asarray(
        scaled_problem.source_strengths
    )[None, :]
    np.testing.assert_allclose(
        scaled.scattered_response, expected, rtol=1.0e-13, atol=0.0
    )

    with pytest.raises(ValueError, match="even"):
        nystrom_paired_response(
            star_problem, target_shape.parameterization(), num_nodes=127
        )


def test_fitted_star_reaches_both_solvers_and_agrees_with_the_oracle(
    star_problem: PairedForwardProblem,
    target_shape: StarShape,
    coarse_geometry_config: OrderedSDFGeometryConfig,
) -> None:
    exact = nystrom_paired_response(
        star_problem, target_shape.parameterization(), num_nodes=256
    ).scattered_response
    model = target_shape.implicit_model()
    results = {
        solver: predict_paired_response(
            model, star_problem, coarse_geometry_config, solver=solver
        )
        for solver in ("mod", "kress")
    }
    np.testing.assert_allclose(
        results["mod"].geometry_build.curve.points,
        results["kress"].geometry_build.curve.points,
        atol=0.0,
        rtol=0.0,
    )

    nodes = np.asarray(results["kress"].geometry_build.curve.points)
    # The bandwidth-24 arc-length Fourier truncation, not the extraction grid,
    # sets this floor; see the driver's star geometry configuration.
    assert np.max(target_shape.distance_to_boundary(nodes)) < 5.0e-4

    errors = {
        solver: float(
            np.linalg.norm(result.scattered_response - exact)
            / np.linalg.norm(exact)
        )
        for solver, result in results.items()
    }
    assert errors["kress"] < 1.0e-3, errors
    assert errors["kress"] < errors["mod"], errors


@pytest.fixture(scope="module")
def star_observations(
    star_problem: PairedForwardProblem, target_shape: StarShape
) -> np.ndarray:
    return nystrom_paired_response(
        star_problem, target_shape.parameterization(), num_nodes=256
    ).scattered_response


def test_wrong_star_inverse_reduces_the_objective_and_the_geometry_error(
    star_problem: PairedForwardProblem,
    star_observations: np.ndarray,
    target_shape: StarShape,
    coarse_geometry_config: OrderedSDFGeometryConfig,
) -> None:
    data = ComplexScatteredData(star_problem, star_observations)
    model, controller = _build_initial_model("star")
    initial_distance = float(
        np.max(
            target_shape.distance_to_boundary(
                np.asarray(
                    build_ordered_sdf_geometry(model, coarse_geometry_config).curve.points
                )
            )
        )
    )

    result = run_parameter_fd_inverse(
        model,
        controller,
        data,
        coarse_geometry_config,
        solver="kress",
        config=_inverse_config_for_controller(controller, max_iterations=4),
    )
    losses = [item.loss for item in result.iterations]
    assert losses == sorted(losses, reverse=True)
    assert result.final_iteration.loss < 0.5 * result.initial_iteration.loss

    final_distance = float(
        np.max(
            target_shape.distance_to_boundary(
                np.asarray(
                    build_ordered_sdf_geometry(model, coarse_geometry_config).curve.points
                )
            )
        )
    )
    assert final_distance < 0.8 * initial_distance

    # Only the objective is monotone.  Four iterations of the approach phase
    # are measured to raise the mean radius and to overshoot the lobe phase
    # before the fit closes, so per-control progress is not asserted here; the
    # converged recovery is the driver's gated evidence.


def test_lobe_depth_and_phase_are_recoverable_from_the_same_objective(
    star_problem: PairedForwardProblem,
    star_observations: np.ndarray,
    coarse_geometry_config: OrderedSDFGeometryConfig,
) -> None:
    """The two controls a circle or an ellipse target cannot exercise at all."""

    initial_amplitude = 0.19
    initial_rotation = 0.12
    model = StarLevelSet2D(
        center=TARGET_CENTER,
        mean_radius=TARGET_MEAN_RADIUS,
        amplitude=initial_amplitude,
        lobes=TARGET_LOBES,
        rotation_radians=initial_rotation,
        dtype=torch.float64,
        device="cpu",
    )
    controller = build_star_parameter_controller(
        model,
        center_bounds=DEFAULT_STAR_CENTER_BOUNDS,
        mean_radius_bounds=DEFAULT_STAR_MEAN_RADIUS_BOUNDS,
        amplitude_bounds=DEFAULT_STAR_AMPLITUDE_BOUNDS,
        rotation_bounds=DEFAULT_STAR_ROTATION_BOUNDS,
    )
    result = run_parameter_fd_inverse(
        model,
        controller,
        ComplexScatteredData(star_problem, star_observations),
        coarse_geometry_config,
        solver="kress",
        config=_inverse_config_for_controller(controller, max_iterations=3),
    )
    assert result.final_iteration.loss < 1.0e-5 * result.initial_iteration.loss

    physical = controller.physical_parameter_dict()
    amplitude_error = abs(physical["amplitude"] - TARGET_AMPLITUDE)
    rotation_error = abs(physical["rotation_radians"])
    assert amplitude_error < 1.0e-3
    assert rotation_error < 1.0e-3
    assert amplitude_error < 0.1 * abs(initial_amplitude - TARGET_AMPLITUDE)
    assert rotation_error < 0.1 * initial_rotation


def test_driver_targets_expose_consistent_defaults_and_gates() -> None:
    circle = _build_target("circle")
    star = _build_target("star")
    assert isinstance(circle, CircleTarget) and isinstance(star, StarTarget)
    assert star.default_initial_model == "star"
    assert star.default_num_nodes >= 2 * star.bandwidth + 2
    assert star.center == TARGET_CENTER
    assert star.reference_radius == TARGET_MEAN_RADIUS
    assert "nystrom" in star.truth_oracle.lower()
    assert circle.oracle_diagnostics(None) is None

    gate_names = {key for key, _threshold, _requirement in star.shape_error_gates()}
    assert gate_names == {
        "final_center_error_m",
        "final_radius_error_m",
        "final_amplitude_error",
        "final_rotation_error_radians",
    }
    polyline = star.exact_boundary_polyline(256)
    errors = star.shape_errors(
        {
            "center_x": TARGET_CENTER[0],
            "center_y": TARGET_CENTER[1],
            "radius": TARGET_MEAN_RADIUS,
            "amplitude": TARGET_AMPLITUDE,
            "rotation_radians": 0.0,
        },
        polyline,
    )
    assert set(errors) == gate_names
    assert max(errors.values()) == 0.0

    # The same four numbers must also be recoverable from a contour alone,
    # which is the only route open to a field with no shape parameters.
    fitted = star.shape_errors({}, polyline)
    assert set(fitted) == gate_names
    assert max(fitted.values()) < 1.0e-6
    assert star.shape_measurement_source({}) == "contour"

    assert polyline.shape == (256, 2)
    assert np.max(star.boundary_distances(polyline)) < 1.0e-12


def test_driver_arguments_follow_the_selected_target(tmp_path) -> None:
    circle_arguments = _parse_args([])
    assert circle_arguments.target == "circle"
    assert circle_arguments.initial_model == "circle"
    assert circle_arguments.train_ghz == (0.25, 0.50)
    assert circle_arguments.num_nodes == 64

    star_arguments = _parse_args(["--target", "star"])
    assert star_arguments.initial_model == "star"
    assert star_arguments.train_ghz == (0.50, 1.50)
    assert star_arguments.holdout_ghz == (0.25, 1.0, 2.5)
    assert star_arguments.num_nodes == 128
    assert "star-nystrom" in str(star_arguments.output_dir)
    assert not set(star_arguments.train_ghz) & set(star_arguments.holdout_ghz)

    overridden = _parse_args(
        ["--target", "star", "--train-ghz", "2.0", "--num-nodes", "160"]
    )
    assert overridden.train_ghz == (2.0,)
    assert overridden.num_nodes == 160
    # An override that collides with the target's default holdout band is an
    # error rather than a silently overlapping train/test split.
    with pytest.raises(SystemExit):
        _parse_args(["--target", "star", "--train-ghz", "1.0"])

    with pytest.raises(SystemExit):
        _parse_args(["--target", "star", "--initial-model", "ellipse"])
    with pytest.raises(SystemExit):
        _parse_args(["--target", "circle", "--initial-model", "star"])
    # A star needs more nodes than a circle to sample its bandwidth-48 fit.
    with pytest.raises(SystemExit):
        _parse_args(["--target", "star", "--num-nodes", "64"])


def test_infeasible_trials_are_rejected_only_when_the_policy_says_so(
    star_problem: PairedForwardProblem,
    star_observations: np.ndarray,
    coarse_geometry_config: OrderedSDFGeometryConfig,
    monkeypatch,
) -> None:
    """A neural field's zero set can split; a bounded parametric one cannot.

    The default policy must keep propagating the geometry error, because for
    the parametric models a lost contour means the bounds were chosen wrongly
    and should not be silently absorbed.
    """

    from sdf_inverse import forward as forward_module
    from sdf_inverse.geometry import OrderedSDFGeometryError
    from sdf_inverse.optimization import _ObjectiveEvaluator

    assert ParameterFDConfig().infeasible_trial_policy == "error"
    assert ParameterFDConfig(
        infeasible_trial_policy="reject"
    ).infeasible_trial_policy == "reject"
    with pytest.raises(ValueError, match="infeasible_trial_policy"):
        ParameterFDConfig(infeasible_trial_policy="ignore")

    def explode(*_args, **_kwargs):
        raise OrderedSDFGeometryError("no admissible single zero contour")

    monkeypatch.setattr(forward_module, "predict_paired_response", explode)
    model, controller = _build_initial_model("star")
    data = ComplexScatteredData(star_problem, star_observations)
    parameters = controller.parameter_vector()

    strict = _ObjectiveEvaluator(
        model, controller, data, coarse_geometry_config, "kress"
    )
    with pytest.raises(OrderedSDFGeometryError):
        strict.evaluate(parameters)

    lenient = _ObjectiveEvaluator(
        model,
        controller,
        data,
        coarse_geometry_config,
        "kress",
        infeasible_trial_policy="reject",
    )
    evaluation = lenient.evaluate(parameters)
    assert evaluation.feasible is False
    assert evaluation.loss == float("inf")
    assert evaluation.forward_result is None
    assert lenient.infeasible_trial_count == 1
    # An infinite objective can never beat an accepted one, so the ordinary
    # line search rejects it without any special case.
    assert not evaluation.loss < 1.0


def test_neural_initialization_is_deterministic_and_topology_valid(
    coarse_geometry_config: OrderedSDFGeometryConfig,
) -> None:
    """The warm start is a precondition, so it must be reproducible."""

    first, first_controller = _build_initial_model("siren_circle")
    second, _ = _build_initial_model("siren_circle")
    np.testing.assert_array_equal(
        first_controller.parameter_vector(),
        build_siren_parameter_controller(second).parameter_vector(),
    )
    assert first.claims_signed_distance is False
    assert first_controller.num_parameters == first.num_network_parameters

    report = first.initialization_metadata()["pretraining"]
    assert report["final_data_rms_m"] < 1.0e-2
    assert report["final_data_rms_m"] < 0.1 * report["initial_data_rms_m"]

    build = build_ordered_sdf_geometry(first, coarse_geometry_config)
    points = np.asarray(build.curve.points)
    # The Eikonal penalty is the only reason this field is distance-like.
    probes = torch.tensor(points, dtype=torch.float64).requires_grad_(True)
    gradients = torch.autograd.grad(first(probes).sum(), probes)[0]
    norms = np.linalg.norm(gradients.detach().numpy(), axis=1)
    assert np.max(np.abs(norms - 1.0)) < 0.25

    # A neural field has no shape controls, so its geometry must be readable
    # from the contour instead.
    summary = _contour_shape_summary(points)
    assert math.hypot(summary["center_x"] - 0.48, summary["center_y"] - 0.52) < 5.0e-3
    assert abs(summary["radius"] - 0.065) < 5.0e-3
