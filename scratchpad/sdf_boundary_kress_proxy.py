#!/usr/bin/env python3
"""Isolated logarithmic Kress proxy for frozen SDF boundary fits.

This is a validation probe, not a BIE assembler and not a solver backend.  It
applies the scalar logarithmic product rule

    integral log(|gamma(t) - gamma(s)|) rho(s) |gamma'(s)| ds

to coefficient-owning Method A/B/C artifacts.  Marching squares, projection,
fitting, and coefficient optimization are never rerun while the quadrature
node count changes.

The manufactured density is chosen so that ``rho(s) |gamma'(s)|`` is a known
Poisson kernel.  Its canonical circular-log convolution is analytic.  For a
general frozen curve, only the smooth geometric remainder is integrated for
the reference, using composite Gauss-Legendre quadrature rather than another
instance of the Kress rule under test.

Nothing in this file is imported by ``solver_select`` or an active forward,
adjoint, or inverse path.  In particular, the probe deliberately does not
import private numerical code from ``nystrom_ref`` or any ``gpr_bem_*``
package.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from numpy.polynomial.legendre import leggauss


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"
if str(SOLVERS_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVERS_ROOT))

from ordered_boundary import PeriodicParameterization2D, circle  # noqa: E402
from sdf_to_ordered_boundary.representations import (  # noqa: E402
    FourierBoundary,
    PeriodicSplineBoundary,
)


Array = np.ndarray
TWO_PI = 2.0 * np.pi
DEFAULT_NODE_COUNTS = (32, 64, 128, 256, 512, 1024, 2048)
DEFAULT_SHAPE_ORDER = ("circle", "rotated_ellipse", "radial_fourier_star")


@dataclass(frozen=True)
class ProductRuleTiming:
    """Wall-clock breakdown for one complete proxy action."""

    discretization_seconds: float
    weight_build_seconds: float
    action_seconds: float
    total_seconds: float


@dataclass(frozen=True)
class ProductRuleResult:
    """Values and timings from one application of the scalar product rule."""

    values: Array
    canonical_values: Array
    remainder_values: Array
    target_indices: Array
    timing: ProductRuleTiming


@dataclass(frozen=True)
class CompositeReferenceResult:
    """Independent total and smooth-remainder reference values."""

    values: Array
    canonical_values: Array
    remainder_values: Array


@dataclass(frozen=True)
class FrozenArtifactCurve:
    """A reconstructed continuous curve plus its recorded study metadata."""

    row: dict[str, Any]
    curve: PeriodicParameterization2D
    gauss_panel_edges: Array
    reconstruction_maximum_error: float
    native_arrays: dict[str, Array]
    source_bundle_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPOSITORY_ROOT))
    except ValueError:
        return str(resolved)


def _even_node_count(value: int, *, label: str = "num_nodes") -> int:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be an integer, not bool.")
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be an integer.") from exc
    if count != value:
        raise TypeError(f"{label} must be an integer.")
    if count < 4 or count % 2:
        raise ValueError(f"{label} must be an even integer at least 4.")
    return count


def kress_log_weights(num_nodes: int) -> Array:
    """Return weights for the full canonical ``log(4 sin^2/2)`` factor.

    The returned vector is indexed by ``(target_index-source_index) % N``.
    An FFT evaluates the standard finite cosine sum; this is algebraically the
    same Kress/Kussmaul-Martensen formula used by the reference Nyström code,
    but this independent probe shares no implementation with that solver.
    """

    count = _even_node_count(num_nodes)
    half = count // 2
    modes = np.arange(1, half, dtype=np.int64)
    reciprocal_spectrum = np.zeros(count, dtype=np.complex128)
    reciprocal_spectrum[modes] = 0.5 / modes
    reciprocal_spectrum[count - modes] = 0.5 / modes
    cosine_sum = np.fft.fft(reciprocal_spectrum).real
    nyquist_cosine = np.where(np.arange(count) % 2 == 0, 1.0, -1.0)
    weights = (
        -(TWO_PI / half) * cosine_sum
        - (np.pi / half**2) * nyquist_cosine
    )
    weights.setflags(write=False)
    return weights


def poisson_weighted_density(
    parameters: Array,
    *,
    concentration: float = 0.75,
    phase: float = 0.37,
) -> Array:
    """Return the non-bandlimited manufactured quantity ``rho * speed``."""

    a = float(concentration)
    beta = float(phase)
    if not np.isfinite(a) or not 0.0 < a < 1.0:
        raise ValueError("concentration must lie strictly between zero and one.")
    if not np.isfinite(beta):
        raise ValueError("phase must be finite.")
    values = np.asarray(parameters, dtype=np.float64)
    return 1.0 / (1.0 - 2.0 * a * np.cos(values - beta) + a**2)


def poisson_canonical_action(
    targets: Array,
    *,
    concentration: float = 0.75,
    phase: float = 0.37,
) -> Array:
    """Exact circular-log convolution of :func:`poisson_weighted_density`."""

    a = float(concentration)
    beta = float(phase)
    values = np.asarray(targets, dtype=np.float64)
    denominator = 1.0 - 2.0 * a * np.cos(values - beta) + a**2
    return np.pi * np.log(denominator) / (1.0 - a**2)


def exact_circle_poisson_action(
    targets: Array,
    *,
    radius: float,
    concentration: float = 0.75,
    phase: float = 0.37,
) -> Array:
    """Exact manufactured logarithmic action on a circle of ``radius``.

    The physical density is ``rho=f/J``.  Therefore the parameter-space source
    factor is the Poisson function ``f`` and the radius contributes only the
    constant ``log(radius)`` part of the logarithmic kernel.
    """

    radius_value = float(radius)
    if not np.isfinite(radius_value) or radius_value <= 0.0:
        raise ValueError("radius must be finite and positive.")
    a = float(concentration)
    return poisson_canonical_action(
        targets,
        concentration=a,
        phase=phase,
    ) + TWO_PI * np.log(radius_value) / (1.0 - a**2)


def _target_index_array(num_nodes: int, target_indices: Array | None) -> Array:
    if target_indices is None:
        result = np.arange(num_nodes, dtype=np.int64)
    else:
        raw = np.asarray(target_indices)
        if raw.ndim != 1 or raw.size == 0:
            raise ValueError("target_indices must be a non-empty one-dimensional array.")
        if raw.dtype.kind not in "iu":
            raise TypeError("target_indices must contain integers.")
        result = np.asarray(raw, dtype=np.int64)
        if np.any(result < 0) or np.any(result >= num_nodes):
            raise ValueError("target_indices must lie in [0, num_nodes).")
        if np.unique(result).size != result.size:
            raise ValueError("target_indices must not contain duplicates.")
    result.setflags(write=False)
    return result


def logarithmic_product_rule_action(
    curve: PeriodicParameterization2D,
    num_nodes: int,
    *,
    weighted_density: Callable[[Array], Array] = poisson_weighted_density,
    target_indices: Array | None = None,
) -> ProductRuleResult:
    """Apply the scalar Kress product rule on one frozen continuous curve.

    ``weighted_density`` supplies ``rho(t) * |gamma'(t)|``.  The default is the
    manufactured Poisson factor, so no numerical division by speed is needed.
    The factor one half multiplying the Kress weights is required because the
    weights integrate ``log(4 sin^2((t-s)/2))``, while ``log|gamma(t)-gamma(s)|``
    contains one half of that canonical logarithm.
    """

    if not isinstance(curve, PeriodicParameterization2D):
        raise TypeError("curve must be a PeriodicParameterization2D.")
    if not np.isclose(curve.period, TWO_PI, rtol=0.0, atol=1.0e-13):
        raise ValueError("The Kress proxy requires a 2*pi-periodic curve.")
    if not np.isclose(curve.parameter_origin, 0.0, rtol=0.0, atol=1.0e-13):
        raise ValueError("The Kress proxy currently requires parameter_origin == 0.")

    count = _even_node_count(num_nodes)
    selected_targets = _target_index_array(count, target_indices)
    total_started = time.perf_counter()

    discretization_started = time.perf_counter()
    nodes = curve.discretize(count, require_even=True)
    discretization_seconds = time.perf_counter() - discretization_started
    if np.any(nodes.speeds <= 0.0) or not np.all(np.isfinite(nodes.speeds)):
        raise ValueError("The frozen curve has nonfinite or nonpositive speed.")

    weights_started = time.perf_counter()
    one_dimensional_weights = kress_log_weights(count)
    weight_build_seconds = time.perf_counter() - weights_started

    action_started = time.perf_counter()
    source_indices = np.arange(count, dtype=np.int64)
    offset_indices = (
        selected_targets[:, None] - source_indices[None, :]
    ) % count
    target_points = nodes.points[selected_targets]
    delta_x = target_points[:, None, 0] - nodes.points[None, :, 0]
    delta_y = target_points[:, None, 1] - nodes.points[None, :, 1]
    distances = np.hypot(delta_x, delta_y)
    del delta_x, delta_y

    chord_denominator = 2.0 * np.abs(
        np.sin(np.pi * np.arange(count, dtype=np.float64) / count)
    )
    denominators = chord_denominator[offset_indices]
    local_rows = np.arange(selected_targets.size, dtype=np.int64)
    distances[local_rows, selected_targets] = 1.0
    denominators[local_rows, selected_targets] = 1.0
    if np.any(distances <= 0.0) or np.any(denominators <= 0.0):
        raise ValueError("The curve contains a duplicate nonlocal point.")
    distances /= denominators
    np.log(distances, out=distances)
    distances[local_rows, selected_targets] = np.log(
        nodes.speeds[selected_targets]
    )

    source_factor = np.asarray(weighted_density(nodes.parameters), dtype=np.float64)
    if source_factor.shape != (count,) or not np.all(np.isfinite(source_factor)):
        raise ValueError("weighted_density must return one finite value per source node.")
    pairwise_weights = one_dimensional_weights[offset_indices]
    canonical_values = 0.5 * (pairwise_weights @ source_factor)
    remainder_values = (TWO_PI / count) * (distances @ source_factor)
    values = canonical_values + remainder_values
    action_seconds = time.perf_counter() - action_started
    total_seconds = time.perf_counter() - total_started
    values = np.asarray(values, dtype=np.float64)
    canonical_values = np.asarray(canonical_values, dtype=np.float64)
    remainder_values = np.asarray(remainder_values, dtype=np.float64)
    values.setflags(write=False)
    canonical_values.setflags(write=False)
    remainder_values.setflags(write=False)

    return ProductRuleResult(
        values=values,
        canonical_values=canonical_values,
        remainder_values=remainder_values,
        target_indices=selected_targets,
        timing=ProductRuleTiming(
            discretization_seconds=discretization_seconds,
            weight_build_seconds=weight_build_seconds,
            action_seconds=action_seconds,
            total_seconds=total_seconds,
        ),
    )


def composite_gauss_reference(
    curve: PeriodicParameterization2D,
    targets: Array,
    panel_edges: Array,
    *,
    order: int,
) -> CompositeReferenceResult:
    """Poisson-density reference using exact convolution plus smooth Gauss rule.

    This routine never calls :func:`kress_log_weights`.  Spline callers pass
    every native knot as a panel edge; Fourier callers use a separately chosen
    uniform panelization.  Gauss nodes lie strictly inside panels and hence do
    not evaluate the removable diagonal directly.
    """

    if not isinstance(curve, PeriodicParameterization2D):
        raise TypeError("curve must be a PeriodicParameterization2D.")
    if not np.isclose(curve.period, TWO_PI, rtol=0.0, atol=1.0e-13):
        raise ValueError("The Gauss reference requires a 2*pi-periodic curve.")
    if not np.isclose(curve.parameter_origin, 0.0, rtol=0.0, atol=1.0e-13):
        raise ValueError("The Gauss reference currently requires parameter_origin == 0.")
    target_values = np.asarray(targets, dtype=np.float64)
    edges = np.asarray(panel_edges, dtype=np.float64)
    if isinstance(order, bool):
        raise TypeError("Gauss-Legendre order must be an integer, not bool.")
    quadrature_order = int(order)
    if quadrature_order != order:
        raise TypeError("Gauss-Legendre order must be an integer.")
    if target_values.ndim != 1 or target_values.size == 0:
        raise ValueError("targets must be a non-empty one-dimensional array.")
    if edges.ndim != 1 or edges.size < 2 or np.any(np.diff(edges) <= 0.0):
        raise ValueError("panel_edges must be a strictly increasing array.")
    if quadrature_order < 4:
        raise ValueError("Gauss-Legendre order must be at least 4.")
    tolerance = 64.0 * np.finfo(float).eps * TWO_PI
    if abs(edges[0] - curve.parameter_origin) > tolerance:
        raise ValueError("panel_edges must start at the curve parameter origin.")
    if abs(edges[-1] - (curve.parameter_origin + curve.period)) > tolerance:
        raise ValueError("panel_edges must end at one complete period.")

    reference_nodes, reference_weights = leggauss(quadrature_order)
    left = edges[:-1]
    right = edges[1:]
    source_parameters = (
        0.5 * (left + right)[:, None]
        + 0.5 * (right - left)[:, None] * reference_nodes[None, :]
    ).reshape(-1)
    integration_weights = (
        0.5 * (right - left)[:, None] * reference_weights[None, :]
    ).reshape(-1)

    sources = curve.evaluate(source_parameters)
    target_geometry = curve.evaluate(target_values)
    delta = target_geometry.points[:, None, :] - sources.points[None, :, :]
    distances = np.linalg.norm(delta, axis=2)
    denominators = 2.0 * np.abs(
        np.sin(0.5 * (target_values[:, None] - source_parameters[None, :]))
    )
    if np.any(distances <= 0.0) or np.any(denominators <= 0.0):
        raise ValueError("Gauss reference encountered an unresolved coincident point.")
    smooth_remainder = np.log(distances / denominators)
    source_factor = np.asarray(poisson_weighted_density(source_parameters), dtype=np.float64)
    if source_factor.shape != source_parameters.shape or not np.all(
        np.isfinite(source_factor)
    ):
        raise ValueError("The manufactured reference density is invalid.")
    canonical_values = poisson_canonical_action(target_values)
    remainder_values = smooth_remainder @ (integration_weights * source_factor)
    values = canonical_values + remainder_values
    for array in (values, canonical_values, remainder_values):
        array.setflags(write=False)
    return CompositeReferenceResult(
        values=np.asarray(values, dtype=np.float64),
        canonical_values=np.asarray(canonical_values, dtype=np.float64),
        remainder_values=np.asarray(remainder_values, dtype=np.float64),
    )


def _strict_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        result = float(value)
        return result if np.isfinite(result) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return [_strict_json_value(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _strict_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_json_value(item) for item in value]
    raise TypeError(f"Unsupported JSON value {type(value).__name__}.")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(
            _strict_json_value(payload),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    records = list(rows)
    for row_index, record in enumerate(records):
        for key, value in record.items():
            if isinstance(value, (float, np.floating)) and not np.isfinite(value):
                raise ValueError(
                    f"CSV row {row_index} field {key!r} is nonfinite: {value!r}."
                )
    columns = sorted({key for row in records for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def _load_study_rows(artifact_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = artifact_root / "manifest.json"
    metrics_path = artifact_root / "metrics.json"
    if not manifest_path.is_file() or not metrics_path.is_file():
        raise FileNotFoundError(
            "artifact_root must contain manifest.json and metrics.json."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = json.loads(metrics_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Only SDF comparison artifact schema_version 1 is supported.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("metrics.json must contain a non-empty list of rows.")
    return manifest, rows


def _select_representative_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select a declared, nonvisual comparison subset from the full study.

    For each shape this retains Method A, the highest-bandwidth accepted C and
    its same-K Method-B initializer, and the highest tested Method B.  Every row
    comes from the finest available extraction grid and largest projected-loop
    sample count.  Duplicate B rows are removed while preserving this order.
    """

    selected: list[dict[str, Any]] = []
    available_shapes = {str(row.get("shape")) for row in rows}
    ordered_shapes = [shape for shape in DEFAULT_SHAPE_ORDER if shape in available_shapes]
    ordered_shapes += sorted(available_shapes - set(ordered_shapes))
    for shape in ordered_shapes:
        shape_rows = [row for row in rows if row.get("shape") == shape]
        grid = max(tuple(row["grid_shape"]) for row in shape_rows)
        grid_rows = [row for row in shape_rows if tuple(row["grid_shape"]) == grid]
        projected_count = max(int(row["projected_sample_count"]) for row in grid_rows)
        candidates = [
            row
            for row in grid_rows
            if int(row["projected_sample_count"]) == projected_count
        ]

        a_rows = [row for row in candidates if row.get("method") == "A"]
        if len(a_rows) != 1:
            raise ValueError(f"Expected exactly one Method-A row for {shape!r}.")
        if a_rows[0].get("status") != "success":
            raise ValueError(f"The selected Method-A row for {shape!r} is not successful.")
        selected.append(a_rows[0])

        accepted_c = [
            row
            for row in candidates
            if row.get("method") == "C" and row.get("status") == "success"
        ]
        if not accepted_c:
            raise ValueError(f"No accepted Method-C curve is available for {shape!r}.")
        c_row = max(accepted_c, key=lambda row: int(row["bandwidth"]))
        paired_b = [
            row
            for row in candidates
            if row.get("method") == "B" and row.get("bandwidth") == c_row["bandwidth"]
        ]
        if len(paired_b) != 1:
            raise ValueError(f"Missing the paired Method-B initializer for {shape!r}.")
        if paired_b[0].get("status") != "success":
            raise ValueError(f"The paired Method-B row for {shape!r} is not successful.")
        if paired_b[0].get("frontend_id") != c_row.get("frontend_id"):
            raise ValueError(f"The paired B/C rows for {shape!r} do not share a front end.")
        selected.extend((paired_b[0], c_row))

        all_b = [
            row
            for row in candidates
            if row.get("method") == "B" and row.get("status") == "success"
        ]
        if not all_b:
            raise ValueError(f"No successful Method-B row is available for {shape!r}.")
        highest_b = max(all_b, key=lambda row: int(row["bandwidth"]))
        if highest_b["run_id"] != paired_b[0]["run_id"]:
            selected.append(highest_b)
    return selected


