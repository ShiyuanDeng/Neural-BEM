"""Independent cylindrical-harmonic reference for penetrable circles.

The module is intentionally self contained.  In particular, it does not use
the boundary-integral kernels, assembly, or forward operators from any of the
``gpr_bem_*`` packages.  It provides a second numerical route for validating
multi-component forward solvers when every component is a circle made from
the same material.

The time convention is the one used by the rest of this repository: the
outgoing two-dimensional Green function is

``G(x, y) = 0.25j * H_0^(1)(k * |x-y|)``.

For cylinder ``p``, the exterior scattered field is expanded as

``sum_n a[p,n] H_n^(1)(k_e r_p) exp(1j*n*theta_p)``.

Graf's addition theorem converts every other cylinder's outgoing expansion to
a regular Bessel expansion about ``p``.  Applying the exact diagonal circular
transmission T-matrix then produces one dense multiple-scattering system for
the outgoing coefficients.  Interior coefficients are eliminated locally;
there is no fictitious coupling between disconnected interiors.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from scipy.special import h1vp, hankel1, jv, jvp

__all__ = [
    "CircularCylinder2D",
    "ConvergedFieldResult",
    "MultiCylinderSolution",
    "MultiCylinderSystem",
    "TruncationConfig",
    "TruncationConvergenceError",
    "TruncationRecord",
    "build_multicylinder_system",
    "converge_multicylinder_scattered_field",
    "line_source_incident_field_matrix",
    "multicylinder_scattered_field",
    "multicylinder_total_field",
    "recommended_mode_order",
    "solve_multicylinder_line_sources",
]


@dataclass(frozen=True)
class CircularCylinder2D:
    """One circular penetrable component.

    Parameters
    ----------
    center:
        Cartesian centre ``(x, y)``.
    radius:
        Strictly positive radius in the same units as sources and receivers.
    component_id:
        Optional diagnostic label.  It has no effect on the physics.
    """

    center: tuple[float, float]
    radius: float
    component_id: str | None = None

    def __post_init__(self) -> None:
        center = _coerce_real_array(self.center, name="center")
        if center.shape != (2,) or not np.all(np.isfinite(center)):
            raise ValueError("center must contain two finite Cartesian coordinates.")
        radius = _coerce_real_scalar(self.radius, name="radius")
        if not math.isfinite(radius) or radius <= 0.0:
            raise ValueError("radius must be finite and strictly positive.")
        if self.component_id is not None and not str(self.component_id):
            raise ValueError("component_id must be non-empty when provided.")
        object.__setattr__(self, "center", (float(center[0]), float(center[1])))
        object.__setattr__(self, "radius", radius)
        if self.component_id is not None:
            object.__setattr__(self, "component_id", str(self.component_id))


@dataclass(frozen=True)
class TruncationConfig:
    """Controls receiver-field convergence over cylindrical mode order.

    Adaptive convergence compares the complete paired scattered field at
    successive mode orders.  This is more meaningful than comparing raw
    multipole coefficients, whose natural magnitude changes strongly with
    mode number.
    """

    initial_order: int | None = None
    order_step: int = 4
    maximum_order: int = 64
    relative_tolerance: float = 1.0e-10
    absolute_tolerance: float = 1.0e-13
    required_successive_passes: int = 1

    def __post_init__(self) -> None:
        if self.initial_order is not None:
            initial_order = _validate_mode_order(
                self.initial_order,
                name="initial_order",
            )
        else:
            initial_order = None
        order_step = _validate_positive_integer(self.order_step, name="order_step")
        maximum_order = _validate_mode_order(
            self.maximum_order,
            name="maximum_order",
        )
        if initial_order is not None and initial_order > maximum_order:
            raise ValueError("initial_order cannot exceed maximum_order.")
        relative_tolerance = _coerce_nonnegative_finite_scalar(
            self.relative_tolerance,
            name="relative_tolerance",
        )
        absolute_tolerance = _coerce_nonnegative_finite_scalar(
            self.absolute_tolerance,
            name="absolute_tolerance",
        )
        if relative_tolerance == 0.0 and absolute_tolerance == 0.0:
            raise ValueError("At least one convergence tolerance must be positive.")
        required_passes = _validate_positive_integer(
            self.required_successive_passes,
            name="required_successive_passes",
        )
        object.__setattr__(self, "initial_order", initial_order)
        object.__setattr__(self, "order_step", order_step)
        object.__setattr__(self, "maximum_order", maximum_order)
        object.__setattr__(self, "relative_tolerance", relative_tolerance)
        object.__setattr__(self, "absolute_tolerance", absolute_tolerance)
        object.__setattr__(self, "required_successive_passes", required_passes)


@dataclass(frozen=True)
class TruncationRecord:
    """One entry in an adaptive mode-order convergence history."""

    mode_order: int
    absolute_change: float | None
    relative_change: float | None
    matrix_condition_number: float
    linear_solve_relative_residual: float

    def __post_init__(self) -> None:
        mode_order = _validate_mode_order(self.mode_order)
        absolute_change = _coerce_optional_nonnegative_finite_scalar(
            self.absolute_change,
            name="absolute_change",
        )
        relative_change = _coerce_optional_nonnegative_finite_scalar(
            self.relative_change,
            name="relative_change",
        )
        condition_number = _coerce_nonnegative_finite_scalar(
            self.matrix_condition_number,
            name="matrix_condition_number",
        )
        if condition_number == 0.0:
            raise ValueError("matrix_condition_number must be strictly positive.")
        residual = _coerce_nonnegative_finite_scalar(
            self.linear_solve_relative_residual,
            name="linear_solve_relative_residual",
        )
        object.__setattr__(self, "mode_order", mode_order)
        object.__setattr__(self, "absolute_change", absolute_change)
        object.__setattr__(self, "relative_change", relative_change)
        object.__setattr__(self, "matrix_condition_number", condition_number)
        object.__setattr__(self, "linear_solve_relative_residual", residual)


@dataclass(frozen=True)
class MultiCylinderSystem:
    """Dense multiple-scattering system at one pair of wavenumbers."""

    cylinders: tuple[CircularCylinder2D, ...]
    k_exterior: complex
    k_interior: complex
    mode_order: int
    modes: np.ndarray
    scattering_ratios: np.ndarray
    outgoing_basis_scales: np.ndarray
    system_matrix: np.ndarray
    condition_number: float

    def __post_init__(self) -> None:
        cylinders = _coerce_cylinders(self.cylinders)
        exterior_wave = _coerce_wavenumber(
            self.k_exterior,
            name="k_exterior",
        )
        interior_wave = _coerce_wavenumber(
            self.k_interior,
            name="k_interior",
        )
        mode_order = _validate_mode_order(self.mode_order)
        expected_modes = np.arange(-mode_order, mode_order + 1, dtype=int)
        modes = _coerce_integer_array(self.modes, name="modes")
        if modes.shape != expected_modes.shape or not np.array_equal(
            modes,
            expected_modes,
        ):
            raise ValueError("modes must be the ordered range -mode_order...mode_order.")
        expected_shape = (len(cylinders), expected_modes.size)
        ratios = _coerce_finite_complex_array(
            self.scattering_ratios,
            name="scattering_ratios",
        )
        scales = _coerce_finite_complex_array(
            self.outgoing_basis_scales,
            name="outgoing_basis_scales",
        )
        if ratios.shape != expected_shape:
            raise ValueError(
                f"scattering_ratios must have shape {expected_shape}."
            )
        if scales.shape != expected_shape:
            raise ValueError(
                f"outgoing_basis_scales must have shape {expected_shape}."
            )
        if np.any(scales == 0.0):
            raise ValueError("outgoing_basis_scales cannot contain zero.")
        unknown_count = len(cylinders) * expected_modes.size
        matrix = _coerce_finite_complex_array(
            self.system_matrix,
            name="system_matrix",
        )
        if matrix.shape != (unknown_count, unknown_count):
            raise ValueError(
                "system_matrix must have shape "
                f"({unknown_count}, {unknown_count})."
            )
        condition_number = _coerce_nonnegative_finite_scalar(
            self.condition_number,
            name="condition_number",
        )
        if condition_number == 0.0:
            raise ValueError("condition_number must be strictly positive.")

        object.__setattr__(self, "cylinders", cylinders)
        object.__setattr__(self, "k_exterior", exterior_wave)
        object.__setattr__(self, "k_interior", interior_wave)
        object.__setattr__(self, "mode_order", mode_order)
        object.__setattr__(self, "modes", _readonly(modes))
        object.__setattr__(self, "scattering_ratios", _readonly(ratios))
        object.__setattr__(self, "outgoing_basis_scales", _readonly(scales))
        object.__setattr__(self, "system_matrix", _readonly(matrix))
        object.__setattr__(self, "condition_number", condition_number)

    @property
    def num_cylinders(self) -> int:
        return len(self.cylinders)

    @property
    def num_modes(self) -> int:
        return int(self.modes.size)

    @property
    def num_unknowns(self) -> int:
        return self.num_cylinders * self.num_modes


@dataclass(frozen=True)
class MultiCylinderSolution:
    """Outgoing coefficients for one or more independent line sources.

    ``boundary_normalized_coefficients`` has shape
    ``(num_sources, num_cylinders, num_modes)``.  Receiver evaluation returns
    a full ``(num_receivers, num_sources)`` response matrix by default.  The
    stored unknown is ``a[p,n] * H_n(k_e * radius[p])`` rather than the raw
    outgoing coefficient.  This basis scaling keeps high-order systems well
    conditioned without changing the represented field.
    """

    system: MultiCylinderSystem
    source_points: np.ndarray
    source_strengths: np.ndarray
    boundary_normalized_coefficients: np.ndarray
    linear_solve_relative_residual: float

    def __post_init__(self) -> None:
        if not isinstance(self.system, MultiCylinderSystem):
            raise TypeError("system must be a MultiCylinderSystem object.")
        sources = _coerce_points(self.source_points, name="source_points")
        _validate_exterior_points(
            sources,
            self.system.cylinders,
            name="source_points",
        )
        strengths = _coerce_strengths(
            self.source_strengths,
            sources.shape[0],
            name="source_strengths",
        )
        coefficients = _coerce_finite_complex_array(
            self.boundary_normalized_coefficients,
            name="boundary_normalized_coefficients",
        )
        expected_shape = (
            sources.shape[0],
            self.system.num_cylinders,
            self.system.num_modes,
        )
        if coefficients.shape != expected_shape:
            raise ValueError(
                "boundary_normalized_coefficients must have shape "
                f"{expected_shape}."
            )
        residual = _coerce_nonnegative_finite_scalar(
            self.linear_solve_relative_residual,
            name="linear_solve_relative_residual",
        )
        object.__setattr__(self, "source_points", _readonly(sources))
        object.__setattr__(self, "source_strengths", _readonly(strengths))
        object.__setattr__(
            self,
            "boundary_normalized_coefficients",
            _readonly(coefficients),
        )
        object.__setattr__(self, "linear_solve_relative_residual", residual)

    @property
    def outgoing_coefficients(self) -> np.ndarray:
        """Return raw ``a[p,n]`` multipole coefficients as a copy.

        Field evaluation deliberately uses the normalized representation to
        avoid multiplying very large and very small high-order quantities.
        """

        values = (
            self.boundary_normalized_coefficients
            / self.system.outgoing_basis_scales[None, :, :]
        )
        return _readonly(values)

    def scattered_field(self, receiver_points: np.ndarray) -> np.ndarray:
        """Evaluate every source solution at every exterior receiver."""

        receivers = _coerce_points(receiver_points, name="receiver_points")
        _validate_exterior_points(
            receivers,
            self.system.cylinders,
            name="receiver_points",
        )
        values = np.zeros(
            (receivers.shape[0], self.source_points.shape[0]),
            dtype=np.complex128,
        )
        modes = self.system.modes
        wave = self.system.k_exterior
        for component_index, cylinder in enumerate(self.system.cylinders):
            center = np.asarray(cylinder.center, dtype=float)
            displacement = receivers - center
            radii = np.linalg.norm(displacement, axis=1)
            angles = np.arctan2(displacement[:, 1], displacement[:, 0])
            basis = (
                hankel1(modes[None, :], wave * radii[:, None])
                / self.system.outgoing_basis_scales[component_index][None, :]
                * np.exp(1j * angles[:, None] * modes[None, :])
            )
            values += (
                basis
                @ self.boundary_normalized_coefficients[:, component_index, :].T
            )
        return values

    def paired_scattered_field(self, receiver_points: np.ndarray) -> np.ndarray:
        """Evaluate receiver ``i`` for source ``i``."""

        values = self.scattered_field(receiver_points)
        if values.shape[0] != values.shape[1]:
            raise ValueError(
                "Paired evaluation needs one receiver point per source point."
            )
        return np.diag(values).copy()

    def total_field(self, receiver_points: np.ndarray) -> np.ndarray:
        """Return the full receiver-by-source incident-plus-scattered matrix."""

        return self.scattered_field(receiver_points) + line_source_incident_field_matrix(
            receiver_points,
            self.source_points,
            k_exterior=self.system.k_exterior,
            source_strength=self.source_strengths,
        )

    def paired_total_field(self, receiver_points: np.ndarray) -> np.ndarray:
        """Return incident plus scattered field for paired receivers/sources."""

        values = self.total_field(receiver_points)
        if values.shape[0] != values.shape[1]:
            raise ValueError(
                "Paired evaluation needs one receiver point per source point."
            )
        return np.diag(values).copy()


@dataclass(frozen=True)
class ConvergedFieldResult:
    """Adaptive paired scattered field and its final coefficient solution."""

    scattered_field: np.ndarray
    solution: MultiCylinderSolution
    history: tuple[TruncationRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.solution, MultiCylinderSolution):
            raise TypeError("solution must be a MultiCylinderSolution object.")
        field = _coerce_finite_complex_array(
            self.scattered_field,
            name="scattered_field",
        )
        expected_shape = (self.solution.source_points.shape[0],)
        if field.shape != expected_shape:
            raise ValueError(f"scattered_field must have shape {expected_shape}.")
        history = tuple(self.history)
        if not history or not all(
            isinstance(item, TruncationRecord) for item in history
        ):
            raise ValueError("history must contain at least one TruncationRecord.")
        if history[-1].mode_order != self.solution.system.mode_order:
            raise ValueError(
                "The final history mode order must match the solution system."
            )
        object.__setattr__(self, "scattered_field", _readonly(field))
        object.__setattr__(self, "history", history)

    @property
    def mode_order(self) -> int:
        return self.solution.system.mode_order


class TruncationConvergenceError(RuntimeError):
    """Raised when adaptive mode refinement reaches its configured limit."""

    def __init__(
        self,
        message: str,
        *,
        history: tuple[TruncationRecord, ...],
        last_field: np.ndarray,
    ) -> None:
        super().__init__(message)
        self.history = history
        self.last_field = np.asarray(last_field, dtype=np.complex128).copy()


def recommended_mode_order(
    cylinders: Sequence[CircularCylinder2D],
    k_exterior: complex,
    k_interior: complex,
) -> int:
    """Return a practical starting order for adaptive refinement.

    The size-dependent term follows the usual cylindrical-wave heuristic.  A
    mild gap term raises the starting order when components approach one
    another, but close configurations should still be verified with
    :func:`converge_multicylinder_scattered_field`.
    """

    resolved = _coerce_cylinders(cylinders)
    exterior_wave = _coerce_wavenumber(k_exterior, name="k_exterior")
    interior_wave = _coerce_wavenumber(k_interior, name="k_interior")
    size = max(
        max(abs(exterior_wave), abs(interior_wave)) * cylinder.radius
        for cylinder in resolved
    )
    size_term = size + 4.0 * np.cbrt(max(size, 1.0)) + 8.0

    gap_term = 0.0
    if len(resolved) > 1:
        worst_ratio = 0.0
        for first_index, first in enumerate(resolved[:-1]):
            first_center = np.asarray(first.center)
            for second in resolved[first_index + 1 :]:
                separation = float(
                    np.linalg.norm(first_center - np.asarray(second.center))
                )
                gap = separation - first.radius - second.radius
                worst_ratio = max(
                    worst_ratio,
                    (first.radius + second.radius) / gap,
                )
        gap_term = 2.0 * math.log1p(worst_ratio)
    return max(4, int(math.ceil(size_term + gap_term)))


def build_multicylinder_system(
    cylinders: Sequence[CircularCylinder2D],
    k_exterior: complex,
    k_interior: complex,
    *,
    mode_order: int | None = None,
) -> MultiCylinderSystem:
    """Assemble the independent cylindrical multiple-scattering system.

    Each diagonal block is identity.  For distinct target/source cylinders
    ``p`` and ``q``, the block is ``-R_p T_pq``, where ``R_p`` is the exact
    circular transmission coefficient and ``T_pq`` is Graf translation from
    outgoing waves about ``q`` to regular waves about ``p``.
    """

    resolved = _coerce_cylinders(cylinders)
    exterior_wave = _coerce_wavenumber(k_exterior, name="k_exterior")
    interior_wave = _coerce_wavenumber(k_interior, name="k_interior")
    if mode_order is None:
        order = recommended_mode_order(resolved, exterior_wave, interior_wave)
    else:
        order = _validate_mode_order(mode_order)
    modes = np.arange(-order, order + 1, dtype=int)
    num_modes = modes.size
    num_cylinders = len(resolved)

    ratios = np.stack(
        [
            _scattering_coefficient_ratios(
                modes,
                exterior_wave,
                interior_wave,
                cylinder.radius,
            )
            for cylinder in resolved
        ],
        axis=0,
    )
    basis_scales = np.stack(
        [
            hankel1(modes, exterior_wave * cylinder.radius)
            for cylinder in resolved
        ],
        axis=0,
    ).astype(np.complex128)
    if not np.all(np.isfinite(basis_scales)) or np.any(basis_scales == 0.0):
        raise FloatingPointError(
            "The boundary normalization for an outgoing cylindrical mode is "
            "non-finite or zero at this mode order."
        )
    matrix = np.eye(num_cylinders * num_modes, dtype=np.complex128)
    target_modes = modes[:, None]
    source_modes = modes[None, :]
    translation_orders = target_modes - source_modes

    for target_index, target in enumerate(resolved):
        target_slice = slice(target_index * num_modes, (target_index + 1) * num_modes)
        target_center = np.asarray(target.center, dtype=float)
        for source_index, source in enumerate(resolved):
            if target_index == source_index:
                continue
            source_slice = slice(
                source_index * num_modes,
                (source_index + 1) * num_modes,
            )
            center_vector = np.asarray(source.center, dtype=float) - target_center
            distance = float(np.linalg.norm(center_vector))
            angle = float(np.arctan2(center_vector[1], center_vector[0]))
            translation = hankel1(
                translation_orders,
                exterior_wave * distance,
            ) * np.exp(1j * (source_modes - target_modes) * angle)
            matrix[target_slice, source_slice] = (
                -basis_scales[target_index, :, None]
                * ratios[target_index, :, None]
                * translation
                / basis_scales[source_index, None, :]
            )

    if not np.all(np.isfinite(matrix)):
        raise FloatingPointError(
            "The cylindrical translation matrix overflowed. Reduce the mode "
            "order or use a scaled-basis implementation for this configuration."
        )
    condition_number = float(np.linalg.cond(matrix))
    if not math.isfinite(condition_number):
        raise np.linalg.LinAlgError("The multi-cylinder system is singular.")

    return MultiCylinderSystem(
        cylinders=resolved,
        k_exterior=exterior_wave,
        k_interior=interior_wave,
        mode_order=order,
        modes=_readonly(modes),
        scattering_ratios=_readonly(ratios),
        outgoing_basis_scales=_readonly(basis_scales),
        system_matrix=_readonly(matrix),
        condition_number=condition_number,
    )


def solve_multicylinder_line_sources(
    cylinders: Sequence[CircularCylinder2D],
    source_points: np.ndarray,
    *,
    k_exterior: complex,
    k_interior: complex,
    source_strength: complex | np.ndarray = 1.0,
    mode_order: int | None = None,
    system: MultiCylinderSystem | None = None,
) -> MultiCylinderSolution:
    """Solve outgoing coefficients for independent exterior line sources.

    Supplying a prebuilt ``system`` is useful when many source batches share
    one geometry and frequency.  In that case the other system-defining
    arguments must agree exactly with the supplied system.
    """

    sources = _coerce_points(source_points, name="source_points")
    strengths = _coerce_strengths(
        source_strength,
        sources.shape[0],
        name="source_strength",
    )
    if system is None:
        resolved_system = build_multicylinder_system(
            cylinders,
            k_exterior,
            k_interior,
            mode_order=mode_order,
        )
    else:
        resolved_system = system
        _validate_matching_system_arguments(
            system,
            cylinders,
            k_exterior,
            k_interior,
            mode_order,
        )
    _validate_exterior_points(
        sources,
        resolved_system.cylinders,
        name="source_points",
    )

    modes = resolved_system.modes
    num_modes = resolved_system.num_modes
    num_sources = sources.shape[0]
    incident_regular = np.empty(
        (resolved_system.num_cylinders, num_modes, num_sources),
        dtype=np.complex128,
    )
    for component_index, cylinder in enumerate(resolved_system.cylinders):
        displacement = sources - np.asarray(cylinder.center, dtype=float)
        radii = np.linalg.norm(displacement, axis=1)
        angles = np.arctan2(displacement[:, 1], displacement[:, 0])
        # Graf expansion of (i/4) H0(k |x-source|) about the cylinder centre.
        incident_regular[component_index] = (
            0.25j
            * hankel1(modes[:, None], resolved_system.k_exterior * radii[None, :])
            * np.exp(-1j * modes[:, None] * angles[None, :])
            * strengths[None, :]
        )

    right_hand_side = (
        resolved_system.outgoing_basis_scales[:, :, None]
        * resolved_system.scattering_ratios[:, :, None]
        * incident_regular
    ).reshape(resolved_system.num_unknowns, num_sources)
    coefficient_matrix = np.linalg.solve(
        resolved_system.system_matrix,
        right_hand_side,
    )
    residual = resolved_system.system_matrix @ coefficient_matrix - right_hand_side
    denominator = max(float(np.linalg.norm(right_hand_side)), np.finfo(float).tiny)
    relative_residual = float(np.linalg.norm(residual) / denominator)
    normalized_outgoing = coefficient_matrix.T.reshape(
        num_sources,
        resolved_system.num_cylinders,
        num_modes,
    )
    return MultiCylinderSolution(
        system=resolved_system,
        source_points=_readonly(sources),
        source_strengths=_readonly(strengths),
        boundary_normalized_coefficients=_readonly(normalized_outgoing),
        linear_solve_relative_residual=relative_residual,
    )


def multicylinder_scattered_field(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    *,
    cylinders: Sequence[CircularCylinder2D],
    k_exterior: complex,
    k_interior: complex,
    source_strength: complex | np.ndarray = 1.0,
    mode_order: int | None = None,
) -> np.ndarray:
    """Return paired exterior scattered fields for line sources.

    This mirrors the shape convention of the existing one-cylinder analytic
    reference: receiver and source arrays must both have shape
    ``(num_pairs, 2)``.  Use :class:`MultiCylinderSolution` when a full
    receiver-by-source response matrix is wanted.
    """

    receivers, sources = _coerce_paired_points(receiver_points, source_points)
    solution = solve_multicylinder_line_sources(
        cylinders,
        sources,
        k_exterior=k_exterior,
        k_interior=k_interior,
        source_strength=source_strength,
        mode_order=mode_order,
    )
    return solution.paired_scattered_field(receivers)


def multicylinder_total_field(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    *,
    cylinders: Sequence[CircularCylinder2D],
    k_exterior: complex,
    k_interior: complex,
    source_strength: complex | np.ndarray = 1.0,
    mode_order: int | None = None,
) -> np.ndarray:
    """Return paired incident-plus-scattered exterior fields."""

    receivers, sources = _coerce_paired_points(receiver_points, source_points)
    solution = solve_multicylinder_line_sources(
        cylinders,
        sources,
        k_exterior=k_exterior,
        k_interior=k_interior,
        source_strength=source_strength,
        mode_order=mode_order,
    )
    return solution.paired_total_field(receivers)


def converge_multicylinder_scattered_field(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    *,
    cylinders: Sequence[CircularCylinder2D],
    k_exterior: complex,
    k_interior: complex,
    source_strength: complex | np.ndarray = 1.0,
    config: TruncationConfig | None = None,
) -> ConvergedFieldResult:
    """Refine cylindrical order until the paired scattered field converges.

    Raises
    ------
    TruncationConvergenceError
        If ``maximum_order`` is reached before the configured number of
        successive comparisons pass.
    """

    receivers, sources = _coerce_paired_points(receiver_points, source_points)
    if config is None:
        config = TruncationConfig()
    resolved = _coerce_cylinders(cylinders)
    if config.initial_order is None:
        initial_order = recommended_mode_order(
            resolved,
            k_exterior,
            k_interior,
        )
    else:
        initial_order = config.initial_order
    if initial_order > config.maximum_order:
        raise ValueError(
            "The recommended initial mode order exceeds maximum_order; raise "
            "the configured maximum or supply a smaller explicit initial_order."
        )

    history: list[TruncationRecord] = []
    previous: np.ndarray | None = None
    latest_solution: MultiCylinderSolution | None = None
    latest_field: np.ndarray | None = None
    successful_passes = 0
    order = initial_order
    while True:
        latest_solution = solve_multicylinder_line_sources(
            resolved,
            sources,
            k_exterior=k_exterior,
            k_interior=k_interior,
            source_strength=source_strength,
            mode_order=order,
        )
        latest_field = latest_solution.paired_scattered_field(receivers)
        if previous is None:
            absolute_change = None
            relative_change = None
            successful_passes = 0
        else:
            absolute_change = float(np.linalg.norm(latest_field - previous))
            field_norm = float(np.linalg.norm(latest_field))
            relative_change = absolute_change / max(
                field_norm,
                config.absolute_tolerance,
                np.finfo(float).tiny,
            )
            threshold = (
                config.absolute_tolerance
                + config.relative_tolerance * field_norm
            )
            if absolute_change <= threshold:
                successful_passes += 1
            else:
                successful_passes = 0
        history.append(
            TruncationRecord(
                mode_order=order,
                absolute_change=absolute_change,
                relative_change=relative_change,
                matrix_condition_number=latest_solution.system.condition_number,
                linear_solve_relative_residual=(
                    latest_solution.linear_solve_relative_residual
                ),
            )
        )
        if successful_passes >= config.required_successive_passes:
            return ConvergedFieldResult(
                scattered_field=_readonly(latest_field),
                solution=latest_solution,
                history=tuple(history),
            )
        previous = latest_field
        if order == config.maximum_order:
            break
        order = min(order + config.order_step, config.maximum_order)

    assert latest_solution is not None and latest_field is not None
    frozen_history = tuple(history)
    last_change = frozen_history[-1].relative_change
    raise TruncationConvergenceError(
        "Cylindrical series did not converge by mode order "
        f"{config.maximum_order}; last relative change was {last_change!r}.",
        history=frozen_history,
        last_field=latest_field,
    )


def line_source_incident_field_matrix(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    *,
    k_exterior: complex,
    source_strength: complex | np.ndarray = 1.0,
) -> np.ndarray:
    """Return the full receiver-by-source free-space line-source field."""

    receivers = _coerce_points(receiver_points, name="receiver_points")
    sources = _coerce_points(source_points, name="source_points")
    strengths = _coerce_strengths(
        source_strength,
        sources.shape[0],
        name="source_strength",
    )
    wave = _coerce_wavenumber(k_exterior, name="k_exterior")
    distances = np.linalg.norm(
        receivers[:, None, :] - sources[None, :, :],
        axis=-1,
    )
    if np.any(distances <= 0.0):
        raise ValueError("Source and receiver points must be distinct.")
    return 0.25j * hankel1(0, wave * distances) * strengths[None, :]


def _scattering_coefficient_ratios(
    modes: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    radius: float,
) -> np.ndarray:
    exterior_argument = k_exterior * radius
    interior_argument = k_interior * radius
    exterior_j = jv(modes, exterior_argument)
    interior_j = jv(modes, interior_argument)
    interior_j_derivative = jvp(modes, interior_argument)
    numerator = (
        k_interior * interior_j_derivative * exterior_j
        - k_exterior * jvp(modes, exterior_argument) * interior_j
    )
    denominator = (
        k_exterior * h1vp(modes, exterior_argument) * interior_j
        - k_interior
        * interior_j_derivative
        * hankel1(modes, exterior_argument)
    )
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        ratios = numerator / denominator
    if not np.all(np.isfinite(ratios)):
        raise FloatingPointError(
            "A circular transmission coefficient is non-finite at this "
            "wavenumber and mode order."
        )
    return np.asarray(ratios, dtype=np.complex128)


def _coerce_cylinders(
    cylinders: Sequence[CircularCylinder2D],
) -> tuple[CircularCylinder2D, ...]:
    resolved = tuple(cylinders)
    if not resolved:
        raise ValueError("At least one circular cylinder is required.")
    if not all(isinstance(item, CircularCylinder2D) for item in resolved):
        raise TypeError("cylinders must contain CircularCylinder2D values.")
    labels = [item.component_id for item in resolved if item.component_id is not None]
    if len(labels) != len(set(labels)):
        raise ValueError("Non-null cylinder component_id values must be unique.")

    geometry_scale = max(
        1.0,
        *(abs(coordinate) for item in resolved for coordinate in item.center),
        *(item.radius for item in resolved),
    )
    tolerance = 64.0 * np.finfo(float).eps * geometry_scale
    for first_index, first in enumerate(resolved[:-1]):
        first_center = np.asarray(first.center, dtype=float)
        for second_index, second in enumerate(
            resolved[first_index + 1 :],
            start=first_index + 1,
        ):
            separation = float(
                np.linalg.norm(first_center - np.asarray(second.center, dtype=float))
            )
            gap = separation - first.radius - second.radius
            if gap <= tolerance:
                first_label = first.component_id or str(first_index)
                second_label = second.component_id or str(second_index)
                raise ValueError(
                    "Circular cylinders must be strictly disjoint; components "
                    f"{first_label!r} and {second_label!r} have gap {gap:.6g}."
                )
    return resolved


def _coerce_points(values: np.ndarray, *, name: str) -> np.ndarray:
    points = _coerce_real_array(values, name=name)
    if points.shape == (2,):
        points = points[None, :]
    if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] == 0:
        raise ValueError(f"{name} must have shape (num_points, 2).")
    if not np.all(np.isfinite(points)):
        raise ValueError(f"{name} must contain only finite coordinates.")
    return np.asarray(points, dtype=float)


def _coerce_paired_points(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    receivers = _coerce_points(receiver_points, name="receiver_points")
    sources = _coerce_points(source_points, name="source_points")
    if receivers.shape != sources.shape:
        raise ValueError(
            "receiver_points and source_points must contain the same number "
            "of paired Cartesian points."
        )
    return receivers, sources


def _coerce_strengths(
    values: complex | np.ndarray,
    count: int,
    *,
    name: str,
) -> np.ndarray:
    strengths = np.atleast_1d(np.asarray(values, dtype=np.complex128))
    if strengths.size == 1:
        strengths = np.full((count,), strengths[0], dtype=np.complex128)
    if strengths.shape != (count,):
        raise ValueError(f"{name} must be scalar or contain one value per source.")
    if not np.all(np.isfinite(strengths)):
        raise ValueError(f"{name} must contain only finite values.")
    return strengths


def _validate_exterior_points(
    points: np.ndarray,
    cylinders: tuple[CircularCylinder2D, ...],
    *,
    name: str,
) -> None:
    scale = max(
        1.0,
        float(np.max(np.abs(points))),
        *(item.radius for item in cylinders),
    )
    tolerance = 64.0 * np.finfo(float).eps * scale
    for index, cylinder in enumerate(cylinders):
        distance = np.linalg.norm(
            points - np.asarray(cylinder.center, dtype=float),
            axis=1,
        )
        if np.any(distance <= cylinder.radius + tolerance):
            label = cylinder.component_id or str(index)
            raise ValueError(
                f"{name} must lie strictly outside every cylinder; at least "
                f"one point is on or inside component {label!r}."
            )


def _coerce_wavenumber(value: complex, *, name: str) -> complex:
    wave = complex(value)
    if not math.isfinite(wave.real) or not math.isfinite(wave.imag) or abs(wave) == 0.0:
        raise ValueError(f"{name} must be finite and non-zero.")
    return wave


def _validate_mode_order(value: int, *, name: str = "mode_order") -> int:
    raw = np.asarray(value)
    if (
        raw.ndim != 0
        or isinstance(value, (bool, np.bool_))
        or np.iscomplexobj(raw)
    ):
        raise ValueError(f"{name} must be a non-negative integer.")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a non-negative integer.") from error
    try:
        is_exact = bool(result == value)
    except (TypeError, ValueError):
        is_exact = False
    if not is_exact or result < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return result


def _validate_positive_integer(value: int, *, name: str) -> int:
    result = _validate_mode_order(value, name=name)
    if result == 0:
        raise ValueError(f"{name} must be a positive integer.")
    return result


def _coerce_real_array(values, *, name: str) -> np.ndarray:
    raw = np.asarray(values)
    if np.iscomplexobj(raw):
        raise ValueError(f"{name} must be real-valued, not complex-valued.")
    try:
        result = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain real numeric values.") from error
    return result


def _coerce_real_scalar(value, *, name: str) -> float:
    raw = np.asarray(value)
    if (
        raw.ndim != 0
        or isinstance(value, (bool, np.bool_))
        or np.iscomplexobj(raw)
    ):
        raise ValueError(f"{name} must be a real scalar.")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a real scalar.") from error
    return result


def _coerce_nonnegative_finite_scalar(value, *, name: str) -> float:
    result = _coerce_real_scalar(value, name=name)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


def _coerce_optional_nonnegative_finite_scalar(
    value,
    *,
    name: str,
) -> float | None:
    if value is None:
        return None
    return _coerce_nonnegative_finite_scalar(value, name=name)


def _coerce_integer_array(values, *, name: str) -> np.ndarray:
    real = _coerce_real_array(values, name=name)
    if not np.all(np.isfinite(real)) or not np.all(real == np.rint(real)):
        raise ValueError(f"{name} must contain only finite integer values.")
    return np.asarray(real, dtype=int)


def _coerce_finite_complex_array(values, *, name: str) -> np.ndarray:
    try:
        result = np.asarray(values, dtype=np.complex128)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain numeric values.") from error
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values.")
    return result


def _validate_matching_system_arguments(
    system: MultiCylinderSystem,
    cylinders: Sequence[CircularCylinder2D],
    k_exterior: complex,
    k_interior: complex,
    mode_order: int | None,
) -> None:
    resolved = _coerce_cylinders(cylinders)
    if resolved != system.cylinders:
        raise ValueError("cylinders do not match the supplied system.")
    if complex(k_exterior) != system.k_exterior:
        raise ValueError("k_exterior does not match the supplied system.")
    if complex(k_interior) != system.k_interior:
        raise ValueError("k_interior does not match the supplied system.")
    if mode_order is not None:
        resolved_order = _validate_mode_order(mode_order)
        if resolved_order != system.mode_order:
            raise ValueError("mode_order does not match the supplied system.")


def _readonly(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values).copy()
    array.setflags(write=False)
    return array
