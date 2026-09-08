"""Shared scene, objective and topological-derivative helpers for the review probes.

Everything here is read-only with respect to the repository.  The forward model
is the independent ``multicylinder_ref`` cylindrical-harmonic oracle, never the
Kress/Mueller BEM, so no discretization question is entangled with the
derivative question these probes ask.  The scalar objective is the production
``normalized_complex_residual`` helper used by the radial inverse.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "solvers"))

import config.two_circle_config as cfg  # noqa: E402
from multicylinder_ref import (  # noqa: E402
    CircularCylinder2D,
    line_source_incident_field_matrix,
    solve_multicylinder_line_sources,
)
from sdf_inverse.optimization import normalized_complex_residual  # noqa: E402

EPS0 = float(cfg.EPS0)
MU0 = float(cfg.MU0)
EPSR_EXT = float(cfg.SAND_EPSR)
EPSR_INT = float(cfg.PLASTIC_EPSR)
CENTER = (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y))
CENTERS = np.asarray(cfg.TARGET_CIRCLE_CENTERS, dtype=float)
RADII = np.asarray(cfg.TARGET_CIRCLE_RADII, dtype=float)
TX_RX_OFFSET = float(cfg.TX_RX_OFFSET)

# Acquisition of pytest/solver_comparisons/test_two_circle_comparison.py.
STANDOFF = 0.30
NUM_PAIRS = 24
# Source strength of run_sdf_inverse_comparison._build_problem.
SOURCE_STRENGTH = 1.0e-6 + 0.0j

COMPONENT_A = CircularCylinder2D(
    center=(float(CENTERS[0][0]), float(CENTERS[0][1])),
    radius=float(RADII[0]),
    component_id="A",
)
COMPONENT_B = CircularCylinder2D(
    center=(float(CENTERS[1][0]), float(CENTERS[1][1])),
    radius=float(RADII[1]),
    component_id="B",
)


def ring_scan(num_pairs: int = NUM_PAIRS, standoff: float = STANDOFF):
    """Return the paired source/receiver ring used by the two-circle case."""

    angles = np.linspace(0.0, 2.0 * np.pi, num_pairs, endpoint=False)
    separation = TX_RX_OFFSET / standoff
    sources = np.column_stack(
        (
            CENTER[0] + standoff * np.cos(angles),
            CENTER[1] + standoff * np.sin(angles),
        )
    )
    receivers = np.column_stack(
        (
            CENTER[0] + standoff * np.cos(angles + separation),
            CENTER[1] + standoff * np.sin(angles + separation),
        )
    )
    return sources, receivers


def wavenumbers(frequency_hz: float) -> tuple[complex, complex]:
    """Exterior and interior wavenumbers under ``Material.wavenumber``."""

    angular = 2.0 * math.pi * frequency_hz
    return (
        complex(angular * np.sqrt(MU0 * EPS0 * EPSR_EXT)),
        complex(angular * np.sqrt(MU0 * EPS0 * EPSR_INT)),
    )


def paired_scattered(cylinders, sources, receivers, k_exterior, k_interior,
                     strength=SOURCE_STRENGTH):
    """Paired-diagonal scattered response, the production measurement set."""

    solution = solve_multicylinder_line_sources(
        cylinders,
        sources,
        k_exterior=k_exterior,
        k_interior=k_interior,
        source_strength=strength,
    )
    return np.diag(solution.scattered_field(receivers)).copy()


def objective(predicted_column, observed_column, weight: float = 1.0):
    """``0.5 * ||normalized_complex_residual||^2`` for one frequency column."""

    predicted = np.asarray(predicted_column, dtype=np.complex128).reshape(-1, 1)
    observed = np.asarray(observed_column, dtype=np.complex128).reshape(-1, 1)
    residual, relative = normalized_complex_residual(
        predicted, observed, np.array([weight], dtype=float)
    )
    return 0.5 * float(np.dot(residual, residual)), relative


def observed_scale(observed_column) -> float:
    """``s_f``, the fixed observed-column norm the objective divides by."""

    return float(np.linalg.norm(np.asarray(observed_column)))


def current_domain_td(points, cylinders, sources, receivers, complex_residual,
                      scale, k_exterior, k_interior, strength=SOURCE_STRENGTH,
                      weight: float = 1.0):
    """``D_T J(z; Omega)`` at ``points`` for one frequency and a non-empty ``Omega``.

    ``complex_residual`` is the paired ``p - d``.  ``u`` carries the physical
    source strength; the reciprocal Green response ``g`` uses a unit source.
    """

    forward = solve_multicylinder_line_sources(
        cylinders, sources, k_exterior=k_exterior, k_interior=k_interior,
        source_strength=strength,
    )
    reciprocal = solve_multicylinder_line_sources(
        cylinders, receivers, k_exterior=k_exterior, k_interior=k_interior,
        source_strength=1.0,
    )
    u = forward.total_field(points)
    g = reciprocal.total_field(points)
    accumulated = np.sum(
        np.conjugate(complex_residual)[None, :] * u * g, axis=1
    )
    contrast = k_interior * k_interior - k_exterior * k_exterior
    return (weight / scale**2) * np.real(contrast * accumulated)


def empty_domain_td(points, sources, receivers, complex_residual, scale,
                    k_exterior, k_interior, strength=SOURCE_STRENGTH,
                    weight: float = 1.0):
    """``D_T J(z; empty)``: the same expression with free-space Green fields."""

    u = line_source_incident_field_matrix(
        points, sources, k_exterior=k_exterior, source_strength=strength
    )
    g = line_source_incident_field_matrix(
        points, receivers, k_exterior=k_exterior, source_strength=1.0
    )
    accumulated = np.sum(
        np.conjugate(complex_residual)[None, :] * u * g, axis=1
    )
    contrast = k_interior * k_interior - k_exterior * k_exterior
    return (weight / scale**2) * np.real(contrast * accumulated)


def inspection_grid(num_points: int, *, radius: float = 0.20,
                    exclude=(), buffer: float = 0.004):
    """Cell-centre-free node grid clipped to a disk about the scene centre.

    The disk keeps every inspection point at least ``STANDOFF - radius`` from
    every source and receiver, so the logarithmic station singularities of the
    raw field cannot reach the grid.
    """

    axis_x = np.linspace(CENTER[0] - radius, CENTER[0] + radius, num_points)
    axis_y = np.linspace(CENTER[1] - radius, CENTER[1] + radius, num_points)
    grid_x, grid_y = np.meshgrid(axis_x, axis_y, indexing="xy")
    points = np.column_stack((grid_x.ravel(), grid_y.ravel()))
    keep = np.linalg.norm(points - np.asarray(CENTER), axis=1) <= radius
    for cylinder in exclude:
        keep &= (
            np.linalg.norm(points - np.asarray(cylinder.center), axis=1)
            > cylinder.radius + buffer
        )
    return axis_x, axis_y, grid_x, grid_y, points, keep
