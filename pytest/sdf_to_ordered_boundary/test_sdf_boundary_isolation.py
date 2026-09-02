"""Geometry-contract isolation checks for the SDF study; no solver errors."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from ordered_boundary import (
    BoundaryValidationConfig,
    PeriodicCurve2D,
    PeriodicParameterization2D,
)
from sdf_to_ordered_boundary import (
    ArcLengthConfig,
    EllipseLevelSet,
    FrontendConfig,
    MethodAConfig,
    MethodBConfig,
    fit_method_a,
    fit_method_b,
    prepare_single_component,
)
from sdf_to_ordered_boundary.method_c import (
    MethodCConfig,
    RefinementStage,
    RefinementWeights,
    fit_method_c,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"


def test_importing_sdf_boundary_package_does_not_import_active_solver_modules() -> None:
    """Use a fresh interpreter so the assertion is independent of test order."""

    program = """
import sys
import sdf_to_ordered_boundary

forbidden = sorted(
    name
    for name in sys.modules
    if name == "solver_select"
    or name.startswith("solver_select.")
    or name == "gpr_bem"
    or name.startswith("gpr_bem.")
    or name.startswith("gpr_bem_")
)
if forbidden:
    raise SystemExit("active solver modules imported: " + ", ".join(forbidden))
"""
    environment = os.environ.copy()
    existing_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(SOLVERS_ROOT) + (
        os.pathsep + existing_path if existing_path else ""
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _sdf_package_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sdf_to_ordered_boundary" or alias.name.startswith(
                    "sdf_to_ordered_boundary."
                ):
                    findings.append(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "sdf_to_ordered_boundary" or module.startswith(
                "sdf_to_ordered_boundary."
            ):
                findings.append(f"{path}:{node.lineno}: from {module} import ...")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Also reject a literal dynamic-import target such as
            # importlib.import_module("sdf_to_ordered_boundary").
            if node.value == "sdf_to_ordered_boundary" or node.value.startswith(
                "sdf_to_ordered_boundary."
            ):
                findings.append(f"{path}:{node.lineno}: dynamic import target {node.value!r}")
    return findings


def test_active_solver_sources_do_not_import_sdf_boundary_research_package() -> None:
    active_sources = [SOLVERS_ROOT / "solver_select.py"]
    for package in sorted(SOLVERS_ROOT.glob("gpr_bem*")):
        if package.is_dir():
            active_sources.extend(sorted(package.rglob("*.py")))
    assert active_sources, "No active solver sources were found to audit."
    findings = [
        finding
        for path in active_sources
        for finding in _sdf_package_imports(path)
    ]
    assert not findings, "Active solver sources depend on the isolated study:\n" + "\n".join(
        findings
    )


def _small_arc_length_config(sample_count: int) -> ArcLengthConfig:
    return ArcLengthConfig(
        dense_resolution=512,
        refit_sample_count=sample_count,
        validation_resolution=256,
    )


def _small_method_c_config(sample_count: int) -> MethodCConfig:
    return MethodCConfig(
        dense_sample_count=128,
        validation_sample_count=256,
        checkpoint_interval=4,
        stages=(
            RefinementStage(
                "attach",
                iterations=8,
                relative_learning_rate=8.0e-4,
                weights=RefinementWeights(
                    fidelity=1.0,
                    anchor=5.0e-2,
                    spectral=1.0e-9,
                ),
            ),
            RefinementStage(
                "regularize",
                iterations=6,
                relative_learning_rate=3.0e-4,
                weights=RefinementWeights(
                    fidelity=1.0,
                    anchor=2.0e-2,
                    speed=5.0e-3,
                    regularity=1.0e-2,
                ),
            ),
        ),
        final_stage=RefinementStage(
            "final",
            iterations=4,
            relative_learning_rate=1.0e-4,
            weights=RefinementWeights(fidelity=1.0, anchor=5.0e-2),
        ),
        arc_length=_small_arc_length_config(sample_count),
    )


def _assert_existing_node_contract(result) -> None:
    assert result.status == "success"
    assert isinstance(result.parameterization, PeriodicParameterization2D)
    nodes = result.parameterization.discretize(64, require_even=True)
    assert isinstance(nodes, PeriodicCurve2D)
    assert nodes.num_nodes == 64
    assert nodes.orientation == "counterclockwise"
    assert nodes.parameters[-1] < nodes.parameter_origin + nodes.period
    np.testing.assert_allclose(
        nodes.parameters,
        nodes.parameter_origin + nodes.period * np.arange(64) / 64,
        rtol=0.0,
        atol=2.0e-15,
    )
    assert np.all(np.isfinite(nodes.points))
    assert np.all(np.isfinite(nodes.first_derivatives))
    assert np.all(np.isfinite(nodes.second_derivatives))
    assert np.all(np.isfinite(nodes.speeds))
    assert np.all(np.isfinite(nodes.tangents))
    assert np.all(np.isfinite(nodes.normals))
    assert np.all(np.isfinite(nodes.curvatures))
    assert np.all(np.isfinite(nodes.arc_length_weights))
    assert np.all(nodes.speeds > 0.0)
    np.testing.assert_allclose(
        np.linalg.norm(nodes.tangents, axis=1), 1.0, rtol=3.0e-14, atol=3.0e-14
    )
    np.testing.assert_allclose(
        np.linalg.norm(nodes.normals, axis=1), 1.0, rtol=3.0e-14, atol=3.0e-14
    )
    np.testing.assert_allclose(
        np.sum(nodes.tangents * nodes.normals, axis=1),
        0.0,
        rtol=0.0,
        atol=3.0e-14,
    )
    np.testing.assert_allclose(
        nodes.arc_length_weights,
        nodes.parameter_step * nodes.speeds,
        rtol=2.0e-15,
        atol=2.0e-15,
    )
    for values in (
        nodes.parameters,
        nodes.points,
        nodes.first_derivatives,
        nodes.second_derivatives,
        nodes.speeds,
        nodes.tangents,
        nodes.normals,
        nodes.curvatures,
        nodes.arc_length_weights,
    ):
        assert not values.flags.writeable
    with pytest.raises(ValueError, match="even"):
        result.parameterization.discretize(63, require_even=True)


def test_successful_methods_a_b_c_use_existing_continuous_and_node_contracts() -> None:
    field = EllipseLevelSet((0.1, -0.1), 1.2, 0.6, rotation=0.3)
    frontend = prepare_single_component(
        field,
        FrontendConfig(
            bounds=((-1.5, -1.2), (1.7, 1.0)),
            grid_shape=(65, 65),
            projected_samples=96,
        ),
    )
    arc_length = _small_arc_length_config(frontend.parameters.size)
    method_a = fit_method_a(
        frontend,
        config=MethodAConfig(arclength=arc_length),
        component_id="method-a",
    )
    method_b = fit_method_b(
        frontend,
        config=MethodBConfig(
            bandwidth=8,
            arclength=arc_length,
            validation=BoundaryValidationConfig(num_samples_per_component=256),
        ),
        component_id="method-b",
    )
    method_c = fit_method_c(
        field,
        frontend,
        method_b,
        config=_small_method_c_config(frontend.parameters.size),
    )

    for result in (method_a, method_b, method_c):
        _assert_existing_node_contract(result)
