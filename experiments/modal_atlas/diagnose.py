"""MA-002b: why the frozen policy fails when the target is denser than the host.

Evaluation-only diagnosis on saved MA-002 states; nothing here feeds an inverse.

Part 1 (frontier). For the stage-1 start state of every attempt (the warm-up
endpoint) and the stage frequencies, the column norms of the paired Jacobian on
the orthonormal arclength harmonics p = 0..PMAX, the observable frontier (the
highest p whose column norm is within tau of the strongest, MA-001's
definition), the trace supports K_U + K_V, and the update band M the frozen
schedule released there.

Part 2 (horizon and poles, the pre-declared MA-002b). At one fixed state and
frequency (the contrast-4 C warm-up endpoint at the stage-1 frequency), the
per-harmonic linearization horizon (SC-016's 10% criterion, cosine directions)
at contrasts 0.5, 2, 4 and 13.3, together with the nearest scattering pole
k* of that state, its sensitivity dk*/d(eps) along each direction (finite
difference of the polished pole), and the two predictions: SC-016's smooth law
eps*(k) min(1, 2.05 s_p / max s) with eps*(k) = 0.112 k^-0.97, and the
single-pole law 0.1 |k - k*| / |dk*/d eps|.

Part 3 (localization landscape). SC-050's circle-localization objective on a
dense grid (centres every 4 mm over [0.28, 0.72]^2, radii 15-75 mm every 1 mm,
circles inside [0.2, 0.8]^2) from exact Mie data, against the circle SC-050's
9x9x3 search returned and the truth-equivalent circle (centroid, equal area;
evaluation only).

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.diagnose frontier
    PYTHONPATH=solvers:. python -m experiments.modal_atlas.diagnose horizon
Part 4 (resolution). The contrast-4 C numerical stop, one factor at a time: the
512/1024 and 1024/2048 field discrepancies of its stage-1 endpoint at the
failing frequency (0.75 GHz) at every contrast, with the nearest pole.

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.diagnose localization
    PYTHONPATH=solvers:. python -m experiments.modal_atlas.diagnose resolution
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import warnings

import numpy as np

from experiments.modal_atlas.contrast_screen import CONTRASTS, OUT, SCENES, tag

PMAX = 40
TAUS = (1e-1, 1e-2, 1e-3)
AMPLITUDES = np.geomspace(1e-5, 0.3, 28)   # RMS normal displacement, package units (5 cm)


def read(path):
    return json.loads(path.read_text())


def stage_start(contrast, scene):
    """Warm-up endpoint (the curve stage 1 starts from) and the configured stages."""
    from experiments.shape_continuation import atlas_strategy_tests as ast
    folder = OUT / 'runs' / tag(contrast) / scene
    warm = read(folder / 'warmup_025.json')
    return ast.curve_from(warm['curve']), read(folder / 'configuration.json')['stages']


def support(E, eps):
    n = np.arange(-(E.shape[1] // 2), E.shape[1] // 2 + 1)
    profile = np.sqrt((np.abs(E) ** 2).sum(axis=0))
    return int(np.abs(n[profile >= eps * profile.max()]).max())


def column_profile(curve, wavenumber, contrast, acquisition, nodes=512):
    """Paired-Jacobian column norms per harmonic p (cos/sin combined) and trace supports."""
    from experiments.shape_continuation.atlas import orthonormal_normal_basis
    from experiments.shape_continuation.forward import PointSourceAcquisition, shape_jacobian, solve
    from experiments.shape_continuation.geometry import arclength_angles
    from experiments.shape_continuation import trajectory_atlas as ta
    state = solve(curve, wavenumber, contrast, acquisition, nodes)
    basis = orthonormal_normal_basis(state.curve, PMAX)
    J = shape_jacobian(state, basis)
    norms = np.linalg.norm(J, axis=0)
    per_p = np.r_[norms[0], np.sqrt(norms[1::2] ** 2 + norms[2::2] ** 2)]
    full = PointSourceAcquisition(acquisition.sources, acquisition.receivers, acquisition.strength, paired=False)
    fstate = solve(curve, wavenumber, contrast, full, nodes)
    reciprocal, _ = ta.reciprocal_traces(fstate)
    u, v = fstate.traces[:nodes], reciprocal[:nodes]
    angles, length = arclength_angles(fstate.curve)
    w = fstate.curve.arc_length_weights
    n = np.arange(-80, 81)
    U = (np.exp(-1j * np.outer(n, angles)) @ (w[:, None] * u)).T / length
    V = (np.exp(-1j * np.outer(n, angles)) @ (w[:, None] * v)).T / length
    out = dict(k=float(wavenumber), column_norm=per_p.tolist(),
               relative_data_sensitivity=(per_p / np.linalg.norm(state.prediction)).tolist())
    for tau in TAUS:
        out[f'frontier_{tau:g}'] = int(np.nonzero(per_p >= tau * per_p.max())[0].max())
    for eps in (1e-1, 1e-2):
        out[f'K_U+K_V_{eps:g}'] = support(U, eps) + support(V, eps)
    return out


def _frontier_job(args):
    contrast, scene, eval_contrast = args
    from experiments.shape_continuation import atlas_strategy_tests as ast
    warnings.simplefilter('ignore')
    curve, stages = stage_start(contrast, scene)
    catalog = {round(o.wavenumber, 9): o for o in ast.catalog_only('circle_to_c')}
    rows = []
    for stage in stages[1:4]:                       # stage_1..stage_3: the prefix where failures began
        k = stage['wavenumbers'][-1]
        obs = catalog[round(k, 9)]
        row = column_profile(curve, obs.wavenumber, eval_contrast, obs.acquisition)
        row.update(stage=stage['label'], released_M=stage['update_modes'],
                   exterior_rule_M=int(np.floor(3 * obs.wavenumber)))
        rows.append(row)
    return dict(attempt=f'{tag(contrast)}/{scene}', evaluated_contrast=eval_contrast, rows=rows)


def frontier(workers):
    jobs = [(c, s, c) for c in CONTRASTS for s in SCENES]
    # One-factor control: the contrast-4 C start state evaluated at every contrast.
    jobs += [(4.0, 'development_c', c) for c in CONTRASTS if c != 4.0]
    with ProcessPoolExecutor(workers) as pool:
        result = list(pool.map(_frontier_job, jobs))
    (OUT / 'diagnosis_frontier.json').write_text(json.dumps(result, indent=1))
    for r in result:
        print(r['attempt'], 'at', r['evaluated_contrast'],
              [(x['stage'], x['released_M'], x['exterior_rule_M'], x['frontier_0.01'], x['K_U+K_V_0.1'])
               for x in r['rows']], flush=True)


def _horizon_job(contrast):
    from experiments.shape_continuation import atlas_strategy_tests as ast
    from experiments.shape_continuation.horizon import linearization_error, perturbed, default_storage_band
    from experiments.modal_atlas import poles as P
    warnings.simplefilter('ignore')
    curve, stages = stage_start(4.0, 'development_c')
    k = stages[1]['wavenumbers'][-1]
    obs = next(o for o in ast.catalog_only('circle_to_c') if abs(o.wavenumber - k) < 1e-9)
    band = 8
    directions = {f'cos{p}': np.eye(2 * band + 1)[0 if p == 0 else 2 * p - 1] for p in range(band + 1)}
    probes, state, jacobian = linearization_error(curve, k, contrast, obs.acquisition, 512, band, directions,
                                                  AMPLITUDES)
    perimeter = float(state.curve.perimeter)
    # Nearest pole of this state (Newton from just below k), qualified at 1024 nodes.
    pole = P.polish(curve.nodes(512), contrast, complex(k, -1e-3 * k))
    check = P.polish(curve.nodes(1024), contrast, pole.k, steps=8)
    rows = []
    storage = default_storage_band(curve, band)
    for probe, (label, direction) in zip(probes, directions.items()):
        delta = 1e-4
        moved = perturbed(curve, direction * delta * np.sqrt(perimeter), storage).shape
        shifted = P.polish(moved.nodes(512), contrast, pole.k, steps=12)
        slope = (shifted.k - pole.k) / delta          # dk*/d(eps), eps = RMS normal displacement
        rows.append(dict(direction=label, horizon=probe.horizon(), order=probe.order(),
                         column_norm=float(np.linalg.norm(jacobian @ direction)),
                         pole_slope_real=slope.real, pole_slope_imag=slope.imag,
                         failures=len(probe.failures)))
    return dict(contrast=contrast, k=k, pole_real=pole.k.real, pole_imag=pole.k.imag, quality=pole.quality,
                pole_sigma_ratio=pole.smallest_singular, pole_refined_shift=abs(check.k - pole.k) / abs(pole.k),
                data_norm=float(np.linalg.norm(state.prediction)), rows=rows)


def horizon(workers):
    with ProcessPoolExecutor(workers) as pool:
        result = list(pool.map(_horizon_job, CONTRASTS))
    for r in result:
        k, kstar = r['k'], complex(r['pole_real'], r['pole_imag'])
        s = np.array([x['column_norm'] for x in r['rows']])
        smooth = 0.112 * k ** -0.97 * np.minimum(1, 2.05 * s / s.max())
        for x, sm in zip(r['rows'], smooth):
            slope = abs(complex(x['pole_slope_real'], x['pole_slope_imag']))
            x['smooth_prediction'] = float(sm)
            x['pole_prediction'] = float(0.1 * abs(k - kstar) / slope) if slope > 0 else float('inf')
        print(r['contrast'], 'pole', kstar, 'Q %.1f' % r['quality'],
              [(x['direction'], '%.2e' % x['horizon'], '%.2e' % x['smooth_prediction'], '%.2e' % x['pole_prediction'])
               for x in r['rows']], flush=True)
    (OUT / 'diagnosis_horizon.json').write_text(json.dumps(result, indent=1))


def dense_grid():
    from experiments.shape_continuation import spd_cases as sc
    xs = np.arange(0.28, 0.7201, 0.004)
    radii_m = np.arange(0.015, 0.0751, 0.001)
    X, Y = np.meshgrid(xs, xs, indexing='ij')
    centers_m = (X + 1j * Y).ravel()
    inside = (((X.ravel()[:, None] - radii_m[None]) >= .2) & ((X.ravel()[:, None] + radii_m[None]) <= .8)
              & ((Y.ravel()[:, None] - radii_m[None]) >= .2) & ((Y.ravel()[:, None] + radii_m[None]) <= .8))
    return centers_m, radii_m, (centers_m - sc.CENTER) / sc.LENGTH, radii_m / sc.LENGTH, inside


def dense_landscape(observations, contrast):
    from experiments.modal_atlas import mie_localize as ml
    centers_m, radii_m, centers, radii, inside = dense_grid()
    L = np.concatenate([ml.landscape(observations, contrast, centers[i:i + 800], radii)
                        for i in range(0, len(centers), 800)])
    return centers_m, radii_m, np.where(inside, L, np.inf)


def localization(workers):
    from experiments.modal_atlas import mie_localize as ml
    from experiments.modal_atlas.contrast_screen import SC050, fitting_data
    from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
    warnings.simplefilter('ignore')
    out = {}
    for contrast in CONTRASTS:
        for scene in SCENES:
            catalog, _ = fitting_data(contrast, scene)
            centers_m, radii_m, L = dense_landscape(catalog[:3], contrast)
            i, j = np.unravel_index(np.argmin(L), L.shape)
            truth = ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'truth.json'))
            z = truth.values(4096)
            area = abs(0.5 * np.imag(np.sum(np.conj(z) * np.roll(z, -1))))
            cen, req = np.mean(z) * sc.LENGTH + sc.CENTER, np.sqrt(area / np.pi) * sc.LENGTH
            loc = read(OUT / 'runs' / tag(contrast) / scene / 'localization.json')
            eq = ml.landscape(catalog[:3], contrast, [(cen - sc.CENTER) / sc.LENGTH], [req / sc.LENGTH])[0, 0]
            out[f'{tag(contrast)}/{scene}'] = dict(
                dense_best=[centers_m[i].real, centers_m[i].imag, radii_m[j]], dense_loss=float(L[i, j]),
                sc050_localization=loc['parameters_m'], sc050_loss=loc['loss'],
                equivalent_circle=[cen.real, cen.imag, req], equivalent_loss=float(eq),
                dense_center_error_mm=float(abs(centers_m[i] - cen) * 1000),
                sc050_center_error_mm=float(abs(complex(*loc['parameters_m'][:2]) - cen) * 1000))
            print(tag(contrast), scene, out[f'{tag(contrast)}/{scene}'], flush=True)
    (OUT / 'diagnosis_localization.json').write_text(json.dumps(out, indent=1))


def resolution(workers):
    from experiments.shape_continuation import atlas_strategy_tests as ast
    from experiments.shape_continuation.forward import solve
    from experiments.modal_atlas import poles as P
    warnings.simplefilter('ignore')
    curve = ast.curve_from(read(OUT / 'runs/c4/development_c/stage_1.json')['curve'])
    obs = ast.catalog_only('circle_to_c')[4]
    rows = []
    for contrast in CONTRASTS:
        a, b, c = [solve(curve, obs.wavenumber, contrast, obs.acquisition, n).prediction for n in (512, 1024, 2048)]
        pole = P.polish(curve.nodes(512), contrast, complex(obs.wavenumber, -1e-3))
        physical = pole.k.imag < 0 and pole.k.real > 0
        rows.append(dict(contrast=contrast, k=float(obs.wavenumber),
                         discrepancy_512_1024=float(np.linalg.norm(a - b) / np.linalg.norm(b)),
                         discrepancy_1024_2048=float(np.linalg.norm(b - c) / np.linalg.norm(c)),
                         nearest_pole=[pole.k.real, pole.k.imag] if physical else None,
                         pole_quality=pole.quality if physical else None,
                         pole_relative_distance=abs(obs.wavenumber - pole.k) / abs(pole.k) if physical else None))
        print(rows[-1], flush=True)
    (OUT / 'diagnosis_resolution.json').write_text(json.dumps(dict(state='runs/c4/development_c/stage_1.json curve',
                                                                   gate=1e-7, rows=rows), indent=1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('part', choices=('frontier', 'horizon', 'localization', 'resolution'))
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    globals()[args.part](args.workers)
