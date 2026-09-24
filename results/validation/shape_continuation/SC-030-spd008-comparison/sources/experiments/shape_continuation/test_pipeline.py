"""Physical controls and isolation for the new inverse, not legacy-driver tests."""
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from scipy.special import hankel1, h1vp, jv, jvp

from .forward import Acquisition, Work, solve, shape_jacobian
from .geometry import FourierCurve, curvature_tail, normal_basis, reparameterize, displaced
from .inverse import FitConfig, Observation, fit_frequency, run_continuation
from .schedule import Stage, paper_stage, paper_wavenumbers
from .metrics import boundary_distance, points_to_polygon_distance
from .validation import self_intersections


def ellipse(a=1.0, b=0.8):
    return FourierCurve(np.array([(a - b) / 2, 0j, (a + b) / 2]))


def circle_series(radius, k, contrast, acquisition):
    # Independent separation-of-variables solution for equal-density transmission.
    ki = k * np.sqrt(contrast)
    modes = np.arange(-40, 41)
    outer, inner = jv(modes, k * radius), jv(modes, ki * radius)
    a = ((ki * jvp(modes, ki * radius) * outer - k * jvp(modes, k * radius) * inner)
         / (k * h1vp(modes, k * radius) * inner - ki * jvp(modes, ki * radius) * hankel1(modes, k * radius)))
    theta = np.arctan2(acquisition.receivers[:, 1], acquisition.receivers[:, 0])
    alpha = np.arctan2(acquisition.directions[:, 1], acquisition.directions[:, 0])
    receiver = hankel1(modes[None, :], k * np.linalg.norm(acquisition.receivers, axis=1)[:, None])
    return np.einsum("dm,rm,m->dr", np.exp(-1j * alpha[:, None] * modes),
                     receiver * np.exp(1j * theta[:, None] * modes), 1j ** modes * a)


@pytest.mark.parametrize("k,contrast", [(1.0, 1.44), (3.0, 0.33), (2.0, 4.0), (1.0, 10.0)])
def test_plane_wave_forward_matches_independent_circle_series(k, contrast):
    acquisition = Acquisition.ring(7, 11)
    result = solve(FourierCurve.circle(0.85), k, contrast, acquisition, 96)
    expected = circle_series(0.85, k, contrast, acquisition)
    assert np.linalg.norm(result.prediction - expected) / np.linalg.norm(expected) < 1e-9
    assert result.system_residual < 1e-12


def test_zero_contrast_field_and_shape_derivative():
    state = solve(ellipse(), 2.0, 1.0, Acquisition.ring(3, 5), 64)
    assert np.max(np.abs(state.prediction)) < 1e-11
    assert np.max(np.abs(shape_jacobian(state, normal_basis(state.curve, 3)))) == 0


def test_arclength_reparameterization_preserves_ellipse_and_is_not_radial():
    shape, error = reparameterize(ellipse(), 32)
    nodes = shape.nodes(256)
    assert error < 1e-8
    assert np.ptp(nodes.speeds) / np.mean(nodes.speeds) < 1e-6
    assert np.max(np.abs((nodes.points[:, 0]) ** 2 + (nodes.points[:, 1] / .8) ** 2 - 1)) < 1e-7
    assert curvature_tail(FourierCurve.circle(), 1) < 1e-25
    assert curvature_tail(shape, 1) > curvature_tail(shape, 6)


def test_non_star_shaped_curve_is_supported():
    # A bent ellipse: x=cos(t)+.8*cos(2t), y=sin(t), simple but not
    # star-shaped about its Fourier mean (negative polar-angle derivative).
    curve = FourierCurve(np.array([.4, 0, 0, 1, .4], complex))
    nodes = curve.validate()
    cross = nodes.points[:, 0] * nodes.first_derivatives[:, 1] - nodes.points[:, 1] * nodes.first_derivatives[:, 0]
    assert np.min(cross) < 0
    # This tightly bent shape has a long arclength Fourier tail. A deliberately
    # underresolved refit must fail, rather than silently changing the boundary.
    with pytest.raises(ValueError, match="projection unresolved"):
        reparameterize(curve, 32)
    converted, _ = reparameterize(curve, 100, tolerance=1e-3)
    assert converted.validate().signed_area > 0


