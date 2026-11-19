"""Truth-free exact-disk diagnostics at one real TG-002 frequency, outside the fitting path."""
import argparse
from time import perf_counter

import numpy as np
from scipy.ndimage import minimum_filter
from scipy.optimize import least_squares

from bem_inverse import mie_grid, mie_localize as mie
from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.policy import LocalizationRule
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.compare_clean_schedules import OUT, write_rows

DIR = OUT.parent/'real_disk_starts'
MM = scenes.LENGTH * 1000
RULE = LocalizationRule()
RMIN, RMAX = RULE.radius_min_m*1000, RULE.radius_max_m*1000
QMIN, QMAX = .02, 100.
CUT = 41   # k*sqrt(100)*75/50 + 30, rounded up
PARAMS = ['x_mm', 'y_mm', 'radius_mm', 'contrast']


def observation(case):
    row = campaign.row(case)
    obs = bem.observations(BASE, row, OUT)[0][0]
    assert obs.frequency_hz == .25e9 and np.isreal(obs.wavenumber)
    return obs


def folded(obs, centers, cut=CUT):
    acq = obs.acquisition
    p = mie_grid.products_recurrence(obs.wavenumber, centers, acq.sources, acq.receivers, cut)
    pos = p[:, :, cut:].copy()
    pos[:, :, 1:] += p[:, :, cut-1::-1]
    return acq.strength*pos


def sensors(obs):
    pts = np.vstack((obs.acquisition.sources, obs.acquisition.receivers))
    return np.unique(pts[:, 0]+1j*pts[:, 1])


def residual(obs, p):
    x, y, r, logq = p
    center = (x+1j*y)/MM
    if np.min(abs(sensors(obs)-center))*MM <= r:
        return np.full(2*len(obs.scattered), 1.e2)
    product = folded(obs, np.array([center]))[0]
    radial = mie.radial_coefficients(obs.wavenumber, np.exp(logq), np.array([r/MM]), np.arange(CUT+1))[0]
    v = (product@radial-obs.scattered)/np.linalg.norm(obs.scattered)
    return np.r_[v.real, v.imag]


def refine(obs, xyzq, *, wide=False):
    # Four disk coordinates only. This minimises the analytic map, without a BEM call.
    start = np.array(xyzq, float)
    start[3] = np.log(start[3])
    rlo, rhi, qlo, qhi = (1., 200., 1.e-10, 1000.) if wide else (RMIN, RMAX, QMIN, QMAX)
    lower = [-220., -220., rlo, np.log(qlo)]
    upper = [220., 220., rhi, np.log(qhi)]
    res = least_squares(lambda p: residual(obs, p), np.clip(start, lower, upper), bounds=(lower, upper),
                        x_scale=[40, 40, 30, 1], ftol=1e-12, xtol=1e-11, gtol=1e-11, max_nfev=240)
    return dict(zip(PARAMS, [*res.x[:3], np.exp(res.x[3])]), loss=res.cost, nfev=res.nfev, status=res.status)


