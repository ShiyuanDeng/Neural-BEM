"""TR-002: retrospective applicability of an empirical sufficient handoff rule."""
import numpy as np
from .common import *


def normal_graph(reference, other, count=512):
    """Nearest normal intersections, checked for a single orientation-preserving winding.

    Polygon intersections seed Newton on the actual Fourier curve. This is a
    sampled chart-validity test, not a continuum reach certificate.
    """
    a = reference.nodes(count)
    z = reference.values(count)
    n = a.normals@np.array([1, 1j])
    w = other.values(2048)
    tangential = ((w[None, :]-z[:, None])*np.conj(1j*n[:, None])).real
    following = np.roll(tangential, -1, axis=1)
    crosses = tangential*following <= 0
    fraction = np.divide(tangential, tangential-following,
                         out=np.zeros_like(tangential), where=tangential != following)
    interpolated = w[None, :]+fraction*(np.roll(w, -1)-w)[None, :]
    height = ((interpolated-z[:, None])*np.conj(n[:, None])).real
    nearest = np.argmin(np.where(crosses, abs(height), np.inf), axis=1)
    theta = (nearest+fraction[np.arange(count), nearest])*2*np.pi/2048
    for _ in range(8):
        e = np.exp(1j*np.outer(theta, other.modes))
        p, dp = e@other.coefficients, e@(1j*other.modes*other.coefficients)
        mismatch = ((p-z)*np.conj(1j*n)).real
        slope = (dp*np.conj(1j*n)).real
        if np.min(abs(slope)) < 1e-12:
            break
        theta -= mismatch/slope
    e = np.exp(1j*np.outer(theta, other.modes))
    p, dp = e@other.coefficients, e@(1j*other.modes*other.coefficients)
    delta = (np.roll(theta, -1)-theta+np.pi) % (2*np.pi)-np.pi
    winding = float(np.sum(delta)/(2*np.pi))
    tangent_alignment = ((dp/abs(dp))*np.conj(1j*n)).real
    tangent_error = float(np.max(abs(((p-z)*np.conj(1j*n)).real)))
    valid = bool(np.all(np.any(crosses, axis=1)) and np.all(delta > 0) and
                 abs(winding-1) < 1e-8 and np.min(tangent_alignment) > .2 and tangent_error < 1e-8)
    return dict(valid=valid, winding=winding, minimum_parameter_increment=float(np.min(delta)),
                minimum_tangent_alignment=float(np.min(tangent_alignment)),
                tangential_error_package=tangent_error,
                h_package=((p-z)*np.conj(n)).real)


def estimate(case, catalog, band, count, paired):
    path = OUTPUT/'TR-001/rows'/f'{case}__{catalog}__M{band}.json'
    record = read(path)
    if not record['qualification']['passed'] or not record.get('complete'):
        return None
    return next(e for e in record['estimates'] if e['frequencies'] == count and e['paired'] == paired)


def run(folder, budget):
    transitions = [('stage_1_damped', 'stage_2_damped', 3, 5, 1, 2, 'damped', 'damped'),
                   ('stage_2_damped', 'stage_3_damped', 5, 7, 2, 3, 'damped', 'damped'),
                   ('stage_3_damped', 'stage_4_damped', 7, 9, 3, 4, 'damped', 'damped'),
                   ('stage_4_damped', 'stage_4_undamped', 9, 9, 4, 4, 'damped', 'real')]
    for case in CASES[1:]:
        problem, truth = load_case(case)
        evaluator = Evaluator(problem, budget)
        for full in (False, True):
            for first, second, m1, m2, f1, f2, cat1, cat2 in transitions:
                saved, next_saved = read(archived(case, full, first)), read(archived(case, full, second))
                curve = curve_from(saved['curve'])
                graph = normal_graph(truth, curve)
                record = dict(case=case, full=full, first=first, second=second,
                    archived_stop=saved['stop'], next_stop=next_saved['stop'], normal_graph=graph,
                    next_accepted_steps=next_saved['accepted_steps'], applicable=False,
                    certified=False, truth_assisted=True)
                path = folder/'rows'/f'{case}__{full}__{first}.json'
                if not graph['valid']:
                    record['reason'] = 'No qualified single normal graph over truth'
                    write(path, record); continue
                chart = Chart(truth, m1, problem.length_unit_m)
                nodes = truth.nodes(512)
                basis = chart.velocities(None, nodes)*(1000*problem.length_unit_m)
                weights = nodes.arc_length_weights/nodes.perimeter
                h_mm = np.asarray(graph['h_package'])*(1000*problem.length_unit_m)
                q = np.linalg.solve(basis.T@(weights[:, None]*basis), basis.T@(weights*h_mm))
                remainder = h_mm-basis@q
                tail = float(np.sqrt(weights@remainder**2))
                e1, e2 = estimate(case, cat1, m1, f1, not full), estimate(case, cat2, m2, f2, not full)
                record.update(coordinates_mm=q, coefficient_norm_mm=np.linalg.norm(q),
                    band_tail_rms_mm=tail, band_tail_max_mm=np.max(abs(remainder)), current=e1, following=e2)
                if e1 is None or e2 is None or not e1['sigma_resolved'] or not e2['sigma_resolved']:
                    record['reason'] = 'Missing or unresolved empirical constants'
                    write(path, record); continue
                r = float(np.linalg.norm(q))
                if r >= min(1., e1['rho_sample_mm']):
                    record.update(reason='Endpoint is outside its current empirical radius or sampled 1 mm neighborhood',
                                  next_radius_mm=e2['rho_sample_mm'])
                    write(path, record); continue
                obs = select(getattr(problem, cat1), f1)
                actual, _ = evaluator.evaluate(chart, q, obs, jacobian=False, curve=curve)
                projected, _ = evaluator.evaluate(chart, q, obs, jacobian=False)
                origin, _ = evaluator.evaluate(chart, np.zeros(chart.dimension), obs, jacobian=False)
                target = np.stack([o.scattered for o in obs], axis=1)
                res = float(np.linalg.norm(normalized(actual-target, obs, not full)))
                model = float(np.linalg.norm(normalized(projected-actual, obs, not full)))
                discrepancy = float(np.linalg.norm(normalized(origin-target, obs, not full)))
                r = float(np.linalg.norm(q))
                denominator = e1['sigma_min']-2*e1['L_sample']*r
                eligible = r < min(1., e1['rho_sample_mm']) and denominator > 0
                lhs = (res+model+discrepancy)/denominator+tail if denominator > 0 else None
                record.update(residual_norm=res, data_truncation_error=model, truth_data_discrepancy=discrepancy,
                    empirical_error_indicator_mm=lhs, next_radius_mm=e2['rho_sample_mm'],
                    applicable=eligible, indicator_pass=bool(eligible and lhs < e2['rho_sample_mm']),
                    reason='Empirical only: sampled L and chart/truncation measurements' if eligible else
                           'Endpoint is outside its current empirical radius or sampled 1 mm neighborhood')
                write(path, record)
                print('HANDOFF', case, full, first, record['reason'], flush=True)
    census = {}
    for phase in ('phase1', 'phase3', 'phase4'):
        path = ROOT/'results/validation/cleaned_interfaces/FM-003'/phase/'census.json'
        if path.exists():
            census[phase] = dict(path=b.path_ref(path), sha256=digest(path), record=read(path))
        else:
            census[phase] = dict(status='pending; no partial census used for truth scoring')
    write(folder/'fm003_context.json', census)


if __name__ == '__main__':
    execute('TR-002', run, 1800., 10000)
