"""The six development scenes through the current pipeline, each with its atlas. No field solves.

One trajectory per scene: SC-035's low state band (stages 1-4: 0.5 -> 1.25 GHz,
M 3/5/7/9, K 8/12/16/20), then SC-038's update-band release (all 19
frequencies, M 11/15/19, K=192). C and kite come from SC-038 (kite on its
recorded 768/1536-node path); circle, star, peanut and hook from SC-040.
`SC-040-six-scene-pipeline/trajectories.json` lists every accepted state.

Each frame shows the saved accepted state against the target, and the atlas at
that state (`atlas_video`): what misfit each ripple order could still remove at
each frequency, the amber box of what each update uses, and the state's own
content per order. Every accepted state appears; nothing is interpolated. The
target is used only for display, the RMS readout and the dashed spectrum.

Checks that stop rendering: each atlas reproduces the loss the run saved at that
state; the last frame is the recorded endpoint with its recorded RMS. Every
displayed value is recomputed on twice the nodes and the largest change is
recorded. Run from the repository root under EMNerf:

PYTHONPATH=solvers:. python -m experiments.shape_continuation.pipeline_video
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

from . import atlas_strategy_tests as ast, atlas_video as av, render_videos as rv, spd_cases as sc
from .atlas_survey import symmetric_rms_distance
from .geometry import FourierCurve, reparameterize

RESULTS = sc.ROOT / 'results/validation/shape_continuation'
TRAJECTORIES = RESULTS / 'SC-040-six-scene-pipeline' / 'trajectories.json'
OUTPUT = RESULTS / 'videos'
SCENES = dict(wrong_circle=('1_circle', 'Circle'), circle_to_star=('2_star', 'Star'),
              circle_to_c=('3_c', 'C (not star-shaped)'), kite=('4_kite', 'Kite'),
              peanut=('5_peanut', 'Peanut'), hook=('6_hook', 'Hook (not star-shaped)'))
RELEASE = {11: 1, 15: 2, 19: 3}
SECONDS = dict(start=1.5, stage=4, release=4, final=5)
FPS = rv.FPS
COLOR = '#eb6834'          # the state-band track colour of the earlier videos
STAGE_GHZ = ('0.5', '0.5, 0.75', '0.5, 0.75, 1.0', '0.5, 0.75, 1.0, 1.25')
# The data are noise-free and these runs fit them to about 1e-4 (C's final catalog residual is
# 2.3e-4), so the declared resolution level is 1e-4 rather than the comparison videos' 1%.
NOISE, LOW = 1e-4, -6
GUIDE = [
    ('How to read', True),
    ('Colour: capped QR residual score in ideal normal ripples; lower orders enter first. '
     'Not achievable finite-step loss reduction.', False),
    ('Amber box: active frequencies and nominal update band. Projected solver motions differ. '
     'Left column combines active frequencies.', False),
    ('White line: first sensitivity crossing at an assumed 0.01% level; not a recovery limit.', False),
    ('Bright inside: test the implemented update and finite-step validity.', False),
    ('Bright above: test extra update freedom on the same data.', False),
    ('Hatching alone does not justify adding frequencies.', False),
    ('Strip: what the outline holds per order; dashed line K is its storage band; small bars: orders above 24.', False),
]


def phase(index, step):
    if index == 0:
        return ('start', 0)
    if step['stage'].startswith('stage_'):
        return ('stage', int(step['stage'].split('_')[1]))
    return ('release', RELEASE[step['update_modes']])


def states(trajectory, observed, truth_points):
    """Atlas, RMS and label of every accepted state; stops on any disagreement with the saved run."""
    out, worst = [], dict(saved_loss_relative=0.0, log10=0.0, frontier_changes=0, joint_frontier_changes=0)
    clip = lambda x: np.log10(np.maximum(x, 10.0 ** LOW))
    for index, step in enumerate(trajectory['steps']):
        grid = step['nodes']
        base = av.shot_atlas(step['shot'], observed, grid, NOISE)
        fine = av.shot_atlas(step['shot'], observed, 2 * grid, NOISE)
        active = [int(np.argmin(abs(base['wavenumbers'] - k))) for k in step['active_wavenumbers']]
        summary = av.joint(base, active, step['update_modes'], NOISE)
        other = av.joint(fine, active, step['update_modes'], NOISE)
        if step['saved_loss'] is not None:
            mismatch = abs(summary['misfit'] ** 2 / 2 - step['saved_loss']) / step['saved_loss']
            assert mismatch < 1e-8, (trajectory['id'], index, mismatch)
            worst['saved_loss_relative'] = max(worst['saved_loss_relative'], mismatch)
        worst['log10'] = max(worst['log10'], float(np.max(abs(clip(base['heat']) - clip(fine['heat'])))),
                             float(np.max(abs(clip(summary['column']) - clip(other['column'])))))
        worst['frontier_changes'] += int(np.sum(base['front'] != fine['front']))
        worst['joint_frontier_changes'] += int(summary['front_joint'] != other['front_joint'])
        curve = FourierCurve(base['coefficients'])
        kind, number = phase(index, step)
        out.append(dict(heat=base['heat'], front=base['front'], active=active, M=step['update_modes'],
                        K=step['curve_band'], iteration=step['iteration'], stage=number, kind=kind, nodes=grid,
                        spectrum=av.position_spectrum(curve.coefficients, sc.LENGTH * 1e3),
                        z=curve.values(2048) * sc.LENGTH + sc.CENTER,
                        rms_mm=1e3 * symmetric_rms_distance(curve, truth_points, sc.LENGTH), **summary))
    return out, worst


def timeline(items):
    phases = [('start', 0)] + [('stage', n) for n in (1, 2, 3, 4)] + [('release', n) for n in (1, 2, 3)]
    frames, held = [], 0
    for kind, number in phases:
        members = [i for i, s in enumerate(items) if (s['kind'], s['stage']) == (kind, number)]
        count = max(int(SECONDS[kind] * FPS), len(members))
        for i in range(count):
            if members:
                held = members[round(i * (len(members) - 1) / max(1, count - 1))]
            frames.append((kind, number, held))
    frames += [('final', 0, len(items) - 1)] * int(SECONDS['final'] * FPS)
    assert {f[2] for f in frames} == set(range(len(items)))
    return frames


def label(state):
    if state['kind'] == 'start':
        return 'common start circle'
    where = f"stage {state['stage']}" if state['kind'] == 'stage' else f"release {state['stage']}"
    grid = '' if state['nodes'] == 512 else f" · {state['nodes']} nodes"
    return f"{where} · M={state['M']}, K={state['K']} · step {state['iteration']}{grid}"


def render(case, trajectory, output):
    name, title = SCENES[case]
    observed = np.array([o.scattered for o in ast.catalog_only(case)])
    truth_curve = ast.curve_from(sc.read(ast.source_folder(case) / 'truth.json'))
    truth_points, truth = truth_curve.values(16384), truth_curve.values(2048) * sc.LENGTH + sc.CENTER
    refit, refit_error = reparameterize(truth_curve, 192, tolerance=1e-3)
    target = av.position_spectrum(refit.coefficients, sc.LENGTH * 1e3)
    items, worst = states(trajectory, observed, truth_points)

    last_source = sc.ROOT / trajectory['steps'][-1]['source']
    result = sc.read(last_source if last_source.name.endswith('.json') and 'history' not in last_source.name
                     else last_source.parent / 'result.json')
    recorded = result['score']['symmetric_rms_mm']
    assert abs(items[-1]['rms_mm'] - recorded) <= 1e-9 * max(recorded, 1e-3), (case, items[-1]['rms_mm'], recorded)
    assert np.allclose(ast.curve_from(result['curve']).values(2048) * sc.LENGTH + sc.CENTER, items[-1]['z'], atol=1e-12)

    everything = np.concatenate([truth] + [s['z'] for s in items]) * 1e3
    low = everything.real.min() + 1j * everything.imag.min()
    high = everything.real.max() + 1j * everything.imag.max()
    middle, half = (low + high) / 2, 0.58 * max((high - low).real, (high - low).imag)

    fig = plt.figure(figsize=(15, 6.6), dpi=100, facecolor=av.SURFACE)
    fig.text(.5, .955, title, ha='center', fontsize=18, weight='bold', color=av.INK)
    heading = fig.text(.5, .905, '', ha='center', fontsize=12.5, color=av.INK)
    fig.text(.5, .018, 'Saved accepted states only: no interpolation, no new solves. Dashed: target, used only for the '
             'display, the RMS and the dashed spectrum. Noise-free data; the 0.01% level and the 0.12/k step are display conventions.',
             ha='center', fontsize=8.5, color=av.MUTED)

    shape = fig.add_axes([.035, .15, .27, .66])
    av.style(shape)
    shape.plot(1e3 * np.r_[truth.real, truth.real[0]], 1e3 * np.r_[truth.imag, truth.imag[0]], color=rv.TARGET,
               lw=1.4, ls=(0, (4, 3)), label='Target')
    line = shape.plot([], [], color=COLOR, lw=2.2, label='Accepted state')[0]
    shape.set(xlim=(middle.real - half, middle.real + half), ylim=(middle.imag - half, middle.imag + half), aspect='equal')
    shape.grid(alpha=.15)
    shape.legend(loc='upper right', fontsize=8.5, frameon=False, labelcolor=av.MUTED)
    shape.set_xlabel('x (mm)', color=av.MUTED, fontsize=9)
    shape.set_ylabel('y (mm)', color=av.MUTED, fontsize=9)
    detail = shape.text(.5, 1.015, '', ha='center', va='bottom', transform=shape.transAxes, fontsize=9.5, color=av.MUTED)
    error = shape.text(.5, -.12, '', ha='center', va='top', transform=shape.transAxes, fontsize=11, color=av.INK)

    fig.text(.515, .835, 'Atlas at this state', ha='center', fontsize=10, color=av.INK, weight='bold')
    readout = fig.text(.515, .795, '', ha='center', fontsize=9, color=av.MUTED)
    panel = av.Panel(fig, [.36, .15, .31, .62], [.685, .15, .065, .62], [.685, .785, .065, .065], readout,
                     low=LOW, noise=NOISE)

    bar = fig.add_axes([.8, .15, .008, .62])
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=av.CMAP, norm=plt.Normalize(LOW, av.HIGH)), cax=bar)
    cb.set_ticks([-6, -5, -4, -3, -2, -1, 0])
    cb.set_ticklabels(['1e-6', '1e-5', '1e-4', '1e-3', '0.01', '0.1', '1'])
    cb.ax.tick_params(labelsize=7.5, colors=av.MUTED)
    cb.outline.set_edgecolor(av.SPINE)
    cb.set_label('QR score (relative data units)', fontsize=8, color=av.MUTED, labelpad=4)
    cb.ax.yaxis.set_label_position('left')
    y = .8
    for text, bold in GUIDE:
        lines = textwrap.wrap(text, 40)
        fig.text(.835, y, '\n'.join(lines), fontsize=8, color=av.INK if bold else av.MUTED,
                 weight='bold' if bold else 'normal', va='top', linespacing=1.2)
        y -= .0285 * len(lines) + .011

    status = ('completed schedule' if trajectory['status'] == 'COMPLETED_SCHEDULE'
              else f"stopped: {str(trajectory['reason'] or trajectory['status']).replace('_', ' ').lower()}")

    def draw(frame):
        kind, number, index = frame
        state = items[index]
        if kind == 'stage':
            heading.set_text(f'Stage {number} of 4 · data at {STAGE_GHZ[number - 1]} GHz')
        elif kind == 'release':
            heading.set_text(f'Release {number} of 3 · all 19 frequencies, 0.25–2.5 GHz · M={[11, 15, 19][number - 1]}')
        else:
            heading.set_text('Common start: circle of radius 65 mm' if kind == 'start' else 'Final state')
        line.set_data(1e3 * np.r_[state['z'].real, state['z'].real[0]], 1e3 * np.r_[state['z'].imag, state['z'].imag[0]])
        text = label(state)
        if kind in ('stage', 'release') and (state['kind'], state['stage']) != (kind, number):
            text = 'no accepted step here · ' + text
        detail.set_text(('last accepted: ' if kind == 'final' else '') + text)
        error.set_text(f"Final RMS {state['rms_mm']:.3g} mm · {status}" if kind == 'final'
                       else f"RMS to target {state['rms_mm']:.3g} mm")
        panel.draw(state, target, COLOR, kind)

    frames = timeline(items)
    video = output / f'{name}.mp4'
    record = rv.encode(fig, video, frames, draw)
    draw(frames[-1])
    (output / 'frames').mkdir(exist_ok=True)
    fig.savefig(output / 'frames' / f'{name}_final.png', dpi=100, facecolor=av.SURFACE)
    plt.close(fig)
    record.update(trajectory=trajectory['id'], states=len(items), status=trajectory['status'],
                  reason=trajectory['reason'], final_rms_mm=items[-1]['rms_mm'], recorded_rms_mm=recorded,
                  final_score=result['score'], checks=worst, target_arclength_refit_error=float(refit_error),
                  stage_ends=[dict(kind=s['kind'], stage=s['stage'], step=s['iteration'], M=s['M'], K=s['K'],
                                   misfit=s['misfit'], removable_inside_box=s['inside'],
                                   removable_M1_to_M3=s['near'], joint_frontier=s['front_joint'], rms_mm=s['rms_mm'])
                              for s in {(s['kind'], s['stage']): s for s in items if s['kind'] != 'start'}.values()])
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--cases', nargs='*', default=list(SCENES))
    args = parser.parse_args()
    declared = {t['case']: t for t in sc.read(TRAJECTORIES)['trajectories']}
    outputs = {}
    for case in args.cases:
        outputs[case] = render(case, declared[case], args.output)
        print('Rendered', case, outputs[case]['frames'], 'frames', 'RMS', outputs[case]['final_rms_mm'],
              outputs[case]['checks'], flush=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=sc.ROOT, text=True).strip()
    sc.write(args.output / 'frames' / 'manifest.json', dict(
        new_field_solves=0, trajectories=str(TRAJECTORIES.relative_to(sc.ROOT)), trajectories_sha256=sc.digest(TRAJECTORIES),
        renderer_sha256=sc.digest(Path(__file__)), atlas_sha256=sc.digest(Path(av.__file__)), commit=head,
        conventions=dict(noise=NOISE, colour_floor=10.0 ** LOW, horizon='0.12/k package units', ripple_orders=av.BAND,
                         displayed=av.SHOW),
        outputs=outputs))


if __name__ == '__main__':
    main()
