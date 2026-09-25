"""SC-036: finite ray motion with exactly the existing normal tangent space.

No radial bandwidth truncation or state smoothing is applied. A ray chart is
available only about the current parameter-mean centre and away from tangency.
The Jacobian, step metric and coefficient controls remain BorgesUpdate's.
"""
import numpy as np

from .geometry import FourierCurve, _refit_samples, grid_size, normal_basis
from .updates import BorgesUpdate, UpdateRefused, _refusal, speed_ratio


class RayUpdate(BorgesUpdate):
    name = "matched_normal_velocity_ray_path"

    def __init__(self, length_unit_m, *, projection_tolerance=1e-5,
                 minimum_cosine=0.05, fallback=False):
        super().__init__(length_unit_m, projection_tolerance=projection_tolerance)
        if not 0 < minimum_cosine < 1:
            raise ValueError("minimum_cosine must lie in (0, 1).")
        self.minimum_cosine = float(minimum_cosine)
        self.fallback = bool(fallback)

    def settings(self):
        return dict(super().settings(), minimum_cosine=self.minimum_cosine,
                    fallback=self.fallback, centre="current parameter mean")

    def frame(self, space, count):
        nodes = space.curve.nodes(count)
        z = space.curve.values(count)
        centre = space.curve.coefficients[space.curve.band]
        radius = np.abs(z - centre)
        if np.min(radius) <= 1e-12:
            raise UpdateRefused("ray_chart_unavailable", "Boundary reaches ray centre.")
        ray = (z - centre) / radius
        normal = nodes.normals @ np.array([1, 1j])
        cosine = (ray * np.conj(normal)).real
        if np.min(cosine) <= self.minimum_cosine:
            raise UpdateRefused("ray_chart_unavailable", f"minimum cosine {np.min(cosine):.6g}")
        return nodes, z, ray, radius, cosine

    def trial(self, space, coefficients):
        a = self._checked(space, coefficients)
        count = grid_size(max(space.curve.band, space.update_modes))
        try:
            nodes, z, ray, radius, cosine = self.frame(space, count)
        except UpdateRefused:
            if not self.fallback:
                raise
            shape, record = super().trial(space, a)
            return shape, dict(record, finite_path="normal_chart_fallback")
        h = normal_basis(nodes, space.update_modes) @ a / self.length_unit_m
        radial_step = h / cosine
        if np.min(radius + radial_step) <= 1e-8:
            raise UpdateRefused("nonpositive_ray_radius", "Ray trial crosses its centre.")
        candidate = FourierCurve.from_samples(z + radial_step * ray, count // 2 - 1)
        try:
            shape, projection = _refit_samples(candidate, space.curve_modes, count,
                                                self.projection_tolerance)
        except ValueError as exc:
            raise _refusal(exc) from exc
        return shape, dict(projection_error=float(projection),
            projection_relative=float(projection / (nodes.perimeter / (2 * np.pi))),
            **self.measure(space, a), speed_ratio=speed_ratio(shape), refits=1,
            finite_path="ray", minimum_ray_cosine=float(np.min(cosine)),
            maximum_vector_m=float(np.max(np.abs(radial_step)) * self.length_unit_m))
