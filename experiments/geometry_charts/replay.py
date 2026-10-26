"""TA-001: rebuild saved refusals, classify and replay a positive-speed chart.

Run with single-thread BLAS and taskset -c 6-11 in the EMNerf environment.
No fits, truth scoring, policy changes or maintained solver edits occur here.
"""
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import resource
import subprocess
from time import perf_counter
import traceback

import numpy as np
from scipy.optimize import minimize, root

from bem_inverse import b5_residual, b8_gauss_newton, c9_lm, checks
from bem_inverse.continuation.geometry import FourierCurve, grid_size, values
from bem_inverse.geometry_update_methods import control_step
from bem_inverse.geometry_update_methods.spectral import SpectralProjectedUpdate, geometry_update
from bem_inverse.io import curve_from, curve_record, digest, read, write
from bem_inverse.physics import Execution
from bem_inverse.stage_types import BackendConfig, FitStage
from experiments.benchmark import campaign

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'results/validation/cleaned_interfaces/NR-001/M1/runs'
OUTPUT = ROOT/'results/validation/cleaned_interfaces/TA-001'
ROWS = [('aphex_twin__c0.5', 'stage_3_damped'), ('aphex_twin__c4', 'stage_2_damped'),
        ('aphex_twin__c13.3', 'stage_4_undamped'), ('hook__c13.3', 'release_M11')]
UNIT = .05


def environment():
    return dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                load=os.getloadavg(), cpu_affinity=sorted(os.sched_getaffinity(0)),
                blas={k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS')},
                gpu='not used', max_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)


def inputs(case, label):
    folder = SOURCE/case
    saved = read(folder/(label+'.json'))
    config = read(folder/'configuration.json')
    operation = next(o for o in config['plan']['operations'] if o['label'] == label)
    raw = operation['stage']
    problem = campaign.problem(case)
    catalog = problem.damped if any(raw['damping']) else problem.real
    observations = tuple(next(o for o in catalog if o.frequency_hz == f) for f in raw['frequencies_hz'])
    stage = FitStage(**{k: raw[k] for k in ('label', 'weights', 'update_modes', 'curve_modes',
                                          'nodes', 'iterations', 'quota', 'resolution_kind')},
                     observations=observations)
    return saved, config, stage, BackendConfig(**operation['optimizer'])


def evaluate(curve, stage, contrast, physics, forward):
    """Exact current A1-A4 and B5 at the recorded stage catalog/resolution."""
    states = tuple(forward(curve, o, contrast, stage.nodes) for o in stage.observations)
    observed = np.column_stack([o.scattered.reshape(-1) for o in stage.observations])
    prediction = np.column_stack([s.prediction.reshape(-1) for s in states])
    return b5_residual.evaluate(curve, prediction, states, observed, stage.weights, 1e-12)


def try_physics(curve, stage, contrast, physics, forward):
    started = perf_counter()
    try:
        evaluated = evaluate(curve, stage, contrast, physics, forward)
        return dict(status='accepted_by_physics', loss=evaluated.loss,
                    relative_l2=evaluated.relative_l2, seconds=perf_counter()-started)
    except Exception as exc:
        return dict(status='physics_refused', loss=None, exception=type(exc).__name__,
                    message=str(exc), seconds=perf_counter()-started)


