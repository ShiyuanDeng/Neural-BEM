"""Structural checks for the artifact-only parameterization study notebook."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK = (
    Path(__file__).resolve().parents[1]
    / "notebooks"
    / "sdf_boundary_parameterization_comparison.ipynb"
)


def _source(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def test_comparison_notebook_is_valid_unexecuted_v4_json() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert isinstance(notebook["cells"], list)
    assert notebook["cells"]
    assert notebook["cells"][0]["cell_type"] == "markdown"
    for cell in notebook["cells"]:
        assert cell["cell_type"] in {"markdown", "code"}
        assert isinstance(_source(cell), str)
        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs") == []
            ast.parse(_source(cell))


def test_notebook_reads_artifacts_without_importing_or_calling_fitting_code() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code = "\n".join(
        _source(cell) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    lowered = code.lower()

    forbidden_text = (
        "sdf_to_ordered_boundary",
        "ordered_boundary",
        "torch",
        "pandas",
        "nbformat",
        "scipy",
        "skimage",
        "fit_method_a",
        "fit_method_b",
        "fit_method_c",
        "prepare_single_component",
        "extract_frontend_components",
        "project_to_zero_set",
        "fit_fourier",
        "cubicspline",
        "subprocess",
        "os.system",
    )
    for forbidden in forbidden_text:
        assert forbidden not in lowered

    allowed_import_roots = {
        "collections",
        "csv",
        "json",
        "math",
        "matplotlib",
        "numpy",
        "os",
        "pathlib",
    }
    tree = ast.parse(code)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots <= allowed_import_roots

    assert "csv.DictReader" in code
    assert "json.load" in code
    assert "np.load" in code
    assert "allow_pickle=False" in code
    assert "metrics.csv" in code
    assert "manifest.json" in code
    assert "metrics.json" in code
    assert '"pytest" / "results" / "sdf_boundary_parameterization"' in code
    assert '"results" / "sdf_boundary_parameterization"' in code
    assert "timestamped_roots" in code
    assert 'key = (record["shape"], record["grid"], record["projected_samples"])' in code
    assert "assert not mismatched" in code


def test_notebook_explicitly_covers_status_grid_and_bandwidth_convergence() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    all_text = "\n".join(_source(cell) for cell in notebook["cells"]).lower()
    code = "\n".join(
        _source(cell) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )

    for shape in ("circle", "ellipse", "star"):
        assert shape in all_text
    for phrase in (
        "artifact-only",
        "does not choose a winner",
        "grid convergence",
        "bandwidth convergence",
        "frozen-curve even-node convergence",
        "failure",
        "fallback",
        "self-intersection",
    ):
        assert phrase in all_text
    for identifier in (
        "shape_label",
        "grid_resolution",
        "projected_samples",
        "bandwidth",
        "status",
        "reference_hausdorff",
        "normalized_sdf_max",
        "normalized_sdf_rms",
        "sdf_rms",
        "speed_ratio",
        "self_intersections",
        "spectral_tail_0",
        "spectral_tail_1",
        "area",
        "perimeter",
        "frozen_curve_sampling",
    ):
        assert identifier in code
