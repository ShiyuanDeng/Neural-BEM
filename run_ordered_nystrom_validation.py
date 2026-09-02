#!/usr/bin/env python3
"""Reproducible convergence and runtime evidence for ordered Nyström.

This opt-in driver accepts continuous analytic or frozen Fourier geometry,
discretizes it as ``PeriodicCurve2D`` at every requested even node count, and
calls only the explicit ``gpr_bem_mod.ordered_nystrom`` API. Circle fields are
compared with the analytic Mie series; all other shapes use the independent
high-resolution ``nystrom_ref`` implementation as a frozen numerical reference.

Only scalar metrics and small tables are written. Dense operators, solutions,
and receiver arrays remain transient and are never persisted.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import subprocess
import sys
from time import perf_counter
from typing import Any, Callable, Sequence


# Set reproducible timing defaults before NumPy/SciPy initialize a BLAS runtime.
# Explicit caller choices still win.
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_variable, "1")

import numpy as np
from scipy.special import h1vp, hankel1, jv, jvp


REPOSITORY_ROOT = Path(__file__).resolve().parent
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
if str(SOLVERS_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVERS_ROOT))

import config.circle_config as physical_config  # noqa: E402
import gpr_bem_mod  # noqa: E402
from gpr_bem_mod.ordered_nystrom import (  # noqa: E402
    MullerAssemblyConfig,
    OrderedSolveConfig,
    solve_ordered_tmz_total_field_batch,
)
from nystrom_ref import build_curve as build_reference_curve  # noqa: E402
from nystrom_ref import solve_transmission as solve_reference_transmission  # noqa: E402
from ordered_boundary import (  # noqa: E402
    PeriodicParameterization2D,
    circle,
    ellipse,
    fourier_curve,
    star,
)


TWO_PI = 2.0 * np.pi
CENTER = (
    float(physical_config.TARGET_CENTER_X),
    float(physical_config.TARGET_CENTER_Y),
)
RADIUS = float(physical_config.TARGET_RADIUS)


@dataclass(frozen=True)
class ValidationPreset:
    nodes: tuple[int, ...]
    frequencies_ghz: tuple[float, ...]
    reference_nodes: int
    num_pairs: int


PRESETS = {
    "quick": ValidationPreset(
        nodes=(64, 128, 256),
        frequencies_ghz=(0.5, 2.5, 8.0),
        reference_nodes=512,
        num_pairs=4,
    ),
    "full": ValidationPreset(
        nodes=(32, 64, 128, 256),
        frequencies_ghz=(0.5, 1.5, 2.5, 4.0, 6.0, 8.0),
        reference_nodes=512,
        num_pairs=12,
    ),
}


@dataclass(frozen=True)
class CurveCase:
    name: str
    parameterization: PeriodicParameterization2D
    source_kind: str
    definition: str
    reference_kind: str
    frozen_path: Path | None = None
    frozen_sha256: str | None = None
    fourier_bandwidth: int | None = None
    normalization_scale: float | None = None
    original_center: tuple[float, float] | None = None
    original_mean_radius: float | None = None
    target_mean_radius: float | None = None


@dataclass(frozen=True)
class ReferenceResult:
    field: np.ndarray
    dirichlet_trace: np.ndarray | None
    neumann_trace: np.ndarray | None
    reference_kind: str
    num_nodes: int | None
    seconds: float
    relative_residual: float | None
    incident_consistency: float | None


def _comma_tokens(value: str, *, label: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in str(value).split(","))
    if not tokens or any(not token for token in tokens):
        raise argparse.ArgumentTypeError(
            f"{label} must be a non-empty comma-separated list."
        )
    if len(set(tokens)) != len(tokens):
        raise argparse.ArgumentTypeError(f"{label} must not contain duplicates.")
    return tokens


def _even_nodes(value: str) -> tuple[int, ...]:
    tokens = _comma_tokens(value, label="nodes")
    try:
        nodes = tuple(int(token) for token in tokens)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("nodes must contain integers.") from exc
    if any(node < 8 or node % 2 for node in nodes):
        raise argparse.ArgumentTypeError("every node count must be even and at least 8.")
    return tuple(sorted(nodes))


def _frequencies(value: str) -> tuple[float, ...]:
    tokens = _comma_tokens(value, label="frequencies")
    try:
        frequencies = tuple(float(token) for token in tokens)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "frequencies must contain numbers in GHz."
        ) from exc
    if any(not np.isfinite(item) or item <= 0.0 for item in frequencies):
        raise argparse.ArgumentTypeError("every frequency must be finite and positive.")
    return tuple(sorted(frequencies))


def _shape_names(value: str) -> tuple[str, ...]:
    names = tuple(token.lower() for token in _comma_tokens(value, label="shapes"))
    if names == ("none",):
        return ()
    if "none" in names:
        raise argparse.ArgumentTypeError(
            "'none' must be the only --shapes value; add curves with --curve-npz."
        )
    valid = {"circle", "ellipse", "star"}
    unknown = sorted(set(names) - valid)
    if unknown:
        raise argparse.ArgumentTypeError(
            "unknown shape(s): " + ", ".join(unknown) + "; choose circle, ellipse, star"
        )
    return names


def _positive_integer(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer.") from exc
    if result < 1:
        raise argparse.ArgumentTypeError("value must be positive.")
    return result


def _positive_float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be numeric.") from exc
    if not np.isfinite(result) or result <= 0.0:
        raise argparse.ArgumentTypeError("value must be finite and positive.")
    return result


def _safe_run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise argparse.ArgumentTypeError(
            "run-id may contain only letters, digits, '.', '_' and '-'."
        )
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the isolated PeriodicCurve2D Müller/Kress candidate on "
            "circle, ellipse, and smooth-star curves."
        )
    )
    parser.add_argument("--preset", choices=tuple(PRESETS), default="quick")
    parser.add_argument(
        "--nodes",
        type=_even_nodes,
        help="Comma-separated even node counts; overrides the preset.",
    )
    parser.add_argument(
        "--frequencies-ghz",
        type=_frequencies,
        help="Comma-separated positive frequencies in GHz; overrides the preset.",
    )
    parser.add_argument(
        "--shapes",
        type=_shape_names,
        default=("circle", "ellipse", "star"),
        help=(
            "Comma-separated analytic shapes, or 'none' for a frozen-curve-only "
            "run (default: circle,ellipse,star)."
        ),
    )
    parser.add_argument(
        "--curve-npz",
        type=Path,
        action="append",
        default=[],
        help=(
            "Append a frozen Fourier curve containing cosine_coefficients and "
            "sine_coefficients. Repeat for multiple files."
        ),
    )
    parser.add_argument(
        "--frozen-target-mean-radius-m",
        type=_positive_float,
        default=RADIUS,
        help=(
            "Uniformly scale frozen dimensionless curves about mode zero and "
            "translate them to the benchmark center (default: 0.05 m)."
        ),
    )
    parser.add_argument(
        "--reference-nodes",
        type=_positive_integer,
        help="Even high-resolution nystrom_ref node count for noncircles.",
    )
    parser.add_argument(
        "--num-pairs",
        type=_positive_integer,
        help="Number of sources and receivers on the exterior scan ring.",
    )
    parser.add_argument(
        "--timing-repeats",
        type=_positive_integer,
        default=1,
        help="Repeat each candidate solve and report median timings (default: 1).",
    )
    parser.add_argument("--target-chunk-size", type=_positive_integer, default=64)
    parser.add_argument("--near-argument", type=_positive_float, default=0.75)
    parser.add_argument("--series-terms", type=_positive_integer, default=24)
    parser.add_argument("--receiver-gate", type=_positive_float, default=1.0e-6)
    parser.add_argument("--trace-gate", type=_positive_float, default=1.0e-6)
    parser.add_argument("--residual-gate", type=_positive_float, default=1.0e-10)
    parser.add_argument("--leak-gate", type=_positive_float, default=1.0e-10)
    parser.add_argument("--overlap-gate", type=_positive_float, default=2.0e-11)
    parser.add_argument("--circle-block-gate", type=_positive_float, default=1.0e-8)
    parser.add_argument(
        "--mixed-floor-fraction",
        type=_positive_float,
        default=0.05,
        help="Broadband reference-norm floor used by the mixed receiver error.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPOSITORY_ROOT / "results" / "ordered_boundary_nystrom",
    )
    parser.add_argument(
        "--run-id",
        type=_safe_run_id,
        help="Unique output directory name; defaults to preset-UTC timestamp.",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Return nonzero when any configured largest-N check fails.",
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _analytic_cases(names: Sequence[str]) -> list[CurveCase]:
    cases: list[CurveCase] = []
    for name in names:
        if name == "circle":
            parameterization = circle(
                CENTER,
                RADIUS,
                component_id="validation-circle",
            )
            definition = f"center={CENTER}, radius={RADIUS:.17g} m"
            reference_kind = "analytic_mie_series"
        elif name == "ellipse":
            parameterization = ellipse(
                CENTER,
                1.4 * RADIUS,
                RADIUS / 1.4,
                rotation=0.31,
                component_id="validation-ellipse",
            )
            definition = (
                f"center={CENTER}, semi_axes=({1.4 * RADIUS:.17g},"
                f" {RADIUS / 1.4:.17g}) m, rotation=0.31 rad"
            )
            reference_kind = "independent_nystrom_ref_frozen_high_N"
        else:
            parameterization = star(
                CENTER,
                RADIUS,
                0.25,
                5,
                rotation=0.19,
                component_id="validation-star",
            )
            definition = (
                f"center={CENTER}, mean_radius={RADIUS:.17g} m, "
                "relative_amplitude=0.25, lobes=5, rotation=0.19 rad"
            )
            reference_kind = "independent_nystrom_ref_frozen_high_N"
        cases.append(
            CurveCase(
                name=name,
                parameterization=parameterization,
                source_kind="analytic",
                definition=definition,
                reference_kind=reference_kind,
            )
        )
    return cases


def _unique_case_name(path: Path, existing: set[str]) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-.")
    base = f"frozen-{stem or 'curve'}"
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _load_frozen_case(
    path: Path,
    existing: set[str],
    target_mean_radius: float,
) -> CurveCase:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"frozen curve does not exist: {resolved}")
    with np.load(resolved, allow_pickle=False) as archive:
        required = {"cosine_coefficients", "sine_coefficients"}
        missing = sorted(required - set(archive.files))
        if missing:
            raise ValueError(
                f"{resolved} is missing frozen Fourier arrays: {', '.join(missing)}"
            )
        raw_cosine = np.array(
            archive["cosine_coefficients"], dtype=np.float64, copy=True
        )
        raw_sine = np.array(
            archive["sine_coefficients"], dtype=np.float64, copy=True
        )
        stored_parameters = (
            np.array(archive["parameters"], dtype=np.float64, copy=True)
            if "parameters" in archive.files
            else None
        )
        stored_points = (
            np.array(archive["points"], dtype=np.float64, copy=True)
            if "points" in archive.files
            else None
        )
    name = _unique_case_name(resolved, existing)
    raw_parameterization = fourier_curve(
        raw_cosine,
        raw_sine,
        component_id=f"{name}-raw",
        name=f"{name}-raw",
    )
    if (stored_parameters is None) != (stored_points is None):
        raise ValueError(
            f"{resolved} must contain both parameters and points when either is present."
        )
    if stored_parameters is not None:
        reconstructed = raw_parameterization.evaluate(stored_parameters).points
        scale = max(
            float(np.max(np.abs(stored_points))),
            np.finfo(float).tiny,
        )
        mismatch = float(np.max(np.abs(reconstructed - stored_points)) / scale)
        if mismatch > 5.0e-10:
            raise ValueError(
                f"{resolved} coefficients do not reconstruct stored points "
                f"(scaled max mismatch {mismatch:.3e})."
            )

    original_center_array = np.asarray(raw_cosine[0], dtype=np.float64)
    dense_parameters = TWO_PI * np.arange(4096, dtype=np.float64) / 4096
    dense_points = raw_parameterization.evaluate(dense_parameters).points
    radii = np.linalg.norm(dense_points - original_center_array, axis=1)
    original_mean_radius = float(np.mean(radii))
    if not np.isfinite(original_mean_radius) or original_mean_radius <= 0.0:
        raise ValueError(f"{resolved} has no positive finite mean radius.")
    normalization_scale = float(target_mean_radius / original_mean_radius)
    cosine = raw_cosine.copy()
    sine = raw_sine.copy()
    cosine[0] = np.asarray(CENTER)
    cosine[1:] *= normalization_scale
    sine[1:] *= normalization_scale
    sine[0] = 0.0
    parameterization = fourier_curve(
        cosine,
        sine,
        component_id=name,
        name=name,
    )
    bandwidth = int(cosine.shape[0] - 1)
    return CurveCase(
        name=name,
        parameterization=parameterization,
        source_kind="frozen_fourier_npz_normalized",
        definition=(
            f"Fourier bandwidth={bandwidth}; source mean radius "
            f"{original_mean_radius:.17g}; uniformly scaled by "
            f"{normalization_scale:.17g} about mode zero to mean radius "
            f"{target_mean_radius:.17g} m and translated to center={CENTER}; "
            f"source={resolved}"
        ),
        reference_kind="independent_nystrom_ref_frozen_high_N",
        frozen_path=resolved,
        frozen_sha256=_sha256(resolved),
        fourier_bandwidth=bandwidth,
        normalization_scale=normalization_scale,
        original_center=tuple(float(value) for value in original_center_array),
        original_mean_radius=original_mean_radius,
        target_mean_radius=float(target_mean_radius),
    )


def _scan_points(num_pairs: int) -> tuple[np.ndarray, np.ndarray]:
    angles = TWO_PI * np.arange(num_pairs, dtype=np.float64) / num_pairs
    sources = np.asarray(CENTER) + 0.27 * np.column_stack(
        (np.cos(angles - 0.06), np.sin(angles - 0.06))
    )
    receivers = np.asarray(CENTER) + 0.27 * np.column_stack(
        (np.cos(angles + 0.06), np.sin(angles + 0.06))
    )
    return sources, receivers


def _reference_parameterization(
    parameterization: PeriodicParameterization2D,
) -> Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]:
    """Adapt a producer to nystrom_ref's independent canonical-theta API."""

    def evaluate(theta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        theta_values = np.asarray(theta, dtype=np.float64)
        native = parameterization.parameter_origin + (
            parameterization.period * theta_values / TWO_PI
        )
        values = parameterization.evaluate(native, wrap=False)
        native_per_theta = parameterization.period / TWO_PI
        return values.points, native_per_theta * values.first_derivatives

    return evaluate


def _periodic_resample(values: np.ndarray, num_nodes: int) -> np.ndarray:
    """Evaluate periodic nodal data on a new endpoint-free uniform grid.

    The normal preset ladders are nested, in which case exact node selection
    avoids introducing an interpolation step.  The Fourier path keeps custom
    CLI node ladders usable without refitting the reference geometry.
    """

    samples = np.asarray(values, dtype=np.complex128)
    if samples.ndim != 2 or samples.shape[1] < 2:
        raise ValueError("reference trace samples must have shape (sources, nodes).")
    source_nodes = samples.shape[1]
    if source_nodes % num_nodes == 0:
        return np.array(samples[:, :: source_nodes // num_nodes], copy=True)

    coefficients = np.fft.fft(samples, axis=1) / source_nodes
    modes = np.fft.fftfreq(source_nodes, d=1.0 / source_nodes)
    target_theta = TWO_PI * np.arange(num_nodes, dtype=np.float64) / num_nodes
    basis = np.exp(1j * modes[:, None] * target_theta[None, :])
    return np.asarray(coefficients @ basis, dtype=np.complex128)


def _analytic_circle_traces(
    theta: np.ndarray,
    sources: np.ndarray,
    strengths: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
) -> tuple[np.ndarray, np.ndarray]:
    """Return exact total traces from the penetrable-cylinder Mie series."""

    modes = gpr_bem_mod.cylinder_series_mode_numbers(
        k_exterior,
        k_interior,
        RADIUS,
    )
    ratio = gpr_bem_mod.penetrable_cylinder_scattering_coefficient_ratio(
        modes,
        k_exterior,
        k_interior,
        RADIUS,
    )
    exterior_argument = k_exterior * RADIUS
    dirichlet_radial = (
        jv(modes, exterior_argument)
        + ratio * hankel1(modes, exterior_argument)
    )
    neumann_radial = k_exterior * (
        jvp(modes, exterior_argument)
        + ratio * h1vp(modes, exterior_argument)
    )
    dirichlet = np.empty((sources.shape[0], theta.size), dtype=np.complex128)
    neumann = np.empty_like(dirichlet)
    for source_index, source in enumerate(sources):
        source_delta = source - np.asarray(CENTER)
        source_radius = float(np.linalg.norm(source_delta))
        source_angle = float(np.arctan2(source_delta[1], source_delta[0]))
        incident_modes = hankel1(modes, k_exterior * source_radius)
        phase = np.exp(1j * np.outer(theta - source_angle, modes))
        common = 0.25j * strengths[source_index] * incident_modes
        dirichlet[source_index] = phase @ (common * dirichlet_radial)
        neumann[source_index] = phase @ (common * neumann_radial)
    return dirichlet, neumann


def _compute_reference(
    case: CurveCase,
    frequency_hz: float,
    sources: np.ndarray,
    receivers: np.ndarray,
    reference_nodes: int,
    exterior: gpr_bem_mod.Material,
    interior: gpr_bem_mod.Material,
) -> ReferenceResult:
    angular_frequency = TWO_PI * frequency_hz
    k_exterior = complex(
        exterior.wavenumber(
            angular_frequency,
            physical_config.EPS0,
            physical_config.MU0,
        )
    )
    k_interior = complex(
        interior.wavenumber(
            angular_frequency,
            physical_config.EPS0,
            physical_config.MU0,
        )
    )
    started = perf_counter()
    if case.name == "circle" and case.source_kind == "analytic":
        num_sources = sources.shape[0]
        num_receivers = receivers.shape[0]
        paired_sources = np.repeat(sources, num_receivers, axis=0)
        paired_receivers = np.tile(receivers, (num_sources, 1))
        field = gpr_bem_mod.penetrable_cylinder_scattered_field(
            paired_receivers,
            paired_sources,
            k_exterior=k_exterior,
            k_interior=k_interior,
            radius=RADIUS,
            center=CENTER,
        ).reshape(num_sources, num_receivers)
        return ReferenceResult(
            field=np.asarray(field, dtype=np.complex128),
            dirichlet_trace=None,
            neumann_trace=None,
            reference_kind=case.reference_kind,
            num_nodes=None,
            seconds=float(perf_counter() - started),
            relative_residual=None,
            incident_consistency=None,
        )

    reference_curve = build_reference_curve(
        _reference_parameterization(case.parameterization),
        reference_nodes,
        name=f"{case.name}-reference-{reference_nodes}",
    )
    solution = solve_reference_transmission(
        reference_curve,
        sources,
        receivers,
        k_exterior,
        k_interior,
        condition_number=False,
    )
    return ReferenceResult(
        field=np.asarray(solution.scattered, dtype=np.complex128),
        dirichlet_trace=np.asarray(
            solution.dirichlet_trace.T,
            dtype=np.complex128,
        ),
        neumann_trace=np.asarray(
            solution.neumann_trace.T,
            dtype=np.complex128,
        ),
        reference_kind=case.reference_kind,
        num_nodes=reference_nodes,
        seconds=float(perf_counter() - started),
        relative_residual=float(solution.relative_residual),
        incident_consistency=float(solution.incident_consistency),
    )


def _circle_eigenvalues(
    mode: int,
    k_exterior: complex,
    k_interior: complex,
) -> dict[str, complex]:
    order = abs(int(mode))
    exterior_argument = k_exterior * RADIUS
    interior_argument = k_interior * RADIUS
    common = 0.5j * np.pi * RADIUS
    return {
        "delta_v": common
        * (
            jv(order, exterior_argument) * hankel1(order, exterior_argument)
            - jv(order, interior_argument) * hankel1(order, interior_argument)
        ),
        "delta_k": common
        * (
            k_exterior
            * jvp(order, exterior_argument)
            * hankel1(order, exterior_argument)
            - k_interior
            * jvp(order, interior_argument)
            * hankel1(order, interior_argument)
        ),
        "delta_kp": common
        * (
            k_exterior
            * jvp(order, exterior_argument)
            * hankel1(order, exterior_argument)
            - k_interior
            * jvp(order, interior_argument)
            * hankel1(order, interior_argument)
        ),
        "delta_t": common
        * (
            k_exterior**2
            * jvp(order, exterior_argument)
            * h1vp(order, exterior_argument)
            - k_interior**2
            * jvp(order, interior_argument)
            * h1vp(order, interior_argument)
        ),
    }


def _circle_block_errors(forward: Any) -> dict[str, float]:
    blocks = forward.system.difference_blocks
    count = forward.system.num_nodes
    maxima = {name: 0.0 for name in ("delta_v", "delta_k", "delta_kp", "delta_t")}
    scales = {
        "delta_v": RADIUS,
        "delta_k": 1.0,
        "delta_kp": 1.0,
        "delta_t": 1.0 / RADIUS,
    }
    for mode in (0, 1, 3, 7):
        if mode >= count // 2:
            continue
        density = np.exp(1j * mode * forward.system.geometry.parameters)
        eigenvalues = _circle_eigenvalues(
            mode,
            forward.system.k_exterior,
            forward.system.k_interior,
        )
        for name, eigenvalue in eigenvalues.items():
            observed = getattr(blocks, name) @ density
            error = (
                float(np.linalg.norm(observed - eigenvalue * density))
                / math.sqrt(count)
                / scales[name]
            )
            maxima[name] = max(maxima[name], error)
    return maxima


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(float(value) for value in values))


def _candidate_row(
    case: CurveCase,
    num_nodes: int,
    frequency_hz: float,
    reference: ReferenceResult,
    reference_norm_floor: float,
    sources: np.ndarray,
    receivers: np.ndarray,
    exterior: gpr_bem_mod.Material,
    interior: gpr_bem_mod.Material,
    assembly_config: MullerAssemblyConfig,
    timing_repeats: int,
) -> tuple[dict[str, Any], np.ndarray]:
    curve = case.parameterization.discretize(num_nodes, require_even=True)
    solve_config = OrderedSolveConfig(
        assembly=assembly_config,
        compute_condition_number=False,
    )
    timing_samples: dict[str, list[float]] = {
        name: []
        for name in (
            "block_build_seconds",
            "matrix_composition_seconds",
            "system_assembly_seconds",
            "condition_seconds",
            "solve_seconds",
            "receiver_seconds",
            "forward_total_seconds",
            "measured_total_seconds",
        )
    }
    condition_numbers: list[float] = []
    forward = None
    for _ in range(timing_repeats):
        measured_started = perf_counter()
        forward = solve_ordered_tmz_total_field_batch(
            curve,
            sources,
            receivers,
            TWO_PI * frequency_hz,
            exterior=exterior,
            interior=interior,
            eps0=physical_config.EPS0,
            mu0=physical_config.MU0,
            config=solve_config,
        )
        condition_started = perf_counter()
        condition_number = float(np.linalg.cond(forward.system.system_matrix))
        condition_seconds = float(perf_counter() - condition_started)
        measured_total = float(perf_counter() - measured_started)
        timings = forward.system.diagnostics["timings_seconds"]
        timing_samples["block_build_seconds"].append(
            forward.system.difference_blocks.build_seconds
        )
        timing_samples["matrix_composition_seconds"].append(
            float(timings["matrix_composition"])
        )
        timing_samples["system_assembly_seconds"].append(
            forward.system.assembly_seconds
        )
        timing_samples["condition_seconds"].append(condition_seconds)
        timing_samples["solve_seconds"].append(forward.solve_seconds)
        timing_samples["receiver_seconds"].append(
            forward.receiver_evaluation_seconds
        )
        timing_samples["forward_total_seconds"].append(forward.total_seconds)
        timing_samples["measured_total_seconds"].append(measured_total)
        condition_numbers.append(condition_number)
    assert forward is not None

    observed = np.asarray(forward.scattered_receiver, dtype=np.complex128)
    error = observed - reference.field
    reference_norm = float(np.linalg.norm(reference.field))
    observed_norm = float(np.linalg.norm(observed))
    absolute_error = float(np.linalg.norm(error))
    relative_error = absolute_error / max(reference_norm, np.finfo(float).tiny)
    mixed_error = absolute_error / max(reference_norm, reference_norm_floor)
    overlap = forward.system.difference_blocks.diagnostics["overlap"]
    overlap_errors = tuple(float(value) for value in overlap["errors"].values())
    overlap_max = max(overlap_errors) if overlap_errors else None
    is_circle = case.name == "circle" and case.source_kind == "analytic"
    block_errors = _circle_block_errors(forward) if is_circle else {}
    if is_circle:
        reference_dirichlet, reference_neumann = _analytic_circle_traces(
            forward.system.geometry.parameters,
            forward.source_points,
            forward.source_strengths,
            forward.system.k_exterior,
            forward.system.k_interior,
        )
        trace_reference_kind = "analytic_mie_series"
    else:
        if reference.dirichlet_trace is None or reference.neumann_trace is None:
            raise ValueError("the noncircular reference did not retain boundary traces.")
        reference_dirichlet = _periodic_resample(
            reference.dirichlet_trace,
            num_nodes,
        )
        reference_neumann = _periodic_resample(
            reference.neumann_trace,
            num_nodes,
        )
        trace_reference_kind = "nystrom_ref_periodic_resample"
    dirichlet_trace_error = float(
        np.linalg.norm(forward.dirichlet_total - reference_dirichlet)
        / max(float(np.linalg.norm(reference_dirichlet)), np.finfo(float).tiny)
    )
    neumann_trace_error = float(
        np.linalg.norm(forward.neumann_total - reference_neumann)
        / max(float(np.linalg.norm(reference_neumann)), np.finfo(float).tiny)
    )
    trace_max_error = max(dirichlet_trace_error, neumann_trace_error)
    retained_block_bytes = int(
        forward.system.difference_blocks.diagnostics["retained_block_bytes"]
    )
    retained_system_bytes = int(
        forward.system.diagnostics["retained_system_matrix_bytes"]
    )
    row: dict[str, Any] = {
        "status": "ok",
        "shape": case.name,
        "source_kind": case.source_kind,
        "num_nodes": num_nodes,
        "frequency_ghz": frequency_hz / 1.0e9,
        "frequency_hz": frequency_hz,
        "reference_kind": reference.reference_kind,
        "reference_nodes": reference.num_nodes,
        "reference_seconds": reference.seconds,
        "reference_relative_residual": reference.relative_residual,
        "reference_incident_consistency": reference.incident_consistency,
        "k_exterior_real": float(np.real(forward.system.k_exterior)),
        "k_exterior_imag": float(np.imag(forward.system.k_exterior)),
        "k_interior_real": float(np.real(forward.system.k_interior)),
        "k_interior_imag": float(np.imag(forward.system.k_interior)),
        "receiver_reference_l2": reference_norm,
        "receiver_observed_l2": observed_norm,
        "receiver_absolute_error_l2": absolute_error,
        "receiver_relative_error_l2": relative_error,
        "receiver_mixed_relative_error_l2": mixed_error,
        "receiver_max_absolute_error": float(np.max(np.abs(error))),
        "receiver_adjacent_relative_difference": None,
        "receiver_error_ratio_to_previous": None,
        "trace_reference_kind": trace_reference_kind,
        "dirichlet_trace_relative_error_l2": dirichlet_trace_error,
        "neumann_trace_relative_error_l2": neumann_trace_error,
        "maximum_trace_relative_error_l2": trace_max_error,
        "condition_number_2": _median(condition_numbers),
        "linear_system_relative_residual": float(
            forward.linear_system_relative_residual
        ),
        "maximum_per_source_residual": float(
            np.max(forward.per_source_relative_residual)
        ),
        "incident_representation_leak": float(
            forward.incident_representation_leak
        ),
        "minimum_speed": float(np.min(curve.speeds)),
        "speed_ratio": float(np.max(curve.speeds) / np.min(curve.speeds)),
        "area": float(curve.signed_area),
        "perimeter": float(curve.perimeter),
        "retained_block_bytes": retained_block_bytes,
        "retained_system_matrix_bytes": retained_system_bytes,
        "retained_core_dense_bytes": retained_block_bytes + retained_system_bytes,
        "overlap_pair_count": int(overlap["pair_count"]),
        "overlap_max_relative_error": overlap_max,
        "near_pair_count": int(
            forward.system.difference_blocks.diagnostics["near_pair_count"]
        ),
        "direct_pair_count": int(
            forward.system.difference_blocks.diagnostics["direct_pair_count"]
        ),
        "circle_delta_v_scaled_action_error": block_errors.get("delta_v"),
        "circle_delta_k_scaled_action_error": block_errors.get("delta_k"),
        "circle_delta_kp_scaled_action_error": block_errors.get("delta_kp"),
        "circle_delta_t_scaled_action_error": block_errors.get("delta_t"),
        "circle_max_scaled_block_action_error": (
            max(block_errors.values()) if block_errors else None
        ),
        "timing_repeats": timing_repeats,
        **{name: _median(values) for name, values in timing_samples.items()},
        "largest_n_gate": "diagnostic",
        "failure_reason": None,
    }
    return row, observed


def _failure_row(
    case: CurveCase,
    num_nodes: int,
    frequency_hz: float,
    reference: ReferenceResult | None,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "shape": case.name,
        "source_kind": case.source_kind,
        "num_nodes": num_nodes,
        "frequency_ghz": frequency_hz / 1.0e9,
        "frequency_hz": frequency_hz,
        "reference_kind": case.reference_kind,
        "reference_nodes": None if reference is None else reference.num_nodes,
        "reference_seconds": None if reference is None else reference.seconds,
        "largest_n_gate": "failed" if num_nodes else "diagnostic",
        "failure_reason": f"{type(exc).__name__}: {exc}",
    }


def _apply_convergence_and_gates(
    rows: list[dict[str, Any]],
    fields: dict[tuple[str, float, int], np.ndarray],
    maximum_nodes: int,
    *,
    receiver_gate: float,
    trace_gate: float,
    residual_gate: float,
    leak_gate: float,
    overlap_gate: float,
    circle_block_gate: float,
) -> list[dict[str, Any]]:
    lookup = {
        (row["shape"], float(row["frequency_hz"]), int(row["num_nodes"])): row
        for row in rows
        if row["status"] == "ok"
    }
    groups = sorted({(key[0], key[1]) for key in lookup})
    gate_records: list[dict[str, Any]] = []
    for shape_name, frequency_hz in groups:
        keys = sorted(
            (
                key
                for key in lookup
                if key[0] == shape_name and key[1] == frequency_hz
            ),
            key=lambda key: key[2],
        )
        previous_row = None
        previous_field = None
        for key in keys:
            row = lookup[key]
            field = fields[key]
            if previous_row is not None and previous_field is not None:
                row["receiver_adjacent_relative_difference"] = float(
                    np.linalg.norm(field - previous_field)
                    / max(float(np.linalg.norm(field)), np.finfo(float).tiny)
                )
                previous_error = float(
                    previous_row["receiver_mixed_relative_error_l2"]
                )
                if previous_error > np.finfo(float).tiny:
                    row["receiver_error_ratio_to_previous"] = float(
                        row["receiver_mixed_relative_error_l2"] / previous_error
                    )
            previous_row = row
            previous_field = field

        row = lookup.get((shape_name, frequency_hz, maximum_nodes))
        if row is None:
            continue
        checks = {
            "receiver": row["receiver_mixed_relative_error_l2"] <= receiver_gate,
            "boundary_traces": row["maximum_trace_relative_error_l2"] <= trace_gate,
            "linear_residual": row["linear_system_relative_residual"] <= residual_gate,
            "incident_leak": row["incident_representation_leak"] <= leak_gate,
            "finite_condition": bool(np.isfinite(row["condition_number_2"])),
        }
        overlap_error = row["overlap_max_relative_error"]
        if overlap_error is not None:
            checks["near_direct_overlap"] = overlap_error <= overlap_gate
        block_error = row["circle_max_scaled_block_action_error"]
        if block_error is not None:
            checks["circle_blocks"] = block_error <= circle_block_gate
        passed = all(checks.values())
        row["largest_n_gate"] = "pass" if passed else "fail"
        gate_records.append(
            {
                "shape": shape_name,
                "frequency_ghz": frequency_hz / 1.0e9,
                "num_nodes": maximum_nodes,
                "status": row["largest_n_gate"],
                "checks": checks,
            }
        )
    for row in rows:
        if row["status"] == "failed" and int(row["num_nodes"]) == maximum_nodes:
            row["largest_n_gate"] = "fail"
            gate_records.append(
                {
                    "shape": row["shape"],
                    "frequency_ghz": row["frequency_ghz"],
                    "num_nodes": maximum_nodes,
                    "status": "fail",
                    "checks": {"execution": False},
                }
            )
    return gate_records


CSV_FIELDS = (
    "status",
    "shape",
    "source_kind",
    "num_nodes",
    "frequency_ghz",
    "frequency_hz",
    "reference_kind",
    "reference_nodes",
    "receiver_absolute_error_l2",
    "receiver_relative_error_l2",
    "receiver_mixed_relative_error_l2",
    "receiver_max_absolute_error",
    "receiver_adjacent_relative_difference",
    "receiver_error_ratio_to_previous",
    "receiver_reference_l2",
    "receiver_observed_l2",
    "trace_reference_kind",
    "dirichlet_trace_relative_error_l2",
    "neumann_trace_relative_error_l2",
    "maximum_trace_relative_error_l2",
    "condition_number_2",
    "linear_system_relative_residual",
    "maximum_per_source_residual",
    "incident_representation_leak",
    "circle_delta_v_scaled_action_error",
    "circle_delta_k_scaled_action_error",
    "circle_delta_kp_scaled_action_error",
    "circle_delta_t_scaled_action_error",
    "circle_max_scaled_block_action_error",
    "overlap_pair_count",
    "overlap_max_relative_error",
    "near_pair_count",
    "direct_pair_count",
    "minimum_speed",
    "speed_ratio",
    "area",
    "perimeter",
    "retained_block_bytes",
    "retained_system_matrix_bytes",
    "retained_core_dense_bytes",
    "k_exterior_real",
    "k_exterior_imag",
    "k_interior_real",
    "k_interior_imag",
    "block_build_seconds",
    "matrix_composition_seconds",
    "system_assembly_seconds",
    "condition_seconds",
    "solve_seconds",
    "receiver_seconds",
    "forward_total_seconds",
    "measured_total_seconds",
    "reference_seconds",
    "reference_relative_residual",
    "reference_incident_consistency",
    "timing_repeats",
    "largest_n_gate",
    "failure_reason",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_json_value(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_value(row.get(key)) for key in CSV_FIELDS})


def _scientific(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(numeric):
        return "—"
    return f"{numeric:.{digits}e}"


def _milliseconds(value: Any) -> str:
    if value is None:
        return "—"
    return f"{1.0e3 * float(value):.1f}"


def _mebibytes(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value) / (1024.0**2):.2f}"


def _markdown_summary(
    rows: Sequence[dict[str, Any]],
    gates: Sequence[dict[str, Any]],
    settings: dict[str, Any],
) -> str:
    failures = [row for row in rows if row["status"] != "ok"]
    gate_failures = [gate for gate in gates if gate["status"] != "pass"]
    lines = [
        "# Ordered-boundary Nyström validation",
        "",
        (
            "This run contains actual Müller operator, direct-solve, and "
            "off-surface receiver errors. It is not a geometry-only or scalar "
            "Kress-proxy study."
        ),
        "",
        (
            f"Preset `{settings['preset']}`; nodes `{settings['nodes']}`; "
            f"frequencies `{settings['frequencies_ghz']}` GHz; "
            f"{settings['num_pairs']} sources × {settings['num_pairs']} receivers."
        ),
        "",
        (
            "Circle truth is the analytic penetrable-cylinder Mie series. "
            "Ellipse, star, and frozen Fourier curves use the independently "
            f"implemented `nystrom_ref` solver frozen at N={settings['reference_nodes']}."
        ),
        "",
        (
            "Frozen Fourier bundles are first reconstructed exactly, then scaled "
            "uniformly about their mode-zero center to the configured physical "
            "mean radius and translated to the benchmark center. Candidate and "
            "reference receive that same normalized parameterization."
        ),
        "",
        (
            "Times below are medians over "
            f"{settings['timing_repeats']} repeat(s). `total ms` includes the "
            "candidate forward call and the separately timed 2-norm condition "
            "estimate; oracle time is reported separately in the detailed CSV."
        ),
        (
            "`Rx+leak ms` includes both the physical receiver representation and "
            "the second incident-representation convention check."
        ),
        "",
        (
            "`raw cond.` is a mixed-unit nodal diagnostic, not a scale-invariant "
            "quality score. `core MiB` is exact retained storage for the four "
            "difference matrices plus the system matrix, not process peak RSS."
        ),
        "",
        "## Largest-N configured checks",
        "",
        "| Shape | GHz | N | Mixed receiver error | Max trace error | Raw cond. (diag.) | Residual | Leak | Circle block | Block ms | Cond. ms | Solve ms | Rx+leak ms | Total ms | Core MiB | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    gate_keys = {
        (gate["shape"], float(gate["frequency_ghz"]), int(gate["num_nodes"]))
        for gate in gates
    }
    for row in rows:
        key = (row["shape"], float(row["frequency_ghz"]), int(row["num_nodes"]))
        if key not in gate_keys:
            continue
        lines.append(
            "| "
            + " | ".join(
                (
                    str(row["shape"]),
                    f"{float(row['frequency_ghz']):g}",
                    str(row["num_nodes"]),
                    _scientific(row.get("receiver_mixed_relative_error_l2")),
                    _scientific(row.get("maximum_trace_relative_error_l2")),
                    _scientific(row.get("condition_number_2")),
                    _scientific(row.get("linear_system_relative_residual")),
                    _scientific(row.get("incident_representation_leak")),
                    _scientific(row.get("circle_max_scaled_block_action_error")),
                    _milliseconds(row.get("block_build_seconds")),
                    _milliseconds(row.get("condition_seconds")),
                    _milliseconds(row.get("solve_seconds")),
                    _milliseconds(row.get("receiver_seconds")),
                    _milliseconds(row.get("measured_total_seconds")),
                    _mebibytes(row.get("retained_core_dense_bytes")),
                    str(row.get("largest_n_gate", "fail")),
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Nyström node refinement",
            "",
            "| Shape | GHz | N | Relative receiver error | Mixed error | Adjacent-N difference | Error ratio | Total ms |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    str(row["shape"]),
                    f"{float(row['frequency_ghz']):g}",
                    str(row["num_nodes"]),
                    _scientific(row.get("receiver_relative_error_l2")),
                    _scientific(row.get("receiver_mixed_relative_error_l2")),
                    _scientific(row.get("receiver_adjacent_relative_difference")),
                    _scientific(row.get("receiver_error_ratio_to_previous")),
                    _milliseconds(row.get("measured_total_seconds")),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "Only the largest requested N is checked against this run's configurable "
                "smoke thresholds. Earlier rows are deliberately retained as convergence "
                "evidence. Passing these checks is not Phase-4 acceptance or solver "
                "promotion; reference self-convergence, transmission residuals, and the "
                "broader frequency ladder remain separate gates."
            ),
            "",
            (
                f"Execution failures: {len(failures)}. Largest-N check failures: "
                f"{len(gate_failures)}."
            ),
            "",
            "No dense matrices or solution arrays are stored by this runner.",
            "",
        ]
    )
    if failures:
        lines.extend(["## Failures", ""])
        for row in failures:
            lines.append(
                f"- `{row['shape']}`, {row['frequency_ghz']:g} GHz, "
                f"N={row['num_nodes']}: {row['failure_reason']}"
            )
        lines.append("")
    return "\n".join(lines)


def _git_metadata() -> dict[str, Any]:
    def command(*arguments: str) -> str | None:
        try:
            return subprocess.run(
                ("git", *arguments),
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = command("status", "--porcelain")
    return {
        "commit": command("rev-parse", "HEAD"),
        "dirty": None if status is None else bool(status),
        "status_entry_count": None if status is None else len(status.splitlines()),
    }


def _source_hashes() -> dict[str, str]:
    paths = [
        Path(__file__).resolve(),
        REPOSITORY_ROOT / "config" / "base_config.py",
        REPOSITORY_ROOT / "config" / "circle_config.py",
        SOLVERS_ROOT / "gpr_bem_mod" / "__init__.py",
        SOLVERS_ROOT / "gpr_bem_mod" / "materials.py",
        SOLVERS_ROOT / "gpr_bem_mod" / "cylinder_reference.py",
    ]
    for package in (
        SOLVERS_ROOT / "gpr_bem_mod" / "ordered_nystrom",
        SOLVERS_ROOT / "ordered_boundary",
        SOLVERS_ROOT / "periodic_kress",
        SOLVERS_ROOT / "nystrom_ref",
    ):
        paths.extend(sorted(package.glob("*.py")))
    return {
        str(path.relative_to(REPOSITORY_ROOT)): _sha256(path)
        for path in paths
        if path.is_file()
    }


def _validate_settings(
    parser: argparse.ArgumentParser,
    cases: Sequence[CurveCase],
    nodes: tuple[int, ...],
    reference_nodes: int,
    series_terms: int,
) -> None:
    if reference_nodes < 8 or reference_nodes % 2:
        parser.error("--reference-nodes must be even and at least 8.")
    if any(case.reference_kind != "analytic_mie_series" for case in cases):
        if reference_nodes < 2 * max(nodes):
            parser.error(
                "--reference-nodes must be at least twice the largest candidate N "
                "for noncircular or frozen curves."
            )
    if series_terms < 6:
        parser.error("--series-terms must be at least 6.")
    for case in cases:
        if case.fourier_bandwidth is None:
            continue
        minimum_nodes = 2 * case.fourier_bandwidth + 2
        if min(nodes) < minimum_nodes:
            parser.error(
                f"frozen curve {case.name!r} has Fourier bandwidth "
                f"{case.fourier_bandwidth}; every candidate N must be at least "
                f"{minimum_nodes} to avoid aliasing."
            )
        if reference_nodes < minimum_nodes:
            parser.error(
                f"--reference-nodes must be at least {minimum_nodes} for "
                f"frozen curve {case.name!r}."
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    preset = PRESETS[args.preset]
    nodes = preset.nodes if args.nodes is None else args.nodes
    frequencies_ghz = (
        preset.frequencies_ghz
        if args.frequencies_ghz is None
        else args.frequencies_ghz
    )
    reference_nodes = (
        preset.reference_nodes
        if args.reference_nodes is None
        else args.reference_nodes
    )
    num_pairs = preset.num_pairs if args.num_pairs is None else args.num_pairs

    cases = _analytic_cases(args.shapes)
    existing = {case.name for case in cases}
    try:
        for frozen_path in args.curve_npz:
            case = _load_frozen_case(
                frozen_path,
                existing,
                args.frozen_target_mean_radius_m,
            )
            cases.append(case)
            existing.add(case.name)
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    if not cases:
        parser.error("at least one analytic or frozen curve is required.")
    _validate_settings(parser, cases, nodes, reference_nodes, args.series_terms)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or f"{args.preset}-{timestamp}"
    output_directory = args.output_root.expanduser().resolve() / run_id
    try:
        output_directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error(f"output directory already exists: {output_directory}")

    exterior = gpr_bem_mod.Material(
        epsr=physical_config.SAND_EPSR,
        sigma=physical_config.SAND_SIGMA,
    )
    interior = gpr_bem_mod.Material(
        epsr=physical_config.PLASTIC_EPSR,
        sigma=physical_config.PLASTIC_SIGMA,
    )
    sources, receivers = _scan_points(num_pairs)
    assembly_config = MullerAssemblyConfig(
        near_argument=args.near_argument,
        series_terms=args.series_terms,
        target_chunk_size=args.target_chunk_size,
    )
    settings: dict[str, Any] = {
        "preset": args.preset,
        "nodes": list(nodes),
        "frequencies_ghz": list(frequencies_ghz),
        "reference_nodes": reference_nodes,
        "num_pairs": num_pairs,
        "timing_repeats": args.timing_repeats,
        "frozen_target_mean_radius_m": args.frozen_target_mean_radius_m,
        "assembly": {
            "near_argument": args.near_argument,
            "series_terms": args.series_terms,
            "target_chunk_size": args.target_chunk_size,
        },
        "gates": {
            "receiver_mixed_relative_error_l2": args.receiver_gate,
            "maximum_trace_relative_error_l2": args.trace_gate,
            "linear_system_relative_residual": args.residual_gate,
            "incident_representation_leak": args.leak_gate,
            "near_direct_overlap": args.overlap_gate,
            "circle_scaled_block_action_error": args.circle_block_gate,
            "mixed_floor_fraction": args.mixed_floor_fraction,
        },
    }

    frequencies_hz = tuple(item * 1.0e9 for item in frequencies_ghz)
    references: dict[tuple[str, float], ReferenceResult] = {}
    reference_failures: dict[tuple[str, float], Exception] = {}
    for case in cases:
        for frequency_hz in frequencies_hz:
            try:
                references[(case.name, frequency_hz)] = _compute_reference(
                    case,
                    frequency_hz,
                    sources,
                    receivers,
                    reference_nodes,
                    exterior,
                    interior,
                )
            except Exception as exc:  # Keep a complete sweep failure table.
                reference_failures[(case.name, frequency_hz)] = exc

    norm_floors: dict[str, float] = {}
    for case in cases:
        norms = [
            float(np.linalg.norm(reference.field))
            for (shape_name, _), reference in references.items()
            if shape_name == case.name
        ]
        norm_floors[case.name] = args.mixed_floor_fraction * max(
            norms or [np.finfo(float).tiny]
        )

    rows: list[dict[str, Any]] = []
    fields: dict[tuple[str, float, int], np.ndarray] = {}
    for case in cases:
        for frequency_hz in frequencies_hz:
            reference = references.get((case.name, frequency_hz))
            for num_nodes in nodes:
                if reference is None:
                    rows.append(
                        _failure_row(
                            case,
                            num_nodes,
                            frequency_hz,
                            None,
                            reference_failures[(case.name, frequency_hz)],
                        )
                    )
                    continue
                try:
                    row, field = _candidate_row(
                        case,
                        num_nodes,
                        frequency_hz,
                        reference,
                        norm_floors[case.name],
                        sources,
                        receivers,
                        exterior,
                        interior,
                        assembly_config,
                        args.timing_repeats,
                    )
                    rows.append(row)
                    fields[(case.name, frequency_hz, num_nodes)] = field
                except Exception as exc:  # Keep already-computed evidence usable.
                    rows.append(
                        _failure_row(
                            case,
                            num_nodes,
                            frequency_hz,
                            reference,
                            exc,
                        )
                    )

    gates = _apply_convergence_and_gates(
        rows,
        fields,
        max(nodes),
        receiver_gate=args.receiver_gate,
        trace_gate=args.trace_gate,
        residual_gate=args.residual_gate,
        leak_gate=args.leak_gate,
        overlap_gate=args.overlap_gate,
        circle_block_gate=args.circle_block_gate,
    )
    rows.sort(key=lambda row: (row["shape"], row["frequency_hz"], row["num_nodes"]))

    metrics_csv = output_directory / "metrics.csv"
    metrics_json = output_directory / "metrics.json"
    summary_path = output_directory / "summary.md"
    manifest_path = output_directory / "manifest.json"
    _write_csv(metrics_csv, rows)
    _write_json(
        metrics_json,
        {
            "schema_version": 1,
            "measurement_scope": {
                "geometry_only": False,
                "bie_operators_assembled": True,
                "linear_system_solved": True,
                "receiver_field_evaluated": True,
                "contains_solver_error_metrics": True,
                "dense_arrays_persisted": False,
            },
            "settings": settings,
            "gates": gates,
            "rows": rows,
        },
    )
    summary_path.write_text(
        _markdown_summary(rows, gates, settings),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "command": shlex.join(
            [sys.executable, str(Path(__file__).name), *(argv or sys.argv[1:])]
        ),
        "output_directory": str(output_directory),
        "settings": settings,
        "cases": [
            {
                "name": case.name,
                "source_kind": case.source_kind,
                "definition": case.definition,
                "reference_kind": case.reference_kind,
                "frozen_path": case.frozen_path,
                "frozen_sha256": case.frozen_sha256,
                "fourier_bandwidth": case.fourier_bandwidth,
                "normalization_scale": case.normalization_scale,
                "original_center": case.original_center,
                "original_mean_radius": case.original_mean_radius,
                "target_mean_radius": case.target_mean_radius,
            }
            for case in cases
        ],
        "physics": {
            "eps0": physical_config.EPS0,
            "mu0": physical_config.MU0,
            "exterior": {
                "epsr": exterior.epsr,
                "sigma": exterior.sigma,
                "mur": exterior.mur,
            },
            "interior": {
                "epsr": interior.epsr,
                "sigma": interior.sigma,
                "mur": interior.mur,
            },
            "source_strength": 1.0,
            "source_ring_radius_m": 0.27,
            "receiver_ring_radius_m": 0.27,
            "source_receiver_angular_offset_rad": 0.12,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "thread_environment": {
                name: os.environ.get(name)
                for name in (
                    "OMP_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                )
            },
        },
        "git": _git_metadata(),
        "source_sha256": _source_hashes(),
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (metrics_csv, metrics_json, summary_path)
        },
        "storage_policy": {
            "dense_matrices_persisted": False,
            "solutions_persisted": False,
            "receiver_arrays_persisted": False,
            "artifacts_are_scalar_tables_and_metadata_only": True,
        },
    }
    _write_json(manifest_path, manifest)

    execution_failures = sum(row["status"] != "ok" for row in rows)
    gate_failures = sum(gate["status"] != "pass" for gate in gates)
    print(f"artifacts: {output_directory}")
    print(f"metric rows: {len(rows)}; execution failures: {execution_failures}")
    print(
        f"largest-N configured checks: {len(gates) - gate_failures} pass, "
        f"{gate_failures} fail"
    )
    print(f"summary: {summary_path}")
    print(f"CSV: {metrics_csv}")
    print(f"JSON: {metrics_json}")
    print(f"manifest: {manifest_path}")
    if execution_failures:
        return 1
    if args.enforce and gate_failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
