"""TR-003: full-curvature stopping audits and bounded real data homotopies."""
import numpy as np
from .common import *


def hessian(gradient, q, step):
    eye = np.eye(len(q))*step
    raw = np.column_stack([(gradient(q+u)-gradient(q-u))/(2*step) for u in eye])
    return (raw+raw.T)/2, float(np.linalg.norm(raw-raw.T, 2))


class Objective:
    def __init__(self, evaluator, chart, observations, paired, nodes=512):
        self.evaluator, self.chart, self.obs, self.paired, self.nodes = evaluator, chart, observations, paired, nodes
        self.cache = {}

    def evaluate(self, q):
        key = np.asarray(q).tobytes()
        if key not in self.cache:
            g, j = self.evaluator.evaluate(self.chart, q, self.obs, self.nodes)
            self.cache[key] = residual_jacobian(g, j, self.obs, self.paired)
            if len(self.cache) > 150:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[key]

    def gradient(self, q):
        r, j = self.evaluate(q)
        return j.T@r

    def loss(self, q):
        r, _ = self.evaluate(q)
        return .5*float(r@r)


def track(system, x0, *, max_steps=40, initial_step=.5, maximum_step=1., minimum_step=.015625,
          tolerance=1e-8, time_scale=5., callback=None):
    """Bounded diagnostic pseudo-arclength, including folds in the last coordinate.

    system(x) returns F, [dF/dq, dF/d(5t)]. Corrector uses the tangent hyperplane,
    not t as an independent coordinate. This is not a production inverse solver.
    """
    x = np.asarray(x0, float).copy()
    f, matrix = system(x)
    if np.linalg.norm(f, np.inf) > tolerance:
        raise ValueError('Continuation start is not stationary')
    _, _, vt = np.linalg.svd(matrix, full_matrices=True)
    tangent = vt[-1]
    if tangent[-1] < 0:
        tangent *= -1
    path = [dict(x=x.copy(), gradient_inf=np.linalg.norm(f, np.inf), tangent=tangent.copy())]
    refusals, ds = [], initial_step
    reason = 'accepted-step cap'
    while len(path)-1 < max_steps:
        predictor = x+ds*tangent
        y = predictor.copy()
        try:
            for iteration in range(8):
                f, matrix = system(y)
                arc = float(tangent@(y-predictor))
                if np.linalg.norm(f, np.inf) <= tolerance and abs(arc) <= 1e-8:
                    break
                augmented = np.vstack((matrix, tangent))
                correction = np.linalg.solve(augmented, np.r_[f, arc])
                if np.linalg.norm(correction) > 3*ds:
                    raise ValueError('Corrector left local arclength neighborhood')
                y -= correction
            else:
                raise ValueError('Corrector iteration cap')
            _, singular, vt = np.linalg.svd(matrix, full_matrices=True)
            next_tangent = vt[-1]
            if next_tangent@tangent < 0:
                next_tangent *= -1
            row = dict(x=y.copy(), gradient_inf=np.linalg.norm(f, np.inf), tangent=next_tangent.copy(),
                       tangent_time_reversal=bool(tangent[-1]*next_tangent[-1] < 0),
                       step=ds, corrector_iterations=iteration+1,
                       augmented_jacobian_sigma_min=singular[-1])
            path.append(row)
            x, tangent = y, next_tangent
            if callback:
                callback(path, refusals)
            if x[-1] >= time_scale:
                reason = 'target parameter crossed'; break
            ds = min(maximum_step, ds*1.25)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            refusals.append(dict(predictor=predictor, step=ds, reason=str(exc)))
            ds /= 2
            if ds < minimum_step:
                reason = 'minimum arclength step'; break
    return dict(path=path, refusals=refusals, stop=reason)


