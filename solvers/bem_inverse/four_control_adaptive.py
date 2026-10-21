"""Charged four-control adaptive decision slots using the maintained LM fit.

The controller consumes supplied observations only. It knows no scene identity,
truth, campaign results, or geometric scoring. All speculative work is retained.
"""
from dataclasses import replace
from time import perf_counter
import traceback
import numpy as np
from .continuation.lm_backend import (Objective,StageResult,Stop,StageQuota,TrialSolveCap,TrialWallLimit,
    NORMAL_RETURN,STAGE_QUOTA,fit_stage,normalize,observe)
from .continuation.geometry import resize
from .modal_muller import ModalMuller,ModalSettings,token
from .modal_accuracy import IndependentModalMuller,WorkspaceEpochRequired,WorkspaceUnresolved
from .four_control_policy import truncated_levels


def common_monitor(problem,curve,physics,ledger,label):
    ledger.reserve(38)
    monitor=ModalMuller(physics.execution,replace(physics.settings,trace_cutoff=None),observer=physics.observer)
    monitor.calculation_role='online_controller_monitor'
    physics._adaptive_receipts.append(monitor.receipt())
    receipt_index=len(physics._adaptive_receipts)-1
    predictions=[]
    for cutoff in (320,352):
        columns=[]
        for o in problem.real:
            ledger.reserve(1);ledger.charge('solve',label)
            try:columns.append(monitor.evaluate(curve,o,problem.contrast,token(cutoff)).prediction)
            except Exception:
                ledger.fail(label)
                observe(physics,'physics_failure',failure=dict(category=label,frequency_hz=o.frequency_hz,
                    resolution=token(cutoff),traceback=traceback.format_exc()),ledger=ledger)
                raise
            finally:physics._adaptive_receipts[receipt_index]=monitor.receipt()
        predictions.append(np.column_stack(columns))
    observed=np.column_stack([o.scattered for o in problem.real]);weights=np.ones(19)/19
    residuals=[normalize(p-observed,observed,weights) for p in predictions]
    fields=np.linalg.norm(predictions[0]-predictions[1],axis=0)/np.maximum(np.linalg.norm(predictions[1],axis=0),1e-30)
    limits=np.asarray([1e-5 if o.frequency_hz<=.5e9 else 1e-7 for o in problem.real])
    result=dict(status='qualified' if np.all(fields<=limits) else 'MONITOR_UNRESOLVED',
        losses=[.5*float(r@r) for r in residuals],work_units=38)
    observe(physics,'qualification',kind_detail='online_controller_monitor',row=dict(result,label=label),
        arrays=dict(coefficients=curve.coefficients,production_prediction=predictions[0],
            witness_prediction=predictions[1],observed=observed,weights=weights,
            production_residual=residuals[0],witness_residual=residuals[1],field_errors=fields),ledger=ledger)
    return result


def choose(base,branches,index):
    eligible=[]
    for branch in branches:
        if not branch['numerically_qualified'] or branch['monitor']['status']!='qualified':continue
        decrease=base['losses'][index]-branch['monitor']['losses'][index]
        useful=decrease>=1e-8 and decrease/max(base['losses'][index],1e-30)>=.01
        if useful:
            eligible.append((decrease/branch['charged_work_units'],branch))
    if not eligible:return None
    maximum=max(x[0] for x in eligible)
    near=[branch for score,branch in eligible if score>=.99*maximum]
    return min(near,key=lambda b:(b['raw_branch_work_units'],('HOLD','F','M','K').index(b['name'])))['name']


