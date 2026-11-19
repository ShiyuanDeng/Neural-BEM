"""Plot disk-only loss slices for the actual 24 paired TG-002 measurements."""
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.lines import Line2D
from scipy.ndimage import label
import numpy as np

from bem_inverse import mie_localize as mie
from bem_inverse.io import curve_from, read
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.compare_clean_schedules import OUT, stage_settings, write_rows
from experiments.comparison.trace_slider_refusals import ACTIVITY

MM = scenes.LENGTH*1000
CASES = ['circle__c4', 'circle__c13.3']


def disk_losses(obs_sets, centers, radii_mm, etas):
    """Use order symmetry to evaluate positive and negative terms together."""
    radii = radii_mm / MM
    radius_mesh, eta_mesh = np.meshgrid(radii, etas)
    output = np.empty((len(obs_sets), len(centers), len(obs_sets[0]), len(etas), len(radii)))
    for f, observations in enumerate(zip(*obs_sets)):
        first = observations[0]
        k = first.wavenumber
        geom = first.acquisition
        for obs in observations:
            assert k == obs.wavenumber and geom.strength == obs.acquisition.strength
            assert np.array_equal(geom.sources, obs.acquisition.sources)
            assert np.array_equal(geom.receivers, obs.acquisition.receivers)
        cut = int(np.ceil(abs(k)*np.sqrt(etas.max())*radii.max()+30))
        modes = np.arange(-cut, cut+1)
        products = mie.geometric_products(k, centers, geom.sources, geom.receivers, modes) * geom.strength
        products = products[:, :, cut:].copy() + np.concatenate(
            (np.zeros_like(products[:, :, :1]), products[:, :, cut-1::-1]), axis=2)
        radial = mie.radial_coefficients(k, eta_mesh.reshape(-1, 1), radius_mesh.ravel(), np.arange(cut+1))
        for center, product in enumerate(products):
            pred = radial @ product.T
            for case, obs in enumerate(observations):
                loss = .5*np.linalg.norm(pred-obs.scattered, axis=1)**2/np.linalg.norm(obs.scattered)**2
                output[case, center, f] = loss.reshape(eta_mesh.shape)
    return output


def connecting_loss(field, start, target):
    """Smallest sampled loss level at which start and target share an eight-neighbour component."""
    levels = np.unique(field)
    low, high = 0, len(levels)-1
    while low < high:
        mid = (low+high)//2
        components, _ = label(field <= levels[mid], structure=np.ones((3, 3)))
        if components[start] and components[start] == components[target]:
            high = mid
        else:
            low = mid+1
    return levels[low]


def main():
    with (OUT/'original_area_contrast.csv').open() as stream:
        records = list(csv.DictReader(stream))
    inputs = [campaign.row(case) for case in CASES]
    fits = [read(BASE.folder()/case/'fit.json') for case in CASES]
    catalogs = [bem.observations(BASE, row, OUT)[0] for row in inputs]
    start = curve_from(read(campaign.ROOT/inputs[0]['initial']))
    truth = curve_from(read(campaign.ROOT/inputs[0]['truth']))
    centers = [start.coefficients[start.band], truth.coefficients[truth.band]]
    radii = np.r_[np.arange(2.5, 25, 2.5), np.arange(25., 106., 1.25), np.arange(107.5, 141, 2.5)]
    etas = np.unique(np.r_[np.linspace(.05, 1., 16), np.geomspace(1.05, 17, 90),
                           np.geomspace(18, 30, 13), 4., 13.3,
                           [s['contrast_start']['start_contrast'] for s in fits]])
    losses = disk_losses(catalogs, centers, radii, etas)
    hz = [o.frequency_hz for o in catalogs[0]]
    settings = stage_settings(fits[0]['decisions'])
    stage_keys = ['ladder_1_real', 'ladder_2_real', 'ladder_3_real', 'ladder_4_real', 'full_1_M11']
    freq_sets = [[.25e9]] + [settings[key]['frequencies_hz'] for key in stage_keys]
    groups = np.stack([losses[:, :, [hz.index(f) for f in fs]].mean(axis=2) for fs in freq_sets], axis=2)
    # Check both the absolute normalization and the independently generated sealed observations.
    points, summary = [], []
    for case_idx, fit in enumerate(fits):
        case = CASES[case_idx]
        q = float(case.split('__c')[1])
        at_truth = groups[case_idx, 1, :, etas == q, :][:, :, radii == 50]
        assert np.max(at_truth) < 1e-12
        saved_start = fit['stages'][0]['initial_loss']
        start_eta = fit['contrast_start']['start_contrast']
        measured_start = groups[case_idx, 0, 1, np.flatnonzero(etas == start_eta)[0], np.flatnonzero(radii == 65)[0]]
        assert np.isclose(measured_start, saved_start, rtol=2e-7)
        target_center_m = centers[1]*scenes.LENGTH
        for row in records:
            if row['case'] != case:
                continue
            number = int(row['number'])
            radius_mm = np.sqrt(float(row['area_mm2'])/np.pi)
            curve = start if number == 0 else curve_from(fit['stages'][number-1]['curve'])
            centroid = curve_region(curve).centroid
            center_m = complex(centroid.x, centroid.y)
            distances_mm = abs(curve.values(8192)*MM - center_m*1000)
            points.append(dict(case=case, number=number, stage=row['stage'], radius_mm=radius_mm,
                               eta=float(row['contrast']), centroid_from_true_mm=abs(center_m-target_center_m)*1000,
                               min_radius_from_centroid_mm=distances_mm.min(),
                               max_radius_from_centroid_mm=distances_mm.max()))
        for ci, center in enumerate(['start', 'truth']):
            for si, fs in enumerate(freq_sets):
                field = groups[case_idx, ci, si]
                # Restrict the weak-side comparison to disks at least as large as the prescribed start.
                weak = ((etas[:, None] > 1) & (etas[:, None] <= 2.5) &
                        (radii[None, :] >= 65) & (radii[None, :] <= 105))
                iy, ix = np.unravel_index(np.argmin(np.where(weak, field, np.inf)), field.shape)
                initial_idx = (np.flatnonzero(etas == start_eta)[0], np.flatnonzero(radii == 65)[0])
                target_idx = (np.flatnonzero(etas == q)[0], np.flatnonzero(radii == 50)[0])
                peak = connecting_loss(field, initial_idx, target_idx)
                stage_path = [p for p in points if p['case'] == case]
                entry = stage_path[max(0, si-1)]
                entry_idx = (abs(etas-entry['eta']).argmin(), abs(radii-entry['radius_mm']).argmin())
                entry_peak = connecting_loss(field, entry_idx, target_idx)
                summary.append(dict(minimum_connecting_loss=peak, rise_above_start=peak-field[initial_idx],
                                    loss_at_nearest_entry_disk=field[entry_idx], entry_connecting_loss=entry_peak,
                                    rise_above_entry=entry_peak-field[entry_idx], case=case, center=center, stage='warmup_025_real' if si==0 else stage_keys[si-1],
                                    frequencies_ghz='|'.join(str(f/1e9) for f in fs),
                                    loss_at_65mm_weak_start=field[etas == start_eta][:, radii == 65].item(),
                                    loss_at_50mm_true_eta=field[etas == q][:, radii == 50].item(),
                                    weak_region_min_loss=field[iy, ix], weak_region_radius_mm=radii[ix],
                                    weak_region_contrast=etas[iy]))
    target = OUT.parent/'circle_loss_slices'
    target.mkdir(exist_ok=True)
    np.savez_compressed(target/'loss.npz', loss=groups, radii_mm=radii, contrast=etas, centers=centers,
                        cases=CASES, stages=['warmup_025_real']+stage_keys)
    write_rows(target/'comparison.csv', summary)
    write_rows(target/'stage_path.csv', points)
    draw(groups, radii, etas, points)


