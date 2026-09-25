"""Atlas videos: what the data can still change, under the inverse videos. No field solves.

At every accepted state that `render_videos` shows for the original hybrid and
the SC-035 state band, SC-039's stored traces give each catalog frequency's
relative Jacobian A_f (paired data, each frequency scaled by its own data norm)
with respect to arclength normal ripples of unit RMS, orders 0..30, and the
relative residual r_f of the stored prediction.

- Heatmap cell (f, m): the part of r_f that ripple order m removes beyond all
  lower orders (QR of A_f with columns in order of m), capped at what a step of
  the linearization horizon 0.12/k moves (iteration 04, SC-016).
- White line: above it, even that step moves the data by less than a declared
  1% noise (conditional sensitivity x horizon < noise). Hatched.
- Amber box: what each update uses. Its columns are the stage's frequencies,
  all stacked into one Levenberg-Marquardt step (`lm_backend.jacobian`); its
  height is the ripple orders the step may move, |m| <= M. The left column is
  those frequencies together, with the runs' equal weights.
- Strip: the state itself, its Cartesian coefficients read as ripple order
  (order m from c_{1+m} and c_{1-m}; exact for ripples on a circle), with the
  storage band K. Small bars above it combine the orders beyond the heatmap.

Frames come from `render_videos.timeline` over the same three inverse tracks,
so each atlas video has exactly the frames of the matching inverse video; the
two are also stacked into one. Truth enters only the dashed reference spectrum.
Every displayed quantity is recomputed on 1024 nodes and the largest change is
recorded. Run from the repository root under EMNerf:

PYTHONPATH=solvers:. python -m experiments.shape_continuation.atlas_video
"""
import argparse
import json
from pathlib import Path
import subprocess
import textwrap

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

from . import atlas_strategy_tests as ast, render_videos as rv, spd_cases as sc, trajectory_atlas as ta
from .geometry import FourierCurve, arclength_angles, reparameterize

OUTPUT = rv.OUTPUT
SHOT_DIRS = (ta.OUTPUT / 'shots', ta.RESULTS / 'SC-040-six-scene-pipeline' / 'shots')
BAND, SHOW = 30, 24                          # ripple orders computed / displayed
TAIL = ((25, 48), (49, 96), (97, 192))       # state orders summarized above the strip
NOISE, HORIZON = 1e-2, 0.12                  # declared display conventions
GRID, CHECK_GRID = 512, 1024
LOW, HIGH = -4, 0                            # colour range, log10 of relative residual
INK, MUTED, SURFACE, AMBER, SPINE = rv.INK, rv.MUTED, rv.SURFACE, '#eda100', '#c9c8c2'
LIGHT = '#f2f8fe'
CMAP = LinearSegmentedColormap.from_list('atlas', ['#0a1628', '#123a6b', '#2a78d6', '#9cc7f2', LIGHT])
CMAP.set_bad(SURFACE)
GHZ = np.array([0.25 + 0.125 * i for i in range(19)])
# Column slots of the inverse video's three panels (subplots_adjust left=.04, right=.99, wspace=.12).
SLOT = .95 / (3 + 2 * .12)
SLOTS = [.04 + k * SLOT * 1.12 for k in range(3)]


# ------------------------------------------------------------------ atlas maths

def ripple_basis(coefficients, nodes, unit_m):
    """Normal ripples of unit RMS over arclength, [1, c1, s1, c2, s2, ...], per mm of displacement."""
    curve = FourierCurve(np.asarray(coefficients)).nodes(nodes)
    s, _ = arclength_angles(curve)
    columns = [np.ones_like(s)]
    for m in range(1, BAND + 1):
        columns += [np.sqrt(2) * np.cos(m * s), np.sqrt(2) * np.sin(m * s)]
    return np.column_stack(columns) * (1e-3 / unit_m)


def per_order(values, combine):
    values = np.asarray(values)
    return np.r_[values[0], combine(values[1::2], values[2::2])]


