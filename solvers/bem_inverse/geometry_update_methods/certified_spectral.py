"""Optional spectral geometry update with continuous-curve certificate checks.

Preparation, displacement measurement and finite construction are together here.
The ordinary ``spectral`` method uses direct sampled checks instead. Certificate
mathematics lives in ``certificates``; no check calls back into this method.
"""
from dataclasses import dataclass, field
import time
import numpy as np
import torch

from .. import checks
from ..errors import UpdateRefused, refusal_from_value_error
from ..continuation.geometry import (
    FourierCurve, grid_size, integer, normal_basis, reparameterize,
    signed_area, speed_ratio, values,
)
from .spectral import CHUNK_BYTES, arclength_quadrature, batched_projection, push_and_refit, sample_grid
from .certificates import curve_certificate, derivative_norm, device_certificate, increment_bound, regularity_floor

CONSTRUCTION = 'z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial'
WINDOW = 64
FULL_WINDOWS = (64, 128)
SPEED_FACTOR = 1e-6
ROLES = ('moved_coarse', 'moved_fine', 'candidate')
TIERS = ('area_refused', 'increment', 'full', 'sampled_accepted', 'sampled_refused', 'full_override')
ORDERS = ('certificate_first', 'sampled_first')
VALIDITY = ('exact area -> Lemma 3-4 increment vs accepted-curve Y -> full |W|^2 certificate '
            '(crop + Lemma 3 tail) -> sampled test (unchanged fallback)')
VALIDITY_SAMPLED_FIRST = ('exact area -> Lemma 3-4 increment vs accepted-curve Y -> sampled test -> '
                          'full |W|^2 certificate only to overturn a sampled refusal (same accept set)')


def pad(coefficients, band):
    old = len(coefficients)//2
    if old >= band:
        return coefficients[old-band:old+band+1]
    return np.pad(coefficients, (band-old,)*2)


@dataclass(frozen=True)
class CertifiedSpace:
    """Data tied to this curve and these normal-update coordinates."""
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


