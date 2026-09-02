"""Manufactured scalar Kress-action checks, not BIE/PDE solver errors."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ordered_boundary import circle, ellipse
from sdf_to_ordered_boundary.representations import (
    FourierBoundary,
    PeriodicSplineBoundary,
)
from scratchpad.sdf_boundary_kress_proxy import (
    TWO_PI,
    _reconstruct_artifact_curve,
    composite_gauss_reference,
    exact_circle_poisson_action,
    kress_log_weights,
    logarithmic_product_rule_action,
    run_benchmark,
)


def _circulant_weights(num_nodes: int) -> np.ndarray:
    weights = kress_log_weights(num_nodes)
    indices = np.arange(num_nodes)
    return weights[(indices[:, None] - indices[None, :]) % num_nodes]


@pytest.mark.parametrize("num_nodes", [16, 32, 64])
@pytest.mark.parametrize("mode", [1, 3, 7])
def test_kress_weights_reproduce_resolved_circle_modes(
    num_nodes: int,
    mode: int,
) -> None:
    if mode >= num_nodes // 2:
        pytest.skip("mode must lie below the Kress Nyquist term")
    parameters = TWO_PI * np.arange(num_nodes, dtype=np.float64) / num_nodes
    weights = _circulant_weights(num_nodes)

    cosine = 0.5 * weights @ np.cos(mode * parameters)
    sine = 0.5 * weights @ np.sin(mode * parameters)
    expected_cosine = -(np.pi / mode) * np.cos(mode * parameters)
    expected_sine = -(np.pi / mode) * np.sin(mode * parameters)

    assert np.max(np.abs(cosine - expected_cosine)) < 8.0e-14
    assert np.max(np.abs(sine - expected_sine)) < 8.0e-14


@pytest.mark.parametrize("num_nodes", [16, 32, 64])
def test_kress_weights_include_the_special_nyquist_term(num_nodes: int) -> None:
    parameters = TWO_PI * np.arange(num_nodes, dtype=np.float64) / num_nodes
    mode = num_nodes // 2
    approximation = 0.5 * _circulant_weights(num_nodes) @ np.cos(mode * parameters)
    expected = -(np.pi / mode) * np.cos(mode * parameters)

    assert np.max(np.abs(approximation - expected)) < 8.0e-14


def test_poisson_circle_control_reaches_roundoff_spectrally() -> None:
    radius = 0.72
    curve = circle((0.12, -0.08), radius)
    errors = []
    for num_nodes in (32, 64, 128, 256):
        result = logarithmic_product_rule_action(curve, num_nodes)
        parameters = curve.discretize(num_nodes, require_even=True).parameters
        exact = exact_circle_poisson_action(parameters, radius=radius)
        errors.append(float(np.max(np.abs(result.values - exact))))

    assert errors[1] < 0.01 * errors[0]
    assert errors[2] < 1.0e-4 * errors[1]
    assert errors[3] < 2.0e-13


def test_gauss_reference_is_independent_and_matches_exact_circle() -> None:
    radius = 0.72
    curve = circle((0.12, -0.08), radius)
    targets = TWO_PI * np.arange(16, dtype=np.float64) / 16
    panel_edges = np.linspace(0.0, TWO_PI, 129)

    reference = composite_gauss_reference(
        curve,
        targets,
        panel_edges,
        order=24,
    ).values
    exact = exact_circle_poisson_action(targets, radius=radius)

    assert np.max(np.abs(reference - exact)) < 8.0e-13


def test_gauss_reference_rejects_nonzero_parameter_origin() -> None:
    cosine = np.zeros((2, 2), dtype=np.float64)
    sine = np.zeros_like(cosine)
    cosine[1, 0] = 0.72
    sine[1, 1] = 0.72
    origin = 0.25
    curve = FourierBoundary(
        cosine_coefficients=cosine,
        sine_coefficients=sine,
        parameter_origin=origin,
    ).to_parameterization()
    targets = origin + TWO_PI * np.arange(8, dtype=np.float64) / 8
    panel_edges = np.linspace(origin, origin + TWO_PI, 65)

    with pytest.raises(ValueError, match="parameter_origin"):
        composite_gauss_reference(curve, targets, panel_edges, order=24)


def test_periodic_spline_proxy_enters_expected_algebraic_regime() -> None:
    exact_curve = ellipse((0.1, -0.1), 0.9, 0.45, rotation=0.3)
    sample_count = 32
    parameters = TWO_PI * np.arange(sample_count, dtype=np.float64) / sample_count
    representation = PeriodicSplineBoundary.interpolate(
        parameters,
        exact_curve.evaluate(parameters).points,
    )
    curve = representation.to_parameterization()
    targets = TWO_PI * np.arange(16, dtype=np.float64) / 16
    reference = composite_gauss_reference(
        curve,
        targets,
        representation.knots,
        order=32,
    ).values
    scale = max(float(np.max(np.abs(reference))), 1.0)

    errors = []
    for num_nodes in (128, 256, 512, 1024):
        target_indices = np.arange(16, dtype=np.int64) * (num_nodes // 16)
        approximation = logarithmic_product_rule_action(
            curve,
            num_nodes,
            target_indices=target_indices,
        ).values
        errors.append(float(np.max(np.abs(approximation - reference))) / scale)

    ratios = [upper / lower for lower, upper in zip(errors, errors[1:])]
    assert errors[-1] < 3.0e-12
    assert all(ratio < 0.08 for ratio in ratios)


def test_proxy_rejects_non_kress_node_counts() -> None:
    curve = circle((0.0, 0.0), 1.0)
    with pytest.raises(ValueError, match="even integer"):
        kress_log_weights(15)
    with pytest.raises(ValueError, match="even integer"):
        logarithmic_product_rule_action(curve, 15)


def test_reconstructs_compact_fourier_bundle_with_native_hash(tmp_path: Path) -> None:
    cosine = np.array(
        [
            [0.12, -0.08],
            [0.72, 0.0],
            [0.04, -0.02],
        ],
        dtype=np.float64,
    )
    sine = np.array(
        [
            [0.0, 0.0],
            [0.0, 0.51],
            [0.01, 0.03],
        ],
        dtype=np.float64,
    )
    representation = FourierBoundary(
        cosine_coefficients=cosine,
        sine_coefficients=sine,
        component_id="synthetic_component",
    )
    parameters = TWO_PI * np.arange(32, dtype=np.float64) / 32
    points = representation.evaluate(parameters, wrap=False).points
    curve_directory = tmp_path / "curves"
    curve_directory.mkdir()
    run_id = "synthetic_fourier_b"
    bundle_path = curve_directory / f"{run_id}.npz"
    np.savez_compressed(
        bundle_path,
        parameters=parameters,
        points=points,
        cosine_coefficients=cosine,
        sine_coefficients=sine,
    )
    expected_hash = hashlib.sha256(bundle_path.read_bytes()).hexdigest()

    frozen = _reconstruct_artifact_curve(
        curve_directory,
        {
            "run_id": run_id,
            "method": "B",
            "metrics": {"component_id": "synthetic_component"},
        },
        fourier_reference_panels=64,
    )

    assert frozen.source_bundle_sha256 == expected_hash
    assert frozen.reconstruction_maximum_error < 1.0e-14
    assert set(frozen.native_arrays) == {
        "cosine_coefficients",
        "sine_coefficients",
    }
    np.testing.assert_array_equal(frozen.native_arrays["cosine_coefficients"], cosine)
    np.testing.assert_array_equal(frozen.native_arrays["sine_coefficients"], sine)
    np.testing.assert_allclose(
        frozen.curve.evaluate(parameters, wrap=False).points,
        points,
        rtol=0.0,
        atol=2.0e-15,
    )
    assert frozen.gauss_panel_edges.shape == (65,)


def test_benchmark_refuses_nonempty_output_before_loading_sources(
    tmp_path: Path,
) -> None:
    output = tmp_path / "occupied-output"
    output.mkdir()
    (output / "sentinel.txt").write_text("do not overwrite\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="non-empty directory"):
        run_benchmark(tmp_path / "missing-study", output, timing_repeats=1)

    assert (output / "sentinel.txt").read_text(encoding="utf-8") == "do not overwrite\n"


def test_checked_benchmark_replays_from_compact_bundles(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    artifact_root = (
        repository_root
        / "results"
        / "sdf_boundary_parameterization"
        / "study-20260902"
    )
    checked_result = (
        repository_root
        / "results"
        / "sdf_boundary_parameterization"
        / "kress-scalar-proxy-20260902"
    )

    payload = run_benchmark(
        artifact_root,
        tmp_path / "replay",
        curve_root=checked_result / "frozen_curves",
        timing_repeats=1,
    )

    assert payload["acceptance"]["passed"]
    assert payload["measurement_scope"] == "manufactured_scalar_quadrature_proxy"
    assert payload["contains_bie_assembly"] is False
    assert payload["contains_linear_solve"] is False
    assert payload["contains_solver_error_metrics"] is False
    assert len(payload["frozen_curves"]) == 12
    assert len(payload["frozen_curve_inputs"]) == 12
    assert (tmp_path / "replay" / "manifest.json").is_file()
    replay_manifest = json.loads(
        (tmp_path / "replay" / "manifest.json").read_text(encoding="utf-8")
    )
    assert replay_manifest["measurement_scope"] == payload["measurement_scope"]
    assert replay_manifest["contains_solver_error_metrics"] is False
    assert (tmp_path / "replay" / "metrics.csv").read_text(
        encoding="utf-8"
    ).count("\n") == 92


def test_scratchpad_probe_remains_solver_isolated() -> None:
    source_path = (
        Path(__file__).resolve().parents[2]
        / "scratchpad"
        / "sdf_boundary_kress_proxy.py"
    )
    source = source_path.read_text(encoding="utf-8")
    forbidden_imports = (
        "from nystrom_ref",
        "import nystrom_ref",
        "from gpr_bem_",
        "import gpr_bem_",
        "from solver_select",
        "import solver_select",
    )
    assert all(token not in source for token in forbidden_imports)


def test_active_solver_sources_do_not_import_scratchpad_probe() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    active_sources = [repository_root / "solvers" / "solver_select.py"]
    active_sources.extend(sorted(repository_root.glob("run_ibim_*.py")))
    for package_name in (
        "gpr_bem_ref",
        "gpr_bem_mod",
        "gpr_bem_kdiff",
        "gpr_bem_ndiff",
        "gpr_bem_qbx",
    ):
        active_sources.extend(
            sorted((repository_root / "solvers" / package_name).rglob("*.py"))
        )

    assert active_sources
    offenders = [
        str(path.relative_to(repository_root))
        for path in active_sources
        if "sdf_boundary_kress_proxy" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