def rebuild(case, label):
    saved, configuration, stage, config = inputs(case, label)
    trial = saved['trials'][-1]
    curve = curve_from(saved['curve'])
    exact = curve_from(trial['physics_failures'][0]['candidate_coefficients'])
    contrast = configuration['contrast']
    physics, forward = campaign._physics('modal_muller', Execution(device='cpu', frequency_threads=1))
    started = perf_counter()
    current = evaluate(curve, stage, contrast, physics, forward)
    update = SpectralProjectedUpdate(UNIT, batched=True, device='cpu')
    prepared = update.prepare(curve, stage.update_modes, stage.curve_modes)
    blocks = [physics.derivative(f, update, prepared).reshape(-1, len(prepared.orders)) for f in current.forwards]
    observed = np.column_stack([o.scattered.reshape(-1) for o in stage.observations])
    jac = b8_gauss_newton.residual_jacobian(blocks, observed, stage.weights, config.residual_floor)
    gradient = b8_gauss_newton.gradient(jac, current.residual)
    curvature = b8_gauss_newton.curvature(jac)
    damping = c9_lm.damping_matrix(curvature, prepared, update, config, None)
    raw = c9_lm.solve_proposal(gradient, curvature, damping, trial['damping'])
    bounded = control_step(raw, prepared, update, config)
    used = bounded*2.**-trial['backtrack']
    rebuilt, metrics = geometry_update(used, prepared=prepared, settings=update)
    scalar = {k: dict(saved=trial[k], rebuilt=float(v), relative_error=abs(v-trial[k])/max(abs(trial[k]),1e-30))
              for k,v in dict(step_norm_m=np.linalg.norm(used), **{k: metrics[k] for k in
                                  ('maximum_normal_m', 'speed_ratio')}).items()}
    coefficient_error = np.max(abs(rebuilt.values(grid_size(curve.band))-exact.values(grid_size(curve.band))))*UNIT*1000
    passed = coefficient_error < .001 and all(s['relative_error'] < .01 for s in scalar.values())
    row = dict(case=case, stage=label, M=stage.update_modes, K=curve.band, nodes=stage.nodes,
               contrast=contrast, roundoff_tolerance=dict(curve_mm=.001, scalar_relative=.01),
               reproduction_passed=passed, scalar_comparison=scalar, coefficient_curve_error_mm=coefficient_error,
               current_loss=current.loss, saved_loss=saved['final_loss'],
               saved_loss_relative_error=abs(current.loss/saved['final_loss']-1),
               bounded_step_m=bounded, used_step_m=used,
               b6_velocity=curve_record(FourierCurve(prepared.derivatives@bounded)),
               accepted=curve_record(curve), original=curve_record(exact), rebuilt=curve_record(rebuilt),
               backtracks=list(range(trial['backtrack']+1)), failed_backtrack=trial['backtrack'],
               source_sha256=digest(SOURCE/case/(label+'.json')),
               original_physics=try_physics(exact, stage, contrast, physics, forward),
               seconds=perf_counter()-started, environment=environment())
    write(OUTPUT/'rebuild'/f'{case}.json', row)
    print(case, 'REBUILD', passed, f'curve error {coefficient_error:.3g} mm',
          f'loss {current.loss:.9g}', 'rss_MB', environment()['max_rss_mb'], flush=True)
    return row


def at(curve, theta, derivative=0):
    return np.exp(1j*np.asarray(theta)[..., None]*curve.modes)@(curve.coefficients*(1j*curve.modes)**derivative)


def geometry_metrics(curve, count=1024):
    """Sample the complete torus, then refine its lowest candidates continuously."""
    theta = 2*np.pi*np.arange(count)/count
    z, dz = curve.values(count), curve.values(count, 1)
    delta = abs(np.exp(1j*theta[:,None])-np.exp(1j*theta[None,:]))
    chords = abs(z[:,None]-z[None,:])
    np.fill_diagonal(delta, 1.)
    quotient2 = (chords/delta)**2
    np.fill_diagonal(quotient2, abs(dz)**2)
    candidates = np.argpartition(quotient2.ravel(), 16)[:16]

    def objective(t):
        # The finite sine quotient evaluates W stably even on the diagonal.
        mid, separation = t
        sine_quotient = curve.modes*np.sinc(curve.modes*separation/(2*np.pi))/np.sinc(separation/(2*np.pi))
        return float(abs(np.sum(curve.coefficients*np.exp(1j*curve.modes*mid)*sine_quotient))**2)

    refined = []
    for flat in candidates:
        i,j = np.unravel_index(flat, quotient2.shape)
        separation = (theta[i]-theta[j]+np.pi)%(2*np.pi)-np.pi
        mid = theta[j]+separation/2
        fit = minimize(objective, [mid,separation], method='Nelder-Mead',
                       options=dict(xatol=1e-11, fatol=1e-15, maxiter=400))
        refined.append((fit.fun, fit.x))
    qmin, (mid, separation) = min(refined, key=lambda item: item[0])
    separation = abs((separation+np.pi)%(2*np.pi)-np.pi)
    speeds = abs(dz)
    idx = np.argpartition(speeds, 8)[:8]
    speed_fits = [minimize(lambda t: float(abs(at(curve,t[0],1))**2), [theta[i]],
                          method='Nelder-Mead', options=dict(xatol=1e-12,fatol=1e-16)) for i in idx]
    minimum_speed = np.sqrt(min(f.fun for f in speed_fits))
    gap = np.minimum(abs(theta[:,None]-theta[None,:]), 2*np.pi-abs(theta[:,None]-theta[None,:]))
    distant = np.where(gap>=np.pi/4, chords, np.inf)
    i,j = np.unravel_index(np.argmin(distant), distant.shape)
    closest = minimize(lambda t: float(abs(at(curve,t[0])-at(curve,t[0]+t[1]))**2),
                       [theta[i],(theta[j]-theta[i])%(2*np.pi)], method='SLSQP',
                       bounds=[(-4*np.pi,4*np.pi), (np.pi/4, 2*np.pi-np.pi/4)],
                       options=dict(ftol=1e-15,maxiter=200))
    # A second sign start covers a wrapped pair without relying on sample order.
    sampled_closest = float(distant[i,j])
    distant_min = min(sampled_closest, np.sqrt(max(closest.fun,0)))
    ratio = minimum_speed/float(np.mean(speeds))
    where = 'diagonal' if separation < .01 else 'off_diagonal'
    # Position is primary; severity is reported separately instead of asserting a binary pathology.
    kind = ('speed-controlled' if where=='diagonal' else 'nonlocal-chord-controlled')
    return dict(min_W2=float(qmin), W_over_mean_speed=float(np.sqrt(qmin)/np.mean(speeds)),
                minimum_location=where, refusal_type=kind, separation_rad=float(separation),
                min_pair_theta=[float(mid+separation/2),float(mid-separation/2)],
                min_speed_package=float(minimum_speed), minimum_speed_over_mean=float(ratio),
                speed_max_over_min=float(max(speeds)/minimum_speed),
                distant_approach_mm=float(distant_min*UNIT*1000),
                distant_cutoff_rad=float(np.pi/4), search_nodes=count)