def draw(groups, radii, etas, points):
    fig, axes = plt.subplots(4, 6, sharex=True, sharey=True, figsize=(13.3, 8.4), layout='constrained')
    cmap = LinearSegmentedColormap.from_list('loss', ['#125e4c', '#69ad96', '#e7efdf', '#f3d7af', '#b64d28', '#593021'])
    titles = ['0.25 GHz warm-up', '0.5 GHz', '+ 0.75 GHz', '+ 1 GHz', '+ 1.25 GHz', 'All 19 frequencies']
    for row, row_axes in enumerate(axes):
        case_idx, center_idx = divmod(row, 2)
        case = CASES[case_idx]
        eta = float(case.split('__c')[1])
        path = [p for p in points if p['case'] == case]
        start = path[0]
        for si, ax in enumerate(row_axes):
            field = groups[case_idx, center_idx, si]
            mesh = ax.pcolormesh(radii, etas, field, cmap=cmap, norm=LogNorm(1e-4, 3), shading='auto', rasterized=True)
            ax.contour(radii, etas, field, levels=[.003, .03, .15, .3, .5, 1], colors='#5e5048', alpha=.55, linewidths=.5)
            ax.plot(50, eta, marker='*', color='#fcfcfb', mec='black', ms=9, mew=.7)
            ax.plot(start['radius_mm'], start['eta'], marker='s', color='black', ms=4)
            if si:
                prefix = path[:si+1] if si<5 else path
                ax.plot([r['radius_mm'] for r in prefix], [r['eta'] for r in prefix], 'o-', c='#352d42',
                        mfc='white', lw=1, ms=3.2)
                ax.plot(start['radius_mm'], start['eta'], 'ks', ms=4)
            ax.set(yscale='log', ylim=(1.05, 17), xlim=(25, 105))
            if row == 0:
                ax.set_title(titles[si], fontsize=10)
            if row == 3:
                ax.set_xlabel('Radius (mm)')
            ax.set_yticks([1.1, 2, 4, 8, 13.3], labels=['1.1', '2', '4', '8', '13.3'])
            if si == 0:
                center = ['start centre', 'true centre'][center_idx]
                ax.set_ylabel(f'True contrast {eta:g}\n{center}\nDisk contrast')
    handles = [Line2D([], [], color='black', marker='s', ls='', label='Weak start'),
               Line2D([], [], color='#352d42', marker='o', mfc='white', label='Saved free-shape path (equal area)'),
               Line2D([], [], color='black', marker='*', mfc='white', ls='', label='True radius and contrast')]
    fig.legend(handles=handles, loc='outside lower center', ncol=3, frameon=False)
    fig.colorbar(mesh, ax=axes, shrink=.78, label='B5 loss on exact disks')
    fig.savefig(ACTIVITY/'figures/circle_stage_losses.png', dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
