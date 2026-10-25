"""Exact translation and uniform scaling about the stored Cartesian zero mode."""
from .. import checks
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from ..continuation.geometry import FourierCurve, grid_size, integer
from ..errors import UpdateRefused, refusal_from_value_error


@dataclass(frozen=True)
class SimilaritySpace:
    """Coordinates and derivatives of one accepted curve's similarity map."""
    curve: FourierCurve
    update_modes: int
    curve_modes: int
    length_unit_m: float
    orders: np.ndarray
    labels: tuple
    derivatives: np.ndarray
    radius_m: float


class SimilarityUpdate:
    """Metre coordinates (tx, ty, dr); positive scale is 1 + dr/R.

    R is the accepted curve's area-equivalent physical radius. Scaling keeps
    c0 fixed; translation changes only c0. This preserves a circle exactly and
    preserves any validated curve's shape up to a positive uniform scale.
    """
    name = 'exact_cartesian_translation_scale'

    def __init__(self, length_unit_m):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.projection_tolerance = 1e-7
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
        if checks.invalid_similarity_radius(radius):
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

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f'Expected {len(space.orders)} finite update coefficients.')
        return a

    def geometry_update(self, normal_update, *, prepared):
        return geometry_update(normal_update, prepared=prepared, settings=self)


def geometry_update(normal_update, *, prepared, settings):
    """Translate the zero mode and uniformly scale every nonzero mode.

    The prepared base is validated once. A finite positive scale preserves
    its regularity, orientation and lack of intersections without resampling.
    ``normal_update`` contains (translation_x, translation_y, radius_change).
    """
    space, method = prepared, settings
    curve = space.curve
    started = perf_counter()
    method.counts['trial_constructions'] += 1
    try:
        step = method._checked(space, normal_update)
        factor = float(1+step[2]/space.radius_m)
        if checks.invalid_similarity_factor(factor):
            raise UpdateRefused('invalid_scale', 'Similarity scale must be finite and strictly positive.')
        if not np.any(step):
            candidate = curve
        else:
            c = curve.coefficients*factor
            c[curve.band] = curve.coefficients[curve.band]+complex(*step[:2])/method.length_unit_m
            candidate = FourierCurve(c)
        return candidate, dict(method.measure(space, step), projection_error=0.,
            projection_relative=0., refits=0, finite_path=method.name,
            translation_m=step[:2].tolist(), scale_factor=factor,
            equivalent_radius_m=space.radius_m*factor, intrinsic_validity_preserved=True)
    except UpdateRefused:
        method.counts['refused_trials'] += 1
        raise
    finally:
        method.counts['trial_seconds'] += perf_counter()-started
