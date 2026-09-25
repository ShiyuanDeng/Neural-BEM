"""Render the six development cases from saved accepted states; no field solves.

Each video shows three inversions side by side, stage by stage:

- the original hybrid (SC-029 baseline, which SC-036 replays bitwise);
- the SC-035 low state band, K 8/12/16/20 then a K=192 release stage
  (run on peanut, C, star and kite only);
- SPD-L (SC-034 arm L, radial K 4/6/8/10).

Every saved accepted state is shown exactly once or held; nothing is
interpolated. The target and the RMS readout are evaluation only. The final
frame must reproduce each run's recorded endpoint and score, or rendering
stops. Run from the repository root under EMNerf:

PYTHONPATH=solvers:. python -m experiments.shape_continuation.render_videos
"""
import argparse
import json
from pathlib import Path
import subprocess

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from . import atlas_strategy_tests as ast, spd_cases as sc
from .atlas_survey import symmetric_rms_distance

RESULTS = sc.ROOT / 'results/validation/shape_continuation'
OUTPUT = RESULTS / 'videos'
FPS = 12
NAMES = dict(wrong_circle='Circle', circle_to_star='Star', circle_to_c='C (not star-shaped)',
             kite='Kite', peanut='Peanut', hook='Hook (not star-shaped)')
STAGE_GHZ = ('0.5', '0.5, 0.75', '0.5, 0.75, 1.0', '0.5, 0.75, 1.0, 1.25')
UPDATE_MODES = (3, 5, 7, 9)
# Reference palette slots 1-3 (validated all-pairs); target and text in neutral ink.
INK, MUTED, SURFACE, TARGET = '#0b0b0b', '#52514e', '#fcfcfb', '#52514e'
SECONDS = dict(start=1.5, stage=4, release=2.5, final=5)


class Track:
    """One inversion's accepted states, in order, each tagged with its stage."""

    def __init__(self, name, color, sources, status, reason, score, final):
        self.name, self.color, self.sources = name, color, sources
        self.status, self.reason, self.score, self.final = status, reason, score, final
        self.states, self.stages_run = [], set()

    def add(self, curve, stage, label):
        self.stages_run.add(stage)
        z = curve.values(2048) * sc.LENGTH + sc.CENTER
        if self.states and np.max(np.abs(z - self.states[-1]['z'])) <= 1e-12:
            return  # a stage start repeats the previous accepted state
        self.states.append(dict(curve=curve, z=z, stage=stage, label=label))

    def indices(self, stage):
        return [i for i, s in enumerate(self.states) if s['stage'] == stage]


def digest_all(paths):
    return {str(p.relative_to(sc.ROOT)): sc.digest(p) for p in paths}


def hybrid(case):
    folder = RESULTS / 'SC-029-atlas-strategies/runs/baseline' / case / 'none'
    result = sc.read(folder / 'result.json')
    files = sorted(folder.glob('stage_*_history.json'))
    track = Track('Original hybrid (K=192 throughout)', '#1baf7a', digest_all(files + [folder / 'result.json']),
                  result['status'], result['reason'], result['score']['symmetric_rms_mm'],
                  ast.curve_from(result['final_curve']))
    for path in files:
        stage = int(path.name.split('_')[1])
        for row in sc.read(path)['history']:
            curve = ast.curve_from(row['coefficients'])
            track.add(curve, 0 if not track.states else stage,
                      f"stage {stage} · M={UPDATE_MODES[stage-1]}, K={curve.band} · step {row['iteration']}")
    return track


def state_band(case):
    folder = RESULTS / 'SC-035-state-band/runs' / case / 'low'
    if not folder.exists():
        return None
    result = sc.read(folder / 'continue.json')
    files = sorted(folder.glob('stage_*_history.json'))
    track = Track('State band (SC-035: K 8/12/16/20, then 192)', '#eb6834',
                  digest_all(files + [folder / 'continue.json']), result['status'], result['reason'],
                  result['score']['symmetric_rms_mm'], ast.curve_from(result['curve']))
    for path in files:
        stage = 5 if 'release' in path.name else int(path.name.split('_')[1])
        for row in sc.read(path)['history']:
            curve = ast.curve_from(row['coefficients'])
            track.add(curve, 0 if not track.states else stage,
                      f"{'release' if stage == 5 else f'stage {stage}'} · M={UPDATE_MODES[min(stage, 4)-1]}, "
                      f"K={curve.band} · step {row['iteration']}")
    return track


