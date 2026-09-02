"""Analytic block-action, system-sign, and zero-contrast solver tests."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import h1vp, hankel1, jv, jvp

from gpr_bem_kress import (
    MullerAssemblyConfig,
    PROJECT_MULLER_CONVENTION,
    build_muller_difference_blocks,
    build_muller_system,
)
from ordered_boundary import circle, ellipse


RADIUS = 0.05
K_EXTERIOR = 12.0 - 0.1j
K_INTERIOR = 20.0 - 0.2j
NUM_NODES = 32


def _circle_eigenvalues(mode: int) -> dict[str, complex]:
    order = abs(int(mode))
    exterior_argument = K_EXTERIOR * RADIUS
    interior_argument = K_INTERIOR * RADIUS
    common = 0.5j * np.pi * RADIUS
    return {
        "delta_v": common
        * (
            jv(order, exterior_argument) * hankel1(order, exterior_argument)
            - jv(order, interior_argument) * hankel1(order, interior_argument)
        ),
        "delta_k": common
        * (
            K_EXTERIOR
            * jvp(order, exterior_argument)
            * hankel1(order, exterior_argument)
            - K_INTERIOR
            * jvp(order, interior_argument)
            * hankel1(order, interior_argument)
        ),
        "delta_kp": common
        * (
            K_EXTERIOR
            * jvp(order, exterior_argument)
            * hankel1(order, exterior_argument)
            - K_INTERIOR
            * jvp(order, interior_argument)
            * hankel1(order, interior_argument)
        ),
        "delta_t": common
        * (
            K_EXTERIOR**2
            * jvp(order, exterior_argument)
            * h1vp(order, exterior_argument)
            - K_INTERIOR**2
            * jvp(order, interior_argument)
            * h1vp(order, interior_argument)
        ),
    }


@pytest.fixture(scope="module")
def circle_blocks():
    curve = circle((0.0, 0.0), RADIUS, component_id="block-circle").discretize(
        NUM_NODES,
        require_even=True,
    )
    return build_muller_difference_blocks(curve, K_EXTERIOR, K_INTERIOR)


@pytest.mark.parametrize("mode", [0, 1, 3, 7, -3])
def test_all_circle_blocks_match_independent_fourier_bessel_actions(
    circle_blocks,
    mode: int,
) -> None:
    density = np.exp(1j * mode * circle_blocks.geometry.parameters)
    eigenvalues = _circle_eigenvalues(mode)
    physical_scales = {
        "delta_v": RADIUS,
        "delta_k": 1.0,
        "delta_kp": 1.0,
        "delta_t": 1.0 / RADIUS,
    }
    tolerances = {
        "delta_v": 1.0e-9,
        "delta_k": 1.0e-9,
        "delta_kp": 1.0e-9,
        "delta_t": 1.0e-8,
    }

    for name, eigenvalue in eigenvalues.items():
        observed = getattr(circle_blocks, name) @ density
        scaled_error = (
            np.linalg.norm(observed - eigenvalue * density)
            / np.sqrt(NUM_NODES)
            / physical_scales[name]
        )
        assert scaled_error < tolerances[name], (mode, name, scaled_error)


def test_assembly_records_a_consistent_near_direct_overlap(circle_blocks) -> None:
    overlap = circle_blocks.diagnostics["overlap"]
    assert overlap["pair_count"] > 0
    assert overlap["scaled_argument_min"] < 0.75
    assert overlap["scaled_argument_max"] > 0.75
    assert set(overlap["errors"]) == {"V", "K", "Kp", "T"}
    assert max(overlap["errors"].values()) < 2.0e-11


def test_system_quadrants_apply_project_signs_and_identity_once() -> None:
    curve = circle((0.0, 0.0), RADIUS, component_id="sign-circle").discretize(
        NUM_NODES,
        require_even=True,
    )
    system = build_muller_system(curve, K_EXTERIOR, K_INTERIOR)
    blocks = system.difference_blocks
    identity = np.eye(NUM_NODES)

    np.testing.assert_array_equal(system.a11, identity - blocks.delta_k)
    np.testing.assert_array_equal(system.a12, blocks.delta_v)
    np.testing.assert_array_equal(system.a21, -blocks.delta_t)
    np.testing.assert_array_equal(system.a22, identity + blocks.delta_kp)
    assert system.diagnostics["unknown_order"] == ("u_D", "u_N")
    assert system.diagnostics["solve_form"] == "direct_unsquared"
    assert PROJECT_MULLER_CONVENTION.system == (
        "[[I-Delta K, Delta V], [-Delta T, I+Delta Kp]]"
    )


def test_manufactured_modal_system_action_and_direct_solve() -> None:
    mode = 3
    curve = circle((0.0, 0.0), RADIUS, component_id="modal-circle").discretize(
        NUM_NODES,
        require_even=True,
    )
    system = build_muller_system(curve, K_EXTERIOR, K_INTERIOR)
    eigenvalues = _circle_eigenvalues(mode)
    fourier_mode = np.exp(1j * mode * curve.parameters)
    dirichlet_coefficient = 0.7 + 0.2j
    neumann_coefficient = -0.4 + 0.1j
    exact_solution = np.concatenate(
        (
            dirichlet_coefficient * fourier_mode,
            neumann_coefficient * fourier_mode,
        )
    )
    expected_rhs = np.concatenate(
        (
            (
                (1.0 - eigenvalues["delta_k"]) * dirichlet_coefficient
                + eigenvalues["delta_v"] * neumann_coefficient
            )
            * fourier_mode,
            (
                -eigenvalues["delta_t"] * dirichlet_coefficient
                + (1.0 + eigenvalues["delta_kp"]) * neumann_coefficient
            )
            * fourier_mode,
        )
    )

    observed_rhs = system.system_matrix @ exact_solution
    action_error = np.linalg.norm(observed_rhs - expected_rhs) / np.linalg.norm(
        expected_rhs
    )
    assert action_error < 1.0e-9
    recovered = np.linalg.solve(system.system_matrix, expected_rhs)
    recovery_error = np.linalg.norm(recovered - exact_solution) / np.linalg.norm(
        exact_solution
    )
    assert recovery_error < 1.0e-10


def test_zero_contrast_blocks_vanish_and_system_is_identity() -> None:
    curve = circle((0.0, 0.0), RADIUS, component_id="zero-circle").discretize(
        NUM_NODES,
        require_even=True,
    )
    system = build_muller_system(curve, K_EXTERIOR, K_EXTERIOR)
    blocks = system.difference_blocks
    scaled_norms = (
        np.linalg.norm(blocks.delta_v, ord=np.inf) / RADIUS,
        np.linalg.norm(blocks.delta_k, ord=np.inf),
        np.linalg.norm(blocks.delta_kp, ord=np.inf),
        RADIUS * np.linalg.norm(blocks.delta_t, ord=np.inf),
    )
    assert max(scaled_norms) < 5.0e-13
    np.testing.assert_allclose(
        system.system_matrix,
        np.eye(2 * NUM_NODES),
        rtol=0.0,
        atol=5.0e-13,
    )


def test_target_row_chunking_does_not_change_noncircular_blocks() -> None:
    curve = ellipse(
        (0.03, -0.04),
        0.08,
        0.045,
        rotation=0.31,
        component_id="chunk-ellipse",
    ).discretize(32, require_even=True)
    reference = build_muller_difference_blocks(
        curve,
        K_EXTERIOR,
        K_INTERIOR,
        config=MullerAssemblyConfig(target_chunk_size=32),
    )
    chunked = build_muller_difference_blocks(
        curve,
        K_EXTERIOR,
        K_INTERIOR,
        config=MullerAssemblyConfig(target_chunk_size=3),
    )
    for name in ("delta_v", "delta_k", "delta_kp", "delta_t"):
        np.testing.assert_allclose(
            getattr(chunked, name),
            getattr(reference, name),
            rtol=2.0e-14,
            atol=2.0e-14,
        )
