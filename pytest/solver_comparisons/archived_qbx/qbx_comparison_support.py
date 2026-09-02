"""Archived QBX-row support for the five solver-comparison pipelines.

These rows reproduce the closed compressed-cloud QBX investigation only when
``--include-qbx-archive`` is supplied.  They are not production candidates.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np

import gpr_bem_kdiff
from gpr_bem_qbx import FullRowQBX


ReferenceField = Callable[[float, Any], np.ndarray]


def run_qbx_metrics(
    *,
    boundary: Any,
    sources: np.ndarray,
    receivers: np.ndarray,
    frequencies_hz: Sequence[float],
    exterior: Any,
    interior: Any,
    eps0: float,
    mu0: float,
    t_assembly: FullRowQBX,
    discretization: str,
    sdf_fn: Callable | None = None,
    reference_field: ReferenceField | Mapping[float, np.ndarray] | None = None,
) -> dict[str, Any]:
    """Run one full-row QBX T strategy through the shared kdiff solver.

    The strategy object is deliberately reused over the frequency sweep so its
    frequency-independent source quadrature and prolongation are prepared once.
    """

    frequencies = [float(frequency) for frequency in frequencies_hz]
    metrics: dict[str, Any] = {
        "num_samples": int(boundary.num_samples),
        "merge_distance": float(boundary.merge_distance),
        "requested_offset_distance": None,
        "offset_distance": None,
        "formulation": "muller",
        "normal_derivative_scheme": discretization,
        "relative_error": {frequency: float("nan") for frequency in frequencies},
        "condition_number": {},
        "residual": {},
        "scattered": {},
        "elapsed_seconds": 0.0,
        "t_assembly": {},
    }
    for frequency_hz in frequencies:
        started = time.perf_counter()
        forward = gpr_bem_kdiff.solve_ibim_tmz_total_field_batch(
            boundary,
            sources,
            receivers,
            2.0 * np.pi * frequency_hz,
            1.0,
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            sdf_fn=sdf_fn,
            t_assembly=t_assembly,
        )
        metrics["elapsed_seconds"] += time.perf_counter() - started
        scattered = np.asarray(forward.scattered_receiver)
        metrics["scattered"][frequency_hz] = scattered
        metrics["residual"][frequency_hz] = float(forward.linear_system_relative_residual)
        metrics["condition_number"][frequency_hz] = float(
            np.linalg.cond(np.asarray(forward.system.system_matrix)[0])
        )
        report = forward.system.t_assembly_report
        if report is None:
            raise AssertionError("FullRowQBX solve did not return a T-assembly report.")
        metrics["t_assembly"][frequency_hz] = {
            "method": report.method,
            "parameters": dict(report.parameters),
            "diagnostics": dict(report.diagnostics),
        }
        if reference_field is not None:
            exact = (
                np.asarray(reference_field[frequency_hz])
                if isinstance(reference_field, Mapping)
                else np.asarray(reference_field(frequency_hz, forward))
            )
            metrics["relative_error"][frequency_hz] = float(
                np.linalg.norm(scattered - exact) / np.linalg.norm(exact)
            )
    return metrics


__all__ = ["run_qbx_metrics"]
