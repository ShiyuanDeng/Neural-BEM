"""Exact translation and uniform scaling about the stored Cartesian zero mode."""
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from .continuation.geometry import FourierCurve, grid_size, integer
from .continuation.updates import BorgesUpdate, LocalSpace, UpdateRefused


@dataclass(frozen=True)
class SimilaritySpace(LocalSpace):
    derivatives: np.ndarray
    radius_m: float


class SimilarityUpdate(BorgesUpdate):
    """Metre coordinates (tx, ty, dr); positive scale is 1 + dr/R.

    R is the accepted curve's area-equivalent physical radius. Scaling keeps
    c0 fixed; translation changes only c0. This preserves a circle exactly and
    preserves any validated curve's shape up to a positive uniform scale.
    """
    name = 'exact_cartesian_translation_scale'

    def __init__(self, length_unit_m):
        super().__init__(length_unit_m)
        self.counts = dict(preparations=0, preparation_seconds=0.,
                           trial_constructions=0, trial_seconds=0., refused_trials=0)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m,
                    coordinates=['translation_x_m', 'translation_y_m', 'radius_change_m'],
                    construction='c0 += (tx+i*ty)/length_unit_m; c_m *= 1+dr/R for m!=0',
                    radius='area-equivalent physical radius of the accepted curve',
                    validity='validated base; positive similarity preserves intrinsic validity')

    def prepare(self, curve, update_modes, curve_modes):
        started = perf_counter()
        integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('Similarity preserves the existing storage band.')
        curve.validate()
        # Signed area / pi = sum_m m |c_m|^2, exact for Fourier storage.
        radius = float(self.length_unit_m*np.sqrt(np.sum(curve.modes*abs(curve.coefficients)**2)))
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError('Similarity needs positive finite enclosed area.')
        derivative = np.zeros((len(curve.coefficients), 3), complex)
        derivative[curve.band, :2] = np.array([1., 1j])/self.length_unit_m
        derivative[:, 2] = curve.coefficients/radius
        derivative[curve.band, 2] = 0.
        derivative.setflags(write=False)
        space = SimilaritySpace(curve, update_modes, curve_modes, self.length_unit_m,
                                np.array([1, 1, 0]),
                                ('translation_x_m', 'translation_y_m', 'radius_change_m'),
                                derivative, radius)
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += perf_counter()-started
        return space

    def velocities(self, space, nodes):
        centre = space.curve.coefficients[space.curve.band]
        relative = nodes.points-np.array([centre.real, centre.imag])
        radial = np.sum(relative*nodes.normals, axis=1)/space.radius_m
        return np.column_stack((nodes.normals/self.length_unit_m, radial))

    def measure(self, space, coefficients):
        step = self._checked(space, coefficients)
        nodes = space.curve.nodes(grid_size(space.curve.band))
        normal = self.velocities(space, nodes)@step*self.length_unit_m
        weights = nodes.arc_length_weights/nodes.perimeter
        return dict(maximum_normal_m=float(np.max(abs(normal))),
                    rms_normal_m=float(np.sqrt(weights@normal**2)),
                    translation_distance_m=float(np.linalg.norm(step[:2])),
                    radius_change_m=float(step[2]))

    def metric(self, space, kind, smoothing_m=None):
        if kind != 'mass':
            raise ValueError('Similarity only implements the normal mass metric.')
        nodes = space.curve.nodes(grid_size(space.curve.band))
        basis = self.velocities(space, nodes)*self.length_unit_m
        weights = nodes.arc_length_weights/nodes.perimeter
        return basis.T@(weights[:, None]*basis)

    def trial(self, space, coefficients):
        started = perf_counter()
        self.counts['trial_constructions'] += 1
        try:
            step = self._checked(space, coefficients)
            factor = float(1+step[2]/space.radius_m)
            if not np.isfinite(factor) or factor <= 0:
                raise UpdateRefused('invalid_scale', 'Similarity scale must be finite and strictly positive.')
            if not np.any(step):
                candidate = space.curve
            else:
                c = space.curve.coefficients*factor
                c[space.curve.band] = space.curve.coefficients[space.curve.band]+complex(*step[:2])/self.length_unit_m
                candidate = FourierCurve(c)
            return candidate, dict(self.measure(space, step), projection_error=0.,
                projection_relative=0., refits=0, finite_path=self.name,
                translation_m=step[:2].tolist(), scale_factor=factor,
                equivalent_radius_m=space.radius_m*factor, intrinsic_validity_preserved=True)
        except UpdateRefused:
            self.counts['refused_trials'] += 1
            raise
        finally:
            self.counts['trial_seconds'] += perf_counter()-started
