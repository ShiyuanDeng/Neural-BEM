"""Spectral arclength update with direct area, speed and intersection checks.

Preparation batches the complete geometry derivative when requested. A trial
moves the boundary, checks it, resets arclength and subtracts the base projection.
"""
from .. import checks
from dataclasses import dataclass, field
import time
import numpy as np
from ..continuation.geometry import (
    FourierCurve, arclength_angles, grid_size, normal_basis, integer,
    reparameterize, values, speed_ratio,
)
from ..errors import UpdateRefused, refusal_from_value_error as _refusal
import torch

CHUNK_BYTES = 2**29
CONSTRUCTION = 'z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial'


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
    preparation_seconds: float
    cache: dict = field(default_factory=dict, compare=False)


ProjectedSpace = Prepared


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

def spectral_project(curve, coefficients, band, count, length_unit_m, *, validate=False):
    """``geometry.project`` with A replaced by ``arclength_quadrature``; same signature and checks."""
    nodes = curve.nodes(count)
    z = curve.values(count)
    h = normal_basis(nodes, len(coefficients)//2)@coefficients/length_unit_m
    normal = nodes.normals@np.array([1, 1j])
    moved = FourierCurve.from_samples(z+h*normal, count//2-1)
    n = moved.nodes(count)
    if validate:
        checks.check_area(moved.coefficients)
        checks.check_speed(n.speeds)
        checks.check_intersection(n.points)
    return arclength_quadrature(moved, n, band)


def batched_projection(curve, steps, band, count, length_unit_m, device):
    """``spectral_project(curve, a, band, count, unit)[0]`` for every row a of ``steps``."""
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

    def regauge(self, curve, curve_modes):
        """Express an input curve in this strategy's gauge at storage band K."""
        integer(curve_modes, "curve_modes")
        try:
            shape, error = reparameterize(curve, curve_modes, tolerance=self.projection_tolerance)
        except ValueError as exc:
            raise _refusal(exc) from exc
        return shape, float(error)

    def _project(self, *args, **kwargs):
        self.counts['geometry_projections'] += 1
        return spectral_project(*args, **kwargs)

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
            base = self._project(curve, zeros, curve_modes, count, self.length_unit_m)[0]
            fine = self._project(curve, zeros, curve_modes, 2*count, self.length_unit_m)[0]
            columns = []
            for step in eye:
                plus = self._project(curve, step, curve_modes, count, self.length_unit_m)[0]
                minus = self._project(curve, -step, curve_modes, count, self.length_unit_m)[0]
                columns.append((plus-minus)/(2*self.derivative_step_m))
            derivatives = np.stack(columns, axis=1)
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        return Prepared(**plain, derivatives=derivatives, base_projection=base,
                        fine_base_projection=fine, count=count, preparation_seconds=elapsed)

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

    def _base_grid(self, space, count, dimension):
        key = ('base_grid', count, dimension)
        if key not in space.cache:
            nodes = space.curve.nodes(count)
            arrays = (normal_basis(nodes, dimension//2), space.curve.values(count),
                      nodes.normals@np.array([1, 1j]))
            for array in arrays:
                array.setflags(write=False)
            space.cache[key] = (nodes, *arrays)
        return space.cache[key]

    def geometry_update(self, curve, normal_update, *, prepared):
        return geometry_update(curve, normal_update, prepared=prepared, settings=self)

    def trial(self, space, coefficients):
        """Compatibility entry point; use the same implementation as the fitter."""
        return geometry_update(space.curve, coefficients, prepared=space, settings=self)


def geometry_update(curve, normal_update, *, prepared, settings):
    """Move, check and refit a trial on both grids; retain the centred increment."""
    if curve is not prepared.curve and not np.array_equal(curve.coefficients, prepared.curve.coefficients):
        raise ValueError('Prepared geometry belongs to a different curve.')
    started = time.perf_counter()
    settings.counts['trial_constructions'] += 1
    a = settings._checked(prepared, normal_update)
    try:
        if not np.any(a):
            return curve, dict(projection_error=0., projection_relative=0.,
                maximum_normal_m=0., rms_normal_m=0., refits=2, speed_ratio=speed_ratio(curve),
                intentional_projection_mm=0., finite_path=settings.name)

        projections = []
        for count in (prepared.count, 2*prepared.count):
            settings.counts['geometry_projections'] += 1
            nodes, basis, base, normal = settings._base_grid(prepared, count, len(a))
            h = basis@a/settings.length_unit_m
            moved = FourierCurve.from_samples(base+h*normal, count//2-1)

            checked_at = time.perf_counter()
            try:
                checks.check_area(moved.coefficients)
                moved_nodes = moved.nodes(count)
                checks.check_speed(moved_nodes.speeds)
                checks.check_intersection(moved_nodes.points)
            finally:
                settings.counts['sampled_seconds'] += time.perf_counter()-checked_at

            projected_at = time.perf_counter()
            try:
                projections.append(arclength_quadrature(moved, moved_nodes, prepared.curve_modes))
            finally:
                settings.counts['projection_seconds'] += time.perf_counter()-projected_at

        coarse, smoothing = projections[0]
        fine, _ = projections[1]
        c_trial = curve.coefficients+coarse-prepared.base_projection
        c_refined = curve.coefficients+fine-prepared.fine_base_projection
        error = float(np.max(np.abs(values(c_trial-c_refined, 2*prepared.count))))
        radius = settings._base_grid(prepared, prepared.count, len(a))[0].perimeter/(2*np.pi)
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
