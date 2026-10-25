"""Slider: one linear coefficient step dc = A a that moves the boundary normally (GU-001).

The step asks for two things at once: the normal velocity is the requested
push h(t; a) = sum_l a_l psi_l (psi in normalised arclength, as spectral), and
the relative speed change dJ/J is the same everywhere, so the speed
unevenness before the step is kept. With dc as a real vector (real parts, then
imaginary parts) and Q sample points,

    A = argmin ||B dc - H a||^2 + xi ||U dc||^2 = (B^T B + xi U^T U)^+ B^T H,

where B maps dc to the normal velocity, U to the uneven part of dJ/J and H maps
a to h; rows carry the square root of the arclength weights J 2pi/Q. On a
constant-speed curve a parameter shift moves nothing and keeps dJ/J even, so
the matrix is singular there; the pseudo-inverse drops that direction. There is
no resampling, no refit and no crop.
"""
from dataclasses import dataclass
import time

import numpy as np

from .. import checks
from ..continuation.geometry import FourierCurve, grid_size, integer, normal_basis, values, speed_ratio
from ..errors import UpdateRefused, refusal_from_value_error as _refusal

SAMPLES_PER_MODE = 32  # Q = 32K points; the tested ratio was Q = 1024 at K = 32
CONSTRUCTION = 'z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit'


@dataclass(frozen=True)
class Prepared:
    """The slider matrix A at one accepted curve, as complex coefficient directions."""
    curve: FourierCurve
    update_modes: int
    curve_modes: int
    length_unit_m: float
    orders: np.ndarray
    labels: tuple
    derivatives: np.ndarray   # (2K+1, 2M+1) = A, coefficient change per metre, package units
    samples: int
    count: int
    preparation_seconds: float


class SliderUpdate:
    name = 'slider_even_speed_change'

    def __init__(self, length_unit_m, *, xi=10.):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.xi = float(xi)
        self.counts = dict(preparations=0, trial_constructions=0, refused_trials=0,
                           preparation_seconds=0., trial_seconds=0.)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m, construction=CONSTRUCTION,
                    coordinates='real Fourier coefficients of normal distance h (m) in normalized arclength',
                    gauge='none: keeps the existing speed unevenness; no refit', xi=self.xi,
                    samples=f'{SAMPLES_PER_MODE}K points uniform in t, arclength weights J 2pi/Q',
                    solve='pseudo-inverse of the normal equations (numpy lstsq, default rcond)',
                    validity='coefficient area, sampled minimum speed and segment intersections')

    def prepare(self, curve, update_modes, curve_modes):
        started = time.perf_counter()
        update_modes = integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('The accepted curve must already use the stage storage band.')
        harmonics = np.arange(1, update_modes+1)
        Q = SAMPLES_PER_MODE*curve_modes
        nodes = curve.nodes(Q)
        speed = nodes.speeds
        tangent = curve.values(Q, 1)/speed
        normal = -1j*tangent
        weights = speed*2*np.pi/Q
        root = np.sqrt(weights)[:, None]
        waves = np.exp(1j*np.outer(nodes.parameters, curve.modes))          # dz = waves @ dc
        moved = np.conj(normal)[:, None]*waves                              # v_n = Re(moved @ dc)
        stretched = np.conj(tangent)[:, None]*waves*(1j*curve.modes)/speed[:, None]  # dJ/J = Re(stretched @ dc)
        B = np.hstack((moved.real, -moved.imag))
        U = np.hstack((stretched.real, -stretched.imag))
        U -= weights@U/weights.sum()                                         # uneven part only
        H = normal_basis(nodes, update_modes)/self.length_unit_m
        B, U, H = root*B, root*U, root*H
        A = np.linalg.lstsq(B.T@B+self.xi*U.T@U, B.T@H, rcond=None)[0]
        width = 2*curve_modes+1
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        return Prepared(curve, update_modes, curve_modes, self.length_unit_m,
                        np.concatenate(([0], harmonics, harmonics)),
                        ('a0', *[f'a{m}' for m in harmonics], *[f'b{m}' for m in harmonics]),
                        A[:width]+1j*A[width:], Q, grid_size(max(curve_modes, update_modes)), elapsed)

    def velocities(self, space, nodes):
        vectors = values(space.derivatives, nodes.num_nodes)
        n = nodes.normals@np.array([1, 1j])
        return (vectors*np.conj(n[:, None])).real

    def measure(self, space, coefficients):
        """The actual normal move of the step, not the requested h."""
        a = self._checked(space, coefficients)
        n = space.curve.nodes(space.count)
        h = self.velocities(space, n)@a*self.length_unit_m
        w = n.arc_length_weights/n.perimeter
        return dict(maximum_normal_m=float(np.max(np.abs(h))), rms_normal_m=float(np.sqrt(w@h**2)))

    def metric(self, space, kind, smoothing_m=None):
        raise ValueError('slider supports only the Marquardt metric.')

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f"Expected {len(space.orders)} finite update coefficients.")
        return a


def geometry_update(normal_update, *, prepared, settings):
    """Add the linear step A a, then check the resulting curve."""
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