@pytest.mark.parametrize("nodes", [64, 128])
def test_normal_shape_jacobian_matches_rebuilt_forward(nodes):
    curve, _ = reparameterize(ellipse(), 24)
    acquisition = Acquisition.ring(5, 7)
    state = solve(curve, 2.0, 1.44, acquisition, nodes)
    basis = normal_basis(state.curve, 3)
    direction = np.array([.03, .04, -.02, .01, -.03, .02, .015])
    jac = shape_jacobian(state, basis)
    tangent = jac @ direction
    errors = []
    for step in (2e-3, 1e-3):
        plus = displaced(curve, direction, 32, step=step).shape
        minus = displaced(curve, direction, 32, step=-step).shape
        # Resolve the refitted geometry more finely for the FD control.
        fd = (solve(plus, 2., 1.44, acquisition, 128).prediction
              - solve(minus, 2., 1.44, acquisition, 128).prediction) / (2 * step)
        errors.append(np.linalg.norm(fd - tangent) / np.linalg.norm(tangent))
    assert errors[-1] < 2e-5
    assert errors[-1] < errors[0] * .8 + 1e-7


def test_step_size_measures_physical_filtered_motion_before_reparameterization():
    circle = FourierCurve.circle()
    coefficients = np.zeros(9)
    coefficients[4] = .01
    plain = displaced(circle, coefficients, 32)
    filtered = displaced(circle, coefficients, 32, filter_index=3)
    assert plain.rms_displacement == pytest.approx(.01 / np.sqrt(2), rel=1e-13)
    assert plain.maximum_displacement == pytest.approx(.01, rel=1e-13)
    # The update is a single cos(4t) harmonic at the band edge, which the
    # Gaussian removes: a raw coefficient norm of .01 would miss that the
    # resulting motion is negligible.
    assert filtered.rms_displacement < 1e-12
    assert filtered.maximum_displacement < 1e-12
    assert np.max(np.abs(filtered.shape.values(1024) - circle.values(1024))) < 1e-10


def test_inverse_stops_on_small_filtered_motion(monkeypatch):
    from . import inverse
    def require_filter(*args, **kwargs):
        if kwargs["filter_index"] < 2:
            raise ValueError("Controlled feasibility rejection of unfiltered proposals.")
        return displaced(*args, **kwargs)
    monkeypatch.setattr(inverse, "displaced", require_filter)
    acquisition = Acquisition.ring(10, 10)
    # An elliptical target needs a cos(2t) update, which the filter does damp;
    # the mean radius already matches, so no undamped constant term hides that.
    observation = Observation(1., acquisition,
                              solve(ellipse(), 1., 1.44, acquisition, 128).prediction)
    result = fit_frequency(FourierCurve.circle(.9), observation, Stage(1., 3, 16, 64, 2), 1.44,
        config=FitConfig(step_tolerance=.01, backtracks=0, max_iterations=3))
    last = result.history[-1]
    assert result.stop_reason == "small_step"
    assert len(result.states) == 2 and last["filter_index"] == 2
    assert last["update_norm"] < .01 < last["coefficient_step_norm"]
    assert result.relative_residual > 1e-5  # The stop does not claim a data fit.


def test_single_frequency_inverse_recovers_circle_and_preserves_observations():
    acquisition = Acquisition.ring(10, 10)
    truth = circle_series(.9, 1., 1.44, acquisition)
    observation = Observation(1., acquisition, truth)
    work = Work(max_forwards=80)
    result = fit_frequency(FourierCurve.circle(1.), observation,
        Stage(1., 3, 16, 64, 2), 1.44, config=FitConfig(max_iterations=12), work=work)
    assert result.stop_reason == "data_fit"
    assert result.relative_residual < 1e-5
    assert np.max(np.abs(np.abs(result.shape.values(128)) - .9)) < 1e-4
    assert np.array_equal(observation.scattered, truth)
    assert work.attempted == work.completed and work.failed == 0
    assert len(result.states) == len(result.history)
    assert result.states[-1] is result.shape
    assert all(b["relative_residual"] < a["relative_residual"] for a, b in zip(result.history, result.history[1:]))


def test_continuation_uses_separate_frequencies_and_warm_starts():
    acquisition = Acquisition.ring(10, 10)
    stages = [Stage(1., 3, 16, 64, 2), Stage(1.25, 4, 20, 64, 3)]
    data = [Observation(s.wavenumber, acquisition, circle_series(.9, s.wavenumber, 1.44, acquisition)) for s in stages]
    result = run_continuation(FourierCurve.circle(1.), data, stages, 1.44)
    assert len(result) == 2
    assert result[-1].stop_reason == "data_fit"
    expected = solve(result[0].shape, 1.25, 1.44, acquisition, 64).prediction
    expected_error = np.linalg.norm(expected - data[1].scattered) / np.linalg.norm(data[1].scattered)
    assert result[1].history[0]["relative_residual"] == pytest.approx(expected_error, abs=1e-13)
    with pytest.raises(ValueError, match="increasing"):
        run_continuation(FourierCurve.circle(), data[::-1], stages[::-1], 1.44)


