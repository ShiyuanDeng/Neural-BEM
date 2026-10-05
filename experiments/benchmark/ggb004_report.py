"""GGB-004/005 saved-data reports and direct-boundary videos; no solver calls."""
import argparse
import json
from pathlib import Path

import numpy as np

from experiments.benchmark import ggb003_report as previous

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT/'results/validation/cleaned_interfaces/GGB-004'
COLORS = ('#2974b5', '#c5552c', '#2b8666')


def frequencies(result):
    values = result.get('frequencies_hz')
    if values is None and result.get('experiment_id') == 'GGB-004':
        values = [.5e9, .75e9, 1e9, 1.25e9]
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError('Receipt needs a nonempty list of positive finite fitted frequencies.')
    return values


def frequency_label(result):
    return ', '.join(f'{value*1e-9:.2f}' for value in frequencies(result))+' GHz'


def load(output):
    folder = output/'W'
    receipt, stream, endpoint = (folder/name for name in ('result.json', 'accepted.jsonl', 'endpoint.npz'))
    result = json.loads(receipt.read_text())
    if result.get('experiment_id') not in ('GGB-004', 'GGB-005'):
        raise ValueError('Expected a GGB-004 or GGB-005 receipt.')
    frequencies(result)
    track = previous.Track('W', result, sources=[receipt, stream])
    for row in previous.json_lines(stream, track.warnings):
        track.add(row, 'accepted.jsonl')
        state = track.states[-1]
        c = state['coefficients']
        band = len(c)//2
        other = c.copy()
        other[band:band+2] = 0
        if np.any(other != 0) or abs(c[band+1]) <= 0:
            raise ValueError('Restricted-stage stream contains a non-circular boundary.')
        geometry = np.array([c[band].real, c[band].imag, abs(c[band+1])])
        recorded = np.r_[row.get('centre_m', geometry[:2]), row.get('radius_m', geometry[2])]
        if not np.allclose(geometry, recorded, rtol=1e-12, atol=1e-12):
            raise ValueError('Recorded centre/radius disagrees with saved coefficients.')
        state.update(geometry=geometry, elapsed_fit_seconds=row.get('elapsed_fit_seconds'))
    if not track.states:
        raise ValueError('No saved accepted circle states.')
    if endpoint.exists():
        track.sources.append(endpoint)
        with np.load(endpoint) as data:
            if not np.array_equal(data['coefficients'], track.states[-1]['coefficients']):
                raise ValueError('Endpoint differs from the final accepted state.')
    elif result.get('status') == 'COMPLETE':
        raise ValueError('Complete receipt has no saved endpoint.')
    track.stream_used = True
    return track


