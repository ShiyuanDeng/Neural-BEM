#!/usr/bin/env python3
"""Automatic unknown-topology inversions and trajectory videos.

``--chart radial`` is the iteration-02 radial-Fourier controller.  ``--chart
cartesian`` runs the identical cases, data and budgets with every accepted
component held as a polar-angle Cartesian Fourier curve, gauge-fixed after
every retraction.  The two differ only in the chart, so their bundles compare
directly.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter

os.environ.setdefault('MPLCONFIGDIR', '/tmp/topology-matplotlib')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
import run_radial_fourier_topology_inverse as baseline
from ordered_boundary import OrderedBoundary2D, ellipse
from sdf_bem_multicomponent import predict_multicomponent_kress_paired_boundary_response
from sdf_inverse import ComplexScatteredData, MultiRadialFourierState, circle_radial_fourier_state
from sdf_inverse.curve_updates import RadialFourierCurveState
from sdf_inverse.explicit_fourier import CartesianFourierCurveState
from sdf_inverse.experiment_record import source_provenance
from sdf_inverse.work_accounting import accounted_call, collect_work
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, TopologyFrame, component_parameterization, run_topology_aware_fourier_inverse,
    state_in_chart, topology_objective,
)

CASES = ('repeated-birth', 'death', 'split', 'merge', 'mixed')
CHARTS = ('radial', 'cartesian')
DEFAULT_OUTPUT_ROOT = {'radial': Path('results/inverse/radial_fourier/topology_controller'),
                       'cartesian': Path('results/inverse/cartesian_fourier/topology_controller')}


def circle(x, y, radius, cid):
    return circle_radial_fourier_state((x, y), radius, cid)


def peanut(cid):
    return RadialFourierCurveState(np.array([.5, .5]), np.array([.067, 0., .035]),
                                  np.zeros(3), cid)


def case_spec(name, demonstration='original', chart='radial'):
    """The case's initial state, truth curves and truth components.

    ``chart`` re-expresses only the *initial* state.  Truth geometry, the
    oracle and every budget are identical across charts, so a Cartesian run is
    a chart substitution and not a different experiment.
    """
    initial, truth, circles = _case_spec(name, demonstration)
    return state_in_chart(initial, chart), truth, circles


def _case_spec(name, demonstration='original'):
    a, b = circle(.44, .50, .033, 'truth.A'), circle(.56, .50, .033, 'truth.B')
    visible = demonstration == 'visible-refinement'
    if visible:
        a, b = circle(.44, .50, .0317, 'truth.A'), circle(.56, .50, .0361, 'truth.B')
    if name == 'repeated-birth':
        truth = (circle(.43, .455, .028, 'truth.A'), circle(.58, .46, .03, 'truth.B'),
                 circle(.505, .60, .027, 'truth.C'))
        if visible:
            truth = (circle(.43, .455, .0273, 'truth.A'), circle(.58, .46, .0317, 'truth.B'),
                     circle(.505, .60, .0259, 'truth.C'))
        initial = None
    elif name == 'death':
        truth = (a, b)
        initial = MultiRadialFourierState((replace(a, component_id='initial.A'),
            replace(b, component_id='initial.B'), circle(.50, .62, .023, 'spurious')))
    elif name in ('split', 'mixed'):
        truth = (a, b)
        initial = MultiRadialFourierState((peanut('parent'),) +
            ((circle(.5, .65, .023, 'spurious'),) if name == 'mixed' else ()))
        if visible and name == 'split':
            # An exact circle with free, initially zero shape modes. The
            # inverse may deform it before asking the controller for a cut.
            initial = MultiRadialFourierState((RadialFourierCurveState(
                np.array([.5, .5]), np.array([.100, 0., 0.]), np.zeros(3), 'large_circle'),))
    elif name == 'merge':
        return MultiRadialFourierState((circle(.45, .5, .033, 'left'), circle(.55, .5, .033, 'right'))), (
            ellipse((.5, .5), .092, .039, component_id='truth.connected'),), None
    else:
        raise ValueError(name)
    return initial, tuple(component_parameterization(c) for c in truth), truth


def serialize_state(state):
    if state is None:
        return None
    return [dict(component_id=c.component_id, chart='cartesian' if isinstance(c, CartesianFourierCurveState) else 'radial',
                 parameters=MultiRadialFourierState((c,)).parameter_vector(), maximum_mode=c.maximum_mode)
            for c in state.components]


def deserialize_state(records):
    if records is None:
        return None
    components = []
    for record in records:
        k, values = record['maximum_mode'], np.asarray(record['parameters'])
        if record['chart'] == 'cartesian':
            n = 2 * (k + 1)
            component = CartesianFourierCurveState(values[:n].reshape(-1, 2),
                np.vstack((np.zeros(2), values[n:].reshape(-1, 2))), record['component_id'])
        elif record['chart'] == 'radial':
            seed = RadialFourierCurveState(np.array([.5, .5]), np.r_[.03, np.zeros(k)],
                                          np.zeros(k + 1), record['component_id'])
            component = MultiRadialFourierState((seed,)).from_parameter_vector(values).components[0]
        else:
            raise ValueError(f"Unknown chart: {record['chart']}")
        components.append(component)
    return MultiRadialFourierState(tuple(components))


def write_json(path, value):
    baseline._write_json(path, value)


def render_case(path, title, truth, frames, events, *, show_refinement=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter
    from matplotlib.patches import Polygon
    fig = plt.figure(figsize=(11, 6), facecolor='#f6f8fb')
    grid = fig.add_gridspec(2, 2, width_ratios=(1.4, 1), height_ratios=(3, 1), hspace=.35, wspace=.28)
    ax = fig.add_subplot(grid[:, 0])
    loss_ax = fig.add_subplot(grid[0, 1])
    count_ax = fig.add_subplot(grid[1, 1])
    palette = ('#167d9a', '#ed8735', '#8160ba', '#279d73', '#d64f6a')
    all_ids = list(dict.fromkeys(c.component_id for f in frames if f.state for c in f.state.components))
    colors = {cid: palette[i % len(palette)] for i, cid in enumerate(all_ids)}
    losses = [max(f.loss, 1e-14) for f in frames]
    counts = [0 if f.state is None else len(f.state.components) for f in frames]
    truth_points = [c.discretize(512).points for c in truth]
    all_points = np.concatenate(truth_points + [component_parameterization(c).discretize(128).points
                                for f in frames if f.state for c in f.state.components])
    lower = np.minimum((.32, .32), np.min(all_points, axis=0) - .015)
    upper = np.maximum((.69, .70), np.max(all_points, axis=0) + .015)
    event_seeds = {}
    for frame in frames:
        if 'accepted' in frame.label and frame.state:
            for c in frame.state.components:
                event_seeds.setdefault(c.component_id, c)
    def draw(index):
        frame = frames[index]
        ax.clear(); loss_ax.clear(); count_ax.clear()
        for i, p in enumerate(truth_points):
            closed = np.vstack((p, p[0]))
            ax.plot(*closed.T, '--', color='#24344a', lw=2, label='Truth' if i == 0 else None)
        if frame.state:
            for c in frame.state.components:
                if show_refinement and c.component_id in event_seeds:
                    seed = component_parameterization(event_seeds[c.component_id]).discretize(512).points
                    ax.plot(*np.vstack((seed, seed[0])).T, ':', color=colors[c.component_id], alpha=.65, lw=1.7)
                p = component_parameterization(c).discretize(512).points
                ax.add_patch(Polygon(p, facecolor=colors[c.component_id], alpha=.16))
                label = c.component_id
                if show_refinement and not isinstance(c, CartesianFourierCurveState) and c.maximum_mode == 1:
                    label += f' | r={1000 * c.mean_radius_m:.3f} mm'
                ax.plot(*np.vstack((p, p[0])).T, color=colors[c.component_id], lw=2.5, label=label)
        ax.set(xlim=(lower[0], upper[0]), ylim=(lower[1], upper[1]), aspect='equal', xlabel='x (m)', ylabel='y (m)')
        ax.grid(alpha=.15)
        ax.legend(loc='lower left', fontsize=7)
        ax.set_title(f'{counts[index]} material component(s) | {frame.label}', fontsize=12, pad=12)
        loss_ax.semilogy(range(len(frames)), losses, color='#d6dce6', lw=1.5)
        loss_ax.semilogy(range(index + 1), losses[:index + 1], color='#167d9a', lw=2)
        loss_ax.scatter(index, losses[index], color='#ed8735', zorder=5)
        loss_ax.set(title='Actual Kress data objective', xlabel='Accepted trajectory state', ylabel='J')
        loss_ax.grid(alpha=.2)
        count_ax.step(range(index + 1), counts[:index + 1], where='post', color='#8160ba', lw=2)
        count_ax.set(xlim=(0, max(1, len(frames) - 1)), ylim=(-.3, max(counts) + .5),
                     yticks=range(max(counts) + 1), ylabel='Count', xlabel='Accepted trajectory state')
        count_ax.grid(alpha=.15)
        fig.suptitle(f'Automatic Fourier topology inversion — {title}', fontsize=16, x=.51, y=.98)
        if show_refinement:
            ax.text(.02, .98, 'Solid: current   Dashed: truth\nDotted: accepted topology seed',
                    transform=ax.transAxes, va='top', fontsize=8)
    writer = FFMpegWriter(fps=10, bitrate=1800, metadata={'title': title})
    with writer.saving(fig, str(path / 'inversion.mp4'), dpi=120):
        for index, frame in enumerate(frames):
            draw(index)
            hold = 24 if index in (0, len(frames) - 1) or 'accepted' in frame.label else (10 if show_refinement else 5)
            for _ in range(hold):
                writer.grab_frame()
    draw(len(frames) - 1)
    fig.savefig(path / 'final.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


def run_case(name, output, args):
    path = output / name
    path.mkdir(parents=True, exist_ok=False)
    initial, truth, circles = case_spec(name, args.demonstration, args.chart)
    quick = args.profile == 'quick'
    production, refined = baseline._geometry_config(48 if quick else 64), baseline._geometry_config(96 if quick else 128)
    solve = baseline.iteration01_solve_config()
    frequencies = np.array([.5e9])
    problem = baseline._problem(frequencies)
    if circles is not None:
        observed = baseline._oracle_response(np.array([c.center for c in circles]),
            np.array([c.mean_radius_m for c in circles]), frequencies,
            component_ids=tuple(c.component_id for c in circles))
        oracle = 'independent cylindrical harmonics'
    else:
        observed = predict_multicomponent_kress_paired_boundary_response(
            OrderedBoundary2D(tuple(c.discretize(256) for c in truth)), problem, solve_config=solve).scattered_response
        oracle = '256-node Kress analytic truth'
    data = ComplexScatteredData(problem, observed)
    config = TopologyControllerConfig(raster_size=81 if quick else 121,
        fixed_iterations=12 if quick else 22, candidate_refinement_iterations=3,
        maximum_cycles=10, maximum_events=7, relative_error_tolerance=.003, chart=args.chart)
    config = replace(config,
        include_simplest_candidate=getattr(args, 'include_simplest_candidate', False),
        candidates_refined_per_group=getattr(args, 'candidates_refined_per_group', 1),
        candidate_refinement_iterations=getattr(args, 'candidate_refinement_iterations', 3))
    if args.demonstration == 'visible-refinement':
        config = replace(config, candidate_refinement_iterations=0,
                         birth_radius_grid_m=(.016, .024, .036, .048),
                         split_seed_radius_factors=(1., .75, .5))
    write_json(path / 'manifest.json', dict(case=name, demonstration=args.demonstration,
        provenance=source_provenance(Path(__file__).resolve().parent),
        chart=args.chart, controller=asdict(config), oracle=oracle,
        frequencies_hz=frequencies, production_nodes=production.num_nodes, refined_nodes=refined.num_nodes,
        initial_state=serialize_state(initial), truth_state=None if circles is None else serialize_state(MultiRadialFourierState(circles)),
        supplied_target_count=False, supplied_event_policy=False))
    np.savez_compressed(path / 'observations.npz', observed=observed, source_points=problem.source_points,
                        receiver_points=problem.receiver_points, frequencies_hz=frequencies)
    def progress(frame):
        print(f'{name}: cycle={frame.cycle} {frame.label} M={0 if frame.state is None else len(frame.state.components)} J={frame.loss:.6g}', flush=True)
        write_json(path / 'checkpoint.json', dict(cycle=frame.cycle, label=frame.label,
                   loss=frame.loss, state=serialize_state(frame.state)))
    def workspace(cycle, w):
        np.savez_compressed(path / f'workspace_{cycle:02d}.npz', points=w.points, material=w.material,
                            addition=w.addition, removal=w.removal)
    started = perf_counter()
    result = run_topology_aware_fourier_inverse(initial, data, production, refined,
        solve_config=solve, config=config, progress_callback=progress, workspace_callback=workspace)
    with collect_work() as audit_work:
        prod_loss, relative = accounted_call('final_production_audit', topology_objective,
                                            result.final_state, data, production, solve)
        refined_loss, refined_relative = accounted_call('final_refined_audit', topology_objective,
                                                       result.final_state, data, refined, solve)
    final_points = np.concatenate([component_parameterization(c).discretize(512).points for c in result.final_state.components]) if result.final_state else np.zeros((0, 2))
    truth_points = np.concatenate([c.discretize(512).points for c in truth])
    if len(final_points):
        from scipy.spatial import cKDTree
        hausdorff = max(cKDTree(final_points).query(truth_points)[0].max(), cKDTree(truth_points).query(final_points)[0].max())
    else:
        hausdorff = None
    metrics = dict(case=name, stop_reason=result.stop_reason, events=result.events,
        evaluation_count=result.evaluation_count, work=result.work,
        final_audit_work=audit_work.snapshot(),
        demonstration=args.demonstration, chart=args.chart,
        final_parameter_count=None if result.final_state is None else result.final_state.parameter_count,
        component_counts=[0 if initial is None else len(initial.components)] + [len(e['after_ids']) for e in result.events],
        final_relative_error=relative, refined_relative_error=refined_relative,
        final_loss=prod_loss, refined_loss=refined_loss, hausdorff_m=hausdorff,
        elapsed_seconds=perf_counter() - started, final_state=serialize_state(result.final_state))
    write_json(path / 'metrics.json', metrics)
    write_json(path / 'topology_passes.json', result.passes)
    write_json(path / 'trajectory.json', [dict(cycle=f.cycle, label=f.label, loss=f.loss,
        state=serialize_state(f.state)) for f in result.frames])
    if circles is not None:
        searched = sorted(set(trial['birth_radius_m'] for stage in result.passes
                              for trial in stage['trials'] if trial['kind'] == 'birth'))
        radius_audit = dict(searched_birth_radii_m=searched,
            targets=[dict(component_id=c.component_id, radius_m=c.mean_radius_m,
                nearest_searched_radius_distance_m=min((abs(c.mean_radius_m - r) for r in searched), default=None))
                for c in circles], candidate_refinement_iterations=config.candidate_refinement_iterations)
        write_json(path / 'radius_audit.json', radius_audit)
    if not args.skip_video:
        render_case(path, f'{name} ({args.chart} chart)', truth, result.frames, result.events,
                    show_refinement=args.demonstration == 'visible-refinement')
    print(json.dumps({k: metrics[k] for k in ('case', 'stop_reason', 'component_counts', 'final_relative_error', 'hausdorff_m')}, default=float), flush=True)
    return metrics


def write_suite_summary(output):
    """Index completed cases, including separately launched case processes."""
    metrics = [json.loads((output / name / 'metrics.json').read_text())
               for name in CASES if (output / name / 'metrics.json').exists()]
    write_json(output / 'suite_metrics.json', metrics)
    chart = next((item.get('chart', 'radial') for item in metrics), 'radial')
    rows = [f'# Automatic Fourier topology inversions — {chart} chart', '',
            'The same controller receives data and initial geometry, with no target count or event policy.', '']
    if chart == 'cartesian':
        rows += ['Every accepted component is a polar-angle Cartesian Fourier curve, re-expressed '
                 'in its own polar angle after each retraction. The cases, observations, oracle and '
                 'budgets are those of the radial bundle, so the two compare directly.', '']
    rows += ['| Case / inversion video | Component counts | Relative data error | Sampled Hausdorff (mm) | Parameters | Stop |',
             '|---|---|---:|---:|---:|---|']
    for item in metrics:
        name = item['case']
        counts = ' → '.join(map(str, item['component_counts']))
        distance = '—' if item['hausdorff_m'] is None else f"{1000 * item['hausdorff_m']:.4g}"
        parameters = item.get('final_parameter_count') or '—'
        artifact = 'inversion.mp4' if (output / name / 'inversion.mp4').exists() else 'metrics.json'
        rows.append(f"| [{name}]({name}/{artifact}) | {counts} | {item['final_relative_error']:.3g} "
                    f"| {distance} | {parameters} | {item['stop_reason']} |")
    completed = [item['case'] for item in metrics]
    if len(completed) >= 2 and all((output / name / 'inversion.mp4').exists() for name in completed):
        playlist = output / 'video_playlist.txt'
        playlist.write_text(''.join(f"file '{name}/inversion.mp4'\n" for name in completed))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0',
                        '-i', str(playlist), '-c', 'copy', '-movflags', '+faststart',
                        str(output / 'topology_changes.mp4')], check=True)
        rows += ['', f'[Watch all {len(completed)} inversions](topology_changes.mp4).']
    if any(item.get('demonstration') == 'visible-refinement' for item in metrics):
        rows += ['', 'The visible-refinement demonstrations use a fixed 16/24/36/48-mm birth ladder '
                 'and zero candidate-refinement steps. Normal LM updates begin after the raw topology '
                 'seed is accepted and every update appears in the video. Dotted curves retain the accepted seeds. '
                 'See each case’s `radius_audit.json` for the exact searched radii and target offsets. '
                 'The split starts with a 100-mm-radius circle and tests smaller circular seeds from its cut regions.']
    rows += ['', 'Each case contains `manifest.json`, `metrics.json`, `trajectory.json`, '
             '`topology_passes.json`, observations and sensitivity rasters. When rendered, videos contain actual accepted '
             'states; topology transitions are discrete. Both production and refined objectives must improve.', '',
             'These are noiseless, same-material, 0.5-GHz demonstrations. Nested holes and touching boundaries '
             'are unsupported. Generated videos and array files follow the repository’s existing Git-ignore policy.', '']
    (output / 'README.md').write_text('\n'.join(rows))
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('all',) + CASES, default='all')
    parser.add_argument('--profile', choices=('quick', 'full'), default='full')
    parser.add_argument('--demonstration', choices=('original', 'visible-refinement'), default='original')
    parser.add_argument('--chart', choices=CHARTS, default='radial',
                        help='Chart every accepted component is held in.')
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--skip-video', action='store_true')
    parser.add_argument('--candidates-refined-per-group', type=int, default=1)
    parser.add_argument('--candidate-refinement-iterations', type=int, default=3)
    parser.add_argument('--include-simplest-candidate', action='store_true',
                        help='Also refine the simplest family if the best raw candidate has more optimization directions.')
    parser.add_argument('--render-only', action='store_true', help='Render existing saved trajectories without rerunning inversions.')
    args = parser.parse_args()
    output = args.output or DEFAULT_OUTPUT_ROOT[args.chart] / datetime.now().strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=True)
    metrics = []
    for name in CASES if args.case == 'all' else (args.case,):
        if args.render_only:
            path = output / name
            records = json.loads((path / 'trajectory.json').read_text())
            frames = tuple(TopologyFrame(deserialize_state(r['state']), r['loss'], r['label'], r['cycle']) for r in records)
            metric = json.loads((path / 'metrics.json').read_text())
            manifest = json.loads((path / 'manifest.json').read_text())
            demonstration = manifest.get('demonstration', 'original')
            chart = manifest.get('chart', 'radial')
            truth_state = deserialize_state(manifest.get('truth_state'))
            truth = (tuple(component_parameterization(c) for c in truth_state.components)
                     if truth_state is not None else case_spec(name, demonstration, chart)[1])
            render_case(path, f'{name} ({chart} chart)', truth, frames, metric['events'],
                        show_refinement=demonstration == 'visible-refinement')
            metrics.append(metric)
        else:
            metrics.append(run_case(name, output, args))
        write_suite_summary(output)
    return 0 if all(item['stop_reason'] == 'recovered' for item in metrics) else 1

if __name__ == '__main__':
    raise SystemExit(main())
