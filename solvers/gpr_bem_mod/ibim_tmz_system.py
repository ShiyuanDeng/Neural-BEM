"""Implicit-boundary TMz frequency-system assembly and solve helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from .backend import AssemblyBackend, get_assembly_backend
from .ibim_geometry import ImplicitBoundaryBand2D, ImplicitBoundarySamples2D
from .ibim_tmz_forward import (
    _normalize_normal_derivative_scheme,
    build_implicit_boundary_operator_family,
    default_trace_offset_distance,
    implicit_double_layer_potential_from_band,
    implicit_single_layer_potential_from_band,
)
from .materials import Material

__all__ = [
    "ImplicitTMzFrequencySystem",
    "ImplicitTMzForwardResult",
    "ImplicitTMzMultiFrequencyForwardResult",
    "adjoint_system_matrix",
    "build_ibim_tmz_frequency_system",
    "ibim_incident_trace_on_boundary",
    "solve_ibim_tmz_frequency_response",
    "solve_ibim_tmz_total_field_batch",
]


@dataclass(frozen=True)
class ImplicitTMzFrequencySystem:
    """Single-frequency implicit-boundary TMz multitrace system."""

    angular_frequency: float
    k_exterior: complex
    k_interior: complex
    system_matrix: object
    system_matrix_squared: object
    operator_family_exterior: object
    operator_family_interior: object
    num_boundary_samples: int
    offset_distance: float
    use_strict_quadrature: bool
    backend_name: str
    formulation: str = "muller"
    normal_derivative_scheme: str = "analytic_extrapolated"


@dataclass(frozen=True)
class ImplicitTMzForwardResult:
    """Host-side decomposition of an implicit-boundary TMz forward solve."""

    system: ImplicitTMzFrequencySystem
    source_points: np.ndarray
    receiver_points: np.ndarray
    source_strengths: np.ndarray
    dirichlet_incident: np.ndarray
    neumann_incident: np.ndarray
    dirichlet_total: np.ndarray
    neumann_total: np.ndarray
    incident_receiver: np.ndarray
    single_receiver: np.ndarray
    double_receiver: np.ndarray
    scattered_receiver: np.ndarray
    total_receiver: np.ndarray
    solve_strategy: str
    linear_system_relative_residual: float


@dataclass(frozen=True)
class ImplicitTMzMultiFrequencyForwardResult:
    """Multi-frequency implicit-boundary TMz forward response."""

    angular_frequencies: np.ndarray
    frequency_response: np.ndarray
    forwards: tuple[ImplicitTMzForwardResult, ...]


_FORMULATIONS = ("muller", "difference")
DEFAULT_FORMULATION = "muller"

# The first-kind "difference" system has an accuracy valley at 2 x merge_distance and
# blows up below it. That lower bound belongs to the FORMULATION, not to the quadrature
# and not to the finite differencing: every normal-derivative scheme, including the
# analytic kernels that do no differencing at all, fails there by the same amount.
#
# Under the second-kind Muller combination the bound disappears and the valley moves in
# by roughly 8x. Swept on the analytic circle at 257^2 / 272 samples, 0.5-2.5 GHz, the
# geometric-mean optimum for the default analytic_extrapolated scheme is
# 0.275 x merge_distance = 0.1375 x the historical default. The valley is shallow
# between 0.25 and 0.30 md (within ~1.4x at 2.5 GHz), so this is not a knife edge, but
# it is tuned on one geometry and one discretisation and should be re-swept if either
# changes materially.
#
# The optimum is scheme-dependent: finite_difference bottoms out near 0.125 md and
# analytic near 0.0625 md. A caller who overrides normal_derivative_scheme should
# override offset_distance too.
MULLER_OFFSET_SCALE = 0.1375


def _normalize_formulation(formulation: str | None) -> str:
    if formulation is None:
        return DEFAULT_FORMULATION
    name = str(formulation).strip().lower()
    if name not in _FORMULATIONS:
        raise ValueError(f"formulation must be one of {_FORMULATIONS}, got {formulation!r}.")
    return name


def build_ibim_tmz_frequency_system(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    angular_frequency: float,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    formulation: str | None = None,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitTMzFrequencySystem:
    """Assemble a single-frequency implicit-boundary TMz multitrace system."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    normalized_formulation = _normalize_formulation(formulation)
    if offset_distance is None and normalized_formulation == "muller":
        offset_distance = MULLER_OFFSET_SCALE * default_trace_offset_distance(boundary)
    angular_frequency_value = float(angular_frequency)
    k_exterior = complex(exterior.wavenumber(angular_frequency_value, eps0, mu0))
    k_interior = complex(interior.wavenumber(angular_frequency_value, eps0, mu0))
    exterior_family = build_implicit_boundary_operator_family(
        boundary,
        np.array([k_exterior], dtype=np.complex128),
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    interior_family = build_implicit_boundary_operator_family(
        boundary,
        np.array([k_interior], dtype=np.complex128),
        offset_distance=exterior_family.offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    xp = resolved_backend.xp
    # Both Calderon equations (exterior scattered-field representation, interior Green
    # representation) are written for the same unknowns (u, q) = total Dirichlet/Neumann
    # traces, with n pointing out of the interior domain. They can be combined two ways.
    #
    #   difference:  (exterior) - (interior).  The +-1/2 identity terms cancel and every
    #                block becomes a SUM of the two wavenumbers. First kind, and the
    #                hypersingular principal parts reinforce instead of cancelling.
    #                This is what the solver did historically; kept for reproducibility.
    #
    #   muller:      (exterior) + (interior).  The identity survives on the diagonal and
    #                every block becomes a DIFFERENCE, whose leading singularities cancel
    #                (T_out - T_in is only logarithmically singular for smooth Gamma).
    #                Second kind. This is the Muller formulation and is the default.
    #
    # Note that hypersingular_matrix carries W = -T (see the sign in
    # build_implicit_hypersingular_boundary_matrix), which is why all four blocks take
    # the same exterior-minus-interior orientation here.
    if normalized_formulation == "muller":
        single_layer = exterior_family.single_layer_matrix - interior_family.single_layer_matrix
        double_layer = exterior_family.double_layer_matrix - interior_family.double_layer_matrix
        adjoint_double_layer = (
            exterior_family.adjoint_double_layer_matrix - interior_family.adjoint_double_layer_matrix
        )
        hypersingular = exterior_family.hypersingular_matrix - interior_family.hypersingular_matrix
        num_samples = int(exterior_family.num_boundary_samples)
        identity = xp.eye(num_samples, dtype=resolved_backend.complex_dtype)[None, :, :]
        upper_left = identity - double_layer
        lower_right = identity + adjoint_double_layer
    else:
        single_layer = exterior_family.single_layer_matrix + interior_family.single_layer_matrix
        double_layer = exterior_family.double_layer_matrix + interior_family.double_layer_matrix
        adjoint_double_layer = (
            exterior_family.adjoint_double_layer_matrix + interior_family.adjoint_double_layer_matrix
        )
        hypersingular = exterior_family.hypersingular_matrix + interior_family.hypersingular_matrix
        upper_left = -double_layer
        lower_right = adjoint_double_layer
    system_matrix = xp.concatenate(
        [
            xp.concatenate([upper_left, single_layer], axis=2),
            xp.concatenate([hypersingular, lower_right], axis=2),
        ],
        axis=1,
    )
    system_matrix_squared = xp.matmul(system_matrix, system_matrix)
    return ImplicitTMzFrequencySystem(
        angular_frequency=angular_frequency_value,
        k_exterior=k_exterior,
        k_interior=k_interior,
        system_matrix=system_matrix,
        system_matrix_squared=system_matrix_squared,
        operator_family_exterior=exterior_family,
        operator_family_interior=interior_family,
        num_boundary_samples=exterior_family.num_boundary_samples,
        offset_distance=exterior_family.offset_distance,
        use_strict_quadrature=bool(use_strict_quadrature),
        backend_name=resolved_backend.name,
        formulation=normalized_formulation,
        normal_derivative_scheme=_normalize_normal_derivative_scheme(normal_derivative_scheme),
    )


def adjoint_system_matrix(system: ImplicitTMzFrequencySystem):
    """Return ``A^H`` for the dual solve ``A^H mu = C^H psi``.

    Phase 2 of ``docs/legacy/adjoint_inverse_rebuild_plan.md``. Deliberately the
    conjugate transpose of the already-assembled dense ``system.system_matrix``
    -- not a from-scratch block reconstruction. ``docs/ibim_shape_derivative.md``
    S7 describes what the block-swap *should* look like (``single_layer`` and
    ``hypersingular`` trade places, each individually transposed) as a way to
    understand and sanity-check the structure, but since ``A`` is already a
    fully materialized dense array by the time this is called, computing the
    transpose directly removes any chance of a hand-reconstruction bug in the
    block bookkeeping -- there is nothing to get backwards.
    """

    xp = np if system.backend_name != "cupy" else __import__("cupy")
    matrix = system.system_matrix
    return xp.conj(xp.swapaxes(matrix, -1, -2))


def ibim_incident_trace_on_boundary(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_points,
    angular_frequency: float,
    source_strength,
    *,
    exterior: Material,
    eps0: float,
    mu0: float,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> tuple[object, object]:
    """Evaluate the incident Dirichlet/Neumann traces on an implicit boundary."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    boundary_points, normals = _boundary_geometry(boundary, resolved_backend)
    source_points_array = _as_backend_real_matrix(source_points, resolved_backend)
    strengths = _as_backend_complex_vector(source_strength, resolved_backend)
    if strengths.shape[0] == 1 and source_points_array.shape[0] > 1:
        strengths = xp.full((source_points_array.shape[0],), strengths[0], dtype=resolved_backend.complex_dtype)
    if strengths.shape != (source_points_array.shape[0],):
        raise ValueError("source_strength must be scalar or have one value per source point.")
    k_exterior = complex(exterior.wavenumber(float(angular_frequency), eps0, mu0))
    displacement = boundary_points[None, :, :] - source_points_array[:, None, :]
    distance = xp.linalg.norm(displacement, axis=2)
    factor = xp.einsum("bsd,sd->bs", displacement, normals, optimize=True) / distance
    dirichlet_kernel = 0.25j * resolved_backend.hankel1(0, k_exterior * distance)
    neumann_kernel = -0.25j * k_exterior * resolved_backend.hankel1(1, k_exterior * distance) * factor
    dirichlet = strengths[:, None] * dirichlet_kernel
    neumann = strengths[:, None] * neumann_kernel
    return dirichlet, neumann


def solve_ibim_tmz_total_field_batch(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_points,
    receiver_points,
    angular_frequency: float,
    source_strength,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    solve_strategy: str = "direct",
    formulation: str | None = None,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitTMzForwardResult:
    """Solve the implicit-boundary TMz multitrace system and evaluate receivers."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    normalized_solve_strategy = _normalize_solve_strategy(solve_strategy)
    source_points_array = _as_backend_real_matrix(source_points, resolved_backend)
    receiver_points_array = _as_backend_real_matrix(receiver_points, resolved_backend)
    if receiver_points_array.shape != source_points_array.shape:
        raise ValueError("receiver_points must have the same shape as source_points.")

    system = build_ibim_tmz_frequency_system(
        boundary,
        angular_frequency,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        formulation=formulation,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    dirichlet_incident, neumann_incident = ibim_incident_trace_on_boundary(
        boundary,
        source_points_array,
        angular_frequency,
        source_strength,
        exterior=exterior,
        eps0=eps0,
        mu0=mu0,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    rhs = resolved_backend.xp.concatenate((dirichlet_incident, neumann_incident), axis=1).T
    traces = _solve_state_traces(
        system,
        rhs,
        resolved_backend,
        solve_strategy=normalized_solve_strategy,
    )
    linear_system_relative_residual = _relative_linear_system_residual(
        system.system_matrix[0],
        traces,
        rhs,
        resolved_backend,
    )
    num_boundary = system.num_boundary_samples
    dirichlet_total = traces[:num_boundary].T
    neumann_total = traces[num_boundary:].T

    strengths = _as_backend_complex_vector(source_strength, resolved_backend)
    if strengths.shape[0] == 1 and source_points_array.shape[0] > 1:
        strengths = resolved_backend.xp.full(
            (source_points_array.shape[0],),
            strengths[0],
            dtype=resolved_backend.complex_dtype,
        )
    source_receiver_distance = resolved_backend.xp.linalg.norm(receiver_points_array - source_points_array, axis=1)
    incident_receiver = strengths * (0.25j * resolved_backend.hankel1(0, system.k_exterior * source_receiver_distance))
    single_receiver = implicit_single_layer_potential_from_band(
        receiver_points_array,
        boundary,
        neumann_total.T,
        system.k_exterior,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    ).potentials
    double_receiver = implicit_double_layer_potential_from_band(
        receiver_points_array,
        boundary,
        dirichlet_total.T,
        system.k_exterior,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    ).potentials
    single_receiver = _paired_receiver_response(single_receiver, resolved_backend)
    double_receiver = _paired_receiver_response(double_receiver, resolved_backend)
    scattered_receiver = double_receiver - single_receiver
    total_receiver = incident_receiver + scattered_receiver
    return ImplicitTMzForwardResult(
        system=system,
        source_points=np.asarray(resolved_backend.to_host(source_points_array), dtype=float),
        receiver_points=np.asarray(resolved_backend.to_host(receiver_points_array), dtype=float),
        source_strengths=np.asarray(resolved_backend.to_host(strengths), dtype=np.complex128),
        dirichlet_incident=np.asarray(resolved_backend.to_host(dirichlet_incident), dtype=np.complex128),
        neumann_incident=np.asarray(resolved_backend.to_host(neumann_incident), dtype=np.complex128),
        dirichlet_total=np.asarray(resolved_backend.to_host(dirichlet_total), dtype=np.complex128),
        neumann_total=np.asarray(resolved_backend.to_host(neumann_total), dtype=np.complex128),
        incident_receiver=np.asarray(resolved_backend.to_host(incident_receiver), dtype=np.complex128),
        single_receiver=np.asarray(resolved_backend.to_host(single_receiver), dtype=np.complex128),
        double_receiver=np.asarray(resolved_backend.to_host(double_receiver), dtype=np.complex128),
        scattered_receiver=np.asarray(resolved_backend.to_host(scattered_receiver), dtype=np.complex128),
        total_receiver=np.asarray(resolved_backend.to_host(total_receiver), dtype=np.complex128),
        solve_strategy=normalized_solve_strategy,
        linear_system_relative_residual=linear_system_relative_residual,
    )


def solve_ibim_tmz_frequency_response(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_points,
    receiver_points,
    angular_frequencies,
    source_strength,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    solve_strategy: str = "direct",
    formulation: str | None = None,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitTMzMultiFrequencyForwardResult:
    """Solve the implicit-boundary TMz system for multiple frequencies."""

    frequency_array = np.atleast_1d(np.asarray(angular_frequencies, dtype=float))
    if frequency_array.ndim != 1:
        raise ValueError("angular_frequencies must be scalar or one-dimensional.")
    forwards = tuple(
        solve_ibim_tmz_total_field_batch(
            boundary,
            source_points,
            receiver_points,
            float(angular_frequency),
            source_strength,
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            offset_distance=offset_distance,
            use_strict_quadrature=use_strict_quadrature,
            solve_strategy=solve_strategy,
            formulation=formulation,
            normal_derivative_scheme=normal_derivative_scheme,
            backend=backend,
            complex_precision=complex_precision,
        )
        for angular_frequency in frequency_array
    )
    frequency_response = np.stack([forward.total_receiver for forward in forwards], axis=1).astype(np.complex128)
    return ImplicitTMzMultiFrequencyForwardResult(
        angular_frequencies=frequency_array,
        frequency_response=frequency_response,
        forwards=forwards,
    )


def _resolve_backend(backend: str | AssemblyBackend, *, complex_precision: str) -> AssemblyBackend:
    if isinstance(backend, AssemblyBackend):
        return backend
    return get_assembly_backend(str(backend), complex_precision=complex_precision)


def _as_backend_real_matrix(values, backend: AssemblyBackend):
    array = _as_backend_real_array(values, backend)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("Expected an array of shape (batch, 2).")
    return array


def _as_backend_complex_vector(values, backend: AssemblyBackend):
    if isinstance(values, torch.Tensor):
        host = values.detach().cpu().numpy()
        array = backend.ascomplex(np.atleast_1d(host))
    else:
        array = backend.ascomplex(np.atleast_1d(values))
    if array.ndim != 1:
        raise ValueError("Expected a one-dimensional complex vector.")
    return array


def _boundary_geometry(boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D, backend: AssemblyBackend):
    if isinstance(boundary, ImplicitBoundarySamples2D):
        return _as_backend_real_array(boundary.points, backend), _as_backend_real_array(boundary.normals, backend)
    return _as_backend_real_array(boundary.projected_points, backend), _as_backend_real_array(boundary.normals, backend)


def _solve_linear_system(matrix, rhs, backend: AssemblyBackend):
    if backend.name == "cupy":
        return backend.xp.linalg.solve(matrix, rhs)
    return np.linalg.solve(np.asarray(matrix), np.asarray(rhs))


def _normalize_solve_strategy(solve_strategy: str) -> str:
    normalized = str(solve_strategy).strip().lower()
    if normalized not in {"direct", "squared"}:
        raise ValueError("solve_strategy must be 'direct' or 'squared'.")
    return normalized


def _solve_state_traces(
    system: ImplicitTMzFrequencySystem,
    rhs,
    backend: AssemblyBackend,
    *,
    solve_strategy: str,
):
    if solve_strategy == "direct":
        return _solve_linear_system(system.system_matrix[0], rhs, backend)
    reduced_rhs = backend.xp.matmul(system.system_matrix[0], rhs)
    return _solve_linear_system(system.system_matrix_squared[0], reduced_rhs, backend)


def _relative_linear_system_residual(matrix, solution, rhs, backend: AssemblyBackend) -> float:
    residual = backend.xp.matmul(matrix, solution) - rhs
    residual_norm = float(backend.to_host(backend.xp.linalg.norm(residual)))
    rhs_norm = float(backend.to_host(backend.xp.linalg.norm(rhs)))
    if rhs_norm <= 0.0:
        return 0.0 if residual_norm <= 0.0 else float("inf")
    return residual_norm / rhs_norm


def _paired_receiver_response(potentials, backend: AssemblyBackend):
    array = potentials[0]
    if array.ndim == 1:
        return array
    if array.ndim != 2 or array.shape[0] != array.shape[1]:
        raise ValueError(
            "Expected paired receiver potentials with shape (batch,) or (batch, batch)."
        )
    xp = backend.xp
    indices = xp.arange(array.shape[0])
    return array[indices, indices]


def _as_backend_real_array(values, backend: AssemblyBackend):
    if isinstance(values, torch.Tensor):
        if backend.name == "cupy":
            import cupy as cp

            tensor = values.detach().contiguous()
            array = cp.from_dlpack(tensor) if tensor.is_cuda else cp.asarray(tensor.cpu().numpy())
            return array.astype(backend.real_dtype, copy=False)
        return np.asarray(values.detach().cpu().numpy(), dtype=backend.real_dtype)
    return backend.asreal(values)
