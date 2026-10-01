"""NU-001 N-update drift audit: control, matched three-arm campaign and drift report.

    python -m experiments.cleaned_interface.n_update_audit control --output DIR
    python -m experiments.cleaned_interface.n_update_audit prepare --arm A --output CAMPAIGN
    python -m experiments.cleaned_interface.n_update_audit run --output CAMPAIGN --cases core__kite ...
    python -m experiments.cleaned_interface.n_update_audit drift --campaigns NODAL A B --output DIR

Arms: ``nodal`` (ProjectedUpdate, the CI-001 trial map; the archived CI-001
campaign serves, see iteration 08), ``A`` (NormalUpdate)
and ``B`` (NormalUpdate with the HLS tangential term). Every arm uses the
unchanged CI-001 schedule, LM, clips and physics selection. Only the time caps
differ from CI-001 (CPU host), identically for all three arms; work-unit caps
are unchanged. No CI-001 frozen source is modified: the runner's update class
and policy are substituted for the duration of a run, and configuration.json
records the substituted update's settings.
"""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass, fields
import json
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import CubicSpline

from experiments.shape_continuation.geometry import FourierCurve, arclength_angles, grid_size
from . import benchmark as b
from . import runner
from .geometry import ProjectedUpdate, values
from .io import read, write, curve_from, portable
from .n_update import NormalUpdate, centred, curve_certificate
from .physics import Execution
from .policy import CumulativePolicy, Operation

ROOT = b.ROOT
CORE = ('core__wrong_circle', 'core__circle_to_star', 'core__circle_to_c', 'core__kite', 'core__peanut', 'core__hook')
ARMS = dict(
    nodal=dict(update='ProjectedUpdate', construction='z + P_K[A(z+h*n)-A(z)], derivative of the complete trial'),
    A=dict(update='NormalUpdate', tangential=False,
           construction='z + P_K[g_a N], g_a=h_a(theta)/sigma_0; exact affine trial and derivative'),
    B=dict(update='NormalUpdate', tangential=True,
           construction='z + P_K[g_a N + psi_a z\'], HLS eq. 11 psi; exact affine trial and derivative'))
CERTIFICATE_WINDOW = 64
FIT_SECONDS, AUDIT_SECONDS = 14400., 3600.


def make_update(arm, length_unit_m):
    if arm == 'nodal':
        return ProjectedUpdate(length_unit_m)
    return NormalUpdate(length_unit_m, tangential=ARMS[arm]['tangential'],
                        certificate_window=CERTIFICATE_WINDOW)


@dataclass(frozen=True)
class ArmOperation(Operation):
    geometry_update: str = ''

    def record(self):
        row = super().record()
        if 'geometry_update' in row:
            row['geometry_update'] = self.geometry_update
        return row


@dataclass(frozen=True)
class ArmPolicy(CumulativePolicy):
    """CI-001 v1 schedule; records the arm's update; CPU-host time caps."""
    fit_seconds: float = FIT_SECONDS
    audit_seconds: float = AUDIT_SECONDS
    geometry_update: str = ARMS['nodal']['construction']

    def _explicit_cleanup(self, operations):
        return tuple(ArmOperation(**{f.name: getattr(op, f.name) for f in fields(Operation)},
                                  geometry_update=self.geometry_update)
                     for op in super()._explicit_cleanup(operations))


@contextmanager
def arm_substitution(arm):
    """Substitute the runner's update class and policy for one arm, then restore them."""
    saved = runner.ProjectedUpdate, runner.CumulativePolicy
    runner.ProjectedUpdate = lambda unit: make_update(arm, unit)
    runner.CumulativePolicy = lambda: ArmPolicy(geometry_update=ARMS[arm]['construction'])
    try:
        yield
    finally:
        runner.ProjectedUpdate, runner.CumulativePolicy = saved


# --------------------------------------------------------------------------- control

