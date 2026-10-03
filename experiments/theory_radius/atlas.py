"""TR-001: empirical, not certified, local normal-chart radius measurements."""
from dataclasses import replace
import numpy as np
from .common import *
from bem_inverse.mie_localize import paired_data


def relative(a, b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b), 1e-300))


def groups(g, j, observations):
    for count in range(1, 5):
        obs = observations[:count]
        for paired in (True, False):
            yield count, paired, normalized(g[:, :count], obs, paired), normalized(j[:, :count], obs, paired)


def qualification(evaluator, chart, observations, g, j, circle=False):
    zero = np.zeros(chart.dimension)
    gf, jf = evaluator.evaluate(chart, zero, observations, 1024)
    checks = dict(field_relative=relative(g, gf), jacobian_relative=relative(j, jf))
    rng = np.random.default_rng(20261003)
    u = rng.normal(size=chart.dimension); u /= np.linalg.norm(u)
    checks['fd'] = []
    for step in (.001, .0003):
        gp, _ = evaluator.evaluate(chart, step*u, observations, jacobian=False)
        gm, _ = evaluator.evaluate(chart, -step*u, observations, jacobian=False)
        fd = (gp-gm)/(2*step)
        error = np.linalg.norm(fd-j@u)
        checks['fd'].append(dict(step_mm=step, relative=float(error/max(np.linalg.norm(j@u), 1e-300)),
                                whole_jacobian_scaled=float(error/np.linalg.norm(j))))
    if circle:
        mie = []
        for i, obs in enumerate(observations):
            a = obs.acquisition
            def disk(radius):
                return paired_data(obs.wavenumber, evaluator.problem.contrast, [0j], [radius],
                                   a.sources, a.receivers, 80)[0, 0]*a.strength
            h = 1e-5  # package length; 0.0005 mm on this acquisition
            exact = disk(.6)
            derivative = (disk(.6+h)-disk(.6-h))/(2*h*1000*chart.unit)
            constant = np.linalg.solve(chart.transform, np.eye(chart.dimension)[0])
            mie.append(dict(frequency_hz=obs.frequency_hz,
                            field_relative=relative(np.diag(g[:, i]), exact),
                            radial_derivative_relative=relative(np.diag(j[:, i]@constant), derivative)))
        checks['mie'] = mie
    checks['metric_error'] = chart.metric_error
    checks['chart_projection_relative'] = chart.projection_error
    checks['passed'] = bool(checks['field_relative'] <= 1e-7 and checks['jacobian_relative'] <= 1e-5
        and max(r['whole_jacobian_scaled'] for r in checks['fd']) <= 1e-4
        and chart.projection_error <= 1e-5 and chart.metric_error <= 1e-10
        and all(r['field_relative'] <= 1e-7 and r['radial_derivative_relative'] <= 1e-4
                for r in checks.get('mie', [])))
    return checks, gf, jf