def decision_slot(problem,curve,op,policy,physics,update,ledger,state):
    """End the slot at the selected branch endpoint; reset lambda next slot."""
    started=perf_counter();original=curve;original_u=physics.actual_cutoff;original_state=state
    vector=list(state['controls']);stage=op.stage;config=op.optimizer
    if not hasattr(physics,'_adaptive_receipts'):physics._adaptive_receipts=[]
    history=[];trials=[];checks=[];branches=[];current=None;outcome=NORMAL_RETURN;reason=None;detail=None
    result_curve=curve;selected_op=op;winner=None
    try:
        space=update.prepare(curve,stage.update_modes,stage.curve_modes)
        objective=Objective(stage,problem.contrast,config,ledger,physics=physics)
        current=objective.production(curve,'controller_base_qualification')
        if current is None:raise ValueError('controller base fields unresolved')
        matrix=objective.jacobian(current,update,space);gradient=matrix.T@current.residual
        while True:
            promoted=physics.qualify_linearization(current,stage,config,problem.contrast,space,update,
                ledger,matrix,gradient,config.initial_damping)
            if promoted is None:break
            stage,objective,current=promoted['stage'],promoted['objective'],promoted['evaluation']
            matrix,gradient=promoted['matrix'],promoted['gradient']
        original_u=physics.actual_cutoff
        vectors=[('HOLD',tuple(vector))]
        for name,axis in (('F',0),('M',1),('K',2)):
            levels=truncated_levels(axis,policy.caps[axis])
            next_value=next((x for x in levels if x>vector[axis]),None)
            if next_value is not None:
                changed=list(vector);changed[axis]=next_value;vectors.append((name,tuple(changed)))
        # The reservation is against the original 3000-unit slot AND global
        # remainder before switching to bounded branch subquotas.
        try:ledger.reserve(len(vectors)*(200+38)+38)
        except (StageQuota,TrialSolveCap,TrialWallLimit) as exc:
            raise ControllerCensored('complete contest reservation failed: '+str(exc))
        base=common_monitor(problem,curve,physics,ledger,op.label+'_base_monitor')
        slot=(ledger.stage,ledger.stage_start,ledger.stage_quota,ledger.endpoint_reserve)
        for name,controls in vectors:
            branch_op=policy.control_operation(problem,physics,op.label+'_'+name,controls,
                op.details['catalog'],iterations=2,quota=200)
            branch_stage=replace(branch_op.stage,nodes=token(original_u),refined_nodes=token(original_u+32))
            branch_physics=IndependentModalMuller(physics.execution,trace_cap=policy.caps[3],
                workspace=physics.settings.coefficient_workspace,observer=physics.observer)
            branch_physics.actual_cutoff=original_u
            before=ledger.units;ledger.stage=branch_stage.label;ledger.stage_start=before
            ledger.stage_quota=200;ledger.endpoint_reserve=0
            try:
                endpoint=[]
                branch=fit_stage(resize(curve,branch_stage.curve_modes),branch_stage,problem.contrast,
                    update,branch_op.optimizer,ledger,physics=branch_physics,
                    on_accept=lambda iteration,evaluation:endpoint.__setitem__(slice(None),[evaluation]))
            finally:
                ledger.stage,ledger.stage_start,ledger.stage_quota,ledger.endpoint_reserve=slot
            raw=ledger.units-before
            physics._adaptive_receipts.append(branch_physics.receipt())
            if branch.outcome in ('TRIAL_WALL_LIMIT','TRIAL_SOLVE_CAP','EXCEPTION','IMPLEMENTATION_ERROR',
                                  'WORKSPACE_UNRESOLVED','WORKSPACE_EPOCH_PROMOTION_REQUIRED'):
                if branch.outcome=='WORKSPACE_UNRESOLVED':raise WorkspaceUnresolved(branch.detail)
                if branch.outcome=='WORKSPACE_EPOCH_PROMOTION_REQUIRED':raise WorkspaceEpochRequired(branch.detail)
                raise ControllerCensored('contest interrupted by '+branch.outcome+': '+str(branch.detail))
            measured=common_monitor(problem,branch.curve,physics,ledger,branch_stage.label+'_endpoint_monitor')
            row=dict(name=name,controls=controls,outcome=branch.outcome,stop=branch.stop_reason,
                accepted_steps=branch.accepted_steps,raw_branch_work_units=raw,charged_work_units=raw+38,
                monitor=measured,numerically_qualified=branch.outcome in (NORMAL_RETURN,STAGE_QUOTA),
                final_K_u=branch_physics.actual_cutoff)
            observe(physics,'qualification',kind_detail='adaptive_branch_endpoint',
                row=dict(row,history=branch.history,trials=branch.trials,acceptance_checks=branch.acceptance_checks,
                    physics=branch_physics.receipt()),
                arrays=dict(base_coefficients=curve.coefficients,candidate_coefficients=branch.curve.coefficients),ledger=ledger)
            branches.append(dict(row,result=branch,operation=branch_op,
                endpoint_evaluation=endpoint[-1] if endpoint else None))
        if base['status']!='qualified':reason='MONITOR_SELECTION_UNRESOLVED'
        else:
            a,b=choose(base,branches,0),choose(base,branches,1)
            # Useful classifications must also agree even if the winner ties.
            def useful(x,index):
                d=base['losses'][index]-x['monitor']['losses'][index]
                return x['numerically_qualified'] and x['monitor']['status']=='qualified' and d>=1e-8 and d/max(base['losses'][index],1e-30)>=.01
            disagreement=any(useful(x,0)!=useful(x,1) for x in branches)
            if a!=b or disagreement:reason='MONITOR_SELECTION_UNRESOLVED'
            else:winner=a
        if winner is not None:
            chosen=next(x for x in branches if x['name']==winner);branch=chosen['result']
            result_curve=branch.curve;state=dict(state,controls=chosen['controls'])
            physics.actual_cutoff=chosen['final_K_u']
            selected_op=replace(chosen['operation'],label=op.label,
                    stage=replace(chosen['operation'].stage,label=op.label,nodes=branch.final_nodes,
                    refined_nodes=branch.final_refined_nodes,quota=3000),details=dict(op.details,
                    selected_controls=chosen['controls'],adaptive_winner=winner,branch_controller_endpoint=branch.history[-1] if branch.history else None))
            history,trials,checks=branch.history,branch.trials,branch.acceptance_checks
            reason='saved_branch_endpoint'
        else:physics.actual_cutoff=original_u;reason=reason or 'no_useful_qualified_branch'
        observe(physics,'qualification',kind_detail='adaptive_decision',
            row=dict(slot=op.label,winner=winner,reason=reason,lambda_reset=config.initial_damping,
                branches=[{k:v for k,v in x.items() if k not in ('result','operation','endpoint_evaluation')} for x in branches]),
            arrays=dict(original_coefficients=original.coefficients,selected_coefficients=result_curve.coefficients),ledger=ledger)
    except Stop as exc:
        result_curve=original;physics.actual_cutoff=original_u;outcome=exc.code;reason=exc.code;detail=str(exc)
        winner=None;state=original_state;selected_op=op;history=[];trials=[];checks=[]
    except Exception:
        result_curve=original;physics.actual_cutoff=original_u
        outcome='CONTROLLER_EXCEPTION_CENSORED';reason=outcome;detail=traceback.format_exc()
        winner=None;state=original_state;selected_op=op;history=[];trials=[];checks=[]
    if outcome!=NORMAL_RETURN:
        observe(physics,'qualification',kind_detail='adaptive_contest_censored',
            row=dict(slot=op.label,outcome=outcome,detail=detail,eligible=False,
                completed_branches=[{k:v for k,v in x.items() if k not in ('result','operation','endpoint_evaluation')} for x in branches]),
            arrays=dict(retained_base_coefficients=original.coefficients),ledger=ledger)
    result=StageResult(op.label,result_curve,outcome,reason,False,
        sum(h.get('iteration',0)>0 for h in history),chosen['result'].initial_loss if winner is not None else current.loss if current is not None else np.nan,
        history[-1]['loss'] if history else current.loss if current is not None else np.nan,
        history,trials,checks,detail=detail,work=ledger.snapshot(),seconds=perf_counter()-started,
        final_nodes=token(physics.actual_cutoff),final_refined_nodes=token(physics.actual_cutoff+32))
    result.committed_evaluation=(chosen['endpoint_evaluation'] if winner is not None else current) if outcome==NORMAL_RETURN else None
    return result,selected_op,state


class ControllerCensored(Stop):
    code='CONTROLLER_BUDGET_CENSORED'
