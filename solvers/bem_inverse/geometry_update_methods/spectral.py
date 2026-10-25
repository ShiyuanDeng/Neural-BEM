"""Spectral arclength update with direct area, speed and intersection checks.

Preparation batches the complete geometry derivative when requested. A trial
moves the boundary, resets arclength, subtracts the base projection and checks
the resulting curve.
"""
from .. import checks
from dataclasses import dataclass
import time
import numpy as np
from ..continuation.geometry import (
    FourierCurve, arclength_angles, grid_size, normal_basis, integer, values, speed_ratio,
)
from ..errors import UpdateRefused, refusal_from_value_error as _refusal
import torch

CHUNK_BYTES = 2**29
CONSTRUCTION = 'z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial'


@dataclass(frozen=True)
class Grid:
    """The accepted curve sampled at uniform nodes, as every trial reads it."""
    nodes: object        # accepted-curve nodes
    values: np.ndarray   # boundary points z
    normal: np.ndarray   # unit normals n
    basis: np.ndarray    # column j: normal-distance shape of update coefficient j


def sample_grid(curve, count, update_modes):
    """Sample ``curve`` at ``count`` nodes with the normal basis of ``update_modes``."""
    nodes = curve.nodes(count)
    grid = Grid(nodes, curve.values(count), nodes.normals@np.array([1, 1j]),
                normal_basis(nodes, update_modes))
    for array in (grid.values, grid.normal, grid.basis):
        array.setflags(write=False)
    return grid


@dataclass(frozen=True)
class Prepared:
    """Directions and projection data for this method at one accepted curve."""
    curve: FourierCurve
    update_modes: int
    curve_modes: int
    length_unit_m: float
    orders: np.ndarray
    labels: tuple
    derivatives: np.ndarray
    base_projection: np.ndarray
    fine_base_projection: np.ndarray
    count: int
    grid: Grid
    fine_grid: Grid
    preparation_seconds: float


def arclength_quadrature(moved, nodes, band):
    """Coefficients |k| <= band of the arclength curve of ``moved`` by eq. 9 on its uniform nodes.

    Returns (coefficients, crop error): the error is max |P_band R(moved)(alpha_i) - moved(theta_i)|,
    the same intentional-smoothing quantity ``project`` reports, sampled at alpha(theta_i).
    """
    angles, length = arclength_angles(nodes)
    count = nodes.num_nodes
    w = moved.values(count)
    weights = w*nodes.speeds/(length/(2*np.pi))
    step = np.exp(-1j*angles)
    powers = np.empty((band+1, count), complex)
    powers[0] = 1.
    for k in range(1, band+1):
        powers[k] = powers[k-1]*step                       # e^{-i k alpha}
    positive = powers@weights/count                        # k = 0..band
    negative = np.conj(powers[1:])@weights/count           # k = -1..-band
    coefficients = np.concatenate((negative[::-1], positive))
    evaluated = coefficients[band]+np.conj(powers[1:]).T@positive[1:]+powers[1:].T@negative
    return coefficients, float(np.max(np.abs(evaluated-w)))