def test_budget_exhaustion_and_schedule_validation():
    acquisition = Acquisition.ring(4, 5)
    obs = Observation(1., acquisition, circle_series(.9, 1., 1.44, acquisition))
    result = fit_frequency(FourierCurve.circle(), obs, Stage(1., 3, 16, 64, 2), 1.44,
                           work=Work(max_forwards=1))
    assert result.stop_reason == "budget_exhausted"
    assert np.array_equal(result.shape.coefficients[15:18], FourierCurve.circle().coefficients)
    with pytest.raises(ValueError, match="Even"):
        Stage(1., 3, 32, 64, 2)
    assert len(paper_wavenumbers()) == 117 and paper_wavenumbers()[-1] == 30
    stage = paper_stage(2, 4, 2 * np.pi)
    assert stage.update_modes == 12 and stage.curvature_modes == 4
    assert stage.nodes > 2 * stage.curve_modes


def test_clean_import_and_forward_never_load_legacy_inverse_or_torch():
    root = Path(__file__).resolve().parents[2]
    code = """
import sys
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.forward import Acquisition, solve
from experiments.shape_continuation.inverse import run_continuation
from experiments.shape_continuation.continuation import run_adaptive
from experiments.shape_continuation.paper import Figure1Case
solve(FourierCurve.circle(), 1., 1.44, Acquisition.ring(2,3), 32)
forbidden = ('sdf_inverse', 'sdf_to_ordered_boundary', 'gpr_bem_mod', 'gpr_bem_ref',
             'torch', 'solver_select', 'experiments.modal_muller_research')
assert not any(name == f or name.startswith(f+'.') for name in sys.modules for f in forbidden)
assert 'shapely' not in sys.modules  # Area scoring is evaluation-only and lazy.
"""
    environment = dict(os.environ, PYTHONPATH=f"{root / 'solvers'}:{root}")
    subprocess.run([sys.executable, "-c", code], env=environment, cwd=root, check=True, capture_output=True)


def test_geometry_metric_uses_segments_and_not_parameter_phase():
    square = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])
    assert np.allclose(points_to_polygon_distance(np.array([[.5, -.2], [.5, .5]]), square), [.2, .5])
    first = FourierCurve.circle()
    second = FourierCurve(first.coefficients * np.exp(1j * first.modes * .123))
    error, bound = boundary_distance(first, second)
    assert error < 1e-7 and bound > error


def test_sampling_bound_contains_known_continuous_hausdorff_distance():
    # z=exp(it)+.1 exp(7it) stays within .1 of the unit circle and attains
    # that distance at z=1.1. A phase shift changes samples, not this exact bound.
    coefficients = np.zeros(15, complex)
    coefficients[8], coefficients[14] = np.exp(.11j), .1 * np.exp(.77j)
    curve = FourierCurve(coefficients)
    bounds = []
    for count in (16, 64, 256):
        error, bound = boundary_distance(FourierCurve.circle(), curve, count=count)
        assert abs(error - .1) <= bound
        bounds.append(bound)
    assert bounds[0] > bounds[1] > bounds[2]
    assert abs(error - .1) < 1e-4


def test_cartesian_real_and_complex_fourier_forms_are_equivalent():
    from ordered_boundary import fourier_curve
    rng = np.random.default_rng(91)
    cosine, sine = rng.normal(size=(2, 5, 2))
    sine[0] = 0
    a = cosine[:, 0] + 1j * cosine[:, 1]
    b = sine[:, 0] + 1j * sine[:, 1]
    coefficients = np.r_[(a[1:] + 1j * b[1:])[::-1] / 2, a[0], (a[1:] - 1j * b[1:]) / 2]
    shape = FourierCurve(coefficients)
    expected = fourier_curve(cosine, sine, component_id="algebra").evaluate(2 * np.pi * np.arange(64) / 64).points
    assert np.allclose(shape.values(64), expected[:, 0] + 1j * expected[:, 1], atol=1e-13)


