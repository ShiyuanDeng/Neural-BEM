"""Validation of the independent circular multiple-scattering oracle."""

from __future__ import annotations

import numpy as np
import pytest

from gpr_bem_ref import penetrable_cylinder_scattered_field
from multicylinder_ref import (
    CircularCylinder2D,
    TruncationConfig,
    TruncationConvergenceError,
    build_multicylinder_system,
    converge_multicylinder_scattered_field,
    multicylinder_scattered_field,
    solve_multicylinder_line_sources,
)


K_EXTERIOR = 13.0 - 0.1j
K_INTERIOR = 21.0 - 0.2j


def _two_cylinders(*, reverse: bool = False) -> tuple[CircularCylinder2D, ...]:
    values = (
        CircularCylinder2D((-0.10, 0.0), 0.04, component_id="left"),
        CircularCylinder2D((0.11, 0.015), 0.05, component_id="right"),
    )
    return values[::-1] if reverse else values


def _paired_points() -> tuple[np.ndarray, np.ndarray]:
    sources = np.asarray(
        (
            (0.31, 0.12),
            (-0.27, 0.19),
            (0.02, 0.31),
        ),
        dtype=float,
    )
    receivers = np.asarray(
        (
            (0.28, -0.16),
            (-0.30, -0.11),
            (0.10, -0.29),
        ),
        dtype=float,
    )
    return receivers, sources


def test_single_cylinder_matches_existing_analytic_reference() -> None:
    cylinder = CircularCylinder2D(
        (0.03, -0.02),
        0.05,
        component_id="only-cylinder",
    )
    angles = np.linspace(0.2, 5.7, 9)
    center = np.asarray(cylinder.center)
    sources = center + np.column_stack(
        (0.30 * np.cos(angles), 0.30 * np.sin(angles))
    )
    receivers = center + np.column_stack(
        (0.25 * np.cos(angles + 0.3), 0.25 * np.sin(angles + 0.3))
    )
    strengths = np.linspace(0.7, 1.3, angles.size) * np.exp(
        1j * np.linspace(-0.2, 0.4, angles.size)
    )

    observed = multicylinder_scattered_field(
        receivers,
        sources,
        cylinders=(cylinder,),
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        source_strength=strengths,
        mode_order=14,
    )
    expected = penetrable_cylinder_scattered_field(
        receivers,
        sources,
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        radius=cylinder.radius,
        center=cylinder.center,
        source_strength=strengths,
    )

    np.testing.assert_allclose(observed, expected, rtol=3.0e-13, atol=3.0e-15)


def test_two_cylinder_truncation_converges_and_field_is_reciprocal() -> None:
    receivers, sources = _paired_points()
    convergence = converge_multicylinder_scattered_field(
        receivers,
        sources,
        cylinders=_two_cylinders(),
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        config=TruncationConfig(
            initial_order=4,
            order_step=4,
            maximum_order=20,
            relative_tolerance=1.0e-11,
            absolute_tolerance=1.0e-13,
        ),
    )

    assert convergence.mode_order <= 16
    assert len(convergence.history) >= 2
    assert convergence.history[-1].relative_change is not None
    assert convergence.history[-1].relative_change < 1.0e-11
    assert convergence.solution.linear_solve_relative_residual < 1.0e-13
    assert convergence.solution.system.condition_number < 2.0

    higher_order = multicylinder_scattered_field(
        receivers,
        sources,
        cylinders=_two_cylinders(),
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        mode_order=convergence.mode_order + 4,
    )
    reverse = multicylinder_scattered_field(
        sources,
        receivers,
        cylinders=_two_cylinders(),
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        mode_order=convergence.mode_order + 4,
    )
    np.testing.assert_allclose(
        convergence.scattered_field,
        higher_order,
        rtol=2.0e-11,
        atol=2.0e-13,
    )
    np.testing.assert_allclose(higher_order, reverse, rtol=2.0e-12, atol=2.0e-14)


def test_truncation_refinement_always_evaluates_non_aligned_maximum_order() -> None:
    receivers, sources = _paired_points()
    with pytest.raises(TruncationConvergenceError) as captured:
        converge_multicylinder_scattered_field(
            receivers,
            sources,
            cylinders=_two_cylinders(),
            k_exterior=K_EXTERIOR,
            k_interior=K_INTERIOR,
            config=TruncationConfig(
                initial_order=2,
                order_step=4,
                maximum_order=9,
                relative_tolerance=1.0e-30,
                absolute_tolerance=0.0,
                required_successive_passes=10,
            ),
        )

    assert [record.mode_order for record in captured.value.history] == [2, 6, 9]
    assert "mode order 9" in str(captured.value)


def test_component_permutation_does_not_change_full_response_matrix() -> None:
    receivers, sources = _paired_points()
    forward = solve_multicylinder_line_sources(
        _two_cylinders(),
        sources,
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        mode_order=16,
    )
    permuted = solve_multicylinder_line_sources(
        _two_cylinders(reverse=True),
        sources,
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        mode_order=16,
    )

    np.testing.assert_allclose(
        forward.scattered_field(receivers),
        permuted.scattered_field(receivers),
        rtol=5.0e-14,
        atol=5.0e-15,
    )