def grid(cases, obs, radii, etas, centers, *, cut=CUT):
    """Share predictions across cases. Retain the best centre for each radius and contrast."""
    k = obs[0].wavenumber
    shape = (len(etas), len(radii))
    radius, eta = np.broadcast_arrays(radii[None, :], etas[:, None])
    coef = mie.radial_coefficients(k, eta.reshape(-1, 1), radius.ravel()/MM, np.arange(cut+1))
    data = np.array([o.scattered for o in obs])
    data_norm2 = np.sum(abs(data)**2, axis=1)
    for o in obs:
        assert o.wavenumber == k and o.acquisition.strength == obs[0].acquisition.strength
        np.testing.assert_array_equal(o.acquisition.sources, obs[0].acquisition.sources)
        np.testing.assert_array_equal(o.acquisition.receivers, obs[0].acquisition.receivers)
    best = np.full((len(coef), len(cases)), np.inf)
    i_best = np.zeros(best.shape, dtype=int)
    sensor = sensors(obs[0])
    for start in range(0, len(centers), 16):
        c = centers[start:start+16]
        prop = folded(obs[0], c/MM, cut)
        pred = (coef @ prop.transpose(0, 2, 1)).reshape(-1, data.shape[1])
        norm = np.einsum('ij,ij->i', pred.conj(), pred).real
        loss = .5 + (.5*norm[:, None] - (pred@data.conj().T).real)/data_norm2
        loss = loss.reshape(len(c), len(coef), len(cases))
        clearance = np.min(abs(c[:, None]/MM - sensor[None, :]), axis=1)*MM
        loss = np.where((clearance[:, None] > radius.ravel()+1.e-9*MM)[..., None], loss, np.inf)
        idx = loss.argmin(axis=0)
        mins = np.take_along_axis(loss, idx[None, :, :], axis=0)[0]
        i_best = np.where(mins < best, idx + start, i_best)
        best = np.minimum(best, mins)
    return np.maximum(best.T.reshape((-1,)+shape), 0), i_best.T.reshape((-1,)+shape)


def score(case, best):
    truth = curve_region(curve_from(read(campaign.ROOT/campaign.row(case)['truth'])))
    true_q = float(read(BASE.folder()/case/'score.json')['contrast_true'])
    t = truth.centroid
    r = np.sqrt(truth.area/np.pi)*1000
    return dict(true_radius_mm=r, true_contrast=true_q, true_x_mm=t.x*1000, true_y_mm=t.y*1000,
                center_error_mm=abs(complex(best['x_mm']-t.x*1000, best['y_mm']-t.y*1000)),
                radius_error_pct=100*(best['radius_mm']/r-1), contrast_error_pct=100*(best['contrast']/true_q-1))


def joint(cases, *, crosscheck=False):
    obs = [observation(c) for c in cases]
    started = perf_counter()
    radii = np.arange(RMIN, RMAX+.001, 2.)
    etas = np.geomspace(QMIN, QMAX, 105)
    axis = np.arange(-220., 221., 8.)
    output = DIR
    if crosscheck:
        # A separately sampled map checks sensitivity to narrow resonant troughs.
        axis = np.arange(-220., 221., 10.)
        radii = np.linspace(RMIN, RMAX, 47)
        etas = np.geomspace(QMIN, QMAX, 159)
        output = DIR/'mesh_check'
    centers = (axis[:, None]+1j*axis).ravel()
    maps, ix = grid(cases, obs, radii, etas, centers)
    grid_seconds = perf_counter()-started
    starts, all_minima = [], []
    for case, o, m, ids in zip(cases, obs, maps, ix):
        t = perf_counter()
        dips = np.argwhere(m == minimum_filter(m, size=3, mode='nearest'))
        # Refine the best sampled minima, including separate resonant branches.
        sorted_dips = sorted(dips, key=lambda ij: m[tuple(ij)])[:18]
        minima = []
        for i, j in sorted_dips:
            c = centers[ids[i, j]]
            seed = [c.real, c.imag, radii[j], etas[i]]
            refined = refine(o, seed)
            minima.append(refined)
            all_minima.append(dict(case=case, grid_loss=m[i,j], seed=seed, **refined))
        winner = min(minima, key=lambda v: v['loss'])
        elapsed = perf_counter()-t
        row = dict(case=case, data_sha256=digest(campaign.ROOT/campaign.row(case)['data']), **winner,
                   refinement_seconds=elapsed, refinements=len(minima))
        starts.append(row)
    # The start file uses observations alone. Only after selection open the truths.
    output.mkdir(parents=True, exist_ok=True)
    write(output/'joint_starts.json', dict(starts=starts, grid_seconds=grid_seconds, seconds=perf_counter()-started,
          centers=len(centers), radii=len(radii), contrasts=len(etas), grid_templates=len(centers)*len(radii)*len(etas)))
    write(output/'joint_minima.json', all_minima)
    write_rows(output/'joint_scores.csv', [dict(**v, **score(v['case'],v)) for v in starts])