def atlas_case(folder, budget, case, catalog):
    problem, truth = load_case(case)
    evaluator = Evaluator(problem, budget)
    observations = getattr(problem, catalog)
    wide = Chart(truth, 31, problem.length_unit_m)
    g_all, j_all = evaluator.evaluate(wide, np.zeros(63), observations)
    if case == CASES[0]:
        # Newly synthesized circle data are explicitly qualified at N1024/2048.
        fine, _ = evaluator.evaluate(wide, np.zeros(63), observations, 1024, False)
        finer, _ = evaluator.evaluate(wide, np.zeros(63), observations, 2048, False)
        circle_data_error = relative(fine, finer)
        observations = tuple(replace(o, scattered=fine[:, i]) for i, o in enumerate(observations))
        if circle_data_error > 1e-8:
            raise ValueError('Circle catalog resolution failed')
    else:
        circle_data_error = None
    indices = [next(i for i, o in enumerate(observations) if o.frequency_hz == f) for f in FREQUENCIES]
    obs = tuple(observations[i] for i in indices)
    g, jw = g_all[:, indices], j_all[:, indices]
    baseline = []
    grams = {}
    for paired in (True, False):
        for i, observation in enumerate(observations):
            z = normalized(j_all[:, i:i+1], (observation,), paired)
            grams[f'{paired}_{i}'] = z.T@z
    np.savez_compressed(folder/f'{case}__{catalog}__grams.npz', **grams)
    for band in BANDS+(23, 31):
        chart = Chart(truth, band, problem.length_unit_m)
        mapping = np.linalg.lstsq(wide.vectors, chart.vectors, rcond=None)[0]
        if relative(wide.vectors@mapping, chart.vectors) > 1e-8:
            raise ValueError('Nested fixed-chart mapping is unresolved')
        for paired in (True, False):
            for count, inds in [(n, indices[:n]) for n in range(1, 5)]+[(19, list(range(19)))]:
                jo = normalized(j_all[:, inds]@mapping, tuple(observations[i] for i in inds), paired)
                s, _ = spectrum(jo)
                baseline.append(dict(M=band, paired=paired, frequencies=len(inds), singular_values=s,
                                     sigma_min=s[-1], structural_nullity=max(0, jo.shape[1]-jo.shape[0])))
    write(folder/'base'/f'{case}__{catalog}.json', dict(case=case, catalog=catalog, spectra=baseline,
          circle_catalog_resolution_error=circle_data_error, curve=curve_record(truth)))
    for band in BANDS:
        chart = Chart(truth, band, problem.length_unit_m)
        mapping = np.linalg.lstsq(wide.vectors, chart.vectors, rcond=None)[0]
        j = jw@mapping
        checks, gf, jf = qualification(evaluator, chart, obs, g, j, case == CASES[0])
        path = folder/'rows'/f'{case}__{catalog}__M{band}.json'
        record = dict(case=case, catalog=catalog, M=band, qualification=checks, probes=[], estimates=[], radius_checks=[])
        write(path, record)
        if not checks['passed']:
            print('UNQUALIFIED', case, catalog, band, flush=True)
            continue
        origins = {(n, p):(gg, jj) for n, p, gg, jj in groups(g, j, obs)}
        estimates = {}
        for key, (gg, jj) in origins.items():
            s, weakest = spectrum(jj)
            jr = normalized(jf[:, :key[0]], obs[:key[0]], key[1])
            estimates[key] = dict(frequencies=key[0], paired=key[1], sigma_min=float(s[-1]),
                jacobian_error_operator=float(np.linalg.norm(jj-jr, 2)), L_sample=0., max_tcc=0.,
                weakest=weakest, probes=0)
        rng = np.random.default_rng(20261003)
        directions = [rng.normal(size=chart.dimension) for _ in range(4)]
        directions += [estimates[(4, p)]['weakest'] for p in (True, False)]
        directions = [u/np.linalg.norm(u) for u in directions]
        for direction, u in enumerate(directions):
            for radius in (.01, .1, 1.):
                evaluated = {}
                for sign in (-1, 1):
                    q = sign*radius*u
                    try:
                        gp, jp = evaluator.evaluate(chart, q, obs)
                    except (ValueError, FloatingPointError) as exc:
                        record['probes'].append(dict(direction=direction, radius_mm=radius, sign=sign,
                                                      refused=str(exc)))
                        continue
                    for n, p, gg, jj in groups(gp, jp, obs):
                        g0, j0 = origins[(n, p)]
                        delta, remainder = gg-g0, gg-g0-j0@q
                        L = float(np.linalg.norm(jj-j0, 2)/radius)
                        ratio = float(np.linalg.norm(remainder)/max(np.linalg.norm(delta), 1e-300))
                        row = dict(direction=direction, radius_mm=radius, sign=sign, frequencies=n,
                            paired=p, L_from_origin=L, tcc=ratio, remainder_norm=np.linalg.norm(remainder),
                            data_change_norm=np.linalg.norm(delta), q_mm=q)
                        record['probes'].append(row)
                        e = estimates[(n, p)]
                        e['L_sample'] = max(e['L_sample'], L)
                        e['max_tcc'] = max(e['max_tcc'], ratio)
                        e['probes'] += 1
                        if sign == 1 and (n, p) in evaluated:
                            gm, jm = evaluated[(n, p)]
                            pair_L = float(np.linalg.norm(jj-jm, 2)/(2*radius))
                            pair_tcc = float(np.linalg.norm(gg-gm-jm@(2*q))/max(np.linalg.norm(gg-gm), 1e-300))
                            row.update(opposite_L=pair_L, opposite_tcc=pair_tcc)
                            e['L_sample'] = max(e['L_sample'], pair_L)
                            e['max_tcc'] = max(e['max_tcc'], pair_tcc)
                        evaluated[(n, p)] = (gg, jj)
                    if radius == 1. and sign == 1 and direction >= 4:
                        gr, jr = evaluator.evaluate(chart, q, obs, 1024)
                        check = dict(direction=direction, field_relative=relative(gp, gr),
                                     jacobian_relative=relative(jp, jr))
                        checks.setdefault('outer_probe_refinement', []).append(check)
                        checks['passed'] = bool(checks['passed'] and check['field_relative'] <= 1e-7
                                                and check['jacobian_relative'] <= 1e-5)
                write(path, record)
        for key, e in estimates.items():
            e['rho_sample_mm'] = e['sigma_min']/(4*e['L_sample']) if e['L_sample'] else None
            e['sigma_resolved'] = bool(e['sigma_min'] > 10*e['jacobian_error_operator'])
            # L is a finite sampled lower estimate of a supremum, not an upper bound.
            e['certified'] = False
            if e['rho_sample_mm'] and e['sigma_resolved']:
                n, p = key
                for factor in (.5, 1., 2.):
                    radius = min(1., factor*e['rho_sample_mm'])
                    q = radius*e['weakest']
                    try:
                        gp, _ = evaluator.evaluate(chart, q, obs[:n], jacobian=False)
                        delta = normalized(gp-g[:, :n], obs[:n], p)
                        rem = delta-origins[key][1]@q
                        floor = np.linalg.norm(normalized(gf[:, :n]-g[:, :n], obs[:n], p))
                        record['radius_checks'].append(dict(frequencies=n, paired=p, factor=factor,
                            radius_mm=radius, capped=radius < factor*e['rho_sample_mm'],
                            data_change_norm=np.linalg.norm(delta), origin_resolution_floor=floor,
                            resolved_against_origin_floor=bool(np.linalg.norm(delta) > 100*floor),
                            tcc=float(np.linalg.norm(rem)/max(np.linalg.norm(delta), 1e-300))))
                    except (ValueError, FloatingPointError) as exc:
                        record['radius_checks'].append(dict(frequencies=n, paired=p, factor=factor, refused=str(exc)))
            record['estimates'].append(e)
        record.update(complete=True, physics=evaluator.physics.receipt(), work_so_far=budget.record())
        write(path, record)
        print('ATLAS', case, catalog, band, 'rho', [round(e['rho_sample_mm'], 7) for e in record['estimates']], flush=True)


def run(folder, budget):
    for case in CASES:
        for catalog in ('real', 'damped'):
            atlas_case(folder, budget, case, catalog)


if __name__ == '__main__':
    execute('TR-001', run, 5400., 30000)
