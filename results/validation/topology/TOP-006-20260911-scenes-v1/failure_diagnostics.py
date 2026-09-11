"""Visualize saved pre-exception states; no inverse or forward solves."""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))
import run_topology_scene_benchmark as benchmark


def main():
    spec = benchmark.read(HERE / 'scene_spec.json')
    requested = next(s for s in spec['scenes'] if s['id']=='far-ellipse-star')
    for failure_path in sorted(HERE.glob('runs/*/*/failure.json')):
        path = failure_path.parent
        if not (path / 'checkpoint.json').exists():
            continue
        scene = next(s for s in spec['scenes'] if s['id']==path.name)
        checkpoint = benchmark.read(path / 'checkpoint.json')
        state = benchmark.driver.deserialize_state(checkpoint['state'])
        geometry = benchmark.geometry_metrics(state, scene, spec)
        result = dict(scene=scene['id'], arm=path.parent.name,
            status='failed run: last saved accepted state, not a successful reconstruction',
            geometry=geometry, last_saved_loss=checkpoint['loss'],
            completed_bie_solve_lower_bound=checkpoint['work']['totals']['bie_frequency_solve_count'],
            no_forward_or_inverse_solves_for_this_diagnostic=True,
            full_candidate_trials_unavailable_after_controller_exception=True)
        benchmark.driver.write_json(path / 'failure_diagnostics.json', result)
        if scene['id']=='far-ellipse-star' and not (path / 'inversion.mp4').exists():
            records = [json.loads(line) for line in (path / 'progress.jsonl').read_text().splitlines()]
            frames = [benchmark.TopologyFrame(benchmark.driver.deserialize_state(r['state']),
                r['loss'], r['label'], r['cycle']) for r in records]
            last = frames[-1]
            frames[-1] = benchmark.TopologyFrame(last.state, last.loss,
                'FAILED — last saved state before geometry error', last.cycle)
            benchmark.driver.render_case(path, f'FAILED distant ellipse/star / {path.parent.name}',
                                         benchmark.truth_curves(scene), frames, ())
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), constrained_layout=True)
    benchmark.plot_geometry(axes[0], requested, None, benchmark.initial_state(requested))
    axes[0].set_title('Starting circle and targets')
    axes[0].legend(fontsize=8)
    for ax, arm in zip(axes[1:], benchmark.ARMS):
        path = HERE / 'runs' / arm / requested['id']
        record = benchmark.read(path / 'checkpoint.json')
        state = benchmark.driver.deserialize_state(record['state'])
        benchmark.plot_geometry(ax, requested, state)
        ax.set_title(f"{'Default A' if arm=='A' else 'Selective F'} — FAILED\nLast saved state: {len(state.components)} objects")
    fig.suptitle('Distant circle to ellipse + star: both policies hit an unsupported inferred separation')
    fig.savefig(HERE / 'far_ellipse_star_failure.svg')
    fig.savefig(HERE / 'far_ellipse_star_failure.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
