"""Muller system assembly, solve, and receiver evaluation for ``gpr_bem_kdiff``.

Structurally simpler than ``gpr_bem_mod``'s file of the same name, on purpose:
there is only one formulation (Muller, kernel-differenced) and one backend
(numpy). No ``offset_distance``, no ``normal_derivative_scheme``, no
``solve_strategy="squared"`` (the direct solve was already shown preferable
in ``gpr_bem_mod``'s own history -- see ``docs/validation_change_log.md``,
2026-08-21 follow-up pass -- and this formulation never had the conditioning
problem that motivated the squared route in the first place), no GPU backend.
Forward only -- no adjoint, no inverse; see the package docstring for why.

The receiver-evaluation step (boundary -> physically distant Tx/Rx points) is
unchanged in spirit from ``gpr_bem_mod``: it was never part of the
finite-offset problem, so it stays a plain kernel sum against the same
boundary nodes and weights, no differencing or diagonal treatment needed
there at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import torch
from scipy.special import hankel1

from .ibim_geometry import ImplicitBoundaryBand2D, ImplicitBoundarySamples2D
from .ibim_tmz_forward import boundary_points_normals_weights, build_kdiff_operator_blocks
from .materials import Material
from .t_assembly import TAssembler, TAssemblyReport

__all__ = [
    "ImplicitTMzForwardResult",
    "ImplicitTMzFrequencySystem",
    "ImplicitTMzMultiFrequencyForwardResult",
    "build_ibim_tmz_frequency_system",
    "ibim_incident_trace_on_boundary",
    "solve_ibim_tmz_frequency_response",
    "solve_ibim_tmz_total_field_batch",
]


@dataclass
class ImplicitTMzFrequencySystem:
    angular_frequency: float
    k_exterior: complex
    k_interior: complex
    system_matrix: np.ndarray  # shape (1, 2N, 2N), leading axis kept for API parity with gpr_bem_mod
    num_boundary_samples: int
    boundary_points: np.ndarray
    boundary_normals: np.ndarray
    boundary_weights: np.ndarray
    formulation: str = "muller"
    normal_derivative_scheme: str = "kernel_diff"
    t_assembly_report: TAssemblyReport | None = None


def build_ibim_tmz_frequency_system(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    angular_frequency: float,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
    t_assembly: TAssembler | None = None,
) -> ImplicitTMzFrequencySystem:
    """Assemble the kernel-differenced Muller system directly on the real boundary.

    ``t_assembly`` changes only dT; S/D/K' and the Muller composition are
    shared. ``sdf_fn`` is forwarded for assemblers that need SDF geometry.
    """

    points, normals, weights = boundary_points_normals_weights(boundary)
    angular_frequency_value = float(angular_frequency)
    k_exterior = complex(exterior.wavenumber(angular_frequency_value, eps0, mu0))
    k_interior = complex(interior.wavenumber(angular_frequency_value, eps0, mu0))

    blocks = build_kdiff_operator_blocks(
        boundary, k_exterior, k_interior, sdf_fn=sdf_fn, t_assembly=t_assembly
    )
    num_nodes = blocks.num_boundary_samples
    identity = np.eye(num_nodes, dtype=complex)
    # Muller: identity survives, every block is exterior-minus-interior --
    # already true by construction here (the kernels were differenced before
    # any quadrature), unlike gpr_bem_mod where the difference is taken after
    # two separate finite-offset assemblies.
    upper_left = identity - blocks.double_layer_matrix
    lower_right = identity + blocks.adjoint_double_layer_matrix
    system_matrix = np.block(
        [
            [upper_left, blocks.single_layer_matrix],
            [-blocks.hypersingular_matrix, lower_right],
        ]
    )[None, :, :]

    return ImplicitTMzFrequencySystem(
        angular_frequency=angular_frequency_value,
        k_exterior=k_exterior,
        k_interior=k_interior,
        system_matrix=system_matrix,
        num_boundary_samples=num_nodes,
        boundary_points=points,
        boundary_normals=normals,
        boundary_weights=weights,
        t_assembly_report=blocks.t_assembly_report,
    )


def ibim_incident_trace_on_boundary(
    boundary_points: np.ndarray,
    boundary_normals: np.ndarray,
    source_points: np.ndarray,
    angular_frequency: float,
    source_strength,
    *,
    exterior: Material,
    eps0: float,
    mu0: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate the incident Dirichlet/Neumann traces on the boundary nodes.

    Closed-form line-source trace -- never involved the finite-offset problem
    (the source is genuinely off the boundary), so this is unchanged in spirit
    from ``gpr_bem_mod``'s version of the same function.
    """

    source_points_array = np.atleast_2d(np.asarray(source_points, dtype=float))
    strengths = np.atleast_1d(np.asarray(source_strength, dtype=complex))
    if strengths.shape[0] == 1 and source_points_array.shape[0] > 1:
        strengths = np.full(source_points_array.shape[0], strengths[0], dtype=complex)
    k_exterior = complex(exterior.wavenumber(float(angular_frequency), eps0, mu0))
    displacement = boundary_points[None, :, :] - source_points_array[:, None, :]
    distance = np.linalg.norm(displacement, axis=2)
    factor = np.einsum("bsd,sd->bs", displacement, boundary_normals) / distance
    dirichlet_kernel = 0.25j * hankel1(0, k_exterior * distance)
    neumann_kernel = -0.25j * k_exterior * hankel1(1, k_exterior * distance) * factor
    return strengths[:, None] * dirichlet_kernel, strengths[:, None] * neumann_kernel


