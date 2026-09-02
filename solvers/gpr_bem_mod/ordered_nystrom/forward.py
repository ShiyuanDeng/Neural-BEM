"""Direct solve and safely separated receiver evaluation on ordered curves."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import numpy as np
from scipy.special import hankel1

from ordered_boundary import PeriodicCurve2D

from ..materials import Material
from ._kernels import validate_wavenumber
from .geometry import PeriodicCurveAdapter, adapt_periodic_curve
from .operators import MullerAssemblyConfig
from .system import OrderedTMzFrequencySystem, build_ordered_tmz_frequency_system


def _readonly(values: np.ndarray, *, dtype) -> np.ndarray:
    result = np.array(values, dtype=dtype, copy=True, order="C")
    result.setflags(write=False)
    return result


def _points(values, *, name: str) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    result = np.atleast_2d(np.asarray(values, dtype=np.float64))
    if result.ndim != 2 or result.shape[1] != 2 or result.shape[0] == 0:
        raise ValueError(f"{name} must have shape (count, 2).")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values.")
    return result


def _strengths(values, count: int) -> np.ndarray:
    result = np.atleast_1d(np.asarray(values, dtype=np.complex128))
    if result.ndim != 1:
        raise ValueError("source_strength must be scalar or one-dimensional.")
    if result.size == 1 and count > 1:
        result = np.full(count, result[0], dtype=np.complex128)
    if result.shape != (count,):
        raise ValueError("source_strength must be scalar or have one value per source.")
    if not np.all(np.isfinite(result)):
        raise ValueError("source_strength must contain only finite values.")
    return result


def _trace_matrix(values, num_nodes: int, *, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.complex128)
    if result.ndim == 1:
        result = result[None, :]
    if result.ndim != 2 or result.shape[1] != num_nodes or result.shape[0] == 0:
        raise ValueError(f"{name} must have shape (num_rhs, {num_nodes}).")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values.")
    return result


def _inside_closed_polygon(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    x = points[:, 0, None]
    y = points[:, 1, None]
    x0 = polygon[:, 0][None, :]
    y0 = polygon[:, 1][None, :]
    x1 = np.roll(polygon[:, 0], -1)[None, :]
    y1 = np.roll(polygon[:, 1], -1)[None, :]
    crosses = (y0 > y) != (y1 > y)
    denominator = np.where(np.abs(y1 - y0) > 0.0, y1 - y0, 1.0)
    intersection_x = x0 + (y - y0) * (x1 - x0) / denominator
    return np.count_nonzero(crosses & (x < intersection_x), axis=1) % 2 == 1


def _minimum_curve_distance(points: np.ndarray, curve: PeriodicCurve2D) -> float:
    starts = curve.points
    segments = np.roll(starts, -1, axis=0) - starts
    segment_squared = np.einsum("nd,nd->n", segments, segments)
    minimum = float("inf")
    for first in range(0, points.shape[0], 256):
        candidates = points[first : first + 256]
        displacement = candidates[:, None, :] - starts[None, :, :]
        numerator = np.einsum("pnd,nd->pn", displacement, segments)
        fraction = np.divide(
            numerator,
            segment_squared[None, :],
            out=np.zeros_like(numerator),
            where=segment_squared[None, :] > 0.0,
        )
        fraction = np.clip(fraction, 0.0, 1.0)
        closest = starts[None, :, :] + fraction[..., None] * segments[None, :, :]
        minimum = min(
            minimum,
            float(
                np.min(
                    np.linalg.norm(candidates[:, None, :] - closest, axis=-1)
                )
            ),
        )
    return minimum


def _validate_exterior_points(
    points: np.ndarray,
    curve: PeriodicCurve2D,
    *,
    name: str,
    minimum_clearance: float,
) -> float:
    if np.any(_inside_closed_polygon(points, curve.points)):
        raise ValueError(f"{name} must lie in the homogeneous exterior.")
    distance = _minimum_curve_distance(points, curve)
    if distance <= minimum_clearance:
        raise ValueError(
            f"{name} are too close to the boundary for ordinary receiver quadrature: "
            f"minimum {distance:.6e}, required > {minimum_clearance:.6e}."
        )
    return distance


@dataclass(frozen=True)
class OrderedSolveConfig:
    """Controls that belong to the direct solve and off-surface evaluation."""

    assembly: MullerAssemblyConfig = field(default_factory=MullerAssemblyConfig)
    compute_condition_number: bool = False
    minimum_clearance_in_weights: float = 2.0

    def __post_init__(self) -> None:
        if not isinstance(self.assembly, MullerAssemblyConfig):
            raise TypeError("assembly must be a MullerAssemblyConfig object.")
        if not isinstance(self.compute_condition_number, (bool, np.bool_)):
            raise TypeError("compute_condition_number must be boolean.")
        if isinstance(self.minimum_clearance_in_weights, (bool, np.bool_)):
            raise TypeError(
                "minimum_clearance_in_weights must be a real number, not bool."
            )
        clearance = float(self.minimum_clearance_in_weights)
        if not np.isfinite(clearance) or clearance < 0.0:
            raise ValueError("minimum_clearance_in_weights must be finite and non-negative.")
        object.__setattr__(
            self, "compute_condition_number", bool(self.compute_condition_number)
        )
        object.__setattr__(self, "minimum_clearance_in_weights", clearance)


@dataclass(frozen=True)
class ExteriorRepresentationResult:
    """Separated single-, double-, and combined exterior potentials."""

    single_layer: np.ndarray
    double_layer: np.ndarray
    scattered: np.ndarray
    minimum_receiver_distance: float
    evaluation_seconds: float


def _incident_trace_from_adapter(
    adapter: PeriodicCurveAdapter,
    sources: np.ndarray,
    strengths: np.ndarray,
    wave: complex,
) -> tuple[np.ndarray, np.ndarray]:
    displacement = adapter.points[None, :, :] - sources[:, None, :]
    distance = np.linalg.norm(displacement, axis=-1)
    if np.any(distance <= 0.0):
        raise ValueError("source_points must not lie on a boundary node.")
    projection = np.einsum("snd,nd->sn", displacement, adapter.normals) / distance
    dirichlet = strengths[:, None] * 0.25j * hankel1(0, wave * distance)
    neumann = (
        -strengths[:, None]
        * 0.25j
        * wave
        * hankel1(1, wave * distance)
        * projection
    )
    return (
        _readonly(dirichlet, dtype=np.complex128),
        _readonly(neumann, dtype=np.complex128),
    )


def ordered_incident_trace_on_boundary(
    curve: PeriodicCurve2D,
    source_points,
    k_exterior: complex,
    source_strength=1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate positive line-source Dirichlet and outward-normal traces.

    Arrays have shape ``(num_sources, num_nodes)`` and contain unweighted
    nodal values.
    """

    adapter = adapt_periodic_curve(curve)
    sources = _points(source_points, name="source_points")
    strengths = _strengths(source_strength, sources.shape[0])
    wave = validate_wavenumber(k_exterior, name="k_exterior")
    return _incident_trace_from_adapter(adapter, sources, strengths, wave)


