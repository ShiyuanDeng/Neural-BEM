"""Isolation and public-contract tests for the direct-import Kress sibling."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import gpr_bem_kress
from gpr_bem_kress import (
    Material,
    adapt_periodic_curve,
    build_muller_difference_blocks,
    build_kress_tmz_frequency_system,
)
from ordered_boundary import PeriodicCurve2D, circle, fourier_curve
import solver_select


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"
KRESS_PACKAGE_ROOT = SOLVERS_ROOT / "gpr_bem_kress"
OLD_NESTED_ROOT = SOLVERS_ROOT / "gpr_bem_mod" / "ordered_nystrom"
KRESS_ROOT = REPOSITORY_ROOT / "solvers" / "periodic_kress"
FORBIDDEN_NUMERICAL_PACKAGES = {
    "gpr_bem_mod",
    "gpr_bem_ref",
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


def test_kress_does_not_depend_on_oracle_archived_or_sdf_numerics() -> None:
    sources = sorted(KRESS_PACKAGE_ROOT.glob("*.py")) + sorted(KRESS_ROOT.glob("*.py"))
    assert sources
    findings = {
        str(path.relative_to(REPOSITORY_ROOT)): sorted(
            _absolute_import_roots(path) & FORBIDDEN_NUMERICAL_PACKAGES
        )
        for path in sources
    }
    findings = {path: imports for path, imports in findings.items() if imports}
    assert not findings, findings


def test_clean_import_does_not_load_mod_ref_sdf_or_torch() -> None:
    code = """
import sys
import gpr_bem_kress

forbidden = {"gpr_bem_mod", "gpr_bem_ref", "sdf_to_ordered_boundary", "torch"}
loaded = sorted(forbidden & {name.split(".", 1)[0] for name in sys.modules})
if loaded:
    raise SystemExit(f"forbidden packages loaded by gpr_bem_kress: {loaded}")
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SOLVERS_ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_kress_is_a_direct_import_sibling_not_a_mod_subpackage() -> None:
    assert not OLD_NESTED_ROOT.exists()
    assert "gpr_bem_kress" not in solver_select.SOLVER_NAMES.values()
    expected_public_api = {
        "KressSolveConfig",
        "KressTMzForwardResult",
        "KressTMzFrequencySystem",
        "KressTMzMultiFrequencyForwardResult",
        "Material",
        "build_exterior_receiver_operator",
        "build_kress_tmz_frequency_system",
        "kress_incident_trace_on_boundary",
        "solve_kress_tmz_frequency_response",
        "solve_kress_tmz_total_field_batch",
    }
    assert expected_public_api <= set(gpr_bem_kress.__all__)
    assert not any(name.startswith("OrderedTMz") for name in gpr_bem_kress.__all__)


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
    assert blocks.config == gpr_bem_kress.MullerAssemblyConfig()
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
    exterior = Material(epsr=6.0)
    magnetic_interior = Material(epsr=3.0, mur=1.2)
    with pytest.raises(ValueError, match="nonmagnetic"):
        build_kress_tmz_frequency_system(
            curve,
            2.0 * np.pi * 1.0e9,
            exterior=exterior,
            interior=magnetic_interior,
            eps0=8.854187817e-12,
            mu0=4.0e-7 * np.pi,
        )


def test_high_level_material_api_rejects_unvalidated_lossy_convention() -> None:
    curve = circle((0.0, 0.0), 0.05).discretize(16, require_even=True)
    exterior = Material(epsr=6.0)
    lossy_interior = Material(epsr=3.0, sigma=0.01)
    with pytest.raises(ValueError, match="lossless materials only"):
        build_kress_tmz_frequency_system(
            curve,
            2.0 * np.pi * 1.0e9,
            exterior=exterior,
            interior=lossy_interior,
            eps0=8.854187817e-12,
            mu0=4.0e-7 * np.pi,
        )
