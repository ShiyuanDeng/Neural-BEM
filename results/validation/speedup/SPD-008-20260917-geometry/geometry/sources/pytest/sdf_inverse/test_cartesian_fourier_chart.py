"""Validation gates for the MLP-free Cartesian Fourier chart.

These are the gates named in
``docs/iterations/cartesian_fourier/iteration_01/03_plan.md``.  Gate A is the
load-bearing one: the analytic target is band-limited in the *polar-angle*
parameter and not in arc length, which is what makes the chart's accuracy
ceiling a choice rather than a property of Fourier truncation.
"""

from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ordered_boundary.analytic import star
from sdf_inverse import (
    AlternatingNeuralInverseConfig, ComplexScatteredData, MaterialSpec,
    NeuralRedistanceConfig, OrderedSDFGeometryConfig, PairedForwardProblem,
    run_alternating_neural_inverse,
)
from sdf_inverse.curve_updates import (
    apply_cartesian_fourier_update, cartesian_fourier_displacement_basis,
    cartesian_fourier_phase_gauge_direction, cartesian_fourier_state_curve,
    fit_cartesian_fourier_curve_state, project_off_phase_gauge,
)
from sdf_inverse.explicit_fourier import CartesianFourierCurveState

TARGET_CENTER = (0.5, 0.5)
TARGET_RADIUS = 0.05
TARGET_AMPLITUDE = 0.25
TARGET_LOBES = 5


def _target_points(count=4096):
    producer = star(TARGET_CENTER, TARGET_RADIUS, TARGET_AMPLITUDE, TARGET_LOBES)
    parameters = 2.0 * np.pi * np.arange(count) / count
    return producer, parameters, producer.evaluate(parameters, wrap=False).points


def _arclength_resample(points, count=4096):
    closed = np.vstack((points, points[:1]))
    steps = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    distance = np.concatenate(([0.0], np.cumsum(steps)))
    sample = np.linspace(0.0, distance[-1], count, endpoint=False)
    return np.column_stack(
        [np.interp(sample, distance, closed[:, axis]) for axis in range(2)]
    )


def _truncation_maximum(points, band):
    spectrum = np.fft.rfft(points, axis=0)
    spectrum[band + 1 :] = 0.0
    rebuilt = np.fft.irfft(spectrum, n=len(points), axis=0)
    return float(np.max(np.linalg.norm(rebuilt - points, axis=1)))


def test_gate_a_the_star_is_exactly_band_six_in_the_polar_angle_chart():
    _, _, points = _target_points()
    below = fit_cartesian_fourier_curve_state(
        points, maximum_mode=5, center=np.asarray(TARGET_CENTER)
    )
    at = fit_cartesian_fourier_curve_state(
        points, maximum_mode=6, center=np.asarray(TARGET_CENTER)
    )
    # Band five is short of the target by millimetres; band six contains it.
    assert below.initial_projection_maximum_m > 5.0e-3
    assert at.initial_projection_maximum_m < 1.0e-14

    amplitude = np.linalg.norm(at.cosine_coefficients, axis=1) + np.linalg.norm(
        at.sine_coefficients, axis=1
    )
    assert [mode for mode in range(7) if amplitude[mode] > 1.0e-12] == [0, 1, 4, 6]


def test_gate_a_arclength_is_not_band_limited_at_any_useful_bandwidth():
    _, _, points = _target_points()
    resampled = _arclength_resample(points)
    # The same curve, reparameterized: no practical band reaches the polar
    # chart's machine-precision floor.  This is the frozen-tail floor that
    # Method B's arc-length refit imposes, and the reason nothing here refits.
    assert _truncation_maximum(resampled, 6) > 1.0e-3
    assert _truncation_maximum(resampled, 32) > 1.0e-5
    assert _truncation_maximum(points, 6) < 1.0e-14


def test_gate_b_displacement_basis_matches_finite_differences():
    _, parameters, points = _target_points()
    state = fit_cartesian_fourier_curve_state(
        points, maximum_mode=6, center=np.asarray(TARGET_CENTER)
    )
    basis = cartesian_fourier_displacement_basis(parameters, maximum_mode=6)
    direction = np.random.default_rng(11).normal(size=basis.shape[1])
    direction /= np.linalg.norm(direction)
    analytic = np.einsum("npd,p->nd", basis, direction)
    step = 1.0e-4
    plus = state.incremented(step * direction).parameterization()
    minus = state.incremented(-step * direction).parameterization()
    difference = (
        plus.evaluate(parameters, wrap=False).points
        - minus.evaluate(parameters, wrap=False).points
    ) / (2.0 * step)
    assert np.max(np.linalg.norm(difference - analytic, axis=1)) < 1.0e-10