def removable(A, r, amplitude):
    """Squared residual each ripple order removes beyond all lower orders with a step of at most
    `amplitude` mm, and each order's conditional sensitivity |R_mm| (RMS over cosine/sine)."""
    Q, R = np.linalg.qr(A)
    n = min(A.shape)
    q, c = np.zeros(A.shape[1]), np.zeros(A.shape[1])
    q[:n], c[:n] = Q.T @ r, np.abs(np.diag(R))
    cap = np.where(c > 0, c * amplitude, 0.0)          # a column with no new information removes nothing
    d = np.minimum(np.abs(q), cap) ** 2
    return per_order(d, np.add), per_order(c, lambda a, b: np.sqrt((a ** 2 + b ** 2) / 2))


def frontier(sensitivity, amplitude, noise=NOISE):
    """Highest order before a step of `amplitude` first moves the data by less than `noise`."""
    below = np.nonzero(sensitivity * amplitude < noise)[0]
    return int(below[0]) - 1 if len(below) else len(sensitivity) - 1


def horizon_mm(k, unit_m):
    return HORIZON / k * unit_m * 1e3


def stacked(values):
    return np.concatenate([values.real, values.imag])


def shot_path(key):
    return next(path for folder in SHOT_DIRS if (path := folder / f'{key}.npz').exists())


def shot_atlas(key, observed, grid, noise=NOISE):
    names = [f'{a}_{grid}' for a in ('traces', 'reciprocal', 'weights', 'prediction')]
    with np.load(shot_path(key)) as data:
        shot = {n: data[n] for n in names + ['wavenumbers', 'interior_wavenumbers', 'coefficients', 'length_unit_m']}
    unit = float(shot['length_unit_m'])
    h = ripple_basis(shot['coefficients'], grid, unit)
    out = dict(heat=np.zeros((SHOW + 1, 19)), front=np.zeros(19, int), blocks=[], residuals=[],
               wavenumbers=shot['wavenumbers'], unit=unit, coefficients=shot['coefficients'])
    for f in range(19):
        scale = np.linalg.norm(observed[f])
        A = stacked(ta.jacobian(shot, f, grid, h)) / scale
        r = stacked(np.diag(shot[f'prediction_{grid}'][f]) - observed[f]) / scale
        amplitude = horizon_mm(shot['wavenumbers'][f], unit)
        d, c = removable(A, r, amplitude)
        out['heat'][:, f] = np.sqrt(d[:SHOW + 1])
        out['front'][f] = frontier(c, amplitude, noise)
        out['blocks'].append(A)
        out['residuals'].append(r)
    return out


def joint(atlas, active, M, noise=NOISE):
    """The active frequencies as one update sees them (equal weights), and where its removable part lies."""
    n = len(active)
    A = np.vstack([atlas['blocks'][f] for f in active]) / np.sqrt(n)
    r = np.concatenate([atlas['residuals'][f] for f in active]) / np.sqrt(n)
    amplitude = horizon_mm(max(atlas['wavenumbers'][f] for f in active), atlas['unit'])
    d, c = removable(A, r, amplitude)
    total = d.sum()
    return dict(column=np.sqrt(d[:SHOW + 1]), front_joint=frontier(c, amplitude, noise), misfit=float(np.linalg.norm(r)),
                inside=d[:M + 1].sum() / total, near=d[M + 1:M + 4].sum() / total)


def position_spectrum(coefficients, unit_mm):
    """RMS ripple (mm) per order: m=0 -> |c_1|, m>=1 -> sqrt(|c_{1+m}|^2 + |c_{1-m}|^2); plus TAIL sums."""
    c = np.asarray(coefficients)
    band = len(c) // 2
    get = lambda p: abs(c[band + p]) if abs(p) <= band else 0.0
    shown = np.array([get(1)] + [np.hypot(get(1 + m), get(1 - m)) for m in range(1, SHOW + 1)]) * unit_mm
    tail = [np.sqrt(sum(get(1 + m) ** 2 + get(1 - m) ** 2 for m in range(lo, hi + 1))) * unit_mm for lo, hi in TAIL]
    return shown, tail


# ------------------------------------------------------------------ states

