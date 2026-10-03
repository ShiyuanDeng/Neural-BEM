"""NU-005 validity without samples: certificate tiers in front of the sampled test.

NU-004-MS (modal Müller + the NU-003 spectral increment map) still decides validity with
the sampled test inherited from CI-001: ``spectral_project(validate=True)`` on the moved
curve at the coarse and fine grids, then ``FourierCurve.validate`` on the candidate. Each
samples the curve, checks area and minimum speed, and runs a polygon self-intersection
search. NU-005 keeps the trial map and its order of checks unchanged and puts three tiers
in front of each of the three tests (compass proposal section 5, iteration 08):

  1. exact signed area pi sum j|x_j|^2 (O(K)); area <= 0 refuses, as the sampled test does;
  2. Lemmas 3-4 against the accepted curve's |W|^2 reciprocal Y (O(K) per curve):
       rho_c + (2 nu(z) nu(D) + nu(D)^2) ||Y||_1 < 1,  D = x - z;
  3. the full |W|^2 certificate of x itself (``n_update.curve_certificate``). A moved curve
     has band count/2-1, so its crop x_B = P_B x (B = max(K, 64)) is certified and the tail
     x - x_B is absorbed by Lemma 3 against x_B's own certificate; window 64, then 128;
  4. otherwise the unchanged sampled test (fallback).

Tiers 2-3 only ACCEPT. A tier accepts only when its bound gives |W_x|^2 >= lambda > 0 on the
torus (x simple and regular) with lambda >= 1e-12 sum j^2|x_j|^2, which by Parseval implies
the sampled test's speed condition min|x'| >= 1e-6 mean|x'|. Anything inconclusive falls
through to the sampled test, so refusals and their reasons are unchanged. The candidate
curves are computed exactly as in NU-004-MS; only the validity path differs.

Campaigns and diagnostics remain under experiments.cleaned_interface.
"""
from dataclasses import dataclass, field
import time
import numpy as np
from .continuation.geometry import FourierCurve, normal_basis
from .continuation.updates import UpdateRefused, _refusal, speed_ratio
from .continuation.validation import self_intersections
from .geometry import ProjectedSpace, values
from .n_update import curve_certificate, derivative_norm, signed_area
from .spectral import SpectralProjectedUpdate, arclength_quadrature


WINDOW = 64             # NU-001's certificate window (iteration 08); also the minimum crop band


FULL_WINDOWS = (64, 128)  # tier 3 escalates once when the window-64 reciprocal is not decisive


SPEED_FACTOR = 1e-6     # the sampled test's min speed / mean speed


ROLES = ('moved_coarse', 'moved_fine', 'candidate')


TIERS = ('area_refused', 'increment', 'full', 'sampled_accepted', 'sampled_refused')


VALIDITY = ('exact area -> Lemma 3-4 increment vs accepted-curve Y -> full |W|^2 certificate '
            '(crop + Lemma 3 tail) -> sampled test (unchanged fallback)')


def pad(coefficients, band):
    old = len(coefficients)//2
    if old >= band:
        return coefficients[old-band:old+band+1]
    return np.pad(coefficients, (band-old,)*2)


