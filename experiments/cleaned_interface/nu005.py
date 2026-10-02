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

    python -m experiments.cleaned_interface.nu005 precheck --output DIR
    python -m experiments.cleaned_interface.nu005 prepare --output CAMPAIGN
    python -m experiments.cleaned_interface.nu005 run --output CAMPAIGN --cases ...
    python -m experiments.cleaned_interface.nu005 drift --output DIR
"""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import time

import numpy as np

from experiments.shape_continuation.geometry import FourierCurve, grid_size, normal_basis
from experiments.shape_continuation.updates import UpdateRefused, _refusal, speed_ratio
from experiments.shape_continuation.validation import self_intersections
from . import benchmark as b
from . import runner
from .geometry import ProjectedSpace, values
from .io import read, write, curve_from, portable
from .modal_muller import register
from .n_update import curve_certificate, derivative_norm, signed_area
from .n_update_audit import ArmPolicy, CORE, case_drift
from .nu003 import BASE, CONSTRUCTION, SpectralProjectedUpdate, arclength_quadrature, decide, identity
from .physics import Execution
from .policy import CumulativePolicy

ROOT = b.ROOT
SOLVER = 'modal_muller'
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
                    regularity='certified |W|^2 >= 1e-12 sum j^2|x_j|^2', shadow=self.shadow)

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
        a = self._checked(space, coefficients)
        try:
            if not np.any(a):
                return space.curve, dict(projection_error=0., projection_relative=0.,
                    maximum_normal_m=0., rms_normal_m=0., refits=2, speed_ratio=speed_ratio(space.curve),
                    intentional_projection_mm=0., finite_path=self.name)
            self.records = []
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


# --------------------------------------------------------------------------- pre-check

def precheck_state(curve, update_modes, length_unit_m=.05, sizes_m=(1e-7, 1e-3, 6e-3, 1.8e-2), directions=3,
                   seed=5):
    """Random trials at one accepted state; the sampled test runs in shadow on every certified curve."""
    K, M = curve.band, update_modes
    reference, update = SpectralProjectedUpdate(length_unit_m), CertifiedSpectralUpdate(length_unit_m, shadow=True)
    s_ref, s_cert = reference.prepare(curve, M, K), update.prepare(curve, M, K)
    rng = np.random.default_rng(seed)
    trials = []
    for size in sizes_m:
        for _ in range(directions):
            a = rng.normal(size=len(s_ref.orders))
            a *= size/max(reference.measure(s_ref, a)['maximum_normal_m'], 1e-300)
            outcome = {}
            for name, u, s in (('sampled', reference, s_ref), ('tiered', update, s_cert)):
                t0 = time.perf_counter()
                try:
                    shape, _ = u.trial(s, a)
                    outcome[name] = dict(status='accepted', coefficients=shape.coefficients)
                except (UpdateRefused, ValueError) as exc:
                    outcome[name] = dict(status='refused', reason=getattr(exc, 'reason', str(exc)))
                outcome[name]['seconds'] = time.perf_counter()-t0
            same = outcome['sampled']['status'] == outcome['tiered']['status'] and (
                outcome['sampled']['status'] == 'refused' and outcome['sampled']['reason'] == outcome['tiered']['reason']
                or outcome['sampled']['status'] == 'accepted' and
                np.array_equal(outcome['sampled']['coefficients'], outcome['tiered']['coefficients']))
            trials.append(dict(size_m=size, same_decision=bool(same),
                               sampled=outcome['sampled']['status'], tiered=outcome['tiered']['status'],
                               reason=outcome['tiered'].get('reason'),
                               seconds=dict(sampled=outcome['sampled']['seconds'], tiered=outcome['tiered']['seconds']),
                               curves=list(update.records)))
    return dict(K=K, M=M, trials=trials, base_certificate=update._base(s_cert) is not None)


def precheck(output, source=BASE/'NU-004-MS/runs', **kwargs):
    rows = []
    for case in CORE:
        last = {}
        for state in read(Path(source)/case/'accepted.json')['states']:
            last[state['stage']] = state
        for stage, state in last.items():
            row = dict(case=case, stage=stage, **precheck_state(curve_from(state['curve']), state['M'], **kwargs))
            rows.append(row)
            tiers = [c['tier'] for t in row['trials'] for c in t['curves']]
            print(case, stage, 'K', row['K'], 'M', row['M'],
                  {t: tiers.count(t) for t in sorted(set(tiers))},
                  'same', sum(t['same_decision'] for t in row['trials']), '/', len(row['trials']), flush=True)
    trials = [t for r in rows for t in r['trials']]
    curves = [c for t in trials for c in t['curves']]
    by = {f'{role}:{tier}': sum(c['role'] == role and c['tier'] == tier for c in curves)
          for role in ROLES for tier in TIERS}
    by_size = {str(s): {tier: sum(c['tier'] == tier for t in trials if t['size_m'] == s for c in t['curves'])
                        for tier in TIERS} for s in sorted({t['size_m'] for t in trials})}
    certified = [c for c in curves if c['tier'] in ('increment', 'full')]
    gates = dict(
        same_decisions=all(t['same_decision'] for t in trials),
        no_shadow_disagreement=all(c.get('shadow') == 'accepted' for c in certified))
    result = dict(experiment='NU-005 pre-check', source=str(Path(source).relative_to(ROOT)), states=len(rows),
                  trials=len(trials), curves=len(curves), tiers=by, tiers_by_size=by_size,
                  fallback_fraction=sum(c['tier'].startswith('sampled') for c in curves)/max(len(curves), 1),
                  seconds=dict(sampled=float(sum(t['seconds']['sampled'] for t in trials)),
                               tiered=float(sum(t['seconds']['tiered'] for t in trials))),
                  gates=gates, passed=all(gates.values()), rows=rows)
    write(Path(output)/'precheck.json', result)
    return {k: v for k, v in result.items() if k != 'rows'}


# --------------------------------------------------------------------------- campaign

@contextmanager
def substitution():
    saved = runner.ProjectedUpdate, runner.CumulativePolicy
    runner.ProjectedUpdate = CertifiedSpectralUpdate
    runner.CumulativePolicy = lambda: ArmPolicy(geometry_update=CONSTRUCTION)
    try:
        yield
    finally:
        runner.ProjectedUpdate, runner.CumulativePolicy = saved


def prepare(output):
    output = Path(output)
    value = b.prepare(output)
    b.augment(output, None, allow_new_damped_data=True, reuse_from=BASE/'CI-001')
    write(output/'arm.json', dict(experiment='NU-005', arm='MC', solver=SOLVER, update='CertifiedSpectralUpdate',
        construction=CONSTRUCTION, validity=VALIDITY, update_settings=CertifiedSpectralUpdate(.05).settings(),
        cases=list(CORE),
        policy_changes=dict(fit_seconds=[CumulativePolicy.fit_seconds, ArmPolicy.fit_seconds],
                            audit_seconds=[CumulativePolicy.audit_seconds, ArmPolicy.audit_seconds],
                            reason='identical to the NU-001, NU-003 and NU-004 arms; unit caps unchanged')))
    return value


def run(output, execution, cases):
    register()
    with substitution():
        return b.run(output, execution, solver=SOLVER, workers=1, cases=cases)


def report(output):
    register()
    return b.report(output)


def tier_counts(folder):
    work = read(Path(folder)/'result.json')['geometry_work']
    counts = {f'{r}:{t}': work.get(f'{r}_{t}', 0) for r in ROLES for t in TIERS}
    curves = sum(counts.values())
    fallback = sum(v for k, v in counts.items() if ':sampled' in k)
    return dict(counts=counts, curves=curves, fallback=fallback,
                certified=sum(v for k, v in counts.items() if k.endswith(('increment', 'full'))),
                trials=work['trial_constructions'], refused_trials=work['refused_trials'],
                certificate_seconds=work.get('certificate_seconds'), sampled_seconds=work.get('sampled_seconds'),
                base_certificate_failures=work.get('base_certificate_failures'),
                full_certificate_failures=work.get('full_certificate_failures'),
                preparation_seconds=work['preparation_seconds'], trial_seconds=work['trial_seconds'])


def drift(output, nodal=BASE/'CI-001', ms=BASE/'NU-004-MS', mc=BASE/'NU-005', certificate=True):
    out = dict(experiment='NU-005 drift, decision and tier audit', arms={})
    for name, campaign in (('nodal', Path(nodal)), ('MS', Path(ms)), ('MC', Path(mc))):
        comparison = read(campaign/'comparison.json') if (campaign/'comparison.json').exists() else dict(rows=[])
        status = {r['id']: r['status'] for r in comparison['rows'] if r['id'] in CORE}
        cases = {}
        for case in CORE:
            folder = campaign/'runs'/case
            if (folder/'result.json').exists():
                cases[case] = case_drift(folder, certificate)
                if name == 'MC':
                    cases[case]['identity_vs_MS'] = identity(Path(ms)/'runs'/case, folder)
                    cases[case]['identity_vs_nodal'] = identity(Path(nodal)/'runs'/case, folder)
                    cases[case]['validity'] = tier_counts(folder)
                print(name, case, 'max r', round(cases[case]['max_speed_ratio'], 4), cases[case]['outcome'], flush=True)
        out['arms'][name] = dict(campaign=str(campaign.resolve().relative_to(ROOT)), status=status, cases=cases)
    if len(out['arms']['MC']['cases']) == len(CORE) and len(out['arms']['nodal']['cases']) == len(CORE):
        rule = decide(out['arms']['nodal'], out['arms']['MC'])
        rule.pop('outcome')
        mc = out['arms']['MC']['cases']
        units = {c: [read(Path(a)/'runs'/c/'result.json')['total_units'] for a in (ms, mc)] for c in CORE}
        identical = all(mc[c]['identity_vs_MS']['same_accepted_steps'] and units[c][0] == units[c][1] for c in CORE)
        fallback = sum(mc[c]['validity']['fallback'] for c in CORE)
        curves = sum(mc[c]['validity']['curves'] for c in CORE)
        retained = rule['qualifies'] and identical
        out['decision'] = dict(rule, decision_identical_to_MS=identical, units=units,
                               fallback=fallback, curves=curves, fallback_fraction=fallback/max(curves, 1),
                               retained=retained,
                               outcome=('not retained: the tiers changed a decision' if not retained else
                                        'validity decided without samples on the six core cases' if fallback == 0 else
                                        f'retained; the sampled fallback decided {fallback} of {curves} curves'))
    write(Path(output)/'drift.json', out)
    return out.get('decision', 'incomplete')


def main(argv=None):
    parser = argparse.ArgumentParser(description='NU-005 validity without samples')
    parser.add_argument('command', choices=('precheck', 'prepare', 'run', 'report', 'drift'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', default=list(CORE))
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--frequency-threads', type=int, default=4)
    args = parser.parse_args(argv)
    if args.command == 'precheck':
        value = precheck(args.output)
    elif args.command == 'prepare':
        value = prepare(args.output)
    elif args.command == 'run':
        value = run(args.output, Execution(args.device, args.frequency_threads), args.cases)
    elif args.command == 'report':
        value = report(args.output)
    else:
        value = drift(args.output)
    print(json.dumps(portable(value), indent=2))


if __name__ == '__main__':
    main(sys.argv[1:])
