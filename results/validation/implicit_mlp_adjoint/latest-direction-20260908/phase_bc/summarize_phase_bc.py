"""Build concise Phase B/C evidence from the completed, bounded diagnostics."""
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
truth = json.loads((OUT / 'start-at-truth/metrics.json').read_text())
row = truth['solvers']['kress']
frozen = json.loads((OUT / 'frozen_fallback_metrics.json').read_text())
replay = json.loads((OUT / 'post_optimization_holdout_replay.json').read_text())
test_count = int(re.search(r'(\d+) passed', (OUT / 'tests.log').read_text()).group(1))
accepted = row['accepted_iterate_diagnostics']
for record in accepted:
    norm = record['weighted_eikonal_gradient_norm']
    record['eikonal_gradient_norm'] = None if norm is None else norm / row['optimizer_config']['eikonal_weight']
(OUT / 'start-at-truth/kress_accepted_iterates.json').write_text(json.dumps(accepted, indent=2) + '\n')
first, last = accepted[0], accepted[-1]
metrics = {
    'scope': 'Bounded start-at-target-fitting-control and frozen-fallback diagnostics; no long neural inverse.',
    'short_truth_control': {
        'source': 'start-at-truth/metrics.json',
        'acquisition': 'paired: source row i observed at receiver row i',
        'source_count': 8, 'receiver_count': 8, 'measurement_count_per_frequency': 8,
        'train_frequencies_ghz': truth['train_frequencies_ghz'],
        'holdout_frequencies_ghz': truth['holdout_frequencies_ghz'],
        'stop_reason': row['stop_reason'], 'accepted_updates': row['accepted_updates'],
        'attempted_training_forward_evaluations': row['total_forward_evaluations'],
        'evaluation_only_holdout_forward_evaluations': row['evaluation_only_holdout_forward_evaluations'],
        'additional_all_frequency_reporting_forward_evaluations': 4,
        'inverse_wall_seconds': row['inverse_wall_seconds'],
        'original_inverse_timing_policy': 'includes successful original holdout callbacks; corrected driver replays holdout after completed inverse',
        'post_optimization_holdout_replay': replay,
        'rejected_trial_count': row['optimizer_diagnostics']['rejected_trial_count'],
        'rejection_reason_counts': row['optimizer_diagnostics']['rejection_reason_counts'],
        'initial_data_gradient_norm': first['data_gradient_norm'],
        'initial_weighted_eikonal_gradient_norm': first['weighted_eikonal_gradient_norm'],
        'initial_eikonal_gradient_norm': first['eikonal_gradient_norm'],
        'accepted_iterates': accepted,
        'decision': 'A usable three-step local neighborhood: training and fixed holdout improve while maximum boundary error worsens modestly. Long-term stability is untested.',
    },
    'frozen_fallback_audit': {
        'source': 'frozen_fallback_metrics.json',
        'first_accepted_beyond_historical_8': frozen['first_accepted_beyond_historical_8'],
        'rejection_reason_counts': frozen['rejection_reason_counts'],
        'stop_reason': frozen['stop_reason'],
        'forward_evaluations': frozen['forward_evaluations'], 'wall_seconds': frozen['wall_seconds'],
        'meaningful_boundary_step_floor_m': frozen['meaningful_boundary_step_floor_m'],
        'decision': 'The historical stop is a conversion-refinement/search-depth effect. Accepted deeper steps are below the declared geometric movement floor and do not establish recovery.',
    },
    'validation': {'focused_tests_passed': test_count, 'test_log': 'tests.log'},
}
(OUT / 'metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
sources = [
    'run_implicit_mlp_inverse.py', 'run_sdf_inverse_comparison.py',
    'solvers/sdf_inverse/implicit_adjoint.py', 'solvers/sdf_inverse/geometry.py',
    'solvers/sdf_inverse/models.py', 'solvers/sdf_inverse/forward.py',
    'solvers/sdf_inverse/method_b_pullback.py',
    'solvers/gpr_bem_kress/shape_derivative.py',
    'pytest/sdf_inverse/test_implicit_adjoint.py',
    'pytest/sdf_inverse/test_implicit_adjoint_driver.py',
    'pytest/sdf_inverse/test_pretraining_and_conversion_repairs.py',
    str((OUT / 'frozen_fallback_audit.py').relative_to(ROOT)),
    str((OUT / 'replay_truth_holdout.py').relative_to(ROOT)),
    str(Path(__file__).resolve().relative_to(ROOT)),
]
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
provenance = {
    'commit_sha': commit, 'created_utc': datetime.now(timezone.utc).isoformat(),
    'working_tree_dirty': True,
    'hash_capture': 'Post-run integration snapshot; original run provenance and numerical settings are retained below and in source metrics.',
    'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
    'original_truth_run_provenance': truth['provenance'],
    'frozen_checkpoint_sha256': frozen['checkpoint_sha256'],
    'truth_geometry_config': row['geometry_config'] if 'geometry_config' in row else truth['experiment'].get('geometry_config'),
    'truth_optimizer_config': row['optimizer_config'],
    'holdout_oracle_validation': '../phase_a/oracle_3ghz_validation.json',
    'test_log_sha256': hashlib.sha256((OUT / 'tests.log').read_bytes()).hexdigest(),
}
(OUT / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
lines = [
    '# Start-at-truth and termination diagnostics — 2026-09-08', '',
    f'Commit `{commit}`, with the working-tree changes hashed in [provenance.json](provenance.json).', '',
    'The three-update truth control remains near its supervised target fit and improves training and fixed holdout errors. Maximum boundary error increases slightly, so this is a usable short local neighborhood, not a stability or recovery result. The separate frozen audit closes the historical termination question: the first valid fallback is backtrack 9, but its movement is below the declared meaningful-step floor.', '',
    'Both experiments use eight source rows and eight receiver rows on the existing ring, paired diagonal readout (eight complex measurements per frequency), train frequencies 0.5 and 1.5 GHz, float64 SIREN width 64 with two hidden layers (8,577 weights), Kress nodes 194, Method-B bandwidth 96, grid 513 × 513, projected samples 256, arc-length integration 2048 and validation 1024. Conversion distance must remain at most 0.2 mm and refinement change at most 0.01 mm; maximum boundary movement is 2 mm. All existing Armijo and extraction gates are retained.', '',
    '## Short truth control', '',
    'The initialization is the exact-target SIREN fitting control built by the existing 6,000-step supervised procedure, with pretraining Eikonal weight zero. It is an approximate target fit, not the analytic boundary. The inverse retains Eikonal weight 0.01 and fixed regularization samples, learning rate 0.001, Adam with adjoint steepest-descent fallback, and a 14-halving search budget. Work budget: three accepted updates. The fixed evaluation-only holdout is 3.0 GHz; its independent 512-versus-1024-node oracle check is recorded in [Phase A](../phase_a/oracle_3ghz_validation.json). Holdout values never enter acceptance or stopping.', '',
    '| Accepted iterate | Data loss | Regularized objective | Train rel. L2 | Holdout rel. L2 | Max boundary error (mm) | Movement (mm) |',
    '|---:|---:|---:|---:|---:|---:|---:|',
]
for record in accepted:
    lines.append(f"| {record['iteration']} | {record['loss']:.8g} | {record['objective']:.8g} | {record['relative_l2_error']:.8g} | {record['holdout_relative_l2']:.8g} | {1e3 * record['maximum_node_to_exact_boundary_distance_m']:.6f} | {1e3 * record['boundary_movement_m']:.6f} |")
lines += ['',
    f"Initial data-gradient norm: `{first['data_gradient_norm']:.10g}`. Initial Eikonal-gradient norm: `{first['eikonal_gradient_norm']:.10g}`; weighted by 0.01: `{first['weighted_eikonal_gradient_norm']:.10g}`. The final budget iterate does not require another adjoint, so its gradient norms remain explicitly unevaluated.", '',
    f"Fitted amplitude changes from `{first['fitted_shape']['amplitude']:.9g}` to `{last['fitted_shape']['amplitude']:.9g}` (target 0.25); rotation from `{first['fitted_shape']['rotation_radians']:.9g}` to `{last['fitted_shape']['rotation_radians']:.9g}` radians (target 0). Center, mean radius, both conversion checks and every accepted holdout value are in [the compact trajectory](start-at-truth/kress_accepted_iterates.json). Boundary error is the maximum sampled Method-B-node distance to the exact target, not a certified continuous Hausdorff bound.", '',
    f"Stop: `{row['stop_reason']}` after {row['accepted_updates']} accepted updates, {row['total_forward_evaluations']} attempted training forward evaluations and {row['optimizer_diagnostics']['rejected_trial_count']} rejected trials. Four additional holdout evaluations are evaluation only. Inverse wall time: {row['inverse_wall_seconds']:.3f} seconds including callback work. Rejection reasons overlap: `{json.dumps(row['optimizer_diagnostics']['rejection_reason_counts'], sort_keys=True)}`. The [trial log](start-at-truth/kress_trials.jsonl) records each candidate and every applicable failure reason; physics/motion tests are not evaluated when extraction or conversion rejects the candidate first.", '',
    'Four additional all-frequency forward evaluations (initial field, analytic target, supervised target fit, final field), supervised fitting and oracle work sit outside the inverse counts/timing. The separate post-optimization replay validation below adds four more evaluation-only holdout predictions and is reported separately.', '',
    'The three steps reduce data loss and holdout error, and all move more than the 0.1 mm reporting floor. Maximum boundary error nevertheless worsens from 1.191125 to 1.290189 mm. This separates a usable near-target neighborhood from the large wrong-start failure, while retaining evidence of geometrically adverse descent. Longer local stability, basin reachability and general recovery are not established. The ordinary full-recovery gates still report FAIL; a three-step truth diagnostic does not satisfy their recovery-from-wrong-start requirements.', '',
    f"The original run's {row['inverse_wall_seconds']:.3f}-second inverse timing includes {row['evaluation_only_holdout_forward_seconds']:.3f} seconds of successful holdout forward callbacks. Subtracting that measured work gives {replay['original_inverse_minus_measured_holdout_forward_seconds']:.3f} seconds, with small callback bookkeeping overhead still included. The corrected driver saves the accepted checkpoint and completes optimization before an optional separate holdout replay; evaluation errors are recorded per iterate and final accepted weights are restored. A [post-optimization replay of this saved trajectory](post_optimization_holdout_replay.json) reproduces every holdout value with maximum absolute difference {replay['maximum_absolute_holdout_difference']:.3g} and preserves final weights exactly. No inverse was rerun.", '',
    '## Frozen fallback audit', '',
    'Reloaded the historical `star-bw96` final checkpoint and its exact archived observations. This audit uses no holdout and does not replay Adam moments or update/snapshot a new neural state. It evaluates every unchanged production fallback from backtrack 0 through 14 and restores the frozen weights exactly after each trial.', '',
    '| Backtracks | Rejection / result |',
    '|---|---|',
    '| 0–1 | Extraction/topology: two components |',
    '| 2 | Boundary motion and both Armijo tests |',
    '| 3–4 | Conversion distance |',
    '| 5–8 | Conversion refinement change |',
    '| 9–14 | All production gates pass |', '',
    'Backtrack 8 has conversion distance 0.112325 mm (passes), but refinement change 0.0115825 mm (fails). Backtrack 9 lowers data loss from 0.3461879920809253 to 0.3460535595880327, a 0.0388322% improvement; its conversion distance is 0.109192 mm, refinement change 0.00900314 mm and movement 0.0707587 mm. This exactly reproduces the prior review probe.', '',
    f"Stop: `{frozen['stop_reason']}`, after {frozen['forward_evaluations']} attempted forward evaluations including the initial state, {frozen['wall_seconds']:.3f} seconds, and nine rejected trials. Independent reason counts: `{json.dumps(frozen['rejection_reason_counts'], sort_keys=True)}`. Full metrics are in [frozen_fallback_metrics.json](frozen_fallback_metrics.json).", '',
    'A movement below 0.1 mm is explicitly classified as a crawl for this diagnostic. The floor is a declared reporting threshold, not an acceptance change or a convergence theorem. Every valid frozen fallback here is below it. An available accepted step explains the former premature stop; it does not explain or solve the approximately 36 mm wrong-start reconstruction error.', '',
    '## Reproduction and validation', '',
    'Exact commands are in [commands.txt](commands.txt). The frozen audit requires the existing locally ignored historical checkpoint and response archive. The direct truth control regenerates its supervised target fit. Per-weight CSV/checkpoints/response archives are generated locally; the compact JSON trajectory is the reviewable accepted-state record.', '',
    f'Validation: {test_count} focused inverse, driver and conversion-repair tests pass; see [tests.log](tests.log). Tests cover independent conversion rejection metadata, acceptance beyond eight halvings, unchanged fatal solver propagation with weight rollback, failed holdout replay isolation, the reporting-only movement floor, terminal unevaluated gradients and neural/analytic CLI defaults.', '',
]
(OUT / 'README.md').write_text('\n'.join(lines))