def _reconstruct_artifact_curve(
    curve_directory: Path,
    row: dict[str, Any],
    *,
    fourier_reference_panels: int,
) -> FrozenArtifactCurve:
    run_id = str(row["run_id"])
    if Path(run_id).name != run_id:
        raise ValueError(f"Unsafe curve run_id {run_id!r}.")
    bundle_path = curve_directory / f"{run_id}.npz"
    if not bundle_path.is_file():
        raise FileNotFoundError(
            f"Missing native coefficient bundle {bundle_path}. Regenerate the full "
            "study or pass --curve-root with the checked compact bundles."
        )

    with np.load(bundle_path, allow_pickle=False) as bundle:
        parameters = np.array(bundle["parameters"], dtype=np.float64, copy=True)
        stored_points = np.array(bundle["points"], dtype=np.float64, copy=True)
        if parameters.ndim != 1 or parameters.size < 4:
            raise ValueError(f"{bundle_path} has an invalid parameter sample array.")
        if stored_points.shape != (parameters.size, 2):
            raise ValueError(f"{bundle_path} has an invalid point snapshot.")
        increments = np.diff(parameters)
        if np.any(increments <= 0.0) or not np.allclose(
            increments,
            increments[0],
            rtol=2.0e-13,
            atol=2.0e-14,
        ):
            raise ValueError(f"{bundle_path} parameters are not uniformly increasing.")
        origin = float(parameters[0])
        period = float(parameters.size * (parameters[1] - parameters[0]))
        if not np.isclose(origin, 0.0, rtol=0.0, atol=1.0e-13):
            raise ValueError(f"{bundle_path} must start at parameter zero.")
        if not np.isclose(period, TWO_PI, rtol=0.0, atol=2.0e-12):
            raise ValueError(f"{bundle_path} must cover a uniform 2*pi period.")
        component_id = str(row.get("metrics", {}).get("component_id", "component_000"))
        method = str(row["method"])
        if method == "A":
            native_arrays = {
                "spline_knots": np.array(
                    bundle["spline_knots"], dtype=np.float64, copy=True
                ),
                "spline_coefficients": np.array(
                    bundle["spline_coefficients"], dtype=np.float64, copy=True
                ),
            }
            representation = PeriodicSplineBoundary(
                knots=native_arrays["spline_knots"],
                coefficients=native_arrays["spline_coefficients"],
                component_id=component_id,
                name=f"{run_id}_reconstructed",
                period=period,
                parameter_origin=origin,
            )
            panel_edges = np.array(representation.knots, copy=True)
        elif method in {"B", "C"}:
            native_arrays = {
                "cosine_coefficients": np.array(
                    bundle["cosine_coefficients"], dtype=np.float64, copy=True
                ),
                "sine_coefficients": np.array(
                    bundle["sine_coefficients"], dtype=np.float64, copy=True
                ),
            }
            representation = FourierBoundary(
                cosine_coefficients=native_arrays["cosine_coefficients"],
                sine_coefficients=native_arrays["sine_coefficients"],
                component_id=component_id,
                name=f"{run_id}_reconstructed",
                period=period,
                parameter_origin=origin,
            )
            panel_edges = np.linspace(
                origin,
                origin + period,
                int(fourier_reference_panels) + 1,
                dtype=np.float64,
            )
        else:
            raise ValueError(f"Unsupported method label {method!r}.")

    curve = representation.to_parameterization()
    reconstructed = curve.evaluate(parameters, wrap=False).points
    reconstruction_error = float(
        np.max(np.linalg.norm(reconstructed - stored_points, axis=1))
    )
    if reconstruction_error > 5.0e-13:
        raise ValueError(
            f"Native coefficient reconstruction changed {run_id} by {reconstruction_error:.3e}."
        )
    for array in native_arrays.values():
        array.setflags(write=False)
    panel_edges.setflags(write=False)
    return FrozenArtifactCurve(
        row=dict(row),
        curve=curve,
        gauss_panel_edges=panel_edges,
        reconstruction_maximum_error=reconstruction_error,
        native_arrays=native_arrays,
        source_bundle_sha256=_sha256(bundle_path),
    )


