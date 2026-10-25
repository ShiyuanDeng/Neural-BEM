"""N-update: z_new = P_K[z + eta N + tau z'], N = -i z' the unnormalised outward normal (GU-001).

eta and tau are real Fourier series of the update band in the curve parameter
t. The unknowns are metres, h = eta J and s = tau J with J = L/(2 pi) the mean
speed, so the coefficient step clip bounds both. Before the crop the boundary
moves h |z'|/J along the unit normal; the tangential slide s only re-spaces
points. The map is linear in the unknowns: its derivatives are exact
coefficient arrays (index shifts and one convolution), with no finite
differences or resampling. Nothing is refitted; the gauge is whatever the
steps make it. Direction construction from NU-001 (deleted in 105af6380),
extended with the tau columns.
"""
from dataclasses import dataclass
import time

import numpy as np

from .. import checks
from ..continuation.geometry import FourierCurve, grid_size, integer, values, speed_ratio
from ..errors import UpdateRefused, refusal_from_value_error as _refusal

CONSTRUCTION = "z + P_K[(h N + s z')/J], N = -i z', J = L/2pi; h, s real series of band M in t; exact derivative"


def basis_products(poly, update_modes):
    """Coefficients of phi_q*poly for phi = (1, cos m, ..., sin m, ...), band P+M, no truncation."""
    P, M = (len(poly)-1)//2, update_modes
    out = np.zeros((2*M+1, 2*(P+M)+1), complex)
    out[0, M:M+2*P+1] = poly
    for m in range(1, M+1):
        up = np.zeros(2*(P+M)+1, complex)
        down = np.zeros(2*(P+M)+1, complex)
        up[M+m:M+m+2*P+1] = poly    # times e^{imt}
        down[M-m:M-m+2*P+1] = poly  # times e^{-imt}
        out[m] = (up+down)/2
        out[M+m] = (up-down)/2j
    return out


def crop(array, band):
    """Centred crop of the last axis to half-width ``band`` (P_K)."""
    old = (array.shape[-1]-1)//2
    return array[..., old-band:old+band+1]


@dataclass(frozen=True)
class Prepared:
    """Exact coefficient directions of the h and s unknowns at one accepted curve."""
    curve: FourierCurve
    update_modes: int
    curve_modes: int
    length_unit_m: float
    orders: np.ndarray
    labels: tuple
    derivatives: np.ndarray   # (2K+1, 2(2M+1)) coefficient change per metre, package units
    mean_speed: float
    count: int
    preparation_seconds: float


class NUpdate:
    name = 'n_update_normal_and_tangent_coefficients'

    def __init__(self, length_unit_m):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.counts = dict(preparations=0, trial_constructions=0, refused_trials=0,
                           preparation_seconds=0., trial_seconds=0.)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m, construction=CONSTRUCTION,
                    coordinates='real Fourier coefficients (m) of h (normal) then s (tangential) in the curve parameter t',
                    gauge='none: no refit; the tangential unknowns s and an optional level penalty act on it',
                    validity='coefficient area, sampled minimum speed and segment intersections')

    def prepare(self, curve, update_modes, curve_modes):
        started = time.perf_counter()
        update_modes = integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('The accepted curve must already use the stage storage band.')
        harmonics = np.arange(1, update_modes+1)
        orders = np.concatenate(([0], harmonics, harmonics))
        labels = ('a0', *[f'a{m}' for m in harmonics], *[f'b{m}' for m in harmonics])
        count = grid_size(max(curve_modes, update_modes))
        mean_speed = float(np.mean(curve.nodes(count).speeds))
        normal = curve.modes*curve.coefficients           # N = -i z'
        tangent = 1j*curve.modes*curve.coefficients       # z'
        directions = np.vstack((basis_products(normal, update_modes), basis_products(tangent, update_modes)))
        derivatives = crop(directions, curve_modes).T/(mean_speed*self.length_unit_m)
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        return Prepared(curve, update_modes, curve_modes, self.length_unit_m, np.concatenate((orders, orders)),
                        labels+tuple('s_'+label for label in labels), derivatives, mean_speed, count, elapsed)

    def velocities(self, space, nodes):
        vectors = values(space.derivatives, nodes.num_nodes)
        n = nodes.normals@np.array([1, 1j])
        return (vectors*np.conj(n[:, None])).real

    def measure(self, space, coefficients):
        """The actual normal move after the crop, not the requested h."""
        a = self._checked(space, coefficients)
        n = space.curve.nodes(space.count)
        h = self.velocities(space, n)@a*self.length_unit_m
        w = n.arc_length_weights/n.perimeter
        return dict(maximum_normal_m=float(np.max(np.abs(h))), rms_normal_m=float(np.sqrt(w@h**2)))

    def metric(self, space, kind, smoothing_m=None):
        raise ValueError('n_update supports only the Marquardt metric: its s columns have no normal move.')

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f"Expected {len(space.orders)} finite update coefficients.")
        return a


def geometry_update(normal_update, *, prepared, settings):
    """Add the exact cropped coefficient step, then check the resulting curve."""
    started = time.perf_counter()
    settings.counts['trial_constructions'] += 1
    a = settings._checked(prepared, normal_update)
    try:
        candidate = FourierCurve(prepared.curve.coefficients+prepared.derivatives@a)
        checks.check_area(candidate.coefficients)
        final_nodes = candidate.nodes(grid_size(candidate.band))
        checks.check_speed(final_nodes.speeds)
        checks.check_intersection(final_nodes.points)
        return candidate, dict(**settings.measure(prepared, a), speed_ratio=speed_ratio(candidate),
                               refits=0, finite_path=settings.name)
    except UpdateRefused:
        settings.counts['refused_trials'] += 1
        raise
    except ValueError as exc:
        settings.counts['refused_trials'] += 1
        raise _refusal(exc) from exc
    finally:
        settings.counts['trial_seconds'] += time.perf_counter()-started