def stage_name(stage):
    return 'stage_1' if stage == 0 else 'stage_5_release_repeat' if stage == 5 else f'stage_{stage}'


def atlas_states(track, trajectory, observed, check):
    """Atlas of every state of a render_videos track, at the stage configuration that produced it."""
    steps = {}
    for step in trajectory['steps']:
        steps.setdefault((step['shot'], step['stage']), step)
    states, worst = [], dict(saved_loss_relative=0.0, log10=0.0, frontier_changes=0, joint_frontier_changes=0)
    for state in track.states:
        key = ta.shot_key(state['curve'])
        step = steps[(key, stage_name(state['stage']))]
        assert step['nodes'] == GRID, (trajectory['id'], key, step['nodes'])
        base = shot_atlas(key, observed, GRID)
        active = [int(np.argmin(abs(base['wavenumbers'] - k))) for k in step['active_wavenumbers']]
        summary = joint(base, active, step['update_modes'])
        # The joint residual is the run's own: loss = misfit^2 / 2 with its equal weights.
        mismatch = abs(summary['misfit'] ** 2 / 2 - step['saved_loss']) / step['saved_loss']
        assert mismatch < 1e-8, (trajectory['id'], key, mismatch)
        worst['saved_loss_relative'] = max(worst['saved_loss_relative'], mismatch)
        if check:
            fine = shot_atlas(key, observed, CHECK_GRID)
            other = joint(fine, active, step['update_modes'])
            clip = lambda x: np.log10(np.maximum(x, 10.0 ** LOW))
            worst['log10'] = max(worst['log10'], float(np.max(abs(clip(base['heat']) - clip(fine['heat'])))),
                                 float(np.max(abs(clip(summary['column']) - clip(other['column'])))))
            worst['frontier_changes'] += int(np.sum(base['front'] != fine['front']))
            worst['joint_frontier_changes'] += int(summary['front_joint'] != other['front_joint'])
        states.append(dict(key=key, heat=base['heat'], front=base['front'], active=active, M=step['update_modes'],
                           iteration=step['iteration'],
                           K=step['curve_band'], spectrum=position_spectrum(state['curve'].coefficients, sc.LENGTH * 1e3),
                           stage=state['stage'], **summary))
    return states, worst


# ------------------------------------------------------------------ drawing

def style(axis):
    axis.set_facecolor(SURFACE)
    axis.tick_params(labelsize=7.5, colors=MUTED)
    for spine in axis.spines.values():
        spine.set_color(SPINE)


