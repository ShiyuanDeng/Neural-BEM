"""Frequency/time-domain transforms used by the IBIM inverse workflow."""

from __future__ import annotations

import numpy as np


def trapz_weights(abscissae: np.ndarray) -> np.ndarray:
    points = np.asarray(abscissae, dtype=float)
    if points.ndim != 1:
        raise ValueError("abscissae must be one-dimensional.")
    if points.size == 0:
        raise ValueError("abscissae must not be empty.")
    if points.size == 1:
        return np.zeros(1, dtype=float)

    deltas = np.diff(points)
    weights = np.empty(points.size, dtype=float)
    weights[0] = 0.5 * deltas[0]
    weights[-1] = 0.5 * deltas[-1]
    if points.size > 2:
        weights[1:-1] = 0.5 * (deltas[:-1] + deltas[1:])
    return weights


def _coerce_angular_frequencies(angular_frequencies: np.ndarray) -> np.ndarray:
    frequencies = np.atleast_1d(np.asarray(angular_frequencies, dtype=float))
    if frequencies.ndim != 1 or frequencies.size == 0:
        raise ValueError("angular_frequencies must be a non-empty scalar or 1D array.")
    return frequencies


def _coerce_time_vector(time_vector: np.ndarray) -> np.ndarray:
    time_array = np.asarray(time_vector, dtype=float)
    if time_array.ndim != 1 or time_array.size == 0:
        raise ValueError("time_vector must be a non-empty 1D array.")
    return time_array


def _coerce_frequency_window(
    frequency_window: np.ndarray | None,
    num_frequencies: int,
) -> np.ndarray:
    if frequency_window is None:
        return np.ones(num_frequencies, dtype=float)
    window = np.asarray(frequency_window, dtype=float)
    if window.shape != (num_frequencies,):
        raise ValueError("frequency_window must have shape (num_frequencies,).")
    return window


def inverse_frequency_transform_matrix(
    angular_frequencies: np.ndarray,
    time_vector: np.ndarray,
    *,
    frequency_window: np.ndarray | None = None,
) -> np.ndarray:
    frequencies = _coerce_angular_frequencies(angular_frequencies)
    time_array = _coerce_time_vector(time_vector)
    window = _coerce_frequency_window(frequency_window, frequencies.size)
    integration_weights = trapz_weights(frequencies) / (2.0 * np.pi)
    return (window * integration_weights)[:, None] * np.exp(-1j * frequencies[:, None] * time_array[None, :])


def bscan_from_frequency_response(
    frequency_response: np.ndarray,
    angular_frequencies: np.ndarray,
    time_vector: np.ndarray,
    *,
    frequency_window: np.ndarray | None = None,
) -> np.ndarray:
    response = np.asarray(frequency_response, dtype=np.complex128)
    if response.ndim == 1:
        response = response[None, :]
    if response.ndim != 2:
        raise ValueError("frequency_response must have shape (batch, num_frequencies).")
    transform = inverse_frequency_transform_matrix(
        angular_frequencies,
        time_vector,
        frequency_window=frequency_window,
    )
    if response.shape[1] != transform.shape[0]:
        raise ValueError("frequency_response must have one column per angular frequency.")
    return 2.0 * np.real(response @ transform)
