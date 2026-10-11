"""NU-001 coefficient-space normal update: z_new = z + P_K(g_a N + psi_a z').

N = -i z' = sum_j j z_j w^j is the outward normal times the speed sigma=|z'|.
The step coordinates a are metres: g_a = h_a/sigma_0 with
h_a = a_0 + sum_m a_m cos(m theta) + b_m sin(m theta) in the curve PARAMETER
theta, and sigma_0 = L/(2 pi) the mean speed. Before the crop the normal move
is h_a sigma/sigma_0 metres, so the clips keep their meaning up to the speed
ratio. Arm A has psi = 0. Arm B adds the band-limited Hou-Lowengrub-Shelley
tangential term (compass eq. 11),

    psi_a = -(1/S_0) d^-1[g_a Im(conj(z') z'') - mean],   S_0 = sigma_0^2,

which cancels the first-order change in the speed profile and, by Lemma 1,
leaves the Hadamard weights unchanged before the crop.

The trial map is affine in a, so the shape directions are exact coefficient
arrays (index shifts and one convolution) and the complete-trial derivative
needs no finite differences or resampling. Nothing is reparameterized: the
gauge is monitored (speed ratio), not restored.

Validity is tiered; the first decisive tier ends the test:
  1. exact signed area pi sum j|z_j|^2 > 0 (refuse otherwise);
  2. optional incremental certificate (Lemmas 3-4): rho_c + ||Delta||_1 ||Y||_1 < 1
     against the accepted curve's |W|^2 reciprocal certifies simple and regular;
  3. a Bernstein lower bound on min |z'|^2 from exact FFT samples (refuses a
     sampled irregular curve early; certifies regularity only);
  4. otherwise the baseline sampled test (FourierCurve.validate), so decisions
     match the nodal path whenever the cheaper tiers are inconclusive.
"""
from dataclasses import dataclass
import time

import numpy as np
from scipy.signal import fftconvolve

from bem_inverse.continuation.geometry import FourierCurve, grid_size, integer
from bem_inverse.continuation.updates import LocalSpace, UpdateRefused, _refusal, speed_ratio
from .geometry import values, resize
from .modal_geometry import log_modulus, real_product


def centred(array, band):
    """Centred crop or zero pad of the last axis to half-width ``band``."""
    old = (array.shape[-1]-1)//2
    if old >= band:
        return array[..., old-band:old+band+1]
    pad = [(0, 0)]*(array.ndim-1)+[(band-old, band-old)]
    return np.pad(array, pad)


def basis_products(poly, update_modes):
    """Coefficients of phi_q*poly for phi = (1, cos m, ..., sin m, ...), band P+M, no truncation."""
    P, M = (len(poly)-1)//2, update_modes
    out = np.zeros((2*M+1, 2*(P+M)+1), complex)
    out[0, M:M+2*P+1] = poly
    for m in range(1, M+1):
        up = np.zeros(2*(P+M)+1, complex)
        down = np.zeros(2*(P+M)+1, complex)
        up[M+m:M+m+2*P+1] = poly    # times w^m
        down[M-m:M-m+2*P+1] = poly  # times w^-m
        out[m] = (up+down)/2
        out[M+m] = (up-down)/2j
    return out


def l1(array, axis=-1):
    return np.sum(np.abs(array), axis=axis)


def derivative_norm(coefficients):
    """nu(f) = sum |j||f_j| (Lemma 4 bounds the divided difference by this)."""
    band = (coefficients.shape[-1]-1)//2
    return l1(np.arange(-band, band+1)*coefficients)