def baseline_linearization(curve, update_modes, length_unit_m):
    """Exact first-order model of d/da ProjectedUpdate trial (centred arclength projection).

    z_a(theta) = z + a h(alpha(theta)) n(theta)/L_unit is refit in its own
    arclength t and added at coefficient index t. Its derivative is
    V(t) = F(theta(t)), F = d - z' dalpha/alpha', with d the normal move,
    dalpha the first-order change of normalized arclength and alpha'=2pi sigma/L.
    Splines evaluate the composition exactly as ``project`` does.
    """
    K = curve.band
    count = grid_size(max(K, update_modes))
    nodes = curve.nodes(count)
    theta = nodes.parameters
    alpha, length = arclength_angles(nodes)
    phase = alpha[:, None]*np.arange(1, update_modes+1)
    h = np.column_stack((np.ones(count), np.cos(phase), np.sin(phase)))
    normal = nodes.normals@np.array([1, 1j])
    tangent = 1j*normal
    speed = nodes.speeds
    modes = np.fft.fftfreq(count)*count
    move = h*normal[:, None]/length_unit_m
    dmove = np.fft.ifft(1j*modes[:, None]*np.fft.fft(move, axis=0), axis=0)
    dspeed = (np.conj(tangent)[:, None]*dmove).real          # d|z_a'|/da = Re(conj(T) d')
    mean = dspeed.mean(axis=0)
    spectrum = np.fft.fft(dspeed-mean, axis=0)
    spectrum[1:] /= 1j*modes[1:, None]
    spectrum[0] = 0
    periodic = np.fft.ifft(spectrum, axis=0).real
    dist = mean*theta[:, None]+periodic-periodic[0]          # first-order change of s(theta)
    dlength = 2*np.pi*mean
    s = alpha*length/(2*np.pi)
    dalpha = 2*np.pi*(dist/length-s[:, None]*dlength/length**2)
    derivative = nodes.speeds*tangent                       # z'(theta)
    F = move-derivative[:, None]*dalpha/(2*np.pi*speed/length)[:, None]
    inverse = CubicSpline(np.r_[alpha, 2*np.pi], np.r_[theta, 2*np.pi])
    at = inverse(theta)
    columns = []
    for q in range(F.shape[1]):
        spline = CubicSpline(np.r_[theta, 2*np.pi], np.r_[F[:, q], F[0, q]], bc_type='periodic')
        columns.append(np.fft.fft(spline(at))/count)
    spectrum = np.stack(columns, axis=1)
    return spectrum[np.arange(-K, K+1) % count]


def weights_on_grid(coefficients, curve, count):
    """Re(V conj N) at uniform parameter nodes, V given as (2K+1, dim) coefficients."""
    normal = values((curve.modes*curve.coefficients)[:, None], count)[:, 0]
    return (values(coefficients, count)*np.conj(normal)[:, None]).real


def relative_columns(a, b):
    return np.linalg.norm(a-b, axis=0)/np.maximum(np.linalg.norm(b, axis=0), 1e-300)


