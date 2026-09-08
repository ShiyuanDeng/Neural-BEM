"""Replay saved records only: no extraction, model evaluation, BEM, or inverse."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'solvers'))
LONG = ROOT / 'results/validation/implicit_mlp_adjoint/iteration-02-final/long-acquisition-20260908T174300326691Z'
SHORT = ROOT / 'results/validation/implicit_mlp_adjoint/iteration-02-final/inverse-20260908T170732213677Z'
OUT = Path(__file__).resolve().parent
hashes = {}
def track(path):
    hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path

def read(path):
    return json.loads(track(path).read_text())

def counts(trials):
    return {'by_reason': dict(Counter(reason for row in trials for reason in row['rejection_reasons'])),
            'exclusive_combinations': dict(Counter('|'.join(row['rejection_reasons']) for row in trials))}

summary = read(LONG / 'metrics.json')
qualification = read(LONG / 'qualification.json')
report = {'scope': 'Existing artifact analysis only; no model, extraction, gradient, BEM, or inverse evaluations.',
          'source_run': str(LONG.relative_to(ROOT)), 'status': summary['status'],
          'posthoc_errors': summary['posthoc_errors'], 'qualification_passed': qualification['passed'],
          'caps_per_arm': summary['caps_per_arm'], 'input_sha256': hashes, 'arms': {}}
field_rows = []
terminal_rows = []
for arm in ('E0','E1'):
    path = LONG / arm
    metrics = read(path / 'metrics.json')
    geometry = read(path / 'geometry_trajectory.json')
    trials = [json.loads(line) for line in track(path / 'trials.jsonl').read_text().splitlines()]
    last = metrics['trajectory'][-1]['iteration']
    terminal = [row for row in trials if row['iteration'] == last]
    accepted = [row for row in trials if row['accepted']]
    assert len(accepted) == metrics['accepted_updates'] == last
    assert len(geometry) == len(metrics['trajectory']) == last+1
    assert not any(row['accepted'] for row in terminal)
    assert len(terminal) == 30
    result = torch.load(track(path / 'inverse_result.pt'), map_location='cpu', weights_only=False)
    convergence = {'converged': result.converged, 'stop_reason': result.stop_reason,
                   'total_evaluation_count_including_initial': result.total_evaluation_count,
                   'final_gradient_evaluated': result.final_iteration.gradient_evaluated}
    del result
    manifest = read(path / 'optimizer_manifest.json')
    final_optimizer = torch.load(track(path / f'optimizer_{last:04d}.pt'), map_location='cpu', weights_only=False)
    descent = {name: {'data_gradient_dot_proposal': float(final_optimizer['data_gradient'] @ final_optimizer[key]),
                     'total_gradient_dot_proposal': float(final_optimizer['total_gradient'] @ final_optimizer[key])}
               for name,key in [('adam','adam_proposal'),('fallback','fallback_proposal')]}
    assert final_optimizer['accepted'] is False
    # Both final accepted updates were fallback steps, which clear Adam moments.
    restored_moments = (not final_optimizer['optimizer_before']['state']
                       and not final_optimizer['optimizer_accepted']['state'])
    del final_optimizer
    bindings = []
    for trial in accepted:
        previous = [t for t in trials if t['iteration']==trial['iteration'] and t['method']==trial['method']
                    and t['backtracks']==trial['backtracks']-1]
        bindings.append({'accepted_state':trial['iteration']+1, 'accepted_method':trial['method'],
                         'accepted_backtracks':trial['backtracks'],
                         'accepted_movement_um':trial['boundary_movement_m']*1e6,
                         'binding_reasons': previous[0]['rejection_reasons'] if len(previous)==1 else None,
                         'next_larger_error':previous[0].get('error') if len(previous)==1 else None})
    for g,m in zip(geometry,metrics['trajectory']):
        assert g['iteration']==m['iteration']
        stats=g['field_statistics'];mean=g['field_norm_spectrum']['coefficients'][0]
        field_rows.append({'arm':arm,'iteration':g['iteration'],'G_min':stats['minimum'],
            'G_max':stats['maximum'],'G_rms':stats['rms'],'G_spread':stats['spread'],
            'on_contour_eikonal_from_saved_spectrum':stats['rms']**2 - 2*mean + 1,
            'box_eikonal':m['eikonal_loss'],'conversion_um':m['conversion_error_m']*1e6,
            'refinement_change_um':m['conversion_refinement_change_m']*1e6,
            'accepted_movement_um':m['boundary_movement_m']*1e6,
            'topology_single_component':g['branch']['topology_single_component']})
    for trial in terminal:
        row=dict(trial,arm=arm)
        error=trial.get('error','')
        row['failure_stage_detail']=('independent_raw_audit' if 'Conversion audit could not resolve' in error
             else 'production_extraction' if 'no admissible single zero contour' in error
             else 'conversion_fidelity' if 'conversion fidelity failed' in error else 'motion_or_objective_acceptance')
        terminal_rows.append(row)
    short_metrics=read(SHORT / arm / 'metrics.json')
    short_trials=[json.loads(line) for line in track(SHORT / arm / 'trials.jsonl').read_text().splitlines()]
    comparable=['training_loss','regularized_loss','eikonal_loss','evaluation_3ghz_relative_l2',
                'conversion_error_m','conversion_refinement_change_m','boundary_movement_m',
                'mean_node_to_exact_boundary_distance_m','maximum_node_to_exact_boundary_distance_m']
    replay=[]
    for state in range(6):
        old=torch.load(track(SHORT / arm / f'accepted_{state:03d}.pt'),map_location='cpu',weights_only=False)
        new=torch.load(track(path / f'accepted_{state:03d}.pt'),map_location='cpu',weights_only=False)
        replay.append({'state':state,'state_dict_equal':all(torch.equal(old['state_dict'][k],new['state_dict'][k]) for k in old['state_dict']),
                       'parameter_vector_equal':bool(np.array_equal(old['record'].parameter_vector,new['record'].parameter_vector)),
                       'geometry_points_equal':bool(np.array_equal(old['record'].geometry_points,new['record'].geometry_points)),
                       'shared_metrics_equal':all(short_metrics['trajectory'][state][k]==metrics['trajectory'][state][k] for k in comparable)})
    fields=[row for row in field_rows if row['arm']==arm]
    earliest_geometry_binding=next((row['accepted_state'] for row in bindings if row['binding_reasons'] and any(r.startswith('conversion') or r=='extraction_topology' for r in row['binding_reasons'])),None)
    report['arms'][arm]={
        'accepted_updates':last,'candidate_evaluations':len(trials),'inverse_seconds':metrics['inverse_seconds'],
        'serialized_result':convergence,'optimizer_record_count':manifest['optimizer_record_count'],
        'not_stopped_by_work_cap':last<summary['caps_per_arm']['accepted_updates'] and len(trials)<summary['caps_per_arm']['attempted_candidates'] and metrics['inverse_seconds']<summary['caps_per_arm']['wall_seconds'],
        'initial_metrics':metrics['trajectory'][0],'final_metrics':metrics['trajectory'][-1],
        'initial_field':fields[0],'final_field':fields[-1],
        'minimum_contour_G_over_accepted_states':min(row['G_min'] for row in fields),
        'maximum_contour_spread_over_accepted_states':max(row['G_spread'] for row in fields),
        'all_accepted_single_component':all(row['topology_single_component'] for row in fields),
        'terminal_trial_count':len(terminal),'terminal_counts':counts(terminal),
        'terminal_by_method':{method:counts([t for t in terminal if t['method']==method]) for method in ('adam','adjoint_steepest_descent')},
        'smallest_terminal_trials':{method:next(t for t in terminal if t['method']==method and t['backtracks']==14) for method in ('adam','adjoint_steepest_descent')},
        'terminal_proposals_are_data_and_total_descent_before_geometry':descent,
        'empty_adam_moments_restored_after_terminal_rejection':restored_moments,
        'binding_constraints':bindings,'earliest_geometry_binding_accepted_state':earliest_geometry_binding,
        'last_ten_accepted_steps':accepted[-10:],
        'below_reporting_step_floor_100um':[t['iteration']+1 for t in accepted if t['boundary_movement_m']<1e-4],
        'first_five_updates_match_short':{'states':replay,'all_common_metrics_equal':all(x['shared_metrics_equal'] for x in replay),
              'all_saved_weights_and_geometry_equal':all(x['state_dict_equal'] and x['parameter_vector_equal'] and x['geometry_points_equal'] for x in replay),
              'trial_prefix_exactly_equal':trials[:len(short_trials)]==short_trials,
              'short_terminal_missing_gradient_is_not_compared':True},
    }
report['interpretation']={
    'completion':'Execution and posthoc reporting completed successfully; both inverse searches exhausted all15 Adam and15 fallback backtracks at nonzero loss, not convergence or a work cap.',
    'E0_stop':'Smallest candidates fail independent raw-contour topology because a second component is detected; final accepted contour itself passes current single-component checks.',
    'E1_stop':'Smallest candidates exceed the fixed conversion-distance budget; refinement change passes. A larger Adam backtrack2 candidate lowers data loss but exceeds the2mm motion limit.',
    'wrong_shape_cause':'Terminal feasibility gates describe why search stops. They do not establish why earlier neural updates created the remaining non-target geometry. Field-conditioning deterioration is correlated evidence, not a new causal repair experiment.',
    'do_not_promote':'Do not count micrometre accepted motion as recovery, relax tolerances, silently deepen backtracking, or describe accepted-state topology as a continuum certificate.'}
(OUT/'terminal_review.json').write_text(json.dumps(report,indent=2)+'\n')
(OUT/'terminal_candidates.json').write_text(json.dumps(terminal_rows,indent=2)+'\n')
with (OUT/'accepted_field_trajectory.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(field_rows[0]));writer.writeheader();writer.writerows(field_rows)
print(json.dumps({arm:{key:row[key] for key in ('accepted_updates','candidate_evaluations','serialized_result','terminal_counts','earliest_geometry_binding_accepted_state','below_reporting_step_floor_100um','first_five_updates_match_short')} for arm,row in report['arms'].items()},indent=2))
