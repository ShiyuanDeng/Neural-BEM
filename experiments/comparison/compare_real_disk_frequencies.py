"""Add one real frequency to the bounded exact-disk search on five TG-002 misses."""
from time import perf_counter

import numpy as np
from scipy.ndimage import minimum_filter
from scipy.optimize import least_squares

from bem_inverse import mie_localize as mie
from bem_inverse.io import read, write
from experiments.benchmark import campaign
from experiments.comparison import bem
from experiments.comparison.localize_clean_real_disks import (
    BASE, DIR, MM, OUT, PARAMS, QMAX, QMIN, RMAX, RMIN, folded, score, sensors, write_rows,
)

CASES = [shape+'__c13.3' for shape in ('peanut', 'asymmetric', 'c_shape', 'hook', 'aphex_twin')]
RESULT = DIR.parent/'real_disk_frequency_pairs'
GHZ = (.25, .375, .5)


def cutoff(obs):
    return int(np.ceil(obs.wavenumber*np.sqrt(QMAX)*RMAX/MM + 30))


def grid_terms(observations, radius, eta):
    first = observations[0]
    for obs in observations[1:]:
        assert obs.wavenumber == first.wavenumber and obs.acquisition.strength == first.acquisition.strength
        np.testing.assert_array_equal(obs.acquisition.sources, first.acquisition.sources)
        np.testing.assert_array_equal(obs.acquisition.receivers, first.acquisition.receivers)
    cut = cutoff(first)
    coeff = mie.radial_coefficients(first.wavenumber, eta[:, None], radius/MM, np.arange(cut+1))
    data = np.array([obs.scattered for obs in observations])
    return first, cut, coeff, data.conj().T, np.sum(abs(data)**2, axis=1)


def grid_loss(terms, centers):
    obs, cut, coeff, data_h, norm_data = terms
    prop = folded(obs, centers/MM, cut)
    pred = (coeff @ prop.transpose(0, 2, 1)).reshape(-1, data_h.shape[0])
    norm_pred = np.einsum('ij,ij->i', pred.conj(), pred).real
    losses = .5 + (.5*norm_pred[:, None] - (pred @ data_h).real)/norm_data
    return losses.reshape(len(centers), len(coeff), len(norm_data))


def search_grid(catalog, radii, etas, centers):
    radius, eta = np.broadcast_arrays(radii[None, :], etas[:, None])
    terms = [grid_terms(group, radius.ravel(), eta.ravel()) for group in zip(*catalog)]
    points = np.unique(np.concatenate([sensors(t[0]) for t in terms]))
    best = np.full((2, radius.size, len(catalog)), np.inf)
    index = np.zeros_like(best, dtype=int)
    for i in range(0, len(centers), 16):
        c = centers[i:i+16]
        clearance = np.min(abs(c[:, None]/MM - points), axis=1)*MM
        valid = clearance[:, None] > radius.ravel()+1.e-9*MM
        usable = np.flatnonzero(valid.any(axis=1))
        if not usable.size:
            continue
        c, valid = c[usable], valid[usable]
        low = grid_loss(terms[0], c)
        for arm, other in enumerate(terms[1:]):
            pair_loss = .5*(low+grid_loss(other, c))
            if not np.isfinite(pair_loss[valid]).all():
                raise ArithmeticError('Nonfinite Mie prediction for a disk exterior to every sensor')
            loss = np.where(valid[..., None], pair_loss, np.inf)
            idx = loss.argmin(axis=0)
            mins = np.take_along_axis(loss, idx[None], axis=0)[0]
            index[arm] = np.where(mins < best[arm], i+usable[idx], index[arm])
            best[arm] = np.minimum(best[arm], mins)
    shape = (2, len(catalog), len(etas), len(radii))
    return best.transpose(0, 2, 1).reshape(shape), index.transpose(0, 2, 1).reshape(shape)


def refine(pair, start):
    low = [-220., -220., RMIN, np.log(QMIN)]
    high = [220., 220., RMAX, np.log(QMAX)]
    orders = [np.arange(cutoff(o)+1) for o in pair]
    sensor = np.unique(np.concatenate([sensors(o) for o in pair]))

    def residual(p):
        center = complex(*p[:2])/MM
        if np.min(abs(center-sensor))*MM <= p[2]+1.e-9*MM:
            return np.full(2*sum(o.scattered.size for o in pair), 100.)
        values = []
        for obs, n in zip(pair, orders):
            coeff = mie.radial_coefficients(obs.wavenumber, np.exp(p[3]), [p[2]/MM], n)[0]
            pred = folded(obs, np.array([center]), n[-1])[0] @ coeff
            values.append((pred-obs.scattered)/(np.sqrt(2)*np.linalg.norm(obs.scattered)))
        v = np.concatenate(values)
        return np.r_[v.real, v.imag]

    p = [*start[:3], np.log(start[3])]
    fit = least_squares(residual, p, bounds=(low, high), x_scale=[40, 40, 30, 1],
                        ftol=1.e-12, xtol=1.e-11, gtol=1.e-11, max_nfev=240)
    return dict(zip(PARAMS, [*fit.x[:3], np.exp(fit.x[3])]), loss=fit.cost, status=fit.status)