def control_state(curve, update_modes, length_unit_m=.05):
    K, M = curve.band, update_modes
    count = grid_size(max(K, M))
    projected = ProjectedUpdate(length_unit_m)
    space = projected.prepare(curve, M, K)
    fd = space.derivatives
    linear = baseline_linearization(curve, M, length_unit_m)
    nodes = curve.nodes(count)
    alpha, _ = arclength_angles(nodes)
    theta, speed = nodes.parameters, nodes.speeds

    def basis(angle):
        phase = angle[:, None]*np.arange(1, M+1)
        return np.column_stack((np.ones(count), np.cos(phase), np.sin(phase)))
    baseline = weights_on_grid(fd, curve, count)*length_unit_m
    candidates = dict(arclength_hybrid=basis(alpha)*speed[:, None], theta_unit_normal=basis(theta)*speed[:, None])
    rows = {}
    for arm, tangential in (('A', False), ('B', True)):
        update = NormalUpdate(length_unit_m, tangential=tangential)
        s = update.prepare(curve, M, K)
        rows[arm] = s
        candidates['n_update_'+arm] = weights_on_grid(s.derivatives, curve, count)*length_unit_m
    a, b2 = rows['A'], rows['B']
    nupd = candidates['n_update_A']
    eq3 = basis(theta)*(speed**2/a.mean_speed)[:, None]
    rng = np.random.default_rng(7)
    step = rng.normal(size=len(a.orders))*1e-7
    affine = []
    for s, update in ((a, NormalUpdate(length_unit_m)), (b2, NormalUpdate(length_unit_m, tangential=True))):
        plus = update.trial(s, step)[0].coefficients
        minus = update.trial(s, -step)[0].coefficients
        exact = s.derivatives@step
        affine.append(float(np.linalg.norm((plus-minus)/2-exact)/np.linalg.norm(exact)))
    summary = lambda e: dict(max=float(np.max(e)), median=float(np.median(e)))
    return dict(
        K=K, M=M, speed_ratio=float(speed.max()/speed.min()), mean_speed=a.mean_speed,
        baseline_fd_vs_linearization=summary(relative_columns(fd, linear)),
        baseline_weights_vs=dict({k: summary(relative_columns(v, baseline)) for k, v in candidates.items()}),
        n_update_weights_vs_eq3=summary(relative_columns(nupd, eq3)),
        arm_B_minus_A_weights=summary(relative_columns(candidates['n_update_B'], nupd)),
        n_update_affine_fd_relative=dict(A=affine[0], B=affine[1]),
        crop_tail=dict(A=float(np.max(np.sum(np.abs(a.uncropped), axis=1)-np.sum(np.abs(centred(a.uncropped, K)), axis=1))
                               / np.max(np.sum(np.abs(a.uncropped), axis=1))),
                       B=float(np.max(np.sum(np.abs(b2.uncropped), axis=1)-np.sum(np.abs(centred(b2.uncropped, K)), axis=1))
                               / np.max(np.sum(np.abs(b2.uncropped), axis=1)))),
        preparation_seconds=dict(nodal=space.preparation_seconds, A=a.preparation_seconds, B=b2.preparation_seconds))


def control(output, source=ROOT/'results/validation/cleaned_interfaces/CI-001/runs'):
    """Columns at saved nodal states (last accepted state of every stage of the six core runs)."""
    rows = []
    for case in CORE:
        states = read(Path(source)/case/'accepted.json')['states']
        last = {}
        for state in states:
            last[state['stage']] = state
        for stage, state in last.items():
            row = control_state(curve_from(state['curve']), state['M'])
            row.update(case=case, stage=stage, iteration=state['iteration'])
            rows.append(row)
            print(case, stage, 'K', row['K'], 'M', row['M'], 'r', round(row['speed_ratio'], 4),
                  'fd/lin', f"{row['baseline_fd_vs_linearization']['max']:.1e}",
                  {k: f"{v['max']:.1e}" for k, v in row['baseline_weights_vs'].items()}, flush=True)
    worst = lambda key, sub=None: max((r[key][sub] if sub else r[key])['max'] for r in rows)
    result = dict(
        experiment='NU-001 control', source=str(Path(source).relative_to(ROOT)), states=len(rows),
        baseline_fd_vs_linearization_max=worst('baseline_fd_vs_linearization'),
        baseline_weights_vs_max={k: max(r['baseline_weights_vs'][k]['max'] for r in rows)
                                 for k in rows[0]['baseline_weights_vs']},
        n_update_weights_vs_eq3_max=worst('n_update_weights_vs_eq3'),
        n_update_affine_fd_relative_max=max(max(r['n_update_affine_fd_relative'].values()) for r in rows),
        rows=rows)
    write(Path(output)/'control.json', result)
    return {k: v for k, v in result.items() if k != 'rows'}


# --------------------------------------------------------------------------- campaign

def prepare(output, arm):
    output = Path(output)
    value = b.prepare(output)
    b.augment(output, None, allow_new_damped_data=True,
              reuse_from=ROOT/'results/validation/cleaned_interfaces/CI-001')
    write(output/'arm.json', dict(experiment='NU-001', arm=arm, **ARMS[arm],
        update_settings=make_update(arm, .05).settings(), cases=list(CORE),
        policy_changes=dict(fit_seconds=[CumulativePolicy.fit_seconds, FIT_SECONDS],
                            audit_seconds=[CumulativePolicy.audit_seconds, AUDIT_SECONDS],
                            reason='CPU host without CUDA; identical in all three arms; unit caps unchanged'),
        certificate_window=None if arm == 'nodal' else CERTIFICATE_WINDOW))
    return dict(value, arm=arm)