def endpoint(folder, budget, case, full):
    problem, op = op_problem(case, full, 'stage_2_damped')
    saved = read(archived(case, full, op.label))
    chart = Chart(curve_from(saved['curve']), 5, problem.length_unit_m, projected=True, storage=12)
    evaluator = Evaluator(problem, budget)
    zero = np.zeros(chart.dimension)
    data = []
    objectives = {}
    for nodes in (512, 1024):
        objective = Objective(evaluator, chart, op.stage.observations, not full, nodes)
        objectives[nodes] = objective
        r, j = objective.evaluate(zero)
        for step in (.002, .001):
            h, asymmetry = hessian(objective.gradient, zero, step)
            data.append(dict(nodes=nodes, step_mm=step, gradient=j.T@r, gradient_inf=np.linalg.norm(j.T@r, np.inf),
                loss=.5*float(r@r), hessian=h, hessian_eigenvalues=np.linalg.eigvalsh(h),
                gauss_newton_eigenvalues=np.linalg.eigvalsh(j.T@j), hessian_asymmetry=asymmetry,
                residual_curvature_relative=np.linalg.norm(h-j.T@j, 2)/max(np.linalg.norm(h, 2), 1e-300)))
    h = np.asarray(data[-1]['hessian'])
    errors = [np.linalg.norm(np.asarray(r['hessian'])-h, 2) for r in data[:-1]]
    error = max(errors+[r['hessian_asymmetry'] for r in data])
    gradient_error = max(np.linalg.norm(np.asarray(r['gradient'])-data[-1]['gradient'], np.inf) for r in data)
    eig, vectors = np.linalg.eigh(h)
    scale = max(np.linalg.norm(h, 2), 1e-300)
    loss_error = abs(data[-1]['loss']-saved['final_loss'])/max(abs(saved['final_loss']), 1e-14)
    qualified = (error/scale <= 1e-3 and gradient_error <= max(1e-10, data[-1]['gradient_inf']*1e-3)
                 and loss_error <= 1e-7)
    stationary = data[-1]['gradient_inf'] <= 1e-8 and qualified
    kind = ('resolved positive curvature' if eig[0] > 10*error else
            'resolved negative curvature' if eig[0] < -10*error else 'unresolved near-zero curvature')
    record = dict(case=case, full=full, archive_stop=saved['stop'], archive_loss=saved['final_loss'],
        measurements=data, hessian_error_operator=error, hessian_error_relative=error/scale,
        archived_loss_relative_error=loss_error,
        gradient_error_inf=gradient_error, numerical_qualification=qualified,
        stationary_at_declared_tolerance=stationary, curvature=kind,
        chart='affine production tangent; second derivative differs from finite retraction away from stationarity',
        production_trials=[], archived_acceptance_checks=saved['acceptance_checks'])
    gradient = np.asarray(data[-1]['gradient'])
    directions = [-gradient/max(np.linalg.norm(gradient), 1e-300), vectors[:, 0]]
    for name, direction in zip(('negative_gradient', 'weakest_curvature'), directions):
        for step in (.001, .01, .1):
            for sign in (-1, 1):
                q = sign*step*direction
                try:
                    trial = chart.production_trial(q)
                    gains = []
                    for nodes in (512, 1024):
                        g, _ = evaluator.evaluate(chart, q, op.stage.observations, nodes, False, curve=trial)
                        target = np.stack([o.scattered for o in op.stage.observations], axis=1)
                        r = normalized(g-target, op.stage.observations, not full)
                        gains.append(objectives[nodes].loss(zero)-.5*float(r@r))
                    margin = op.optimizer.acceptance_absolute_margin+op.optimizer.acceptance_relative_margin*data[-1]['loss']
                    record['production_trials'].append(dict(direction=name, step_mm=sign*step, gains=gains,
                        acceptance_margin=margin, resolvable_decrease=min(gains)>5*abs(gains[0]-gains[1]),
                        passes_archived_margin=min(gains)>margin+5*abs(gains[0]-gains[1])))
                except (ValueError, FloatingPointError) as exc:
                    record['production_trials'].append(dict(direction=name, step_mm=sign*step, refused=str(exc)))
    record.update(physics=evaluator.physics.receipt(), work_so_far=budget.record())
    write(folder/'endpoints'/f'{case}__{full}.json', record)
    print('ENDPOINT', case, full, stationary, kind, flush=True)