def _write_compact_curve_bundle(
    frozen: FrozenArtifactCurve,
    output_directory: Path,
    *,
    snapshot_count: int = 32,
) -> dict[str, Any]:
    """Persist the native coefficients plus a small reconstruction snapshot."""

    count = _even_node_count(snapshot_count, label="snapshot_count")
    run_id = str(frozen.row["run_id"])
    output_directory.mkdir(parents=True, exist_ok=True)
    bundle_path = output_directory / f"{run_id}.npz"
    parameters = TWO_PI * np.arange(count, dtype=np.float64) / count
    points = frozen.curve.evaluate(parameters, wrap=False).points
    np.savez_compressed(
        bundle_path,
        parameters=parameters,
        points=points,
        **frozen.native_arrays,
    )
    return {
        "run_id": run_id,
        "path": _display_path(bundle_path),
        "sha256": _sha256(bundle_path),
        "source_bundle_sha256": frozen.source_bundle_sha256,
        "snapshot_count": count,
    }


def _nested_target_indices(num_nodes: int, target_count: int) -> Array:
    count = _even_node_count(num_nodes)
    targets = _even_node_count(target_count, label="target_count")
    if count % targets:
        raise ValueError("Every node count must be divisible by target_count.")
    return np.arange(targets, dtype=np.int64) * (count // targets)


def _median_timing(results: Sequence[ProductRuleResult]) -> dict[str, float]:
    fields = (
        "discretization_seconds",
        "weight_build_seconds",
        "action_seconds",
        "total_seconds",
    )
    payload = {
        field: float(statistics.median(getattr(result.timing, field) for result in results))
        for field in fields
    }
    totals = [result.timing.total_seconds for result in results]
    payload["minimum_total_seconds"] = float(min(totals))
    payload["maximum_total_seconds"] = float(max(totals))
    return payload


def _timed_full_action(
    curve: PeriodicParameterization2D,
    num_nodes: int,
    *,
    repeats: int,
) -> tuple[ProductRuleResult, dict[str, float]]:
    logarithmic_product_rule_action(curve, num_nodes)
    gc.collect()
    runs = [logarithmic_product_rule_action(curve, num_nodes) for _ in range(repeats)]
    first = runs[0]
    for result in runs[1:]:
        for name in ("values", "canonical_values", "remainder_values"):
            if not np.allclose(
                getattr(result, name),
                getattr(first, name),
                rtol=0.0,
                atol=2.0e-13,
            ):
                raise RuntimeError("Repeated proxy actions produced inconsistent values.")
    return first, _median_timing(runs)


def _error_record(approximation: Array, reference: Array) -> dict[str, float]:
    difference = np.asarray(approximation) - np.asarray(reference)
    maximum = float(np.max(np.abs(difference)))
    rms = float(np.sqrt(np.mean(np.abs(difference) ** 2)))
    scale = max(float(np.max(np.abs(reference))), 1.0)
    return {
        "maximum_absolute_error": maximum,
        "rms_error": rms,
        "mixed_relative_error": maximum / scale,
        "reference_scale": scale,
    }


def _format_scientific(value: float, *, floor: float | None = None) -> str:
    number = float(value)
    if floor is not None and number < floor:
        return f"<{floor:.0e}"
    return f"{number:.2e}"


def _prefixed_error_record(prefix: str, record: dict[str, float]) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in record.items()}