def run(output, execution, cases):
    arm = read(Path(output)/'arm.json')['arm']
    with arm_substitution(arm):
        return b.run(output, execution, solver='nodal_kress', workers=1, cases=cases)


# --------------------------------------------------------------------------- drift report

def energy_above_half(curve):
    c, K = curve.coefficients, curve.band
    modes = np.abs(curve.modes)
    total = np.sum(np.abs(c[modes > 0])**2)
    return float(np.sum(np.abs(c[modes > K/2])**2)/total)


def case_drift(folder, certificate=True):
    folder = Path(folder)
    states = read(folder/'accepted.json')['states']
    ratios = []
    last = {}
    for state in states:
        curve = curve_from(state['curve'])
        speeds = curve.nodes(grid_size(curve.band)).speeds
        ratios.append(dict(stage=state['stage'], iteration=state['iteration'],
                           speed_ratio=float(speeds.max()/speeds.min())))
        last[state['stage']] = state
    stages = []
    for stage, state in last.items():
        curve = curve_from(state['curve'])
        row = dict(stage=stage, M=state['M'], K=curve.band, energy_above_half=energy_above_half(curve),
                   speed_ratio=max(r['speed_ratio'] for r in ratios if r['stage'] == stage))
        if certificate:
            try:
                cert = curve_certificate(curve, CERTIFICATE_WINDOW)
                row.update(beta_W=cert['beta'], Lambda_W=cert['Lambda'], Lambda_over_beta=cert['Lambda']/cert['beta'],
                           log_degree=cert['log_degree'], reciprocal_l1=cert['reciprocal_l1'], rho_c=cert['rho'])
            except ValueError as exc:
                row.update(certificate_error=str(exc))
        saved = folder/f'{stage}.json'
        if saved.exists():
            data = read(saved)
            trials = data.get('trials', [])
            reasons, tiers = {}, {}
            for t in trials:
                key = t.get('status', 'pending') if t.get('status') != 'refused' else 'refused:'+t.get('reason', '?')
                reasons[key] = reasons.get(key, 0)+1
                if 'validity_tier' in t:
                    tiers[t['validity_tier']] = tiers.get(t['validity_tier'], 0)+1
            tails = [t['crop_tail'] for t in trials if 'crop_tail' in t]
            row.update(accepted_steps=data.get('accepted_steps'), iterations=len(data.get('history', []))-1,
                       trials=len(trials), trial_status=reasons, validity_tiers=tiers,
                       crop_tail_max=max(tails) if tails else None,
                       crop_tail_median=float(np.median(tails)) if tails else None,
                       stop=data.get('stop'), outcome=data.get('outcome'), seconds=data.get('seconds'))
        stages.append(row)
    decisions = read(folder/'decisions.json')['decisions']
    frontier = [d for d in decisions if d['operation']['label'] == 'observable_frontier' and 'measured' in d]
    result = read(folder/'result.json') if (folder/'result.json').exists() else {}
    work = result.get('geometry_work', {})
    physics = result.get('physics', {}).get('seconds', {})
    return dict(max_speed_ratio=max(r['speed_ratio'] for r in ratios), speed_ratios=ratios, stages=stages,
                frontier=frontier[0]['measured']['frontier'] if frontier else None,
                outcome=result.get('outcome'), recovered=result.get('recovered'),
                final_audit_passed=result.get('final_audit_passed'), metrics=result.get('metrics'),
                fit_seconds=result.get('fit_and_localization_seconds'), total_seconds=result.get('total_seconds'),
                fit_units=result.get('fit_and_localization_units'),
                geometry_seconds=dict(preparation=work.get('preparation_seconds'), trial=work.get('trial_seconds'),
                                      certificate=work.get('certificate_seconds')),
                geometry_counts={k: v for k, v in work.items() if not k.endswith('seconds')},
                physics_seconds=physics)