def scan(catalog, *, counts, folder, max_dips=18, extra_seeds=None):
    n_r, n_q, n_xy = counts
    radii = np.linspace(RMIN, RMAX, n_r)
    etas = np.geomspace(QMIN, QMAX, n_q)
    axis = np.linspace(-220., 220., n_xy)
    centers = (axis[:, None]+1j*axis).ravel()
    started = perf_counter()
    maps, indices = search_grid(catalog, radii, etas, centers)
    grid_seconds = perf_counter()-started
    starts, all_minima = [], []
    for arm, ghz in enumerate(GHZ[1:]):
        for k, case in enumerate(CASES):
            obs = catalog[k]
            m = maps[arm, k]
            dips = np.argwhere(m == minimum_filter(m, size=3, mode='nearest'))
            minima = []
            for i, j in sorted(dips, key=lambda ij: m[tuple(ij)])[:max_dips]:
                c = centers[indices[arm, k, i, j]]
                seed = [c.real, c.imag, radii[j], etas[i]]
                fit = refine([obs[0], obs[arm+1]], seed)
                minima.append(fit)
                all_minima.append(dict(case=case, added_ghz=ghz, seed=seed, grid_loss=m[i, j], **fit))
            for row in (extra_seeds or {}).get(case, []):
                seed = [row[key] for key in PARAMS]
                fit = refine([obs[0], obs[arm+1]], seed)
                minima.append(fit)
                all_minima.append(dict(case=case, added_ghz=ghz, seed=seed, source='previous real-data minimum', **fit))
            starts.append(dict(case=case, added_ghz=ghz, **min(minima, key=lambda v: v['loss'])))
    write(folder/'starts.json', dict(starts=starts, centers=len(centers), radii=len(radii), contrasts=len(etas),
                                    grid_seconds=grid_seconds, seconds=perf_counter()-started))
    write(folder/'minima.json', all_minima)
    return starts


def direct(obs, row):
    acq = obs.acquisition
    center = complex(row['x_mm'], row['y_mm'])/MM
    return acq.strength*mie.paired_data(obs.wavenumber, row['contrast'], [center], [row['radius_mm']/MM],
                                        acq.sources, acq.receivers, cutoff(obs))[0, 0]


def ring_power(v, obs):
    # Orders of the observed paired-ring samples as both antennas rotate.
    m = np.abs(np.fft.fftfreq(len(v))*len(v)).round().astype(int)
    power = abs(np.fft.fft(v, norm='ortho'))**2/np.vdot(obs, obs).real
    return [float(power[group].sum()) for group in (m == 0, m == 1, m == 2, m >= 3)]


def diagnose(catalog, starts, mesh_winners):
    old = {s['case']: s for s in read(DIR/'joint_starts.json')['starts']}
    branches = {s['case']: s for s in read(DIR/'disk_checks.json')}
    rows, spectra = [], []
    for case, observations in zip(CASES, catalog):
        original = old[case]
        ref = score(case, original)
        equal = dict(zip(PARAMS, [ref['true_x_mm'], ref['true_y_mm'], ref['true_radius_mm'], ref['true_contrast']]))
        candidates = dict(original=original, competing=branches[case]['competitor'],
                          truth_seed_descent=branches[case]['truth_seed_check'], equal_area=equal)
        for i, start in enumerate(starts):
            if start['case'] != case:
                continue
            ghz = start['added_ghz']
            candidates[str(ghz)] = start
            mesh_losses = {f'{name}_loss': group[i]['loss'] for name, group in mesh_winners.items()}
            rows.append(dict(**start, **score(case, start), **mesh_losses))
        for name, disk in candidates.items():
            for ghz, o in zip(GHZ, observations):
                pred = direct(o, disk)
                bins = ring_power(pred-o.scattered, o.scattered)
                loss = .5*sum(bins)
                if name == 'original' and ghz == .25:
                    np.testing.assert_allclose(loss, disk['loss'], atol=1.e-12)
                spectra.append(dict(case=case, disk=name, frequency_ghz=ghz, loss=loss,
                                    measured_power_fraction=ring_power(o.scattered, o.scattered),
                                    residual_loss_by_order=[.5*x for x in bins],
                                    prediction_gap_to_original_relative=np.linalg.norm(pred-direct(o, original))
                                    /np.linalg.norm(o.scattered)))
            if name in ('0.375', '0.5'):
                losses = [row['loss'] for row in spectra[-3:] if row['frequency_ghz'] in (.25, float(name))]
                np.testing.assert_allclose(np.mean(losses), disk['loss'], atol=1.e-12)
    write_rows(RESULT/'scores.csv', rows)
    write(RESULT/'ring_diagnostics.json', spectra)


if __name__ == '__main__':
    catalog = [bem.observations(BASE, campaign.row(case), OUT)[0][:3] for case in CASES]
    for observations in catalog:
        np.testing.assert_array_equal([o.frequency_hz for o in observations], np.array(GHZ)*1.e9)
    primary = scan(catalog, counts=(31, 105, 56), folder=RESULT)
    check = scan(catalog, counts=(47, 159, 45), folder=RESULT/'mesh_check')
    single_minima = read(DIR/'joint_minima.json')
    seeds = {}
    for case in CASES:
        unique = {}
        for row in [*single_minima, *primary, *check]:
            if row['case'] == case:
                key = tuple(round(row[name], 2) for name in PARAMS)
                unique[key] = row
        seeds[case] = list(unique.values())
    dense = scan(catalog, counts=(61, 201, 57), folder=RESULT/'branch_check', max_dips=50, extra_seeds=seeds)
    meshes = dict(primary=primary, check=check, dense=dense)
    starts = [min(group, key=lambda row: row['loss']) for group in zip(*meshes.values())]
    write(RESULT/'selected_starts.json', starts)
    diagnose(catalog, starts, meshes)