def _curve_label(row: dict[str, Any]) -> str:
    method = str(row["method"])
    if method == "A":
        return "A spline"
    return f"{method} K={int(row['bandwidth'])}"


def _markdown_summary(payload: dict[str, Any]) -> str:
    config = payload["config"]
    node_counts = [int(value) for value in config["node_counts"]]
    circle_rows = payload["analytic_circle_control"]
    curve_rows = payload["frozen_curves"]
    gate = payload["acceptance"]
    source = payload["source_study"]

    lines = [
        "# Frozen SDF boundary: isolated Kress proxy",
        "",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "## Verdict",
        "",
        (
            "**PASS.** The independent manufactured-circle identity reaches "
            "floating-point accuracy, and every selected frozen A/B/C curve "
            "meets its configured convergence gate."
            if gate["passed"]
            else "**REVISE.** At least one configured proxy gate failed."
        ),
        "",
        "This validates a scalar logarithmic product-rule seam only. It does not "
        "validate Müller blocks, diagonal kernel formulas, a linear solve, or a "
        "production BIE pipeline.",
        "",
        "## Configuration",
        "",
        f"- Source study: `{source['artifact_root']}` ({source['row_count']} rows)",
        f"- Curve inputs: `{source['curve_root']}` (SHA-256 recorded per bundle)",
        "- Self-contained replay inputs: `frozen_curves/` beside this summary",
        f"- Frozen source grid / projected samples: finest available per shape",
        f"- Node ladder: `{node_counts}`",
        (
            f"- Fitted-curve errors: `{config['target_count']}` fixed nested targets; "
            "timings use all N targets"
        ),
        (
            "- Manufactured weighted density: Poisson kernel with "
            f"`a={config['poisson_concentration']}`, `beta={config['poisson_phase']}`"
        ),
        (
            "- Independent remainder reference: composite Gauss-Legendre orders "
            f"`{config['reference_orders']}`; agreement tolerance "
            f"`{config['reference_agreement_tolerance']:.1e}`"
        ),
        (
            f"- Timing: warm-up plus median of `{config['timing_repeats']}` dense "
            "full-grid matrix-formation/actions"
        ),
        "",
        "## Analytic circle control",
        "",
        "The reference is closed form; no numerical reference quadrature is used.",
        "",
        "| N | max abs error | mixed relative error | dense full action median |",
        "|---:|---:|---:|---:|",
    ]
    for row in circle_rows:
        lines.append(
            "| {n} | {absolute} | {relative} | {runtime:.3f} ms |".format(
                n=row["num_nodes"],
                absolute=_format_scientific(row["full_error"]["maximum_absolute_error"]),
                relative=_format_scientific(
                    row["full_error"]["mixed_relative_error"], floor=1.0e-14
                ),
                runtime=1.0e3 * row["timing"]["total_seconds"],
            )
        )

    display_counts = [64, 128, 256, 1024, 2048]
    error_header = " → ".join(str(value) for value in display_counts)
    runtime_counts = [256, 1024, 2048]
    runtime_header = " / ".join(str(value) for value in runtime_counts)
    lines.extend(
        [
            "",
            "## Skimmed fitted-curve table",
            "",
            (
                "The geometry column is the normalized maximum SDF residual from "
                "the source study. The q-error column isolates the geometry-sensitive "
                "smooth Kress remainder; `ref-limited` means the error is no larger "
                "than the float64/reference-disagreement floor. Full error also includes "
                "the common manufactured Poisson convolution."
            ),
            "",
            (
                "| Shape | Frozen curve | status | geometry error | q mixed-relative "
                f"error, N={error_header} | full error N=256 | conversion | dense action "
                f"ms, N={runtime_header} |"
            ),
            "|---|---|---|---:|---|---:|---:|---:|",
        ]
    )
    for curve_record in curve_rows:
        by_n = {int(item["num_nodes"]): item for item in curve_record["node_results"]}
        reference_floor = max(
            5.0e-14,
            2.0 * float(curve_record["remainder_reference_mixed_floor"]),
        )
        errors = " → ".join(
            (
                "ref-limited"
                if by_n[count]["remainder_error"]["mixed_relative_error"]
                <= reference_floor
                else _format_scientific(
                    by_n[count]["remainder_error"]["mixed_relative_error"]
                )
            )
            for count in display_counts
        )
        runtimes = " / ".join(
            f"{1.0e3 * by_n[count]['timing']['total_seconds']:.2f}"
            for count in runtime_counts
        )
        lines.append(
            "| {shape} | {curve} | {status} | {geometry} | {errors} | {full} | "
            "{conversion:.3f} s | {runtimes} |".format(
                shape=curve_record["shape"],
                curve=curve_record["curve_label"],
                status=curve_record["status"],
                geometry=_format_scientific(curve_record["normalized_maximum_sdf_residual"]),
                errors=errors,
                full=_format_scientific(
                    by_n[256]["full_error"]["mixed_relative_error"],
                    floor=1.0e-14,
                ),
                conversion=curve_record["converter_runtime_seconds"],
                runtimes=runtimes,
            )
        )

    lines.extend(
        [
            "",
            "`conversion` is copied from the earlier study and includes the shared front "
            "end in every row; do not sum it across methods or read it as incremental fit "
            "cost. `dense action` includes curve discretization, weight construction, "
            "dense N×N smooth-remainder matrix formation, and one matrix-vector action. "
            "It is neither an FFT-only weight application nor a four-block BIE assembly/solve.",
            "",
            "Selection is fixed rather than visual: at the finest grid and largest "
            "projected sample count, retain A, the highest-bandwidth accepted C with "
            "its same-bandwidth B initializer, and the highest tested B. High-bandwidth "
            "C fallbacks are omitted because their serialized geometry is bit-identical "
            "to B, but their overall status remains reported below.",
            "",
            "## Gates and interpretation",
            "",
        ]
    )
    for check in gate["checks"]:
        marker = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- **{marker}:** {check['description']}")
    lines.extend(
        [
            "",
            (
                f"Method C in the complete source sweep: {source['method_c_successes']} "
                f"accepted and {source['method_c_fallbacks']} guarded fallbacks. A fallback "
                "returns B's geometry and is not an independent curve."
            ),
            "",
            "The proxy makes the separation especially visible: a Fourier curve can "
            "become reference/roundoff limited while still having appreciable SDF geometry "
            "error. Quadrature convergence does not repair an under-resolved boundary.",
            "",
            "Current preference remains **Method B with adaptive bandwidth**. B and "
            "accepted C both show spectral smooth-remainder convergence here, with no "
            "demonstrated quadrature advantage for C. B avoids nonlinear cost and fallback "
            "behavior. A is the useful finite-smoothness control and shows post-knot "
            "algebraic convergence.",
            "",
        ]
    )
    return "\n".join(lines)