def decide(report):
    """Pre-registered NU-001 rules (docs/iterations/cleaned_interfaces/iteration_08/01_plan.md)."""
    nodal = report['arms']['nodal']['cases']
    verdict = {}
    for arm in ('A', 'B'):
        cases = report['arms'][arm]['cases']
        drift, match = {}, {}
        for case, row in cases.items():
            base = nodal[case]
            degree = {s['stage']: s.get('log_degree') for s in base['stages']}
            flags = []
            if row['max_speed_ratio'] > 1.5:
                flags.append('speed_ratio>1.5')
            if row['max_speed_ratio'] > base['max_speed_ratio']*1.1:
                flags.append('speed_ratio>1.1x nodal')
            for s in row['stages']:
                d0 = degree.get(s['stage'])
                if s.get('log_degree') and d0 and s['log_degree'] > 1.3*d0:
                    flags.append(f"log_degree>{1.3:g}x nodal at {s['stage']}")
                    break
            drift[case] = flags
            status, base_status = report['arms'][arm]['status'].get(case), report['arms']['nodal']['status'].get(case)
            match[case] = bool((status == 'PASS' or base_status != 'PASS') and
                               (row['recovered'] or not base['recovered']))
        verdict[arm] = dict(drift_flags=drift, drifts=any(drift.values()), matches=sum(match.values()),
                            match=match, qualifies=not any(drift.values()) and sum(match.values()) >= 5)
    if verdict['A']['qualifies']:
        outcome = 'adopt arm A (N-update)'
    elif verdict['B']['qualifies']:
        outcome = 'adopt arm B (N-update + HLS tangential term)'
    else:
        outcome = 'keep the nodal trial map'
    return dict(verdict, outcome=outcome)


def drift(campaigns, output, certificate=True):
    report = dict(experiment='NU-001 drift audit', arms={})
    for campaign in campaigns:
        campaign = Path(campaign)
        # The nodal arm may be an archived CI-001 campaign (no arm.json).
        arm = read(campaign/'arm.json')['arm'] if (campaign/'arm.json').exists() else 'nodal'
        comparison = read(campaign/'comparison.json') if (campaign/'comparison.json').exists() else dict(rows=[])
        status = {r['id']: r['status'] for r in comparison['rows'] if r['id'] in CORE}
        cases = {}
        for case in CORE:
            folder = campaign/'runs'/case
            if (folder/'accepted.json').exists():
                cases[case] = case_drift(folder, certificate)
                print(arm, case, 'max r', round(cases[case]['max_speed_ratio'], 4), cases[case]['outcome'], flush=True)
        report['arms'][arm] = dict(campaign=str(campaign.resolve().relative_to(ROOT)), status=status, cases=cases)
    if all(a in report['arms'] for a in ARMS) and all(
            len(report['arms'][a]['cases']) == len(CORE) for a in ARMS):
        report['decision'] = decide(report)
    write(Path(output)/'drift.json', report)
    return report.get('decision', 'incomplete')


def main(argv=None):
    parser = argparse.ArgumentParser(description='NU-001 N-update drift audit')
    parser.add_argument('command', choices=('control', 'prepare', 'run', 'report', 'drift'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arm', choices=tuple(ARMS))
    parser.add_argument('--cases', nargs='+', default=list(CORE))
    parser.add_argument('--campaigns', type=Path, nargs='+')
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--frequency-threads', type=int, default=1)
    parser.add_argument('--no-certificate', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'control':
        value = control(args.output)
    elif args.command == 'prepare':
        if args.arm is None:
            parser.error('prepare requires --arm')
        value = prepare(args.output, args.arm)
    elif args.command == 'run':
        value = run(args.output, Execution(args.device, args.frequency_threads), args.cases)
    elif args.command == 'report':
        value = b.report(args.output)
    else:
        if not args.campaigns:
            parser.error('drift requires --campaigns')
        value = drift(args.campaigns, args.output, not args.no_certificate)
    print(json.dumps(portable(value), indent=2))


if __name__ == '__main__':
    main(sys.argv[1:])