def spd_l(case):
    folder = RESULTS / 'SC-034-spd-legacy-controls/runs/L' / case
    result = sc.read(folder / 'result.json')
    files = sorted(folder.glob('stage_*/trajectory.jsonl'))
    track = Track('SPD-L (SC-034: radial K 4/6/8/10)', '#2a78d6', digest_all(files + [folder / 'result.json']),
                  result['status'], result['reason'], result['score']['symmetric_rms_mm'],
                  ast.curve_from(result['final_curve']))
    driver = sc.spd_modules()[0].p.driver
    for path in files:
        stage = int(path.parent.name.split('_')[1])
        for line in path.read_text().splitlines():
            row = json.loads(line)
            component = driver.deserialize_state(row['state']).components[0]
            track.add(sc.from_cartesian(component), 0 if not track.states else stage,
                      f"stage {stage} · radial K={component.maximum_mode} · step {row['iteration']}")
        # As in TOP-025's renderer: a hard stop can leave the stage's last
        # accepted state in its checkpoint but not in the trajectory log.
        checkpoint = path.parent / 'accepted_state.json'
        if checkpoint.exists():
            track.sources[str(checkpoint.relative_to(sc.ROOT))] = sc.digest(checkpoint)
            component = driver.deserialize_state(sc.read(checkpoint)['state']).components[0]
            track.add(sc.from_cartesian(component), stage,
                      f"stage {stage} · radial K={component.maximum_mode} · accepted checkpoint")
    return track


def check_endpoint(track):
    """The video must end at the scored endpoint and reproduce its score."""
    last = track.states[-1]
    final = track.final.values(2048) * sc.LENGTH + sc.CENTER
    assert np.max(np.abs(last['z'] - final)) <= 1e-12, f'{track.name}: last frame is not the scored endpoint'
    assert abs(last['rms_mm'] - track.score) <= 1e-9 * max(track.score, 1e-3), (track.name, last['rms_mm'], track.score)


def timeline(tracks):
    """Frames as (phase, index per track); stages stay aligned across tracks."""
    phases = [('start', SECONDS['start'], 0)] + [('stage', SECONDS['stage'], n) for n in (1, 2, 3, 4)]
    if any(t and 5 in t.stages_run for t in tracks):  # shown even when the release accepts no step
        phases.append(('release', SECONDS['release'], 5))
    frames, held = [], [0 if t else None for t in tracks]
    for kind, seconds, stage in phases:
        lists = [t.indices(stage) if t else [] for t in tracks]
        count = max([int(seconds * FPS)] + [len(items) for items in lists])
        for i in range(count):
            for k, items in enumerate(lists):
                if items:
                    held[k] = items[round(i * (len(items) - 1) / max(1, count - 1))]
            frames.append((kind, stage, tuple(held)))
    frames += [('final', 0, tuple(len(t.states) - 1 if t else None for t in tracks))] * int(SECONDS['final'] * FPS)
    shown = {(k, i) for _, _, indices in frames for k, i in enumerate(indices) if i is not None}
    assert all((k, i) in shown for k, t in enumerate(tracks) if t for i in range(len(t.states)))
    return frames


def encode(fig, path, frames, draw):
    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    command = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{width}x{height}', '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-crf', '24',
               '-pix_fmt', 'yuv420p', '-threads', '2', '-movflags', '+faststart', str(path)]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        last = pixels = None
        for frame in frames:
            if frame != last:
                draw(frame)
                fig.canvas.draw()
                pixels = np.ascontiguousarray(np.asarray(fig.canvas.buffer_rgba())[:, :, :3]).tobytes()
                last = frame
            process.stdin.write(pixels)
        process.stdin.close()
        stderr = process.stderr.read().decode()
        if process.wait():
            raise RuntimeError(f'ffmpeg failed: {stderr}')
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,nb_frames,duration', '-of', 'json', str(path)], text=True))['streams'][0]
    assert int(probe['nb_frames']) == len(frames)
    return dict(probe=probe, sha256=sc.digest(path), frames=len(frames), fps=FPS, bytes=path.stat().st_size)


def outcome(track):
    text = 'completed schedule' if track.status == 'COMPLETED_SCHEDULE' else \
        f"hard stop: {str(track.reason or track.status).replace('_', ' ').lower()}"
    return f'Final RMS {track.score:.3g} mm · {text}'


