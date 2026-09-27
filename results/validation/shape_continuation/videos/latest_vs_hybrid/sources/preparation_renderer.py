"""Saved six-scene SC-043 paths versus original hybrid, in the established atlas layout.

No inverse is rerun. Old traces are reused; missing diagnostic fields are
computed on the saved geometry only. New compact display caches are resumable.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast
from experiments.shape_continuation import atlas_video as av, render_videos as rv
from experiments.shape_continuation import spd_cases as sc, trajectory_atlas as ta
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.forward import solve, shape_jacobian, Work
from experiments.shape_continuation.geometry import FourierCurve, reparameterize

HERE = Path(__file__).resolve().parent
RESULTS = sc.ROOT / 'results/validation/shape_continuation'
CASES = ('wrong_circle', 'circle_to_star', 'circle_to_c', 'kite', 'peanut', 'hook')
NAMES = ('Circle', 'Star', 'C', 'Kite', 'Peanut', 'Hook')
NOISE, LOW = 1e-4, -6
# Extend the established strip to cover every current active band (up to M43).
av.BAND = av.SHOW = 48
av.TAIL = ((49, 64), (65, 128), (129, 192))
PHASES = ['Common start', *[f'Stage {i}: original frequency ladder' for i in range(1, 5)],
          'All-frequency release: M11', 'All-frequency release: M15', 'All-frequency release: M19',
          'SC-041 continuation', 'Initial K64 cleanup',
          'Latest policy: block 1', 'Latest policy: block 2', 'Latest policy: block 3', 'Final comparison']


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    sc.write(path, value)


def source_record(paths):
    return {str(p.relative_to(sc.ROOT)): sc.digest(p) for p in sorted(set(paths))}


def curve_for_step(step):
    if 'curve' in step:
        return ast.curve_from(step['curve'])
    with np.load(av.shot_path(step['shot'])) as data:
        return FourierCurve(data['coefficients'])


def collect(case, policy):
    old_index = RESULTS / 'SC-039-trajectory-atlas-data/manifest.json'
    new_index = RESULTS / 'SC-040-six-scene-pipeline/trajectories.json'
    old = next(t for t in read(old_index)['trajectories'] if t['id'] == 'A_hybrid/' + case)
    prefix = next(t for t in read(new_index)['trajectories'] if t['case'] == case)
    sources = [old_index, new_index, ast.source_folder(case) / 'truth.json',
               ast.source_folder(case) / 'observations.json']
    tracks = []
    for trajectory, latest in ((old, False), (prefix, True)):
        steps = []
        for i, row in enumerate(trajectory['steps']):
            s = dict(row)
            if i == 0:
                phase = 0
            elif s['stage'].startswith('stage_'):
                phase = int(s['stage'].split('_')[1])
            else:
                phase = {11: 5, 15: 6, 19: 7}[s['update_modes']]
            s.update(phase=phase, label=f"M{s['update_modes']} · K{s['curve_band']} · step {s['iteration']}")
            steps.append(s)
            sources.append(sc.ROOT / s['source'])
        tracks.append(steps)
    catalog = ast.catalog_only(case)
    all_k = [o.wavenumber for o in catalog]
    nodes = tracks[1][-1]['nodes']
    if case in ('circle_to_star', 'kite'):
        m = 25 if case == 'circle_to_star' else 22
        folder = RESULTS / f'SC-041-atlas-decisions/runs/{case}/M{m}'
        states = read(folder / 'accepted.json')['states']
        assert np.max(np.abs(curve_for_step(tracks[1][-1]).values(2048) -
                             ast.curve_from(states[0]['curve']).values(2048))) < 1e-11
        sources.extend([folder / 'accepted.json', folder / 'result.json'])
        for row in states:
            tracks[1].append(dict(curve=row['curve'], phase=8, update_modes=m, curve_band=192,
                active_wavenumbers=all_k, nodes=nodes, saved_loss=row['loss'],
                source=str((folder / 'accepted.json').relative_to(sc.ROOT)),
                iteration=row['iteration'], label=f"SC-041 · M{m} · K192 · step {row['iteration']}"))
    folder = RESULTS / 'SC-043-prospective-band/runs' / case / policy
    decision = read(folder / 'decisions.json')['rows'][0]
    initial = ast.curve_from(decision['curve_before_fit'])
    before = curve_for_step(tracks[1][-1])
    truncated = before.coefficients.copy()
    truncated[:before.band - 64] = 0
    truncated[before.band + 65:] = 0
    np.testing.assert_allclose(initial.coefficients, truncated, rtol=0, atol=0)
    tracks[1].append(dict(curve=decision['curve_before_fit'], phase=9,
        update_modes=decision['low'], curve_band=192, active_wavenumbers=all_k,
        nodes=nodes, saved_loss=None, iteration=0, label='K64 cleanup → K192 storage; saved intervention',
        source=str((folder / 'decisions.json').relative_to(sc.ROOT))))
    for row in read(folder / 'accepted.json')['states']:
        tracks[1].append(dict(curve=row['curve'], phase=9 + row['block'], update_modes=row['M'],
            curve_band=192, active_wavenumbers=all_k, nodes=nodes, saved_loss=row['loss'],
            source=str((folder / 'accepted.json').relative_to(sc.ROOT)), iteration=row['iteration'],
            label=f"block {row['block']} · M{row['M']} · K192 · step {row['iteration']}"))
    latest = read(folder / 'result.json')
    original_path = RESULTS / 'SC-029-atlas-strategies/runs/baseline' / case / 'none/result.json'
    original = read(original_path)
    sources.extend([original_path, folder / 'decisions.json', folder / 'accepted.json', folder / 'result.json'])
    for steps, final in zip(tracks, (original['final_curve'], latest['curve'])):
        np.testing.assert_allclose(curve_for_step(steps[-1]).values(2048),
                                   ast.curve_from(final).values(2048), rtol=0, atol=1e-12)
    np.testing.assert_allclose(curve_for_step(tracks[0][0]).values(2048),
                               curve_for_step(tracks[1][0]).values(2048), rtol=0, atol=1e-12)
    return tracks, (original['score']['symmetric_rms_mm'], latest['score']['rms_mm']), source_record(sources)


def diagnostic(curve, catalog, nodes, raw_path, work):
    observed = np.array([o.scattered for o in catalog])
    if raw_path is not None:
        return av.shot_atlas(raw_path.stem, observed, nodes, NOISE)
    out = dict(heat=np.zeros((av.SHOW + 1, len(catalog))), front=np.zeros(len(catalog), int),
               blocks=[], residuals=[], wavenumbers=np.array([o.wavenumber for o in catalog]),
               unit=sc.LENGTH, coefficients=curve.coefficients)
    h = av.ripple_basis(curve.coefficients, nodes, sc.LENGTH)
    for f, observation in enumerate(catalog):
        state = solve(curve, observation.wavenumber, ac.contrast(), observation.acquisition, nodes, work=work)
        a = av.stacked(shape_jacobian(state, h, work=work)) / np.linalg.norm(observed[f])
        r = av.stacked(state.prediction - observed[f]) / np.linalg.norm(observed[f])
        amplitude = av.horizon_mm(observation.wavenumber, sc.LENGTH)
        d, sensitivity = av.removable(a, r, amplitude)
        out['heat'][:, f] = np.sqrt(d[:av.SHOW + 1])
        out['front'][f] = av.frontier(sensitivity, amplitude, NOISE)
        out['blocks'].append(a)
        out['residuals'].append(r)
    return out


def prepare_case(job):
    case, policy, output = job
    output = Path(output)
    started = time.perf_counter()
    tracks, expected, sources = collect(case, policy)
    catalog = ast.catalog_only(case)
    truth = ast.curve_from(read(ast.source_folder(case) / 'truth.json'))
    truth_points = truth.values(16384)
    work = Work(max_forwards=4000, max_seconds=7200)
    memory = {}
    prepared = []
    checks = dict(max_saved_loss_absolute=0., max_log10_refinement=0., frontier_changes=0,
                  endpoint_rms_difference=0., cached_display_states=0)
    cache_dir = output / 'display_cache' / case
    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_hashes = {}
    for track in tracks:
        states = []
        for index, step in enumerate(track):
            curve = curve_for_step(step)
            key, grid, m = ta.shot_key(curve), step['nodes'], step['update_modes']
            raw_path = next((p / f'{key}.npz' for p in av.SHOT_DIRS if (p / f'{key}.npz').exists()), None)
            if raw_path is not None:
                raw_key = str(raw_path.relative_to(sc.ROOT))
                if raw_key not in raw_hashes:
                    raw_hashes[raw_key] = sc.digest(raw_path)
            active = [int(np.argmin(np.abs(np.array([o.wavenumber for o in catalog]) - k)))
                      for k in step['active_wavenumbers']]
            signature = dict(curve=key, nodes=grid, M=m, active=active, show=av.SHOW,
                noise=NOISE, low=LOW, renderer=sc.digest(Path(__file__)),
                atlas=sc.digest(Path(av.__file__)), observations=sources[str((ast.source_folder(case) / 'observations.json').relative_to(sc.ROOT))])
            cache_key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:24]
            cache_path = cache_dir / (cache_key + '.json')
            if cache_path.exists():
                data = read(cache_path)
                assert data['signature'] == signature
                checks['cached_display_states'] += 1
            else:
                atlases = []
                for n in (grid, 2 * grid):
                    identity = (key, n)
                    if identity not in memory:
                        memory[identity] = diagnostic(curve, catalog, n, raw_path, work)
                    atlases.append(memory[identity])
                base, fine = atlases
                joint, fine_joint = [av.joint(a, active, m, NOISE) for a in atlases]
                clip = lambda a: np.log10(np.maximum(a, 10. ** LOW))
                delta = max(float(np.max(abs(clip(base['heat']) - clip(fine['heat'])))),
                            float(np.max(abs(clip(joint['column']) - clip(fine_joint['column'])))))
                data = dict(signature=signature, heat=base['heat'], front=base['front'], **joint,
                    rms_mm=1000 * symmetric_rms_distance(curve, truth_points, sc.LENGTH),
                    spectrum=av.position_spectrum(curve.coefficients, sc.LENGTH * 1000),
                    refinement_log10=delta,
                    frontier_changes=int(np.sum(base['front'] != fine['front'])) + int(joint['front_joint'] != fine_joint['front_joint']))
                write(cache_path, data)
            loss_difference = (abs(data['misfit'] ** 2 / 2 - step['saved_loss'])
                               if step['saved_loss'] is not None else 0.)
            assert step['saved_loss'] is None or loss_difference <= 1e-8 * step['saved_loss'] + 5e-16, (case, index, loss_difference)
            checks['max_saved_loss_absolute'] = max(checks['max_saved_loss_absolute'], loss_difference)
            checks['max_log10_refinement'] = max(checks['max_log10_refinement'], data['refinement_log10'])
            checks['frontier_changes'] += data['frontier_changes']
            z = curve.values(2048) * sc.LENGTH * 1000
            states.append(dict(data, phase=step['phase'], label=step['label'], active=active, M=m,
                K=step['curve_band'], stage=step['phase'], iteration=step['iteration'],
                x=z.real, y=z.imag, source=step['source'], shot=key, saved_loss=step['saved_loss']))
        prepared.append(states)
        difference = abs(states[-1]['rms_mm'] - expected[len(prepared) - 1])
        assert difference <= 1e-9 * max(expected[len(prepared) - 1], 1e-3), (case, difference)
        checks['endpoint_rms_difference'] = max(checks['endpoint_rms_difference'], difference)
    fitted, fit_error = reparameterize(truth, 192, tolerance=1e-3)
    z = truth.values(2048) * sc.LENGTH * 1000
    result = dict(case=case, policy=policy, tracks=prepared, expected_rms_mm=expected, checks=checks,
        sources=sources, raw_shots=raw_hashes, diagnostic_work=work.summary(),
        seconds=time.perf_counter() - started, target_x=z.real, target_y=z.imag,
        target_spectrum=av.position_spectrum(fitted.coefficients, sc.LENGTH * 1000),
        target_parameter_refit_error=fit_error)
    write(output / 'prepared' / (case + '.json'), result)
    return dict(case=case, checks=checks, diagnostic_work=work.summary(), seconds=result['seconds'])


def timeline(tracks):
    frames, held = [], [0, 0]
    for phase in range(13):
        rows = [[i for i, s in enumerate(t) if s['phase'] == phase] for t in tracks]
        seconds = 1.5 if phase == 0 else 2 if phase == 9 else 3
        count = max(int(seconds * rv.FPS), *[len(r) for r in rows])
        for i in range(count):
            for k, members in enumerate(rows):
                if members:
                    held[k] = members[round(i * (len(members) - 1) / max(1, count - 1))]
            frames.append((phase, *held))
    frames += [(13, len(tracks[0]) - 1, len(tracks[1]) - 1)] * (5 * rv.FPS)
    for k, track in enumerate(tracks):
        assert {f[k + 1] for f in frames} == set(range(len(track)))
    return frames


def render_case(case, policy, output):
    data = read(output / 'prepared' / (case + '.json'))
    tracks = data['tracks']
    number = CASES.index(case) + 1
    title = NAMES[number - 1]
    fig = plt.figure(figsize=(18, 11), dpi=100, facecolor=av.SURFACE)
    fig.text(.5, .975, f'{title} · latest six-scene results versus original hybrid',
             ha='center', fontsize=18, color=av.INK, weight='bold')
    heading = fig.text(.5, .943, '', ha='center', fontsize=12, color=av.INK)
    fig.text(.5, .018, 'Saved states; no interpolation or new fitting. Playback is not solve time. '
             'Later continuation uses more frequencies and work. Dashed = target, evaluation only.',
             ha='center', fontsize=9, color=av.MUTED)
    x = np.concatenate([np.array(data['target_x'])] + [s['x'] for t in tracks for s in t])
    y = np.concatenate([np.array(data['target_y'])] + [s['y'] for t in tracks for s in t])
    centre = ((x.max() + x.min()) / 2, (y.max() + y.min()) / 2)
    half = .57 * max(np.ptp(x), np.ptp(y))
    artists = []
    colors = ('#1baf7a', '#eb6834')
    labels = ('Original hybrid · K192', f'Latest · initial cleanup + {policy} release')
    for k, bottom in enumerate((.555, .105)):
        top = bottom + .29
        fig.text(.19, top + .061, labels[k], ha='center', fontsize=12, weight='bold', color=colors[k])
        detail = fig.text(.19, top + .035, '', ha='center', fontsize=9, color=av.MUTED)
        shape = fig.add_axes([.035, bottom, .30, .29])
        av.style(shape)
        shape.plot(np.r_[data['target_x'], data['target_x'][0]], np.r_[data['target_y'], data['target_y'][0]],
                   color=rv.TARGET, linestyle='--', linewidth=1.2)
        line, = shape.plot([], [], color=colors[k], linewidth=2)
        shape.set(xlim=(centre[0] - half, centre[0] + half), ylim=(centre[1] - half, centre[1] + half),
                  aspect='equal', xlabel='x from scene centre (mm)', ylabel='y (mm)')
        shape.grid(alpha=.15)
        rms = fig.text(.19, bottom - .052, '', ha='center', fontsize=11, color=av.INK)
        fig.text(.515, top + .055, 'Residual heatmap · ideal normal ripples', ha='center', fontsize=10, color=av.INK)
        readout = fig.text(.515, top + .034, '', ha='center', fontsize=8.5, color=av.MUTED)
        panel = av.Panel(fig, [.385, bottom, .31, .29], [.72, bottom, .072, .29],
                         [.72, top + .015, .072, .053], readout, low=LOW, noise=NOISE)
        artists.append((line, detail, rms, panel))
    fig.text(.757, .916, 'Shape harmonics', ha='center', fontsize=10, color=av.INK)
    bar = fig.add_axes([.825, .30, .012, .46])
    colorbar = fig.colorbar(plt.cm.ScalarMappable(cmap=av.CMAP, norm=plt.Normalize(LOW, 0)), cax=bar)
    colorbar.set_ticks([-6, -5, -4, -3, -2, -1, 0])
    colorbar.set_ticklabels(['1e-6', '1e-5', '1e-4', '1e-3', '0.01', '0.1', '1'])
    colorbar.ax.tick_params(labelsize=8, colors=av.MUTED)
    fig.text(.862, .80, 'How to read', fontsize=11, color=av.INK, weight='bold')
    guide = [
        'Amber: active frequencies\nand nominal update band M.',
        'First column: active\nfrequencies combined.',
        'Colour: capped QR score.\nA descriptive heuristic,\nnot finite-step improvement.',
        'White line: first crossing\nof an assumed 0.01% level.\nNot a recovery limit.',
        'Strip: Cartesian shape\nharmonics; dashed = target.\nUpper bars: orders 49–192.',
        'Original hybrid holds its\nendpoint during later stages.'
    ]
    for i, text in enumerate(guide):
        fig.text(.862, .75 - .10 * i, text, va='top', fontsize=9, color=av.MUTED, linespacing=1.4)

    def draw(frame):
        phase, *indices = frame
        heading.set_text(PHASES[phase])
        for k, index in enumerate(indices):
            s = tracks[k][index]
            line, detail, rms, panel = artists[k]
            line.set_data(np.r_[s['x'], s['x'][0]], np.r_[s['y'], s['y'][0]])
            held = 'held · ' if s['phase'] != phase and phase != 13 else ''
            detail.set_text(held + s['label'])
            rms.set_text(f"{'Final ' if phase == 13 else ''}RMS {s['rms_mm']:.4g} mm")
            values = dict(s, heat=np.array(s['heat']), front=np.array(s['front']),
                          column=np.array(s['column']), spectrum=tuple(np.array(v) for v in s['spectrum']))
            panel.draw(values, tuple(np.array(v) for v in data['target_spectrum']), colors[k], 'final' if phase == 13 else '')
    frames = timeline(tracks)
    stem = f'{number}_{title.lower()}'
    result = rv.encode(fig, output / (stem + '.mp4'), frames, draw)
    for label, frame in [('start', frames[0]), ('middle', frames[len(frames) // 2]), ('final', frames[-1])]:
        draw(frame)
        fig.savefig(output / 'frames' / f'{stem}_{label}.png', dpi=100, facecolor=av.SURFACE)
    plt.close(fig)
    result.update(case=case, policy=policy, states=[len(t) for t in tracks], expected_rms_mm=data['expected_rms_mm'],
                  checks=data['checks'], sources=data['sources'], raw_shots=data['raw_shots'],
                  diagnostic_work=data['diagnostic_work'], preparation_seconds=data['seconds'], timeline=frames)
    write(output / 'receipts' / (case + '.json'), result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', choices=('fixed', 'stagnation', 'atlas'), default='fixed')
    parser.add_argument('--cases', nargs='+', default=list(CASES), choices=CASES)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--render-only', action='store_true')
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    for folder in ('prepared', 'frames', 'receipts'):
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    if not args.render_only:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(prepare_case, (case, args.policy, str(args.output))): case for case in args.cases}
            for future in as_completed(futures):
                print('PREPARED', json.dumps(future.result()), flush=True)
    if not args.prepare_only:
        for case in args.cases:
            result = render_case(case, args.policy, args.output)
            print('RENDERED', case, result['frames'], result['expected_rms_mm'], flush=True)
        write(args.output / 'manifest.json', dict(policy=args.policy,
            renderer_sha256=sc.digest(Path(__file__)), atlas_sha256=sc.digest(Path(av.__file__)),
            new_inverse_fits=0, conventions=dict(heatmap='legacy descriptive capped QR score',
                display_level=NOISE, displayed_orders=av.SHOW, colour_floor=10. ** LOW),
            outputs={case: read(args.output / 'receipts' / (case + '.json')) for case in args.cases}))


if __name__ == '__main__':
    main()
