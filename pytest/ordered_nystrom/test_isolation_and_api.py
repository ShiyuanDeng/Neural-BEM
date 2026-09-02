"""Isolation and public-contract tests for the opt-in solver candidate."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

import gpr_bem_mod
import gpr_bem_mod.ordered_nystrom as ordered_nystrom
from gpr_bem_mod.ordered_nystrom import (
    adapt_periodic_curve,
    build_muller_difference_blocks,
    build_ordered_tmz_frequency_system,
)
from ordered_boundary import PeriodicCurve2D, circle, fourier_curve
import solver_select


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_ROOT = REPOSITORY_ROOT / "solvers" / "gpr_bem_mod" / "ordered_nystrom"
KRESS_ROOT = REPOSITORY_ROOT / "solvers" / "periodic_kress"
FORBIDDEN_NUMERICAL_PACKAGES = {
    "gpr_bem_kdiff",
    "gpr_bem_qbx",
    "kernel_diff_ref",
    "nystrom_ref",
    "scratchpad",
    "sdf_to_ordered_boundary",
    "torch",
}


def _absolute_import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_candidate_does_not_depend_on_oracle_archived_or_sdf_numerics() -> None:
    sources = sorted(CANDIDATE_ROOT.glob("*.py")) + sorted(KRESS_ROOT.glob("*.py"))
    assert sources
    findings = {
        str(path.relative_to(REPOSITORY_ROOT)): sorted(
            _absolute_import_roots(path) & FORBIDDEN_NUMERICAL_PACKAGES
        )
        for path in sources
    }
    findings = {path: imports for path, imports in findings.items() if imports}
    assert not findings, findings


def test_candidate_remains_direct_import_only() -> None:
    assert "ordered_nystrom" not in gpr_bem_mod.__all__
    assert set(ordered_nystrom.__all__).isdisjoint(gpr_bem_mod.__all__)
    assert all("ordered_nystrom" not in package for package in solver_select.SOLVER_NAMES.values())


def test_adapter_preserves_the_node_owned_curve_and_weights() -> None:
    curve = circle((0.12, -0.08), 0.7, component_id="api-circle").discretize(
        16,
        require_even=True,
    )
    point_snapshot = curve.points.copy()
    weight_snapshot = curve.arc_length_weights.copy()

    adapter = adapt_periodic_curve(curve)
    blocks = build_muller_difference_blocks(curve, 2.1 - 0.03j, 3.4 - 0.07j)

    assert isinstance(curve, PeriodicCurve2D)
    assert adapter.curve is curve
    assert adapter.points is curve.points
    assert adapter.normals is curve.normals
    assert adapter.arc_length_weights is curve.arc_length_weights
    np.testing.assert_array_equal(curve.points, point_snapshot)
    np.testing.assert_array_equal(curve.arc_length_weights, weight_snapshot)
    assert blocks.geometry is curve
    assert blocks.diagnostics["source_jacobian_included"] is True
    assert blocks.diagnostics["parameter_step_included"] is True
    assert blocks.diagnostics["unknowns_are_weighted"] is False

    for values in (
        adapter.theta,
        adapter.theta_first_derivatives,
        adapter.theta_second_derivatives,
        adapter.theta_speeds,
        blocks.delta_v,
        blocks.delta_k,
        blocks.delta_kp,
        blocks.delta_t,
    ):
        assert not values.flags.writeable


def test_solver_owned_discretization_restrictions_fail_explicitly() -> None:
    parameterization = circle((0.0, 0.0), 1.0, component_id="restriction-circle")
    with pytest.raises(TypeError, match="PeriodicCurve2D"):
        adapt_periodic_curve(parameterization)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="even number"):
        adapt_periodic_curve(parameterization.discretize(15))
    with pytest.raises(ValueError, match="at least 8"):
        adapt_periodic_curve(parameterization.discretize(6))


def test_adapter_affinely_normalizes_a_nonstandard_period_without_changing_ds() -> None:
    cosine = np.asarray(((0.2, -0.1), (0.7, 0.0)))
    sine = np.asarray(((0.0, 0.0), (0.0, 0.7)))
    curve = fourier_curve(
        cosine,
        sine,
        component_id="nonstandard-period",
        period=3.7,
        parameter_origin=-0.4,
    ).discretize(16, require_even=True)
    adapter = adapt_periodic_curve(curve)

    np.testing.assert_allclose(
        adapter.theta,
        2.0 * np.pi * np.arange(16) / 16,
        rtol=0.0,
        atol=2.0e-15,
    )
    np.testing.assert_allclose(adapter.theta_speeds, 0.7, rtol=2.0e-14)
    np.testing.assert_allclose(
        adapter.theta_step * adapter.theta_speeds,
        curve.arc_length_weights,
        rtol=2.0e-14,
    )


def test_high_level_material_api_rejects_magnetic_contrast() -> None:
    curve = circle((0.0, 0.0), 0.05).discretize(16, require_even=True)
    exterior = gpr_bem_mod.Material(epsr=6.0)
    magnetic_interior = gpr_bem_mod.Material(epsr=3.0, mur=1.2)
    with pytest.raises(ValueError, match="nonmagnetic"):
        build_ordered_tmz_frequency_system(
            curve,
            2.0 * np.pi * 1.0e9,
            exterior=exterior,
            interior=magnetic_interior,
            eps0=8.854187817e-12,
            mu0=4.0e-7 * np.pi,
        )


def test_high_level_material_api_rejects_unvalidated_lossy_convention() -> None:
    curve = circle((0.0, 0.0), 0.05).discretize(16, require_even=True)
    exterior = gpr_bem_mod.Material(epsr=6.0)
    lossy_interior = gpr_bem_mod.Material(epsr=3.0, sigma=0.01)
    with pytest.raises(ValueError, match="lossless materials only"):
        build_ordered_tmz_frequency_system(
            curve,
            2.0 * np.pi * 1.0e9,
            exterior=exterior,
            interior=lossy_interior,
            eps0=8.854187817e-12,
            mu0=4.0e-7 * np.pi,
        )
