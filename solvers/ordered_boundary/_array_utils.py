"""Small array-normalisation helpers for ordered-boundary geometry."""

from __future__ import annotations

import numpy as np


def readonly_float_array(values, *, name: str, ndim: int | None = None) -> np.ndarray:
    """Return an owned, finite, read-only ``float64`` array."""

    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    array = np.array(values, dtype=np.float64, copy=True)
    if ndim is not None and array.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions.")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")
    array.setflags(write=False)
    return array


def readonly_int_array(values, *, name: str, ndim: int | None = None) -> np.ndarray:
    """Return an owned, read-only integer array."""

    array = np.array(values, dtype=np.int64, copy=True)
    if ndim is not None and array.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions.")
    array.setflags(write=False)
    return array


def cross2d(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Two-dimensional scalar cross product with NumPy broadcasting."""

    return first[..., 0] * second[..., 1] - first[..., 1] * second[..., 0]
