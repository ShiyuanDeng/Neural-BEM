"""Read-only NumPy/Torch-array audit of actual saved E0/E1 proposals.

No model is constructed, no geometry is extracted and no BEM or inverse is run.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
import time

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[4]
INPUT = ROOT / 'results/validation/implicit_mlp_adjoint/iteration-02-final/inverse-20260908T170732213677Z'
OUTPUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arr(value):
    return value.detach().cpu().numpy() if isinstance(value, torch.Tensor) else np.asarray(value)


def maximum(value):
    return float(np.max(np.abs(value))) if np.size(value) else 0.


def rms(value, weights=None):
    value = arr(value)
    return float(np.sqrt(np.mean(value ** 2) if weights is None else weights @ value ** 2))


def cosine(first, second, weights=None):
    first, second = arr(first), arr(second)
    weights = np.ones_like(first) if weights is None else weights
    return float(weights @ (first * second) / np.sqrt((weights @ first ** 2) * (weights @ second ** 2)))


def polygon_weights(points):
    points = np.asarray(points)
    lengths = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
    return (lengths + np.roll(lengths, 1)) / (2 * lengths.sum())


def state_vectors(state, sizes):
    group = state['param_groups'][0]
    first, second, steps = [], [], []
    for key, size in zip(group['params'], sizes):
        values = state['state'].get(key)
        if values is None:
            first.append(np.zeros(size)); second.append(np.zeros(size)); steps.append(0)
        else:
            first.append(arr(values['exp_avg']).reshape(-1))
            second.append(arr(values['exp_avg_sq']).reshape(-1))
            steps.append(int(arr(values['step'])))
    return np.concatenate(first), np.concatenate(second), steps


def direction_geometry(row):
    weights = polygon_weights(row['raw_contour'])
    result = {key: row[key] for key in ('direction', 'scale_label', 'scale')}
    norm = row['V_n_spectrum']['rms']
    coefficients = arr(row['V_n_spectrum']['coefficients'])
    correction = arr(row['V_n_spectrum']['target_correction_coefficients'])
    numerator = -arr(row['N_spectrum']['coefficients'])
    orders = arr(row['V_n_spectrum']['orders'])
    effects = row['V_n_spectrum']['signed_effect_by_mode']
    result.update(predicted_rms_m=norm,
                  predicted_maximum_normal_motion_m=maximum(row['V_n']),
                  signed_target_score_modes_0_20_m2=float(coefficients @ correction),
                  signed_target_cosine_modes_0_20=float(coefficients @ correction / (norm * np.linalg.norm(correction))),
                  signed_target_score_modes_2_20_m2=float(coefficients[orders >= 2] @ correction[orders >= 2]),
                  numerator_score_at_rms_20um_m2=float(numerator @ correction * 2e-5 / row['N_spectrum']['rms']),
                  velocity_score_at_rms_20um_m2=float(coefficients @ correction * 2e-5 / norm),
                  negative_numerator_velocity_cosine=cosine(-arr(row['N']), row['V_n'], weights),
                  signed_mode_effects=effects,
                  mode5_effect_m2=effects['5'],
                  mode3_effect_m2=effects['3'],
                  mode4_effect_m2=effects['4'],
                  G_min=float(np.min(row['G'])), G_max=float(np.max(row['G'])),
                  energy_11_20_fraction=row['V_n_spectrum']['energy_11_20'] / norm ** 2,
                  unresolved_energy_fraction=row['V_n_spectrum']['unresolved_energy'] / norm ** 2)
    if row.get('finite_probe_failure'):
        result['finite_probe_failure'] = row['finite_probe_failure']
    else:
        actual = arr(row['actual_raw_motion'])
        result.update(actual_raw_rms_m=rms(actual, weights),
                      actual_raw_prediction_relative_rms_error=rms(actual - arr(row['V_n']), weights) / norm,
                      actual_raw_prediction_cosine=cosine(actual, row['V_n'], weights),
                      actual_converted_rms_node_average_m=rms(row['actual_converted_motion']),
                      raw_correspondence=row['raw_correspondence'],
                      converted_correspondence=row['converted_correspondence'],
                      actual_raw_signed_target_score_modes_0_20_m2=float(sum(row['actual_raw_motion_spectrum']['signed_effect_by_mode'].values())))
    return result


def main():
    started = time.perf_counter()
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'input_run': str(INPUT.relative_to(ROOT)),
              'scope': 'Actual saved proposals, moments, gradients, trials and existing geometry probes; no model, extraction, BEM, inverse or new finite perturbation.',
              'score_scope': 'Signed target scores use saved nearest-target squared-distance correction projected through arc-length modes 0..20. Positive removes that error. These are not global recovery guarantees.',
              'inputs_sha256': {}, 'arms': {}}
    table = []
    for arm in ('E0', 'E1'):
        folder = INPUT / arm
        files = ('optimizer_records.pt', 'trials.jsonl', 'fresh_proposal_geometry.json', 'geometry_trajectory.json', 'metrics.json')
        for name in files:
            report['inputs_sha256'][f'{arm}/{name}'] = sha(folder / name)
        records = torch.load(folder / 'optimizer_records.pt', map_location='cpu', weights_only=False)
        trials = [json.loads(line) for line in (folder / 'trials.jsonl').read_text().splitlines()]
        geometry = json.loads((folder / 'fresh_proposal_geometry.json').read_text())
        trajectory = json.loads((folder / 'geometry_trajectory.json').read_text())
        metrics = json.loads((folder / 'metrics.json').read_text())
        rows = []
        for index, record in enumerate(records):
            iteration = record['iteration']
            group = record['optimizer_after_proposal']['param_groups'][0]
            sizes = [arr(record['optimizer_after_proposal']['state'][key]['exp_avg']).size for key in group['params']]
            before_m, before_v, before_steps = state_vectors(record['optimizer_before'], sizes)
            after_m, after_v, after_steps = state_vectors(record['optimizer_after_proposal'], sizes)
            accepted_m, accepted_v, accepted_steps = state_vectors(record['optimizer_accepted'], sizes)
            gradient = arr(record['total_gradient'])
            data_gradient = arr(record['data_gradient'])
            beta1, beta2 = group['betas']
            clipped = gradient * record['gradient_clip_factor']
            expected_m = beta1 * before_m + (1 - beta1) * clipped
            expected_v = beta2 * before_v + (1 - beta2) * clipped ** 2
            assert len(set(after_steps)) == 1
            step_count = after_steps[0]
            expected_proposal = -group['lr'] * (after_m / (1 - beta1 ** step_count)) / (np.sqrt(after_v / (1 - beta2 ** step_count)) + group['eps'])
            adam = arr(record['adam_proposal'])
            raw_adam = arr(record['raw_adam_proposal'])
            fallback = arr(record['fallback_proposal'])
            accepted = next(t for t in record['trials'] if t['accepted'])
            alpha = accepted['backtrack_factor']
            prior = next((t for t in record['trials'] if t['method'] == accepted['method'] and t['backtracks'] == accepted['backtracks'] - 1), None)
            local_geometry = [r for r in geometry if r['iteration'] == iteration]
            common = {r['direction']: r for r in local_geometry if r['scale_label'] == 'common_predicted_rms_20um'}
            weights = polygon_weights(common['raw_adam_proposal']['raw_contour'])
            normal_adam = arr(common['raw_adam_proposal']['V_n'])
            normal_total = arr(common['total_steepest_descent']['V_n'])
            normal_data = arr(common['data_steepest_descent']['V_n'])
            row = {'iteration': iteration, 'checks': {
                'data_plus_eikonal_gradient_maximum_error': maximum(gradient - data_gradient - arr(record['weighted_eikonal_gradient'])),
                'adam_first_moment_equation_maximum_error': maximum(after_m - expected_m),
                'adam_second_moment_equation_maximum_error': maximum(after_v - expected_v),
                'raw_adam_update_equation_maximum_error': maximum(raw_adam - expected_proposal),
                'projected_minus_raw_adam_maximum_difference': maximum(adam - raw_adam),
                'accepted_vs_backtracked_adam_maximum_error': maximum(arr(record['accepted_step']) - alpha * adam),
                'accepted_weights_maximum_error': maximum(arr(record['accepted_parameter_vector']) - arr(record['parameter_vector']) - arr(record['accepted_step'])),
                'accepted_vs_proposal_first_moment_error': maximum(accepted_m - after_m),
                'accepted_vs_proposal_second_moment_error': maximum(accepted_v - after_v),
                'adam_steps_before': before_steps, 'adam_steps_after': after_steps, 'adam_steps_accepted': accepted_steps,
                'trials_match_jsonl_exactly': record['trials'] == [t for t in trials if t['iteration'] == iteration],
            }, 'data_total_weight_cosine': cosine(data_gradient, gradient),
                'total_gradient_raw_adam_weight_cosine': cosine(-gradient, raw_adam),
                'raw_projected_adam_weight_cosine': cosine(raw_adam, adam),
                'accepted_adam_weight_cosine': cosine(record['accepted_step'], adam),
                'total_gradient_fallback_weight_cosine': cosine(-gradient, fallback),
                'weighted_eikonal_to_data_gradient_norm_ratio': float(np.linalg.norm(record['weighted_eikonal_gradient']) / np.linalg.norm(data_gradient)),
                'total_gradient_norm': float(np.linalg.norm(gradient)),
                'clip_factor': record['gradient_clip_factor'],
                'adam_data_directional_derivative': float(data_gradient @ adam),
                'adam_total_directional_derivative': float(gradient @ adam),
                'actual_accepted_data_linearized_decrease': float(-data_gradient @ record['accepted_step']),
                'actual_accepted_data_decrease': metrics['trajectory'][index]['training_loss'] - accepted['loss'],
                'accepted_factor': alpha, 'accepted_method': accepted['method'], 'fallback_reset': record['fallback_reset'],
                'accepted_boundary_movement_m': accepted['boundary_movement_m'],
                'next_larger_rejected_reasons': prior['rejection_reasons'] if prior else [],
                'next_larger_rejected_movement_m': prior.get('boundary_movement_m') if prior else None,
                'trial_count': len(record['trials']),
                'normal_data_total_cosine': cosine(normal_data, normal_total, weights),
                'normal_total_adam_cosine': cosine(normal_total, normal_adam, weights),
                'numerator_total_adam_cosine': cosine(common['total_steepest_descent']['N'], common['raw_adam_proposal']['N'], weights),
                'normal_total_fallback_cosine': cosine(normal_total, common['fallback']['V_n'], weights),
                'directions': [direction_geometry(r) for r in local_geometry]}
            if index:
                prior_m, prior_v, prior_steps = state_vectors(records[index - 1]['optimizer_accepted'], sizes)
                row['checks'].update(moment_first_continuity_error=maximum(before_m - prior_m),
                    moment_second_continuity_error=maximum(before_v - prior_v),
                    accepted_theta_continuity_error=maximum(arr(record['parameter_vector']) - arr(records[index - 1]['accepted_parameter_vector'])))
            raw_actual = next(r for r in local_geometry if r['direction'] == 'raw_adam_proposal' and r['scale_label'] == 'actual_proposal')
            row['accepted_predicted_raw_rms_m'] = raw_actual['V_n_spectrum']['rms'] * alpha
            row['raw_adam_full_proposal_predicted_max_m'] = maximum(raw_actual['V_n'])
            cg = {v['direction']: v for v in row['directions'] if v['scale_label'] == 'common_predicted_rms_20um'}
            flat = {'arm': arm, 'iteration': iteration, 'accepted_factor': alpha,
                    'binding': ','.join(row['next_larger_rejected_reasons']),
                    'weight_total_adam_cosine': row['total_gradient_raw_adam_weight_cosine'],
                    'normal_total_adam_cosine': row['normal_total_adam_cosine'],
                    'data_score_20um_m2': cg['data_steepest_descent']['signed_target_score_modes_0_20_m2'],
                    'total_score_20um_m2': cg['total_steepest_descent']['signed_target_score_modes_0_20_m2'],
                    'adam_score_20um_m2': cg['raw_adam_proposal']['signed_target_score_modes_0_20_m2'],
                    'total_actual_score_20um_m2': cg['total_steepest_descent'].get('actual_raw_signed_target_score_modes_0_20_m2'),
                    'adam_actual_score_20um_m2': cg['raw_adam_proposal'].get('actual_raw_signed_target_score_modes_0_20_m2'),
                    'adam_mode5_effect_m2': cg['raw_adam_proposal']['mode5_effect_m2'],
                    'total_mode5_effect_m2': cg['total_steepest_descent']['mode5_effect_m2'],
                    'adam_raw_probe_relative_error': cg['raw_adam_proposal'].get('actual_raw_prediction_relative_rms_error'),
                    'total_raw_probe_relative_error': cg['total_steepest_descent'].get('actual_raw_prediction_relative_rms_error')}
            table.append(flat)
            rows.append(row)
        report['arms'][arm] = {'states': rows, 'reported_metrics': metrics,
            'recomputed_rejections': dict(Counter(reason for t in trials if not t['accepted'] for reason in t['rejection_reasons'])),
            'accepted_methods': dict(Counter(t['method'] for t in trials if t['accepted'])),
            'next_larger_rejection_counts': dict(Counter(reason for r in rows for reason in r['next_larger_rejected_reasons'])),
            'gradient_field_statistics_by_state': [{'iteration': r['iteration'], **r['field_statistics']} for r in trajectory],
            'sample_set_count': len({r['sample_set_hash'] for r in records}),
            'initial_optimizer_state_empty': not records[0]['optimizer_before']['state']}
    report['conclusions'] = {
        'all_saved_common_scale_adam_scores_exceed_total_gradient': all(r['adam_score_20um_m2'] > r['total_score_20um_m2'] for r in table),
        'all_saved_common_scale_actual_raw_adam_scores_exceed_total_gradient': all(r['adam_actual_score_20um_m2'] > r['total_actual_score_20um_m2'] for r in table),
        'all_next_larger_rejected_trials_bind_motion': all(r['binding'] == 'boundary_motion_limit' for r in table),
        'projection_changed_any_adam_proposal': any(r['checks']['projected_minus_raw_adam_maximum_difference'] > 0 for a in report['arms'].values() for r in a['states']),
        'optimizer_replacement_supported': False,
        'scope_limit': 'Five early accepted updates per arm; one existing 20um finite probe per direction does not establish an alpha convergence window or late-state recovery.',
    }
    report['elapsed_seconds'] = time.perf_counter() - started
    report['review_script_sha256'] = sha(Path(__file__))
    (OUTPUT / 'optimizer_review.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (OUTPUT / 'optimizer_review.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0])); writer.writeheader(); writer.writerows(table)
    print(json.dumps({'elapsed_seconds': report['elapsed_seconds'], 'rows': table}, indent=2))


if __name__ == '__main__':
    main()
