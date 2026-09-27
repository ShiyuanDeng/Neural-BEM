"""SC-048: existing normal updates enriched by exact global similarities."""
from dataclasses import dataclass
import numpy as np

from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.updates import UpdateRefused, speed_ratio


@dataclass(frozen=True)
class GlobalSpace:
    curve: FourierCurve
    local: object
    mapping: np.ndarray
    radius: float
    orders: np.ndarray
    labels: tuple


class GlobalUpdate:
    name = "normal_plus_exact_global_motions"

    def __init__(self, base):
        self.base = base
        self.length_unit_m = base.length_unit_m

    @property
    def counts(self):
        return self.base.counts

    def raw_velocities(self, local, nodes, radius):
        z = nodes.points @ np.array([1, 1j])
        normal = nodes.normals @ np.array([1, 1j])
        radial = (z - local.curve.coefficients[local.curve.band]) / radius
        global_part = np.column_stack((nodes.normals,
            np.real(1j * radial * np.conj(normal)), np.real(radial * np.conj(normal))))
        return np.column_stack((self.base.velocities(local, nodes), global_part / self.length_unit_m))

    def prepare(self, curve, update_modes, curve_modes):
        local = self.base.prepare(curve, update_modes, curve_modes)
        nodes = curve.nodes(local.count)
        radius = nodes.perimeter / (2 * np.pi)
        raw = self.raw_velocities(local, nodes, radius) * self.length_unit_m
        weights = np.sqrt(nodes.arc_length_weights / nodes.perimeter)
        weighted = weights[:, None] * raw
        dim = len(local.orders)
        mapping = np.eye(dim + 4)[:, :dim]
        labels = list(local.labels)
        for j, name in enumerate(("translation_x", "translation_y", "rotation", "dilation")):
            target = weighted[:, dim + j]
            size = np.linalg.norm(target)
            if size <= 1e-8:
                continue
            coefficients = np.linalg.lstsq(weighted @ mapping, target, rcond=1e-10)[0]
            direction = np.eye(dim + 4)[:, dim + j] - mapping @ coefficients
            residual = np.linalg.norm(weighted @ direction)
            if residual < .05 * size:
                continue
            mapping = np.column_stack((mapping, direction / residual))
            labels.append("extra_" + name)
        return GlobalSpace(curve, local, mapping, radius,
            np.r_[local.orders, np.zeros(len(labels) - dim, int)], tuple(labels))

    def velocities(self, space, nodes):
        return self.raw_velocities(space.local, nodes, space.radius) @ space.mapping

    def metric(self, space, kind, smoothing_m=None):
        if kind != "mass":
            raise ValueError("Only the complete physical mass metric is qualified.")
        nodes = space.curve.nodes(space.local.count)
        basis = self.velocities(space, nodes) * self.length_unit_m
        return basis.T @ ((nodes.arc_length_weights / nodes.perimeter)[:, None] * basis)

    def measure(self, space, coefficients):
        a = self._checked(space, coefficients)
        nodes = space.curve.nodes(space.local.count)
        h = self.velocities(space, nodes) @ a * self.length_unit_m
        return dict(maximum_normal_m=float(np.max(np.abs(h))),
                    rms_normal_m=float(np.sqrt(nodes.arc_length_weights @ h**2 / nodes.perimeter)))

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError("Invalid global-motion update.")
        return a

    def trial(self, space, coefficients):
        a = self._checked(space, coefficients)
        raw = space.mapping @ a
        dim = len(space.local.orders)
        shape, record = self.base.trial(space.local, raw[:dim])
        tx, ty, rotation, dilation = raw[dim:]
        angle = rotation / (space.radius * self.length_unit_m)
        factor = 1 + dilation / (space.radius * self.length_unit_m)
        if factor <= 0:
            raise UpdateRefused("nonpositive_global_scale", "Similarity scale must stay positive.")
        if not np.any(raw[dim:]):
            return shape, dict(record, **self.measure(space, a))
        c = shape.coefficients.copy()
        centre = space.curve.coefficients[space.curve.band]
        c[shape.band] -= centre
        c *= factor * np.exp(1j * angle)
        c[shape.band] += centre + (tx + 1j * ty) / self.length_unit_m
        candidate = FourierCurve(c)
        try:
            candidate.validate()
        except ValueError as exc:
            raise UpdateRefused("global_geometry", str(exc)) from exc
        if factor * record["projection_relative"] > self.base.projection_tolerance:
            raise UpdateRefused("unresolved_projection", "Scaled geometry projection exceeds the fixed tolerance.")
        return candidate, dict(record, **self.measure(space, a),
            projection_relative=factor * record["projection_relative"],
            projection_error=factor * record["projection_error"],
            speed_ratio=speed_ratio(candidate), global_angle=float(angle), global_scale=float(factor),
            global_translation_m=[float(tx), float(ty)], finite_path=self.name)
