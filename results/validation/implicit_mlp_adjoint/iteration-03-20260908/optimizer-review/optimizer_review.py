"""Saved-array-only review of long paired/multistatic optimizer evidence."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import time

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[5]
INPUT = ROOT / 'results/validation/implicit_mlp_adjoint/iteration-02-final/long-acquisition-20260908T174300326691Z'
OUTPUT = Path(__file__).resolve().parent
HELPER = ROOT / 'results/validation/implicit_mlp_adjoint/iteration-02-acquisition-review/optimizer_review.py'
spec = importlib.util.spec_from_file_location('saved_optimizer_array_helpers', HELPER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started = time.perf_counter()
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'input_run': str(INPUT.relative_to(ROOT)),
              'scope': 'Read saved real gradients, moments, proposals, trials and existing finite geometry probes. No model/extraction/BEM/inverse/new perturbations.',
              'implementation_sha256': {str(HELPER.relative_to(ROOT)): sha(HELPER), 'optimizer_review.py': sha(Path(__file__))},
              'input_sha256': {}, 'arms': {}}
    for arm in ('E0', 'E1'):
        folder = INPUT / arm
        for name in ('optimizer_manifest.json', 'metrics.json', 'trials.jsonl', 'fresh_proposal_geometry.json', 'proposal_geometry_selection.json', 'geometry_trajectory.json'):
            report['input_sha256'][f'{arm}/{name}'] = sha(folder / name)
        manifest = json.loads((folder / 'optimizer_manifest.json').read_text())
        metrics = json.loads((folder / 'metrics.json').read_text())
        trials = [json.loads(line) for line in (folder / 'trials.jsonl').read_text().splitlines()]
        geometry = json.loads((folder / 'fresh_proposal_geometry.json').read_text())
        trajectory = json.loads((folder / 'geometry_trajectory.json').read_text())
        records, selected = [], []
        previous_moments = previous_weights = None
        for entry in manifest['records']:
            checkpoint = folder / entry['file']
            report['input_sha256'][f'{arm}/{entry["file"]}'] = sha(checkpoint)
            r = torch.load(checkpoint, map_location='cpu', weights_only=False)
            i = r['iteration']
            group = r['optimizer_after_proposal']['param_groups'][0]
            sizes = [helpers.arr(r['optimizer_after_proposal']['state'][key]['exp_avg']).size for key in group['params']]
            before_m, before_v, before_steps = helpers.state_vectors(r['optimizer_before'], sizes)
            after_m, after_v, after_steps = helpers.state_vectors(r['optimizer_after_proposal'], sizes)
            final_m, final_v, final_steps = helpers.state_vectors(r['optimizer_accepted'], sizes)
            g, gd, ge = (helpers.arr(r[key]) for key in ('total_gradient', 'data_gradient', 'weighted_eikonal_gradient'))
            raw, adam, fallback = (helpers.arr(r[key]) for key in ('raw_adam_proposal', 'adam_proposal', 'fallback_proposal'))
            beta1, beta2 = group['betas']
            clipped = g * r['gradient_clip_factor']
            step = after_steps[0]
            expected_raw = -group['lr'] * (after_m / (1 - beta1 ** step)) / (np.sqrt(after_v / (1 - beta2 ** step)) + group['eps'])
            accepted = next((trial for trial in r['trials'] if trial['accepted']), None)
            prior = next((trial for trial in r['trials'] if accepted and trial['method'] == accepted['method'] and trial['backtracks'] == accepted['backtracks'] - 1), None)
            expected_final_m, expected_final_v = ((after_m, after_v) if accepted and accepted['method'] == 'adam' else
                ((np.zeros_like(before_m), np.zeros_like(before_v)) if accepted else (before_m, before_v)))
            item = {'iteration': i, 'accepted': bool(accepted), 'accepted_method': accepted['method'] if accepted else None,
                'fallback_reset': r['fallback_reset'], 'data_gradient_norm': float(np.linalg.norm(gd)),
                'weighted_eikonal_gradient_norm': float(np.linalg.norm(ge)),
                'weighted_eikonal_to_data_ratio': float(np.linalg.norm(ge) / np.linalg.norm(gd)),
                'clip_factor': r['gradient_clip_factor'], 'data_total_weight_cosine': helpers.cosine(gd, g),
                'total_adam_weight_cosine': helpers.cosine(-g, adam),
                'data_dot_adam': float(gd @ adam), 'total_dot_adam': float(g @ adam),
                'data_dot_fallback': float(gd @ fallback), 'total_dot_fallback': float(g @ fallback),
                'adam_non_descent_by_saved_gradients': bool(gd @ adam >= 0 or g @ adam >= 0),
                'fallback_non_descent_by_saved_gradients': bool(gd @ fallback >= 0 or g @ fallback >= 0),
                'attempted_methods': sorted({trial['method'] for trial in r['trials']}),
                'accepted_factor': accepted['backtrack_factor'] if accepted else None,
                'accepted_boundary_movement_m': accepted.get('boundary_movement_m') if accepted else None,
                'meaningful_accepted_motion': accepted.get('meaningful_boundary_step') if accepted else None,
                'next_larger_rejected_reasons': prior['rejection_reasons'] if prior else [],
                'trial_count': len(r['trials']),
                'checks': {
                    'total_gradient_decomposition_maximum_error': helpers.maximum(g - gd - ge),
                    'raw_projected_adam_maximum_difference': helpers.maximum(raw - adam),
                    'first_moment_recurrence_maximum_error': helpers.maximum(after_m - (beta1 * before_m + (1-beta1) * clipped)),
                    'second_moment_recurrence_maximum_error': helpers.maximum(after_v - (beta2 * before_v + (1-beta2) * clipped ** 2)),
                    'raw_adam_equation_maximum_error': helpers.maximum(raw - expected_raw),
                    'accepted_or_rollback_moment_first_maximum_error': helpers.maximum(final_m - expected_final_m),
                    'accepted_or_rollback_moment_second_maximum_error': helpers.maximum(final_v - expected_final_v),
                    'moments_before_steps': before_steps, 'moments_after_steps': after_steps, 'moments_final_steps': final_steps,
                    'trials_exactly_match_jsonl': r['trials'] == [trial for trial in trials if trial['iteration'] == i],
                }}
            if accepted:
                used = adam if accepted['method'] == 'adam' else fallback
                item['checks']['accepted_backtrack_step_maximum_error'] = helpers.maximum(helpers.arr(r['accepted_step']) - accepted['backtrack_factor'] * used)
            if previous_moments is not None:
                item['checks']['moment_first_continuity_maximum_error'] = helpers.maximum(before_m - previous_moments[0])
                item['checks']['moment_second_continuity_maximum_error'] = helpers.maximum(before_v - previous_moments[1])
                item['checks']['weights_continuity_maximum_error'] = helpers.maximum(helpers.arr(r['parameter_vector']) - previous_weights)
            previous_moments = final_m, final_v
            previous_weights = helpers.arr(r.get('accepted_parameter_vector', r['parameter_vector']))
            local = [row for row in geometry if row['iteration'] == i and row['scale_label'] == 'common_predicted_rms_20um']
            if local:
                cg = {row['direction']: helpers.direction_geometry(row) for row in local}
                lookup = {row['direction']: row for row in local}
                w = helpers.polygon_weights(local[0]['raw_contour'])
                comparison = {'iteration': i, 'accepted_method_after_this_state': item['accepted_method'],
                    'normal_total_adam_cosine': helpers.cosine(lookup['total_steepest_descent']['V_n'], lookup['raw_adam_proposal']['V_n'], w),
                    'normal_data_total_cosine': helpers.cosine(lookup['data_steepest_descent']['V_n'], lookup['total_steepest_descent']['V_n'], w),
                    'directions': cg}
                selected.append(comparison)
            records.append(item)
        terminal = records[-1]
        last_trials = [trial for trial in trials if trial['iteration'] == terminal['iteration']]
        report['arms'][arm] = {'stop_reason': metrics['stop_reason'], 'accepted_updates': metrics['accepted_updates'],
            'candidate_evaluations': metrics['candidate_evaluations'], 'optimizer_record_count': len(records),
            'accepted_methods': dict(Counter(item['accepted_method'] for item in records if item['accepted'])),
            'fallback_reset_iterations': [item['iteration'] for item in records if item['fallback_reset']],
            'adam_non_descent_iterations': [item['iteration'] for item in records if item['adam_non_descent_by_saved_gradients']],
            'fallback_non_descent_iterations': [item['iteration'] for item in records if item['fallback_non_descent_by_saved_gradients']],
            'fallback_attempt_iterations': [item['iteration'] for item in records if 'adjoint_steepest_descent' in item['attempted_methods']],
            'next_larger_rejections': dict(Counter(reason for item in records for reason in item['next_larger_rejected_reasons'])),
            'rejection_counts': dict(Counter(reason for trial in trials if not trial['accepted'] for reason in trial['rejection_reasons'])),
            'terminal_trials': last_trials,
            'accepted_motion_below_0_1mm_count': sum(item['accepted'] and not item['meaningful_accepted_motion'] for item in records),
            'last_accepted_moves_m': [item['accepted_boundary_movement_m'] for item in records if item['accepted']][-8:],
            'records': records, 'selected_common_scale_geometry': selected,
            'on_contour_G_selected': [{'iteration': row['iteration'], **row['field_statistics']} for row in trajectory if row['iteration'] in {s['iteration'] for s in selected}],
            'final_logged_trajectory': metrics['trajectory'][-1]}
    report['elapsed_seconds'] = time.perf_counter() - started
    (OUTPUT / 'optimizer_review.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    for arm, a in report['arms'].items():
        print(arm, {k:a[k] for k in ('accepted_updates','accepted_methods','fallback_reset_iterations','adam_non_descent_iterations','fallback_attempt_iterations','next_larger_rejections','accepted_motion_below_0_1mm_count','last_accepted_moves_m')})
        for row in a['selected_common_scale_geometry']:
            print(row['iteration'], 'Ncos', row['normal_total_adam_cosine'], 'data-totalcos', row['normal_data_total_cosine'],
                {name: {'score': v['signed_target_score_modes_0_20_m2'], 'shape_score': v['signed_target_score_modes_2_20_m2'], 'mode5':v['mode5_effect_m2'], 'failure': v.get('finite_probe_failure'), 'actual_score':v.get('actual_raw_signed_target_score_modes_0_20_m2')} for name,v in row['directions'].items() if name != 'fallback'})
        print('finalG', a['on_contour_G_selected'][-1])
    print('elapsed',report['elapsed_seconds'])


if __name__ == '__main__':
    main()
