"""Read-only numerical-artifact analysis; writes figures, report and checks."""
import hashlib
import ast
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))
import run_topology_scene_benchmark as benchmark


def main():
    data = benchmark.summarize(HERE, render=False)
    spec = benchmark.read(HERE / 'scene_spec.json')
    source = benchmark.read(HERE / 'manifest.json')['source']
    locations = {name: ROOT / name for name in source['source_sha256']}
    archived_driver = HERE / 'executed_run_topology_scene_benchmark.py'
    if archived_driver.exists():
        locations['run_topology_scene_benchmark.py'] = archived_driver
    source_matches = {name: benchmark.digest(locations[name])==value
                      for name, value in source['source_sha256'].items()}
    numerical_functions_unchanged = {}
    if archived_driver.exists():
        def functions(path):
            return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(path.read_text()).body
                    if isinstance(node, ast.FunctionDef)}
        before, after = functions(archived_driver), functions(ROOT/'run_topology_scene_benchmark.py')
        numerical_functions_unchanged = {name:before[name]==after[name] for name in
            ('truth_curves','initial_state','controller_config','relative_columns','scene_geometry_check',
             'geometry_metrics','trajectory_checks','success_gates','verify_source','run_one','run_job')}
    rows = {(r['scene'], r['arm']): r for r in data['metrics']}
    observations_match = {}
    input_initials_match = {}
    expected_gates_match = {}
    control_matches = {}
    for manifest_path in HERE.glob('runs/*/*/manifest.json'):
        manifest = benchmark.read(manifest_path)
        scene_id, arm = manifest['scene'], manifest['arm']
        observations_match[f'{arm}/{scene_id}'] = manifest['observations_sha256']==benchmark.digest(
            HERE / 'scenes' / scene_id / 'observations.json')
        input_initials_match[f'{arm}/{scene_id}'] = manifest['initial_state']==benchmark.read(
            HERE / 'scenes' / scene_id / 'initial_state.json')
    for (scene_id, arm), row in rows.items():
        path = HERE / 'runs' / arm / scene_id
        manifest = benchmark.read(path / 'manifest.json')
        observations_match[f'{arm}/{scene_id}'] = manifest['observations_sha256']==benchmark.digest(
            HERE / 'scenes' / scene_id / 'observations.json')
        input_initials_match[f'{arm}/{scene_id}'] = manifest['initial_state']==benchmark.read(
            HERE / 'scenes' / scene_id / 'initial_state.json')
        frames = [benchmark.TopologyFrame(benchmark.driver.deserialize_state(f['state']),
                  f['loss'], f['label'], f['cycle']) for f in benchmark.read(path / 'trajectory.json')]
        checks = benchmark.trajectory_checks(frames, row['events'], benchmark.controller_config(spec, arm))
        expected = benchmark.success_gates(row['geometry'], row['refined_relative_error'],
                                          max(row['holdout_relative_errors']), checks, spec)
        expected_gates_match[f'{arm}/{scene_id}'] = expected==row['gates'] and all(expected.values())==row['passed']
        if row['group']=='original':
            base = ROOT / 'results/validation/topology'
            old_path = (base / 'TOP-001E-controller-20260911/A' / scene_id / 'metrics.json' if arm=='A'
                        else base / 'TOP-005-20260911/controller/F' / scene_id / 'metrics.json')
            old = benchmark.read(old_path)
            control_matches[f'{arm}/{scene_id}'] = dict(
                same_final_state=old['final_state']==row['final_state'],
                same_solve_count=old['work']['totals']['bie_frequency_solve_count']==row['work']['totals']['bie_frequency_solve_count'],
                same_stop_reason=old['stop_reason']==row['stop_reason'],
                same_training_error=abs(old['final_relative_error']-row['final_relative_error'])<1e-12)
    verification = dict(complete=data['complete'], all_inputs_paired=data['all_inputs_paired'],
        source_matches=source_matches, observations_match=observations_match,
        executed_source_locations={name:str(path.relative_to(ROOT)) for name,path in locations.items()},
        postrun_numerical_functions_unchanged=numerical_functions_unchanged,
        initial_states_match=input_initials_match, rederived_gates_match=expected_gates_match,
        original_control_matches=control_matches,
        oracle_checks=benchmark.read(HERE / 'oracle_checks.json'))
    verification['all_checks_passed'] = (data['complete'] and data['all_inputs_paired'] and
        all(source_matches.values()) and all(observations_match.values()) and
        len(observations_match)==24 and all(numerical_functions_unchanged.values()) and
        all(input_initials_match.values()) and all(expected_gates_match.values()) and
        len(control_matches)==10 and all(all(c.values()) for c in control_matches.values()) and
        all(o['passed'] for o in verification['oracle_checks']))
    benchmark.driver.write_json(HERE / 'verification.json', verification)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)
    positions = np.arange(len(spec['scenes']))
    for arm, offset, color in [('A', -.19, '#62778a'), ('F', .19, '#07877f')]:
        errors, costs, partial = [], [], []
        for scene in spec['scenes']:
            row = rows.get((scene['id'], arm))
            path = HERE/'runs'/arm/scene['id']
            diagnostic = benchmark.read(path/'failure_diagnostics.json') if (path/'failure_diagnostics.json').exists() else None
            geometry = row['geometry'] if row else diagnostic['geometry'] if diagnostic else {}
            error = geometry.get('maximum_matched_hausdorff_m')
            errors.append(np.nan if error is None else max(error*1000, 1e-5))
            costs.append(row['work']['totals']['bie_frequency_solve_count'] if row else
                         diagnostic['completed_bie_solve_lower_bound'] if diagnostic else np.nan)
            partial.append(row is None)
        partial = np.array(partial)
        axes[0].scatter(np.array(errors)[~partial], (positions+offset)[~partial], label=arm, color=color)
        axes[0].scatter(np.array(errors)[partial], (positions+offset)[partial], marker='x', color=color)
        bars = axes[1].barh(positions+offset, costs, height=.35, color=color, label=arm)
        for bar, is_partial in zip(bars, partial):
            if is_partial:
                bar.set_hatch('///'); bar.set_alpha(.45)
    axes[0].axvline(1., color='#b3473f', ls='--', lw=1.4, label='1-mm geometry gate')
    axes[0].set_xscale('log')
    axes[0].set_xlabel('Maximum matched boundary error (mm; log scale)')
    axes[1].set_xlabel('BIE solves; hatched bars are checkpoint lower bounds')
    for ax in axes:
        ax.set_yticks(positions, [s['id'] for s in spec['scenes']])
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=.18)
        ax.legend()
    fig.suptitle('Frozen scenes v1 — crosses show failed-run checkpoints; wrong counts fail separately')
    fig.savefig(HERE / 'error_and_work.svg')
    fig.savefig(HERE / 'error_and_work.png', dpi=140)
    plt.close(fig)

    report = ['# TOP-006 — current automatic controller on twelve frozen scenes', '',
        'This is a measurement of the existing default A and selective F, with no controller changes or scene-specific tuning.', '',
        '**Both policies pass 5/12 scenes.** All 24 declared runs were attempted: fourteen returned '
        'normally, four stopped with a geometry exception, and six reached the ten-minute limit. '
        'Ten normal returns pass all quality gates; the merge and two-star scene fail in both policies.', '',
        'The requested distant 75-mm-radius circle does **not** recover the ellipse and star. '
        'Both policies find their approximate locations but represent them with circles, add a third '
        'small circle, and then fail the refined separation check (9.971 mm against a required >10 mm). '
        'The true objects are separated; the error is in an inferred intermediate geometry. '
        'The last saved state has 0.695 material IoU and 17.59-mm maximum matched boundary error.', '',
        'The same distant initialization succeeds for two circular targets. Two stars also expose '
        'a count-versus-shape distinction: both policies return two circles, with 7.60-mm boundary '
        'error and 100.3% error at the 2.5-GHz holdout. The original merge looks close (0.554-mm '
        'boundary error) but fails the new 5% holdout gate at 9.40%. Its previous qualification was '
        'relative to the old baseline and is preserved, not relabeled retroactively.', '',
        '[Requested distant-circle comparison](far_ellipse_star_failure.svg) · [All initial scenes](initial_scenes.svg) · '
        '[New scene results](new_results.svg) · [Original controls](original_results.svg) · '
        '[Error and work](error_and_work.svg)', '',
        '[Default requested-scene video](runs/A/far-ellipse-star/inversion.mp4) · '
        '[Selective requested-scene video](runs/F/far-ellipse-star/inversion.mp4)', '',
        '## Per-scene outcomes', '',
        '| Scene | Arm | Pass | Objects / truth | Matched error (mm) | Union IoU | Refined train error | Worst holdout error | BIE solves | Stop |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---|']
    for scene in spec['scenes']:
        for arm in benchmark.ARMS:
            row = rows.get((scene['id'], arm))
            if row is None:
                path = HERE/'runs'/arm/scene['id']
                diagnostic = benchmark.read(path/'failure_diagnostics.json') if (path/'failure_diagnostics.json').exists() else None
                reason = benchmark.read(path/'failure.json')['reason'] if (path/'failure.json').exists() else 'pending'
                if diagnostic:
                    g=diagnostic['geometry']; value=g['maximum_matched_hausdorff_m']
                    error='—' if value is None else f'{value*1000:.5g}†'
                    report.append(f"| [{scene['id']}](runs/{arm}/{scene['id']}/failure.json) | {arm} | FAIL | "
                        f"{g['component_count']} / {g['truth_component_count']}† | {error} | {g['union_iou']:.4f}† | "
                        f"— | — | ≥{diagnostic['completed_bie_solve_lower_bound']} | {reason} |")
                else:
                    report.append(f"| {scene['id']} | {arm} | FAIL / incomplete | — | — | — | — | — | — | {reason} |")
                continue
            g = row['geometry']; error = g['maximum_matched_hausdorff_m']
            distance = '—' if error is None else f'{error*1000:.5g}'
            report.append(f"| [{scene['id']}](runs/{arm}/{scene['id']}/metrics.json) | {arm} | "
                f"{'PASS' if row['passed'] else 'FAIL'} | {g['component_count']} / {g['truth_component_count']} | "
                f"{distance} | {g['union_iou']:.4f} | {row['refined_relative_error']:.4g} | "
                f"{row['maximum_holdout_relative_error']:.4g} | {row['work']['totals']['bie_frequency_solve_count']} | {row['stop_reason']} |")
    report += ['', '† Failed-run quantities describe the last saved accepted state, not a qualified final solution. '
        'Their solve counts are lower bounds; full candidate trials are unavailable after an uncaught controller exception. '
        'Saved progress records and tracebacks remain intact. No physics was rerun to fill missing fields.', '',
        'Matched error uses one-to-one minimum-cost component assignment and boundary-to-polyline distances. '
        'When counts differ, unmatched components are not in that distance; the independent count and material-union '
        'overlap gates prevent a misleading pass.', '', '## Protocol and verification', '',
        'The [pre-execution plan](../../../../docs/iterations/topology/iteration_03/03_plan.md) and '
        '[frozen specification](scene_spec.json) define all scenes, budgets and gates. '
        'Use [the benchmark instructions](../../../../docs/benchmarks/topology_scenes.md) for future comparisons.', '',
        'All 24 inversions use the current Cartesian automatic controller: 0.5-GHz training, 24 paired ring '
        'measurements, 64/128 nodes, ten cycles, seven events and unchanged acceptance rules. '
        '1.5/2.5-GHz predictions are evaluation-only. No count, truth shape or prescribed event enters inversion. '
        'The two arms share the exact observations and initial state for each scene.', '',
        'Noncircular observations use analytic boundaries at 256 nodes and the same Kress solver, checked at '
        '512 nodes. Circular scenes use independent cylindrical harmonics. This is noiseless, separated, '
        'same-material 2-D evidence; the star is a smooth lobed boundary, not a sharp polygon.', '',
        'Birth proposals in the current automatic controller remain circular; surviving components '
        'are not generally promoted to richer shape modes. The older prescribed ellipse/star challenge '
        'used explicit mode and frequency schedules. Missing automatic shape adaptation and refined '
        'feasibility of inner optimizer updates are next questions; neither is fixed by this measurement.', '',
        'Four single-thread inversion subprocesses may run concurrently. Solve counts exclude oracle and final '
        'evaluation work; elapsed times are not a controlled speed comparison. The inverse test suite also ran '
        'concurrently for about 72 seconds, and saved failure videos were rendered while later inversions ran. '
        'Per-run timeout is ten minutes; the inversion suite ceiling is 45 minutes. Solve counts are not '
        'weighted by matrix dimension, and failed-run counts are only checkpoint lower bounds.', '',
        'All 155 measured source files were checked before any post-run changes '
        '([checks](pre_reporting_source_verification.json)). The exact '
        '[executed harness](executed_run_topology_scene_benchmark.py) is archived for source identity. '
        'After all jobs stopped, the working harness gained failed-state rendering, unclipped plots, '
        'partial-work reporting and a frozen-data reuse option '
        '([change record](postrun_reporting_changes.json)). AST checks confirm the inversion, '
        'geometry metrics, gates, budgets and job execution functions are unchanged. No inversion was rerun. '
        'The archive is a source snapshot, not a standalone entry point in this result directory.', '',
        f"Artifact verification: **{'PASS' if verification['all_checks_passed'] else 'CHECK REQUIRED'}**. "
        '[Machine-readable checks](verification.json) recheck source/observation hashes, paired inputs, '
        'original-control reproduction and outcome gates. This is an independent re-reading of artifacts '
        'by the implementation owner, not independent scientific review. Reviewer: unassigned.', '',
        '[Tests](tests.log) · [Execution](execution.log) · [Full metrics](suite_metrics.json)', '',
        'Rebuild this analysis from the repository root:', '', '```bash',
        'env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python '
        'results/validation/topology/TOP-006-20260911-scenes-v1/analyze.py', '```', '']
    (HERE / 'README.md').write_text('\n'.join(report))
    print(json.dumps({'verification_passed': verification['all_checks_passed'], 'totals': data['totals']}))


if __name__ == '__main__':
    main()
