"""Render GGB-002 F4 saved boundaries with the established video encoder.

Pure postprocessing: no inverse/forward calls, material rasterization, or
interpolation. Run from the repository root with PYTHONPATH=solvers:.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

from bem_inverse.continuation.geometry import FourierCurve
from experiments.shape_continuation import render_videos as video


OUTPUT = Path(__file__).resolve().parent
ARM = OUTPUT.parent
RUN = ARM.parent
ROOT = next(p for p in OUTPUT.parents if (p / 'AGENTS.md').exists())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def target_edges(x, y, truth):
    """Exposed edges of the supplied target cells, drawn as line segments."""
    xs, ys = np.unique(x), np.unique(y)
    xe = np.r_[xs[0] - (xs[1]-xs[0])/2, (xs[:-1]+xs[1:])/2,
               xs[-1] + (xs[-1]-xs[-2])/2]
    ye = np.r_[ys[0] - (ys[1]-ys[0])/2, (ys[:-1]+ys[1:])/2,
               ys[-1] + (ys[-1]-ys[-2])/2]
    mask = np.zeros((len(ys), len(xs)), bool)
    mask[np.searchsorted(ys, y), np.searchsorted(xs, x)] = truth > 1 + 1e-5
    edges = []
    for j, i in np.argwhere(mask):
        if i == 0 or not mask[j, i-1]:
            edges.append(((xe[i], ye[j]), (xe[i], ye[j+1])))
        if i == len(xs)-1 or not mask[j, i+1]:
            edges.append(((xe[i+1], ye[j]), (xe[i+1], ye[j+1])))
        if j == 0 or not mask[j-1, i]:
            edges.append(((xe[i], ye[j]), (xe[i+1], ye[j])))
        if j == len(ys)-1 or not mask[j+1, i]:
            edges.append(((xe[i], ye[j+1]), (xe[i+1], ye[j+1])))
    assert mask.sum() == 93
    return np.asarray(edges)


def main():
    sources = [ARM/'result.json', ARM/'curve.npz', ARM/'endpoint.npz', RUN/'inputs.npz',
               Path(video.__file__), Path(__file__),
               ROOT/'solvers/bem_inverse/continuation/geometry.py']
    source_hashes = {str(p.relative_to(ROOT)): digest(p) for p in sources}
    result = json.loads((ARM/'result.json').read_text())
    assert result['arm'] == 'F4'
    assert result['frequencies_hz'] == [5e8, 7.5e8, 1e9, 1.25e9]
    assert len(result['stages']) == 1
    stage = result['stages'][0]
    assert stage['stage_label'] == 'F4_M3'
    history = stage['history']
    assert [h['iteration'] for h in history] == list(range(16))
    coefficients = [np.array(h['coefficients']['real']) +
                    1j*np.array(h['coefficients']['imag']) for h in history]
    with np.load(ARM/'curve.npz') as saved:
        assert np.array_equal(coefficients[-1], saved['coefficients'])
    with np.load(ARM/'endpoint.npz') as saved:
        assert np.array_equal(coefficients[-1], saved['coefficients'])
    curves = [FourierCurve(c).values(4096) for c in coefficients]
    with np.load(RUN/'inputs.npz') as inputs:
        edges = target_edges(inputs['x'].astype(float), inputs['y'].astype(float), inputs['truth'])
    initial = curves[0]
    assert np.max(abs(abs(initial) - .35)) < 1e-12
    accepted = {t['iteration']: t for t in stage['trials'] if t.get('status') == 'accepted'}
    assert len(accepted) == 15
    residual = np.array([h['relative_l2'] for h in history]) * 100
    last = len(history)-1
    frames = [(0, False)] * (2*video.FPS)
    for i in range(1, len(history)):
        frames += [(i, False)] * video.FPS
    frames += [(last, True)] * (5*video.FPS)
    assert {i for i, _ in frames} == set(range(len(history)))

    ink, muted, surface = video.INK, video.MUTED, video.SURFACE
    orange, target, faint = '#d85828', '#45515e', '#b7bec5'
    fig = plt.figure(figsize=(12.8, 8), dpi=100, facecolor=surface)
    fig.text(.065, .945, 'Case 8  |  Four-frequency inverse', fontsize=21,
             color=ink, weight='bold')
    fig.text(.065, .899, '0.50, 0.75, 1.00, 1.25 GHz fitted together  •  GGB-002 F4',
             fontsize=11.5, color=muted)
    ax = fig.add_axes([.065, .20, .50, .635], facecolor=surface)
    ax.add_collection(LineCollection(edges, colors=target, linewidths=1.6))
    ax.plot(np.r_[initial.real, initial.real[0]], np.r_[initial.imag, initial.imag[0]],
            color=faint, lw=1.2, ls=(0, (4, 3)))
    boundary, = ax.plot([], [], color=orange, lw=2.6)
    points = np.r_[np.concatenate(curves), edges[..., 0].ravel()+1j*edges[..., 1].ravel()]
    cx, cy = (points.real.min()+points.real.max())/2, (points.imag.min()+points.imag.max())/2
    half = .57*max(np.ptp(points.real), np.ptp(points.imag))
    ax.set(xlim=(cx-half, cx+half), ylim=(cy-half, cy+half), aspect='equal',
           xlabel='x (m)', ylabel='y (m)')
    ax.legend(handles=[Line2D([], [], color=orange, lw=2.6, label='Accepted boundary'),
                       Line2D([], [], color=target, lw=1.6, label='Target cell boundary'),
                       Line2D([], [], color=faint, ls='--', label='Initial circle')],
              loc='upper left', frameon=False, fontsize=9)
    progress = fig.text(.64, .802, '', fontsize=17, color=ink, weight='bold')
    state_detail = fig.text(.64, .747, '', fontsize=11, color=muted)
    loss_ax = fig.add_axes([.64, .38, .31, .305], facecolor=surface)
    loss_ax.plot(range(len(history)), residual, color='#dde0e3', lw=1.3)
    path, = loss_ax.plot([], [], color=orange, lw=2)
    marker, = loss_ax.plot([], [], 'o', color=orange, ms=6)
    loss_ax.set(xlim=(-.3, last+.3), ylim=(0, max(residual)*1.1),
                xlabel='Accepted update', ylabel='Saved data residual (%)')
    loss_ax.set_xticks([0, 5, 10, 15])
    readout = fig.text(.64, .255, '', fontsize=12, color=ink)
    outcome = fig.text(.64, .185, '', fontsize=11, color='#a92d24', linespacing=1.5)
    for axis in (ax, loss_ax):
        axis.grid(alpha=.15)
        axis.tick_params(colors=muted, labelsize=9)
        axis.xaxis.label.set_color(muted)
        axis.yaxis.label.set_color(muted)
        for spine in axis.spines.values():
            spine.set_color('#d3d5d6')
    fig.text(.065, .098, 'Direct Fourier outlines • Initial state + all 15 accepted updates • No interpolated shapes',
             fontsize=10, color=muted)
    fig.text(.065, .063, 'Playback is slowed for inspection. Recorded fitting time: 4.769 s. Target is display-only.',
             fontsize=10, color=muted)

    def draw(frame):
        i, stopped = frame
        z = curves[i]
        boundary.set_data(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]])
        path.set_data(np.arange(i+1), residual[:i+1])
        marker.set_data([i], [residual[i]])
        progress.set_text(f'Accepted update {i} / {last}')
        fraction = 'Initial circle' if i == 0 else (
            'Full candidate accepted' if accepted[i]['backtrack'] == 0 else
            f"Candidate accepted at 1/{2**accepted[i]['backtrack']} step")
        state_detail.set_text('M = 3  •  '+fraction)
        readout.set_text(f'Data residual: {residual[i]:.2f}%\nPer-frequency noise targets: about 5.5%')
        outcome.set_text('Stopped: candidate physics evaluation failed.\nM7 and M11 were not reached.' if stopped else '')

    mp4 = OUTPUT/'case8_four_frequency_boundary.mp4'
    encoded = video.encode(fig, mp4, frames, draw)
    for name, frame in [('initial', (0, False)), ('middle', (8, False)), ('final', (last, True))]:
        draw(frame)
        fig.savefig(OUTPUT/f'{name}.png', dpi=100, facecolor=surface)
    draw((last, True))
    fig.savefig(OUTPUT/'final.svg', facecolor=surface)
    plt.close(fig)
    assert all(digest(ROOT/p) == h for p, h in source_hashes.items())
    receipt = dict(source_hashes=source_hashes,
                   renderer='experiments.shape_continuation.render_videos.encode',
                   encoding=encoded, initial_plus_accepted_states=len(history),
                   shown_state_indices=sorted({i for i, _ in frames}),
                   frequencies_hz=result['frequencies_hz'], stage=stage['stage_label'],
                   fit_seconds=result['fit_seconds'], outcome=stage['outcome'], detail=stage['detail'],
                   coefficients_match_curve_and_endpoint=True,
                   drawing='Direct Fourier boundary lines; exposed supplied target-cell edges.',
                   material_rasterization=False, state_interpolation=False, new_physics_calls=0,
                   states=[dict(iteration=h['iteration'], relative_l2=h['relative_l2'],
                                clock_seconds=h['work']['seconds'],
                                backtrack=None if i == 0 else accepted[i]['backtrack'])
                           for i, h in enumerate(history)])
    (OUTPUT/'manifest.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(dict(video=str(mp4.relative_to(ROOT)), **encoded), indent=2))


if __name__ == '__main__':
    main()