class Panel:
    """Heatmap, state strip and tail bars; `readout` and `detail` are figure texts or None."""

    def __init__(self, fig, heat, strip, tail, readout, detail=None, low=LOW, noise=NOISE):
        self.heat, self.strip, self.tail = fig.add_axes(heat), fig.add_axes(strip), fig.add_axes(tail)
        self.readout, self.detail, self.low, self.noise = readout, detail, low, noise

    @classmethod
    def slot(cls, fig, slot, name):
        x0 = SLOTS[slot]
        middle = x0 + SLOT / 2
        fig.text(middle, .955, name, ha='center', fontsize=12, weight='bold', color=INK)
        detail = fig.text(middle, .915, '', ha='center', fontsize=9, color=MUTED)
        readout = fig.text(middle, .875, '', ha='center', fontsize=9, color=INK)
        return cls(fig, [x0 + .03, .2, .19, .56], [x0 + .228, .2, .058, .56], [x0 + .228, .77, .058, .07],
                   readout, detail)

    def empty(self, message):
        for axis in (self.heat, self.strip, self.tail):
            axis.set_axis_off()
        self.heat.text(.75, .5, message, ha='center', va='center', transform=self.heat.transAxes, fontsize=10.5, color=MUTED)

    def draw(self, a, target, color, kind):
        hm, st, tl = self.heat, self.strip, self.tail
        for axis in (hm, st, tl):
            axis.cla()
            style(axis)
        image = np.full((SHOW + 1, 21), np.nan)
        image[:, 0], image[:, 2:] = a['column'], a['heat']
        with np.errstate(divide='ignore'):
            shown = np.log10(np.maximum(image, 10.0 ** (self.low - 1)))
        hm.imshow(shown, origin='lower', aspect='auto', cmap=CMAP, vmin=self.low, vmax=HIGH,
                  extent=(-.5, 20.5, -.5, SHOW + .5), interpolation='nearest')
        columns = [(0, a['front_joint'])] + [(f + 2, top) for f, top in enumerate(a['front'])]
        for x, top in columns:
            hm.add_patch(Rectangle((x - .5, top + .5), 1, SHOW - top, facecolor='none', edgecolor=LIGHT,
                                   hatch='////', lw=0, alpha=.28))
            hm.plot([x - .5, x + .5], [top + .5] * 2, color=LIGHT, lw=1.5)
        for x0, x1 in zip(range(2, 20), range(3, 21)):
            t0, t1 = a['front'][x0 - 2], a['front'][x1 - 2]
            hm.plot([x0 + .5, x0 + .5], [t0 + .5, t1 + .5], color=LIGHT, lw=1.5)
        for x in [0] + [f + 2 for f in a['active']]:
            hm.add_patch(Rectangle((x - .5, -.5), 1, a['M'] + 1, fill=False, ec=AMBER, lw=2))
        hm.text(-.4, a['M'] + .8, f"M={a['M']}", color=AMBER, fontsize=8, weight='bold', va='bottom')
        hm.set_xlim(-.5, 20.5)
        hm.set_ylim(-.5, SHOW + .5)
        ticks = [0, 4, 8, 12, 16, 20]
        hm.set_xticks(ticks)
        hm.set_xticklabels(['all\nboxed', '0.5', '1', '1.5', '2', '2.5'], fontsize=7.5)
        hm.get_xticklabels()[0].set_color('#b36b00')
        hm.set_xlabel('frequency (GHz)', fontsize=8.5, color=MUTED, labelpad=2)
        hm.set_ylabel('ripple order m', fontsize=8.5, color=MUTED)

        shown, tail = a['spectrum']
        target_shown, target_tail = target
        m = np.arange(SHOW + 1)
        st.axhspan(a['front_joint'] + .5, SHOW + .5, color='#9cc7f2', alpha=.2, lw=0)
        st.barh(m, np.where(shown > 0, shown, np.nan), height=.72, color=color, alpha=.9)
        st.step(np.r_[target_shown, target_shown[-1]], np.r_[m, SHOW + 1] - .5, where='post', color=MUTED,
                lw=1, ls=(0, (3, 2)))
        st.set_xscale('log')
        st.set_xlim(1e-5, 300)
        st.set_ylim(-.5, SHOW + .5)
        st.axhline(a['front_joint'] + .5, color=MUTED, lw=1)
        st.axhline(a['M'] + .5, color=AMBER, lw=1.6)
        if a['K'] + 1 < SHOW:
            st.axhline(a['K'] + 1.5, color=color, lw=1.3, ls=(0, (2, 1.5)))
            st.text(250, a['K'] + 1.6, f"K={a['K']}", color=INK, fontsize=7.5, ha='right', va='bottom')
        st.set_xticks([1e-4, 1e-1, 100])
        st.set_xticklabels(['1e-4', '0.1', '100'])
        st.minorticks_off()
        st.tick_params(labelleft=False, labelsize=7)
        st.set_xlabel('state, mm', fontsize=8, color=MUTED, labelpad=2)

        rows = np.arange(len(TAIL))
        tl.axhspan(-.5, len(TAIL) - .5, color='#9cc7f2', alpha=.2, lw=0)
        tl.barh(rows, [v if v > 0 else np.nan for v in tail], height=.7, color=color, alpha=.9)
        for y, v in zip(rows, target_tail):
            if v > 0:
                tl.plot([v, v], [y - .42, y + .42], color=MUTED, lw=1.1, ls=(0, (2, 1.2)))
        tl.set_xscale('log')
        tl.set_xlim(1e-5, 300)
        tl.set_ylim(-.5, len(TAIL) - .5)
        tl.set_xticks([])
        tl.set_yticks([])
        tl.minorticks_off()
        for y, (lo, hi), v in zip(rows, TAIL, tail):
            tl.text(250, y, f'{lo}–{hi}' + ('' if v > 0 else ' none'), fontsize=6.3, color=MUTED, va='center', ha='right')
        tl.set_title(f"K={a['K']}" if a['K'] + 1 >= SHOW else '', fontsize=7.5, color=INK, pad=2)

        if self.detail is not None:
            where = 'start' if a['stage'] == 0 else 'release' if a['stage'] == 5 else f"stage {a['stage']}"
            data = ', '.join(f'{GHZ[f]:g}' for f in a['active'])
            step = '' if a['stage'] == 0 else f" · step {a['iteration']}"
            self.detail.set_text(f"{where} · data {data} GHz · M={a['M']} · K={a['K']}{step}")
        misfit = f"misfit {a['misfit']:.2g}" + (' (below noise)' if a['misfit'] < self.noise else '')
        self.readout.set_text(f"{misfit} · removable: {100 * a['inside']:.0f}% inside box, "
                              f"{100 * a['near']:.0f}% just above")