def homotopy(folder, budget, case):
    problem, op = op_problem(case, False, 'stage_2_damped')
    start = curve_from(read(archived(case, False, 'stage_1_damped'))['curve'])
    chart = Chart(start, 5, problem.length_unit_m, projected=True, storage=12)
    evaluator = Evaluator(problem, budget)
    objective = Objective(evaluator, chart, op.stage.observations, True)
    zero = np.zeros(chart.dimension)
    r_start, _ = objective.evaluate(zero)
    # r_t = r(q) - (1-t)*r(0); at t=0,q=0 it vanishes exactly.
    def gradient(q, t):
        r, j = objective.evaluate(q)
        return j.T@(r-(1-t)*r_start)
    def system(x):
        q, t = x[:-1], x[-1]/5.
        if np.linalg.norm(q)>15 or t < -.1 or t > 1.5:
            raise ValueError('Declared fixed-chart/parameter domain reached')
        r, j = objective.evaluate(q)
        h, _ = hessian(lambda p:gradient(p, t), q, .002)
        return j.T@(r-(1-t)*r_start), np.column_stack((h, j.T@r_start/5.))
    path = folder/'branches'/f'{case}.json'
    def checkpoint(points, refusals):
        write(path, dict(case=case, complete=False, path=points, refusals=refusals, work_so_far=budget.record()))
    record = track(system, np.zeros(chart.dimension+1), callback=checkpoint)
    record.update(case=case, complete=True, truth_free_path=True, chart_origin=curve_record(chart.base),
                  time_scale=5., stationary_tolerance=1e-8, endpoint_correction=None)
    if record['stop'] == 'target parameter crossed':
        q = np.asarray(record['path'][-1]['x'])[:-1].copy()
        correction = dict(converged=False, iterations=[])
        for iteration in range(12):
            g, matrix = system(np.r_[q, 5.])
            correction['iterations'].append(dict(iteration=iteration, gradient_inf=np.linalg.norm(g, np.inf)))
            if np.linalg.norm(g, np.inf) <= 1e-8:
                correction.update(converged=True, q_mm=q, loss=objective.loss(q), curve=curve_record(chart.curve(q)))
                break
            step = np.linalg.solve(matrix[:, :-1], -g)
            if np.linalg.norm(step)>2:
                correction['refusal']='Target corrector exceeds 2 mm'; break
            q += step
        record['endpoint_correction'] = correction
    record['fold_candidates'] = sum(bool(r.get('tangent_time_reversal')) for r in record['path'])
    record['fold_confirmations'] = []
    if record['fold_candidates']:
        fine = Objective(evaluator, chart, op.stage.observations, True, 1024)
        for index, point in enumerate(record['path']):
            if not point.get('tangent_time_reversal'):
                continue
            bracket = []
            for p in record['path'][index-1:index+1]:
                x = np.asarray(p['x']); q, t = x[:-1], x[-1]/5
                def grad(v):
                    rr, jj = fine.evaluate(v)
                    return jj.T@(rr-(1-t)*r_start)
                hh, skew = hessian(grad, q, .001)
                rr, jj = fine.evaluate(q)
                mat = np.column_stack((hh, jj.T@r_start/5))
                _, _, vt = np.linalg.svd(mat, full_matrices=True)
                tangent = vt[-1]
                if tangent@p['tangent'] < 0:
                    tangent *= -1
                bracket.append(dict(t=t, gradient_inf=np.linalg.norm(grad(q), np.inf),
                                    time_tangent=tangent[-1], eigenvalues=np.linalg.eigvalsh(hh), skew=skew))
            confirmed = (all(v['gradient_inf'] <= 1e-8 for v in bracket) and
                         bracket[0]['time_tangent']*bracket[1]['time_tangent'] < 0 and
                         min(abs(v['time_tangent']) for v in bracket) > 1e-3)
            record['fold_confirmations'].append(dict(index=index, bracket=bracket, confirmed=confirmed))
    record['fold_claim'] = ('Resolved turning bracket in this finite diagnostic chart' if
        any(r['confirmed'] for r in record['fold_confirmations']) else
        'No confirmed fold on this bounded path; global absence is not established')
    record.update(physics=evaluator.physics.receipt(), work_so_far=budget.record())
    write(path, record)
    print('BRANCH', case, record['stop'], record['fold_candidates'], flush=True)


def run(folder, budget):
    for case in CASES[1:3]:
        for full in (False, True):
            endpoint(folder, budget, case, full)
    for case in CASES[1:3]:
        homotopy(folder, budget, case)


if __name__ == '__main__':
    execute('TR-003', run, 3600., 20000)
