"""TOP-018 only: saved-state qualification and one conditional two-star pair.

Existing numerical methods/defaults are imported unchanged. Run `campaign` once
with a fresh --bundle and a source-bound --validation record. Summary rebuilding
is separate and never dispatches physical work.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_top017 as m
import run_top016_screen as screen
import run_topology_recovery_followup as follow

p = m.p
read, write = m.read, m.write
HISTORY = follow.HISTORY
REUSE = ROOT/'results/validation/topology/TOP-017-followup-20260914-engineering/resolution'
SCENE = 'far-two-stars'
NODES = (256, 512)
FREQUENCIES = p.TRAIN + p.EVALUATION
TOLERANCES = np.array([1e-5,1e-7,1e-7,1e-7,1e-5,1e-5])
COMMON_HASH = '8fa832c90e40dd36ee4912ec924788d98ddff3390e28c57eef4d21b2a3101559'
# Source compatibility reviewed before TOP-018, not a blanket ignore of changes.
REVIEWED_DRIVER_HASHES = {
    'run_top017.py':'043727196c5e763bff6d5d7210ad2865c3abc40c1823b3d7f36341bbbd0cacf4',
    'run_topology_recovery_followup.py':'a76af0b61ddd2b38fd1ada84b56d31ef54f1aa451562aa87e9b0e9ace40bffdb',
}


def require(condition, reason):
    if not condition:
        raise m.ImplementationError(reason)


def source_hashes():
    return {**m.source_hashes(), **{str(x.relative_to(ROOT)):p.digest(x)
            for x in sorted(Path(__file__).parent.glob('*.py'))}}


def solve_config():
    return p.driver.baseline.iteration01_solve_config()


def complex_array(record):
    return np.array(record['real'])+1j*np.array(record['imag'])


def discrepancy(low, high):
    norms=np.linalg.norm(high,axis=0)
    if not np.all(np.isfinite(norms)) or np.any(norms<=0):
        raise m.NumericalFailure('zero/nonfinite refined prediction norm')
    value=p.relative(low,high)
    if not np.all(np.isfinite(value)):
        raise m.NumericalFailure('nonfinite prediction discrepancy')
    return value


def validated_inputs():
    """Read-only provenance and geometry reconstruction; no physical calls."""
    manifest=read(REUSE/'manifest.json')
    for name,sha in manifest['historical_sha256'].items():
        require(p.digest(ROOT/name)==sha, f'historical input changed: {name}')
    for name,sha in read(REUSE/'artifact_manifest.json').items():
        require(p.digest(REUSE/name)==sha, f'saved audit changed: {name}')
    differences={}
    for name,sha in manifest['source_sha256'].items():
        current=p.digest(ROOT/name)
        if current!=sha:
            require(REVIEWED_DRIVER_HASHES.get(name)==current, f'unreviewed prediction source: {name}')
            original=subprocess.check_output(['git','show',manifest['git_revision']+':'+name],cwd=ROOT)
            require(hashlib.sha256(original).hexdigest()==sha, f'reuse measured source mismatch: {name}')
            differences[name]=dict(measured=sha,current=current,
                review='iteration_11/02_proposals/02_TOP018_current_checkout_review.md')
    state=p.driver.deserialize_state(read(HISTORY/'inputs'/SCENE/'state.json'))
    require(m.state_hash(state)==COMMON_HASH, 'COMMON state mismatch')
    require(read(HISTORY/'reuse.json')[SCENE]['state_sha256']==COMMON_HASH, 'reuse COMMON mismatch')
    for arm in ('S','F'):
        for saved in (read(HISTORY/'runs'/f'{arm}-{SCENE}'/'metrics.json')['initial_state'],
                      read(HISTORY/'runs'/f'{arm}-{SCENE}'/'stage_2/initial_state.json'),
                      read(m.SOURCE/'runs'/f'{arm}-{SCENE}'/'metrics.json')['final_state']):
            require(m.state_hash(saved)==COMMON_HASH, f'paired start mismatch: {arm}')
    states={'COMMON':state, **{key.upper():value for key,value in follow.archived_states().items()}}
    obstructions=[row for row in read(HISTORY/'runs/F-far-two-stars/stage_2/acceptance.json')
                  if row.get('numerical_obstruction')]
    require(len(obstructions)==1 and obstructions[0]['candidate_state_sha256']==m.state_hash(states['F_REJECTED'])
            and obstructions[0]['base_state_sha256']==m.state_hash(states['F_RETAINED']),
            'replayed candidate is not the unique saved obstruction')
    reused=read(REUSE/'result.json')
    for label in ('F_RETAINED','S_ENDPOINT'):
        arm,stage=('F',2) if label=='F_RETAINED' else ('S',3)
        require(m.state_hash(read(HISTORY/'runs'/f'{arm}-{SCENE}'/f'stage_{stage}/terminal.json')['final_state'])
                ==m.state_hash(states[label]), f'audit terminal mismatch: {label}')
    for label in ('F_RETAINED','S_ENDPOINT','F_REJECTED'):
        row=reused['states'][label[0]+label[1:].lower()]
        require(m.state_hash(states[label])==row['state_sha256']==m.state_hash(row['state']),
                f'reused state mismatch: {label}')
    observed,evaluation=m.observations(HISTORY,SCENE)
    training=read(HISTORY/'inputs'/SCENE/'training_observations.json')
    original=read(HISTORY/'inputs'/SCENE/'observations.json')
    require(training['frequencies_hz']==list(p.TRAIN), 'training order mismatch')
    require(original['frequencies_hz']==[p.TRAIN[0],*p.EVALUATION], 'evaluation order mismatch')
    require(observed.shape==(24,4) and evaluation.shape==(24,2), 'observation shape mismatch')
    for key in ('observed_real','observed_imag'):
        require([x[0] for x in training[key]]==[x[0] for x in original[key]], '0.5 GHz column changed')
    linked=ROOT/training['acquisition_and_material_source']
    require(p.digest(linked)==training['source_sha256'] and read(linked)==original, 'acquisition provenance mismatch')
    problem=p.driver.baseline._problem(np.array(original['frequencies_hz']))
    for key in ('source_points','receiver_points','eps0','mu0'):
        require(np.array_equal(getattr(problem,key),original[key]),f'acquisition mismatch: {key}')
    for key in ('exterior','interior'):
        require(asdict(getattr(problem,key))==original[key],f'material mismatch: {key}')
    strengths=np.array(original['source_strengths_real'])+1j*np.array(original['source_strengths_imag'])
    require(np.array_equal(problem.source_strengths,strengths), 'source strength mismatch')
    for contract in (read(HISTORY/'contract.json'),read(REUSE/'contract.json')):
        require(asdict(solve_config())==contract['solve_config'], 'solve config changed')
    require(reused['frequencies_hz']==list(FREQUENCIES), 'reused frequency mismatch')
    require(np.array_equal(reused['prediction_tolerances'],TOLERANCES), 'reused tolerance mismatch')
    opt=read(HISTORY/'inputs'/SCENE/'optimizer.json')
    optimizer=m.rt.ParameterFDConfig(**opt['config'])
    require(optimizer.loss_tolerance==1e-14 and optimizer.finite_difference_steps==1e-4,
            'optimizer settings differ from contract')
    require(all(c.maximum_mode==9 for c in state.components) and len(state.components)==2,'shape space mismatch')
    # Checks the residual scales without evaluating the forward model.
    p.training_data(p.TRAIN,observed)
    provenance=dict(common_state_sha256=COMMON_HASH,component_ids=state.component_ids,
        historical_prediction_solves=54,historical_prediction_wall_seconds=reused['work']['active_wall_seconds'],
        reuse_measured_revision=manifest['git_revision'],reviewed_source_differences=differences,
        historical_sha256=manifest['historical_sha256'],reuse_result_sha256=p.digest(REUSE/'result.json'),
        normalized_state_sha256={key:m.state_hash(value) for key,value in states.items()})
    return states,observed,evaluation,optimizer,provenance


def prepare(bundle, validation):
    bundle.mkdir(parents=True,exist_ok=False)
    states,observed,evaluation,optimizer,provenance=validated_inputs()
    tests=read(validation)
    require(tests['status']=='PASS' and tests['source_sha256']==source_hashes(), 'tests do not qualify this source')
    test_log=validation.parent/tests['log']
    require(p.digest(test_log)==tests['log_sha256'],'test log changed')
    destination=bundle/'inputs'/SCENE
    destination.mkdir(parents=True)
    for name in ('state.json','optimizer.json','observations.json','training_observations.json'):
        shutil.copyfile(HISTORY/'inputs'/SCENE/name,destination/name)
    for name in ('scene_spec.json','contract.json'):
        shutil.copyfile(HISTORY/name,bundle/('top017_contract.json' if name=='contract.json' else name))
    shutil.copyfile(REUSE/'result.json',bundle/'reused_resolution.json')
    shutil.copyfile(validation,bundle/'pre_dispatch_validation.json')
    shutil.copyfile(test_log,bundle/'pre_dispatch_tests.log')
    for src,dst in [('docs/iterations/topology/iteration_11/03_plan.md','approved_plan.md'),
                    ('experiments/top018/implementation_review.md','implementation_review.md')]:
        shutil.copyfile(ROOT/src,bundle/dst)
    write(bundle/'reuse.json',provenance)
    write(bundle/'contract.json',dict(experiment='TOP-018',approval='2026-09-15 user: yesh',
        nodes=NODES,maximum_mode=9,frequencies_hz=FREQUENCIES,prediction_tolerances=TOLERANCES,
        phase_a_solve_cap=256,phase_a_seconds=900,trial_solve_cap=7000,trial_seconds=7200,
        campaign_solve_cap=14256,campaign_seconds=15300,stage_plan=list(zip((2,3,4),m.QUOTAS)),
        endpoint_reserve=12,normalization=m.NORMALIZATION,derivative_steps=[1e-4,5e-5],
        derivative_relative_stability=.25,derivative_floor_multiplier=5,
        derivative_directions='first and last deterministic reduced gauge basis rows',
        solve_config=asdict(solve_config()),optimizer=asdict(optimizer),
        geometry_configs={str(n):asdict(p.driver.baseline._geometry_config(n)) for n in (128,256,512)},
        owner='Codex /root',reviewer='owner review; no independent agent',
        supplied_component_count=True,new_observations=False,optimizer_receives_truth=False,
        optimizer_receives_evaluation=False,historical_prediction_solves=54,numerical_workers=2))
    files=[x for x in bundle.rglob('*') if x.is_file()]
    write(bundle/'manifest.json',dict(git_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256=source_hashes(),input_sha256={str(x.relative_to(bundle)):p.digest(x) for x in files},
        historical_sha256=provenance['historical_sha256'],command=sys.argv))


def verify(bundle):
    manifest=read(bundle/'manifest.json')
    require(manifest['source_sha256']==source_hashes(),'source changed after freeze')
    for name,sha in manifest['input_sha256'].items():
        require(p.digest(bundle/name)==sha,f'frozen input changed: {name}')
    for name,sha in manifest['historical_sha256'].items():
        require(p.digest(ROOT/name)==sha,f'history changed: {name}')


def objective_identity(state,frequencies,observed):
    objective=dict(active_frequencies_hz=list(frequencies),normalization=m.NORMALIZATION,
        production_nodes=NODES[0],refined_nodes=NODES[1],solve_config=asdict(solve_config()),
        geometry_configs={str(n):asdict(p.driver.baseline._geometry_config(n)) for n in NODES},
        acquisition_and_material_sha256=p.digest(HISTORY/'inputs'/SCENE/'observations.json'),
        observation_sha256=hashlib.sha256(np.asarray(observed,dtype=np.complex128).tobytes()).hexdigest())
    return dict(state_sha256=m.state_hash(state),objective_sha256=m.state_hash(objective),**objective)


def score_predictions(state,spec,observed,evaluation,predictions):
    scene=next(s for s in spec['scenes'] if s['id']==SCENE)
    geometry=p.benchmark.geometry_metrics(state,scene,spec)
    train=discrepancy(predictions[512][:,:4],observed)
    ev=discrepancy(predictions[512][:,4:],evaluation)
    differences=discrepancy(predictions[256],predictions[512])
    gates=dict(count=geometry['component_count']==geometry['truth_component_count'],
        boundary=geometry['maximum_matched_hausdorff_m']<=.001,iou=geometry['union_iou']>=.90,
        original_training=float(train[0])<=.003,evaluation=float(max(ev))<=.05)
    return dict(geometry=geometry,training_errors=train,evaluation_errors=ev,
        maximum_evaluation_error=float(max(ev)),gates=gates,original_gates_pass=all(gates.values()),
        numerical_checks=dict(training_discrepancy=differences[:4],evaluation_discrepancy=differences[4:]),
        numerically_qualified=bool(np.all(differences<=TOLERANCES)),
        state_sha256=m.state_hash(state),production_nodes=256,refined_nodes=512,
        aggregate_objectives={str(k):.5*float(np.mean(train[:k]**2)) for k in (1,2,3,4)})


def quotient(base,sides,h):
    if -1 in sides and 1 in sides:return (sides[1]-sides[-1])/(2*h),'central'
    if 1 in sides:return (sides[1]-base)/h,'forward'
    if -1 in sides:return (base-sides[-1])/h,'backward'
    raise m.UnresolvedDerivative('both prescribed finite-difference sides refused')


def derivative_qualified(coarse,fine,half_step,floor):
    norm=float(np.linalg.norm(fine))
    relative=float(np.linalg.norm(coarse-fine)/norm) if norm>0 else None
    signal=float(half_step*norm)
    passed=bool(relative is not None and np.isfinite(relative) and relative<=.25
                and np.isfinite(floor) and floor>0 and signal>=5*floor)
    return dict(relative_scale_discrepancy=relative,half_step_residual_signal=signal,
                numerical_floor=float(floor),floor_multiplier=5,passed=passed)


def derivative_check(state,observed,bases,ledger,output):
    basis=state.gauge_tangent_basis();selected=(0,len(basis)-1)
    data=p.training_data(p.TRAIN,observed)
    residual=lambda value:p.normalized_complex_residual(value,observed,data.frequency_weights)[0]
    base_res={n:residual(bases[n][:,:4]) for n in NODES}
    repeated=p.prediction(state,p.TRAIN,256,solve_config(),ledger,'derivative_repeatability')
    repeat=float(np.linalg.norm(residual(repeated)-base_res[256]))
    record=dict(state_sha256=m.state_hash(state),basis=basis,selected_rows=selected,
        objective=objective_identity(state,p.TRAIN,observed),steps=[1e-4,5e-5],
        residual_order='pair-major/frequency-minor real flatten, then imaginary flatten',
        residual_scaling='column observed L2 normalization times sqrt(1/4)',
        repeatability_residual_norm=repeat,rows=[],passed=False)
    write(output/'derivative.json',record)
    for index in selected:
        direction=basis[index]
        physical=screen.normal_rms(state,state.incremented(direction*1e-5))/1e-5
        row=dict(basis_index=index,direction=direction,physical_normal_rms_per_unit=physical,
                 estimates={},checks=[],passed=False)
        record['rows'].append(row)
        if physical<=1e-10:
            row['obstruction']='physically trivial prescribed direction'
            write(output/'derivative.json',record)
            return record
        estimates={}
        # Complete two-scale/two-resolution direction batch; no partial dispatch.
        ledger.reserve(2*2*2*len(p.TRAIN))
        for h in (1e-4,5e-5):
            sides={n:{} for n in NODES};refusals=[]
            for sign in (-1,1):
                try:
                    trial=state.incremented(sign*h*direction).polar_angle_gauge_fixed()[0]
                    if not p.feasible(trial,NODES,solve_config(),.008):
                        refusals.append(dict(sign=sign,reason='physical feasibility refused'));continue
                except ValueError as exc:
                    refusals.append(dict(sign=sign,reason=str(exc)));continue
                for n in NODES:
                    value=p.prediction(trial,p.TRAIN,n,solve_config(),ledger,'directional_derivative')
                    sides[n][sign]=residual(value)
            for n in NODES:
                try:value,stencil=quotient(base_res[n],sides[n],h)
                except m.UnresolvedDerivative:
                    row['obstruction']='both sides refused'
                    write(output/'derivative.json',record);return record
                estimates[n,h]=value
                row['estimates'][f'{n}:{h:g}']=dict(derivative=value,stencil=stencil,refusals=refusals,
                    side_residuals={str(s):v for s,v in sides[n].items()})
        # Existing signal/floor rule, using discretization disagreement of the
        # same directional residual change, with repeatability/machine floors.
        uncertainty=5e-5*float(np.linalg.norm(estimates[256,5e-5]-estimates[512,5e-5]))
        floor=max(repeat,64*np.finfo(float).eps,uncertainty)
        for n in NODES:
            row['checks'].append(dict(nodes=n,**derivative_qualified(
                estimates[n,1e-4],estimates[n,5e-5],5e-5,floor)))
        row['passed']=all(c['passed'] for c in row['checks'])
        write(output/'derivative.json',record)
    record['passed']=all(r['passed'] for r in record['rows'])
    write(output/'derivative.json',record)
    return record


def release_gate(audit):
    failures=[]
    for key in ('inputs_verified','tests_verified','source_integrity'):
        if not audit.get(key):failures.append(key)
    rows=audit.get('states',{})
    for label in ('COMMON','F_RETAINED','S_ENDPOINT','F_REJECTED'):
        row=rows.get(label,{})
        feasible=all(row.get('feasible',{}).get(str(n),False) for n in NODES)
        if label=='F_REJECTED' and (row.get('status')=='NOT_RECOVERABLE' or (row.get('feasible') and not feasible)):
            continue
        if not feasible or not row.get('qualified_256_512'):failures.append(label)
    if not audit.get('derivative',{}).get('passed'):failures.append('directional_derivative')
    return dict(passed=not failures,failed_requirements=failures)


def released_arms(audit):
    return ('S','F') if audit.get('status')=='PHASE_A_PASS' and audit.get('gate',{}).get('passed') else ()


def phase_a(bundle,seconds=900):
    output=bundle/'phase_a';output.mkdir(exist_ok=False)
    ledger=m.Ledger(cap=256,seconds=min(900,seconds))
    result=dict(status='IN_PROGRESS',states={},inputs_verified=False,tests_verified=False,
                source_integrity=False,derivative={'passed':False},historical_reused_solves=54)
    predictions={}
    try:
        verify(bundle)
        states,observed,evaluation,optimizer,provenance=validated_inputs()
        result.update(inputs_verified=True,tests_verified=True)
        reused=read(bundle/'reused_resolution.json')
        prediction_context=dict(source_manifest_sha256=m.state_hash(read(bundle/'manifest.json')['source_sha256']),
            acquisition_and_material_sha256=p.digest(bundle/'inputs'/SCENE/'observations.json'),
            frequencies_hz=FREQUENCIES,solve_config=asdict(solve_config()))
        result['prediction_context']=prediction_context
        with ledger.instrument():
            for label,state in states.items():
                row=dict(state=p.driver.serialize_state(state),state_sha256=m.state_hash(state),
                    feasible={},predictions={},comparisons={},status='AVAILABLE')
                result['states'][label]=row;predictions[label]={}
                gauged,gauge_change=state.polar_angle_gauge_fixed()
                row['gauge_retraction_change']=gauge_change
                row['gauge_coefficient_change']=float(np.max(np.abs(gauged.parameter_vector()-state.parameter_vector())))
                require(row['gauge_coefficient_change']<1e-10,f'{label} gauge mismatch')
                for nodes in (128,256,512):
                    row['feasible'][str(nodes)]=p.feasible(state,(nodes,),solve_config(),.008)
                    if not row['feasible'][str(nodes)]:continue
                    if label=='COMMON':
                        values=p.prediction(state,FREQUENCIES,nodes,solve_config(),ledger,'common_resolution')
                        origin='new'
                    else:
                        saved=reused['states'][label[0]+label[1:].lower()]
                        values=complex_array(saved['predictions'][str(nodes)])
                        origin='verified_historical_prediction'
                        ledger.calls['historical_prediction_cache_hits']+=len(FREQUENCIES)
                    predictions[label][nodes]=values
                    identity=dict(state_sha256=m.state_hash(state),nodes=nodes,
                        geometry_config=asdict(p.driver.baseline._geometry_config(nodes)),**prediction_context)
                    row['predictions'][str(nodes)]=dict(**follow.complex_record(values),origin=origin,
                        configuration_sha256=m.state_hash(identity))
                for low,high in ((128,256),(256,512)):
                    if low not in predictions[label] or high not in predictions[label]:continue
                    eta=discrepancy(predictions[label][low],predictions[label][high])
                    row['comparisons'][f'{low}/{high}']=dict(discrepancy=eta,tolerance=TOLERANCES,
                        threshold_fraction=eta/TOLERANCES,threshold_distance=TOLERANCES-eta,
                        qualified=bool(np.all(eta<=TOLERANCES)))
                row['qualified_256_512']=row['comparisons'].get('256/512',{}).get('qualified',False)
                if len(row['comparisons'])==2:
                    coarse=np.array(row['comparisons']['128/256']['discrepancy'])
                    fine=np.array(row['comparisons']['256/512']['discrepancy'])
                    row['contraction_ratio_fine_over_coarse']=[float(b/a) if a>0 else None for a,b in zip(coarse,fine)]
                write(output/'audit.json',result)
                print('Phase A',label,'qualified 256/512',row['qualified_256_512'],flush=True)
            if all(n in predictions.get('F_REJECTED',{}) for n in (128,256,512)):
                losses={label:{str(n):.5*float(np.mean(discrepancy(values[:,:2],observed[:,:2])**2))
                        for n,values in predictions[label].items()} for label in ('F_RETAINED','F_REJECTED')}
                result['rejected_step']=dict(losses=losses,acceptance={f'{low}/{high}':m.old.acceptance(
                    losses['F_RETAINED'][str(low)],losses['F_REJECTED'][str(low)],
                    losses['F_RETAINED'][str(high)],losses['F_REJECTED'][str(high)]) for low,high in ((128,256),(256,512))},
                    accepted=False,purpose='saved candidate audit only')
                old=read(HISTORY/'runs/F-far-two-stars/stage_2/acceptance.json')[-1]
                result['rejected_step']['historical_discrepancy']=old['prediction_discrepancy']
                result['rejected_step']['reproduced_old_discrepancy']=result['states']['F_REJECTED']['comparisons']['128/256']['discrepancy'][:2]
            # Numerical state failure is sufficient to stop; no budget spending
            # on derivatives is required once the binding release cannot pass.
            provisional=dict(result,source_integrity=True,derivative={'passed':True})
            if release_gate(provisional)['passed']:
                result['derivative']=derivative_check(states['COMMON'],observed,predictions['COMMON'],ledger,output)
            if all(n in predictions['COMMON'] for n in NODES):
                result['common_score']=score_predictions(states['COMMON'],read(bundle/'scene_spec.json'),
                    observed,evaluation,predictions['COMMON'])
        verify(bundle);result['source_integrity']=True
        result['gate']=release_gate(result)
        result['status']='PHASE_A_PASS' if result['gate']['passed'] else 'PHASE_A_FAIL'
    except Exception as exc:
        result.update(status='PHASE_A_FAIL',reason=getattr(exc,'code',type(exc).__name__),
                      detail=str(exc),traceback=traceback.format_exc(),gate={'passed':False})
    result['work']=ledger.snapshot()
    write(output/'audit.json',result)
    return result


def schedule(initial,arm,observed,optimizer,floor,ledger,output,initial_score,scorer,
             fit=m.fit_stage,feasibility=p.feasible):
    """Historical schedule plus strictly reporting-only numerical-stop scoring."""
    def bound_score(state):
        score=scorer(state)
        active=1 if arm=='S' else ledger.stage
        score.update(objective_identity(state,p.TRAIN[:active],observed[:,:active]))
        return score
    result=m.run_schedule(initial,arm,observed,NODES,solve_config(),optimizer,floor,ledger,output,
        initial_score,bound_score,fit=fit,feasibility=feasibility)
    if result.get('reason')=='NUMERICAL_FAILURE' and result.get('stages'):
        last=result['stages'][-1]
        if 'score' not in last:
            retained=p.driver.deserialize_state(result['final_state'])
            try:
                if feasibility(retained,NODES,solve_config(),floor):
                    with ledger.endpoint_scope():ledger.reserve(12)
                    result['reporting_score']=bound_score(retained)
                    result['reporting_score_state_sha256']=m.state_hash(retained)
                    result['reporting_score_releases_stage']=False
                else:result['reporting_score_missing_reason']='retained geometry infeasible'
            except Exception as exc:
                result['reporting_score_missing_reason']=f'{type(exc).__name__}: {exc}'
    result['work']=ledger.snapshot()
    for stage in result['stages']:
        active=len(stage['active_frequencies_hz'])
        terminal=stage['terminal']
        state=p.driver.deserialize_state(terminal['final_state'])
        terminal['objective_identity']=objective_identity(state,p.TRAIN[:active],observed[:,:active])
        gradient=terminal.get('gradient')
        if gradient is not None:
            require(gradient['state_sha256']==m.state_hash(state) and gradient['production_nodes']==256
                    and gradient['refined_nodes']==512,'gradient association mismatch')
            gradient['objective_sha256']=terminal['objective_identity']['objective_sha256']
        last_gradient=terminal.get('last_measured_gradient')
        if last_gradient is not None:
            require(last_gradient['active_frequencies_hz']==stage['active_frequencies_hz']
                    and last_gradient['production_nodes']==256 and last_gradient['refined_nodes']==512,
                    'last measured gradient objective/resolution mismatch')
            last_gradient['objective_sha256']=terminal['objective_identity']['objective_sha256']
        stage_path=output/f'stage_{stage["stage"]}'
        if stage_path.exists():
            write(stage_path/'objective_associations.json',dict(
                endpoint=terminal['objective_identity'],gradient=gradient,last_measured_gradient=last_gradient))
    write(output/'metrics.json',result)
    return result


def trial(bundle,arm,seconds=7200):
    verify(bundle)
    audit=read(bundle/'phase_a/audit.json')
    require(arm in released_arms(audit),'Phase A did not release this arm')
    output=bundle/'runs'/f'{arm}-{SCENE}';output.mkdir(parents=True,exist_ok=False)
    initial=p.driver.deserialize_state(read(bundle/'inputs'/SCENE/'state.json'))
    observed,evaluation=m.observations(bundle,SCENE)
    opt=read(bundle/'inputs'/SCENE/'optimizer.json');optimizer=m.rt.ParameterFDConfig(**opt['config'])
    spec=read(bundle/'scene_spec.json');scene=next(s for s in spec['scenes'] if s['id']==SCENE)
    ledger=m.Ledger(cap=7000,seconds=min(7200,seconds))
    write(output/'manifest.json',dict(source_sha256=source_hashes(),input_manifest_sha256=p.digest(bundle/'manifest.json'),
        phase_a_sha256=p.digest(bundle/'phase_a/audit.json'),initial_state_sha256=m.state_hash(initial),
        production_nodes=256,refined_nodes=512,command=sys.argv,numerical_workers=2,blas_threads=1))
    scorer=lambda s:m.old.score(s,scene,spec,observed,evaluation,NODES,solve_config(),ledger)
    with ledger.instrument():
        result=schedule(initial,arm,observed,optimizer,opt['minimum_component_radius_m'],ledger,output,
                        audit['common_score'],scorer)
    verify(bundle)
    result.update(scene=SCENE,source_integrity=True)
    write(output/'metrics.json',result)
    print(arm,result['status'],result.get('reason'),ledger.total,flush=True)
    return result


def run_worker(bundle,arm,deadline,clock=time.monotonic,popen=subprocess.Popen):
    started=clock()
    if started>=deadline:
        return dict(arm=arm,status='NOT_DISPATCHED',campaign_timeout=True,exit_code=None)
    command=[sys.executable,str(Path(__file__).resolve()),'trial','--bundle',str(bundle),
             '--arm',arm,'--seconds',str(min(7200,deadline-started))]
    with (bundle/f'{arm}.log').open('x') as log:
        process=popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        timeout=False
        try:code=process.wait(timeout=max(.001,deadline-clock()))
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(process.pid,signal.SIGALRM)
            try:code=process.wait(timeout=5.)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);code=process.wait()
    return dict(arm=arm,command=command,exit_code=code,campaign_timeout=timeout,
                elapsed_seconds=clock()-started)


def campaign(bundle,validation):
    prepare(bundle,validation)
    began=time.monotonic();deadline=began+15300
    write(bundle/'environment.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
        cpu=subprocess.check_output(['lscpu'],text=True),initial_load=os.getloadavg(),numerical_workers=2,
        threads={key:os.environ.get(key) for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')},
        command=sys.argv))
    record=dict(status='IN_PROGRESS',workers=[],watchdog_seconds=15300)
    write(bundle/'campaign.json',record)
    audit=phase_a(bundle,min(900,deadline-time.monotonic()))
    record['phase_a_status']=audit['status'];write(bundle/'campaign.json',record)
    arms=released_arms(audit)
    if arms:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run_worker,bundle,arm,deadline) for arm in arms]
            for future in futures:
                record['workers'].append(future.result());write(bundle/'campaign.json',record)
        record['status']='COMPLETE'
    else:record['status']='STOPPED_AT_PHASE_A'
    record['elapsed_seconds']=time.monotonic()-began
    write(bundle/'campaign.json',record)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('campaign','trial'))
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--validation',type=Path)
    parser.add_argument('--arm',choices=('S','F'))
    parser.add_argument('--seconds',type=float,default=7200)
    args=parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        require(os.environ.get(key)=='1','single-thread BLAS required')
    if args.phase=='campaign':
        if args.validation is None:parser.error('--validation is required for campaign')
        result=campaign(args.bundle.resolve(),args.validation.resolve())
    else:
        if args.arm is None:parser.error('--arm is required for trial')
        result=trial(args.bundle.resolve(),args.arm,args.seconds)
    print(json.dumps({'status':result['status']}),flush=True)


if __name__=='__main__':main()
