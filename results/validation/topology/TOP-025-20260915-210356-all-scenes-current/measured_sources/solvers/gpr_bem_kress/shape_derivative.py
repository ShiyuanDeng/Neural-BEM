"""Opt-in derivatives of the *discrete*, solved single-interface Kress problem.

The parameter direction is real and the uniform native grid, period, topology,
source/receiver locations and near/direct kernel branch are fixed.  Geometry
directions are coherent position/derivative jets supplied by the caller; this
module does not refit or rephase them.  These are directional covectors, not a
continuous normal shape-gradient density or a neural/SDF update rule.

First-order analytic jets below differentiate the production power-log series
(including its truncation), Hankel/Bessel expressions, analytic diagonals,
normals and quadrature factors.  There are no finite-difference probes.  The
stored production A, B, C and solution are reused for tangent/adjoint solves;
primal reassembly discrepancies are reported to detect implementation drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np
from scipy.special import hankel1, jv

from periodic_kress import kress_log_weights

from ._kernels import EULER_GAMMA
from .forward import KressTMzForwardResult
from .system import _validate_supported_materials


def _readonly(value, *, dtype=np.complex128):
    result = np.array(value, dtype=dtype, copy=True)
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("Kress derivative produced non-finite values.")
    result.setflags(write=False)
    return result


def _real_array(value, *, name):
    if np.iscomplexobj(value):
        raise ValueError(f"{name} must be real-valued.")
    result = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite.")
    return _readonly(result, dtype=np.float64)


@dataclass(frozen=True)
class KressDirection:
    """Jets of one real parameter direction, on the base curve's native grid.

    Omit both position/first jets for a material/source-only direction.  Second
    and third jets are checked but currently unused by the actual cancelled
    difference operators.  ``source_strengths`` is a complex scalar or one
    complex direction per source.  Material entries are real epsr directions;
    conductivity, permeability, frequency and observation locations are fixed.
    """

    points: np.ndarray | None = None
    first_derivatives: np.ndarray | None = None
    second_derivatives: np.ndarray | None = None
    third_derivatives: np.ndarray | None = None
    exterior_epsr: float = 0.0
    interior_epsr: float = 0.0
    source_strengths: np.ndarray | complex | None = None

    def __post_init__(self):
        if (self.points is None) != (self.first_derivatives is None):
            raise ValueError("points and first_derivatives must be supplied together.")
        for name in ("points", "first_derivatives", "second_derivatives", "third_derivatives"):
            value = getattr(self, name)
            if value is not None:
                array = _real_array(value, name=name)
                if array.ndim != 2 or array.shape[1] != 2:
                    raise ValueError(f"{name} must have shape (num_nodes, 2).")
                object.__setattr__(self, name, array)
        for name in ("exterior_epsr", "interior_epsr"):
            value = _real_array(getattr(self, name), name=name)
            if value.ndim != 0:
                raise ValueError(f"{name} must be a scalar.")
            object.__setattr__(self, name, float(value))
        if self.source_strengths is not None:
            value = np.atleast_1d(np.asarray(self.source_strengths, dtype=np.complex128))
            if value.ndim != 1 or value.size == 0 or not np.all(np.isfinite(value)):
                raise ValueError("source_strengths must be a finite scalar or vector.")
            object.__setattr__(self, "source_strengths", _readonly(value))


class _Jet:
    """Small forward analytic jet; only operations used by production kernels."""

    __array_priority__ = 1000

    def __init__(self, value, tangent=0.0):
        self.v = np.asarray(value)
        self.d = np.broadcast_to(
            np.asarray(tangent, dtype=np.result_type(self.v, tangent)), self.v.shape
        )

    def __getitem__(self, index):
        return _Jet(self.v[index], self.d[index])

    def __add__(self, other):
        other = _as_jet(other)
        return _Jet(self.v + other.v, self.d + other.d)

    __radd__ = __add__

    def __neg__(self):
        return _Jet(-self.v, -self.d)

    def __sub__(self, other):
        return self + (-_as_jet(other))

    def __rsub__(self, other):
        return _as_jet(other) - self

    def __mul__(self, other):
        other = _as_jet(other)
        return _Jet(self.v * other.v, self.d * other.v + self.v * other.d)

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = _as_jet(other)
        return _Jet(self.v / other.v, (self.d - self.v / other.v * other.d) / other.v)

    def __rtruediv__(self, other):
        return _as_jet(other) / self

    def __pow__(self, power):
        if power == 0:
            return _Jet(np.ones_like(self.v))
        return _Jet(self.v**power, power * self.v ** (power - 1) * self.d)


def _as_jet(value):
    return value if isinstance(value, _Jet) else _Jet(value)


def _sum(value, axis=-1):
    return _Jet(np.sum(value.v, axis=axis), np.sum(value.d, axis=axis))


def _norm(value):
    magnitude = np.linalg.norm(value.v, axis=-1)
    return _Jet(magnitude, np.sum(value.v * value.d, axis=-1) / magnitude)


def _log(value):
    return _Jet(np.log(value.v), value.d / value.v)


def _special(function, order, value):
    primal = function(order, value.v)
    derivative = 0.5 * (function(order - 1, value.v) - function(order + 1, value.v))
    return _Jet(primal, derivative * value.d)


def _series_radial(r, ko, ki, terms):
    """Differentiate exactly _kernels._series_radial_differences, not its limit."""
    result = [_Jet(np.zeros(r.v.shape, dtype=np.complex128)) for _ in range(6)]
    co = ci = _Jet(1.0 + 0.0j)
    harmonic = 0.0
    log_r, log_ko, log_ki = _log(r), _log(ko), _log(ki)
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
        result[0] = result[0] + r**power * value
        result[3] = result[3] + r**power * p_log
        if mode:
            factor = r ** (power - 2)
            result[1] = result[1] + factor * (power * value + p_log)
            result[2] = result[2] + factor * (
                power * (power - 2) * value + (2 * power - 2) * p_log
            )
            result[4] = result[4] + factor * power * p_log
            result[5] = result[5] + factor * power * (power - 2) * p_log
        co = co * (-0.25 * ko**2 / (mode + 1) ** 2)
        ci = ci * (-0.25 * ki**2 / (mode + 1) ** 2)
    return result


def _direct_radial(r, ko, ki):
    zo, zi = ko * r, ki * r
    dh0 = _special(hankel1, 0, zo) - _special(hankel1, 0, zi)
    dh1 = ko * _special(hankel1, 1, zo) - ki * _special(hankel1, 1, zi)
    dh2 = ko**2 * _special(hankel1, 2, zo) - ki**2 * _special(hankel1, 2, zi)
    dj0 = _special(jv, 0, zo) - _special(jv, 0, zi)
    dj1 = ko * _special(jv, 1, zo) - ki * _special(jv, 1, zi)
    dj2 = ko**2 * _special(jv, 2, zo) - ki**2 * _special(jv, 2, zi)
    scale = -1.0 / (2.0 * np.pi)
    return [0.25j * dh0, -0.25j * dh1 / r, 0.25j * dh2,
            scale * dj0, -scale * dj1 / r, scale * dj2]


def _radial(r, ko, ki, config):
    argument = max(abs(complex(ko.v)), abs(complex(ki.v))) * r.v
    near = argument <= config.near_argument
    result = [_Jet(np.zeros(r.v.shape, dtype=np.complex128)) for _ in range(6)]
    # Do not copy the primal's equality shortcut: unequal material tangents at
    # zero contrast still have nonzero derivatives of the cancelled kernels.
    for mask, evaluator in ((near, _series_radial), (~near, _direct_radial)):
        if not np.any(mask):
            continue
        values = (evaluator(r[mask], ko, ki, config.series_terms)
                  if evaluator is _series_radial else evaluator(r[mask], ko, ki))
        for target, source in zip(result, values):
            target.v[mask] = source.v
            # The jet constructor broadcasts its zero tangent read-only.
            derivative = target.d.copy()
            derivative[mask] = source.d
            target.d = derivative
    return result, {
        "near_pair_count": int(np.count_nonzero(near)),
        "direct_pair_count": int(np.count_nonzero(~near)),
        "minimum_branch_margin": float(np.min(np.abs(argument - config.near_argument))),
        "branch_policy": "fixed_at_base",
        "near_argument": config.near_argument,
        "series_terms": config.series_terms,
        "zero_contrast_base": bool(ko.v == ki.v),
    }


def _difference_matrices(points, normals, speed, ko, ki, config):
    count = points.v.shape[0]
    rows, columns = np.nonzero(~np.eye(count, dtype=bool))
    displacement = points[rows] - points[columns]
    distance = _norm(displacement)
    tx = _sum(displacement * normals[rows])
    sy = _sum(displacement * normals[columns])
    nn = _sum(normals[rows] * normals[columns])
    (g, f, a, glog, flog, alog), diagnostics = _radial(distance, ko, ki, config)
    projection = tx * sy / distance**2
    kernels = (g, -f * sy, f * tx, -f * nn - a * projection)
    logarithms = (glog, -flog * sy, flog * tx, -flog * nn - alog * projection)
    h = 2.0 * np.pi / count
    weights = kress_log_weights(count)
    offsets = (rows - columns) % count
    periodic_log = np.log(4.0 * np.sin(np.pi * offsets / count) ** 2)
    correction = 0.5 * (weights[offsets] - h * periodic_log)
    delta = ko**2 - ki**2
    log_coefficient = -delta / (4.0 * np.pi)
    smooth_coefficient = 0.125j * delta - (
        delta * (EULER_GAMMA - 0.5 - np.log(2.0))
        + ko**2 * _log(ko) - ki**2 * _log(ki)
    ) / (4.0 * np.pi)
    zero = _Jet(np.zeros(count, dtype=np.complex128))
    diagonal_log = (zero, zero, zero, 0.5 * log_coefficient * speed)
    diagonal_smooth = (
        speed * (_log(ki) - _log(ko)) / (2.0 * np.pi), zero, zero,
        speed * (smooth_coefficient + log_coefficient * _log(speed)),
    )
    matrices = []
    diagonal = np.arange(count)
    for kernel, logarithm, dlog, dsmooth in zip(kernels, logarithms, diagonal_log, diagonal_smooth):
        entries = speed[columns] * (h * kernel + correction * logarithm)
        diag_entries = weights[0] * dlog + h * dsmooth
        values = np.zeros((count, count), dtype=np.complex128)
        tangents = values.copy()
        values[rows, columns], tangents[rows, columns] = entries.v, entries.d
        values[diagonal, diagonal], tangents[diagonal, diagonal] = diag_entries.v, diag_entries.d
        matrices.append(_Jet(values, tangents))
    return matrices, diagnostics


def _stack(values, axis):
    return _Jet(np.concatenate([v.v for v in values], axis=axis),
                np.concatenate([v.d for v in values], axis=axis))


@dataclass(frozen=True)
class _DirectionalOperators:
    d_system_matrix: np.ndarray
    d_right_hand_side: np.ndarray
    d_receiver_matrix: np.ndarray
    d_incident_receiver: np.ndarray
    diagnostics: Mapping[str, object]


def _validate_base(base):
    if not isinstance(base, KressTMzForwardResult):
        raise TypeError("base must be a KressTMzForwardResult.")
    _validate_supported_materials(base.exterior_material, base.interior_material)
    for material in (base.exterior_material, base.interior_material):
        epsr = np.asarray(material.epsr)
        if np.iscomplexobj(epsr) or epsr.ndim != 0 or not np.isfinite(epsr) or epsr <= 0:
            raise ValueError("The epsr derivative currently requires positive real lossless epsr.")


def _directional_operators(base, direction):
    started = perf_counter()
    _validate_base(base)
    if not isinstance(direction, KressDirection):
        raise TypeError("direction must be a KressDirection.")
    curve = base.system.geometry
    count = curve.num_nodes
    for name in ("points", "first_derivatives", "second_derivatives", "third_derivatives"):
        array = getattr(direction, name)
        if array is not None and array.shape != (count, 2):
            raise ValueError(f"direction.{name} must have shape ({count}, 2).")
    points = _Jet(curve.points, 0.0 if direction.points is None else direction.points)
    first = _Jet(curve.first_derivatives,
                 0.0 if direction.first_derivatives is None else direction.first_derivatives)
    native_speed = _norm(first)
    tangent = first / native_speed[:, None]
    normals = _Jet(np.column_stack((tangent.v[:, 1], -tangent.v[:, 0])),
                   np.column_stack((tangent.d[:, 1], -tangent.d[:, 0])))
    theta_speed = native_speed * (curve.period / (2.0 * np.pi))
    arc = theta_speed * (2.0 * np.pi / count)
    ko = _Jet(complex(base.system.k_exterior),
              base.system.k_exterior * direction.exterior_epsr / (2.0 * base.exterior_material.epsr))
    ki = _Jet(complex(base.system.k_interior),
              base.system.k_interior * direction.interior_epsr / (2.0 * base.interior_material.epsr))
    (v, k, kp, t), diagnostics = _difference_matrices(
        points, normals, theta_speed, ko, ki, base.system.assembly_config
    )
    identity = np.eye(count)
    system = _stack((_stack((identity - k, v), 1), _stack((-t, identity + kp), 1)), 0)
    strength_direction = direction.source_strengths
    if strength_direction is None:
        strength_direction = np.zeros_like(base.source_strengths)
    elif strength_direction.size == 1:
        strength_direction = np.full(base.source_strengths.shape, strength_direction[0])
    elif strength_direction.shape != base.source_strengths.shape:
        raise ValueError("direction.source_strengths must be scalar or one value per source.")
    strength = _Jet(base.source_strengths, strength_direction)
    source_displacement = points[None, :, :] - base.source_points[:, None, :]
    source_distance = _norm(source_displacement)
    source_projection = _sum(source_displacement * normals[None, :, :]) / source_distance
    incident_d = strength[:, None] * 0.25j * _special(hankel1, 0, ko * source_distance)
    incident_n = -strength[:, None] * 0.25j * ko * _special(hankel1, 1, ko * source_distance) * source_projection
    rhs_rows = _stack((incident_d, incident_n), 1)
    rhs = _Jet(rhs_rows.v.T, rhs_rows.d.T)
    receiver_displacement = base.receiver_points[:, None, :] - points[None, :, :]
    receiver_distance = _norm(receiver_displacement)
    receiver_projection = _sum(receiver_displacement * normals[None, :, :]) / receiver_distance
    single = 0.25j * _special(hankel1, 0, ko * receiver_distance) * arc[None, :]
    double = 0.25j * ko * _special(hankel1, 1, ko * receiver_distance) * receiver_projection * arc[None, :]
    receiver = _stack((double, -single), 1)
    direct_distance = np.linalg.norm(base.receiver_points[None, :, :] - base.source_points[:, None, :], axis=-1)
    direct = strength[:, None] * 0.25j * _special(hankel1, 0, ko * direct_distance)
    for label, reassembled, stored in (
        ("system_matrix", system.v, base.system.system_matrix),
        ("right_hand_side", rhs.v, base.right_hand_side),
        ("receiver_matrix", receiver.v, base.receiver_operator.state_rows),
        ("incident_receiver", direct.v, base.incident_receiver),
    ):
        error = float(np.linalg.norm(reassembled - stored))
        scale = max(float(np.linalg.norm(stored)), float(np.linalg.norm(reassembled)), np.finfo(float).tiny)
        diagnostics[f"primal_{label}_relative_error"] = error / scale
        # No unit-scale absolute allowance: line-source amplitudes can be tiny.
        if not np.isfinite(error) or error > 2.0e-11 * scale + np.finfo(float).tiny:
            raise ValueError(f"Derivative primal {label} no longer matches the stored production forward result.")
    diagnostics["operator_seconds"] = float(perf_counter() - started)
    diagnostics["geometry_dependence"] = "points_and_native_first_jets; fixed_period_and_grid"
    diagnostics["finite_difference_probes"] = 0
    return _DirectionalOperators(
        _readonly(system.d), _readonly(rhs.d), _readonly(receiver.d),
        _readonly(direct.d), MappingProxyType(diagnostics),
    )


@dataclass(frozen=True)
class KressForwardJVP:
    """Actual discrete directional derivative; receiver arrays have shape (S,R)."""

    d_system_matrix: np.ndarray
    d_right_hand_side: np.ndarray
    d_receiver_matrix: np.ndarray
    d_solution: np.ndarray
    d_incident_receiver: np.ndarray
    d_scattered_receiver: np.ndarray
    d_total_receiver: np.ndarray
    diagnostics: Mapping[str, object]


def linearize_kress_forward(base: KressTMzForwardResult, direction: KressDirection) -> KressForwardJVP:
    """One analytic operator JVP and one stored-system tangent solve (all RHS)."""
    started = perf_counter()
    operators = _directional_operators(base, direction)
    solve_started = perf_counter()
    solution_direction = np.linalg.solve(
        base.system.system_matrix,
        operators.d_right_hand_side - operators.d_system_matrix @ base.solution,
    )
    solve_seconds = float(perf_counter() - solve_started)
    scattered = (operators.d_receiver_matrix @ base.solution
                 + base.receiver_operator.state_rows @ solution_direction).T
    diagnostics = dict(operators.diagnostics)
    diagnostics.update(tangent_solve_count=1, tangent_solve_seconds=solve_seconds,
                       total_seconds=float(perf_counter() - started))
    return KressForwardJVP(
        operators.d_system_matrix, operators.d_right_hand_side,
        operators.d_receiver_matrix, _readonly(solution_direction),
        operators.d_incident_receiver, _readonly(scattered),
        _readonly(scattered + operators.d_incident_receiver), MappingProxyType(diagnostics),
    )


@dataclass(frozen=True)
class KressPairedObjectiveAdjoint:
    """Reusable conjugate adjoint for a fixed real-stacked residual objective.

    ``loss = .5 ||residual||²``. ``residual`` is the *transformed* real vector;
    ``prediction`` and ``observed`` have shape (paired rows, frequencies).
    The transform is fixed (including any observation-derived normalization).
    Directional contraction performs no tangent solve and returns a real scalar,
    not a nodal normal-density estimate.  No regularizer is silently added.
    """

    base_results: tuple[KressTMzForwardResult, ...]
    observed: np.ndarray
    source_indices: np.ndarray
    receiver_indices: np.ndarray
    observable: str
    residual_transform: np.ndarray
    prediction: np.ndarray
    residual: np.ndarray
    loss: float
    adjoints: tuple[np.ndarray, ...]
    receiver_cotangents: tuple[np.ndarray, ...]
    diagnostics: Mapping[str, object]

    def directional_derivative(self, direction: KressDirection | Sequence[KressDirection]) -> float:
        """Contract one shared or one-per-frequency real parameter direction."""
        directions = ((direction,) * len(self.base_results) if isinstance(direction, KressDirection)
                      else tuple(direction))
        if len(directions) != len(self.base_results):
            raise ValueError("Supply one direction or exactly one direction per frequency.")
        total = 0.0
        for base, local, adjoint, cotangent in zip(
            self.base_results, directions, self.adjoints, self.receiver_cotangents
        ):
            operators = _directional_operators(base, local)
            receiver_term = operators.d_receiver_matrix @ base.solution
            if self.observable == "total":
                receiver_term = receiver_term + operators.d_incident_receiver.T
            total += float(np.real(
                np.vdot(cotangent, receiver_term)
                + np.vdot(adjoint, operators.d_right_hand_side - operators.d_system_matrix @ base.solution)
            ))
        if not np.isfinite(total):
            raise FloatingPointError("Paired objective directional derivative is non-finite.")
        return total


def _indices(value, *, name):
    result = np.asarray(value)
    if result.ndim != 1 or result.size == 0 or result.dtype.kind not in "iu":
        raise ValueError(f"{name} must be a nonempty one-dimensional integer array.")
    if np.any(result < 0):
        raise ValueError(f"{name} must contain non-negative indices.")
    if result.dtype.kind == "u" and np.any(result > np.uint64(np.iinfo(np.int64).max)):
        raise ValueError(f"{name} indices exceed the supported integer range.")
    return _readonly(result, dtype=np.int64)


def build_paired_objective_adjoint(
    base_results: Sequence[KressTMzForwardResult],
    observed,
    source_indices,
    receiver_indices,
    *,
    residual_transform=None,
    observable: str = "scattered",
) -> KressPairedObjectiveAdjoint:
    """Build one adjoint per frequency for .5||L [Re(z-y); Im(z-y)]||².

    Both real and imaginary parts are flattened in C order (paired row first,
    frequency second), then concatenated. L may be any finite real 2D matrix
    with 2*P*F columns, including rank-deficient/zero weighting. The selection
    adjoint accumulates repeated (source,receiver) rows with ``np.add.at``.
    """
    started = perf_counter()
    bases = tuple(base_results)
    if not bases:
        raise ValueError("base_results must contain at least one frequency.")
    if observable not in ("scattered", "total"):
        raise ValueError("observable must be 'scattered' or 'total'.")
    sources = _indices(source_indices, name="source_indices")
    receivers = _indices(receiver_indices, name="receiver_indices")
    if sources.shape != receivers.shape:
        raise ValueError("source_indices and receiver_indices must have the same shape.")
    for base in bases:
        _validate_base(base)
        if np.any(sources >= base.source_points.shape[0]) or np.any(receivers >= base.receiver_points.shape[0]):
            raise ValueError("Paired selection is outside a base forward result's acquisition.")
    observation = np.asarray(observed, dtype=np.complex128)
    expected_shape = (sources.size, len(bases))
    if observation.shape != expected_shape or not np.all(np.isfinite(observation)):
        raise ValueError(f"observed must be finite with shape {expected_shape}.")
    prediction = np.column_stack([
        getattr(base, f"{observable}_receiver")[sources, receivers] for base in bases
    ])
    difference = prediction - observation
    real_difference = np.concatenate((difference.real.ravel(), difference.imag.ravel()))
    transform = (np.eye(real_difference.size) if residual_transform is None
                 else _real_array(residual_transform, name="residual_transform"))
    if transform.ndim != 2 or transform.shape[1] != real_difference.size or transform.shape[0] == 0:
        raise ValueError("residual_transform must have shape (nonzero rows, 2*P*F).")
    residual = transform @ real_difference
    real_cotangent = transform.T @ residual
    size = prediction.size
    paired_cotangent = (real_cotangent[:size] + 1j * real_cotangent[size:]).reshape(expected_shape)
    adjoints, receiver_cotangents = [], []
    solve_started = perf_counter()
    for frequency, base in enumerate(bases):
        cotangent = np.zeros((base.receiver_points.shape[0], base.source_points.shape[0]), dtype=np.complex128)
        np.add.at(cotangent, (receivers, sources), paired_cotangent[:, frequency])
        adjoint = np.linalg.solve(
            base.system.system_matrix.conj().T,
            base.receiver_operator.state_rows.conj().T @ cotangent,
        )
        adjoints.append(_readonly(adjoint))
        receiver_cotangents.append(_readonly(cotangent))
    loss = float(0.5 * np.dot(residual, residual))
    if not np.isfinite(loss):
        raise FloatingPointError("Paired objective loss is non-finite.")
    diagnostics = MappingProxyType({
        "adjoint_solve_count": len(bases), "tangent_solve_count": 0,
        "finite_difference_probes": 0,
        "adjoint_solve_seconds": float(perf_counter() - solve_started),
        "total_seconds": float(perf_counter() - started),
        "real_stacking": "concatenate(real.ravel_C, imag.ravel_C)",
    })
    return KressPairedObjectiveAdjoint(
        bases, _readonly(observation), sources, receivers, observable,
        _readonly(transform, dtype=np.float64), _readonly(prediction),
        _readonly(residual, dtype=np.float64), loss, tuple(adjoints),
        tuple(receiver_cotangents), diagnostics,
    )


# The established implementation already accepts arbitrary rectangular
# acquisition selections and accumulates duplicates in a full R-by-S
# cotangent. Give that capability an explicit name without another adjoint.
KressIndexedObjectiveAdjoint = KressPairedObjectiveAdjoint


def build_indexed_objective_adjoint(
    base_results: Sequence[KressTMzForwardResult],
    observed,
    source_indices,
    receiver_indices,
    *,
    residual_transform=None,
    observable: str = "scattered",
) -> KressIndexedObjectiveAdjoint:
    """Use the existing conjugate adjoint for arbitrary indexed observations.

    Each measurement is ``full_response[source_indices[m], receiver_indices[m]]``.
    Duplicate measurements accumulate rather than overwrite cotangents. Both
    real and imaginary arrays use C order (measurement first, frequency second)
    before concatenation. The paired entry point retains its existing behavior.
    """

    return build_paired_objective_adjoint(
        base_results, observed, source_indices, receiver_indices,
        residual_transform=residual_transform, observable=observable,
    )


__all__ = ["KressDirection", "KressForwardJVP", "KressPairedObjectiveAdjoint",
           "KressIndexedObjectiveAdjoint", "linearize_kress_forward",
           "build_paired_objective_adjoint", "build_indexed_objective_adjoint"]
