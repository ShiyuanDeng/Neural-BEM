"""Strict, solver-neutral artifacts for SDF-to-boundary comparisons.

This module contains only explicit output helpers.  Importing it does not
select or mutate an active solver, and Matplotlib is imported lazily only when
a diagnostic figure is requested.
"""

from __future__ import annotations

import csv
from dataclasses import fields, is_dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.spatial import cKDTree

from ordered_boundary import PeriodicParameterization2D

from .fields import ImplicitField2D
from .metrics import (
    BoundaryMetricConfig,
    coordinate_spectrum,
    evaluate_field_gradients,
    evaluate_field_values,
    sample_parameterization,
)


Array = np.ndarray
_TWO_PI = 2.0 * np.pi


def _strict_jsonable(value: Any) -> Any:
    """Convert common scientific values to standards-compliant JSON data.

    Nonfinite floating-point values become ``null``.  Callers should pair such
    missing metrics with the run's explicit status/failure reason rather than
    relying on the non-standard JSON spellings ``NaN`` or ``Infinity``.
    """

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        result = float(value)
        return result if np.isfinite(result) else None
    if isinstance(value, (complex, np.complexfloating)):
        result = complex(value)
        return {
            "real": float(result.real) if np.isfinite(result.real) else None,
            "imag": float(result.imag) if np.isfinite(result.imag) else None,
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return _strict_jsonable(value.tolist())
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _strict_jsonable(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _strict_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_strict_jsonable(item) for item in sorted(value, key=str)]
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable.")


def write_strict_json(path: str | Path, payload: Any, *, indent: int = 2) -> Path:
    """Write JSON with ``allow_nan=False`` and a trailing newline."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    serializable = _strict_jsonable(payload)
    destination.write_text(
        json.dumps(
            serializable,
            indent=int(indent),
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def _as_record_mapping(record: Any) -> Mapping[str, Any]:
    if isinstance(record, Mapping):
        return record
    if is_dataclass(record) and not isinstance(record, type):
        return {item.name: getattr(record, item.name) for item in fields(record)}
    to_dict = getattr(record, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if isinstance(result, Mapping):
            return result
    raise TypeError("CSV records must be mappings, dataclasses, or expose to_dict().")


def _flatten_mapping(
    mapping: Mapping[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, raw_value in mapping.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        value = _strict_jsonable(raw_value)
        if isinstance(value, Mapping):
            flattened.update(_flatten_mapping(value, prefix=name))
        elif isinstance(value, (list, tuple)):
            flattened[name] = json.dumps(value, sort_keys=True, allow_nan=False)
        else:
            flattened[name] = value
    return flattened


def write_metrics_csv(path: str | Path, records: Iterable[Any]) -> Path:
    """Write flattened metric records with a stable union of columns."""

    rows = [_flatten_mapping(_as_record_mapping(record)) for record in records]
    if not rows:
        raise ValueError("records must contain at least one row.")
    columns = sorted({key for row in rows for key in row})
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=columns,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key, "") for key in columns})
    return destination


def write_npz(
    path: str | Path,
    arrays: Mapping[str, Any] | None = None,
    **named_arrays: Any,
) -> Path:
    """Write a compressed NPZ bundle without pickled object arrays."""

    destination = Path(path)
    if destination.suffix.lower() != ".npz":
        raise ValueError("NPZ artifact paths must end in '.npz'.")
    payload = dict(arrays or {})
    overlap = set(payload) & set(named_arrays)
    if overlap:
        raise ValueError(f"Duplicate NPZ array names: {sorted(overlap)}")
    payload.update(named_arrays)
    if not payload:
        raise ValueError("At least one named array is required.")
    converted: dict[str, Array] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key:
            raise ValueError("NPZ array names must be non-empty strings.")
        array = np.asarray(value)
        if array.dtype.hasobject:
            raise TypeError(f"NPZ array {key!r} has object dtype; pickled data is not allowed.")
        converted[key] = array
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, **converted)
    return destination


def _optional_contour(values: Any, *, name: str) -> Array | None:
    if values is None:
        return None
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError(f"{name} must have shape (N, 2).")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain finite coordinates.")
    return array


def _plot_closed(ax, points: Array, *args, **kwargs) -> None:
    closed = np.vstack((points, points[0]))
    ax.plot(closed[:, 0], closed[:, 1], *args, **kwargs)


def plot_boundary_diagnostics(
    path: str | Path,
    curve: PeriodicParameterization2D,
    *,
    field: ImplicitField2D | None = None,
    reference: PeriodicParameterization2D | None = None,
    raw_contour: Array | None = None,
    projected_contour: Array | None = None,
    config: BoundaryMetricConfig | None = None,
    title: str | None = None,
) -> Path:
    """Write the requested six-panel geometry and parameterization figure."""

    if not isinstance(curve, PeriodicParameterization2D):
        raise TypeError("curve must be a PeriodicParameterization2D.")
    if reference is not None and not isinstance(reference, PeriodicParameterization2D):
        raise TypeError("reference must be a PeriodicParameterization2D when supplied.")
    settings = BoundaryMetricConfig() if config is None else config
    raw = _optional_contour(raw_contour, name="raw_contour")
    projected = _optional_contour(projected_contour, name="projected_contour")

    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    dense = sample_parameterization(curve, settings.dense_resolution)
    reference_dense = (
        sample_parameterization(reference, settings.reference_resolution)
        if reference is not None
        else None
    )
    parameter = (dense.parameters - curve.parameter_origin) * (_TWO_PI / curve.period)
    field_values = evaluate_field_values(field, dense.points) if field is not None else None
    normalized_residual = None
    if field is not None:
        gradient_norm = np.linalg.norm(evaluate_field_gradients(field, dense.points), axis=1)
        normalized_residual = np.abs(field_values) / (gradient_norm + settings.gradient_epsilon)

    fft_samples = sample_parameterization(curve, settings.fft_resolution)
    modes, amplitudes = coordinate_spectrum(
        fft_samples.points,
        center_coordinates=settings.center_fft_coordinates,
    )

    fig, axes = plt.subplots(2, 3, figsize=(13.2, 7.8), dpi=150)
    geometry_ax, residual_ax, speed_ax, curvature_ax, spectrum_ax, final_ax = axes.ravel()

    if raw is not None:
        _plot_closed(
            geometry_ax,
            raw,
            color="#9e9e9e",
            linewidth=0.9,
            marker=".",
            markersize=2.0,
            label="marching contour",
        )
    if projected is not None:
        geometry_ax.scatter(
            projected[:, 0],
            projected[:, 1],
            s=7,
            color="#ff7f0e",
            alpha=0.75,
            linewidths=0.0,
            label="projected points",
        )
    if reference_dense is not None:
        _plot_closed(
            geometry_ax,
            reference_dense.points,
            color="#111111",
            linewidth=1.2,
            linestyle="--",
            label="reference",
        )
    _plot_closed(
        geometry_ax,
        dense.points,
        color="#1f77b4",
        linewidth=1.5,
        label="fitted curve",
    )
    geometry_ax.set_aspect("equal", adjustable="box")
    geometry_ax.set_title("Extracted and fitted boundary")
    geometry_ax.set_xlabel("x")
    geometry_ax.set_ylabel("y")
    geometry_ax.grid(True, alpha=0.25)
    geometry_ax.legend(fontsize=7)

    if field_values is not None:
        residual_ax.plot(parameter, field_values, color="#d62728", linewidth=1.0)
        residual_ax.axhline(0.0, color="0.3", linewidth=0.7)
        residual_ax.set_ylabel("F(gamma(t))")
    else:
        residual_ax.text(0.5, 0.5, "implicit field not supplied", ha="center", va="center")
    residual_ax.set_title("Pointwise implicit residual")
    residual_ax.set_xlabel("t")
    residual_ax.grid(True, alpha=0.25)

    speed_ax.plot(parameter, dense.speeds, color="#2ca02c", linewidth=1.0)
    speed_ax.set_title("Parameterization speed")
    speed_ax.set_xlabel("t")
    speed_ax.set_ylabel("|gamma'(t)|")
    speed_ax.grid(True, alpha=0.25)

    curvature_ax.plot(parameter, dense.curvatures, color="#9467bd", linewidth=1.0)
    curvature_ax.set_title("Signed curvature")
    curvature_ax.set_xlabel("t")
    curvature_ax.set_ylabel("kappa(t)")
    curvature_ax.grid(True, alpha=0.25)

    positive = amplitudes > 0.0
    spectrum_ax.semilogy(
        modes[positive],
        amplitudes[positive],
        color="#8c564b",
        marker=".",
        markersize=3,
        linewidth=0.8,
    )
    spectrum_ax.axvline(
        settings.fft_tail_start_mode,
        color="0.35",
        linestyle="--",
        linewidth=0.8,
        label="tail cutoff",
    )
    spectrum_ax.set_title("Coordinate Fourier spectrum")
    spectrum_ax.set_xlabel("mode |k|")
    spectrum_ax.set_ylabel("combined amplitude")
    spectrum_ax.grid(True, which="both", alpha=0.25)
    spectrum_ax.legend(fontsize=7)

    if reference_dense is not None:
        nearest = cKDTree(reference_dense.points).query(dense.points, k=1)[1]
        matched = reference_dense.outward_normals[np.asarray(nearest, dtype=np.int64)]
        dot = np.sum(dense.outward_normals * matched, axis=1)
        angle = np.arccos(np.clip(dot, -1.0, 1.0))
        final_ax.plot(parameter, angle, color="#17becf", linewidth=1.0)
        final_ax.set_title("Nearest-reference normal error")
        final_ax.set_ylabel("angle [rad]")
    elif normalized_residual is not None:
        final_ax.semilogy(
            parameter,
            np.maximum(normalized_residual, np.finfo(np.float64).tiny),
            color="#17becf",
            linewidth=1.0,
        )
        final_ax.set_title("Normalized geometric residual")
        final_ax.set_ylabel("|F| / (|grad F| + eps)")
    else:
        cumulative = np.cumsum(dense.speeds) * curve.period / dense.parameters.size
        cumulative /= cumulative[-1]
        final_ax.plot(parameter, cumulative, color="#17becf", linewidth=1.0)
        final_ax.set_title("Normalized cumulative arc length")
        final_ax.set_ylabel("s(t) / L")
    final_ax.set_xlabel("t")
    final_ax.grid(True, alpha=0.25)

    fig.suptitle(title or f"{curve.name}: boundary diagnostics")
    fig.tight_layout()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination)
    plt.close(fig)
    return destination


def _record_value(record: Any, *names: str) -> Any:
    for name in names:
        if isinstance(record, Mapping) and name in record:
            return record[name]
        if hasattr(record, name):
            return getattr(record, name)
    return None


def _first_component_contour(values: Any) -> Any:
    if values is None:
        return None
    if isinstance(values, (tuple, list)) and values:
        candidate = np.asarray(values[0])
        if candidate.ndim == 2 and candidate.shape[-1] == 2:
            return candidate
    return values


def plot_run_record(
    path: str | Path,
    record: Any,
    *,
    field: ImplicitField2D | None = None,
    reference: PeriodicParameterization2D | None = None,
    frontend: Any | None = None,
    config: BoundaryMetricConfig | None = None,
) -> Path:
    """Plot a mapping/dataclass run record using conventional field names.

    The fitted curve is found under ``parameterization`` or ``curve``.  A
    separately supplied front-end result may expose ``raw_contour`` or
    ``raw_contours`` and ``projected_points`` or ``projected_contour``.
    Explicit keyword arguments take precedence over values stored on the run
    record.
    """

    curve = _record_value(record, "parameterization", "curve")
    if curve is None:
        method_result = _record_value(record, "method_result", "result")
        curve = _record_value(method_result, "parameterization", "curve")
    if not isinstance(curve, PeriodicParameterization2D):
        raise ValueError("run record does not contain a continuous parameterization.")
    source = frontend if frontend is not None else _record_value(record, "frontend")
    raw = _first_component_contour(
        _record_value(source, "raw_contour", "raw_contours")
        if source is not None
        else _record_value(record, "raw_contour", "raw_contours")
    )
    projected = _first_component_contour(
        _record_value(source, "projected_points", "projected_contour", "projected_contours")
        if source is not None
        else _record_value(record, "projected_points", "projected_contour", "projected_contours")
    )
    resolved_field = field if field is not None else _record_value(record, "field")
    resolved_reference = (
        reference if reference is not None else _record_value(record, "reference")
    )
    method_name = _record_value(record, "method_name", "name")
    if method_name is None:
        method_result = _record_value(record, "method_result", "result")
        method_name = _record_value(method_result, "method_name", "name")
    return plot_boundary_diagnostics(
        path,
        curve,
        field=resolved_field,
        reference=resolved_reference,
        raw_contour=raw,
        projected_contour=projected,
        config=config,
        title=str(method_name) if method_name is not None else None,
    )


__all__ = [
    "plot_boundary_diagnostics",
    "plot_run_record",
    "write_metrics_csv",
    "write_npz",
    "write_strict_json",
]
