"""Check saved diagnostic claims and evidence hashes without rerunning solves."""
import hashlib
import json
from pathlib import Path

here=Path(__file__).resolve().parent
read=lambda path: json.loads(path.read_text())
checks={}
legacy=read(here/'legacy_replay_resolved/curve_only/metrics.json')
checks['legacy_replay_recovers']=(legacy['accepted_updates']==44
    and legacy['reconstruction_stop_reason']=='stable_data_and_geometry'
    and legacy['canonical_fields']['holdout_relative_l2']<1.4e-8)
for name,counts,limit in [('circle_staged',[5,0,0,0],1e-8),('star_staged',[9,4,0,0],4e-7)]:
    result=read(here/name/'result.json')
    checks[name+'_complete']=(len(result['stages'])==4
        and all(s['stage_outcome']=='NORMAL_OPTIMIZER_RETURN' for s in result['stages']))
    checks[name+'_updates']=[s['accepted_steps'] for s in result['stages']]==counts
    checks[name+'_full_final_capacity']=result['final_state'][0]['maximum_mode']==17
    checks[name+'_field_accuracy']=max(result['relative_field_error'])<limit
    checks[name+'_resolution']=max(result['cross_resolution'])<1e-10
    checks[name+'_no_blocked_stencils']=all(s['one_sided_columns']==s['unresolved_columns']==0 for s in result['stages'])
    for number in range(1,5):
        records=[json.loads(line) for line in (here/name/f'stage_{number}/trajectory.jsonl').read_text().splitlines()]
        losses=[r['loss'] for r in records]
        checks[f'{name}_stage_{number}_monotone']=all(b<a for a,b in zip(losses,losses[1:]))
        acceptance=here/name/f'stage_{number}/acceptance.json'
        if acceptance.exists():
            checks[f'{name}_stage_{number}_no_numerical_refusal']=all(not r.get('numerical_obstruction',False) for r in read(acceptance))
derivatives=read(here/'derivative_diagnostics.json')
backtrack=read(here/'rejected_step_diagnostics.json')
base,half,full=backtrack['trial_scales']
checks['half_step_passes_existing_accuracy_guard']=(half['feasible']
    and half['discrepancy'][0]<1e-5 and full['discrepancy'][0]>1e-5
    and half['production_loss']<base['production_loss']
    and half['refined_loss']<base['refined_loss'] and half['acceptance']['accepted'])
checks['low_order_start_well_conditioned']=backtrack['K4_initial_condition_number']<2.
for row in derivatives:
    key=row['case']+'_'+row['state']
    checks[key+'_finite_analytic']=row['finite_reciprocal_jacobian']
    checks[key+'_operator_agreement']=row['jacobian_relative_difference']<2e-7
    if row['state']=='failed_endpoint':
        checks['blocked_column_disappears_with_smaller_probe']=(row['stencils'][0]['counts']['unresolved']==1
            and row['stencils'][1]['counts'].get('unresolved',0)==0)
        checks['failed_endpoint_derivative_resolution']=row['jacobian_512_vs_1024_relative']<1e-8
manifest_path=here/'manifest.json'
penalty=read(here/'circle_full_penalty_resolved/result.json')
checks['curvature_control_keeps_full_capacity']=penalty['config']['bands']==[17,17,17,17]
checks['curvature_control_limit_reported']=penalty['stages'][-1]['stage_outcome']=='TRIAL_WALL_LIMIT'
checks['curvature_control_geometry']=penalty['radial_rms_mm']<.009 and penalty['radial_max_mm']<.018
checks['curvature_control_no_blocked_stencils']=all(s['one_sided_columns']==s['unresolved_columns']==0 for s in penalty['stages'])
if manifest_path.exists():
    manifest=read(manifest_path)
    for name,digest in manifest['artifact_sha256'].items():
        checks['artifact:'+name]=hashlib.sha256((here/name).read_bytes()).hexdigest()==digest
    root=Path(manifest['repository_root'])
    for name,digest in manifest['source_and_input_sha256'].items():
        checks['source_or_input:'+name]=hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
print(json.dumps(dict(passed=all(checks.values()),checks=checks),indent=2))
if not all(checks.values()): raise SystemExit(1)
