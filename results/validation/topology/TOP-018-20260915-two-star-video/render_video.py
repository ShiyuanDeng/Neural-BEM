"""Animate saved TOP-018 accepted states; sample geometry without physical solves."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUNDLE = HERE.parent / 'TOP-018-20260915-resolution-qualified-pair'
FPS = 24
VIDEO = HERE / 'two_star_S_vs_F.mp4'
os.environ.setdefault('MPLCONFIGDIR', '/tmp/top018-video-matplotlib')
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import run_top017 as m


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_saved():
    sources = {}

    def read(path, jsonl=False):
        sources[str(path.relative_to(ROOT))] = digest(path)
        return ([json.loads(line) for line in path.read_text().splitlines()]
                if jsonl else json.loads(path.read_text()))

    artifact_manifest = read(BUNDLE / 'artifact_manifest.json')
    for name, expected in artifact_manifest.items():
        assert digest(BUNDLE / name) == expected, name
    spec = read(BUNDLE / 'scene_spec.json')
    scene = next(s for s in spec['scenes'] if s['id'] == 'far-two-stars')
    common = read(BUNDLE / 'inputs/far-two-stars/state.json')
    audit = read(BUNDLE / 'phase_a/audit.json')
    catalog = []

    def add(state, path, selector, arm, stage, iteration, score=None):
        state_hash = m.state_hash(state)
        if score is not None:
            assert score['state_sha256'] == state_hash
        catalog.append(dict(state=state, state_sha256=state_hash,
                            source=str(path.relative_to(ROOT)), selector=selector,
                            arm=arm, stage=stage, accepted_update=iteration,
                            score=score))
        return len(catalog) - 1

    first = add(common, BUNDLE / 'inputs/far-two-stars/state.json', 'root',
                'COMMON', None, 0, audit['common_score'])
    stages = {}
    for arm in ('S', 'F'):
        folder = BUNDLE / 'runs' / f'{arm}-far-two-stars'
        metrics = read(folder / 'metrics.json')
        assert metrics['schedule_complete'] and metrics['numerically_qualified']
        assert metrics['initial_state_sha256'] == catalog[first]['state_sha256']
        previous_hash = catalog[first]['state_sha256']
        stages[arm] = {}
        for stage in metrics['stages']:
            n = stage['stage']
            stage_dir = folder / f'stage_{n}'
            initial = read(stage_dir / 'initial_state.json')
            assert m.state_hash(initial) == previous_hash == stage['start_state_sha256']
            path = stage_dir / 'trajectory.jsonl'
            records = read(path, jsonl=True)
            items = []
            for i, row in enumerate(records):
                assert m.state_hash(row['state']) == row['state_sha256']
                items.append(add(row['state'], path, f'line {i + 1}', arm,
                                 n, row['iteration']))
            assert catalog[items[0]]['state_sha256'] == previous_hash
            assert [r['iteration'] for r in records] == sorted(set(r['iteration'] for r in records))
            saved = read(stage_dir / 'accepted_state.json')
            assert m.state_hash(saved['state']) == saved['state_sha256']
            # A quota can stop after acceptance, before the next trajectory record.
            if catalog[items[-1]]['state_sha256'] != saved['state_sha256']:
                items.append(add(saved['state'], stage_dir / 'accepted_state.json',
                                 'state', arm, n, saved['iteration']))
            terminal = read(stage_dir / 'terminal.json')
            previous_hash = catalog[items[-1]]['state_sha256']
            assert previous_hash == terminal['state_sha256'] == stage['score_state_sha256']
            assert previous_hash == m.state_hash(terminal['final_state'])
            assert stage['score']['state_sha256'] == previous_hash
            assert catalog[items[-1]]['accepted_update'] == terminal['accepted_steps']
            catalog[items[-1]]['score'] = stage['score']
            stages[arm][n] = dict(items=items,
                                  frequencies_hz=stage['active_frequencies_hz'],
                                  accepted_updates=terminal['accepted_steps'])
        assert list(stages[arm]) == [2, 3, 4]
        assert previous_hash == metrics['final_state_sha256']
        assert catalog[stages[arm][4]['items'][-1]]['score'] == metrics['final']

    timeline = []

    def append(s, f, stage, chapter, frames=1, final=False):
        row = dict(S=s, F=f, stage=stage, chapter=chapter, final=final)
        if timeline and all(timeline[-1][k] == value for k, value in row.items()):
            timeline[-1]['frames'] += frames
        else:
            timeline.append(dict(row, frames=frames))

    append(first, first, None, 'Identical saved start: two components, fixed throughout', 5 * FPS)
    for n, seconds in ((2, 12), (3, 12), (4, 8)):
        total = seconds * FPS
        for i in range(total):
            pair = {arm: stages[arm][n]['items'][round(i * (len(stages[arm][n]['items']) - 1) / (total - 1))]
                    for arm in ('S', 'F')}
            append(pair['S'], pair['F'], n, f'Stage {n}: saved accepted updates')
        final = n == 4
        chapter = ('Prescribed final states: F passes all recovery gates; S does not'
                   if final else f'Stage {n} endpoints: measured geometry and prediction scores')
        append(stages['S'][n]['items'][-1], stages['F'][n]['items'][-1], n,
               chapter, (7 if final else 3) * FPS, final=final)
    shown = {row[arm] for row in timeline for arm in ('S', 'F')}
    assert shown == set(range(len(catalog))), 'Every saved catalog state must appear'
    assert sum(row['frames'] for row in timeline) == 50 * FPS
    return scene, catalog, stages, timeline, sources, len(artifact_manifest)


def main(preview_only=False):
    scene, catalog, stages, timeline, sources, source_count = load_saved()
    truth = [curve.discretize(1024).points for curve in m.p.benchmark.truth_curves(scene)]
    geometry = [m.p.boundary_points(m.p.driver.deserialize_state(row['state']), 1024)
                for row in catalog]
    assert all(len(curves) == 2 for curves in geometry)
    points = np.concatenate(truth + [xy for curves in geometry for xy in curves])
    lower, upper = points.min(axis=0) - .012, points.max(axis=0) + .012
    bg, ink, muted = '#f5f7fb', '#17283c', '#506176'
    colors = {'S': '#3268b2', 'F': '#008c82'}
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'text.color': ink, 'axes.labelcolor': muted,
                         'xtick.color': muted, 'ytick.color': muted})
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=bg)
    fig.text(.05, .962, 'INVERSE SHAPE RECONSTRUCTION', color=muted, fontsize=10, weight='bold')
    fig.text(.95, .962, 'TOP-018  |  K = 9  |  256/512 nodes', ha='right', fontsize=10, color=muted)
    fig.text(.05, .912, 'Two stars, two frequency schedules', fontsize=26, weight='bold')
    chapter_text = fig.text(.05, .863, '', fontsize=14)
    fig.text(.95, .915, 'Solid: reconstruction\nDashed: target', ha='right', va='center',
             color=muted, fontsize=11, linespacing=1.7)
    panel = {}
    for arm, left, center in (('S', .055, .27), ('F', .515, .73)):
        heading = 'S  |  Single frequency' if arm == 'S' else 'F  |  Cumulative frequencies'
        fig.text(center, .808, heading, ha='center', fontsize=19, weight='bold', color=colors[arm])
        frequencies = fig.text(center, .772, '', ha='center', fontsize=12)
        ax = fig.add_axes((left + .005, .300, .42, .448), facecolor='white')
        lines = [ax.plot([], [], color=colors[arm], lw=2.7, zorder=3)[0] for _ in range(2)]
        for xy in truth:
            ax.plot(*np.vstack((xy, xy[0])).T, '--', color=ink, lw=1.4, zorder=4)
        ax.set(xlim=(lower[0], upper[0]), ylim=(lower[1], upper[1]), aspect='equal',
               xlabel='x (m)', ylabel='y (m)')
        ax.grid(color='#dfe5ed', lw=.7, alpha=.65)
        for spine in ax.spines.values():
            spine.set_color('#d1dbe7')
        counter = fig.text(center, .221, '', ha='center', fontsize=11, color=muted)
        box = FancyBboxPatch((left + .012, .065), .406, .126,
                             boxstyle='round,pad=0.008,rounding_size=0.01',
                             transform=fig.transFigure, facecolor='white',
                             edgecolor='#dbe3ed', lw=.8, zorder=0)
        fig.add_artist(box)
        badge = fig.text(center, .163, '', ha='center', fontsize=12, weight='bold')
        metric = fig.text(center, .128, '', ha='center', fontsize=12)
        evaluation = fig.text(center, .093, '', ha='center', fontsize=11, color=muted)
        panel[arm] = dict(lines=lines, frequencies=frequencies, counter=counter,
                          badge=badge, metric=metric, evaluation=evaluation)
    fig.text(.5, .023,
             'Saved states only; no coefficient interpolation.  Playback is aligned by stage, not computational time.  Evaluation: 1.5 and 2.5 GHz.',
             ha='center', fontsize=10, color=muted)

    def draw(row):
        chapter_text.set_text(row['chapter'])
        for arm in ('S', 'F'):
            p = panel[arm]
            saved = catalog[row[arm]]
            for line, xy in zip(p['lines'], geometry[row[arm]]):
                closed = np.vstack((xy, xy[0]))
                line.set_data(closed[:, 0], closed[:, 1])
            stage = row['stage']
            if stage is None:
                p['frequencies'].set_text('Common start from 0.5 GHz')
                p['counter'].set_text('Same saved coefficients in both arms')
            else:
                info = stages[arm][stage]
                freq = ', '.join(f'{v / 1e9:g}' for v in info['frequencies_hz'])
                p['frequencies'].set_text(f'Active training: {freq} GHz')
                p['counter'].set_text(f"Stage {stage}  |  Accepted update {saved['accepted_update']} / {info['accepted_updates']}")
            score = saved['score']
            if score is None:
                p['badge'].set_text('Saved accepted state')
                p['badge'].set_color(colors[arm])
                p['metric'].set_text('Geometry and prediction scores appear at endpoints')
                p['evaluation'].set_text('Both components stay at K = 9')
            else:
                passed = score['original_gates_pass']
                label = 'Common-start recovery gates' if stage is None else 'Endpoint recovery gates'
                p['badge'].set_text(f"{label}: {'PASS' if passed else 'FAIL'}")
                p['badge'].set_color('#007e64' if passed else '#946027')
                boundary = 1000 * score['geometry']['maximum_matched_hausdorff_m']
                p['metric'].set_text(f"Boundary error: {boundary:.6g} mm   |   IoU: {score['geometry']['union_iou']:.4f}")
                numerics = 'PASS' if score['numerically_qualified'] else 'FAIL'
                p['evaluation'].set_text(f"Worst evaluation error: {score['maximum_evaluation_error']:.5g}   |   Numerics: {numerics}")
        fig.canvas.draw()

    previews = [timeline[0]] + [row for row in timeline if row['frames'] >= 3 * FPS and row['stage'] is not None]
    for i, row in enumerate(previews):
        draw(row)
        fig.savefig(f'/tmp/top018_video_preview_{i}.png', dpi=100, facecolor=bg)
    if preview_only:
        print(f'Previewed {len(previews)} chapters; {len(catalog)} saved records; all {source_count} source artifacts verified.', flush=True)
        plt.close(fig)
        return

    command = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-vcodec', 'rawvideo',
               '-s', '1600x900', '-pix_fmt', 'rgba', '-r', str(FPS), '-i', '-', '-an',
               '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-threads', '2',
               '-movflags', '+faststart', str(VIDEO)]
    frame_count = 0
    with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
        try:
            for row in timeline:
                draw(row)
                pixels = fig.canvas.buffer_rgba().tobytes()
                for _ in range(row['frames']):
                    encoder.stdin.write(pixels)
                    frame_count += 1
            encoder.stdin.close()
            assert encoder.wait() == 0, 'Video encoding failed'
        except BaseException:
            encoder.kill()
            encoder.wait()
            raise
    fig.savefig(HERE / 'final_comparison.svg', facecolor=bg)
    svg = HERE / 'final_comparison.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    plt.close(fig)
    for path, expected in sources.items():
        assert digest(ROOT / path) == expected, path
    for name, expected in json.loads((BUNDLE / 'artifact_manifest.json').read_text()).items():
        assert digest(BUNDLE / name) == expected, name
    m.write(HERE / 'video_manifest.json', dict(
        scope='Fixed-count TOP-018 S/F pair from saved COMMON; prescribed stage-4 endpoints',
        no_new_numerical_solves=True, coefficient_interpolation=False,
        playback_alignment='stage; uniformly spaced saved records within each arm and stage',
        playback_represents_runtime=False, all_catalog_states_shown=True,
        scores='Only exact saved common-start and stage-endpoint scores',
        source_artifacts_verified_unchanged=source_count,
        frame_count=frame_count, fps=FPS, duration_seconds=frame_count / FPS,
        dimensions=[1600, 900], sources_sha256=sources, state_catalog=catalog,
        timeline=timeline, renderer_sha256=digest(Path(__file__)),
        outputs_sha256={p.name: digest(p) for p in (VIDEO, svg)}))
    print(f'Rendered {frame_count} frames ({frame_count / FPS:g} s); {len(catalog)} saved records; {source_count} source artifacts unchanged.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-only', action='store_true')
    main(parser.parse_args().preview_only)