def test_zero_contrast_and_geometry_guards() -> None:
    receivers, sources = _paired_points()
    zero = multicylinder_scattered_field(
        receivers,
        sources,
        cylinders=_two_cylinders(),
        k_exterior=K_EXTERIOR,
        k_interior=K_EXTERIOR,
        mode_order=12,
    )
    assert np.max(np.abs(zero)) < 1.0e-15

    with pytest.raises(ValueError, match="strictly disjoint"):
        build_multicylinder_system(
            (
                CircularCylinder2D((0.0, 0.0), 0.1),
                CircularCylinder2D((0.15, 0.0), 0.1),
            ),
            K_EXTERIOR,
            K_INTERIOR,
        )
    with pytest.raises(ValueError, match="strictly outside"):
        solve_multicylinder_line_sources(
            _two_cylinders(),
            np.asarray(((-0.10, 0.0),)),
            k_exterior=K_EXTERIOR,
            k_interior=K_INTERIOR,
        )


def test_public_api_is_strict_about_real_geometry_and_canonicalizes_config() -> None:
    settings = TruncationConfig(
        initial_order=4.0,
        order_step=np.float64(2.0),
        maximum_order=12.0,
        relative_tolerance=np.float32(1.0e-8),
        absolute_tolerance=np.float64(1.0e-12),
        required_successive_passes=2.0,
    )
    assert settings.initial_order == 4
    assert type(settings.initial_order) is int
    assert settings.order_step == 2
    assert type(settings.order_step) is int
    assert settings.maximum_order == 12
    assert type(settings.maximum_order) is int
    assert type(settings.relative_tolerance) is float
    assert type(settings.absolute_tolerance) is float
    assert settings.required_successive_passes == 2
    assert type(settings.required_successive_passes) is int

    with pytest.raises(ValueError, match="non-negative integer"):
        TruncationConfig(initial_order=4.5)
    with pytest.raises(ValueError, match="real-valued"):
        CircularCylinder2D((0.0 + 0.0j, 0.0), 0.05)
    with pytest.raises(ValueError, match="real scalar"):
        CircularCylinder2D((0.0, 0.0), 0.05 + 0.0j)

    cylinders = _two_cylinders()
    with pytest.raises(ValueError, match="real-valued"):
        solve_multicylinder_line_sources(
            cylinders,
            np.asarray(((0.3 + 0.0j, 0.2),)),
            k_exterior=K_EXTERIOR,
            k_interior=K_INTERIOR,
        )

    solution = solve_multicylinder_line_sources(
        cylinders,
        np.asarray(((0.3, 0.2),)),
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        mode_order=8,
    )
    with pytest.raises(ValueError, match="real-valued"):
        solution.scattered_field(np.asarray(((0.3, -0.2 + 0.0j),)))
    assert not solution.source_points.flags.writeable
    assert not solution.source_strengths.flags.writeable
    assert not solution.boundary_normalized_coefficients.flags.writeable
    assert not solution.system.modes.flags.writeable
    assert not solution.system.system_matrix.flags.writeable


def test_prebuilt_system_rejects_fractional_mode_order_before_comparison() -> None:
    cylinders = _two_cylinders()
    sources = np.asarray(((0.3, 0.2),))
    system = build_multicylinder_system(
        cylinders,
        K_EXTERIOR,
        K_INTERIOR,
        mode_order=8,
    )

    with pytest.raises(ValueError, match="mode_order must be a non-negative integer"):
        solve_multicylinder_line_sources(
            cylinders,
            sources,
            k_exterior=K_EXTERIOR,
            k_interior=K_INTERIOR,
            mode_order=8.5,
            system=system,
        )

    canonical = solve_multicylinder_line_sources(
        cylinders,
        sources,
        k_exterior=K_EXTERIOR,
        k_interior=K_INTERIOR,
        mode_order=np.float64(8.0),
        system=system,
    )
    assert canonical.system is system


def test_multicomponent_kress_matches_independent_cylindrical_oracle() -> None:
    """The production solver and oracle share physics, not assembly code."""

    from gpr_bem_kress import Material
    from gpr_bem_kress.multicomponent import (
        solve_multicomponent_kress_tmz_total_field_batch,
    )
    from ordered_boundary import OrderedBoundary2D, circle

    eps0 = 8.8541878128e-12
    mu0 = 1.25663706212e-6
    angular_frequency = 2.0 * np.pi * 1.2e9
    exterior = Material(epsr=3.1)
    interior = Material(epsr=2.2)
    cylinders = _two_cylinders()
    boundary = OrderedBoundary2D(
        tuple(
            circle(
                cylinder.center,
                cylinder.radius,
                component_id=cylinder.component_id,
            ).discretize(32, require_even=True)
            for cylinder in cylinders
        )
    )
    receivers, sources = _paired_points()
    kress = solve_multicomponent_kress_tmz_total_field_batch(
        boundary,
        sources,
        receivers,
        angular_frequency,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
    )
    oracle = solve_multicylinder_line_sources(
        cylinders,
        sources,
        k_exterior=exterior.wavenumber(angular_frequency, eps0, mu0),
        k_interior=interior.wavenumber(angular_frequency, eps0, mu0),
        mode_order=20,
    )

    # Kress stores source-by-receiver data; the oracle's reusable evaluation
    # API stores receiver-by-source data.
    np.testing.assert_allclose(
        kress.scattered_receiver,
        oracle.scattered_field(receivers).T,
        rtol=2.0e-11,
        atol=2.0e-13,
    )
    assert kress.linear_system_relative_residual < 1.0e-12