def plot(track, edges):
    import matplotlib.pyplot as plt
    states, last = track.states, len(track.states)-1
    geometry = np.array([state['geometry'] for state in states])
    elapsed = np.array([s['elapsed_fit_seconds'] if previous.finite(s.get('elapsed_fit_seconds')) else np.nan for s in states])
    if not np.isfinite(elapsed).all() or np.any(np.diff(elapsed) < 0):
        raise ValueError('Each accepted state needs a finite monotone elapsed_fit_seconds.')
    loss = np.array([s['loss'] if previous.finite(s.get('loss')) else np.nan for s in states])
    fig = plt.figure(figsize=(12.8, 8), dpi=100, facecolor='#fcfcfb')
    fig.text(.065, .95, 'Case 8 | Translation and scaling only', fontsize=20, weight='bold')
    scope = ' fitted together' if len(frequencies(track.result)) > 1 else ' fitted'
    fig.text(.065, .905, f"{track.result['experiment_id']} | {frequency_label(track.result)}{scope} | Initial restricted stage", fontsize=11, color='#52514e')
    boundary = fig.add_axes([.065, .22, .43, .61])
    previous.setup_axis(boundary, edges, previous.limits([track], edges))
    boundary.plot(*previous.close_line(states[0]['z']), color='#aab1b7', ls='--', lw=1.2, label='Initial circle')
    boundary.plot([], [], color='#45515e', lw=1.5, label='Target cell boundary')
    line, = boundary.plot([], [], color='#ce542b', lw=2.4, label='Accepted circle')
    centre, = boundary.plot([], [], 'o', color='#ce542b', ms=4)
    boundary.legend(loc='upper right', fontsize=8, framealpha=.85)
    panels = [fig.add_axes([.59, bottom, .36, .16]) for bottom in (.66, .405, .15)]
    artists = []
    for axis, x, label in zip(panels[:2], (np.arange(len(states)), elapsed), ('Accepted update', 'Elapsed fit time (s)')):
        for column, color, name in zip(range(3), COLORS, ('Centre x', 'Centre y', 'Radius')):
            axis.plot(x, geometry[:, column], color='#e0e3e5', lw=1)
            artist, = axis.plot([], [], color=color, lw=1.8, label=name)
            artists.append((artist, x, geometry[:, column]))
        axis.set(xlabel=label, ylabel='Metres')
        axis.set_xlim(-.02*max(x[-1], 1), max(x[-1], 1)*1.02)
        axis.grid(alpha=.18)
        axis.tick_params(labelsize=8)
    panels[0].legend(loc='lower left', bbox_to_anchor=(0, 1.00), ncol=3, fontsize=8, frameon=False)
    panels[2].semilogy(np.arange(len(states)), loss, color='#e0e3e5', lw=1)
    loss_line, = panels[2].semilogy([], [], color='#ce542b', lw=1.8)
    artists.append((loss_line, np.arange(len(states)), loss))
    panels[2].set(xlabel='Accepted update', ylabel='Joint loss', xlim=(-.2, max(last, 1)+.2))
    panels[2].grid(alpha=.18)
    panels[2].tick_params(labelsize=8)
    status = fig.text(.065, .165, '', fontsize=11, va='top')
    ending = fig.text(.065, .088, '', fontsize=9, va='top', color='#52514e')
    fig.text(.065, .025, 'Direct boundary lines; target used only for display/scoring. Every saved state shown; playback is not solve time.', fontsize=9, color='#52514e')

    def draw(frame):
        index, stopped = frame
        state = states[index]
        line.set_data(*previous.close_line(state['z']))
        centre.set_data([geometry[index, 0]], [geometry[index, 1]])
        for artist, x, y in artists:
            artist.set_data(x[:index+1], y[:index+1])
        status.set_text(f'Accepted update {index}/{last} | Fit elapsed {elapsed[index]:.3f} s\n'
                        f'Centre ({geometry[index, 0]:.4f}, {geometry[index, 1]:.4f}) m | Radius {geometry[index, 2]:.4f} m')
        reason = str((track.stages[0] if track.stages else {}).get('stop_reason') or 'No normal stop recorded')
        ending.set_text(f'Stop: {reason}\nRestricted stationarity and full recovery are assessed separately.' if stopped else '')
    return fig, draw