class CertifiedSpectralUpdate:
    """Self-contained optional method; batching and certificate device are settings."""
    name = 'centred_state_band_spectral_projection'

    def __init__(self, length_unit_m, *, projection_tolerance=1e-5, derivative_step_m=1e-7,
                 window=WINDOW, shadow=False, order='certificate_first', batched=False,
                 device=None, certificate_device=False):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        if not np.isfinite(projection_tolerance) or projection_tolerance <= 0:
            raise ValueError('projection_tolerance must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.projection_tolerance = float(projection_tolerance)
        self.derivative_step_m = float(derivative_step_m)
        checks.require_derivative_step(self.derivative_step_m)
        if order not in ORDERS:
            raise ValueError(f'Unknown validity order {order!r}; choose from {ORDERS}')
        if shadow and order != 'certificate_first':
            raise ValueError('The shadow comparison needs the certificate_first order')
        self.window, self.shadow, self.order = int(window), bool(shadow), order
        self.batched = bool(batched)
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.certificate_device = bool(certificate_device)
        self.counts = dict(preparations=0, geometry_projections=0, trial_constructions=0,
                           refused_trials=0, preparation_seconds=0., trial_seconds=0.)
        self.counts.update({f'{r}_{t}': 0 for r in ROLES for t in TIERS})
        self.counts.update(base_certificates=0, base_certificate_failures=0, full_certificate_failures=0,
                           certificate_seconds=0., sampled_seconds=0., projection_seconds=0., shadow_disagreements=0)
        if self.batched:
            self.counts.update(batched_preparations=0, prepare_fallbacks=0)
        if self.certificate_device:
            self.counts['device_certificate_fallbacks'] = 0
        self.fallback_reasons = {}
        self.records = []

    def settings(self):
        settings = dict(name=self.name, length_unit_m=self.length_unit_m,
            projection_tolerance=self.projection_tolerance,
            coordinates='real Fourier coefficients of normal distance h (m) in normalized arclength',
            gauge='arclength refit on every trial', derivative_step_m=self.derivative_step_m,
            construction=CONSTRUCTION, projection_tolerance_meaning='grid refinement, not intentional smoothing',
            resampler='eq. 9 quadrature on the uniform grid (count and 2*count); no splines',
            boundary_samples=True, projection_error_control='coarse/fine diagnostic; not a rigorous bound',
            validity=VALIDITY if self.order == 'certificate_first' else VALIDITY_SAMPLED_FIRST,
            validity_order=self.order, certificate_window=self.window,
            full_certificate_windows=FULL_WINDOWS, full_crop_band='max(K, 64)',
            regularity='coefficient residual lower bound >= 1e-12 sum j^2|x_j|^2', shadow=self.shadow,
            certificate_arithmetic='float64 with heuristic FFT rounding allowance; not interval verified',
            sampled_validity_fallback=True)
        if self.batched:
            settings.update(prepare='batched torch float64 (NU-006)', prepare_device=self.device,
                            chunk_bytes=CHUNK_BYTES)
        if self.certificate_device:
            settings.update(certificate='torch float64 port of curve_certificate (NU-007)',
                            certificate_device=self.device)
        return settings

    def regauge(self, curve, curve_modes):
        integer(curve_modes, 'curve_modes')
        try:
            shape, error = reparameterize(curve, curve_modes, tolerance=self.projection_tolerance)
        except ValueError as exc:
            raise refusal_from_value_error(exc) from exc
        return shape, float(error)

    def _project(self, grid, coefficients, band):
        self.counts['geometry_projections'] += 1
        return push_and_refit(grid, coefficients, band, self.length_unit_m)

    def prepare(self, curve, update_modes, curve_modes):
        """Differentiate this method's spectral projection and save both base grids."""
        started = time.perf_counter()
        update_modes = integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('The accepted curve must already use the stage storage band.')
        harmonics = np.arange(1, update_modes+1)
        orders = np.concatenate(([0], harmonics, harmonics))
        labels = ('a0', *[f'a{m}' for m in harmonics], *[f'b{m}' for m in harmonics])
        count = grid_size(max(curve_modes, update_modes))
        dim = len(orders)
        coarse = None
        if self.batched:
            eye = np.eye(dim)*self.derivative_step_m
            steps = np.vstack((np.zeros(dim), eye, -eye))
            try:
                coarse = batched_projection(curve, steps, curve_modes, count, self.length_unit_m, self.device)
                fine = batched_projection(curve, steps[:1], curve_modes, 2*count, self.length_unit_m, self.device)[0]
            except torch.OutOfMemoryError as exc:
                torch.cuda.empty_cache()
                self.counts['prepare_fallbacks'] += 1
                self.fallback_reasons[type(exc).__name__] = self.fallback_reasons.get(type(exc).__name__, 0)+1
                coarse = None
                started = time.perf_counter()
        if coarse is None:
            zeros = np.zeros(dim)
            grid, fine_grid = sample_grid(curve, count, update_modes), sample_grid(curve, 2*count, update_modes)
            base = self._project(grid, zeros, curve_modes)[0]
            fine = self._project(fine_grid, zeros, curve_modes)[0]
            columns = []
            for j in range(dim):
                step = np.eye(dim)[j]*self.derivative_step_m
                plus = self._project(grid, step, curve_modes)[0]
                minus = self._project(grid, -step, curve_modes)[0]
                columns.append((plus-minus)/(2*self.derivative_step_m))
            derivatives = np.stack(columns, axis=1)
        else:
            self.counts['geometry_projections'] += len(steps)+1
            self.counts['batched_preparations'] += 1
            base = coarse[0]
            derivatives = ((coarse[1:dim+1]-coarse[dim+1:])/(2*self.derivative_step_m)).T.copy()
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        return CertifiedSpace(curve, update_modes, curve_modes, self.length_unit_m, orders, labels,
            derivatives, base, fine, count, elapsed)

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f'Expected {len(space.orders)} finite update coefficients.')
        return a

    def velocities(self, space, nodes):
        vectors = values(space.derivatives, nodes.num_nodes)
        normal = nodes.normals@np.array([1, 1j])
        return (vectors*np.conj(normal[:, None])).real

    def measure(self, space, coefficients):
        a = self._checked(space, coefficients)
        nodes = space.curve.nodes(space.count)
        h = self.velocities(space, nodes)@a*self.length_unit_m
        weights = nodes.arc_length_weights/nodes.perimeter
        return dict(maximum_normal_m=float(np.max(np.abs(h))), rms_normal_m=float(np.sqrt(weights@h**2)))

    def metric(self, space, kind, smoothing_m=None):
        if kind != 'mass':
            raise ValueError('SC-035 only qualifies the complete physical mass metric.')
        nodes = space.curve.nodes(space.count)
        basis = self.velocities(space, nodes)*self.length_unit_m
        return basis.T@((nodes.arc_length_weights/nodes.perimeter)[:, None]*basis)

    def _certificate(self, curve, window):
        started = time.perf_counter()
        try:
            if self.certificate_device:
                try:
                    return device_certificate(curve, window, self.device)
                except torch.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    self.counts['device_certificate_fallbacks'] += 1
            return curve_certificate(curve, window)
        except ValueError:
            return None
        finally:
            self.counts['certificate_seconds'] += time.perf_counter()-started

    def _base(self, space):
        # Lazy: some prepared states stop before any trial needs this certificate.
        if 'certificate' not in space.cache:
            certificate = self._certificate(space.curve, self.window)
            self.counts['base_certificates' if certificate else 'base_certificate_failures'] += 1
            space.cache['certificate'] = certificate
        return space.cache['certificate']

    def _cheap(self, space, coefficients):
        area = signed_area(coefficients)
        row = dict(band=len(coefficients)//2, signed_area=area)
        if not area > 0:
            return 'refused', row, None
        floor = regularity_floor(coefficients)
        base = self._base(space)
        if base is not None:
            band = max(len(coefficients)//2, space.curve.band)
            change = pad(coefficients, band)-pad(space.curve.coefficients, band)
            bound, lower, nu = increment_bound(base, change)
            row.update(increment_bound=bound, increment_lower=lower, increment_nu=nu)
            if bound < 1 and lower >= floor:
                return 'increment', row, floor
        return None, row, floor

    def _full(self, space, coefficients, row, floor):
        crop = min(len(coefficients)//2, max(space.curve.band, WINDOW))
        cropped = FourierCurve(pad(coefficients, crop))
        tail = pad(coefficients, len(coefficients)//2)-pad(cropped.coefficients, len(coefficients)//2)
        for window in FULL_WINDOWS:
            certificate = self._certificate(cropped, window)
            if certificate is None:
                self.counts['full_certificate_failures'] += 1
                row.setdefault('full_failed_windows', []).append(window)
                continue
            bound, lower, nu = increment_bound(certificate, tail)
            row.update(full_window=window, full_bound=bound, full_lower=lower, tail_nu=nu,
                       full_rho=certificate['rho'], full_reciprocal_l1=certificate['reciprocal_l1'],
                       full_log_degree=certificate['log_degree'])
            if bound < 1 and lower >= floor:
                return 'full'
        return None

    def certify(self, space, coefficients):
        """Retained research interface: certificate-only decision and evidence."""
        tier, row, floor = self._cheap(space, coefficients)
        if tier is None:
            tier = self._full(space, coefficients, row, floor)
        return tier, row

    def _sampled(self, sampled):
        """Check concrete curve/node data, never a callback into trial construction."""
        started = time.perf_counter()
        try:
            if isinstance(sampled, FourierCurve):
                checks.require_sampled_stored_curve(sampled.nodes(grid_size(sampled.band)))
            else:
                checks.require_sampled_moved_curve(sampled)
        finally:
            self.counts['sampled_seconds'] += time.perf_counter()-started

    def check_geometry(self, space, coefficients, role, sampled):
        """Visible certificate/sample decision; every mathematical input is explicit."""
        tier, row, floor = self._cheap(space, coefficients)
        if tier == 'refused':
            self.counts[f'{role}_area_refused'] += 1
            self.records.append(dict(row, role=role, tier='area_refused'))
            raise UpdateRefused('irregular_parameterization', f'exact signed area {row["signed_area"]:g} <= 0')
        if tier is None and self.order == 'certificate_first':
            tier = self._full(space, coefficients, row, floor)
        if tier is not None:
            self.counts[f'{role}_{tier}'] += 1
            if self.shadow:
                try:
                    self._sampled(sampled)
                    row['shadow'] = 'accepted'
                except (UpdateRefused, ValueError) as exc:
                    row['shadow'] = 'refused: '+str(exc)
                    self.counts['shadow_disagreements'] += 1
            self.records.append(dict(row, role=role, tier=tier))
            return
        try:
            self._sampled(sampled)
        except (UpdateRefused, ValueError):
            if self.order == 'sampled_first' and self._full(space, coefficients, row, floor) == 'full':
                self.counts[f'{role}_full_override'] += 1
                self.records.append(dict(row, role=role, tier='full_override'))
                return
            self.counts[f'{role}_sampled_refused'] += 1
            self.records.append(dict(row, role=role, tier='sampled_refused'))
            raise
        self.counts[f'{role}_sampled_accepted'] += 1
        self.records.append(dict(row, role=role, tier='sampled_accepted'))

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

    def geometry_update(self, normal_update, *, prepared):
        return geometry_update(normal_update, prepared=prepared, settings=self)

    def trial(self, space, coefficients):
        """Compatibility entry point; the finite construction is below."""
        return geometry_update(coefficients, prepared=space, settings=self)


def geometry_update(normal_update, *, prepared, settings):
    """Move along normals, check, project at two grids, then check the stored curve."""
    space, method = prepared, settings
    curve = space.curve
    started = time.perf_counter()
    method.counts['trial_constructions'] += 1
    method.records = []
    a = method._checked(space, normal_update)
    try:
        if not np.any(a):
            return curve, dict(projection_error=0., projection_relative=0., maximum_normal_m=0.,
                rms_normal_m=0., refits=2, speed_ratio=speed_ratio(curve),
                intentional_projection_mm=0., finite_path=method.name)
        projections = []
        for count, role in ((space.count, 'moved_coarse'), (2*space.count, 'moved_fine')):
            method.counts['geometry_projections'] += 1
            nodes, basis, base, normal = method._base_grid(space, count, len(a))
            h = basis@a/method.length_unit_m
            moved = FourierCurve.from_samples(base+h*normal, count//2-1)
            moved_nodes = moved.nodes(count)
            method.check_geometry(space, moved.coefficients, role, moved_nodes)
            projection_started = time.perf_counter()
            try:
                projections.append(arclength_quadrature(moved, moved_nodes, space.curve_modes))
            finally:
                method.counts['projection_seconds'] += time.perf_counter()-projection_started
        (coarse, smoothing), (fine, _) = projections
        trial = curve.coefficients+coarse-space.base_projection
        refined = curve.coefficients+fine-space.fine_base_projection
        error = float(np.max(np.abs(values(trial-refined, 2*space.count))))
        radius = method._base_grid(space, space.count, len(a))[0].perimeter/(2*np.pi)
        checks.require_projection_agreement(error, radius, method.projection_tolerance)
        candidate = FourierCurve(trial)
        method.check_geometry(space, trial, 'candidate', candidate)
        tiers = {row['role']: row['tier'] for row in method.records}
        return candidate, dict(projection_error=error, projection_relative=error/radius,
            **method.measure(space, a), speed_ratio=speed_ratio(candidate), refits=2,
            intentional_projection_mm=smoothing*method.length_unit_m*1e3, finite_path=method.name,
            validity_tiers=tiers)
    except UpdateRefused:
        method.counts['refused_trials'] += 1
        raise
    except ValueError as exc:
        method.counts['refused_trials'] += 1
        raise refusal_from_value_error(exc) from exc
    finally:
        method.counts['trial_seconds'] += time.perf_counter()-started


def BatchedCertifiedUpdate(length_unit_m, *, device=None, **kwargs):
    """Compatibility constructor for batched preparation without subclass layers."""
    return CertifiedSpectralUpdate(length_unit_m, device=device, batched=True, **kwargs)


def DeviceCertifiedUpdate(length_unit_m, *, device=None, **kwargs):
    """Compatibility constructor for batched preparation and device certificates."""
    return CertifiedSpectralUpdate(length_unit_m, device=device, batched=True, certificate_device=True, **kwargs)
