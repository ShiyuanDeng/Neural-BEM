"""Validation metrics for forward frequency responses and B-scans."""

from __future__ import annotations

import numpy as np

__all__ = [
    "bscan_error_metrics",
    "frequency_response_error_metrics",
]


def frequency_response_error_metrics(
    observed: np.ndarray,
    reference: np.ndarray,
    *,
    frequencies_hz: np.ndarray | None = None,
    mixed_floor_fraction: float = 0.05,
) -> dict[str, np.ndarray | float]:
    """Return absolute, relative, mixed, and broadband frequency-response errors."""

    observed_array, reference_array = _coerce_matching_arrays(observed, reference, dtype=np.complex128)
    if observed_array.ndim != 2:
        raise ValueError("observed and reference must have shape (num_receivers, num_frequencies).")
    frequency_count = observed_array.shape[1]
    if frequencies_hz is None:
        frequency_axis = np.arange(frequency_count, dtype=float)
    else:
        frequency_axis = np.asarray(frequencies_hz, dtype=float).reshape(-1)
        if frequency_axis.shape != (frequency_count,):
            raise ValueError("frequencies_hz must contain one value per frequency sample.")

    difference = observed_array - reference_array
    reference_norm = np.linalg.norm(reference_array, axis=0)
    observed_norm = np.linalg.norm(observed_array, axis=0)
    error_norm = np.linalg.norm(difference, axis=0)
    mixed_floor = float(mixed_floor_fraction) * float(np.max(reference_norm))
    relative_error = _safe_divide(error_norm, reference_norm)
    mixed_error = error_norm / np.maximum(reference_norm, mixed_floor)
    broadband_reference_norm = float(np.linalg.norm(reference_array))
    broadband_error_norm = float(np.linalg.norm(difference))
    return {
        "frequencies_hz": frequency_axis,
        "reference_norm_by_frequency": reference_norm,
        "observed_norm_by_frequency": observed_norm,
        "error_norm_by_frequency": error_norm,
        "absolute_error_by_frequency": error_norm,
        "relative_error_by_frequency": relative_error,
        "mixed_error_by_frequency": mixed_error,
        "mixed_floor": mixed_floor,
        "broadband_reference_norm": broadband_reference_norm,
        "broadband_error_norm": broadband_error_norm,
        "broadband_relative_error": _safe_scalar_divide(broadband_error_norm, broadband_reference_norm),
        "max_relative_error": float(np.max(relative_error)),
        "max_mixed_error": float(np.max(mixed_error)),
    }


def bscan_error_metrics(
    observed: np.ndarray,
    reference: np.ndarray,
    *,
    time_vector: np.ndarray,
    time_gate_start: float | None = None,
    mixed_floor_fraction: float = 0.05,
) -> dict[str, float]:
    """Return full-record and gated B-scan error metrics."""

    observed_array, reference_array = _coerce_matching_arrays(observed, reference, dtype=float)
    if observed_array.ndim != 2:
        raise ValueError("observed and reference must have shape (num_receivers, num_time_samples).")
    time_array = np.asarray(time_vector, dtype=float).reshape(-1)
    if time_array.shape != (observed_array.shape[1],):
        raise ValueError("time_vector must contain one value per B-scan time sample.")
    if time_gate_start is None:
        gate_mask = np.ones_like(time_array, dtype=bool)
    else:
        gate_mask = time_array >= float(time_gate_start)
        if not np.any(gate_mask):
            raise ValueError("The time gate removed all samples.")

    full_reference_norm = float(np.linalg.norm(reference_array))
    mixed_floor = float(mixed_floor_fraction) * full_reference_norm
    full = _array_error_scalars(observed_array, reference_array, mixed_floor=mixed_floor)
    gated = _array_error_scalars(
        observed_array[:, gate_mask],
        reference_array[:, gate_mask],
        mixed_floor=mixed_floor,
    )
    return {
        "time_gate_start": float("nan") if time_gate_start is None else float(time_gate_start),
        "reference_norm_all": full["reference_norm"],
        "error_norm_all": full["error_norm"],
        "relative_error_all": full["relative_error"],
        "mixed_error_all": full["mixed_error"],
        "reference_norm_gate": gated["reference_norm"],
        "error_norm_gate": gated["error_norm"],
        "relative_error_gate": gated["relative_error"],
        "mixed_error_gate": gated["mixed_error"],
    }


def _coerce_matching_arrays(
    observed: np.ndarray,
    reference: np.ndarray,
    *,
    dtype,
) -> tuple[np.ndarray, np.ndarray]:
    observed_array = np.asarray(observed, dtype=dtype)
    reference_array = np.asarray(reference, dtype=dtype)
    if observed_array.shape != reference_array.shape:
        raise ValueError("observed and reference must have the same shape.")
    return observed_array, reference_array


def _array_error_scalars(
    observed: np.ndarray,
    reference: np.ndarray,
    *,
    mixed_floor: float,
) -> dict[str, float]:
    difference = np.asarray(observed) - np.asarray(reference)
    reference_norm = float(np.linalg.norm(reference))
    error_norm = float(np.linalg.norm(difference))
    return {
        "reference_norm": reference_norm,
        "error_norm": error_norm,
        "relative_error": _safe_scalar_divide(error_norm, reference_norm),
        "mixed_error": _safe_scalar_divide(error_norm, max(reference_norm, mixed_floor)),
    }


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    result = np.full_like(np.asarray(numerator, dtype=float), np.inf, dtype=float)
    mask = np.asarray(denominator, dtype=float) > 0.0
    result[mask] = np.asarray(numerator, dtype=float)[mask] / np.asarray(denominator, dtype=float)[mask]
    return result


def _safe_scalar_divide(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if float(denominator) > 0.0 else float("inf")