def render_case(case, output):
    truth_curve = ast.curve_from(sc.read(ast.source_folder(case) / 'truth.json'))
    truth_points = truth_curve.values(16384)
    truth = truth_curve.values(2048) * sc.LENGTH + sc.CENTER
    tracks = [hybrid(case), state_band(case), spd_l(case)]
    for track in filter(None, tracks):
        for state in track.states:  # evaluation only; the same metric as each run's saved score
            state['rms_mm'] = 1e3 * symmetric_rms_distance(state['curve'], truth_points, sc.LENGTH)
        check_endpoint(track)
    everything = np.concatenate([truth] + [s['z'] for t in filter(None, tracks) for s in t.states]) * 1e3
    low, high = everything.real.min() + 1j * everything.imag.min(), everything.real.max() + 1j * everything.imag.max()
    middle, half = (low + high) / 2, 0.6 * max((high - low).real, (high - low).imag)

    fig, axes = plt.subplots(1, 3, figsize=(15, 6.8), dpi=100, facecolor=SURFACE)
    fig.subplots_adjust(left=.04, right=.99, bottom=.19, top=.80, wspace=.12)
    fig.text(.5, .955, NAMES[case], ha='center', fontsize=18, weight='bold', color=INK)
    phase = fig.text(.5, .895, '', ha='center', fontsize=12.5, color=INK)
    fig.text(.5, .035, 'Saved accepted states only: no interpolation, no new solves. Dashed: target, used only for '
             'this display and the RMS readout. Playback speed is not solve time.', ha='center', fontsize=9.5, color=MUTED)
    artists = []
    for axis, track in zip(axes, tracks):
        axis.set_facecolor(SURFACE)
        axis.plot(1e3 * np.r_[truth.real, truth.real[0]], 1e3 * np.r_[truth.imag, truth.imag[0]], color=TARGET,
                  lw=1.4, ls=(0, (4, 3)), label='Target')
        axis.set(xlim=(middle.real - half, middle.real + half), ylim=(middle.imag - half, middle.imag + half),
                 aspect='equal')
        axis.tick_params(labelsize=8, colors=MUTED)
        axis.grid(alpha=.15)
        for spine in axis.spines.values():
            spine.set_color('#c9c8c2')
        if track is None:
            axis.set_title('State band (SC-035)', fontsize=11.5, color=INK, weight='bold', pad=22)
            axis.text(.5, .5, 'Not run on this case\n(SC-035 covered peanut, C, star and kite)', ha='center',
                      va='center', transform=axis.transAxes, fontsize=11, color=MUTED,
                      bbox=dict(facecolor=SURFACE, edgecolor='none', alpha=.92))
            artists.append(None)
            continue
        axis.set_title(track.name, fontsize=11.5, color=INK, weight='bold', pad=22)
        line = axis.plot([], [], color=track.color, lw=2.2, label='Accepted state')[0]
        detail = axis.text(.5, 1.012, '', ha='center', va='bottom', transform=axis.transAxes, fontsize=9.5, color=MUTED)
        error = axis.text(.5, -.155, '', ha='center', va='top', transform=axis.transAxes, fontsize=11, color=INK)
        axis.legend(loc='upper right', fontsize=8.5, frameon=False, labelcolor=MUTED)
        artists.append((line, detail, error))
    axes[0].set_ylabel('y (mm)', color=MUTED)
    for axis in axes:
        axis.set_xlabel('x (mm)', color=MUTED)

    def draw(frame):
        kind, stage, indices = frame
        phase.set_text(f'Stage {stage} of 4 · data at {STAGE_GHZ[stage-1]} GHz' if kind == 'stage' else
                       dict(start='Common start: circle of radius 65 mm',
                            release='Release stage (state band only): same four frequencies, state K=192',
                            final='Final states')[kind])
        for track, artist, index in zip(tracks, artists, indices):
            if track is None:
                continue
            line, detail, error = artist
            state = track.states[index]
            line.set_data(1e3 * np.r_[state['z'].real, state['z'].real[0]], 1e3 * np.r_[state['z'].imag, state['z'].imag[0]])
            if kind == 'final':
                detail.set_text('last accepted: ' + state['label'])
                error.set_text(outcome(track))
            else:
                label = 'start' if state['stage'] == 0 else state['label']
                if kind in ('stage', 'release') and state['stage'] != stage:
                    stopped = index == len(track.states) - 1 and track.status != 'COMPLETED_SCHEDULE'
                    label = ('run stopped (hard stop)' if stopped else 'no release stage' if kind == 'release'
                             else 'no accepted step this stage') + ' · ' + label
                detail.set_text(label)
                error.set_text(f"RMS to target {state['rms_mm']:.3g} mm")

    frames = timeline(tracks)
    video = output / f'{case}.mp4'
    record = encode(fig, video, frames, draw)
    draw(frames[-1])
    fig.savefig(output / f'{case}_final.png', dpi=100, facecolor=SURFACE)
    plt.close(fig)
    record.update(sources={k: v for t in filter(None, tracks) for k, v in t.sources.items()},
                  tracks=[None if t is None else dict(name=t.name, accepted_states=len(t.states), status=t.status,
                          reason=t.reason, final_rms_mm=t.score) for t in tracks])
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for case in ast.CASES:
        outputs[case] = render_case(case, args.output)
        print('Rendered', case, outputs[case]['frames'], 'frames', outputs[case]['bytes'], 'bytes', flush=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=sc.ROOT, text=True).strip()
    sc.write(args.output / 'manifest.json', dict(new_field_solves=0, coefficient_interpolation=False,
        all_saved_accepted_states_shown=True, renderer_sha256=sc.digest(Path(__file__)), commit=head,
        outputs=outputs))


if __name__ == '__main__':
    main()