def fixed(cases):
    # Same real-data objective, geometry mesh, cutoff, 12 coordinate refinements and bounds as localize().
    # Hold the actual weak estimate unchanged, exactly as the maintained localizer holds problem.contrast.
    axis = np.arange(RULE.center_min_m, RULE.center_max_m+.0001, RULE.center_step_m)
    world_centers = (axis[:, None]+1j*axis).ravel()
    centers = (world_centers-scenes.CENTER)*1000
    radii_m = np.arange(RULE.radius_min_m, RULE.radius_max_m+.0001, RULE.radius_step_m)
    observations = [observation(case) for case in cases]
    weak = np.array([read(BASE.folder()/case/'fit.json')['contrast_start']['start_contrast'] for case in cases])
    cutoffs = np.ceil(observations[0].wavenumber*np.sqrt(np.maximum(weak,1))*radii_m.max()/scenes.LENGTH
                      +RULE.cutoff_padding).astype(int)
    started = perf_counter()
    grid_seconds, num_templates = 0., 0
    rows = {}
    for cut in np.unique(cutoffs):
        group = np.flatnonzero(cutoffs==cut)
        distinct = np.unique(weak[group])
        clock = perf_counter()
        losses, indices = grid([cases[i] for i in group], [observations[i] for i in group],
                               radii_m*1000, distinct, centers, cut=cut)
        grid_seconds += perf_counter()-clock
        num_templates += len(centers)*len(radii_m)*len(distinct)
        for k, i in enumerate(group):
            o, q, case = observations[i], weak[i], cases[i]
            qi = np.flatnonzero(distinct==q)[0]
            j = losses[k,qi].argmin()
            c = world_centers[indices[k,qi,j]]
            p = np.array([c.real, c.imag, radii_m[j]])
            steps = np.array(RULE.refinement_steps_m)
            clock = perf_counter()

            def loss(x):
                if not (RULE.radius_min_m <= x[2] <= RULE.radius_max_m and min(x[:2]-x[2]) >= .2
                        and max(x[:2]+x[2]) <= .8):
                    return np.inf
                center = (complex(*x[:2])-scenes.CENTER)/scenes.LENGTH
                return float(mie.landscape([o], q, [center], [x[2]/scenes.LENGTH], cutoff=cut)[0,0])

            value = loss(p)
            for _ in range(RULE.refinement_iterations):
                neigh = [p+sign*delta for delta in np.diag(steps) for sign in (-1,1)]
                vals = [loss(x) for x in neigh]
                n = int(np.argmin(vals))
                if vals[n] < value:
                    p, value = neigh[n], vals[n]
                else:
                    steps /= 2
            delta_mm = (complex(*p[:2])-scenes.CENTER)*1000
            best = dict(zip(PARAMS, [delta_mm.real,delta_mm.imag,p[2]*1000,q]), loss=value)
            rows[case] = dict(case=case, **best, cutoff=cut, refinement_seconds=perf_counter()-clock)
    elapsed = perf_counter()-started
    DIR.mkdir(exist_ok=True, parents=True)
    write_rows(DIR/'fixed_weak_scores.csv', [dict(**rows[c], **score(c, rows[c])) for c in cases])
    write(DIR/'fixed_cost.json', dict(grid_seconds=grid_seconds, total_seconds=elapsed,
                                      grid_per_case=len(centers)*len(radii_m), grid_templates_shared=num_templates,
                                      coordinate_iterations=RULE.refinement_iterations))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['joint','fixed','crosscheck'])
    args = parser.parse_args()
    if args.mode == 'fixed':
        fixed(scenes.CASES)
    else:
        joint(scenes.CASES, crosscheck=args.mode == 'crosscheck')