GUIDE = [
    ('How to read', True),
    ('Colour: misfit that ripple order m could still remove at that frequency, beyond lower orders, '
     'with a step small enough to trust.', False),
    ('Amber box: the frequencies each update uses together (columns) and the orders it may move (|m| ≤ M). '
     'Left column: those frequencies combined.', False),
    ('Hatched, above the white line: finer than the data resolves at 1% noise.', False),
    ('Bright inside the box: the band is not the limit; steps are blocked.', False),
    ('Dark inside, bright just above: the band is the limit; raise M.', False),
    ('Just above is hatched: these frequencies are used up; add one.', False),
    ('Strip: what the outline holds per order; dashed line K is its storage band; small bars: orders above 24.', False),
]


def guide(fig):
    x0 = SLOTS[2]
    bar = fig.add_axes([x0 + .03, .2, .009, .56])
    image = plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(LOW, HIGH))
    cb = fig.colorbar(image, cax=bar)
    cb.set_ticks([-4, -3, -2, -1, 0])
    cb.set_ticklabels(['1e-4', '1e-3', '0.01', '0.1', '1'])
    cb.ax.tick_params(labelsize=7.5, colors=MUTED)
    cb.outline.set_edgecolor(SPINE)
    cb.set_label('removable misfit (fraction of data)', fontsize=8, color=MUTED, labelpad=4)
    cb.ax.yaxis.set_label_position('left')
    fig.text(x0 + SLOT / 2, .955, 'SPD-L: no atlas row', ha='center', fontsize=10.5, color=MUTED)
    fig.text(x0 + SLOT / 2, .915, 'its update space is polar-angle coefficients, not ripple orders', ha='center',
             fontsize=8, color=MUTED)
    y = .84
    for text, bold in GUIDE:
        lines = textwrap.wrap(text, 44)
        fig.text(x0 + .085, y, '\n'.join(lines), fontsize=8.3, color=INK if bold else MUTED,
                 weight='bold' if bold else 'normal', va='top', linespacing=1.25)
        y -= .036 * len(lines) + .018


# ------------------------------------------------------------------ videos

