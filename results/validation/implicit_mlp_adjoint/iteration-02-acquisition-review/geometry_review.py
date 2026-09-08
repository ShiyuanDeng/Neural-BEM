"""Read-only arithmetic on recorded matched trajectories; no model/BEM calls."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUN = ROOT / 'results/validation/implicit_mlp_adjoint/iteration-02-final/inverse-20260908T170732213677Z'
REPAIR = ROOT / 'results/validation/implicit_mlp_adjoint/iteration-02-suite-20260908T163753015880Z'
OUT = Path(__file__).resolve().parent
sources = {}
def read(path):
    sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())
report = {'scope': 'Saved-data arithmetic only; zero BEM, inverse, extraction, or gradient evaluations.',
          'source_run': str(RUN.relative_to(ROOT)), 'arms': {}, 'historical_field_repair': {},
          'input_sha256': sources}
rows = []
for arm in ('E0', 'E1'):
    geometry = read(RUN / arm / 'geometry_trajectory.json')
    metrics = read(RUN / arm / 'metrics.json')
    trial_path = RUN / arm / 'trials.jsonl'
    sources[str(trial_path.relative_to(ROOT))] = hashlib.sha256(trial_path.read_bytes()).hexdigest()
    trials = [json.loads(line) for line in trial_path.read_text().splitlines()]
    binding = []
    accepted = [t for t in trials if t['accepted']]
    for trial in accepted:
        previous = [t for t in trials if t['iteration'] == trial['iteration'] and t['method'] == trial['method'] and t['backtracks'] == trial['backtracks']-1]
        assert len(previous) == 1
        binding.append({'iteration': trial['iteration'], 'reasons': previous[0]['rejection_reasons'],
                        'next_larger_motion_m': previous[0].get('boundary_movement_m')})
    for shape, metric in zip(geometry, metrics['trajectory']):
        assert shape['iteration'] == metric['iteration']
        stats = shape['field_statistics']
        mean_G = shape['field_norm_spectrum']['coefficients'][0]
        row = {'arm': arm, 'iteration': shape['iteration'], 'minimum_G': stats['minimum'],
               'maximum_G': stats['maximum'], 'rms_G': stats['rms'], 'spread_G': stats['spread'],
               'mean_G': mean_G, 'on_contour_eikonal_from_saved_spectrum': stats['rms']**2 - 2*mean_G + 1,
               'box_eikonal': metric['eikonal_loss'], 'conversion_um': 1e6*metric['conversion_error_m'],
               'refinement_change_um': 1e6*metric['conversion_refinement_change_m'],
               'boundary_movement_mm': 1e3*metric['boundary_movement_m'],
               'topology_single_component': shape['branch']['topology_single_component'],
               'sample_set_hash': shape['sample_set_hash']}
        rows.append(row)
    armrows = [row for row in rows if row['arm'] == arm]
    fresh = read(RUN / arm / 'fresh_proposal_geometry.json')
    report['arms'][arm] = {
        'initial': armrows[0], 'final': armrows[-1],
        'maximum_accepted_conversion_um': max(x['conversion_um'] for x in armrows),
        'maximum_accepted_refinement_change_um': max(x['refinement_change_um'] for x in armrows),
        'all_accepted_single_component': all(x['topology_single_component'] for x in armrows),
        'all_gradients_unclipped_and_nonzero': all(g['field_statistics']['gradient_values_are_unclipped'] and g['field_statistics']['zero_gradient_count'] == 0 for g in geometry),
        'regularizer_sample_hashes': sorted(set(x['sample_set_hash'] for x in armrows)),
        'binding_constraints': binding, 'candidate_evaluations': metrics['candidate_evaluations'],
        'rejection_reason_counts': metrics['rejection_reason_counts'],
        'geometry_rejections': [{k:t.get(k) for k in ('iteration','backtracks','backtrack_factor','rejection_reasons','conversion_error_m','conversion_refinement_change_m','error')} for t in trials if any(r in ('extraction_topology','conversion_distance','conversion_refinement_change') for r in t['rejection_reasons'])],
        'common_20um_probes_all_extract_successfully': all(not x.get('finite_probe_failure') for x in fresh if x['scale_label']=='common_predicted_rms_20um'),
        'common_20um_probe_count': sum(x['scale_label']=='common_predicted_rms_20um' for x in fresh),
        'final_radial_modes_mm': {str(m):1000*geometry[-1]['radial_spectrum']['radial_amplitudes_m'][m] for m in (3,4,5,6,7,9)},
        'mean_target_distance_improvement_fraction': 1-metrics['trajectory'][-1]['mean_node_to_exact_boundary_distance_m']/metrics['trajectory'][0]['mean_node_to_exact_boundary_distance_m'],
    }
for state in (32,47):
    data = read(REPAIR / f'star-{state}-field_repair/report.json')['states'][str(state)]['stages']['field_repair']['measurement']
    report['historical_field_repair'][str(state)] = {
        k: data[k] for k in ('raw_maximum_set_movement_m','raw_rms_normal_movement_m','marching_branch_unchanged')}
    for when in ('before','after'):
        report['historical_field_repair'][str(state)][when] = {
            'field_gradient':data[when]['field_gradient'],
            'conversion_error_m':data[when]['conversion']['maximum_conversion_error_m'],
            'refinement_change_m':data[when]['conversion']['conversion_refinement_change_m']}
report['assessment'] = {
    'field_conditioning_blocks_acquisition_promotion': False,
    'evidence_scope': 'Five accepted updates from one identical saved initialization; no claim of long-run stability.',
    'observed_geometry_bug_requiring_fix': False,
    'field_repair_supports_immediate_sampling_change': False,
    'reason': 'Accepted field spreads remain near1.65, conversion is far inside fixed limits, and nearest rejected steps bind only on boundary motion. Historical25-step field repair did not strongly repair conditioning; the state47 spread worsened.',
    'monitor': 'E1 minimum G declines monotonically; track true unclipped minimum, spread, conversion and signed geometry throughout any longer acquisition-only comparison.',
    'do_not_infer': 'Single-component extraction and marching hashes do not certify differential branch consistency. Changed hashes during finite motion are not by themselves a geometry defect.'}
(OUT/'geometry_review.json').write_text(json.dumps(report,indent=2)+'\n')
with (OUT/'geometry_review.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps({'assessment':report['assessment'],'final':{a:report['arms'][a]['final'] for a in ('E0','E1')}},indent=2))