def _evaluate_exterior_representation_from_adapter(
    adapter: PeriodicCurveAdapter,
    receivers: np.ndarray,
    dirichlet: np.ndarray,
    neumann: np.ndarray,
    wave: complex,
    *,
    minimum_receiver_distance: float,
) -> ExteriorRepresentationResult:
    started = perf_counter()
    displacement = receivers[:, None, :] - adapter.points[None, :, :]
    distance = np.linalg.norm(displacement, axis=-1)
    projection = np.einsum("rnd,nd->rn", displacement, adapter.normals) / distance
    green = 0.25j * hankel1(0, wave * distance)
    green_normal = 0.25j * wave * hankel1(1, wave * distance) * projection
    single = np.einsum(
        "rn,sn,n->sr", green, neumann, adapter.arc_length_weights, optimize=True
    )
    double = np.einsum(
        "rn,sn,n->sr",
        green_normal,
        dirichlet,
        adapter.arc_length_weights,
        optimize=True,
    )
    scattered = double - single
    return ExteriorRepresentationResult(
        single_layer=_readonly(single, dtype=np.complex128),
        double_layer=_readonly(double, dtype=np.complex128),
        scattered=_readonly(scattered, dtype=np.complex128),
        minimum_receiver_distance=float(minimum_receiver_distance),
        evaluation_seconds=float(perf_counter() - started),
    )


def evaluate_exterior_representation(
    curve: PeriodicCurve2D,
    receiver_points,
    dirichlet_trace,
    neumann_trace,
    k_exterior: complex,
    *,
    minimum_clearance: float = 0.0,
) -> ExteriorRepresentationResult:
    """Evaluate ``D u_D-S u_N`` at safely separated exterior receivers."""

    adapter = adapt_periodic_curve(curve)
    receivers = _points(receiver_points, name="receiver_points")
    dirichlet = _trace_matrix(
        dirichlet_trace, adapter.num_nodes, name="dirichlet_trace"
    )
    neumann = _trace_matrix(
        neumann_trace, adapter.num_nodes, name="neumann_trace"
    )
    if dirichlet.shape != neumann.shape:
        raise ValueError("dirichlet_trace and neumann_trace must have the same shape.")
    if isinstance(minimum_clearance, (bool, np.bool_)):
        raise TypeError("minimum_clearance must be a real number, not bool.")
    clearance = float(minimum_clearance)
    if not np.isfinite(clearance) or clearance < 0.0:
        raise ValueError("minimum_clearance must be finite and non-negative.")
    minimum_distance = _validate_exterior_points(
        receivers,
        curve,
        name="receiver_points",
        minimum_clearance=clearance,
    )
    wave = validate_wavenumber(k_exterior, name="k_exterior")
    return _evaluate_exterior_representation_from_adapter(
        adapter,
        receivers,
        dirichlet,
        neumann,
        wave,
        minimum_receiver_distance=minimum_distance,
    )


