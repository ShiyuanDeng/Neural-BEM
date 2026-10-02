"""NU-007: the NU-006 update with its |W|^2 certificates evaluated on the GPU.

NU-005's tiers call ``n_update.curve_certificate`` (``modal_geometry.log_modulus`` on
scipy FFTs) for the accepted curve of each prepared space and for every trial curve that
reaches tier 3. In NU-006 these took 104 s of 242 s wall time. ``device_certificate``
is the same construction in torch float64:

  W divided-difference coefficients -> |W|^2 = Re(W conj W) by FFT convolution;
  Lambda = ||ww||_1; beta = half the sampled minimum on the same FFT grid size;
  Chebyshev degree from the same scalar bound; the windowed multiplier with the
  polynomial cropped to 2B and linear-convolution padding; the reciprocal series;
  the untruncated residual ||1 - |W|^2 Y||_1 and the same rounding allowance
  80 size eps Lambda ||Y||_1.

It refuses (ValueError) under the same conditions: sampled minimum <= 0, degree above
``max_degree`` (including after the one recomputation), or lower bound <= 0. The
log|W|^2 series itself is not formed, because no tier uses it; the recomputed interval
only reports its degree. Everything else is NU-006 unchanged.

    python -m experiments.cleaned_interface.nu007 precheck --output DIR
    python -m experiments.cleaned_interface.nu007 prepare --output CAMPAIGN
    python -m experiments.cleaned_interface.nu007 run --output CAMPAIGN --cases ...
    python -m experiments.cleaned_interface.nu007 drift --output DIR
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.fft import next_fast_len
import torch

from experiments.shape_continuation.updates import UpdateRefused
from . import benchmark as b
from . import runner
from .io import read, write, curve_from, portable
from .modal_muller import register
from .n_update import curve_certificate, derivative_norm
from .n_update_audit import ArmPolicy, CORE, case_drift
from .nu003 import BASE, CONSTRUCTION, decide, identity
from .nu005 import ROOT, SOLVER, tier_counts
from .nu006 import BatchedCertifiedUpdate
from .physics import Execution
from .policy import CumulativePolicy

EPS = np.finfo(float).eps


def _convolve(first, second):
    shape = (first.shape[0]+second.shape[0]-1,)*2
    return torch.fft.ifft2(torch.fft.fft2(first, shape)*torch.fft.fft2(second, shape))


def _degree(upper, beta, tolerance, max_degree):
    root_upper, root_lower = np.sqrt(upper), np.sqrt(beta)
    ratio = (root_upper-root_lower)/(root_upper+root_lower)
    degree = 1
    while 2*ratio**(degree+1)/((degree+1)*(1-ratio)) > tolerance:
        degree += 1
        if degree > max_degree:
            raise ValueError(f'log|W|^2 needs more than {max_degree} Chebyshev terms '
                             f'(beta/Lambda={beta/upper:.3g}); curve is nearly self-touching.')
    return degree, ratio


def device_certificate(curve, window, device, *, tolerance=1e-12, max_degree=4000):
    """``n_update.curve_certificate`` in torch float64 on ``device``; same keys and refusals."""
    started = time.perf_counter()
    z, k = curve.coefficients, curve.band
    quotient = np.zeros((2*k+1, 2*k+1), complex)
    for j in range(1, k+1):
        r = np.arange(j)
        quotient[k+j-1-r, k+r] += z[k+j]
        quotient[k-1-r, k-j+r] -= z[k-j]
    quotient = torch.as_tensor(quotient, device=device)
    product = _convolve(quotient, quotient.flip(0, 1).conj())
    ww = (product+product.flip(0, 1).conj())/2
    upper = float(ww.abs().sum())
    half = (ww.shape[0]-1)//2
    grid = max(64, next_fast_len(4*half+4))
    spectrum = torch.zeros((grid, grid), dtype=torch.complex128, device=device)
    index = torch.arange(-half, half+1, device=device) % grid
    spectrum[index[:, None], index[None, :]] = ww
    sampled = float(torch.fft.ifft2(spectrum).real.min())*grid*grid
    if not sampled > 0:
        raise ValueError(f'Curve is not simple and regular: sampled min |W|^2 = {sampled:g}.')
    beta = sampled/2
    degree, ratio = _degree(upper, beta, tolerance, max_degree)
    mapped = 2*ww/(upper-beta)
    mapped[half, half] -= (upper+beta)/(upper-beta)
    crop = min(half, 2*window)
    poly = mapped[half-crop:half+crop+1, half-crop:half+crop+1]
    size = 2*window+1
    shape = (size+poly.shape[0]-1,)*2
    transform = torch.fft.fft2(poly, shape)

    def multiply(array):
        return torch.fft.ifft2(torch.fft.fft2(array, shape)*transform)[crop:crop+size, crop:crop+size]

    previous = torch.zeros((size, size), dtype=torch.complex128, device=device)
    previous[window, window] = 1
    current = multiply(previous)
    scale = 1/np.sqrt(upper*beta)
    inverse = scale*(previous-2*ratio*current)
    for n in range(2, degree+1):
        previous, current = current, 2*multiply(current)-previous
        inverse = inverse+(2*scale*(-ratio)**n)*current
    product = _convolve(ww, inverse)
    centre = (product.shape[0]-1)//2
    product[centre, centre] -= 1
    residual = float(product.abs().sum())
    norm = float(inverse.abs().sum())
    allowance = 80*product.numel()*EPS*upper*norm
    lower = (1-residual-allowance)/norm
    recomputed = False
    if lower < beta:
        if not lower > 0:
            raise ValueError(f'|W|^2 lower bound not certified (coefficient residual {residual:.3g}).')
        beta, recomputed = lower, True
        degree, _ = _degree(upper, beta, tolerance, max_degree)
    return dict(window=window, rho=residual, allowance=allowance, reciprocal_l1=norm, beta=beta, Lambda=upper,
                log_degree=degree, recomputed=recomputed, nu=float(derivative_norm(z)),
                seconds=time.perf_counter()-started)


class DeviceCertifiedUpdate(BatchedCertifiedUpdate):
    """NU-006 update; tier-2 and tier-3 certificates on the update's device."""

    def __init__(self, length_unit_m, **kwargs):
        super().__init__(length_unit_m, **kwargs)
        self.counts.update(device_certificate_fallbacks=0)

    def settings(self):
        return dict(super().settings(), certificate='torch float64 port of curve_certificate (NU-007)',
                    certificate_device=self.device)

    def _certificate(self, curve, window):
        started = time.perf_counter()
        try:
            return device_certificate(curve, window, self.device)
        except ValueError:
            return None
        except torch.OutOfMemoryError:
            torch.cuda.empty_cache()
            self.counts['device_certificate_fallbacks'] += 1
            try:
                return curve_certificate(curve, window)
            except ValueError:
                return None
        finally:
            self.counts['certificate_seconds'] += time.perf_counter()-started


