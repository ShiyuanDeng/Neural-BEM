"""End-to-end checks for the opt-in multi-component SDF/Kress seam."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from gpr_bem_kress.materials import Material
from gpr_bem_kress.multicomponent import (
    solve_multicomponent_kress_tmz_total_field_batch,
)
from gpr_bem_kress import solve_kress_tmz_total_field_batch
from ordered_boundary import OrderedBoundary2D, circle
from sdf_bem_multicomponent import (
    CircleUnionSDF2D,
    MaterialSpec,
    MultiComponentBoundaryPairedForwardResult,
    MultiComponentOrderedSDFGeometryConfig,
    PairedForwardProblem,
    predict_multicomponent_kress_paired_boundary_response,
    predict_multicomponent_kress_paired_response,
)


EPS0 = 8.8541878128e-12
MU0 = 1.25663706212e-6
CENTERS = ((0.43, 0.5), (0.57, 0.5))
RADII = (0.035, 0.035)


def _paired_problem() -> PairedForwardProblem:
    angles = np.linspace(0.0, 2.0 * np.pi, 3, endpoint=False)
    center = np.asarray((0.5, 0.5))
    source_angles = angles - 0.05
    receiver_angles = angles + 0.05
    sources = center + 0.30 * np.column_stack(
        (np.cos(source_angles), np.sin(source_angles))
    )
    receivers = center + 0.30 * np.column_stack(
        (np.cos(receiver_angles), np.sin(receiver_angles))
    )
    return PairedForwardProblem(
        source_points=sources,
        receiver_points=receivers,
        angular_frequencies=np.asarray((2.0 * np.pi * 0.8e9,)),
        source_strengths=1.0,
        exterior=MaterialSpec(epsr=6.0),
        interior=MaterialSpec(epsr=3.0),
        eps0=EPS0,
        mu0=MU0,
    )


def test_structural_problem_adapter_owns_an_isolated_copy() -> None:
    original = _paired_problem()
    foreign = SimpleNamespace(
        source_points=original.source_points,
        receiver_points=original.receiver_points,
        angular_frequencies=original.angular_frequencies,
        source_strengths=original.source_strengths,
        exterior=SimpleNamespace(epsr=6.0, sigma=0.0, mur=1.0),
        interior=SimpleNamespace(epsr=3.0, sigma=0.0, mur=1.0),
        eps0=EPS0,
        mu0=MU0,
    )

    copied = PairedForwardProblem.from_compatible(foreign)

    assert isinstance(copied.exterior, MaterialSpec)
    assert isinstance(copied.interior, MaterialSpec)
    assert not np.shares_memory(copied.source_points, original.source_points)
    assert not copied.source_points.flags.writeable


def test_direct_boundary_seam_accepts_active_problem_without_sdf_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sdf_inverse.forward import (
        MaterialSpec as ActiveMaterialSpec,
        PairedForwardProblem as ActivePairedForwardProblem,
    )

    local = _paired_problem()
    active_problem = ActivePairedForwardProblem(
        source_points=local.source_points,
        receiver_points=local.receiver_points,
        angular_frequencies=local.angular_frequencies,
        source_strengths=local.source_strengths,
        exterior=ActiveMaterialSpec(epsr=local.exterior.epsr),
        interior=ActiveMaterialSpec(epsr=local.interior.epsr),
        eps0=local.eps0,
        mu0=local.mu0,
    )
    boundary = OrderedBoundary2D(
        tuple(
            circle(center, radius, component_id=f"object-{index}").discretize(
                24,
                require_even=True,
            )
            for index, (center, radius) in enumerate(zip(CENTERS, RADII))
        )
    )

    def fail_if_extracted(*_args, **_kwargs):
        raise AssertionError("the direct boundary seam must not extract an SDF")

    monkeypatch.setattr(
        "sdf_bem_multicomponent.forward.build_multicomponent_ordered_sdf_geometry",
        fail_if_extracted,
    )
    result = predict_multicomponent_kress_paired_boundary_response(
        boundary,
        active_problem,
    )

    assert isinstance(result, MultiComponentBoundaryPairedForwardResult)
    assert result.boundary is boundary
    assert isinstance(result.problem, PairedForwardProblem)
    assert result.problem is not active_problem
    assert result.num_components == 2
    assert result.component_ids == ("object-0", "object-1")
    np.testing.assert_array_equal(result.component_offsets, (0, 24, 48))
    assert result.geometry_seconds == 0.0
    assert result.scattered_response.shape == (3, 1)
    assert result.forwards[0].system.geometry is boundary
    assert result.linear_system_relative_residuals[0] < 1.0e-10


def test_direct_boundary_seam_m1_matches_existing_single_component_kress() -> None:
    problem = _paired_problem()
    curve = circle(
        (0.5, 0.5),
        0.04,
        component_id="only-object",
    ).discretize(32, require_even=True)
    boundary = OrderedBoundary2D((curve,))

    observed = predict_multicomponent_kress_paired_boundary_response(
        boundary,
        problem,
    )
    expected = solve_kress_tmz_total_field_batch(
        curve,
        problem.source_points,
        problem.receiver_points,
        float(problem.angular_frequencies[0]),
        complex(problem.source_strengths[0]),
        exterior=Material(epsr=problem.exterior.epsr),
        interior=Material(epsr=problem.interior.epsr),
        eps0=problem.eps0,
        mu0=problem.mu0,
    )

    assert observed.num_components == 1
    np.testing.assert_array_equal(
        observed.scattered_response[:, 0],
        np.diag(expected.scattered_receiver),
    )
    np.testing.assert_array_equal(
        observed.total_response[:, 0],
        np.diag(expected.total_receiver),
    )


def test_direct_boundary_seam_has_no_fixed_component_arity() -> None:
    problem = _paired_problem()
    boundary = OrderedBoundary2D(
        tuple(
            circle(center, 0.02, component_id=component_id).discretize(
                node_count,
                require_even=True,
            )
            for center, component_id, node_count in (
                ((0.40, 0.50), "left", 16),
                ((0.50, 0.50), "middle", 24),
                ((0.60, 0.50), "right", 32),
            )
        )
    )

    result = predict_multicomponent_kress_paired_boundary_response(
        boundary,
        problem,
    )

    assert result.num_components == 3
    assert result.component_ids == ("left", "middle", "right")
    np.testing.assert_array_equal(result.component_offsets, (0, 16, 40, 72))
    assert result.forwards[0].system.geometry is boundary
    assert result.scattered_response.shape == (3, 1)
    assert result.linear_system_relative_residuals[0] < 1.0e-10


def test_analytic_union_reaches_multi_kress_without_active_dispatch() -> None:
    # Primitive order is deliberately reversed.  Marching squares owns the
    # spatial component order; the trainable primitive array does not.
    model = CircleUnionSDF2D(
        centers=tuple(reversed(CENTERS)),
        radii=tuple(reversed(RADII)),
    )
    geometry_config = MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.30, 0.35), (0.70, 0.65)),
        expected_num_components=2,
        grid_shape=(81, 101),
        projected_samples=32,
        bandwidth=4,
        num_nodes=(32, 32),
        arclength_dense_resolution=64,
        validation_resolution=64,
        minimum_intercomponent_clearance=0.05,
    )
    problem = _paired_problem()

    result = predict_multicomponent_kress_paired_response(
        model,
        problem,
        geometry_config,
    )

    assert result.num_components == 2
    assert result.solver == "kress"
    assert result.component_ids == ("component_000", "component_001")
    np.testing.assert_array_equal(result.component_offsets, (0, 32, 64))
    assert result.scattered_response.shape == (3, 1)
    assert result.total_response.shape == (3, 1)
    assert len(result.forwards) == 1
    assert result.forwards[0].system.geometry is result.geometry_build.boundary
    assert result.linear_system_relative_residuals[0] < 1.0e-10
    assert result.paired_scattered_response is result.scattered_response
    assert result.paired_total_response is result.total_response
    assert (
        result.per_frequency_linear_residuals
        is result.linear_system_relative_residuals
    )
    assert np.all(np.isfinite(result.scattered_response))
    assert not result.scattered_response.flags.writeable

    exact_boundary = OrderedBoundary2D(
        tuple(
            circle(center, radius, component_id=f"component_{index:03d}").discretize(
                32,
                require_even=True,
            )
            for index, (center, radius) in enumerate(zip(CENTERS, RADII))
        )
    )
    exact = solve_multicomponent_kress_tmz_total_field_batch(
        exact_boundary,
        problem.source_points,
        problem.receiver_points,
        float(problem.angular_frequencies[0]),
        complex(problem.source_strengths[0]),
        exterior=Material(epsr=problem.exterior.epsr),
        interior=Material(epsr=problem.interior.epsr),
        eps0=problem.eps0,
        mu0=problem.mu0,
    )
    expected = np.diag(exact.scattered_receiver)
    relative_error = np.linalg.norm(
        result.scattered_response[:, 0] - expected
    ) / np.linalg.norm(expected)
    assert relative_error < 2.0e-6

    with pytest.raises(ValueError, match="must be real-valued"):
        replace(
            result,
            linear_system_relative_residuals=(
                result.linear_system_relative_residuals.astype(np.complex128)
                + 1.0j
            ),
        )
    inconsistent = result.scattered_response.copy()
    inconsistent[0, 0] += 1.0
    with pytest.raises(ValueError, match="retained paired solves"):
        replace(result, scattered_response=inconsistent)