def regularity_floor(x):
    """lambda needed so |x'|^2 >= lambda implies min|x'| >= 1e-6 mean|x'| (mean|x'| <= sqrt(sum j^2|x_j|^2))."""
    modes = np.arange(-(len(x)//2), len(x)//2+1)
    return SPEED_FACTOR**2*float(np.sum(modes**2*np.abs(x)**2))


def increment_bound(certificate, change):
    """Lemma 3 with Lemma 4: (bound, lambda); bound < 1 certifies |W_new|^2 >= lambda on the torus."""
    nu_d = float(derivative_norm(change))
    bound = certificate['rho']+certificate['allowance']+(2*certificate['nu']*nu_d+nu_d**2)*certificate['reciprocal_l1']
    return bound, (1-bound)/certificate['reciprocal_l1'], nu_d


@dataclass(frozen=True)
class CertifiedSpace(ProjectedSpace):
    cache: dict = field(default_factory=dict, compare=False)   # lazy accepted-curve certificate


class CertifiedSpectralUpdate(SpectralProjectedUpdate):
    """NU-003 trial map; validity by certificate tiers with the sampled test as fallback."""

    def __init__(self, length_unit_m, *, window=WINDOW, shadow=False, **kwargs):
        super().__init__(length_unit_m, **kwargs)
        self.window, self.shadow = int(window), bool(shadow)
        self.counts.update({f'{r}_{t}': 0 for r in ROLES for t in TIERS})
        self.counts.update(base_certificates=0, base_certificate_failures=0, full_certificate_failures=0,
                           certificate_seconds=0., sampled_seconds=0., shadow_disagreements=0)
        self.records = []   # per-curve tier rows of the latest trial

    def settings(self):
        return dict(super().settings(), validity=VALIDITY, certificate_window=self.window,
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

    def certify(self, space, x):
        """Tiers 1-3 for coefficients ``x`` (any band): ('refused'|'increment'|'full'|None, record)."""
        area = signed_area(x)
        row = dict(band=len(x)//2, signed_area=area)
        if not area > 0:
            return 'refused', row
        floor = regularity_floor(x)
        base = self._base(space)
        if base is not None:
            K = max(len(x)//2, space.curve.band)
            bound, lower, nu_d = increment_bound(base, pad(x, K)-pad(space.curve.coefficients, K))
            row.update(increment_bound=bound, increment_lower=lower, increment_nu=nu_d)
            if bound < 1 and lower >= floor:
                return 'increment', row
        crop = min(len(x)//2, max(space.curve.band, WINDOW))
        cropped = FourierCurve(pad(x, crop))
        tail = pad(x, len(x)//2)-pad(cropped.coefficients, len(x)//2)
        for window in FULL_WINDOWS:
            own = self._certificate(cropped, window)
            if own is None:
                self.counts['full_certificate_failures'] += 1
                row.setdefault('full_failed_windows', []).append(window)
                continue
            bound, lower, nu_t = increment_bound(own, tail)
            row.update(full_window=window, full_bound=bound, full_lower=lower, tail_nu=nu_t, full_rho=own['rho'],
                       full_reciprocal_l1=own['reciprocal_l1'], full_log_degree=own['log_degree'])
            if bound < 1 and lower >= floor:
                return 'full', row
        return None, row

    def check(self, space, x, role, sampled):
        """Tiered decision for one curve; ``sampled`` runs the unchanged test (raises on refusal)."""
        tier, row = self.certify(space, x)
        if tier == 'refused':
            self.counts[f'{role}_area_refused'] += 1
            self.records.append(dict(row, role=role, tier='area_refused'))
            raise UpdateRefused('irregular_parameterization', f'exact signed area {row["signed_area"]:g} <= 0')
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
            self.counts[f'{role}_sampled_refused'] += 1
            self.records.append(dict(row, role=role, tier='sampled_refused'))
            raise
        self.counts[f'{role}_sampled_accepted'] += 1
        self.records.append(dict(row, role=role, tier='sampled_accepted'))

    def _sampled(self, test):
        started = time.perf_counter()
        try:
            test()
        finally:
            self.counts['sampled_seconds'] += time.perf_counter()-started

    # ------------------------------------------------------------------ trial map

    def _moved(self, space, a, count, role):
        """``spectral_project(validate=True)`` with its sampled test replaced by ``check``."""
        self.counts['geometry_projections'] += 1
        curve = space.curve
        nodes = curve.nodes(count)
        h = normal_basis(nodes, len(a)//2)@a/self.length_unit_m
        normal = nodes.normals@np.array([1, 1j])
        moved = FourierCurve.from_samples(curve.values(count)+h*normal, count//2-1)
        n = moved.nodes(count)

        def sampled():
            if n.signed_area <= 0 or np.min(n.speeds) < 1e-6*np.mean(n.speeds):
                raise UpdateRefused('irregular_parameterization', 'Invalid displaced curve.')
            if self_intersections(n.points):
                raise UpdateRefused('self_intersection', 'Displaced curve self-intersects.')

        self.check(space, moved.coefficients, role, sampled)
        return arclength_quadrature(moved, n, space.curve_modes)

    def trial(self, space, coefficients):
        """``ProjectedUpdate.trial`` with the same order of checks and the same candidate."""
        started = time.perf_counter()
        self.counts['trial_constructions'] += 1
        self.records = []  # zero steps must not inherit the preceding trial's validity evidence
        a = self._checked(space, coefficients)
        try:
            if not np.any(a):
                return space.curve, dict(projection_error=0., projection_relative=0.,
                    maximum_normal_m=0., rms_normal_m=0., refits=2, speed_ratio=speed_ratio(space.curve),
                    intentional_projection_mm=0., finite_path=self.name)
            coarse, smoothing = self._moved(space, a, space.count, 'moved_coarse')
            fine, _ = self._moved(space, a, 2*space.count, 'moved_fine')
            c = space.curve.coefficients+coarse-space.base_projection
            f = space.curve.coefficients+fine-space.fine_base_projection
            error = float(np.max(np.abs(values(c-f, 2*space.count))))
            radius = space.curve.nodes(space.count).perimeter/(2*np.pi)
            if error/radius > self.projection_tolerance:
                raise UpdateRefused('unresolved_projection', f'geometry grid refinement {error/radius:g}')
            candidate = FourierCurve(c)
            self.check(space, c, 'candidate', lambda: candidate.validate())
            tiers = {r['role']: r['tier'] for r in self.records}
            return candidate, dict(projection_error=error, projection_relative=error/radius,
                **self.measure(space, a), speed_ratio=speed_ratio(candidate), refits=2,
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