def run_benchmark(
    artifact_root: Path,
    output_directory: Path,
    *,
    curve_root: Path | None = None,
    node_counts: Sequence[int] = DEFAULT_NODE_COUNTS,
    target_count: int = 16,
    timing_repeats: int = 5,
    fourier_reference_panels: int = 256,
    reference_orders: tuple[int, int] = (24, 40),
    reference_agreement_tolerance: float = 1.0e-11,
) -> dict[str, Any]:
    """Run the analytic control and representative frozen-curve convergence study."""

    root = Path(artifact_root).resolve()
    output = Path(output_directory).resolve()
    curve_directory = (
        (root / "curves").resolve()
        if curve_root is None
        else Path(curve_root).resolve()
    )
    counts = tuple(_even_node_count(value) for value in node_counts)
    if counts != DEFAULT_NODE_COUNTS:
        raise ValueError(
            "This declared benchmark requires the fixed N ladder "
            f"{DEFAULT_NODE_COUNTS}; custom ladders are not supported."
        )
    targets_count = _even_node_count(target_count, label="target_count")
    if any(count % targets_count for count in counts):
        raise ValueError("Every node count must be divisible by target_count.")
    repeats = int(timing_repeats)
    if repeats < 1:
        raise ValueError("timing_repeats must be positive.")
    panel_count = int(fourier_reference_panels)
    if panel_count < targets_count or panel_count % targets_count:
        raise ValueError(
            "fourier_reference_panels must be at least and divisible by target_count."
        )
    low_order, high_order = (int(value) for value in reference_orders)
    if low_order < 4 or high_order <= low_order:
        raise ValueError("reference_orders must be increasing and at least four.")
    agreement_tolerance = float(reference_agreement_tolerance)
    if not np.isfinite(agreement_tolerance) or agreement_tolerance <= 0.0:
        raise ValueError("reference_agreement_tolerance must be finite and positive.")

    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to mix results in non-empty directory {output}.")
    output.mkdir(parents=True, exist_ok=True)

    manifest, study_rows = _load_study_rows(root)
    selected_rows = _select_representative_rows(study_rows)
    source_manifest_path = root / "manifest.json"
    source_metrics_path = root / "metrics.json"
    compact_curve_directory = output / "frozen_curves"

    circle_radius = 0.72
    analytic_curve = circle((0.12, -0.08), circle_radius)
    circle_records: list[dict[str, Any]] = []
    for count in counts:
        result, timing = _timed_full_action(analytic_curve, count, repeats=repeats)
        parameters = analytic_curve.discretize(count, require_even=True).parameters
        exact_canonical = poisson_canonical_action(parameters)
        exact_remainder = np.full(
            count,
            TWO_PI * np.log(circle_radius) / (1.0 - 0.75**2),
            dtype=np.float64,
        )
        exact = exact_canonical + exact_remainder
        circle_records.append(
            {
                "record_kind": "analytic_circle_control",
                "num_nodes": count,
                "full_error": _error_record(result.values, exact),
                "canonical_error": _error_record(
                    result.canonical_values, exact_canonical
                ),
                "remainder_error": _error_record(
                    result.remainder_values, exact_remainder
                ),
                "timing": timing,
            }
        )

    target_parameters = TWO_PI * np.arange(targets_count, dtype=np.float64) / targets_count
    frozen_records: list[dict[str, Any]] = []
    frozen_input_records: list[dict[str, Any]] = []
    flat_rows: list[dict[str, Any]] = []
    for row in selected_rows:
        frozen = _reconstruct_artifact_curve(
            curve_directory,
            row,
            fourier_reference_panels=panel_count,
        )
        compact_input = _write_compact_curve_bundle(
            frozen,
            compact_curve_directory,
        )
        frozen_input_records.append(compact_input)
        reference_started = time.perf_counter()
        low_reference = composite_gauss_reference(
            frozen.curve,
            target_parameters,
            frozen.gauss_panel_edges,
            order=low_order,
        )
        high_reference = composite_gauss_reference(
            frozen.curve,
            target_parameters,
            frozen.gauss_panel_edges,
            order=high_order,
        )
        reference_seconds = time.perf_counter() - reference_started
        full_reference_agreement = float(
            np.max(np.abs(high_reference.values - low_reference.values))
        )
        remainder_reference_agreement = float(
            np.max(
                np.abs(
                    high_reference.remainder_values - low_reference.remainder_values
                )
            )
        )
        reference_agreement = max(
            full_reference_agreement,
            remainder_reference_agreement,
        )
        if reference_agreement > agreement_tolerance:
            raise RuntimeError(
                f"Independent reference orders disagree for {row['run_id']} by "
                f"{reference_agreement:.3e}."
            )

        node_records: list[dict[str, Any]] = []
        for count in counts:
            full_result, timing = _timed_full_action(frozen.curve, count, repeats=repeats)
            target_indices = _nested_target_indices(count, targets_count)
            full_errors = _error_record(
                full_result.values[target_indices], high_reference.values
            )
            canonical_errors = _error_record(
                full_result.canonical_values[target_indices],
                high_reference.canonical_values,
            )
            remainder_errors = _error_record(
                full_result.remainder_values[target_indices],
                high_reference.remainder_values,
            )
            node_record = {
                "num_nodes": count,
                "full_error": full_errors,
                "canonical_error": canonical_errors,
                "remainder_error": remainder_errors,
                "timing": timing,
            }
            node_records.append(node_record)
            flat_rows.append(
                {
                    "record_kind": "frozen_curve",
                    "run_id": row["run_id"],
                    "shape": row["shape"],
                    "method": row["method"],
                    "bandwidth": row.get("bandwidth"),
                    "status": row["status"],
                    "grid_resolution": row["grid_resolution"],
                    "projected_sample_count": row["projected_sample_count"],
                    "normalized_maximum_sdf_residual": row["metrics"]["sdf_residual"][
                        "normalized_maximum"
                    ],
                    "converter_runtime_seconds": row["total_converter_runtime_seconds"],
                    "reference_seconds": reference_seconds,
                    "reference_order_agreement": reference_agreement,
                    "full_reference_order_agreement": full_reference_agreement,
                    "remainder_reference_order_agreement": remainder_reference_agreement,
                    "reconstruction_maximum_error": frozen.reconstruction_maximum_error,
                    "selection_frontend_id": row["frontend_id"],
                    "source_bundle_sha256": frozen.source_bundle_sha256,
                    "compact_bundle_sha256": compact_input["sha256"],
                    "num_nodes": count,
                    **_prefixed_error_record("full", full_errors),
                    **_prefixed_error_record("canonical", canonical_errors),
                    **_prefixed_error_record("remainder", remainder_errors),
                    **timing,
                }
            )

        frozen_records.append(
            {
                "run_id": row["run_id"],
                "shape": row["shape"],
                "curve_label": _curve_label(row),
                "method": row["method"],
                "bandwidth": row.get("bandwidth"),
                "status": row["status"],
                "selection_frontend_id": row["frontend_id"],
                "grid_resolution": row["grid_resolution"],
                "projected_sample_count": row["projected_sample_count"],
                "normalized_maximum_sdf_residual": row["metrics"]["sdf_residual"][
                    "normalized_maximum"
                ],
                "converter_runtime_seconds": row["total_converter_runtime_seconds"],
                "reference_seconds": reference_seconds,
                "reference_order_agreement": reference_agreement,
                "full_reference_order_agreement": full_reference_agreement,
                "remainder_reference_order_agreement": remainder_reference_agreement,
                "remainder_reference_mixed_floor": (
                    remainder_reference_agreement
                    / max(float(np.max(np.abs(high_reference.remainder_values))), 1.0)
                ),
                "reconstruction_maximum_error": frozen.reconstruction_maximum_error,
                "source_bundle_sha256": frozen.source_bundle_sha256,
                "compact_bundle": compact_input,
                "node_results": node_records,
            }
        )

    for row in circle_records:
        flat_rows.append(
            {
                "record_kind": row["record_kind"],
                "run_id": "analytic_circle_poisson_control",
                "shape": "analytic_circle",
                "method": "exact",
                "bandwidth": None,
                "status": "success",
                "grid_resolution": None,
                "projected_sample_count": None,
                "normalized_maximum_sdf_residual": 0.0,
                "converter_runtime_seconds": 0.0,
                "reference_seconds": 0.0,
                "reference_order_agreement": 0.0,
                "full_reference_order_agreement": 0.0,
                "remainder_reference_order_agreement": 0.0,
                "reconstruction_maximum_error": 0.0,
                "selection_frontend_id": None,
                "source_bundle_sha256": None,
                "compact_bundle_sha256": None,
                "num_nodes": row["num_nodes"],
                **_prefixed_error_record("full", row["full_error"]),
                **_prefixed_error_record("canonical", row["canonical_error"]),
                **_prefixed_error_record("remainder", row["remainder_error"]),
                **row["timing"],
            }
        )

    largest_count = counts[-1]
    last_three = counts[-3:]
    acceptance_checks: list[dict[str, Any]] = []
    circle_by_n = {item["num_nodes"]: item for item in circle_records}
    circle_gate_n = 256
    circle_error = circle_by_n[circle_gate_n]["full_error"]["mixed_relative_error"]
    circle_ratios = [
        circle_by_n[64]["full_error"]["mixed_relative_error"]
        / circle_by_n[32]["full_error"]["mixed_relative_error"],
        circle_by_n[128]["full_error"]["mixed_relative_error"]
        / circle_by_n[64]["full_error"]["mixed_relative_error"],
    ]
    acceptance_checks.append(
        {
            "name": "analytic_circle",
            "passed": circle_error < 1.0e-12 and all(
                ratio < 0.01 for ratio in circle_ratios
            ),
            "description": (
                f"analytic circle mixed-relative error at N={circle_gate_n} is "
                f"{circle_error:.3e} < 1e-12, with N=32→64→128 ratios "
                + ", ".join(f"{ratio:.3e}" for ratio in circle_ratios)
                + " < 1e-2"
            ),
        }
    )
    for curve_record in frozen_records:
        by_n = {item["num_nodes"]: item for item in curve_record["node_results"]}
        method = curve_record["method"]
        reference_floor = max(
            5.0e-14,
            2.0 * float(curve_record["remainder_reference_mixed_floor"]),
        )
        if method in {"B", "C"}:
            gate_n = 256
            full_value = by_n[gate_n]["full_error"]["mixed_relative_error"]
            remainder_values = [
                by_n[count]["remainder_error"]["mixed_relative_error"]
                for count in (32, 64, 128)
            ]
            if remainder_values[0] <= reference_floor:
                reduction_passed = True
                reduction_description = "already reference/roundoff limited at N=32"
            else:
                ratios = [
                    upper / max(lower, np.finfo(float).tiny)
                    for lower, upper in zip(remainder_values, remainder_values[1:])
                ]
                pair_passes = [
                    upper <= reference_floor or ratio < 0.25
                    for upper, ratio in zip(remainder_values[1:], ratios)
                ]
                reduction_passed = all(pair_passes)
                reduction_description = (
                    "N=32→64→128 q-error ratios "
                    + ", ".join(f"{ratio:.3e}" for ratio in ratios)
                    + " < 0.25 or reference limited"
                )
            passed = full_value < 1.0e-11 and reduction_passed
            description = (
                f"{curve_record['run_id']} full error at N={gate_n} is "
                f"{full_value:.3e} < 1e-11; {reduction_description}"
            )
        else:
            value = by_n[largest_count]["remainder_error"]["mixed_relative_error"]
            ratios = [
                by_n[upper]["remainder_error"]["mixed_relative_error"]
                / max(
                    by_n[lower]["remainder_error"]["mixed_relative_error"],
                    np.finfo(float).tiny,
                )
                for lower, upper in zip(last_three, last_three[1:])
            ]
            pair_passes = [
                by_n[upper]["remainder_error"]["mixed_relative_error"]
                <= reference_floor
                or ratio < 0.2
                for upper, ratio in zip(last_three[1:], ratios)
            ]
            passed = value < 1.0e-8 and all(pair_passes)
            description = (
                f"{curve_record['run_id']} spline q-error at N={largest_count} is "
                f"{value:.3e} < 1e-8 and final ratios are "
                + ", ".join(f"{ratio:.3f}" for ratio in ratios)
                + " < 0.2 or reference limited"
            )
        acceptance_checks.append(
            {"name": curve_record["run_id"], "passed": passed, "description": description}
        )
    maximum_reference_disagreement = max(
        record["reference_order_agreement"] for record in frozen_records
    )
    acceptance_checks.append(
        {
            "name": "reference_agreement",
            "passed": maximum_reference_disagreement < agreement_tolerance,
            "description": (
                "the two composite-Gauss reference orders agree to "
                f"{maximum_reference_disagreement:.3e} < {agreement_tolerance:.1e}"
            ),
        }
    )

    method_c_rows = [row for row in study_rows if row.get("method") == "C"]
    payload = {
        "artifact_kind": "sdf_boundary_kress_proxy",
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "isolated scalar logarithmic Kress proxy; no BIE blocks, solve, or "
            "active solver integration"
        ),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        },
        "config": {
            "node_counts": counts,
            "target_count": targets_count,
            "timing_repeats": repeats,
            "fourier_reference_panels": panel_count,
            "reference_orders": (low_order, high_order),
            "reference_agreement_tolerance": agreement_tolerance,
            "poisson_concentration": 0.75,
            "poisson_phase": 0.37,
        },
        "source_study": {
            "artifact_root": _display_path(root),
            "curve_root": _display_path(curve_directory),
            "manifest_sha256": _sha256(source_manifest_path),
            "metrics_sha256": _sha256(source_metrics_path),
            "schema_version": manifest["schema_version"],
            "profile_name": manifest.get("profile", {}).get("name"),
            "row_count": len(study_rows),
            "selected_run_ids": [row["run_id"] for row in selected_rows],
            "method_c_successes": sum(row.get("status") == "success" for row in method_c_rows),
            "method_c_fallbacks": sum(row.get("status") == "fallback" for row in method_c_rows),
        },
        "frozen_curve_inputs": frozen_input_records,
        "analytic_circle_control": circle_records,
        "frozen_curves": frozen_records,
        "acceptance": {
            "passed": all(check["passed"] for check in acceptance_checks),
            "checks": acceptance_checks,
        },
    }

    metrics_path = output / "metrics.json"
    csv_path = output / "metrics.csv"
    summary_path = output / "summary.md"
    _write_json(metrics_path, payload)
    _write_csv(csv_path, flat_rows)
    summary_path.write_text(_markdown_summary(payload), encoding="utf-8")
    artifact_manifest = {
        "artifact_kind": "sdf_boundary_kress_proxy_manifest",
        "schema_version": 1,
        "generated_at_utc": payload["generated_at_utc"],
        "acceptance_passed": payload["acceptance"]["passed"],
        "source_study": payload["source_study"],
        "files": {
            "metrics.json": _sha256(metrics_path),
            "metrics.csv": _sha256(csv_path),
            "summary.md": _sha256(summary_path),
        },
        "frozen_curve_inputs": frozen_input_records,
    }
    _write_json(output / "manifest.json", artifact_manifest)
    return payload


