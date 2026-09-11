#!/usr/bin/env python3
"""TOP-001: saved split replays with declared candidate-refinement budgets."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

for _variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_variable, '1')

import numpy as np
from scipy.spatial import cKDTree

import run_radial_fourier_topology_inverse as baseline
from run_fourier_topology_controller import (
    case_spec, deserialize_state, serialize_state, write_json,
)
from sdf_inverse import ComplexScatteredData
from sdf_inverse.experiment_record import source_provenance
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, component_parameterization, run_topology_aware_fourier_inverse,
    topology_objective,
)
from sdf_inverse.work_accounting import accounted_call, collect_work

ROOT = Path(__file__).resolve().parent
REFERENCES = {
    'radial': ROOT / 'results/inverse/radial_fourier/topology_controller/iteration-02-20260909/split',
    'cartesian': ROOT / 'results/validation/cartesian_fourier/pipeline-audit-20260910/controller/split',
}
ARMS = {'A': (1, 3), 'B': (2, 3), 'C': (2, 1)}
MAGNITUDES = (0., 1e-4, 1e-3, 1e-2)
SEEDS = (11, 29, 47)
HOLDOUT_HZ = np.array([1.5e9, 2.5e9])


def canonical_event(event):
    """Ignore only the explicit unit seed-scale suffix added after the radial run."""
    if event is None:
        return None
    return dict(kind=event['kind'], parents=list(event['parents']),
                children=list(event['children']),
                construction=event['construction'].removesuffix('; seed_scale=1'))


def samples(state, count=512):
    if state is None:
        return np.empty((0, 2))
    return np.concatenate([component_parameterization(c).discretize(count).points for c in state.components])


def perturbed_state(state, magnitude, seed, chart):
    if magnitude == 0:
        return state, dict(magnitude=0., seed=None, parameter_delta_norm_m=0., sampled_displacement_maximum_m=0.)
    rng = np.random.default_rng(seed)
    basis = state.gauge_tangent_basis() if chart == 'cartesian' else np.eye(state.parameter_count)
    direction = rng.normal(size=len(basis)) @ basis
    direction /= np.linalg.norm(direction)
    scale = magnitude * np.mean([c.mean_radius_m for c in state.components])
    proposed = state.incremented(scale * direction)
    if chart == 'cartesian':
        proposed, _ = proposed.polar_angle_gauge_fixed()
    return proposed, dict(magnitude=magnitude, seed=seed, isotropic_direction=direction,
        parameter_delta_norm_m=float(np.linalg.norm(proposed.parameter_vector() - state.parameter_vector())),
        sampled_displacement_maximum_m=float(np.max(np.linalg.norm(samples(proposed) - samples(state), axis=1))))


def rejection_class(row):
    if row.get('accepted'):
        return 'accepted'
    if row.get('eligible'):
        return 'eligible_not_selected'
    reason = row.get('reason', row.get('kind', ''))
    if any(text in reason.lower() for text in ('gauge-fixed', 'feature-radius floor', 'unsupported_nested_hole',
                                              'radial fit', 'contour features')):
        return 'representation_restriction'
    if 'too close' in reason or 'cross_resolution_margin_failed' in reason:
        return 'numerical_resolution_failure'
    if reason == 'production_objective_not_decreased':
        return 'poor_objective_value'
    if any(text in reason.lower() for text in ('intersect', 'touch', 'self intersection')):
        return 'geometric_inadmissibility'
    return 'unclassified'


def summarize_rejections(passes):
    rows = [dict(stage=stage['cycle'], source=source, classification=rejection_class(row), **row)
            for stage in passes for source in ('trials', 'rejected_masks') for row in stage[source]]
    return dict(counts=dict(Counter(row['classification'] for row in rows)),
                unclassified=[row for row in rows if row['classification'] == 'unclassified'],
                polish_failures=[row for row in rows if 'polish_reason' in row], rows=rows)


def load_reference(chart):
    path = REFERENCES[chart]
    manifest = json.loads((path / 'manifest.json').read_text())
    trajectory = json.loads((path / 'trajectory.json').read_text())
    frame = next(row for row in trajectory if row['label'] == 'before split')
    state = deserialize_state(frame['state'])
    config = TopologyControllerConfig(**dict(manifest['controller'], chart=chart))
    observed_arrays = np.load(path / 'observations.npz')
    problem = baseline._problem(observed_arrays['frequencies_hz'])
    # The saved acquisition must agree exactly; never silently regenerate training data.
    np.testing.assert_array_equal(problem.source_points, observed_arrays['source_points'])
    np.testing.assert_array_equal(problem.receiver_points, observed_arrays['receiver_points'])
    data = ComplexScatteredData(problem, observed_arrays['observed'])
    historical = json.loads((path / 'metrics.json').read_text())
    return state, config, data, historical, manifest


def audit_geometry(final, truth):
    predicted, exact = samples(final), np.concatenate([c.discretize(512).points for c in truth])
    if not len(predicted):
        return dict(hausdorff_m=None, geometry_relative_l2=None)
    distances = np.r_[cKDTree(predicted).query(exact)[0], cKDTree(exact).query(predicted)[0]]
    return dict(hausdorff_m=float(np.max(distances)),
                geometry_relative_l2=float(np.sqrt(np.mean(distances**2)) / .033))


def run_replay(output, chart, arm, magnitude, seed, *, historical=False, provenance=None):
    frozen, settings, data, reference_metrics, reference_manifest = load_reference(chart)
    initial, perturbation = perturbed_state(frozen, magnitude, seed, chart)
    count, iterations = ARMS[arm]
    config = replace(settings, candidates_refined_per_group=count, candidate_refinement_iterations=iterations,
                     maximum_candidates_per_type=settings.maximum_candidates_per_type if historical else 48)
    relative = Path('historical' if historical else 'comparison') / chart / arm / f'm{magnitude:g}-s{seed if magnitude else 0}'
    path = output / relative
    path.mkdir(parents=True, exist_ok=False)
    truth = case_spec('split')[1]
    solve = baseline.iteration01_solve_config()
    production, refined = baseline._geometry_config(64), baseline._geometry_config(128)
    input_hashes = {name: hashlib.sha256((REFERENCES[chart] / name).read_bytes()).hexdigest()
                    for name in ('manifest.json', 'trajectory.json', 'metrics.json', 'observations.npz')}
    manifest = dict(experiment_id='TOP-001', chart=chart, arm=arm, historical_qualification=historical,
        perturbation=perturbation, controller=asdict(config), source_provenance=provenance,
        reference=str(REFERENCES[chart].relative_to(ROOT)), input_sha256=input_hashes,
        frozen_state=serialize_state(frozen), initial_state=serialize_state(initial),
        production_geometry=asdict(production), refined_geometry=asdict(refined), solve_config=asdict(solve),
        holdout_frequencies_hz=HOLDOUT_HZ, holdout_role='evaluation only; never enters inverse',
        geometry_metric='symmetric nearest-boundary RMS / 0.033m; 512 samples per component',
        recorded_historical_candidate_cap=reference_manifest['controller']['maximum_candidates_per_type'])
    write_json(path / 'manifest.json', manifest)
    write_json(path / 'observations.json', dict(problem=asdict(data.forward_problem),
        observed_real=data.observed_scattered_response.real, observed_imag=data.observed_scattered_response.imag,
        frequency_weights=data.frequency_weights))
    frames = []
    def progress(frame):
        frames.append(dict(cycle=frame.cycle, label=frame.label, loss=frame.loss, state=serialize_state(frame.state)))
        write_json(path / 'checkpoint.json', frames[-1])
    started = perf_counter()
    print(f'START {relative}', flush=True)
    result = run_topology_aware_fourier_inverse(initial, data, production, refined, solve_config=solve,
        config=config, replay_first_event=True, progress_callback=progress)
    inverse_seconds = perf_counter() - started
    write_json(path / 'trajectory.json', frames)
    write_json(path / 'topology_passes.json', result.passes)
    rejection_summary = summarize_rejections(result.passes)
    write_json(path / 'rejections.json', rejection_summary)
    with collect_work() as audit_work:
        training = accounted_call('training_audit', topology_objective, result.final_state, data, production, solve)
        refined_training = accounted_call('refined_training_audit', topology_objective, result.final_state, data, refined, solve)
        holdout_problem = baseline._problem(HOLDOUT_HZ)
        holdout_observed = baseline._oracle_response(np.array([[.44, .5], [.56, .5]]), np.array([.033, .033]),
                                                    HOLDOUT_HZ, component_ids=('truth.A', 'truth.B'))
        holdout = ComplexScatteredData(holdout_problem, holdout_observed)
        holdout_loss, holdout_relative = accounted_call('holdout_audit', topology_objective,
            result.final_state, holdout, refined, solve)
    write_json(path / 'holdout_observations.json', dict(problem=asdict(holdout_problem),
        observed_real=holdout_observed.real, observed_imag=holdout_observed.imag))
    event = canonical_event(result.events[0] if result.events else None)
    metrics = dict(experiment_id='TOP-001', path=str(relative), chart=chart, arm=arm,
        magnitude=magnitude, seed=seed if magnitude else None, historical_qualification=historical,
        stop_reason=result.stop_reason, events=result.events, first_event=event,
        historical_event_match=event == canonical_event(reference_metrics['events'][0]),
        historical_final_loss=reference_metrics['final_loss'],
        final_loss=training[0], final_relative_error=training[1], refined_relative_error=refined_training[1],
        holdout_relative_error=holdout_relative, holdout_loss=holdout_loss,
        evaluation_count=result.evaluation_count, work=result.work, final_audit_work=audit_work.snapshot(),
        rejection_counts=rejection_summary['counts'], inverse_seconds=inverse_seconds,
        final_state=serialize_state(result.final_state), **audit_geometry(result.final_state, truth))
    write_json(path / 'metrics.json', metrics)
    print(json.dumps({key: metrics[key] for key in ('path', 'historical_event_match', 'stop_reason',
        'final_relative_error', 'holdout_relative_error', 'hausdorff_m', 'evaluation_count', 'inverse_seconds')}), flush=True)
    return metrics


def write_summary(output):
    rows = [json.loads(p.read_text()) for p in sorted((output / 'comparison').glob('*/*/*/metrics.json'))]
    zeros = {(row['chart'], row['arm']): row for row in rows if row['magnitude'] == 0}
    matched = {(row['chart'], row['magnitude'], row['seed']): row for row in rows if row['arm'] == 'A'}
    comparisons = []
    for row in rows:
        reference = zeros.get((row['chart'], row['arm']))
        row['event_matches_unperturbed'] = None if reference is None else row['first_event'] == reference['first_event']
        control = matched.get((row['chart'], row['magnitude'], row['seed']))
        if control is not None and row['arm'] != 'A':
            def counts(item, stage=None):
                work = item['work']
                return (work['totals']['bie_frequency_solve_count'] if stage is None else
                        work['stages'].get(stage, {}).get('forward_frequency_solve_count', 0))
            comparisons.append(dict(chart=row['chart'], arm=row['arm'], magnitude=row['magnitude'], seed=row['seed'],
                event_changed=row['first_event'] != control['first_event'],
                geometry_improved=row['hausdorff_m'] is not None and control['hausdorff_m'] is not None and
                                  row['hausdorff_m'] < control['hausdorff_m'],
                bie_solves=counts(row), baseline_bie_solves=counts(control),
                refinement_bie_solves=counts(row, 'candidate_refinement'),
                baseline_refinement_bie_solves=counts(control, 'candidate_refinement'),
                matched_cost=counts(row) <= counts(control) and
                             counts(row, 'candidate_refinement') <= counts(control, 'candidate_refinement')))
    stability = []
    for chart in REFERENCES:
        for arm in ARMS:
            for magnitude in MAGNITUDES[1:]:
                selected = [row for row in rows if (row['chart'], row['arm'], row['magnitude']) == (chart, arm, magnitude)]
                if selected:
                    matched_events = [row['event_matches_unperturbed'] for row in selected
                                      if row['event_matches_unperturbed'] is not None]
                    stability.append(dict(chart=chart, arm=arm, magnitude=magnitude, replay_count=len(selected),
                        fraction_same_event=None if not matched_events else float(np.mean(matched_events))))
    summary = dict(completed=len(rows), expected=60, rows=rows, comparisons=comparisons, stability=stability)
    write_json(output / 'suite_metrics.json', summary)
    lines = ['# TOP-001 candidate-refinement allocation', '',
             f'{len(rows)} / 60 comparison replays complete. See `suite_metrics.json` for every paired comparison.', '',
             'A: best one × 3 LM steps. B: best two × 3. C: best two × 1. Candidate cap 48 in both charts.', '',
             '| Chart | Arm | Magnitude | Seed | Train L2 | Holdout L2 | Hausdorff (µm) | BIE frequency solves |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        distance = '—' if row['hausdorff_m'] is None else f"{row['hausdorff_m'] * 1e6:.6g}"
        lines.append(f"| {row['chart']} | [{row['arm']}]({row['path']}/metrics.json) | {row['magnitude']:g} | "
            f"{row['seed']} | {row['final_relative_error']:.5g} | {row['holdout_relative_error']:.5g} | "
            f"{distance} | {row['work']['totals']['bie_frequency_solve_count']} |")
    lines += ['', 'Work counts exclude final audits and the independent oracle. BIE counts combine completed',
              'objective frequency solves and TD frequency solves (the latter have twice the source RHSs).',
              'Objective calls rejected before a completed BIE prediction remain in `evaluation_count`.',
              'Counts are not weighted for different component/node counts. No controlled wall-time claim.', '']
    (output / 'README.md').write_text('\n'.join(lines))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path,
                        help='Qualified B0 reruns, containing radial/split and cartesian/split.')
    parser.add_argument('--phase', choices=('references', 'comparison', 'all', 'summary'), default='all')
    parser.add_argument('--chart', choices=('both', 'radial', 'cartesian'), default='both')
    parser.add_argument('--magnitudes', type=float, nargs='+', default=MAGNITUDES)
    parser.add_argument('--seeds', type=int, nargs='+', default=SEEDS)
    parser.add_argument('--arms', choices=tuple(ARMS), nargs='+', default=tuple(ARMS))
    parser.add_argument('--maximum-seconds', type=float, default=7200.)
    args = parser.parse_args(argv)
    if args.reference_root:
        for chart in REFERENCES:
            REFERENCES[chart] = args.reference_root.resolve() / chart / 'split'
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    if args.phase == 'summary':
        write_summary(output)
        return 0
    if any(m not in MAGNITUDES for m in args.magnitudes) or any(s not in SEEDS for s in args.seeds):
        parser.error('Only predeclared magnitudes and seeds are allowed for TOP-001.')
    provenance = source_provenance(ROOT)
    manifest_path = output / 'manifest.json'
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text())
        if saved['source_provenance']['source_sha256'] != provenance['source_sha256']:
            raise ValueError('Source hashes changed; use a fresh experiment directory.')
        if saved['references'] != {chart: str(path.relative_to(ROOT)) for chart, path in REFERENCES.items()}:
            raise ValueError('Reference bundle changed; use a fresh experiment directory.')
    else:
        write_json(manifest_path, dict(experiment_id='TOP-001', created_utc=datetime.now(timezone.utc).isoformat(),
            source_provenance=provenance, arms=ARMS, magnitudes=MAGNITUDES, seeds=SEEDS,
            references={chart: str(path.relative_to(ROOT)) for chart, path in REFERENCES.items()},
            candidate_cap=48, maximum_seconds=args.maximum_seconds,
            concurrency='one replay per process; external concurrent launches must be separately declared',
            thread_environment={key: os.environ.get(key) for key in
                ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}))
    started = perf_counter()
    charts = tuple(REFERENCES) if args.chart == 'both' else (args.chart,)
    for chart in charts:
        path = output / 'historical' / chart / 'A' / 'm0-s0' / 'metrics.json'
        if args.phase in ('references', 'all') and not path.exists():
            run_replay(output, chart, 'A', 0., SEEDS[0], historical=True, provenance=provenance)
        if not path.exists() or not json.loads(path.read_text())['historical_event_match']:
            write_json(output / f'replay_gate_{chart}.json', dict(passed=False,
                reason='Historical event missing or not reproduced; comparison not launched.'))
            return 2
    if args.phase == 'references':
        return 0
    for chart in charts:
        for magnitude in args.magnitudes:
            for seed in (SEEDS[0],) if magnitude == 0 else args.seeds:
                for arm in args.arms:
                    if perf_counter() - started > args.maximum_seconds:
                        write_summary(output)
                        return 3
                    path = output / 'comparison' / chart / arm / f'm{magnitude:g}-s{seed if magnitude else 0}' / 'metrics.json'
                    if path.exists():
                        continue
                    run_replay(output, chart, arm, magnitude, seed, provenance=provenance)
                    write_summary(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