def markdown(track, video):
    row, states = track.result, track.states
    stage = track.stages[0] if track.stages else {}
    num = previous.number
    lines = [f"# {row['experiment_id']} — Translation and scaling before shape updates", '',
        f'Case 8; original centred 0.35 m circle and unchanged GGB-002 observations at {frequency_label(row)}. '
        'Only the two centre coordinates and radius are fitted; no shape continuation is included.', '',
        f"Receipt **{row.get('status', 'unavailable')}**; optimizer **{stage.get('outcome', 'unavailable')} / "
        f"{stage.get('stop_reason') or stage.get('detail') or 'unspecified'}**. "
        f"Fit: **{num(row.get('fit_seconds'), '.3f')} s**, {stage.get('accepted_steps', len(states)-1)} accepted updates.", '',
        'Restricted stationarity describes the best circle found by this run. It does not establish full shape recovery. '
        '`no_decreasing_step` alone is a stall, not proof of convergence.', '',
        '| Saved state | Centre x (m) | Centre y (m) | Radius (m) | Joint loss |',
        '|---|---:|---:|---:|---:|']
    for name, state in (('Initial', states[0]), ('Final', states[-1])):
        lines.append('| '+name+' | '+' | '.join(num(v, '.6g') for v in (*state['geometry'], state.get('loss')))+' |')
    image = row.get('image_metrics') or {}
    lines += ['', f"Centre error: {num(row.get('centre_error_m'), '.2f', 1000)} mm; "
        f"SSIM: {num(image.get('ssim'), '.5f')}; RRMSE: {num(image.get('rrmse'), '.5f')}. "
        f"Joint noise target met: {previous.boolean(row.get('noise_discrepancy_met'))}; "
        f"all fitted-frequency noise targets met: {previous.boolean(row.get('all_frequency_noise_targets_met'))}; "
        f"field-refinement gates passed: {previous.boolean(row.get('field_gates_passed'))}.", '',
        'Endpoint restricted-space diagnostics (saved by the experiment driver):', '',
        '```json', json.dumps(row.get('endpoint_stationarity', {}), indent=2, allow_nan=False), '```', '',
        '![Saved circle trajectory and convergence](convergence.png)', '',
        '[Vector figure](convergence.svg).'+(' [Boundary video]('+video['path']+').' if video else ''), '',
        'Plots and video use recorded accepted states without interpolation or material-image rasterization. '
        'Truth is used only for display and post-fit scoring. This postprocessor makes no physics or inverse calls.']
    lines.extend('\n- '+warning for warning in track.warnings)
    return '\n'.join(lines)+'\n'


def report(output=DEFAULT_OUTPUT, inputs=previous.DEFAULT_INPUT, *, videos=True, frames_per_state=6):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from experiments.shape_continuation import render_videos as encoder
    output, inputs = Path(output), Path(inputs)
    if frames_per_state < 1:
        raise ValueError('Every accepted state must have at least one frame.')
    track = load(output)
    sources = track.sources+[inputs, Path(__file__), Path(previous.__file__), Path(encoder.__file__)]
    hashes = {str(p.resolve()): previous.digest(p) for p in sources}
    with np.load(inputs) as data:
        edges = previous.target_edges(data)
    fig, draw = plot(track, edges)
    last, video, artifacts = len(track.states)-1, None, []
    try:
        draw((last, True))
        for suffix in ('svg', 'png'):
            path = output/f'convergence.{suffix}'
            fig.savefig(path, facecolor=fig.get_facecolor())
            if suffix == 'svg':
                previous.clean_svg(path)
            artifacts.append(path)
        if videos:
            destination = output/'W/video'
            destination.mkdir(exist_ok=True)
            path = destination/'case8_translation_scaling_boundary.mp4'
            frames = [(0, False)]*(2*encoder.FPS)+[(i, False) for i in range(1, last+1) for _ in range(frames_per_state)]+[(last, True)]*(4*encoder.FPS)
            video = dict(path=str(path.relative_to(output)), encoding=encoder.encode(fig, path, frames, draw),
                         renderer='experiments.shape_continuation.render_videos.encode',
                         shown_state_indices=sorted({i for i, _ in frames}), states=len(track.states))
            artifacts.append(path)
    finally:
        plt.close(fig)
    path = output/'report.md'
    path.write_text(markdown(track, video))
    artifacts.append(path)
    if any(previous.digest(path) != digest for path, digest in hashes.items()):
        raise ValueError('Saved sources changed during rendering.')
    manifest = dict(experiment_id=track.result['experiment_id'], frequencies_hz=frequencies(track.result).tolist(),
        physics_calls=0, inverse_calls=0, source_hashes=hashes,
        material_rasterization=False, state_interpolation=False, video=video, states=len(track.states),
        warnings=track.warnings, artifact_hashes={str(p.relative_to(output)): previous.digest(p) for p in artifacts})
    (output/'rendering_manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--inputs', type=Path, default=previous.DEFAULT_INPUT)
    parser.add_argument('--no-video', action='store_true')
    parser.add_argument('--frames-per-state', type=int, default=6)
    args = parser.parse_args()
    result = report(args.output, args.inputs, videos=not args.no_video, frames_per_state=args.frames_per_state)
    print(json.dumps(dict(states=result['states'], video=result['video']), indent=2))
