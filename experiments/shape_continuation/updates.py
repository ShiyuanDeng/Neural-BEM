"""Replaceable geometry updates: infinitesimal directions and finite trials.

An update strategy owns the step coordinates, the normal velocities the
Jacobian differentiates along, the physical metric used for step bounds and
the finite operation that builds a trial boundary. It never sees data,
residuals or policy history, and never accepts its own trials.

Units: curves use the package's dimensionless length (one unit is
`length_unit_m` metres). Step coefficients are physical metres, so LM
scaling floors and step bounds keep the meaning they have in the SPD
optimizer.
"""
from dataclasses import dataclass

import numpy as np

from .geometry import FourierCurve, arclength_angles, displaced, grid_size, normal_basis, reparameterize, integer


class UpdateRefused(ValueError):
    """A trial that the strategy cannot build; `reason` is a stable label."""

    def __init__(self, reason, detail):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def _refusal(exc):
    text = str(exc)
    if "self-intersects" in text:
        return UpdateRefused("self_intersection", text)
    if "projection unresolved" in text:
        return UpdateRefused("unresolved_projection", text)
    return UpdateRefused("irregular_parameterization", text)


@dataclass(frozen=True)
class LocalSpace:
    """Update space at one accepted curve. Rebuild after any accepted change."""
    curve: FourierCurve
    update_modes: int
    curve_modes: int
    length_unit_m: float
    orders: np.ndarray  # harmonic order of each coordinate: 0, 1..M, 1..M
    labels: tuple


def speed_ratio(curve):
    speeds = curve.nodes(grid_size(curve.band)).speeds
    return float(np.max(speeds) / np.min(speeds))


class BorgesUpdate:
    """Sample, move along the unit normal by h(s), refit in arclength.

    Coordinates are the real Fourier coefficients (metres) of the physical
    normal distance h in the accepted curve's normalized arclength:
    `h = a0 + sum_m a_m cos(m s) + b_m sin(m s)`. The finite trial is the
    existing `geometry.displaced` operation with no filter, so its projection
    error is checked and counted on every trial, including rejected ones.
    """
    name = "borges_normal_arclength"

    def __init__(self, length_unit_m, *, projection_tolerance=1e-7):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError("length_unit_m must be positive.")
        if not np.isfinite(projection_tolerance) or projection_tolerance <= 0:
            raise ValueError("projection_tolerance must be positive.")
        self.length_unit_m = float(length_unit_m)
        self.projection_tolerance = float(projection_tolerance)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m,
                    projection_tolerance=self.projection_tolerance,
                    coordinates="real Fourier coefficients of normal distance h (m) in normalized arclength",
                    gauge="arclength refit on every trial")

    def regauge(self, curve, curve_modes):
        """Express an input curve in this strategy's gauge at storage band K."""
        integer(curve_modes, "curve_modes")
        try:
            shape, error = reparameterize(curve, curve_modes, tolerance=self.projection_tolerance)
        except ValueError as exc:
            raise _refusal(exc) from exc
        return shape, float(error)

    def prepare(self, curve, update_modes, curve_modes):
        update_modes = integer(update_modes, "update_modes", minimum=0)
        integer(curve_modes, "curve_modes")
        if curve.band != curve_modes:
            raise ValueError("The accepted curve must already use the stage storage band.")
        harmonics = np.arange(1, update_modes + 1)
        orders = np.concatenate(([0], harmonics, harmonics))
        labels = ("a0", *[f"a{m}" for m in harmonics], *[f"b{m}" for m in harmonics])
        return LocalSpace(curve, update_modes, curve_modes, self.length_unit_m, orders, labels)

    def velocities(self, space, nodes):
        """Normal displacement per metre of each coordinate at physics nodes.

        Returned in package length units per metre, with the same arclength
        harmonics that `trial` applies. `nodes` must sample `space.curve`.
        """
        return normal_basis(nodes, space.update_modes) / self.length_unit_m

    def measure(self, space, coefficients):
        """Physical normal displacement (m) on a resolved grid."""
        a = self._checked(space, coefficients)
        nodes = space.curve.nodes(grid_size(max(space.curve.band, space.update_modes)))
        h = normal_basis(nodes, space.update_modes) @ a
        weights = nodes.arc_length_weights
        return dict(maximum_normal_m=float(np.max(np.abs(h))),
                    rms_normal_m=float(np.sqrt(np.sum(h**2 * weights) / np.sum(weights))))

    def metric(self, space, kind, smoothing_m=None):
        """Step metric in update coordinates; ``a @ R @ a`` is in m^2 (SC-031, opt-in).

        ``"mass"``: W = (1/P) int b_i b_j ds, the mean-square normal move, which
        is diag(1, 1/2, ...) on a circle. ``"curvature"``: W + l^4 (1/P) int
        K_i K_j ds, where K_i = -(b_i,ss + kappa^2 b_i) is the linearized
        curvature change per metre of coefficient i (outward normal, convex
        kappa > 0, physical arclength s). ``smoothing_m`` is l in metres.
        Both are covariant under a shift of the arclength origin.
        """
        nodes = space.curve.nodes(grid_size(max(space.curve.band, space.update_modes)))
        basis = normal_basis(nodes, space.update_modes)
        weights = nodes.arc_length_weights / np.sum(nodes.arc_length_weights)
        mass = basis.T @ (weights[:, None] * basis)
        if kind == "mass":
            return mass
        if kind != "curvature":
            raise ValueError(f"Unknown step metric {kind!r}.")
        if smoothing_m is None or not np.isfinite(smoothing_m) or smoothing_m <= 0:
            raise ValueError("The curvature metric needs a positive smoothing length in metres.")
        angles, _ = arclength_angles(nodes)
        harmonics = np.arange(1, space.update_modes + 1)
        phase = angles[:, None] * harmonics
        scale = (2 * np.pi / (nodes.perimeter * self.length_unit_m)) ** 2
        second = np.column_stack((np.zeros(len(angles)), -np.cos(phase) * harmonics**2,
                                  -np.sin(phase) * harmonics**2)) * scale
        kappa = nodes.curvatures / self.length_unit_m
        change = -(second + kappa[:, None] ** 2 * basis)
        return mass + smoothing_m**4 * (change.T @ (weights[:, None] * change))

    def trial(self, space, coefficients):
        a = self._checked(space, coefficients)
        try:
            step = displaced(space.curve, a / self.length_unit_m, space.curve_modes,
                             projection_tolerance=self.projection_tolerance)
        except ValueError as exc:
            raise _refusal(exc) from exc
        return step.shape, dict(projection_error=float(step.projection_error),
            projection_relative=float(step.projection_error / (space.curve.nodes(
                grid_size(space.curve.band)).perimeter / (2 * np.pi))),
            maximum_normal_m=float(step.maximum_displacement * self.length_unit_m),
            rms_normal_m=float(step.rms_displacement * self.length_unit_m),
            speed_ratio=speed_ratio(step.shape), refits=1)

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f"Expected {len(space.orders)} finite update coefficients.")
        return a