@dataclass(frozen=True)
class OrderedTMzForwardResult:
    """Auditable direct solution for all source/receiver combinations."""

    system: OrderedTMzFrequencySystem
    source_points: np.ndarray
    receiver_points: np.ndarray
    source_strengths: np.ndarray
    right_hand_side: np.ndarray
    solution: np.ndarray
    dirichlet_incident: np.ndarray
    neumann_incident: np.ndarray
    dirichlet_total: np.ndarray
    neumann_total: np.ndarray
    incident_receiver: np.ndarray
    single_receiver: np.ndarray
    double_receiver: np.ndarray
    scattered_receiver: np.ndarray
    total_receiver: np.ndarray
    linear_system_relative_residual: float
    per_source_relative_residual: np.ndarray
    incident_representation_leak: float
    solve_seconds: float
    receiver_evaluation_seconds: float
    total_seconds: float
    diagnostics: Mapping[str, object]


def solve_ordered_tmz_total_field_batch(
    curve: PeriodicCurve2D,
    source_points,
    receiver_points,
    angular_frequency: float,
    source_strength=1.0,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    config: OrderedSolveConfig | None = None,
) -> OrderedTMzForwardResult:
    """Build and directly solve the ordered Müller system.

    Receiver arrays have shape ``(num_sources, num_receivers)``.  This is a
    full multi-right-hand-side evaluation, not an implicit pairing convention.
    """

    total_started = perf_counter()
    settings = OrderedSolveConfig() if config is None else config
    if not isinstance(settings, OrderedSolveConfig):
        raise TypeError("config must be an OrderedSolveConfig object.")
    if not isinstance(curve, PeriodicCurve2D):
        raise TypeError("curve must be an ordered_boundary.PeriodicCurve2D object.")
    sources = _points(source_points, name="source_points")
    receivers = _points(receiver_points, name="receiver_points")
    strengths = _strengths(source_strength, sources.shape[0])
    clearance = settings.minimum_clearance_in_weights * float(
        np.max(curve.arc_length_weights)
    )
    minimum_source_distance = _validate_exterior_points(
        sources,
        curve,
        name="source_points",
        minimum_clearance=clearance,
    )
    minimum_receiver_distance = _validate_exterior_points(
        receivers,
        curve,
        name="receiver_points",
        minimum_clearance=clearance,
    )
    source_receiver_distance = np.linalg.norm(
        receivers[None, :, :] - sources[:, None, :], axis=-1
    )
    if np.any(source_receiver_distance <= 0.0):
        raise ValueError("source_points and receiver_points must be distinct.")
    system = build_ordered_tmz_frequency_system(
        curve,
        angular_frequency,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
        config=settings.assembly,
        compute_condition_number=settings.compute_condition_number,
    )
    adapter = system.difference_blocks.geometry_adapter
    dirichlet_incident, neumann_incident = _incident_trace_from_adapter(
        adapter,
        sources,
        strengths,
        system.k_exterior,
    )
    right_hand_side = np.concatenate(
        (dirichlet_incident, neumann_incident), axis=1
    ).T

    solve_started = perf_counter()
    solution = np.linalg.solve(system.system_matrix, right_hand_side)
    solve_seconds = float(perf_counter() - solve_started)
    residual_matrix = system.system_matrix @ solution - right_hand_side
    right_norms = np.linalg.norm(right_hand_side, axis=0)
    residual_norms = np.linalg.norm(residual_matrix, axis=0)
    per_source = np.divide(
        residual_norms,
        right_norms,
        out=np.where(residual_norms == 0.0, 0.0, np.inf),
        where=right_norms > 0.0,
    )
    aggregate_denominator = float(np.linalg.norm(right_hand_side))
    aggregate_residual = float(np.linalg.norm(residual_matrix))
    relative_residual = (
        aggregate_residual / aggregate_denominator
        if aggregate_denominator > 0.0
        else (0.0 if aggregate_residual == 0.0 else float("inf"))
    )
    count = system.num_nodes
    dirichlet_total = solution[:count].T
    neumann_total = solution[count:].T

    receiver_started = perf_counter()
    representation = _evaluate_exterior_representation_from_adapter(
        adapter,
        receivers,
        dirichlet_total,
        neumann_total,
        system.k_exterior,
        minimum_receiver_distance=minimum_receiver_distance,
    )
    leak = _evaluate_exterior_representation_from_adapter(
        adapter,
        receivers,
        dirichlet_incident,
        neumann_incident,
        system.k_exterior,
        minimum_receiver_distance=minimum_receiver_distance,
    )
    incident_receiver = (
        strengths[:, None]
        * 0.25j
        * hankel1(0, system.k_exterior * source_receiver_distance)
    )
    total_receiver = incident_receiver + representation.scattered
    receiver_seconds = float(perf_counter() - receiver_started)
    leak_scale = max(float(np.max(np.abs(incident_receiver))), np.finfo(float).tiny)
    incident_leak = float(np.max(np.abs(leak.scattered)) / leak_scale)
    total_seconds = float(perf_counter() - total_started)
    diagnostics = MappingProxyType(
        {
            "solve_form": "direct_unsquared",
            "num_sources": int(sources.shape[0]),
            "num_receivers": int(receivers.shape[0]),
            "minimum_source_distance": minimum_source_distance,
            "minimum_receiver_distance": representation.minimum_receiver_distance,
            "minimum_clearance_required": clearance,
            "receiver_quadrature": "ordinary_periodic_trapezoid",
            "close_evaluation": False,
        }
    )
    return OrderedTMzForwardResult(
        system=system,
        source_points=_readonly(sources, dtype=np.float64),
        receiver_points=_readonly(receivers, dtype=np.float64),
        source_strengths=_readonly(strengths, dtype=np.complex128),
        right_hand_side=_readonly(right_hand_side, dtype=np.complex128),
        solution=_readonly(solution, dtype=np.complex128),
        dirichlet_incident=dirichlet_incident,
        neumann_incident=neumann_incident,
        dirichlet_total=_readonly(dirichlet_total, dtype=np.complex128),
        neumann_total=_readonly(neumann_total, dtype=np.complex128),
        incident_receiver=_readonly(incident_receiver, dtype=np.complex128),
        single_receiver=representation.single_layer,
        double_receiver=representation.double_layer,
        scattered_receiver=representation.scattered,
        total_receiver=_readonly(total_receiver, dtype=np.complex128),
        linear_system_relative_residual=relative_residual,
        per_source_relative_residual=_readonly(per_source, dtype=np.float64),
        incident_representation_leak=incident_leak,
        solve_seconds=solve_seconds,
        receiver_evaluation_seconds=receiver_seconds,
        total_seconds=total_seconds,
        diagnostics=diagnostics,
    )