def test_spatial_intersection_pruning_matches_all_pairs_reference():
    from ordered_boundary import sampled_self_intersection_count
    rng = np.random.default_rng(873)
    polygons = [rng.normal(size=(n, 2)) for n in (3, 4, 8, 31, 64) for _ in range(8)]
    polygons += [np.array(p, float) for p in (
        [[0, 0], [1, 1], [0, 1], [1, 0]],
        [[0, 0], [2, 0], [1, 0], [1, 1]],
        [[0, 0], [1, 0], [1, 0], [1, 1], [0, 1]],
        [[0, 0], [0, 0], [0, 0]],
        [[0, 0], [1, 0], [.5, 1e-13], [.5, 1]],
        [[0, 0], [1, 0], [.5, 1e-10], [.5, 1]],
    )]
    for polygon in polygons:
        for scale, offset in ((1., 0.), (1e-3, 0.), (2., 1e6)):
            points = polygon * scale + offset
            for tolerance in (0., 1e-12, 1e-6):
                assert self_intersections(points, tolerance) == sampled_self_intersection_count(
                    points, relative_tolerance=tolerance)


def test_dense_geometry_checks_keep_the_same_sample_resolution():
    from .geometry import grid_size
    curve, _ = reparameterize(ellipse(), 48)
    assert curve.validate().num_nodes == grid_size(48) == 2048


def test_spectral_arclength_has_no_spline_integration_error_floor():
    from .geometry import arclength_angles
    curve = ellipse()
    coarse, length = arclength_angles(curve.nodes(64))
    fine, refined_length = arclength_angles(curve.nodes(1024))
    assert np.max(np.abs(coarse - fine[::16])) < 1e-13
    assert abs(length - refined_length) < 1e-13


def test_blocked_reciprocal_contraction_matches_literal_identity():
    from gpr_bem_kress import kress_incident_trace_on_boundary
    from scipy.linalg import lu_solve
    state = solve(ellipse(), 2., 1.44, Acquisition.ring(5, 7), 64)
    h = normal_basis(state.curve, 4)
    d, n = kress_incident_trace_on_boundary(state.curve, state.acquisition.receivers, state.wavenumber)
    reciprocal = lu_solve(state.factors, np.concatenate((d, n), axis=1).T)[:64]
    expected = (state.interior_wavenumber**2 - state.wavenumber**2) * np.einsum(
        'nr,np,nd,n->drp', reciprocal, h, state.traces[:64], state.curve.arc_length_weights)
    assert np.allclose(shape_jacobian(state, h), expected, rtol=2e-13, atol=2e-13)


def test_stage_policy_and_checkpoints_receive_only_current_geometry_and_stage():
    acquisition = Acquisition.ring(6, 7)
    observations = [Observation(k, acquisition, circle_series(.9, k, 1.44, acquisition)) for k in (1., 1.25)]
    called, saved = [], []
    def policy(shape, k, previous):
        called.append((shape.band, k, previous))
        return Stage(k, 3, 16 if previous is None else 20, 64, 3)
    result = run_continuation(FourierCurve.circle(), observations, policy, 1.44,
                              on_stage=lambda index, stage: saved.append((index, stage)))
    assert len(called) == len(result) == len(saved) == 2
    assert called[0][2] is None and called[1][2] is result[0].stage
    assert saved[-1] == (1, result[-1])
    assert result[-1].relative_residual < 1e-5


def test_restart_preserves_endpoint_and_checks_problem_identity(tmp_path):
    import json
    from .run import load_restart
    truth, final = ellipse(), FourierCurve.circle(.9)
    record = dict(contrast=1.44, stages=[dict(stage=dict(wavenumber=2.), stop_reason="budget_exhausted")],
                  inverse_work=dict(attempted=20), cumulative_inverse_forwards=35)
    (tmp_path / "summary.json").write_text(json.dumps(record))
    np.savez(tmp_path / "inputs.npz", truth=truth.coefficients)
    np.savez(tmp_path / "states.npz", stage_0=final.coefficients)
    shape, origin = load_restart(tmp_path, truth, 1.44, 2.)
    assert np.array_equal(shape.coefficients, final.coefficients)
    assert origin["prior_inverse_forwards"] == 35
    assert set(origin["sha256"]) == {"summary.json", "inputs.npz", "states.npz"}
    with pytest.raises(ValueError, match="contrast"):
        load_restart(tmp_path, truth, 2., 2.)
    with pytest.raises(ValueError, match="fixture"):
        load_restart(tmp_path, final, 1.44, 2.)
    with pytest.raises(ValueError, match="backwards"):
        load_restart(tmp_path, truth, 1.44, 1.5)


def test_field_convergence_alone_does_not_qualify_shape_jacobian():
    from .run import fixture, check_stage_resolution
    check = check_stage_resolution(fixture("glider"), Stage(8., 28, 48, 128, 16),
                                   1.44, Acquisition.ring(16, 19), Work())
    assert check["relative_difference"] < 1e-6
    assert check["jacobian_relative_difference"] > 1e-6
