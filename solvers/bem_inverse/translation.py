"""Exact rigid translation as an opt-in two-coordinate geometry update.

Coordinates are physical metres. Physics, objective acceptance, domain checks
and continuation remain the caller's responsibility.
"""
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from .continuation.geometry import FourierCurve, grid_size, integer
from .continuation.updates import BorgesUpdate, LocalSpace


@dataclass(frozen=True)
class TranslationSpace(LocalSpace):
    derivatives: np.ndarray


class TranslationUpdate(BorgesUpdate):
    """Translate only the stored Cartesian zero mode; never refit a curve."""
    name = 'exact_cartesian_translation'

    def __init__(self, length_unit_m):
        super().__init__(length_unit_m)
        self.counts = dict(preparations=0, preparation_seconds=0.,
                           trial_constructions=0, trial_seconds=0.)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m,
                    coordinates=['translation_x_m', 'translation_y_m'],
                    construction='c[0] += (tx + i ty) / length_unit_m',
                    validity='validated base; rigid translation preserves intrinsic geometry')

    def prepare(self, curve, update_modes, curve_modes):
        started = perf_counter()
        integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('Translation preserves the existing storage band.')
        curve.validate()
        derivative = np.zeros((len(curve.coefficients), 2), complex)
        derivative[curve.band] = np.array([1., 1j]) / self.length_unit_m
        derivative.setflags(write=False)
        space = TranslationSpace(curve, update_modes, curve_modes, self.length_unit_m,
                                 np.ones(2, dtype=int), ('translation_x_m', 'translation_y_m'),
                                 derivative)
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += perf_counter()-started
        return space

    def velocities(self, space, nodes):
        return nodes.normals / self.length_unit_m

    def measure(self, space, coefficients):
        step = self._checked(space, coefficients)
        nodes = space.curve.nodes(grid_size(space.curve.band))
        normal = nodes.normals @ step
        weights = nodes.arc_length_weights / nodes.perimeter
        return dict(maximum_normal_m=float(np.max(abs(normal))),
                    rms_normal_m=float(np.sqrt(weights @ normal**2)),
                    translation_distance_m=float(np.linalg.norm(step)))

    def metric(self, space, kind, smoothing_m=None):
        if kind != 'mass':
            raise ValueError('Translation only implements the normal mass metric.')
        nodes = space.curve.nodes(grid_size(space.curve.band))
        weights = nodes.arc_length_weights / nodes.perimeter
        return nodes.normals.T @ (weights[:, None] * nodes.normals)

    def trial(self, space, coefficients):
        started = perf_counter()
        self.counts['trial_constructions'] += 1
        try:
            step = self._checked(space, coefficients)
            c = space.curve.coefficients.copy()
            c[space.curve.band] += complex(*step) / self.length_unit_m
            candidate = FourierCurve(c)
            return candidate, dict(self.measure(space, step), projection_error=0.,
                projection_relative=0., refits=0, finite_path=self.name,
                translation_m=step.tolist(), intrinsic_geometry_preserved=True)
        finally:
            self.counts['trial_seconds'] += perf_counter()-started