@dataclass(frozen=True)
class OrderedTMzMultiFrequencyForwardResult:
    angular_frequencies: np.ndarray
    total_frequency_response: np.ndarray
    scattered_frequency_response: np.ndarray
    forwards: tuple[OrderedTMzForwardResult, ...]


def solve_ordered_tmz_frequency_response(
    curve: PeriodicCurve2D,
    source_points,
    receiver_points,
    angular_frequencies,
    source_strength=1.0,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    config: OrderedSolveConfig | None = None,
) -> OrderedTMzMultiFrequencyForwardResult:
    """Solve independent frequencies with explicit source/frequency/receiver axes.

    Returned field arrays have shape ``(num_sources, num_frequencies,
    num_receivers)``. ``source_strength`` is scalar or one value per source and
    is reused at every frequency; frequency-dependent spectra belong in a
    separate signal-processing step.
    """

    if np.iscomplexobj(angular_frequencies):
        raise ValueError("angular_frequencies must be real-valued.")
    frequencies = np.atleast_1d(np.asarray(angular_frequencies, dtype=np.float64))
    if (
        frequencies.ndim != 1
        or frequencies.size == 0
        or not np.all(np.isfinite(frequencies))
    ):
        raise ValueError("angular_frequencies must be a finite one-dimensional array.")
    if np.any(frequencies <= 0.0):
        raise ValueError("angular_frequencies must be positive.")
    forwards = tuple(
        solve_ordered_tmz_total_field_batch(
            curve,
            source_points,
            receiver_points,
            float(omega),
            source_strength,
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            config=config,
        )
        for omega in frequencies
    )
    total = np.stack([result.total_receiver for result in forwards], axis=1)
    scattered = np.stack(
        [result.scattered_receiver for result in forwards], axis=1
    )
    return OrderedTMzMultiFrequencyForwardResult(
        angular_frequencies=_readonly(frequencies, dtype=np.float64),
        total_frequency_response=_readonly(total, dtype=np.complex128),
        scattered_frequency_response=_readonly(scattered, dtype=np.complex128),
        forwards=forwards,
    )


__all__ = [
    "ExteriorRepresentationResult",
    "OrderedSolveConfig",
    "OrderedTMzForwardResult",
    "OrderedTMzMultiFrequencyForwardResult",
    "evaluate_exterior_representation",
    "ordered_incident_trace_on_boundary",
    "solve_ordered_tmz_frequency_response",
    "solve_ordered_tmz_total_field_batch",
]