def render_case(case, output, manifest, check=True):
    tracks = [rv.hybrid(case), rv.state_band(case), rv.spd_l(case)]
    frames = rv.timeline(tracks)
    inverse = json.loads((OUTPUT / 'manifest.json').read_text())['outputs'][case]
    assert len(frames) == inverse['frames'], (case, len(frames), inverse['frames'])

    observed = np.array([o.scattered for o in ast.catalog_only(case)])
    truth, refit_error = reparameterize(ast.curve_from(sc.read(ast.source_folder(case) / 'truth.json')), 192,
                                        tolerance=1e-3)
    target = position_spectrum(truth.coefficients, sc.LENGTH * 1e3)
    trajectories = {t['id']: t for t in manifest['trajectories']}
    atlases, checks = [], {}
    for track, prefix in zip(tracks[:2], ('A_hybrid', 'B_state_band')):
        if track is None:
            atlases.append(None)
            continue
        states, worst = atlas_states(track, trajectories[f'{prefix}/{case}'], observed, check)
        atlases.append(states)
        checks[prefix] = worst

    fig = plt.figure(figsize=(15, 5.6), dpi=100, facecolor=SURFACE)
    panels = [Panel.slot(fig, 0, 'Original hybrid · atlas'), Panel.slot(fig, 1, 'State band · atlas')]
    guide(fig)
    fig.text(.5, .018, 'Saved accepted states only; SC-039 traces on 512 nodes, no new solves. Noise level (1%) and '
             'step size (0.12/k) are declared display conventions. Dashed: target, evaluation only.',
             ha='center', fontsize=8.5, color=MUTED)
    for panel, states in zip(panels, atlases):
        if states is None:
            panel.empty('Not run on this case\n(SC-035 covered peanut, C, star and kite)')
    colors = ('#1baf7a', '#eb6834')

    def draw(frame):
        _, _, indices = frame
        for panel, states, color, index in zip(panels, atlases, colors, indices):
            if states is not None:
                panel.draw(states[index], target, color, frame[0])

    video = output / f'{case}_atlas.mp4'
    record = rv.encode(fig, video, frames, draw)
    plt.close(fig)

    both = output / f'{case}_with_atlas.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(OUTPUT / f'{case}.mp4'), '-i', str(video),
                    '-filter_complex', '[0:v][1:v]vstack=inputs=2', '-c:v', 'libx264', '-crf', '24', '-pix_fmt',
                    'yuv420p', '-threads', '2', '-movflags', '+faststart', str(both)], check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,nb_frames,duration', '-of', 'json', str(both)], text=True))['streams'][0]
    assert int(probe['nb_frames']) == len(frames), (case, probe)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-sseof', '-0.1', '-i', str(both), '-frames:v', '1',
                    '-update', '1', str(output / f'{case}_with_atlas_final.png')], check=True)
    ends = {}
    for name, states in zip(('hybrid', 'state_band'), atlases):
        if states is None:
            continue
        last = {}
        for state in states:
            last[state['stage']] = state
        ends[name] = [dict(stage=s['stage'], step=s['iteration'], M=s['M'], K=s['K'], misfit=s['misfit'],
                           removable_inside_box=s['inside'], removable_M1_to_M3=s['near'], joint_frontier=s['front_joint'])
                      for s in last.values() if s['stage'] > 0]
    record.update(stacked=dict(path=both.name, probe=probe, sha256=sc.digest(both)), stage_ends=ends,
                  states={name: None if s is None else len(s) for name, s in zip(('hybrid', 'state_band'), atlases)},
                  shots=sorted({s['key'] for states in atlases if states for s in states}),
                  resolution_check_1024=checks, target_arclength_refit_error=float(refit_error))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--cases', nargs='*', default=list(ast.CASES))
    parser.add_argument('--no-check', action='store_true', help='skip the 1024-node recomputation')
    args = parser.parse_args()
    manifest = json.loads((ta.OUTPUT / 'manifest.json').read_text())
    outputs = {}
    for case in args.cases:
        outputs[case] = render_case(case, args.output, manifest, check=not args.no_check)
        print('Rendered', case, outputs[case]['frames'], 'frames', outputs[case]['resolution_check_1024'], flush=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=sc.ROOT, text=True).strip()
    sc.write(args.output / 'atlas_manifest.json', dict(
        new_field_solves=0, source=str(ta.OUTPUT.relative_to(sc.ROOT)), source_manifest_sha256=sc.digest(ta.OUTPUT / 'manifest.json'),
        inverse_manifest_sha256=sc.digest(OUTPUT / 'manifest.json'), renderer_sha256=sc.digest(Path(__file__)), commit=head,
        conventions=dict(ripple_orders=BAND, displayed=SHOW, noise=NOISE, horizon='0.12/k package units',
                         grid=GRID, check_grid=CHECK_GRID, weights='equal per active frequency', colour_floor=10.0 ** LOW),
        outputs=outputs))


if __name__ == '__main__':
    main()
