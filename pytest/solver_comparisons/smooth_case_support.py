"""Shared SDF-to-Kress comparison plumbing for smooth one-component scenes.

This module is test orchestration, not a solver pipeline.  It owns the one
place where the comparison converts the same Torch level-set callable used by
IBIM into a :class:`ordered_boundary.PeriodicCurve2D` for ``gpr_bem_kress``.
The solver itself remains coupled only to ordered boundary geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping

import numpy as np
import torch

from gpr_bem_kress import (
    KressSolveConfig,
    Material,
    solve_kress_tmz_total_field_batch,
)
from ordered_boundary import PeriodicCurve2D
from sdf_to_ordered_boundary import (
    FrontendConfig,
    MethodBConfig,
    TorchImplicitField2D,
    fit_method_b,
    prepare_single_component,
)


ReferenceField = Callable[[float, Any], np.ndarray]


@dataclass(frozen=True)
class KressGeometryConfig:
    """Fixed, explicit discretisation choices for the comparison suite."""

    projected_samples: int = 256
    bandwidth: int = 48
    num_nodes: int = 128

    def __post_init__(self) -> None:
        if self.projected_samples < 8:
            raise ValueError("projected_samples must be at least 8.")
        if self.bandwidth < 1:
            raise ValueError("bandwidth must be positive.")
        if self.projected_samples < 2 * self.bandwidth + 1:
            raise ValueError("projected_samples must resolve the Fourier bandwidth.")
        if self.num_nodes < 8 or self.num_nodes % 2:
            raise ValueError("num_nodes must be even and at least 8 for Kress quadrature.")
        if self.num_nodes < 2 * self.bandwidth + 2:
            raise ValueError("num_nodes must resolve the fitted Fourier curve without aliasing.")


@dataclass(frozen=True)
class KressGeometryBuild:
    """One reusable Method-B curve plus separately measured preprocessing."""

    curve: PeriodicCurve2D
    frontend_seconds: float
    fit_seconds: float
    discretize_seconds: float
    total_seconds: float
    maximum_projected_sdf_residual: float
    maximum_curve_sdf_residual: float
    speed_ratio: float
    config: KressGeometryConfig


def build_kress_geometry(
    sdf_fn: Callable[[torch.Tensor], torch.Tensor],
    *,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    grid_shape: tuple[int, int],
    component_id: str,
    config: KressGeometryConfig = KressGeometryConfig(),
) -> KressGeometryBuild:
    """Extract and fit Method B from the exact Torch SDF callable used by IBIM."""

    if not callable(sdf_fn):
        raise TypeError("sdf_fn must be callable.")
    total_started = perf_counter()
    field = TorchImplicitField2D(
        sdf_fn,
        dtype=torch.float64,
        name=f"{component_id}-shared-sdf",
        sign_convention="negative_inside",
    )

    frontend_started = perf_counter()
    frontend = prepare_single_component(
        field,
        FrontendConfig(
            bounds=bounds,
            grid_shape=grid_shape,
            projected_samples=config.projected_samples,
        ),
    )
    frontend_seconds = perf_counter() - frontend_started
    component = frontend.single_component
    projection_residual = component.projection_passes[-1].maximum_residual

    fit_started = perf_counter()
    fit = fit_method_b(
        component,
        config=MethodBConfig(bandwidth=config.bandwidth),
        component_id=component_id,
        source_identifier=f"{component_id}-shared-sdf",
        projection_residual=projection_residual,
    )
    fit_seconds = perf_counter() - fit_started
    if fit.parameterization is None:  # defensive; successful MethodResult forbids this
        raise RuntimeError("Method B returned no periodic parameterization.")

    discretize_started = perf_counter()
    curve = fit.parameterization.discretize(config.num_nodes, require_even=True)
    discretize_seconds = perf_counter() - discretize_started

    # PeriodicCurve2D arrays are deliberately read-only.  Copy before adapting
    # them to Torch so torch.as_tensor does not warn about non-writable storage.
    curve_residual = np.abs(field.value(np.array(curve.points, copy=True)))
    speed_ratio = float(np.max(curve.speeds) / np.min(curve.speeds))
    return KressGeometryBuild(
        curve=curve,
        frontend_seconds=float(frontend_seconds),
        fit_seconds=float(fit_seconds),
        discretize_seconds=float(discretize_seconds),
        total_seconds=float(perf_counter() - total_started),
        maximum_projected_sdf_residual=float(projection_residual),
        maximum_curve_sdf_residual=float(np.max(curve_residual)),
        speed_ratio=speed_ratio,
        config=config,
    )


def _relative_l2(got: np.ndarray, expected: np.ndarray) -> float:
    numerator = float(np.linalg.norm(got - expected))
    denominator = float(np.linalg.norm(expected))
    if denominator == 0.0:
        return 0.0 if numerator == 0.0 else float("inf")
    return numerator / denominator


def run_kress_metrics(
    geometry: KressGeometryBuild,
    *,
    sources: np.ndarray,
    receivers: np.ndarray,
    frequencies_hz: tuple[float, ...],
    reference_field: ReferenceField,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
) -> dict[str, Any]:
    """Run the full ring and report its paired diagonal against one oracle.

    ``gpr_bem_kress`` evaluates a full source-by-receiver matrix.  The ACC
    comparison contract is paired, so only its diagonal enters receiver L2.
    The retained metadata keeps that distinction visible in exported results.
    """

    source_points = np.asarray(sources, dtype=np.float64)
    receiver_points = np.asarray(receivers, dtype=np.float64)
    if source_points.shape != receiver_points.shape:
        raise ValueError("The paired comparison requires matching source/receiver arrays.")
    pair_count = int(source_points.shape[0])
    metrics: dict[str, Any] = {
        "num_samples": int(geometry.curve.num_nodes),
        "merge_distance": None,
        "requested_offset_distance": None,
        "offset_distance": None,
        "formulation": "muller",
        "normal_derivative_scheme": "periodic_kress",
        "sampling": "shared_sdf_method_b",
        "relative_error": {},
        "index0_relative_error": {},
        "condition_number": {},
        "residual": {},
        "incident_representation_leak": {},
        "scattered": {},
        "assembly_seconds": {},
        "linear_solve_seconds": {},
        "receiver_evaluation_seconds": {},
        "elapsed_seconds": 0.0,
        "preprocessing_seconds": float(geometry.total_seconds),
        "frontend_seconds": float(geometry.frontend_seconds),
        "fit_seconds": float(geometry.fit_seconds),
        "discretize_seconds": float(geometry.discretize_seconds),
        "end_to_end_seconds": 0.0,
        "pair_count": pair_count,
        "error_pair_count": pair_count,
        "num_sources": pair_count,
        "num_receivers": pair_count,
        "receiver_matrix_shape": (pair_count, pair_count),
        "internal_receiver_matrix_shape": (pair_count, pair_count),
        "reported_field_shape": (pair_count,),
        "receiver_selection": "paired_diagonal",
        "error_scope": f"full-ring relative L2 ({pair_count} paired fields)",
        "receiver_evaluation_scope": (
            f"diagonal of {pair_count}x{pair_count} source-receiver matrix"
        ),
        "component_id": geometry.curve.component_id,
        "geometry_source_kind": geometry.curve.provenance.source_kind,
        "geometry_source_identifier": geometry.curve.provenance.source_identifier,
        "maximum_projected_sdf_residual": float(
            geometry.maximum_projected_sdf_residual
        ),
        "maximum_curve_sdf_residual": float(geometry.maximum_curve_sdf_residual),
        "speed_ratio": float(geometry.speed_ratio),
        "fourier_bandwidth": int(geometry.config.bandwidth),
        "projected_samples": int(geometry.config.projected_samples),
    }

    solve_config = KressSolveConfig(compute_condition_number=False)
    for frequency_hz in frequencies_hz:
        angular_frequency = 2.0 * np.pi * frequency_hz
        started = perf_counter()
        forward = solve_kress_tmz_total_field_batch(
            geometry.curve,
            source_points,
            receiver_points,
            angular_frequency,
            1.0,
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            config=solve_config,
        )
        metrics["elapsed_seconds"] += perf_counter() - started

        scattered_matrix = np.asarray(forward.scattered_receiver)
        if scattered_matrix.shape != (pair_count, pair_count):
            raise ValueError(
                "Kress comparison expected a full source-receiver matrix; "
                f"received {scattered_matrix.shape}."
            )
        scattered = np.diag(scattered_matrix)
        reference = np.asarray(reference_field(frequency_hz, forward), dtype=np.complex128)
        if reference.shape != (pair_count,):
            raise ValueError(
                f"reference_field must return ({pair_count},), received {reference.shape}."
            )

        metrics["scattered"][frequency_hz] = scattered
        metrics["relative_error"][frequency_hz] = _relative_l2(scattered, reference)
        metrics["index0_relative_error"][frequency_hz] = _relative_l2(
            scattered[:1], reference[:1]
        )
        metrics["residual"][frequency_hz] = float(
            forward.linear_system_relative_residual
        )
        metrics["incident_representation_leak"][frequency_hz] = float(
            forward.incident_representation_leak
        )
        # Match the legacy comparison timing convention: condition estimation
        # is reported but is deliberately outside elapsed_seconds.
        metrics["condition_number"][frequency_hz] = float(
            np.linalg.cond(np.asarray(forward.system.system_matrix))
        )
        metrics["assembly_seconds"][frequency_hz] = float(
            forward.system.assembly_seconds
        )
        metrics["linear_solve_seconds"][frequency_hz] = float(forward.solve_seconds)
        metrics["receiver_evaluation_seconds"][frequency_hz] = float(
            forward.receiver_evaluation_seconds
        )

    metrics["elapsed_seconds"] = float(metrics["elapsed_seconds"])
    metrics["end_to_end_seconds"] = float(
        metrics["preprocessing_seconds"] + metrics["elapsed_seconds"]
    )
    return metrics


def attach_parallel_solver_discrepancies(
    results: dict[str, dict[str, Any]],
    frequencies_hz: tuple[float, ...],
) -> None:
    """Attach explicitly named agreement diagnostics without treating gprMax as truth."""

    kress = results.get("gpr_bem_kress")
    modified = results.get("gpr_bem_mod")
    if kress is None or modified is None:
        return
    kress["mod_full_ring_relative_discrepancy"] = {}
    for frequency_hz in frequencies_hz:
        kress_field = np.asarray(kress["scattered"][frequency_hz])
        mod_field = np.asarray(modified["scattered"][frequency_hz])
        if kress_field.shape != mod_field.shape:
            raise ValueError(
                "Kress and MOD comparison fields must have identical shapes; "
                f"received {kress_field.shape} and {mod_field.shape}."
            )
        kress["mod_full_ring_relative_discrepancy"][frequency_hz] = _relative_l2(
            kress_field, mod_field
        )

    gprmax = results.get("gprmax")
    if gprmax is None:
        return
    for name in ("gpr_bem_mod", "gpr_bem_kress"):
        solver = results[name]
        solver["gprmax_index0_relative_discrepancy"] = {}
        for frequency_hz in frequencies_hz:
            solver_field = np.asarray(solver["scattered"][frequency_hz])
            gprmax_field = np.asarray(gprmax["scattered"][frequency_hz])
            if solver_field.ndim != 1 or solver_field.size < 1:
                raise ValueError(
                    f"{name} scattered field must be a nonempty vector."
                )
            if gprmax_field.shape != (1,):
                raise ValueError(
                    "The current gprMax comparison cache must contain exactly pair 0; "
                    f"received shape {gprmax_field.shape}."
                )
            solver_pair = solver_field[:1]
            gprmax_pair = gprmax_field
            solver["gprmax_index0_relative_discrepancy"][frequency_hz] = _relative_l2(
                solver_pair, gprmax_pair
            )


def assert_kress_comparison_acceptance(
    kress: Mapping[str, Any],
    modified: Mapping[str, Any],
    frequencies_hz: tuple[float, ...],
    maximum_relative_error: Mapping[float, float],
) -> None:
    """Enforce the shared semantic and physical gates used by every exporter."""

    assert kress["sampling"] == "shared_sdf_method_b"
    assert kress["fourier_bandwidth"] == 48
    assert kress["projected_samples"] == 256
    assert kress["num_samples"] == 128
    pair_count = int(kress["error_pair_count"])
    assert pair_count > 0
    assert int(kress["pair_count"]) == pair_count
    assert int(kress["num_sources"]) == pair_count
    assert int(kress["num_receivers"]) == pair_count
    assert tuple(kress["receiver_matrix_shape"]) == (pair_count, pair_count)
    assert str(kress["error_scope"]).startswith("full-ring relative L2")
    assert np.isfinite(float(kress["maximum_projected_sdf_residual"]))
    assert np.isfinite(float(kress["maximum_curve_sdf_residual"]))
    assert np.isfinite(float(kress["speed_ratio"]))
    assert float(kress["speed_ratio"]) > 0.0

    for frequency_hz in frequencies_hz:
        error = float(kress["relative_error"][frequency_hz])
        index0_error = float(kress["index0_relative_error"][frequency_hz])
        residual = float(kress["residual"][frequency_hz])
        leak = float(kress["incident_representation_leak"][frequency_hz])
        scattered = np.asarray(kress["scattered"][frequency_hz])
        assert scattered.shape == (pair_count,)
        assert np.all(np.isfinite(scattered))
        assert np.isfinite(error)
        assert np.isfinite(index0_error)
        assert np.isfinite(residual)
        assert residual < 1.0e-10
        assert np.isfinite(leak)
        threshold = maximum_relative_error.get(frequency_hz)
        if threshold is not None:
            assert error < float(threshold)
            assert error < float(modified["relative_error"][frequency_hz])


def comparison_error_scope_label(name: str, metrics: dict[str, Any]) -> str:
    """Compact table label which never conflates one-pair and ring L2 errors."""

    pair_count = metrics.get("error_pair_count", metrics.get("pair_count"))
    scope = str(metrics.get("error_scope", ""))
    if pair_count == 1 or scope.startswith("index-0") or name == "gprmax":
        return "pair-0"
    if pair_count is None:
        # Older diagnostic rows predate the explicit scope metadata.  Their
        # stored scattered vectors still identify how many paired fields enter
        # the reported L2, so use that evidence instead of crashing the table
        # formatter or inventing a one-pair label.
        scattered = metrics.get("scattered", {})
        if isinstance(scattered, Mapping) and scattered:
            first_field = np.asarray(next(iter(scattered.values())))
            if first_field.ndim == 1 and first_field.size > 0:
                pair_count = int(first_field.size)
    if pair_count is None:
        return "scope?"
    return f"L2/{int(pair_count)}"


def comparison_timing_cells(name: str, metrics: dict[str, Any]) -> tuple[str, str, str]:
    """Return preprocessing, forward-call, and end-to-end cells for text tables."""

    def cell(value: Any) -> str:
        if value is None:
            return "--"
        seconds = float(value)
        return f"{seconds:.2f}" if np.isfinite(seconds) else "--"

    preprocessing = cell(metrics.get("preprocessing_seconds"))
    if name == "gprmax":
        # The cache records the entire target/background FDTD workload, not a
        # separately instrumented linear-solver phase.
        return preprocessing, "--", cell(metrics.get("end_to_end_seconds", metrics.get("elapsed_seconds")))
    return (
        preprocessing,
        cell(metrics.get("elapsed_seconds")),
        cell(metrics.get("end_to_end_seconds")),
    )


__all__ = [
    "KressGeometryBuild",
    "KressGeometryConfig",
    "assert_kress_comparison_acceptance",
    "attach_parallel_solver_discrepancies",
    "build_kress_geometry",
    "comparison_error_scope_label",
    "comparison_timing_cells",
    "run_kress_metrics",
]