def push_and_refit(grid, coefficients, band, length_unit_m):
    """Move every sample by h along its normal, then refit the moved curve in arclength.

    Returns ``arclength_quadrature`` of the moved curve: coefficients |k| <= band and crop error.
    """
    count = grid.nodes.num_nodes
    h = grid.basis@coefficients/length_unit_m
    moved = FourierCurve.from_samples(grid.values+h*grid.normal, count//2-1)
    return arclength_quadrature(moved, moved.nodes(count), band)


def batched_projection(curve, steps, band, count, length_unit_m, device):
    """``push_and_refit(sample_grid(curve, count, m), a, band, unit)[0]`` for every row a of ``steps``."""
    nodes = curve.nodes(count)
    z = torch.as_tensor(curve.values(count), device=device)
    basis = torch.as_tensor(normal_basis(nodes, steps.shape[1]//2), device=device)
    normal = torch.as_tensor(nodes.normals@np.array([1, 1j]), device=device)
    moved = z[None]+(torch.as_tensor(steps, device=device)@basis.T/length_unit_m)*normal[None]
    spectrum = torch.fft.fft(moved, dim=1)/count
    spectrum[:, count//2] = 0                                    # from_samples keeps |j| <= count/2-1
    modes = torch.fft.fftfreq(count, d=1/count, device=device).to(torch.float64)
    values = torch.fft.ifft(spectrum, dim=1)*count
    speeds = (torch.fft.ifft(spectrum*(1j*modes), dim=1)*count).abs()
    speed = torch.fft.fft(speeds, dim=1)/count
    primitive = torch.zeros_like(speed)
    primitive[:, 1:] = speed[:, 1:]/(1j*modes[1:])
    oscillation = (torch.fft.ifft(primitive, dim=1)*count).real
    theta = 2*np.pi*torch.arange(count, device=device, dtype=torch.float64)/count
    distance = speed[:, :1].real*theta+oscillation-oscillation[:, :1]
    length = 2*np.pi*speed[:, 0].real
    gaps = torch.diff(torch.cat((distance, length[:, None]), 1), dim=1)
    checks.require_arclength_monotone(gaps)
    angles = 2*np.pi*distance/length[:, None]
    weights = values*speeds/(length[:, None]/(2*np.pi))
    k = torch.arange(band+1, device=device, dtype=torch.float64)
    rows = max(1, CHUNK_BYTES//(16*(band+1)*count))
    out = []
    for i in range(0, len(steps), rows):
        powers = torch.exp(-1j*k[None, :, None]*angles[i:i+rows, None, :])
        positive = torch.einsum('pkn,pn->pk', powers, weights[i:i+rows])/count
        negative = torch.einsum('pkn,pn->pk', powers[:, 1:].conj(), weights[i:i+rows])/count
        out.append(torch.cat((negative.flip(1), positive), 1))
    return torch.cat(out).cpu().numpy()


class SpectralProjectedUpdate:
    name = "centred_state_band_spectral_projection"

    def __init__(self, length_unit_m, *, projection_tolerance=1e-5, derivative_step_m=1e-7, device=None, batched=False):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        if not np.isfinite(projection_tolerance) or projection_tolerance <= 0:
            raise ValueError('projection_tolerance must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.projection_tolerance = float(projection_tolerance)
        self.derivative_step_m = float(derivative_step_m)
        checks.require_derivative_step(self.derivative_step_m)
        self.counts = dict(preparations=0, geometry_projections=0, trial_constructions=0,
                          refused_trials=0, preparation_seconds=0., trial_seconds=0.)
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.batched = bool(batched)
        self.counts.update(batched_preparations=0, prepare_fallbacks=0,
                           sampled_seconds=0., projection_seconds=0.)
        self.fallback_reasons = {}

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m,
                    projection_tolerance=self.projection_tolerance,
                    coordinates='real Fourier coefficients of normal distance h (m) in normalized arclength',
                    gauge='arclength refit on every trial', derivative_step_m=self.derivative_step_m,
                    construction=CONSTRUCTION,
                    resampler='eq. 9 quadrature on the uniform grid (count and 2*count); no splines',
                    boundary_samples=True, projection_error_control='coarse/fine diagnostic; not a rigorous bound',
                    validity='coefficient area, sampled minimum speed and segment intersections',
                    prepare='batched torch float64' if self.batched else 'coordinate finite differences',
                    prepare_device=self.device if self.batched else 'cpu', chunk_bytes=CHUNK_BYTES,
                    projection_tolerance_meaning='grid refinement, not intentional smoothing')

    def _project(self, grid, coefficients, band):
        self.counts['geometry_projections'] += 1
        return push_and_refit(grid, coefficients, band, self.length_unit_m)

    def prepare(self, curve, update_modes, curve_modes):
        started = time.perf_counter()
        update_modes = integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('The accepted curve must already use the stage storage band.')
        harmonics = np.arange(1, update_modes+1)
        plain = dict(curve=curve, update_modes=update_modes, curve_modes=curve_modes,
                     length_unit_m=self.length_unit_m,
                     orders=np.concatenate(([0], harmonics, harmonics)),
                     labels=('a0', *[f'a{m}' for m in harmonics], *[f'b{m}' for m in harmonics]))
        count = grid_size(max(curve_modes, update_modes))
        grid, fine_grid = sample_grid(curve, count, update_modes), sample_grid(curve, 2*count, update_modes)
        dim = len(plain['orders'])
        eye = np.eye(dim)*self.derivative_step_m
        steps = np.vstack((np.zeros(dim), eye, -eye))
        use_batch = self.batched
        if use_batch:
            try:
                coarse = batched_projection(curve, steps, curve_modes, count, self.length_unit_m, self.device)
                fine = batched_projection(curve, steps[:1], curve_modes, 2*count, self.length_unit_m, self.device)[0]
            except torch.OutOfMemoryError as exc:
                torch.cuda.empty_cache()
                self.counts['prepare_fallbacks'] += 1
                self.fallback_reasons[type(exc).__name__] = self.fallback_reasons.get(type(exc).__name__, 0)+1
                use_batch = False
        if use_batch:
            self.counts['geometry_projections'] += len(steps)+1
            derivatives = ((coarse[1:dim+1]-coarse[dim+1:])/(2*self.derivative_step_m)).T.copy()
            self.counts['batched_preparations'] += 1
            base = coarse[0]
        else:
            zeros = np.zeros(dim)
            base = self._project(grid, zeros, curve_modes)[0]
            fine = self._project(fine_grid, zeros, curve_modes)[0]
            columns = []
            for step in eye:
                plus = self._project(grid, step, curve_modes)[0]
                minus = self._project(grid, -step, curve_modes)[0]
                columns.append((plus-minus)/(2*self.derivative_step_m))
            derivatives = np.stack(columns, axis=1)
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        return Prepared(**plain, derivatives=derivatives, base_projection=base,
                        fine_base_projection=fine, count=count, grid=grid, fine_grid=fine_grid,
                        preparation_seconds=elapsed)

    def velocities(self,space,nodes):
        vectors=values(space.derivatives,nodes.num_nodes)
        n=nodes.normals@np.array([1,1j])
        return (vectors*np.conj(n[:,None])).real

    def measure(self,space,coefficients):
        a=self._checked(space,coefficients)
        n=space.curve.nodes(space.count)
        # Derivatives are in package units per metre. Convert the resulting
        # normal displacement back to metres for the backend's physical units.
        h=self.velocities(space,n)@a*self.length_unit_m
        w=n.arc_length_weights/n.perimeter
        return dict(maximum_normal_m=float(np.max(np.abs(h))),rms_normal_m=float(np.sqrt(w@h**2)))

    def metric(self,space,kind,smoothing_m=None):
        if kind!='mass':
            raise ValueError('SC-035 only qualifies the complete physical mass metric.')
        n=space.curve.nodes(space.count)
        basis=self.velocities(space,n)*self.length_unit_m
        return basis.T@((n.arc_length_weights/n.perimeter)[:,None]*basis)

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f"Expected {len(space.orders)} finite update coefficients.")
        return a

    def geometry_update(self, normal_update, *, prepared):
        return geometry_update(normal_update, prepared=prepared, settings=self)


def geometry_update(normal_update, *, prepared, settings):
    """Move and refit on both grids, retain the centred increment, then check the result.

    The moved curves are not checked: refitting and centring change them, so
    only the final curve is the boundary that is used.
    """
    curve = prepared.curve
    started = time.perf_counter()
    settings.counts['trial_constructions'] += 1
    a = settings._checked(prepared, normal_update)
    try:
        if not np.any(a):
            return curve, dict(projection_error=0., projection_relative=0.,
                maximum_normal_m=0., rms_normal_m=0., refits=2, speed_ratio=speed_ratio(curve),
                intentional_projection_mm=0., finite_path=settings.name)

        projections = []
        for grid in (prepared.grid, prepared.fine_grid):
            settings.counts['geometry_projections'] += 1
            projected_at = time.perf_counter()
            try:
                projections.append(push_and_refit(grid, a, prepared.curve_modes, settings.length_unit_m))
            finally:
                settings.counts['projection_seconds'] += time.perf_counter()-projected_at

        coarse, smoothing = projections[0]
        fine, _ = projections[1]
        c_trial = curve.coefficients+coarse-prepared.base_projection
        c_refined = curve.coefficients+fine-prepared.fine_base_projection
        error = float(np.max(np.abs(values(c_trial-c_refined, 2*prepared.count))))
        radius = prepared.grid.nodes.perimeter/(2*np.pi)
        checks.require_projection_agreement(error, radius, settings.projection_tolerance)

        candidate = FourierCurve(c_trial)
        checked_at = time.perf_counter()
        try:
            checks.check_area(candidate.coefficients)
            final_nodes = candidate.nodes(grid_size(candidate.band))
            checks.check_speed(final_nodes.speeds)
            checks.check_intersection(final_nodes.points)
        finally:
            settings.counts['sampled_seconds'] += time.perf_counter()-checked_at
        return candidate, dict(projection_error=error, projection_relative=error/radius,
            **settings.measure(prepared, a), speed_ratio=speed_ratio(candidate), refits=2,
            intentional_projection_mm=smoothing*settings.length_unit_m*1e3, finite_path=settings.name)
    except UpdateRefused:
        settings.counts['refused_trials'] += 1
        raise
    except ValueError as exc:
        settings.counts['refused_trials'] += 1
        raise _refusal(exc) from exc
    finally:
        settings.counts['trial_seconds'] += time.perf_counter()-started
