"""Integrity and scope checks for checked non-solver boundary evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = REPOSITORY_ROOT / "results" / "sdf_boundary_parameterization"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_non_solver_scope(payload: dict, expected_scope: str) -> None:
    assert payload["measurement_scope"] == expected_scope
    assert payload["contains_bie_assembly"] is False
    assert payload["contains_linear_solve"] is False
    assert payload["contains_solver_error_metrics"] is False


def test_checked_geometry_studies_declare_scope_and_resolve_artifact_paths() -> None:
    for directory_name in ("smoke-20260902", "study-20260902"):
        manifest = _load_json(RESULT_ROOT / directory_name / "manifest.json")
        _assert_non_solver_scope(manifest, "geometry_parameterization")

    smoke_root = RESULT_ROOT / "smoke-20260902"
    rows = _load_json(smoke_root / "metrics.json")
    assert rows
    solver_only_fields = {
        "condition_number",
        "linear_system_residual",
        "relative_scattered_field_error",
        "scattered_field",
        "solved_density",
    }
    for row in rows:
        assert solver_only_fields.isdisjoint(row)
        for artifact_path in row["artifacts"].values():
            assert (REPOSITORY_ROOT / artifact_path).is_file()


def test_checked_scalar_proxy_declares_scope_and_hashes_current_files() -> None:
    proxy_root = RESULT_ROOT / "kress-scalar-proxy-20260902"
    manifest = _load_json(proxy_root / "manifest.json")
    metrics = _load_json(proxy_root / "metrics.json")
    _assert_non_solver_scope(manifest, "manufactured_scalar_quadrature_proxy")
    _assert_non_solver_scope(metrics, "manufactured_scalar_quadrature_proxy")

    for filename, expected_hash in manifest["files"].items():
        assert _sha256(proxy_root / filename) == expected_hash
    for item in manifest["frozen_curve_inputs"]:
        path = REPOSITORY_ROOT / item["path"]
        assert path.is_file()
        assert _sha256(path) == item["sha256"]

    study_root = RESULT_ROOT / "study-20260902"
    source = manifest["source_study"]
    assert _sha256(study_root / "manifest.json") == source["manifest_sha256"]
    assert _sha256(study_root / "metrics.json") == source["metrics_sha256"]