def _default_output_directory() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPOSITORY_ROOT / "results" / "sdf_boundary_parameterization" / (
        f"kress-proxy-{timestamp}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply an isolated scalar logarithmic Kress proxy to frozen A/B/C "
            "boundary coefficients and write compact error/runtime evidence."
        )
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=REPOSITORY_ROOT
        / "results"
        / "sdf_boundary_parameterization"
        / "study-20260902",
        help="Completed SDF comparison artifact root containing manifest.json and metrics.json.",
    )
    parser.add_argument(
        "--curve-root",
        type=Path,
        default=None,
        help=(
            "Directory containing selected native coefficient NPZ files; defaults "
            "to ARTIFACT_ROOT/curves."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Empty output directory; defaults to a timestamped results directory.",
    )
    parser.add_argument("--target-count", type=int, default=16)
    parser.add_argument("--timing-repeats", type=int, default=5)
    parser.add_argument("--reference-panels", type=int, default=256)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output_dir or _default_output_directory()
    payload = run_benchmark(
        args.artifact_root,
        output,
        curve_root=args.curve_root,
        target_count=args.target_count,
        timing_repeats=args.timing_repeats,
        fourier_reference_panels=args.reference_panels,
    )
    print(f"artifacts: {Path(output).resolve()}")
    print(f"status: {'PASS' if payload['acceptance']['passed'] else 'REVISE'}")
    return 0 if payload["acceptance"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