# --------------------------------------------------------------------------- pre-check

def precheck_state(curve, update_modes, length_unit_m=.05, sizes_m=(1e-7, 1e-3, 6e-3, 1.8e-2), directions=3,
                   seed=5):
    """NU-005's random trials; every curve's tiers with CPU certificates and with device certificates."""
    K, M = curve.band, update_modes
    host, device = BatchedCertifiedUpdate(length_unit_m), DeviceCertifiedUpdate(length_unit_m)
    s_host, s_dev = host.prepare(curve, M, K), device.prepare(curve, M, K)
    rng = np.random.default_rng(seed)
    trials = []
    for size in sizes_m:
        for _ in range(directions):
            a = rng.normal(size=len(s_host.orders))
            a *= size/max(host.measure(s_host, a)['maximum_normal_m'], 1e-300)
            outcome = {}
            for name, u, s in (('host', host, s_host), ('device', device, s_dev)):
                before = u.counts['certificate_seconds']
                try:
                    shape, _ = u.trial(s, a)
                    outcome[name] = dict(status='accepted', coefficients=shape.coefficients)
                except (UpdateRefused, ValueError) as exc:
                    outcome[name] = dict(status='refused', reason=getattr(exc, 'reason', str(exc)))
                outcome[name].update(certificate_seconds=u.counts['certificate_seconds']-before,
                                     curves=list(u.records))
            h, d = outcome['host'], outcome['device']
            same = h['status'] == d['status'] and (h.get('reason') == d.get('reason') if h['status'] == 'refused'
                                                   else np.array_equal(h['coefficients'], d['coefficients']))
            tiers = [c['tier'] for c in h['curves']] == [c['tier'] for c in d['curves']]
            gaps = [abs(x[key]-y[key])/max(abs(x[key]), 1e-300) for x, y in zip(h['curves'], d['curves'])
                    for key in ('increment_bound', 'full_bound') if key in x and key in y]
            trials.append(dict(size_m=size, same_decision=bool(same), same_tiers=bool(tiers),
                               bound_relative=max(gaps, default=0.), tiers=[c['tier'] for c in d['curves']],
                               seconds=dict(host=h['certificate_seconds'], device=d['certificate_seconds'])))
    return dict(K=K, M=M, trials=trials)


def precheck(output, source=BASE/'NU-006/runs', **kwargs):
    rows = []
    for case in CORE:
        last = {}
        for state in read(Path(source)/case/'accepted.json')['states']:
            last[state['stage']] = state
        for stage, state in last.items():
            row = dict(case=case, stage=stage, **precheck_state(curve_from(state['curve']), state['M'], **kwargs))
            rows.append(row)
            t = row['trials']
            print(case, stage, 'K', row['K'], 'M', row['M'], 'same', sum(x['same_decision'] for x in t),
                  'tiers', sum(x['same_tiers'] for x in t), '/', len(t),
                  'bound %.1e' % max(x['bound_relative'] for x in t),
                  'cert s %.2f / %.2f' % (sum(x['seconds']['host'] for x in t), sum(x['seconds']['device'] for x in t)),
                  flush=True)
    trials = [t for r in rows for t in r['trials']]
    gates = dict(same_decisions=all(t['same_decision'] for t in trials),
                 same_tiers=all(t['same_tiers'] for t in trials),
                 bounds_at_roundoff=max(t['bound_relative'] for t in trials) <= 1e-9)
    result = dict(experiment='NU-007 pre-check', source=str(Path(source).relative_to(ROOT)), states=len(rows),
                  trials=len(trials), worst_bound_relative=max(t['bound_relative'] for t in trials),
                  certificate_seconds=dict(host=float(sum(t['seconds']['host'] for t in trials)),
                                           device=float(sum(t['seconds']['device'] for t in trials))),
                  gates=gates, passed=all(gates.values()), rows=rows)
    write(Path(output)/'precheck.json', result)
    return {k: v for k, v in result.items() if k != 'rows'}


