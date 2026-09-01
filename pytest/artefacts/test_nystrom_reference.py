"""Correctness tests for the standalone Nystrom reference solver.

This is the *oracle* for the IBIM packages, so it is checked against things that
do not depend on it: the Fourier-Bessel series for a circle, exact identities
(zero contrast, reciprocity, incident-field consistency), and agreement between
the circle path and the general-curve paths degenerated to a circle.

It imports ``nystrom_ref`` directly rather than through the ``--solver`` alias in
``conftest.py``, the same way ``test_solver_comparison.py`` imports both solver
packages by their real names. The thresholds are loose by five or more orders of
magnitude; the convergence study lives in
``docs/nystrom_reference_study.md`` and is not rerun here.
"""

from __future__ import annotations

import numpy as np
import pytest

import config.simulation_config as cfg
import gpr_bem_ref
from nystrom_ref import (
    build_curve,
    circle_parameterization,
    ellipse_parameterization,
    solve_transmission,
    star_parameterization,
)

RADIUS = float(cfg.TARGET_RADIUS)
CENTER = (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y))


def _scan(num_pairs: int = 12, standoff: float = 0.27, separation: float = 0.12):
    angles = np.linspace(0.0, 2.0 * np.pi, num_pairs, endpoint=False, dtype=float)
    sources = np.column_stack(
        (
            CENTER[0] + standoff * np.cos(angles - 0.5 * separation),
            CENTER[1] + standoff * np.sin(angles - 0.5 * separation),
        )
    )
    receivers = np.column_stack(
        (
            CENTER[0] + standoff * np.cos(angles + 0.5 * separation),
            CENTER[1] + standoff * np.sin(angles + 0.5 * separation),
        )
    )
    return sources, receivers


def _wavenumbers(frequency_hz: float) -> tuple[complex, complex]:
    angular_frequency = 2.0 * np.pi * frequency_hz
    exterior = gpr_bem_ref.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_ref.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)
    return (
        exterior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0),
        interior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0),
    )


def _paired_scattered(solution) -> np.ndarray:
    """The solver returns every Tx/Rx combination; the oracle pairs them up."""

    return np.diag(solution.scattered)


def _exact(receivers, sources, k_exterior, k_interior) -> np.ndarray:
    return gpr_bem_ref.penetrable_cylinder_scattered_field(
        receivers, sources, k_exterior=k_exterior, k_interior=k_interior, radius=RADIUS, center=CENTER
    )


def test_zero_contrast_produces_no_scattered_field() -> None:
    sources, receivers = _scan()
    k_exterior, _ = _wavenumbers(1.5e9)
    curve = build_curve(circle_parameterization(CENTER, RADIUS), 256, "circle")
    solution = solve_transmission(curve, sources, receivers, k_exterior, k_exterior)
    assert np.max(np.abs(solution.scattered)) < 1.0e-12


@pytest.mark.parametrize("frequency_hz", [0.5e9, 1.5e9, 2.5e9])
def test_circle_matches_fourier_bessel_series(frequency_hz: float) -> None:
    sources, receivers = _scan()
    k_exterior, k_interior = _wavenumbers(frequency_hz)
    curve = build_curve(circle_parameterization(CENTER, RADIUS), 128, "circle")
    solution = solve_transmission(curve, sources, receivers, k_exterior, k_interior)
    exact = _exact(receivers, sources, k_exterior, k_interior)

    relative_error = float(
        np.linalg.norm(_paired_scattered(solution) - exact) / np.linalg.norm(exact)
    )
    assert relative_error < 1.0e-9, relative_error
    assert solution.relative_residual < 1.0e-10
    # D_e u_inc - S_e q_inc must vanish outside the scatterer. This is the
    # convention check: it fails loudly on a flipped normal or a wrong jump sign.
    assert solution.incident_consistency < 1.0e-10


def test_refinement_does_not_degrade_the_circle_solution() -> None:
    sources, receivers = _scan()
    k_exterior, k_interior = _wavenumbers(2.5e9)
    exact = _exact(receivers, sources, k_exterior, k_interior)

    errors = []
    for num_nodes in (128, 256, 512):
        curve = build_curve(circle_parameterization(CENTER, RADIUS), num_nodes, "circle")
        solution = solve_transmission(curve, sources, receivers, k_exterior, k_interior)
        errors.append(
            float(np.linalg.norm(_paired_scattered(solution) - exact) / np.linalg.norm(exact))
        )
    assert errors[1] <= errors[0] and errors[2] <= errors[1], errors


@pytest.mark.parametrize(
    "name,parameterization",
    [
        ("ellipse", ellipse_parameterization(CENTER, RADIUS, RADIUS)),
        ("star", star_parameterization(CENTER, RADIUS, 0.0, 5)),
    ],
)
def test_general_curve_paths_degenerate_to_the_circle(name: str, parameterization) -> None:
    """Self-convergence cannot catch a flipped normal on a general curve; this can."""

    sources, receivers = _scan()
    k_exterior, k_interior = _wavenumbers(1.5e9)
    solution = solve_transmission(
        build_curve(parameterization, 256, name), sources, receivers, k_exterior, k_interior
    )
    exact = _exact(receivers, sources, k_exterior, k_interior)
    relative_error = float(
        np.linalg.norm(_paired_scattered(solution) - exact) / np.linalg.norm(exact)
    )
    assert relative_error < 1.0e-9, relative_error


def test_star_shaped_curve_is_reciprocal() -> None:
    sources, receivers = _scan()
    k_exterior, k_interior = _wavenumbers(1.5e9)
    parameterization = star_parameterization(CENTER, RADIUS, 0.25, 5)

    forward = solve_transmission(
        build_curve(parameterization, 512, "star"), sources, receivers, k_exterior, k_interior
    )
    swapped = solve_transmission(
        build_curve(parameterization, 512, "star"), receivers, sources, k_exterior, k_interior
    )
    asymmetry = float(
        np.max(np.abs(forward.scattered - swapped.scattered.T)) / np.max(np.abs(forward.scattered))
    )
    assert asymmetry < 1.0e-8, asymmetry


@pytest.mark.parametrize(
    "name,parameterization",
    [
        ("ellipse", ellipse_parameterization(CENTER, RADIUS * 1.4, RADIUS / 1.4)),
        ("star", star_parameterization(CENTER, RADIUS, 0.25, 5)),
    ],
)
def test_non_circular_curves_self_converge(name: str, parameterization) -> None:
    sources, receivers = _scan()
    k_exterior, k_interior = _wavenumbers(2.5e9)
    reference = _paired_scattered(
        solve_transmission(
            build_curve(parameterization, 1024, name), sources, receivers, k_exterior, k_interior
        )
    )

    errors = []
    for num_nodes in (128, 256, 512):
        solution = solve_transmission(
            build_curve(parameterization, num_nodes, name), sources, receivers, k_exterior, k_interior
        )
        errors.append(
            float(np.linalg.norm(_paired_scattered(solution) - reference) / np.linalg.norm(reference))
        )
    assert errors[0] < 1.0e-6, errors
    assert errors[1] <= errors[0] and errors[2] <= errors[1], errors


def test_odd_node_counts_are_rejected() -> None:
    with pytest.raises(ValueError, match="even number of nodes"):
        build_curve(circle_parameterization(CENTER, RADIUS), 127, "circle")