def test_gate_c_a_phase_shift_moves_no_point_and_is_removed_by_the_projector():
    producer, parameters, points = _target_points()
    state = fit_cartesian_fourier_curve_state(
        points, maximum_mode=6, center=np.asarray(TARGET_CENTER)
    )
    for shift in (1.0e-3, 0.1, 1.0):
        cosine = np.array(state.cosine_coefficients, copy=True)
        sine = np.array(state.sine_coefficients, copy=True)
        for mode in range(1, state.maximum_mode + 1):
            c, s = np.cos(mode * shift), np.sin(mode * shift)
            cosine[mode] = c * state.cosine_coefficients[mode] + s * state.sine_coefficients[mode]
            sine[mode] = c * state.sine_coefficients[mode] - s * state.cosine_coefficients[mode]
        rotated = CartesianFourierCurveState(cosine, sine, state.component_id)
        moved = rotated.parameterization().evaluate(parameters, wrap=False).points
        exact = producer.evaluate(parameters + shift, wrap=False).points
        assert np.max(np.linalg.norm(moved - exact, axis=1)) < 1.0e-14

    direction = cartesian_fourier_phase_gauge_direction(state)
    assert direction is not None and np.isclose(np.linalg.norm(direction), 1.0)
    arbitrary = np.random.default_rng(5).normal(size=direction.size)
    projected, removed = project_off_phase_gauge(arbitrary, state)
    assert abs(removed) > 1.0e-3
    assert abs(float(projected @ direction)) < 1.0e-12


def test_gate_d_increments_are_exact_and_a_reversed_step_restores_the_state():
    _, _, points = _target_points()
    state = fit_cartesian_fourier_curve_state(
        points, maximum_mode=6, center=np.asarray(TARGET_CENTER)
    )
    step = 1.0e-4 * np.random.default_rng(7).normal(size=4 * 6 + 2)
    there_and_back = state.incremented(step).incremented(-step)
    # Additive increments round-trip to float round-off on the state's scale.
    assert np.allclose(
        there_and_back.parameter_vector(), state.parameter_vector(), rtol=0.0, atol=1.0e-15
    )
    # A lower active band moves only its own prefix.
    partial = state.incremented(np.ones(4 * 2 + 2), maximum_mode=2)
    assert np.array_equal(
        partial.cosine_coefficients[3:], state.cosine_coefficients[3:]
    )
    assert np.array_equal(partial.sine_coefficients[3:], state.sine_coefficients[3:])


def _synthetic_arguments():
    geometry = OrderedSDFGeometryConfig(
        bounds=((0.3, 0.3), (0.7, 0.7)), grid_shape=(33, 33), projected_samples=32,
        bandwidth=6, num_nodes=32, arclength_dense_resolution=64,
        validation_resolution=64,
    )
    cosine = np.zeros((2, 2))
    cosine[0] = (0.5, 0.5)
    cosine[1] = (0.05, 0.0)
    sine = np.zeros((2, 2))
    sine[1] = (0.0, 0.05)
    state = CartesianFourierCurveState(cosine, sine, "target")
    problem = PairedForwardProblem(
        source_points=np.array([[0.1, 0.1]]), receiver_points=np.array([[0.2, 0.2]]),
        angular_frequencies=np.array([1.0e9]), source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0), interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12, mu0=1.25663706212e-6,
    )

    def radius_predictor(curve, *args, **kwargs):
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[np.sqrt(curve.signed_area / np.pi) + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    return dict(
        model=_ForbiddenField(),
        data=ComplexScatteredData(problem, np.array([[0.045 + 0.0j]])),
        geometry_config=geometry, solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(bounds=geometry.bounds),
            maximum_mode=1, max_iterations=3, max_backtracks=2, max_damping_trials=2,
            maximum_modal_field_update_m=0.002,
            direct_curve_retraction="cartesian_fourier",
            distillation_policy="curve_only",
        ),
        initial_curve=cartesian_fourier_state_curve(state, geometry_config=geometry),
        initial_cartesian_curve_state=state,
        curve_forward_predictor=radius_predictor,
    )