def speed_squared(coefficients):
    """Exact coefficients of S=|z'|^2, band 2K (real Laurent polynomial)."""
    modes = np.arange(-(len(coefficients)//2), len(coefficients)//2+1)
    derivative = 1j*modes*coefficients
    return real_product(derivative, derivative, 1)


def signed_area(coefficients):
    modes = np.arange(-(len(coefficients)//2), len(coefficients)//2+1)
    return float(np.pi*np.sum(modes*np.abs(coefficients)**2))


def tangential_terms(coefficients, update_modes, mean_speed_squared):
    """psi_q z' for every basis function (eq. 11), band 3K+M, no truncation."""
    K = len(coefficients)//2
    modes = np.arange(-K, K+1)
    first, second = 1j*modes*coefficients, -modes**2*coefficients
    product = fftconvolve(first[::-1].conj(), second)          # conj(z') z'', band 2K
    curvature_speed = (product-product[::-1].conj())/2j          # Im(conj(z') z'') = kappa sigma^3
    g = basis_products(curvature_speed, update_modes)            # band 2K+M, real functions
    band = (g.shape[1]-1)//2
    order = np.arange(-band, band+1)
    psi = np.zeros_like(g)
    nonzero = order != 0
    psi[:, nonzero] = -g[:, nonzero]/(1j*order[nonzero])/mean_speed_squared
    return fftconvolve(psi, first[None, :], axes=-1), psi


def curve_certificate(curve, window, *, tolerance=1e-12, max_degree=4000):
    """rho_c=||1-|W|^2 Y||_1 and ||Y||_1 for the accepted curve (modal_geometry construction)."""
    started = time.perf_counter()
    z, k = curve.coefficients, curve.band
    quotient = np.zeros((2*k+1, 2*k+1), complex)
    for j in range(1, k+1):
        r = np.arange(j)
        quotient[k+j-1-r, k+r] += z[k+j]
        quotient[k-1-r, k-j+r] -= z[k-j]
    _, interval = log_modulus(real_product(quotient, quotient, 2), window, tolerance, max_degree)
    cert = interval['certificate']
    return dict(window=window, rho=cert['residual'], allowance=cert['allowance'],
                reciprocal_l1=cert['reciprocal_l1'], beta=interval['lower'], Lambda=interval['upper'],
                log_degree=interval['degree'], nu=float(derivative_norm(z)),
                arithmetic_verified=False, rounding_model='heuristic FFT allowance',
                proposal_grid=interval['proposal_grid'],
                seconds=time.perf_counter()-started)


@dataclass(frozen=True)
class NormalSpace(LocalSpace):
    derivatives: np.ndarray        # (2K+1, dim) cropped coefficients per metre (package units)
    uncropped: np.ndarray          # (dim, 2B+1) the same directions before P_K
    mean_speed: float
    count: int
    speed_ratio: float
    certificate: object
    preparation_seconds: float


class NormalUpdate:
    """Exact affine coefficient update; same step-coordinate contract as ProjectedUpdate."""

    def __init__(self, length_unit_m, *, tangential=False, certificate_window=None,
                 regularity_factor=1e-6, regularity_oversampling=32):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.tangential = bool(tangential)
        self.certificate_window = certificate_window
        self.regularity_factor = float(regularity_factor)
        self.regularity_oversampling = int(regularity_oversampling)
        self.name = 'coefficient_normal_hls' if self.tangential else 'coefficient_normal'
        self.counts = dict(preparations=0, geometry_projections=0, trial_constructions=0, refused_trials=0,
                           preparation_seconds=0., trial_seconds=0., certificate_seconds=0.,
                           tier_area_refused=0, tier_certificate_accepted=0, tier_certificate_inconclusive=0,
                           tier_regularity_refused=0, tier_regularity_certified=0, tier_sampled_accepted=0,
                           tier_sampled_refused=0)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m, tangential=self.tangential,
                    construction='z + P_K[sum_q a_q (phi_q N + psi_q z\')]/(sigma_0 L_unit)',
                    coordinates='real Fourier coefficients (m) of h in the curve parameter theta; '
                                'normal move h sigma/sigma_0 before the crop',
                    gauge='none: parameter theta kept; speed ratio monitored, never restored',
                    tangential_term='HLS eq. 11, psi=-(1/S_0) d^-1[g Im(conj z\' z\'\') - mean]'
                                    if self.tangential else 'none',
                    validity='area -> incremental certificate (optional) -> Bernstein regularity -> '
                             'sampled FourierCurve.validate',
                    certificate_window=self.certificate_window,
                    regularity_factor=self.regularity_factor,
                    regularity_oversampling=self.regularity_oversampling)

    def regauge(self, curve, curve_modes):
        integer(curve_modes, 'curve_modes')
        return resize(curve, curve_modes), 0.

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
        speeds = curve.nodes(count).speeds
        mean_speed = float(np.mean(speeds))
        z = curve.coefficients
        directions = basis_products(curve.modes*z, update_modes)
        if self.tangential:
            moves, _ = tangential_terms(z, update_modes, mean_speed**2)
            band = (moves.shape[1]-1)//2
            directions = centred(directions, band)+moves
        directions = directions/(mean_speed*self.length_unit_m)
        derivatives = centred(directions, curve_modes).T.copy()
        certificate = None
        if self.certificate_window:
            # Tier 2 is optional: a curve the certificate cannot certify only loses the shortcut.
            try:
                certificate = curve_certificate(curve, int(self.certificate_window))
                self.counts['certificate_seconds'] += certificate['seconds']
            except ValueError:
                self.counts['certificate_failures'] = self.counts.get('certificate_failures', 0)+1
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        return NormalSpace(curve, update_modes, curve_modes, self.length_unit_m, orders, labels,
                           derivatives=derivatives, uncropped=directions, mean_speed=mean_speed, count=count,
                           speed_ratio=float(np.max(speeds)/np.min(speeds)), certificate=certificate,
                           preparation_seconds=elapsed)

    def velocities(self, space, nodes):
        """Normal displacement per metre at uniform-parameter nodes of ``space.curve`` (package units)."""
        vectors = values(space.derivatives, nodes.num_nodes)
        n = nodes.normals@np.array([1, 1j])
        return (vectors*np.conj(n[:, None])).real

    def measure(self, space, coefficients):
        a = self._checked(space, coefficients)
        n = space.curve.nodes(space.count)
        h = self.velocities(space, n)@a*self.length_unit_m
        w = n.arc_length_weights/n.perimeter
        return dict(maximum_normal_m=float(np.max(np.abs(h))), rms_normal_m=float(np.sqrt(w@h**2)))

    def metric(self, space, kind, smoothing_m=None):
        if kind != 'mass':
            raise ValueError('NU-001 only provides the complete physical mass metric.')
        n = space.curve.nodes(space.count)
        basis = self.velocities(space, n)*self.length_unit_m
        return basis.T@((n.arc_length_weights/n.perimeter)[:, None]*basis)

    def crop_tail(self, space, a):
        full = a@space.uncropped
        total = float(l1(full))
        return 0. if total == 0 else float(l1(full-centred(centred(full, space.curve_modes),
                                                            (full.shape[-1]-1)//2)))/total

    def _regularity(self, coefficients):
        """Tier 3: (sampled min S, Bernstein lower bound on min S, threshold) from exact samples."""
        K = len(coefficients)//2
        S = speed_squared(coefficients)
        count = int(2**np.ceil(np.log2(max(64, self.regularity_oversampling*max(K, 1)))))
        sampled = values(centred(S, min((len(S)-1)//2, count//2-1)), count).real
        centre = (len(S)-1)//2
        variation = float(l1(S)-abs(S[centre]))
        lower = float(np.min(sampled)-.5*(np.pi/count)**2*(2*K)**2*variation)
        mean_speed = float(np.mean(np.sqrt(np.maximum(sampled, 0))))
        return float(np.min(sampled)), lower, (self.regularity_factor*mean_speed)**2

    def validate(self, space, delta, coefficients):
        """Tiered test; returns diagnostics or raises UpdateRefused."""
        area = signed_area(coefficients)
        if not area > 0:
            self.counts['tier_area_refused'] += 1
            raise UpdateRefused('irregular_parameterization', f'exact signed area {area:g} <= 0')
        row = dict(signed_area=area)
        cert = space.certificate
        if cert is not None:
            nu_d = float(derivative_norm(delta))
            bound = cert['rho']+cert['allowance']+(2*cert['nu']*nu_d+nu_d**2)*cert['reciprocal_l1']
            row.update(certificate_bound=bound)
            if bound < 1:
                self.counts['tier_certificate_accepted'] += 1
                row.update(validity_tier='incremental_certificate',
                           certified_W2_lower=(1-bound)/cert['reciprocal_l1'])
                return row
            self.counts['tier_certificate_inconclusive'] += 1
        sampled, lower, threshold = self._regularity(coefficients)
        row.update(sampled_min_speed_squared=sampled, bernstein_min_speed_squared=lower)
        if sampled < threshold:
            self.counts['tier_regularity_refused'] += 1
            raise UpdateRefused('irregular_parameterization', f'sampled min |z\'|^2 {sampled:g} below {threshold:g}')
        if lower > threshold:
            self.counts['tier_regularity_certified'] += 1
            row.update(regularity_certified=True)
        try:
            FourierCurve(coefficients).validate()
        except ValueError as exc:
            self.counts['tier_sampled_refused'] += 1
            raise _refusal(exc) from exc
        self.counts['tier_sampled_accepted'] += 1
        row.update(validity_tier='sampled')
        return row

    def trial(self, space, coefficients):
        started = time.perf_counter()
        self.counts['trial_constructions'] += 1
        a = self._checked(space, coefficients)
        try:
            if not np.any(a):
                return space.curve, dict(projection_error=0., projection_relative=0., maximum_normal_m=0.,
                    rms_normal_m=0., refits=0, speed_ratio=space.speed_ratio, crop_tail=0.,
                    finite_path=self.name, validity_tier='identity')
            delta = space.derivatives@a
            coefficients = space.curve.coefficients+delta
            checks = self.validate(space, delta, coefficients)
            candidate = FourierCurve(coefficients)
            return candidate, dict(projection_error=0., projection_relative=0., **self.measure(space, a),
                speed_ratio=speed_ratio(candidate), crop_tail=self.crop_tail(space, a), refits=0,
                finite_path=self.name, **checks)
        except UpdateRefused:
            self.counts['refused_trials'] += 1
            raise
        except ValueError as exc:
            self.counts['refused_trials'] += 1
            raise _refusal(exc) from exc
        finally:
            self.counts['trial_seconds'] += time.perf_counter()-started

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f'Expected {len(space.orders)} finite update coefficients.')
        return a
