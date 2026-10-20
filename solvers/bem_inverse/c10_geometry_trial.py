"""C10. Local coordinate proposal → finite stored Cartesian geometry.

The normal displacement is expressed in normalized arclength and measured in
metres. After moving the boundary, spectral quadrature resets arclength and
projects to K_geometry. The centered increment subtracts the base projection,
so a zero step retains the original stored curve exactly.

CertifiedSpectralUpdate.trial constructs on a grid and a doubled grid, checks
their agreement, and validates the final candidate. Intermediate validation
still precedes arclength refitting. Certificate decisions and their sampled
fallback are in checks.py; cache ownership and geometry construction are here.
The optional spline update remains in geometry.py.
"""
from . import checks
from dataclasses import dataclass, field
import time
import numpy as np
from .continuation.geometry import FourierCurve, arclength_angles, normal_basis
from .continuation.updates import UpdateRefused
from .continuation.validation import self_intersections
from .geometry import ProjectedUpdate, ProjectedSpace, values
from .continuation.updates import _refusal, speed_ratio
from .n_update import curve_certificate, derivative_norm, signed_area


CONSTRUCTION = 'z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial'


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
        checks.require_sampled_moved_curve(n)
    return arclength_quadrature(moved, n, band)


class SpectralProjectedUpdate(ProjectedUpdate):
    name = 'centred_state_band_spectral_projection'

    def settings(self):
        return dict(super().settings(), construction=CONSTRUCTION,
                    resampler='eq. 9 quadrature on the uniform grid (count and 2*count); no splines',
                    boundary_samples=True, projection_error_control='coarse/fine diagnostic; not a rigorous bound')

    def _project(self, *args, **kwargs):
        self.counts['geometry_projections'] += 1
        return spectral_project(*args, **kwargs)


WINDOW = 64             # NU-001's certificate window (iteration 08); also the minimum crop band


FULL_WINDOWS = (64, 128)  # tier 3 escalates once when the window-64 reciprocal is not decisive


SPEED_FACTOR = 1e-6     # the sampled test's min speed / mean speed


ROLES = ('moved_coarse', 'moved_fine', 'candidate')


TIERS = ('area_refused', 'increment', 'full', 'sampled_accepted', 'sampled_refused', 'full_override')


ORDERS = ('certificate_first', 'sampled_first')


VALIDITY = ('exact area -> Lemma 3-4 increment vs accepted-curve Y -> full |W|^2 certificate '
            '(crop + Lemma 3 tail) -> sampled test (unchanged fallback)')


# Tiers 2-3 only accept, so certificate_first accepts inc | full | sampled. Running the
# sampled test before the full certificate accepts the same set, raises the same refusal,
# and computes the full certificate only when it could still overturn a sampled refusal.
VALIDITY_SAMPLED_FIRST = ('exact area -> Lemma 3-4 increment vs accepted-curve Y -> sampled test -> '
                          'full |W|^2 certificate only to overturn a sampled refusal (same accept set)')


def pad(coefficients, band):
    old = len(coefficients)//2
    if old >= band:
        return coefficients[old-band:old+band+1]
    return np.pad(coefficients, (band-old,)*2)


regularity_floor = checks.regularity_floor


increment_bound = checks.increment_bound


@dataclass(frozen=True)
class CertifiedSpace(ProjectedSpace):
    cache: dict = field(default_factory=dict, compare=False)   # lazy accepted-curve certificate


