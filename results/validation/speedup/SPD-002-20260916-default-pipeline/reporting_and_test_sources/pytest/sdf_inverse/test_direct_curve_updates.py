"""Contracts for direct normal-mode curve updates and accepted-state remeshing."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ordered_boundary import circle, ellipse, sampled_self_intersection_count
from sdf_inverse.curve_updates import (
    apply_radial_fourier_update,
    apply_normal_mode_update,
    fit_radial_fourier_curve_state,
    radial_fourier_displacement_basis,
    radial_fourier_state_curve,
    smooth_normal_mode_values,
)
from sdf_inverse.geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from sdf_inverse.neural_optimization import (
    SmoothNormalModeUpdate2D,
    radial_spectral_tail_rms,
)


def _geometry_config(*, num_nodes: int = 64, bandwidth: int = 8):
    return OrderedSDFGeometryConfig(
        bounds=((-0.2, -0.2), (0.2, 0.2)),
        grid_shape=(33, 33),
        projected_samples=max(32, 2 * bandwidth + 1),
        bandwidth=bandwidth,
        num_nodes=num_nodes,
        arclength_dense_resolution=256,
        validation_resolution=256,
    )


def test_numpy_mode_values_match_the_existing_torch_search_basis() -> None:
    class ZeroField(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.anchor = torch.nn.Parameter(torch.zeros((), dtype=torch.float64))

        def forward(self, points):
            return self.anchor + torch.zeros(
                (points.shape[0], 1), dtype=points.dtype, device=points.device
            )

    rng = np.random.default_rng(19)
    points = np.vstack((np.array([[0.03, -0.02]]), rng.uniform(-0.1, 0.1, (31, 2))))
    center = np.array([0.03, -0.02])
    scale = 0.071
    maximum_mode = 5
    model = ZeroField()
    torch_basis = SmoothNormalModeUpdate2D(
        model,
        center=center,
        radius_scale=scale,
        maximum_mode=maximum_mode,
        coefficients=np.zeros(1 + 2 * maximum_mode),
    ).mode_values(torch.as_tensor(points, dtype=torch.float64))
    numpy_basis = smooth_normal_mode_values(
        points,
        center=center,
        radius_scale=scale,
        maximum_mode=maximum_mode,
    )

    np.testing.assert_allclose(
        numpy_basis,
        torch_basis.detach().cpu().numpy(),
        rtol=2.0e-15,
        atol=2.0e-15,
    )
    assert not numpy_basis.flags.writeable


def test_positive_constant_coefficient_expands_circle_in_metres_and_preserves_phase() -> None:
    config = _geometry_config()
    radius = 0.05
    outward_step = 3.0e-3
    original = circle((0.0, 0.0), radius).discretize(
        config.num_nodes, require_even=True
    )
    coefficients = np.zeros(5)
    coefficients[0] = outward_step

    update = apply_normal_mode_update(
        original,
        coefficients,
        center=(0.0, 0.0),
        radius_scale=radius,
        maximum_mode=2,
        geometry_config=config,
    )

    assert update.curve.num_nodes == original.num_nodes
    np.testing.assert_array_equal(update.curve.parameters, original.parameters)
    np.testing.assert_allclose(
        np.linalg.norm(update.curve.points, axis=1),
        radius + outward_step,
        rtol=0.0,
        atol=2.0e-16,
    )
    np.testing.assert_allclose(
        update.requested_normal_displacement_m,
        outward_step,
        rtol=0.0,
        atol=2.0e-18,
    )
    np.testing.assert_allclose(
        update.realized_normal_displacement_m,
        outward_step,
        rtol=0.0,
        atol=2.0e-16,
    )
    assert update.maximum_requested_displacement_m == pytest.approx(outward_step)
    assert update.maximum_normal_displacement_error_m < 2.0e-16
    assert update.maximum_tangential_displacement_m < 2.0e-16
    assert update.curve.signed_area > original.signed_area
    assert update.curve.provenance.source_kind == "direct_normal_mode_update"


def test_angular_coefficient_has_local_outward_sign_and_exact_normal_scaling() -> None:
    config = _geometry_config(bandwidth=8)
    radius = 0.06
    amplitude = 1.5e-3
    maximum_mode = 3
    original = circle((0.0, 0.0), radius).discretize(
        config.num_nodes, require_even=True
    )
    coefficients = np.zeros(1 + 2 * maximum_mode)
    # Ordering is [constant, cos(1t), sin(1t), ..., cos(3t), sin(3t)].
    coefficients[2 * maximum_mode - 1] = amplitude

    update = apply_normal_mode_update(
        original,
        coefficients,
        center=(0.0, 0.0),
        radius_scale=radius,
        maximum_mode=maximum_mode,
        geometry_config=config,
    )
    angles = original.parameters
    expected = amplitude * np.cos(maximum_mode * angles)

    np.testing.assert_allclose(
        update.requested_normal_displacement_m,
        expected,
        rtol=0.0,
        atol=3.0e-18,
    )
    np.testing.assert_allclose(
        update.realized_normal_displacement_m,
        expected,
        rtol=0.0,
        atol=3.0e-16,
    )
    # At phase zero positive means outward; half a lobe later it means inward.
    assert update.realized_normal_displacement_m[0] == pytest.approx(amplitude)
    half_lobe_index = int(round(config.num_nodes / (2 * maximum_mode)))
    assert update.realized_normal_displacement_m[half_lobe_index] < -0.95 * amplitude
    assert update.maximum_tangential_displacement_m < 3.0e-16


def test_non_circular_update_is_bandlimited_and_audits_refit_error() -> None:
    config = _geometry_config(num_nodes=96, bandwidth=12)
    original = ellipse((0.01, -0.015), 0.075, 0.045, rotation=0.31).discretize(
        config.num_nodes, require_even=True
    )
    center = np.mean(original.points, axis=0)
    scale = float(np.mean(np.linalg.norm(original.points - center, axis=1)))
    coefficients = np.array(
        [0.4, -0.2, 0.3, 0.1, -0.05, 0.2, 0.1], dtype=np.float64
    ) * 1.0e-3

    update = apply_normal_mode_update(
        original,
        coefficients,
        center=center,
        radius_scale=scale,
        maximum_mode=3,
        geometry_config=config,
    )

    assert update.fourier_refit_rms_m < 1.0e-6
    assert update.fourier_refit_maximum_m < 2.0e-6
    assert update.maximum_normal_displacement_error_m <= update.fourier_refit_maximum_m
    assert update.maximum_tangential_displacement_m <= update.fourier_refit_maximum_m
    assert update.curve.orientation == "counterclockwise"
    np.testing.assert_array_equal(update.curve.parameters, original.parameters)


def test_invalid_direct_trial_is_reported_as_inverse_geometry_error() -> None:
    config = _geometry_config()
    radius = 0.05
    original = circle((0.0, 0.0), radius).discretize(
        config.num_nodes, require_even=True
    )
    coefficients = np.zeros(3)
    coefficients[0] = 0.20

    with pytest.raises(OrderedSDFGeometryError, match="bounds"):
        apply_normal_mode_update(
            original,
            coefficients,
            center=(0.0, 0.0),
            radius_scale=radius,
            maximum_mode=1,
            geometry_config=config,
        )


def test_probe_mode_skips_only_the_dense_continuous_validation(monkeypatch) -> None:
    import sdf_inverse.curve_updates as updates_module

    config = _geometry_config()
    original = circle((0.0, 0.0), 0.05).discretize(
        config.num_nodes, require_even=True
    )

    def forbidden_dense_validation(*args, **kwargs):
        del args, kwargs
        raise AssertionError("dense validation entered a finite-difference probe")

    monkeypatch.setattr(
        updates_module,
        "validate_periodic_parameterization",
        forbidden_dense_validation,
    )
    update = apply_normal_mode_update(
        original,
        np.array([1.0e-3, 0.0, 0.0]),
        center=(0.0, 0.0),
        radius_scale=0.05,
        maximum_mode=1,
        geometry_config=config,
        full_validation=False,
    )

    assert update.curve.num_nodes == original.num_nodes
    assert sampled_self_intersection_count(update.curve.points) == 0


def test_full_validation_passes_fourier_bandwidth_to_derivative_audit(
    monkeypatch,
) -> None:
    import sdf_inverse.curve_updates as updates_module

    config = _geometry_config(num_nodes=128, bandwidth=48)
    original = circle((0.0, 0.0), 0.05).discretize(
        config.num_nodes,
        require_even=True,
    )
    observed = {}
    real_validation = updates_module.validate_periodic_parameterization

    def capture_validation(parameterization, validation_config, **kwargs):
        observed["topology_samples"] = validation_config.num_samples_per_component
        observed["derivative_samples"] = (
            validation_config.derivative_samples_per_component
        )
        observed["fourier_bandwidth"] = validation_config.fourier_bandwidth
        return real_validation(parameterization, validation_config, **kwargs)

    monkeypatch.setattr(
        updates_module,
        "validate_periodic_parameterization",
        capture_validation,
    )
    apply_normal_mode_update(
        original,
        np.array([1.0e-4, 0.0, 0.0]),
        center=(0.0, 0.0),
        radius_scale=0.05,
        maximum_mode=1,
        geometry_config=config,
        full_validation=True,
    )

    assert observed == {
        "topology_samples": 256,
        "derivative_samples": 2048,
        "fourier_bandwidth": 48,
    }


def test_arclength_refit_preserves_probe_geometry_and_mode_fidelity() -> None:
    from sdf_inverse.neural_optimization import maximum_curve_set_distance

    config = _geometry_config(num_nodes=64, bandwidth=8)
    original = ellipse((0.01, -0.015), 0.075, 0.045, rotation=0.31).discretize(
        config.num_nodes, require_even=True
    )
    center = np.array([0.01, -0.015])
    radius_scale = 0.06
    coefficients = np.array(
        [0.1, 0.5, 0.2, 0.3, -0.4, 0.6, 0.2], dtype=np.float64
    ) * 3.0e-4

    probe = apply_normal_mode_update(
        original,
        coefficients,
        center=center,
        radius_scale=radius_scale,
        maximum_mode=3,
        geometry_config=config,
        full_validation=False,
    )
    accepted = apply_normal_mode_update(
        original,
        coefficients,
        center=center,
        radius_scale=radius_scale,
        maximum_mode=3,
        geometry_config=config,
        full_validation=True,
        reparameterize_arclength=True,
    )

    np.testing.assert_array_equal(accepted.curve.parameters, probe.curve.parameters)
    assert accepted.curve.orientation == probe.curve.orientation == original.orientation
    np.testing.assert_array_equal(
        accepted.realized_normal_displacement_m,
        probe.realized_normal_displacement_m,
    )
    np.testing.assert_array_equal(
        accepted.realized_tangential_displacement_m,
        probe.realized_tangential_displacement_m,
    )
    assert accepted.fourier_refit_rms_m == probe.fourier_refit_rms_m
    assert accepted.fourier_refit_maximum_m == probe.fourier_refit_maximum_m
    assert accepted.arclength_refit_maximum_m > 0.0
    assert accepted.arclength_speed_ratio_before > 1.6
    assert accepted.arclength_speed_ratio_after < 1.03
    # Both fits represent the same displaced geometric image; only their node
    # distribution differs.  The seam remains tied to the original index zero.
    assert (
        maximum_curve_set_distance(accepted.curve.points, probe.curve.points)
        < 3.0 * accepted.arclength_refit_maximum_m
    )
    assert (
        np.linalg.norm(accepted.curve.points[0] - probe.curve.points[0])
        <= accepted.arclength_refit_maximum_m
    )


def test_repeated_accepted_updates_retain_near_uniform_curve_speed() -> None:
    config = _geometry_config(num_nodes=64, bandwidth=8)
    center = np.array([0.01, -0.015])
    radius_scale = 0.06
    raw_curve = ellipse(
        center, 0.075, 0.045, rotation=0.31
    ).discretize(config.num_nodes, require_even=True)
    coefficients = np.array(
        [0.0, 0.5, 0.2, 0.3, -0.4, 0.6, 0.2], dtype=np.float64
    ) * 3.0e-4
    curve = apply_normal_mode_update(
        raw_curve,
        np.zeros_like(coefficients),
        center=center,
        radius_scale=radius_scale,
        maximum_mode=3,
        geometry_config=config,
        reparameterize_arclength=True,
    ).curve

    for _ in range(20):
        update = apply_normal_mode_update(
            curve,
            coefficients,
            center=center,
            radius_scale=radius_scale,
            maximum_mode=3,
            geometry_config=config,
            reparameterize_arclength=True,
        )
        assert update.arclength_speed_ratio_after < 1.02
        assert update.curve.orientation == raw_curve.orientation
        curve = update.curve

    assert float(np.max(curve.speeds) / np.min(curve.speeds)) < 1.02


def test_radial_fourier_projection_has_exact_zero_retraction_and_no_tail() -> None:
    config = _geometry_config(num_nodes=128, bandwidth=12)
    original = ellipse(
        (0.01, -0.015), 0.075, 0.045, rotation=0.31
    ).discretize(config.num_nodes, require_even=True)
    state = fit_radial_fourier_curve_state(original, maximum_mode=5)
    projected = radial_fourier_state_curve(state, geometry_config=config)
    zero = apply_radial_fourier_update(
        state,
        np.zeros(11),
        maximum_mode=5,
        geometry_config=config,
    )

    assert 0.0 < state.initial_projection_rms_m < 2.0e-3
    assert 0.0 < state.initial_projection_maximum_m < 3.0e-3
    assert state.minimum_radius_lower_bound_m > 0.0
    np.testing.assert_array_equal(zero.curve.points, projected.points)
    np.testing.assert_array_equal(zero.curve.first_derivatives, projected.first_derivatives)
    assert zero.maximum_displacement_m == 0.0
    assert radial_spectral_tail_rms(projected.points, 5) < 2.0e-16


def test_radial_fourier_mode_one_slots_are_exact_center_translation() -> None:
    config = _geometry_config(num_nodes=128, bandwidth=12)
    original = circle((0.01, -0.015), 0.055).discretize(
        config.num_nodes, require_even=True
    )
    state = fit_radial_fourier_curve_state(original, maximum_mode=5)
    base = radial_fourier_state_curve(state, geometry_config=config)
    step = np.zeros(11)
    step[1:3] = (2.5e-3, -1.25e-3)
    update = apply_radial_fourier_update(
        state,
        step,
        maximum_mode=5,
        geometry_config=config,
    )

    np.testing.assert_allclose(
        update.curve.points - base.points,
        np.broadcast_to(step[1:3], base.points.shape),
        rtol=0.0,
        atol=2.0e-17,
    )
    np.testing.assert_allclose(update.state.center, state.center + step[1:3])
    np.testing.assert_array_equal(
        update.state.radius_cosine_coefficients,
        state.radius_cosine_coefficients,
    )
    np.testing.assert_array_equal(
        update.state.radius_sine_coefficients,
        state.radius_sine_coefficients,
    )
    assert update.maximum_displacement_m == pytest.approx(
        np.linalg.norm(step[1:3])
    )


def test_repeated_radial_retractions_remain_in_one_finite_dimensional_chart() -> None:
    config = _geometry_config(num_nodes=128, bandwidth=12)
    original = ellipse(
        (0.01, -0.015), 0.075, 0.045, rotation=0.31
    ).discretize(config.num_nodes, require_even=True)
    state = fit_radial_fourier_curve_state(original, maximum_mode=5)
    step = np.array(
        [0.0, 1.0, -0.5, 0.2, -0.1, 0.3, 0.15, -0.2, 0.1, 0.25, -0.15]
    ) * 2.0e-5

    for _ in range(40):
        probe = apply_radial_fourier_update(
            state,
            step,
            maximum_mode=5,
            geometry_config=config,
            full_validation=False,
        )
        accepted = apply_radial_fourier_update(
            state,
            step,
            maximum_mode=5,
            geometry_config=config,
            full_validation=True,
        )
        np.testing.assert_array_equal(probe.curve.points, accepted.curve.points)
        state = accepted.state

    assert state.minimum_radius_lower_bound_m > 0.0
    assert radial_spectral_tail_rms(accepted.curve.points, 5) < 3.0e-16
    np.testing.assert_allclose(
        np.mean(accepted.curve.points, axis=0),
        state.center,
        rtol=0.0,
        atol=2.0e-16,
    )


def test_radial_retraction_rejects_loss_of_positive_radius() -> None:
    config = _geometry_config(num_nodes=128, bandwidth=12)
    original = circle((0.0, 0.0), 0.05).discretize(
        config.num_nodes, require_even=True
    )
    state = fit_radial_fourier_curve_state(original, maximum_mode=2)
    step = np.zeros(5)
    step[0] = -0.06

    with pytest.raises(OrderedSDFGeometryError, match="not admissible"):
        apply_radial_fourier_update(
            state,
            step,
            maximum_mode=2,
            geometry_config=config,
        )


def test_radial_vector_basis_matches_the_exact_state_increment() -> None:
    angles = np.linspace(0.0, 2.0 * np.pi, 257, endpoint=False)
    step = np.array(
        [0.3, 0.2, -0.4, 0.1, -0.05, 0.07, 0.02], dtype=np.float64
    ) * 1.0e-3
    basis = radial_fourier_displacement_basis(angles, maximum_mode=3)
    displacement = np.einsum("npd,p->nd", basis, step)
    radial = np.column_stack((np.cos(angles), np.sin(angles)))
    expected_radius_step = (
        step[0]
        + step[3] * np.cos(2.0 * angles)
        + step[4] * np.sin(2.0 * angles)
        + step[5] * np.cos(3.0 * angles)
        + step[6] * np.sin(3.0 * angles)
    )
    expected = step[1:3] + expected_radius_step[:, None] * radial

    np.testing.assert_allclose(displacement, expected, rtol=0.0, atol=3.0e-19)
    assert not basis.flags.writeable
