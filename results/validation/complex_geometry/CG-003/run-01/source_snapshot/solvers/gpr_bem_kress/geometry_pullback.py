"""Reverse geometry derivative of the solved discrete Kress objective.

This is the reverse counterpart of :mod:`shape_derivative`: it contracts the
stored forward and adjoint states with the actual Kress kernel assembly, then
differentiates that scalar in one reverse pass per frequency.  The returned
arrays are covectors on *independent native position and first-derivative
jets*.  They must be composed with a coherent curve construction before use;
they are neither point velocities nor an arclength-normalized shape density.

The native grid, period, material, acquisition, and near/direct kernel branches
are fixed.  Normals, speeds, quadrature factors and analytic diagonals are all
differentiated.  SciPy supplies the same special-function primal evaluations as
the forward solver, with their analytic derivative in PyTorch's reverse pass.
No perturbed forward solves, finite differences, or tangent solves are used.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import numpy as np
from scipy.special import hankel1, jv

from periodic_kress import kress_log_weights

from ._kernels import EULER_GAMMA
from .shape_derivative import KressPairedObjectiveAdjoint, _real_array, _validate_base


@dataclass(frozen=True)
class KressGeometryPullback:
    """Real covectors, summed over frequencies sharing one native geometry.

    ``d(loss) = sum(points * dx) + sum(first_derivatives * d(dx/dt))``.
    These already contain all discrete quadrature and objective weights; do
    not multiply them by boundary weights a second time.
    """

    points: np.ndarray
    first_derivatives: np.ndarray
    diagnostics: Mapping[str, object]

    def contract(self, points, first_derivatives) -> float:
        """Contract a coherent native curve jet with this covector."""
        result = 0.0
        for name, value in (("points", points), ("first_derivatives", first_derivatives)):
            array = _real_array(value, name=name)
            covector = getattr(self, name)
            if array.shape != covector.shape:
                raise ValueError(f"{name} must have shape {covector.shape}.")
            result += float(np.sum(covector * array))
        return result


def _special_function(torch):
    class SpecialFunction(torch.autograd.Function):
        @staticmethod
        def forward(ctx, argument, order, family):
            function = hankel1 if family == "hankel" else jv
            value = argument.detach().numpy()
            derivative = 0.5 * (function(order - 1, value) - function(order + 1, value))
            ctx.save_for_backward(torch.as_tensor(np.asarray(derivative), dtype=argument.dtype))
            return torch.as_tensor(np.asarray(function(order, value)), dtype=argument.dtype)

        @staticmethod
        def backward(ctx, cotangent):
            (derivative,) = ctx.saved_tensors
            return cotangent * derivative.conj(), None, None

    return SpecialFunction.apply


def _series_radial(torch, radius, ko, ki, terms):
    result = [torch.zeros_like(radius, dtype=torch.complex128) for _ in range(6)]
    co = ci = 1.0 + 0.0j
    harmonic = 0.0
    log_r, log_ko, log_ki = torch.log(radius), np.log(ko), np.log(ki)
    for mode in range(terms):
        if mode:
            harmonic += 1.0 / mode
        difference = co - ci
        p_log = -difference / (2.0 * np.pi)
        q_smooth = difference * (
            0.25j + (np.log(2.0) - EULER_GAMMA + harmonic) / (2.0 * np.pi)
        ) + (ci * log_ki - co * log_ko) / (2.0 * np.pi)
        power = 2 * mode
        value = p_log * log_r + q_smooth
        result[0] = result[0] + radius**power * value
        result[3] = result[3] + radius**power * p_log
        if mode:
            factor = radius ** (power - 2)
            result[1] = result[1] + factor * (power * value + p_log)
            result[2] = result[2] + factor * (
                power * (power - 2) * value + (2 * power - 2) * p_log
            )
            result[4] = result[4] + factor * power * p_log
            result[5] = result[5] + factor * power * (power - 2) * p_log
        co *= -0.25 * ko**2 / (mode + 1) ** 2
        ci *= -0.25 * ki**2 / (mode + 1) ** 2
    return result


def _direct_radial(special, radius, ko, ki):
    zo, zi = ko * radius, ki * radius
    dh0 = special(zo, 0, "hankel") - special(zi, 0, "hankel")
    dh1 = ko * special(zo, 1, "hankel") - ki * special(zi, 1, "hankel")
    dh2 = ko**2 * special(zo, 2, "hankel") - ki**2 * special(zi, 2, "hankel")
    dj0 = special(zo, 0, "bessel") - special(zi, 0, "bessel")
    dj1 = ko * special(zo, 1, "bessel") - ki * special(zi, 1, "bessel")
    dj2 = ko**2 * special(zo, 2, "bessel") - ki**2 * special(zi, 2, "bessel")
    scale = -1.0 / (2.0 * np.pi)
    return (0.25j * dh0, -0.25j * dh1 / radius, 0.25j * dh2,
            scale * dj0, -scale * dj1 / radius, scale * dj2)


def _difference_matrices(torch, special, points, normals, speed, ko, ki, config):
    count = points.shape[0]
    rows, columns = np.nonzero(~np.eye(count, dtype=bool))
    displacement = points[rows] - points[columns]
    radius = torch.linalg.vector_norm(displacement, dim=-1)
    tx = torch.sum(displacement * normals[rows], dim=-1)
    sy = torch.sum(displacement * normals[columns], dim=-1)
    nn = torch.sum(normals[rows] * normals[columns], dim=-1)
    argument = max(abs(ko), abs(ki)) * radius.detach().numpy()
    near = argument <= config.near_argument
    radial = [torch.zeros_like(radius, dtype=torch.complex128) for _ in range(6)]
    for mask, series in ((near, True), (~near, False)):
        if not np.any(mask):
            continue
        local = (_series_radial(torch, radius[mask], ko, ki, config.series_terms)
                 if series else _direct_radial(special, radius[mask], ko, ki))
        for index, values in enumerate(local):
            radial[index] = radial[index].index_put((torch.as_tensor(mask),), values)
    g, f, a, glog, flog, alog = radial
    projection = tx * sy / radius**2
    kernels = (g, -f * sy, f * tx, -f * nn - a * projection)
    logarithms = (glog, -flog * sy, flog * tx, -flog * nn - alog * projection)
    h = 2.0 * np.pi / count
    weights = kress_log_weights(count)
    offsets = (rows - columns) % count
    periodic_log = np.log(4.0 * np.sin(np.pi * offsets / count) ** 2)
    correction = torch.as_tensor(0.5 * (weights[offsets] - h * periodic_log))
    delta = ko**2 - ki**2
    log_coefficient = -delta / (4.0 * np.pi)
    smooth_coefficient = 0.125j * delta - (
        delta * (EULER_GAMMA - 0.5 - np.log(2.0))
        + ko**2 * np.log(ko) - ki**2 * np.log(ki)
    ) / (4.0 * np.pi)
    zero = torch.zeros(count, dtype=torch.complex128)
    diagonal_log = (zero, zero, zero, 0.5 * log_coefficient * speed)
    diagonal_smooth = (
        speed * (np.log(ki) - np.log(ko)) / (2.0 * np.pi), zero, zero,
        speed * (smooth_coefficient + log_coefficient * torch.log(speed)),
    )
    matrices = []
    diagonal = np.arange(count)
    for kernel, logarithm, dlog, dsmooth in zip(kernels, logarithms, diagonal_log, diagonal_smooth):
        entries = speed[columns] * (h * kernel + correction * logarithm)
        diag_entries = weights[0] * dlog + h * dsmooth
        matrix = torch.zeros((count, count), dtype=torch.complex128)
        matrix[rows, columns] = entries
        matrix[diagonal, diagonal] = diag_entries
        matrices.append(matrix)
    diagnostics = {
        "near_pair_count": int(np.count_nonzero(near)),
        "direct_pair_count": int(np.count_nonzero(~near)),
        "minimum_branch_margin": float(np.min(np.abs(argument - config.near_argument))),
        "branch_policy": "fixed_at_base",
    }
    return matrices, diagnostics


def _local_pullback(torch, special, base, adjoint, cotangent):
    curve = base.system.geometry
    points = torch.tensor(curve.points, dtype=torch.float64, requires_grad=True)
    first = torch.tensor(curve.first_derivatives, dtype=torch.float64, requires_grad=True)
    native_speed = torch.linalg.vector_norm(first, dim=-1)
    tangent = first / native_speed[:, None]
    normals = torch.stack((tangent[:, 1], -tangent[:, 0]), dim=1)
    theta_speed = native_speed * (curve.period / (2.0 * np.pi))
    arc = theta_speed * (2.0 * np.pi / curve.num_nodes)
    ko, ki = complex(base.system.k_exterior), complex(base.system.k_interior)
    (v, k, kp, t), diagnostics = _difference_matrices(
        torch, special, points, normals, theta_speed, ko, ki, base.system.assembly_config
    )
    identity = torch.eye(curve.num_nodes, dtype=torch.complex128)
    system = torch.cat((torch.cat((identity - k, v), dim=1),
                        torch.cat((-t, identity + kp), dim=1)), dim=0)
    source = torch.tensor(base.source_points, dtype=torch.float64)
    strength = torch.tensor(base.source_strengths, dtype=torch.complex128)
    source_displacement = points[None, :, :] - source[:, None, :]
    source_distance = torch.linalg.vector_norm(source_displacement, dim=-1)
    source_projection = torch.sum(source_displacement * normals[None, :, :], dim=-1) / source_distance
    incident_d = strength[:, None] * 0.25j * special(ko * source_distance, 0, "hankel")
    incident_n = -strength[:, None] * 0.25j * ko * special(ko * source_distance, 1, "hankel") * source_projection
    rhs = torch.cat((incident_d, incident_n), dim=1).T
    receiver_points = torch.tensor(base.receiver_points, dtype=torch.float64)
    displacement = receiver_points[:, None, :] - points[None, :, :]
    distance = torch.linalg.vector_norm(displacement, dim=-1)
    projection = torch.sum(displacement * normals[None, :, :], dim=-1) / distance
    single = 0.25j * special(ko * distance, 0, "hankel") * arc[None, :]
    double = 0.25j * ko * special(ko * distance, 1, "hankel") * projection * arc[None, :]
    receiver = torch.cat((double, -single), dim=1)
    for label, reassembled, stored in (
        ("system_matrix", system, base.system.system_matrix),
        ("right_hand_side", rhs, base.right_hand_side),
        ("receiver_matrix", receiver, base.receiver_operator.state_rows),
    ):
        rebuilt = reassembled.detach().numpy()
        error = float(np.linalg.norm(rebuilt - stored))
        scale = max(float(np.linalg.norm(stored)), float(np.linalg.norm(rebuilt)), np.finfo(float).tiny)
        diagnostics[f"primal_{label}_relative_error"] = error / scale
        if not np.isfinite(error) or error > 2.0e-11 * scale + np.finfo(float).tiny:
            raise ValueError(f"Geometry pullback primal {label} no longer matches the stored production forward result.")
    state = torch.tensor(base.solution, dtype=torch.complex128)
    dual = torch.tensor(adjoint, dtype=torch.complex128)
    receiver_dual = torch.tensor(cotangent, dtype=torch.complex128)
    # The incident receiver term is independent of geometry for both choices
    # of observable, so total and scattered share this geometry contraction.
    scalar = torch.real(torch.sum(receiver_dual.conj() * (receiver @ state))
                        + torch.sum(dual.conj() * (rhs - system @ state)))
    point_covector, first_covector = torch.autograd.grad(scalar, (points, first))
    return point_covector.detach().numpy(), first_covector.detach().numpy(), diagnostics


def build_kress_geometry_pullback(adjoint: KressPairedObjectiveAdjoint) -> KressGeometryPullback:
    """Pull a paired real objective back to its shared Kress geometry jets.

    The supplied object has already solved one adjoint per frequency. This
    routine performs only kernel assembly and reverse differentiation.  The
    caller composes the resulting covectors with its curve/MLP map, including
    any fitting, reparameterization or extraction derivative it requires.
    """
    if not isinstance(adjoint, KressPairedObjectiveAdjoint):
        raise TypeError("adjoint must be a KressPairedObjectiveAdjoint.")
    if not adjoint.base_results:
        raise ValueError("The adjoint must contain at least one base result.")
    # Import on demand: pure Kress forward/JVP users do not depend on PyTorch.
    import torch

    started = perf_counter()
    curve = adjoint.base_results[0].system.geometry
    point_covector = np.zeros_like(curve.points)
    first_covector = np.zeros_like(curve.first_derivatives)
    local_diagnostics = []
    special = _special_function(torch)
    with torch.enable_grad():
        for base, dual, cotangent in zip(
            adjoint.base_results, adjoint.adjoints, adjoint.receiver_cotangents
        ):
            _validate_base(base)
            local = base.system.geometry
            if (local.period != curve.period
                    or not np.array_equal(local.parameters, curve.parameters)
                    or not np.array_equal(local.points, curve.points)
                    or not np.array_equal(local.first_derivatives, curve.first_derivatives)):
                raise ValueError("Geometry pullback requires identical native geometry at every frequency.")
            points, first, diagnostics = _local_pullback(torch, special, base, dual, cotangent)
            point_covector += points
            first_covector += first
            local_diagnostics.append(MappingProxyType(diagnostics))
    return KressGeometryPullback(
        _real_array(point_covector, name="point covector"),
        _real_array(first_covector, name="first-derivative covector"),
        MappingProxyType({
            "adjoint_solve_count": 0, "tangent_solve_count": 0,
            "finite_difference_probes": 0,
            "reverse_pass_count": len(adjoint.base_results),
            "geometry_dependence": "points_and_native_first_jets; fixed_period_and_grid",
            "covector_convention": "sum(point_covector*dx)+sum(first_covector*d_first)",
            "frequency_diagnostics": tuple(local_diagnostics),
            "total_seconds": float(perf_counter() - started),
        }),
    )


__all__ = ["KressGeometryPullback", "build_kress_geometry_pullback"]