class CertifiedSpectralUpdate(SpectralProjectedUpdate):
    """NU-003 trial map; validity by certificate tiers with the sampled test as fallback."""

    def __init__(self, length_unit_m, *, window=WINDOW, shadow=False, order='certificate_first', **kwargs):
        super().__init__(length_unit_m, **kwargs)
        if order not in ORDERS:
            raise ValueError(f'Unknown validity order {order!r}; choose from {ORDERS}')
        if shadow and order != 'certificate_first':
            raise ValueError('The shadow comparison needs the certificate_first order')
        self.window, self.shadow, self.order = int(window), bool(shadow), order
        self.counts.update({f'{r}_{t}': 0 for r in ROLES for t in TIERS})
        self.counts.update(base_certificates=0, base_certificate_failures=0, full_certificate_failures=0,
                           certificate_seconds=0., sampled_seconds=0., projection_seconds=0., shadow_disagreements=0)
        self.records = []   # per-curve tier rows of the latest trial

    def settings(self):
        return dict(super().settings(), validity=VALIDITY if self.order == 'certificate_first' else
                    VALIDITY_SAMPLED_FIRST, validity_order=self.order, certificate_window=self.window,
                    full_certificate_windows=FULL_WINDOWS, full_crop_band='max(K, 64)',
                    regularity='coefficient residual lower bound >= 1e-12 sum j^2|x_j|^2', shadow=self.shadow,
                    certificate_arithmetic='float64 with heuristic FFT rounding allowance; not interval verified',
                    sampled_validity_fallback=True)

    def prepare(self, curve, update_modes, curve_modes):
        space = super().prepare(curve, update_modes, curve_modes)
        return CertifiedSpace(**space.__dict__)

    # ------------------------------------------------------------------ certificates

    def _certificate(self, curve, window):
        started = time.perf_counter()
        try:
            return curve_certificate(curve, window)
        except ValueError:
            return None
        finally:
            self.counts['certificate_seconds'] += time.perf_counter()-started

    def _base(self, space):
        if 'certificate' not in space.cache:
            cert = self._certificate(space.curve, self.window)
            self.counts['base_certificates' if cert else 'base_certificate_failures'] += 1
            space.cache['certificate'] = cert
        return space.cache['certificate']

    _cheap = checks.certificate_cheap

    _full = checks.certificate_full

    certify = checks.certificate_certify

    _check_sampled_first = checks.certificate_check_sampled_first

    check = checks.certificate_check

    def _sampled(self, test):
        started = time.perf_counter()
        try:
            test()
        finally:
            self.counts['sampled_seconds'] += time.perf_counter()-started

    # ------------------------------------------------------------------ trial map

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

    def _moved(self, space, a, count, role):
        """``spectral_project(validate=True)`` with its sampled test replaced by ``check``."""
        self.counts['geometry_projections'] += 1
        curve = space.curve
        nodes, basis, base, normal = self._base_grid(space, count, len(a))
        h = basis@a/self.length_unit_m
        moved = FourierCurve.from_samples(base+h*normal, count//2-1)
        n = moved.nodes(count)

        def sampled():
            checks.require_sampled_moved_curve(n)

        self.check(space, moved.coefficients, role, sampled)
        started = time.perf_counter()
        try:
            return arclength_quadrature(moved, n, space.curve_modes)
        finally:
            self.counts['projection_seconds'] += time.perf_counter()-started

    def trial(self, space, coefficients):
        """``ProjectedUpdate.trial`` with the same order of checks and the same candidate."""
        started = time.perf_counter()
        self.counts['trial_constructions'] += 1
        self.records = []  # zero steps must not inherit the preceding trial's validity evidence
        a_used = self._checked(space, coefficients)
        try:
            if not np.any(a_used):
                return space.curve, dict(projection_error=0., projection_relative=0.,
                    maximum_normal_m=0., rms_normal_m=0., refits=2, speed_ratio=speed_ratio(space.curve),
                    intentional_projection_mm=0., finite_path=self.name)
            coarse, smoothing = self._moved(space, a_used, space.count, 'moved_coarse')
            fine, _ = self._moved(space, a_used, 2*space.count, 'moved_fine')
            c_trial = space.curve.coefficients+coarse-space.base_projection
            c_refined = space.curve.coefficients+fine-space.fine_base_projection
            error = float(np.max(np.abs(values(c_trial-c_refined, 2*space.count))))
            radius = self._base_grid(space, space.count, len(a_used))[0].perimeter/(2*np.pi)
            checks.require_projection_agreement(error, radius, self.projection_tolerance)
            candidate = FourierCurve(c_trial)
            self.check(space, c_trial, 'candidate', lambda: candidate.validate())
            tiers = {r['role']: r['tier'] for r in self.records}
            return candidate, dict(projection_error=error, projection_relative=error/radius,
                **self.measure(space, a_used), speed_ratio=speed_ratio(candidate), refits=2,
                intentional_projection_mm=smoothing*self.length_unit_m*1e3, finite_path=self.name,
                validity_tiers=tiers)
        except UpdateRefused:
            self.counts['refused_trials'] += 1
            raise
        except ValueError as exc:
            self.counts['refused_trials'] += 1
            raise _refusal(exc) from exc
        finally:
            self.counts['trial_seconds'] += time.perf_counter()-started


def control_step(proposed, space, update, config):
    """Apply the configured step control to an LM proposal (before halving)."""
    if config.step_control == "coefficient":
        bound = config.bounds(space.orders)
        return np.clip(proposed, -bound, bound)
    if config.step_control == "physical":
        size = update.measure(space, proposed)["maximum_normal_m"]
        return proposed * min(1.0, config.physical_step_bound_m / size) if size > 0 else proposed
    raise ValueError(f"Unknown step control {config.step_control!r}.")
