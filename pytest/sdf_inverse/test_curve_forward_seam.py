"""Focused contract checks for the direct ordered-curve forward seam."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

import gpr_bem_kress
import gpr_bem_mod
from ordered_boundary import circle
import sdf_inverse.forward as forward_module
from sdf_inverse.forward import (
    MaterialSpec,
    PairedForwardProblem,
    predict_paired_curve_response,
    predict_paired_response,
)
from sdf_inverse.geometry import (
    OrderedSDFGeometryBuild,
    OrderedSDFGeometryConfig,
    OrderedSDFGeometryError,
)


def _geometry_config() -> OrderedSDFGeometryConfig:
    return OrderedSDFGeometryConfig(
        bounds=((0.3, 0.3), (0.7, 0.7)),
        grid_shape=(17, 17),
        projected_samples=16,
        bandwidth=3,
        num_nodes=16,
        arclength_dense_resolution=32,
        validation_resolution=64,
    )


def _problem() -> PairedForwardProblem:
    return PairedForwardProblem(
        source_points=np.array(((0.1, 0.1), (0.1, 0.9))),
        receiver_points=np.array(((0.9, 0.1), (0.9, 0.9))),
        angular_frequencies=np.array((2.0, 3.0)),
        source_strengths=np.array((1.0 + 0.5j, 2.0 - 0.25j)),
        exterior=MaterialSpec(epsr=2.0, sigma=0.01),
        interior=MaterialSpec(epsr=3.0, sigma=0.02),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )


@pytest.mark.parametrize("solver", ("mod", "kress"))
def test_direct_curve_seam_skips_sdf_extraction_and_preserves_backend_contract(
    monkeypatch: pytest.MonkeyPatch,
    solver: str,
) -> None:
    config = _geometry_config()
    curve = circle((0.5, 0.5), 0.05).discretize(config.num_nodes)
    problem = _problem()
    calls: list[tuple[object, float, complex]] = []

    def extraction_is_forbidden(*args, **kwargs):
        raise AssertionError("the direct curve seam must not extract an SDF")

    monkeypatch.setattr(
        forward_module, "build_ordered_sdf_geometry", extraction_is_forbidden
    )

    if solver == "mod":

        def mod_solve(boundary, sources, receivers, omega, strength, **kwargs):
            np.testing.assert_allclose(
                boundary.points.detach().cpu().numpy(), curve.points, atol=0.0, rtol=0.0
            )
            calls.append((boundary, omega, strength))
            index = len(calls)
            scattered = index * np.array((1.0 + 2.0j, 3.0 + 4.0j))
            return SimpleNamespace(
                scattered_receiver=scattered,
                total_receiver=scattered + 10.0,
                linear_system_relative_residual=index * 1.0e-14,
            )

        monkeypatch.setattr(gpr_bem_mod, "solve_ibim_tmz_total_field_batch", mod_solve)
    else:

        def kress_solve(supplied_curve, sources, receivers, omega, strength, **kwargs):
            assert supplied_curve is curve
            calls.append((supplied_curve, omega, strength))
            index = len(calls)
            scattered = index * np.array(
                ((1.0 + 2.0j, 50.0j), (-75.0j, 3.0 + 4.0j))
            )
            return SimpleNamespace(
                scattered_receiver=scattered,
                total_receiver=scattered + 10.0,
                linear_system_relative_residual=index * 1.0e-14,
            )

        monkeypatch.setattr(
            gpr_bem_kress, "solve_kress_tmz_total_field_batch", kress_solve
        )

    result = predict_paired_curve_response(curve, problem, config, solver=solver)

    expected = np.column_stack(
        (
            np.array((1.0 + 2.0j, 3.0 + 4.0j)),
            2.0 * np.array((1.0 + 2.0j, 3.0 + 4.0j)),
        )
    )
    np.testing.assert_allclose(result.scattered_response, expected)
    np.testing.assert_allclose(result.total_response, expected + 10.0)
    np.testing.assert_allclose(
        result.linear_system_relative_residuals, (1.0e-14, 2.0e-14)
    )
    assert len(calls) == problem.num_frequencies
    assert [call[1] for call in calls] == list(problem.angular_frequencies)
    assert [call[2] for call in calls] == list(problem.source_strengths)
    assert result.geometry_build.curve is curve
    assert result.geometry_build.maximum_projected_sdf_residual == 0.0
    assert result.geometry_build.maximum_curve_sdf_residual == 0.0
    assert result.geometry_build.maximum_normalized_curve_residual == 0.0
    assert result.geometry_seconds >= 0.0
    assert result.forward_seconds >= 0.0
    assert result.total_seconds >= result.forward_seconds
    assert not result.scattered_response.flags.writeable


def test_sdf_entry_point_extracts_once_then_uses_shared_forward_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _geometry_config()
    curve = circle((0.5, 0.5), 0.05).discretize(config.num_nodes)
    problem = _problem()
    extracted = OrderedSDFGeometryBuild(
        curve=curve,
        frontend_seconds=0.1,
        fit_seconds=0.2,
        discretize_seconds=0.3,
        total_seconds=0.6,
        maximum_projected_sdf_residual=1.0e-8,
        maximum_curve_sdf_residual=2.0e-8,
        maximum_normalized_curve_residual=3.0e-8,
        speed_ratio=1.0,
        config=config,
    )
    model = object()
    extraction_calls: list[tuple[object, object]] = []

    def extract(supplied_model, supplied_config):
        extraction_calls.append((supplied_model, supplied_config))
        return extracted

    def mod_solve(boundary, sources, receivers, omega, strength, **kwargs):
        response = np.array((omega + 1.0j, omega + 2.0j))
        return SimpleNamespace(
            scattered_receiver=response,
            total_receiver=response + 1.0,
            linear_system_relative_residual=1.0e-15,
        )

    monkeypatch.setattr(forward_module, "build_ordered_sdf_geometry", extract)
    monkeypatch.setattr(gpr_bem_mod, "solve_ibim_tmz_total_field_batch", mod_solve)

    result = predict_paired_response(model, problem, config, solver="mod")

    assert extraction_calls == [(model, config)]
    assert result.geometry_build is extracted
    assert result.geometry_build.maximum_curve_sdf_residual == 2.0e-8
    np.testing.assert_allclose(
        result.scattered_response,
        np.array(((2.0 + 1.0j, 3.0 + 1.0j), (2.0 + 2.0j, 3.0 + 2.0j))),
    )


def test_direct_curve_seam_rejects_geometry_outside_extraction_contract() -> None:
    config = _geometry_config()
    problem = _problem()
    wrong_count = circle((0.5, 0.5), 0.05).discretize(18)
    outside_bounds = circle((0.68, 0.5), 0.05).discretize(config.num_nodes)

    with pytest.raises(ValueError, match="curve.num_nodes"):
        predict_paired_curve_response(wrong_count, problem, config, solver="kress")
    with pytest.raises(OrderedSDFGeometryError, match="strictly inside"):
        predict_paired_curve_response(outside_bounds, problem, config, solver="kress")
