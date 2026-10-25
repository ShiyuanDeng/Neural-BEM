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

On CUDA (GU-002) the dense rows, the products and the solve run in float64 and
complex128. The matrix is symmetric, so its eigenvalues are its singular values:
the solve keeps |lambda| > eps n max|lambda|, the cutoff of numpy lstsq with
default rcond, and applies the kept eigenvectors to B^T H. NumPy lstsq on the
CPU stays the reference.
"""
from dataclasses import dataclass, fields
import time

import numpy as np
import torch

from .. import checks
from ..continuation.geometry import FourierCurve, grid_size, integer, normal_basis, values, speed_ratio
from ..errors import UpdateRefused, refusal_from_value_error as _refusal

SAMPLES_PER_MODE = 32  # Q = 32K points; the tested ratio was Q = 1024 at K = 32
CONSTRUCTION = 'z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit'
SOLVES = dict(cpu='pseudo-inverse of the normal equations (numpy lstsq, default rcond)',
              cuda='pseudo-inverse of the normal equations (torch eigh, float64; keeps |lambda| > eps n max|lambda|, '
                   'the numpy lstsq default rcond)')


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
    rank: int                 # kept directions of the (4K+2)-square normal matrix
    seconds: dict             # sampling, transfer, dense (rows and products), solve


@dataclass(frozen=True)
class Samples:
    """The accepted curve at Q points, as the normal equations read it (NumPy or torch)."""
    parameters: object   # t, uniform
    modes: object        # Fourier orders -K..K
    tangent: object      # unit tangent T
    speed: object        # J = |z'|
    basis: object        # H: normal-distance shape of each update coefficient, per metre


class SliderUpdate:
    name = 'slider_even_speed_change'

    def __init__(self, length_unit_m, *, xi=10., device=None):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.xi = float(xi)
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        if self.device not in ('cpu', 'cuda'):
            raise ValueError('device must be cpu or cuda')
        if self.device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('The slider preparation was asked to run on CUDA, which is not available.')
        self.counts = dict(preparations=0, trial_constructions=0, refused_trials=0,
                           preparation_seconds=0., trial_seconds=0., sampling_seconds=0., transfer_seconds=0.,
                           dense_seconds=0., solve_seconds=0., dropped_directions=0)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m, construction=CONSTRUCTION,
                    coordinates='real Fourier coefficients of normal distance h (m) in normalized arclength',
                    gauge='none: keeps the existing speed unevenness; no refit', xi=self.xi,
                    samples=f'{SAMPLES_PER_MODE}K points uniform in t, arclength weights J 2pi/Q',
                    solve=SOLVES[self.device], prepare_device=self.device,
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
        samples = Samples(nodes.parameters, curve.modes, curve.values(Q, 1)/speed, speed,
                          normal_basis(nodes, update_modes)/self.length_unit_m)
        seconds = dict(sampling=time.perf_counter()-started)
        if self.device == 'cpu':
            clock = time.perf_counter()
            normal_matrix, rhs = normal_equations(np, samples, self.xi)
            seconds.update(transfer=0., dense=time.perf_counter()-clock)
            clock = time.perf_counter()
            A, _, rank, _ = np.linalg.lstsq(normal_matrix, rhs, rcond=None)
            seconds['solve'] = time.perf_counter()-clock
        else:
            A, rank, cuda_seconds = _cuda_solve(samples, self.xi)
            seconds.update(cuda_seconds)
        width = 2*curve_modes+1
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        for part, value in seconds.items():
            self.counts[part+'_seconds'] += value
        self.counts['dropped_directions'] += 2*width-int(rank)
        return Prepared(curve, update_modes, curve_modes, self.length_unit_m,
                        np.concatenate(([0], harmonics, harmonics)),
                        ('a0', *[f'a{m}' for m in harmonics], *[f'b{m}' for m in harmonics]),
                        A[:width]+1j*A[width:], Q, grid_size(max(curve_modes, update_modes)), elapsed,
                        int(rank), seconds)

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


def normal_equations(xp, samples, xi):
    """B^T B + xi U^T U and B^T H from the sampled curve, with xp numpy or torch."""
    speed, tangent, modes = samples.speed, samples.tangent, samples.modes
    normal = -1j*tangent
    weights = speed*2*np.pi/len(samples.parameters)
    root = xp.sqrt(weights)[:, None]
    waves = xp.exp(1j*xp.outer(samples.parameters, modes))                 # dz = waves @ dc
    moved = xp.conj(normal)[:, None]*waves                                 # v_n = Re(moved @ dc)
    stretched = xp.conj(tangent)[:, None]*waves*(1j*modes)/speed[:, None]  # dJ/J = Re(stretched @ dc)
    B = xp.hstack((moved.real, -moved.imag))
    U = xp.hstack((stretched.real, -stretched.imag))
    U -= weights@U/weights.sum()                                            # uneven part only
    B, U, H = root*B, root*U, root*samples.basis
    return B.T@B+xi*U.T@U, B.T@H


def _cuda_solve(samples, xi):
    """A = (B^T B + xi U^T U)^+ B^T H on CUDA: one transfer in, rows and products, eigh, one transfer out."""
    seconds = {}
    clock = time.perf_counter()
    cuda = lambda x: torch.as_tensor(np.array(x, dtype=np.result_type(x, float)), device='cuda')
    samples = Samples(**{f.name: cuda(getattr(samples, f.name)) for f in fields(samples)})
    torch.cuda.synchronize()
    seconds['transfer'] = time.perf_counter()-clock
    clock = time.perf_counter()
    normal_matrix, rhs = normal_equations(torch, samples, xi)
    torch.cuda.synchronize()
    seconds['dense'] = time.perf_counter()-clock
    clock = time.perf_counter()
    eigenvalues, eigenvectors = torch.linalg.eigh(normal_matrix)
    size = eigenvalues.abs()
    kept = size > torch.finfo(torch.float64).eps*normal_matrix.shape[0]*size.max()
    V = eigenvectors[:, kept]
    A = V@((V.T@rhs)/eigenvalues[kept, None])
    rank = int(kept.sum())
    torch.cuda.synchronize()
    seconds['solve'] = time.perf_counter()-clock
    clock = time.perf_counter()
    A = A.cpu().numpy()
    seconds['transfer'] += time.perf_counter()-clock
    return A, rank, seconds


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