class _ForbiddenField(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.value = torch.nn.Parameter(torch.tensor(0.0, dtype=torch.float64))

    def forward(self, points):
        raise AssertionError("the Cartesian reconstruction evaluated a neural field")


def test_gate_e_the_cartesian_inverse_never_touches_a_neural_field(monkeypatch):
    import sdf_inverse.neural_optimization as inverse

    def forbidden(*args, **kwargs):
        raise AssertionError("the Cartesian reconstruction entered neural work")

    for name in (
        "_field_audit", "_audit_points", "build_ordered_sdf_geometry",
        "redistance_neural_sdf_to_curve",
    ):
        monkeypatch.setattr(inverse, name, forbidden)
    arguments = _synthetic_arguments()
    result = run_alternating_neural_inverse(**arguments)

    assert len(result.iterations) > 1
    assert result.final_iteration.loss < result.initial_iteration.loss
    assert result.final_cartesian_curve_state is not None
    assert not result.representation_evaluated
    assert result.total_redistance_step_count == 0
    assert arguments["model"].value.item() == 0.0
    # No chart in this experiment refits to arc length.
    for iteration in result.iterations:
        assert iteration.arclength_refit_rms_m == 0.0
        assert iteration.arclength_refit_maximum_m == 0.0


def test_the_trust_region_is_measured_on_the_retracted_step():
    geometry = OrderedSDFGeometryConfig(
        bounds=((0.3, 0.3), (0.7, 0.7)), grid_shape=(33, 33), projected_samples=32,
        bandwidth=6, num_nodes=64, arclength_dense_resolution=128,
        validation_resolution=128,
    )
    _, _, points = _target_points()
    state = fit_cartesian_fourier_curve_state(
        points, maximum_mode=6, center=np.asarray(TARGET_CENTER)
    )
    step = np.zeros(4 * 6 + 2)
    step[2] = 1.0e-3  # a pure translation of the first cosine mode
    update = apply_cartesian_fourier_update(
        state, step, maximum_mode=6, geometry_config=geometry
    )
    assert update.arclength_refit_rms_m == 0.0
    assert np.isclose(update.maximum_displacement_m, 1.0e-3, rtol=1.0e-9)
    assert 0.0 <= update.tangential_energy_ratio <= 1.0
    assert update.maximum_normal_displacement_m <= update.maximum_displacement_m


def test_projection_error_is_phase_independent_and_matches_the_built_curve():
    """A contour whose first node is not at angle zero must report the same error.

    The discrete transform's parameter origin is the first sampled angle.
    Measuring the truncation residual in absolute polar angle instead reports
    the phase offset as projection error, which is what this guards.
    """

    producer, _, _ = _target_points()
    offset = 0.7
    shifted_parameters = offset + 2.0 * np.pi * np.arange(4096) / 4096
    shifted_points = producer.evaluate(shifted_parameters, wrap=False).points
    state = fit_cartesian_fourier_curve_state(
        shifted_points, maximum_mode=6, center=np.asarray(TARGET_CENTER)
    )
    assert state.initial_projection_maximum_m < 1.0e-13

    # The recorded projection error must agree with the curve actually built.
    ellipse_angles = 2.0 * np.pi * np.arange(2048) / 2048
    semi_axes = (0.072, 0.038)
    rotation = 0.4
    phi = ellipse_angles - rotation
    radius = semi_axes[0] * semi_axes[1] / np.hypot(
        semi_axes[1] * np.cos(phi), semi_axes[0] * np.sin(phi)
    )
    ellipse = np.column_stack(
        (radius * np.cos(ellipse_angles), radius * np.sin(ellipse_angles))
    ) + np.asarray(TARGET_CENTER)
    for start in (0, 137, 1024):
        rolled = np.roll(ellipse, start, axis=0)
        projected = fit_cartesian_fourier_curve_state(
            rolled, maximum_mode=6, center=np.asarray(TARGET_CENTER)
        )
        rebuilt = projected.parameterization().evaluate(
            ellipse_angles, wrap=False
        ).points
        measured = float(np.max(np.linalg.norm(rebuilt - ellipse, axis=1)))
        assert np.isclose(
            projected.initial_projection_maximum_m, measured, rtol=1.0e-6, atol=1.0e-12
        )
        assert 5.0e-4 < measured < 1.0e-3