@dataclass
class ImplicitTMzForwardResult:
    system: ImplicitTMzFrequencySystem
    source_points: np.ndarray
    receiver_points: np.ndarray
    source_strengths: np.ndarray
    dirichlet_total: np.ndarray
    neumann_total: np.ndarray
    incident_receiver: np.ndarray
    scattered_receiver: np.ndarray
    total_receiver: np.ndarray
    linear_system_relative_residual: float


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
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
    t_assembly: TAssembler | None = None,
) -> ImplicitTMzForwardResult:
    """Solve the kernel-differenced Muller system and evaluate at receivers.

    ``sdf_fn``, if given, is forwarded to ``build_ibim_tmz_frequency_system``
    for the exact-curvature diagonal fit -- optional for now.
    """

    source_points_array = np.atleast_2d(np.asarray(source_points, dtype=float))
    receiver_points_array = np.atleast_2d(np.asarray(receiver_points, dtype=float))
    if receiver_points_array.shape != source_points_array.shape:
        raise ValueError("receiver_points must have the same shape as source_points.")

    system = build_ibim_tmz_frequency_system(
        boundary,
        angular_frequency,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
        sdf_fn=sdf_fn,
        t_assembly=t_assembly,
    )
    dirichlet_incident, neumann_incident = ibim_incident_trace_on_boundary(
        system.boundary_points,
        system.boundary_normals,
        source_points_array,
        angular_frequency,
        source_strength,
        exterior=exterior,
        eps0=eps0,
        mu0=mu0,
    )
    rhs = np.concatenate((dirichlet_incident, neumann_incident), axis=1).T
    matrix = system.system_matrix[0]
    solution = np.linalg.solve(matrix, rhs)
    residual = np.linalg.norm(matrix @ solution - rhs) / np.linalg.norm(rhs)

    num_boundary = system.num_boundary_samples
    dirichlet_total = solution[:num_boundary].T
    neumann_total = solution[num_boundary:].T

    strengths = np.atleast_1d(np.asarray(source_strength, dtype=complex))
    if strengths.shape[0] == 1 and source_points_array.shape[0] > 1:
        strengths = np.full(source_points_array.shape[0], strengths[0], dtype=complex)
    source_receiver_distance = np.linalg.norm(receiver_points_array - source_points_array, axis=1)
    incident_receiver = strengths * (0.25j * hankel1(0, system.k_exterior * source_receiver_distance))

    displacement = receiver_points_array[:, None, :] - system.boundary_points[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    projection = np.einsum("mnd,nd->mn", displacement, system.boundary_normals) / distance
    green = 0.25j * hankel1(0, system.k_exterior * distance)
    green_normal = 0.25j * system.k_exterior * hankel1(1, system.k_exterior * distance) * projection
    # u_sc(x) = (D_e u - S_e q)(x). Bistatic pairing: receiver i only ever
    # uses the density solved for source i's own RHS column, so row i of
    # `green`/`green_normal` (receiver i's kernel row) multiplied elementwise
    # against row i of `neumann_total`/`dirichlet_total` (source i's solved
    # density) already gives exactly that -- no cross terms are ever formed.
    single_receiver = (green * neumann_total * system.boundary_weights[None, :]).sum(axis=-1)
    double_receiver = (green_normal * dirichlet_total * system.boundary_weights[None, :]).sum(axis=-1)
    scattered_receiver = double_receiver - single_receiver
    total_receiver = incident_receiver + scattered_receiver

    return ImplicitTMzForwardResult(
        system=system,
        source_points=source_points_array,
        receiver_points=receiver_points_array,
        source_strengths=strengths,
        dirichlet_total=dirichlet_total,
        neumann_total=neumann_total,
        incident_receiver=incident_receiver,
        scattered_receiver=np.asarray(scattered_receiver, dtype=complex),
        total_receiver=np.asarray(total_receiver, dtype=complex),
        linear_system_relative_residual=float(residual),
    )


@dataclass
class ImplicitTMzMultiFrequencyForwardResult:
    angular_frequencies: np.ndarray
    frequency_response: np.ndarray
    forwards: tuple


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
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
    t_assembly: TAssembler | None = None,
) -> ImplicitTMzMultiFrequencyForwardResult:
    frequency_array = np.atleast_1d(np.asarray(angular_frequencies, dtype=float))
    forwards = tuple(
        solve_ibim_tmz_total_field_batch(
            boundary, source_points, receiver_points, float(f), source_strength,
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            sdf_fn=sdf_fn,
            t_assembly=t_assembly,
        )
        for f in frequency_array
    )
    frequency_response = np.stack([forward.total_receiver for forward in forwards], axis=1)
    return ImplicitTMzMultiFrequencyForwardResult(
        angular_frequencies=frequency_array, frequency_response=frequency_response, forwards=forwards
    )