def coefficient_bound(accepted, trial):
    """Haibing item 3: exact finite q coefficients and the displacement Wiener bound."""
    from bem_inverse.a1_geometry import real_product
    k = accepted.band
    quotient = np.zeros((2*k+1,2*k+1),complex)
    for j in range(1,k+1):
        for r in range(j):
            quotient[k+j-1-r,k+r] += accepted.coefficients[k+j]
            quotient[k-1-r,k-j+r] -= accepted.coefficients[k-j]
    q = real_product(quotient,quotient,2)
    central = q[2*k,2*k].real
    offsum = np.sum(abs(q))-abs(q[2*k,2*k])
    lower2 = float(central-offsum)
    displacement = float(np.sum(abs(accepted.modes)*abs(trial.coefficients-accepted.coefficients)))
    mu = float(np.sqrt(max(lower2,0)))
    return dict(q_constant=float(central), off_diagonal_l1=float(offsum), q_lower_bound=lower2,
                displacement_W_bound=displacement, certified_margin=mu-displacement,
                verdict='certified_safe' if lower2>0 and displacement<mu else 'inconclusive',
                interpretation='An inconclusive sufficient bound is not proof of invalidity.')


def classify(row):
    accepted, original = curve_from(row['accepted']), curve_from(row['original'])
    answer = dict(case=row['case'], accepted=geometry_metrics(accepted), original=geometry_metrics(original),
                  haibing=coefficient_bound(accepted, original), environment=environment())
    write(OUTPUT/'classification'/f'{row["case"]}.json', answer)
    print(row['case'], 'CLASSIFY', answer['original']['refusal_type'],
          'W/mean', answer['original']['W_over_mean_speed'],
          'speed/mean', answer['original']['minimum_speed_over_mean'], flush=True)
    return answer


class TangentChart:
    """Positive speed, angle, closure, then integration and projection to stored K.

    Length plus normalized log-speed density is equivalent to log speed.
    The two closure directions are angle corrections -sin(phi), cos(phi).
    Their 2x2 derivative is nonsingular unless tangents all lie on one line.
    """
    def __init__(self, curve, velocity, count=None):
        self.curve = curve
        self.count = count or max(4096, grid_size(curve.band))
        self.theta = 2*np.pi*np.arange(self.count)/self.count
        dz = curve.values(self.count,1)
        self.speed = abs(dz)
        self.angle = np.unwrap(np.angle(dz))
        self.length = 2*np.pi*float(np.mean(self.speed))
        self.log_density = np.log(self.speed/(self.length/(2*np.pi)))
        self.normal = -1j*dz/self.speed
        # Retain the B6 tangential gauge so cropping leaves its exact normal
        # velocity unchanged to first order. Projecting a purely normal field
        # first would introduce an extra finite-K derivative difference.
        original_velocity = velocity.values(self.count)
        spectrum = np.fft.fft(original_velocity)/self.count
        modes = np.fft.fftfreq(self.count)*self.count
        du = np.fft.ifft(spectrum*(1j*modes))*self.count
        ratio = du/dz
        self.dlogspeed = ratio.real
        self.dangle = ratio.imag
        self.dposition = np.mean(original_velocity)
        self.projected_velocity = velocity
        self.angle_directions = np.column_stack((-np.sin(self.angle),np.cos(self.angle)))

    def trial(self, alpha):
        logspeed = np.log(self.length/(2*np.pi))+self.log_density+alpha*self.dlogspeed
        phi = self.angle+alpha*self.dangle
        speed = np.exp(logspeed)
        directions = self.angle_directions

        def closure(x, jac=False):
            tangent = speed*np.exp(1j*(phi+directions@x))
            if jac:
                derivatives = np.mean(1j*tangent[:,None]*directions,axis=0)
                return np.vstack((derivatives.real,derivatives.imag))
            val = np.mean(tangent)
            return np.array([val.real,val.imag])
        solution = root(closure,np.zeros(2),jac=lambda x: closure(x,True),tol=1e-11)
        residual = float(np.linalg.norm(closure(solution.x)))
        if residual > 1e-10*max(np.mean(speed),1):
            raise ValueError(f'closure did not converge: {residual:.3g}')
        tangent = speed*np.exp(1j*(phi+directions@solution.x))
        coefficients = np.fft.fft(tangent)/self.count
        modes = np.arange(-self.curve.band,self.curve.band+1)
        stored = coefficients[modes%self.count].copy()
        nz = modes!=0
        stored[nz] /= 1j*modes[nz]
        stored[~nz] = self.curve.coefficients[self.curve.band]+alpha*self.dposition
        result = FourierCurve(stored)
        projection_error = np.max(abs(result.values(self.count,1)-tangent))*UNIT*1000
        return result, dict(closure_residual_package=residual, closure_corrections=solution.x,
                            minimum_chart_speed_package=float(min(speed)),
                            tangent_projection_error_mm=projection_error,
                            chart_length_m=float(2*np.pi*np.mean(speed)*UNIT))


