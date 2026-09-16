"""Regressions for neural representation and radial discretization audits."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ordered_boundary import circle
from sdf_inverse import (
    AlternatingNeuralInverseConfig,
    ComplexScatteredData,
    MaterialSpec,
    NeuralRedistanceConfig,
    OrderedSDFGeometryConfig,
    OrderedSDFGeometryError,
    PairedForwardProblem,
    RadialFourierCurveState,
    SmoothMLPSDF2D,
    radial_fourier_state_curve,
    run_alternating_neural_inverse,
)
import sdf_inverse.neural_optimization as optimization_module


def _geometry_config():
    return OrderedSDFGeometryConfig(
        bounds=((0.3, 0.3), (0.7, 0.7)),
        grid_shape=(33, 33),
        projected_samples=32,
        bandwidth=6,
        num_nodes=32,
        arclength_dense_resolution=64,
        validation_resolution=64,
    )


def _initial_inverse_arguments(monkeypatch):
    geometry = _geometry_config()
    initial_curve = circle((0.5, 0.5), 0.05).discretize(geometry.num_nodes)
    model = SmoothMLPSDF2D(
        bounds=geometry.bounds,
        hidden_features=4,
        hidden_layers=1,
        fourier_frequencies=(1.0,),
        geometric_center=(0.5, 0.5),
        geometric_radius=0.05,
    )
    problem = PairedForwardProblem(
        source_points=np.array([[0.1, 0.1]]),
        receiver_points=np.array([[0.2, 0.2]]),
        angular_frequencies=np.array([1.0e9]),
        source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0),
        interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )

    def constant_curve_predictor(curve, *args, **kwargs):
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[1.0 + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    # A pointwise field audit alone cannot certify the topology of a zero set.
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )
    return dict(
        model=model,
        data=ComplexScatteredData(problem, np.array([[1.0 + 0.0j]])),
        geometry_config=geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(
                bounds=geometry.bounds, eikonal_rms_tolerance=0.15
            ),
            maximum_mode=1,
            max_iterations=1,
            max_damping_trials=1,
            max_backtracks=0,
        ),
        initial_curve=initial_curve,
        curve_forward_predictor=constant_curve_predictor,
    )


def test_initial_curve_does_not_fabricate_an_audited_mlp_representation(monkeypatch):
    arguments = _initial_inverse_arguments(monkeypatch)
    representation = circle((0.505, 0.5), 0.05).discretize(32)
    extractions = []

    def extract(model, config):
        extractions.append(model)
        return SimpleNamespace(curve=representation)

    monkeypatch.setattr(optimization_module, "build_ordered_sdf_geometry", extract)
    result = run_alternating_neural_inverse(**arguments)

    assert extractions == [arguments["model"]]
    assert result.final_representation_curve is representation
    assert result.initial_iteration.redistance_curve_drift_m > 4.0e-3
    assert not result.converged


def test_initial_curve_cannot_bypass_mlp_topology_validation(monkeypatch):
    arguments = _initial_inverse_arguments(monkeypatch)

    def reject_multiple_components(*args, **kwargs):
        raise OrderedSDFGeometryError("multiple initial zero components")

    monkeypatch.setattr(
        optimization_module, "build_ordered_sdf_geometry", reject_multiple_components
    )
    with pytest.raises(OrderedSDFGeometryError, match="multiple initial zero"):
        run_alternating_neural_inverse(**arguments)


def test_explicit_audited_continuation_representation_skips_extraction(monkeypatch):
    arguments = _initial_inverse_arguments(monkeypatch)

    def forbidden_extraction(*args, **kwargs):
        raise AssertionError("an explicit audited continuation contour is reusable")

    monkeypatch.setattr(
        optimization_module, "build_ordered_sdf_geometry", forbidden_extraction
    )
    result = run_alternating_neural_inverse(
        **arguments, initial_representation_curve=arguments["initial_curve"]
    )
    assert result.converged


@pytest.mark.parametrize("full_validation", [False, True])
@pytest.mark.parametrize("underresolved_grid", ["num_nodes", "validation_resolution"])
def test_radial_state_checks_its_own_cartesian_sampling_bandwidth(
    full_validation, underresolved_grid
):
    # Radius mode K produces Cartesian position modes K-1 and K+1.  The
    # Method-B bandwidth in geometry_config does not describe this curve.
    mode = 8
    cosine = np.zeros(mode + 1)
    cosine[0] = 0.05
    cosine[mode] = 1.0e-4
    state = RadialFourierCurveState(
        center=np.array([0.5, 0.5]),
        radius_cosine_coefficients=cosine,
        radius_sine_coefficients=np.zeros_like(cosine),
        component_id="target",
    )
    geometry = replace(_geometry_config(), **{underresolved_grid: 18})

    with pytest.raises(ValueError, match=underresolved_grid):
        radial_fourier_state_curve(
            state, geometry_config=geometry, full_validation=full_validation
        )


def test_radial_sampling_floor_allows_its_minimum_even_grid():
    cosine = np.array([0.05, 0.0, 1.0e-4])
    state = RadialFourierCurveState(
        center=np.array([0.5, 0.5]),
        radius_cosine_coefficients=cosine,
        radius_sine_coefficients=np.zeros_like(cosine),
        component_id="target",
    )
    geometry = replace(_geometry_config(), bandwidth=2, num_nodes=8)
    assert radial_fourier_state_curve(state, geometry_config=geometry).num_nodes == 8