# --------------------------------------------------------------------------- campaign

@contextmanager
def substitution():
    saved = runner.ProjectedUpdate, runner.CumulativePolicy
    runner.ProjectedUpdate = DeviceCertifiedUpdate
    runner.CumulativePolicy = lambda: ArmPolicy(geometry_update=CONSTRUCTION)
    try:
        yield
    finally:
        runner.ProjectedUpdate, runner.CumulativePolicy = saved


def prepare(output):
    output = Path(output)
    value = b.prepare(output)
    b.augment(output, None, allow_new_damped_data=True, reuse_from=BASE/'CI-001')
    write(output/'arm.json', dict(experiment='NU-007', arm='MD', solver=SOLVER, update='DeviceCertifiedUpdate',
        construction=CONSTRUCTION, update_settings=DeviceCertifiedUpdate(.05).settings(), cases=list(CORE),
        policy_changes=dict(fit_seconds=[CumulativePolicy.fit_seconds, ArmPolicy.fit_seconds],
                            audit_seconds=[CumulativePolicy.audit_seconds, ArmPolicy.audit_seconds],
                            reason='identical to the NU-001 to NU-006 arms; unit caps unchanged')))
    return value


def run(output, execution, cases):
    register()
    with substitution():
        return b.run(output, execution, solver=SOLVER, workers=1, cases=cases)


def report(output):
    register()
    return b.report(output)


def drift(output, nodal=BASE/'CI-001', reference=BASE/'NU-006', arm=BASE/'NU-007', certificate=True):
    out = dict(experiment='NU-007 drift, decision and identity audit', arms={})
    for name, campaign in (('nodal', Path(nodal)), ('MG', Path(reference)), ('MD', Path(arm))):
        comparison = read(campaign/'comparison.json') if (campaign/'comparison.json').exists() else dict(rows=[])
        status = {r['id']: r['status'] for r in comparison['rows'] if r['id'] in CORE}
        cases = {}
        for case in CORE:
            folder = campaign/'runs'/case
            if (folder/'result.json').exists():
                cases[case] = case_drift(folder, certificate)
                if name != 'nodal':
                    cases[case]['validity'] = tier_counts(folder)
                if name == 'MD':
                    cases[case]['identity_vs_MG'] = identity(Path(reference)/'runs'/case, folder)
                    cases[case]['identity_vs_nodal'] = identity(Path(nodal)/'runs'/case, folder)
                print(name, case, 'max r', round(cases[case]['max_speed_ratio'], 4), cases[case]['outcome'], flush=True)
        out['arms'][name] = dict(campaign=str(campaign.resolve().relative_to(ROOT)), status=status, cases=cases)
    if all(len(out['arms'][a]['cases']) == len(CORE) for a in ('nodal', 'MG', 'MD')):
        rule = decide(out['arms']['nodal'], out['arms']['MD'])
        rule.pop('outcome')
        table, ref = out['arms']['MD']['cases'], out['arms']['MG']['cases']
        result = {name: {c: read(Path(a)/'runs'/c/'result.json') for c in CORE} for name, a in (('MG', reference), ('MD', arm))}
        units = {c: [result['MG'][c]['total_units'], result['MD'][c]['total_units']] for c in CORE}
        identical = all(table[c]['identity_vs_MG']['same_accepted_steps'] and units[c][0] == units[c][1] for c in CORE)
        same_tiers = all(table[c]['validity']['counts'] == ref[c]['validity']['counts'] for c in CORE)
        seconds = {name: dict(wall=float(sum(r['total_seconds'] for r in result[name].values())),
                              certificate=float(sum(r['geometry_work']['certificate_seconds'] for r in result[name].values())))
                   for name in result}
        out['decision'] = dict(rule, decision_identical_to_MG=identical, same_tier_counts=same_tiers, units=units,
                               seconds=seconds, retained=rule['qualifies'],
                               default=rule['qualifies'] and identical and same_tiers,
                               outcome=('not retained' if not rule['qualifies'] else
                                        'retained, decision- and tier-identical: adopt device certificates'
                                        if identical and same_tiers else 'retained, not identical to NU-006'))
    write(Path(output)/'drift.json', out)
    return out.get('decision', 'incomplete')


def main(argv=None):
    parser = argparse.ArgumentParser(description='NU-007 device certificates')
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