def replay(row):
    case = row['case']
    if not row['reproduction_passed']:
        print(case,'STOP: reconstruction did not reproduce',flush=True)
        return
    saved, configuration, stage, config = inputs(case,row['stage'])
    curve, velocity = curve_from(row['accepted']), curve_from(row['b6_velocity'])
    chart = TangentChart(curve,velocity)
    roundtrip,_ = chart.trial(0.)
    roundtrip_mm = float(np.max(abs(roundtrip.values(chart.count)-curve.values(chart.count)))*UNIT*1000)
    if roundtrip_mm > .001:
        raise ValueError(f'round trip {roundtrip_mm} mm exceeds .001 mm')
    derivatives=[]
    for epsilon in (1e-3,5e-4):
        plus,_ = chart.trial(epsilon)
        minus,_ = chart.trial(-epsilon)
        numerical = (plus.coefficients-minus.coefficients)/(2*epsilon)
        expected = chart.projected_velocity.coefficients
        error = np.linalg.norm(numerical-expected)/max(np.linalg.norm(expected),1e-30)
        derivatives.append(dict(epsilon=epsilon, relative_coefficient_error=float(error)))
    physics,forward = campaign._physics('modal_muller', Execution(device='cpu',frequency_threads=1))
    answer=dict(case=case,roundtrip_mm=roundtrip_mm,first_order_checks=derivatives,
                settings=dict(chart_nodes=chart.count, closure='two angle corrections',
                              coordinates='length, normalized log-speed, tangent angle, mean position',
                              finite_band=curve.band,first_order_target='exact original B6 coefficient velocity, including tangential gauge'),
                trials=[], environment_start=environment())
    for backtrack in row['backtracks']:
        alpha=2.**-backtrack
        started=perf_counter()
        try:
            candidate,detail=chart.trial(alpha)
            metrics=geometry_metrics(candidate)
            valid=dict(status='valid')
            try:
                checks.check_area(candidate.coefficients)
                nodes=candidate.nodes(grid_size(candidate.band))
                checks.check_speed(nodes.speeds)
                checks.check_intersection(nodes.points)
            except Exception as exc:
                valid=dict(status='geometry_refused',message=str(exc))
            # Record actual modal refusal even when sampled geometry is invalid;
            # a physics-accepted curve with invalid geometry never counts as success.
            physics_row=try_physics(candidate,stage,configuration['contrast'],physics,forward)
            improved=bool(valid['status']=='valid' and physics_row['status']=='accepted_by_physics'
                          and physics_row['loss']<row['current_loss'])
            trial=dict(backtrack=backtrack,alpha=alpha,curve=curve_record(candidate),
                       **detail,metrics=metrics,geometry=valid,physics=physics_row,
                       lower_exact_loss=improved,seconds=perf_counter()-started)
        except Exception as exc:
            trial=dict(backtrack=backtrack,alpha=alpha,construction_failed=str(exc),
                       traceback=traceback.format_exc(),lower_exact_loss=False)
        answer['trials'].append(trial)
        answer['environment_end']=environment()
        write(OUTPUT/'replay'/f'{case}.json',answer)
        print(case,'CHART',backtrack,trial.get('geometry'),trial.get('physics'),
              'lower_loss',trial['lower_exact_loss'],flush=True)
    return answer


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('step',choices=('rebuild','classify','replay'))
    parser.add_argument('--case',choices=[c for c,_ in ROWS])
    args=parser.parse_args()
    for case,label in ROWS:
        if args.case and args.case!=case:
            continue
        if args.step=='rebuild':
            rebuild(case,label)
        else:
            row=read(OUTPUT/'rebuild'/f'{case}.json')
            (classify if args.step=='classify' else replay)(row)


if __name__=='__main__':
    main()
