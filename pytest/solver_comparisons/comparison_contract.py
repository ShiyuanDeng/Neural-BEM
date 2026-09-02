"""Solver-neutral contracts shared by receiver-field comparisons."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def validate_cached_pair0_coordinates(
    entry: Mapping[str, Any],
    sources: np.ndarray,
    receivers: np.ndarray,
    *,
    scene_center: tuple[float, float],
) -> None:
    """Ensure a translated FDTD scene represents the same relative pair zero."""

    source_points = np.asarray(sources, dtype=np.float64)
    receiver_points = np.asarray(receivers, dtype=np.float64)
    if source_points.ndim != 2 or source_points.shape[1] != 2:
        raise ValueError("sources must have shape (count, 2).")
    if receiver_points.shape != source_points.shape:
        raise ValueError("receivers must have the same shape as sources.")
    cached_source = np.asarray(entry["tx"], dtype=np.float64).reshape(-1)
    cached_receiver = np.asarray(entry["rx"], dtype=np.float64).reshape(-1)
    cached_center = np.asarray(entry["target_center"], dtype=np.float64).reshape(-1)
    expected_center = np.asarray(scene_center, dtype=np.float64).reshape(-1)
    if any(
        value.shape != (2,)
        for value in (cached_source, cached_receiver, cached_center, expected_center)
    ):
        raise ValueError("cached and comparison pair coordinates must each have shape (2,).")

    # gprMax translates each target into a compact FDTD domain. Translation
    # does not change the homogeneous-full-space problem, so compare scan
    # vectors relative to the target rather than unrelated absolute origins.
    cached_source_offset = cached_source - cached_center
    cached_receiver_offset = cached_receiver - cached_center
    expected_source_offset = source_points[0] - expected_center
    expected_receiver_offset = receiver_points[0] - expected_center
    if not np.allclose(
        cached_source_offset, expected_source_offset, rtol=0.0, atol=1.0e-12
    ):
        raise ValueError("cached gprMax transmitter offset does not match scan pair 0.")
    if not np.allclose(
        cached_receiver_offset, expected_receiver_offset, rtol=0.0, atol=1.0e-12
    ):
        raise ValueError("cached gprMax receiver offset does not match scan pair 0.")


__all__ = ["validate_cached_pair0_coordinates"]
