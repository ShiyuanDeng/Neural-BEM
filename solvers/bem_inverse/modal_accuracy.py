"""Opt-in independent modal trace qualification at a fixed coefficient workspace.

Qualification reuses the ordinary objective, LM model, clipping and trial map.
Witness fields never supply a move above a production cap. This backend does
not select scenes, compare research arms, or change the ordinary defaults.
"""
from . import checks
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import numpy as np
from .modal_muller import ModalMuller, ModalSettings, token, trace_cutoff
from .continuation.lm_backend import Objective, NumericalFailure, Stop, resolution_check, observe
from .continuation.globalization import damping_floor
from .continuation.geometry import grid_size, values
from .errors import UpdateRefused
from .geometry_update_methods import bind_geometry_update, control_step

TRACE_LADDER=(64,96,128,160,192,256,320)


class TraceCapUnresolved(NumericalFailure):
    code='KU_CAP_UNRESOLVED'


class WorkspaceUnresolved(NumericalFailure):
    code='WORKSPACE_UNRESOLVED'


class WorkspaceEpochRequired(Stop):
    code='WORKSPACE_EPOCH_PROMOTION_REQUIRED'


def displacement_comparison(base,lower,higher,length_unit_m,*,linear=False):
    previous=None; arrays=None; row=None
    for count in (2**k for k in range(int(np.log2(grid_size(base.band))),17)):
        nodes=base.nodes(count)
        weights=nodes.arc_length_weights/nodes.perimeter
        low=values(lower,count)*length_unit_m
        high=values(higher,count)*length_unit_m
        difference=abs(low-high)
        rms=float(np.sqrt(weights@(difference**2))); maximum=float(np.max(difference))
        reference_rms=float(np.sqrt(weights@(abs(high)**2))); reference_max=float(np.max(abs(high)))
        row=dict(rms_difference_m=rms,maximum_difference_m=maximum,reference_rms_m=reference_rms,
            reference_maximum_m=reference_max,quadrature_points=count,
            displacement_definition='linear complete Cartesian tangent' if linear else 'finite centered trial displacement')
        row['equivalent']=checks.displacement_equivalent(rms, maximum, reference_rms, reference_max)
        if checks.displacement_quadrature_resolved(previous, rms, maximum):
            row['quadrature_resolved']=True
            arrays=dict(parameters=nodes.parameters,weights=weights,lower_displacement_m=low,
                        higher_displacement_m=high)
            break
        previous=(rms,maximum)
    if arrays is None:
        row.update(quadrature_resolved=False,equivalent=False)
        arrays=dict(parameters=nodes.parameters,weights=weights,lower_displacement_m=low,higher_displacement_m=high)
    return row,arrays


class IndependentModalMuller(ModalMuller):
    strict_dispatch=True
    qualified_controller=True

    def __init__(self,execution_settings,*,trace_cap=192,workspace=512,observer=None,
                 reject_unresolved_candidates=True):
        if trace_cap not in TRACE_LADDER or workspace not in (512,768):
            raise ValueError('Use a declared trace cap and common workspace epoch.')
        super().__init__(execution_settings,ModalSettings(trace_cutoff=64,coefficient_workspace=workspace,
                                                          cached_geometries=1),observer)
        self.trace_cap=trace_cap; self.actual_cutoff=64
        self.reject_unresolved_candidates=reject_unresolved_candidates
        self.calculation_role='production'
        self._frames={}; self._workspace_checked=set(); self._workspace_first=True
        self._workspace_services={}

    @contextmanager
    def usage(self,name):
        previous=self.calculation_role; self.calculation_role=name
        try: yield
        finally: self.calculation_role=previous

    def select_stage(self,curve,stage,config,contrast,update,ledger):
        floor=trace_cutoff(stage.nodes)
        if checks.trace_floor_exceeds_cap(floor, self.trace_cap):
            raise ValueError('Scheduled floor exceeds the hard trace cap.')
        self.actual_cutoff=max(self.actual_cutoff,floor)
        self._frames.clear()
        return replace(stage,nodes=token(self.actual_cutoff),refined_nodes=token(self.actual_cutoff+32)),dict(
            requested_floor=floor,actual_cutoff=self.actual_cutoff,forced=self.actual_cutoff>floor,
            trace_cap=self.trace_cap,B_work=self.settings.coefficient_workspace)

    def audit_stage(self,stage):
        return replace(stage,nodes=token(320),refined_nodes=token(352),resolution_kind='modal')

    def _frame(self,curve,stage,config,contrast,space,update,ledger,cutoff,*,workspace=None):
        workspace=workspace or self.settings.coefficient_workspace
        key=(curve.coefficients.tobytes(),stage.update_modes,stage.curve_modes,
             tuple(id(o) for o in stage.observations),cutoff,workspace)
        if key in self._frames: return self._frames[key]
        service=self
        if workspace!=self.settings.coefficient_workspace:
            if workspace not in self._workspace_services:
                self._workspace_services[workspace]=ModalMuller(self.execution,
                    replace(self.settings,coefficient_workspace=workspace),observer=self.observer)
            service=self._workspace_services[workspace]
            service.calculation_role='workspace_witness'
        finer=replace(stage,nodes=token(cutoff),refined_nodes=token(cutoff+32))
        with self.usage('qualification_witness' if cutoff>self.actual_cutoff else 'qualification_production'):
            objective=Objective(finer,contrast,config,ledger,physics=service)
            ledger.reserve(2*len(stage.observations))
            evaluation=objective.production(curve,'qualification')
            if evaluation is None: raise NumericalFailure('modal qualification field solve failed')
            matrix=objective.jacobian(evaluation,update,space)
        frame=dict(stage=finer,objective=objective,evaluation=evaluation,matrix=matrix,
            gradient=matrix.T@evaluation.residual,cutoff=cutoff,workspace=workspace)
        self._frames[key]=frame
        return frame

    def _proposal(self,frame,config,space,update,carried,*,used=None):
        matrix=frame['matrix']; normal=matrix.T@matrix
        if config.metric!='marquardt': raise ValueError('Independent modal qualification expects the fixed Marquardt metric.')
        metric=np.diag(np.maximum(np.diag(normal),config.scaling_floor))
        floor=damping_floor(normal,metric,config.damping_floor_relative)
        damping=max(carried,floor) if used is None else used
        raw=np.linalg.solve(normal+damping*metric,-frame['gradient'])
        return control_step(raw,space,update,config),damping

    def _compare(self,lower,higher,config,space,update,carried):
        a,b=lower['evaluation'],higher['evaluation']
        fields=np.linalg.norm(a.prediction-b.prediction,axis=0)/np.maximum(np.linalg.norm(b.prediction,axis=0),1e-30)
        columns=np.linalg.norm(lower['matrix']-higher['matrix'],axis=0)/np.maximum(np.linalg.norm(higher['matrix'],axis=0),1e-30)
        low_step,used=self._proposal(lower,config,space,update,carried)
        high_step,_=self._proposal(higher,config,space,update,carried,used=used)
        move,arrays=displacement_comparison(a.curve,space.derivatives@low_step,
            space.derivatives@high_step,update.length_unit_m,linear=True)
        H=update.metric(space,'mass'); eigen,vectors=np.linalg.eigh(H)
        keep=eigen>max(float(np.max(eigen)),0)*1e-10
        inverse=vectors[:,keep]/np.sqrt(eigen[keep])[None,:] if np.any(keep) else vectors[:,:0]
        jp=1e-3*lower['matrix']@inverse; jh=1e-3*higher['matrix']@inverse
        gp=jp.T@a.residual; gh=jh.T@b.residual
        gradient_error=float(np.linalg.norm(gp-gh))
        gradient_limit=1e-3*max(float(np.linalg.norm(jh,2)*np.linalg.norm(b.residual)) if jh.shape[1] else 0.,1e-12)
        row=dict(fields=fields,columns=columns,gradient_error=gradient_error,gradient_limit=gradient_limit,
            stage=lower['stage'].label,M=lower['stage'].update_modes,K=lower['stage'].curve_modes,
            base_sha256=hashlib.sha256(a.curve.coefficients.tobytes()).hexdigest(),
            carried_lambda=carried,
            proposal_comparison=move,used_lambda=used,lower_cutoff=lower['cutoff'],higher_cutoff=higher['cutoff'],
            lower_workspace=lower['workspace'],higher_workspace=higher['workspace'],
            passed=checks.modal_qualification_passed(fields, lower['stage'].discrepancy_tolerances,
                columns, gradient_error, gradient_limit, move['equivalent']))
        arrays.update(lower_J=lower['matrix'],higher_J=higher['matrix'],lower_r=a.residual,higher_r=b.residual,
            base_coefficients=a.curve.coefficients,
            field_denominators=np.linalg.norm(b.prediction,axis=0),
            jacobian_column_denominators=np.maximum(np.linalg.norm(higher['matrix'],axis=0),1e-30),
            field_errors=fields,jacobian_errors=columns,
            metric_H=H,lower_step=low_step,higher_step=high_step,gradient_phys_lower=gp,gradient_phys_higher=gh,
            eigenvalues=eigen,diagnostic_removed_eigenvectors=vectors[:,~keep])
        return row,arrays

    def _check_workspace(self,frame,stage,config,contrast,space,update,ledger,carried):
        identity=(frame['evaluation'].curve.coefficients.tobytes(),frame['cutoff'],stage.update_modes,
                  tuple(id(o) for o in stage.observations),carried)
        if identity in self._workspace_checked: return
        base=self.settings.coefficient_workspace
        high_workspace=768 if base==512 else 1024
        higher=self._frame(frame['evaluation'].curve,stage,config,contrast,space,update,ledger,
            frame['cutoff'],workspace=high_workspace)
        row,arrays=self._compare(frame,higher,config,space,update,carried)
        observe(self,'qualification',kind_detail='workspace',row=row,arrays=arrays,ledger=ledger)
        if not row['passed']:
            if base==768: raise WorkspaceUnresolved('768/1024 workspace field/Jacobian/proposal disagreement')
            highest=self._frame(frame['evaluation'].curve,stage,config,contrast,space,update,ledger,
                frame['cutoff'],workspace=1024)
            final,raw=self._compare(higher,highest,config,space,update,carried)
            observe(self,'qualification',kind_detail='workspace_768_1024',row=final,arrays=raw,ledger=ledger)
            if final['passed']: raise WorkspaceEpochRequired('512/768 failed; restart the matched matrix at workspace 768')
            raise WorkspaceUnresolved('neither declared common workspace comparison qualifies')
        self._workspace_checked.add(identity);self._workspace_first=False

    def qualify_linearization(self,evaluation,stage,config,contrast,space,update,ledger,matrix,gradient,carried):
        cutoff=trace_cutoff(stage.nodes)
        self.actual_cutoff=max(self.actual_cutoff,cutoff)
        current_bytes=evaluation.curve.coefficients.tobytes()
        self._frames={key:value for key,value in self._frames.items() if key[0]==current_bytes}
        lower=dict(stage=stage,evaluation=evaluation,matrix=matrix,gradient=gradient,
                   cutoff=cutoff,workspace=self.settings.coefficient_workspace)
        if self._workspace_first:
            self._check_workspace(lower,stage,config,contrast,space,update,ledger,carried)
        higher=self._frame(evaluation.curve,stage,config,contrast,space,update,ledger,cutoff+32)
        row,arrays=self._compare(lower,higher,config,space,update,carried)
        observe(self,'qualification',kind_detail='base_trace',row=row,arrays=arrays,ledger=ledger)
        if row['passed']: return None
        self._check_workspace(lower,stage,config,contrast,space,update,ledger,carried)
        return self._promotion(evaluation.curve,stage,config,contrast,space,update,ledger,cutoff,row)

    def _promotion(self,curve,stage,config,contrast,space,update,ledger,cutoff,reason):
        choices=[k for k in TRACE_LADDER if cutoff<k<=self.trace_cap]
        if not choices:
            observe(self,'qualification',kind_detail='cap_binding',row=dict(cap=self.trace_cap,
                uncapped_request=next((k for k in TRACE_LADDER if k>cutoff),cutoff+32),
                completed_production=cutoff,reason=reason),arrays={},ledger=ledger)
            raise TraceCapUnresolved('retained base cannot qualify at its hard trace cap')
        next_cutoff=choices[0]
        promoted=self._frame(curve,stage,config,contrast,space,update,ledger,next_cutoff)
        self.actual_cutoff=next_cutoff
        observe(self,'qualification',kind_detail='promotion',row=dict(from_cutoff=cutoff,to_cutoff=next_cutoff,
            trace_cap=self.trace_cap,reason=reason),arrays={},ledger=ledger)
        return promoted

    def respond_resolution_failure(self,base,candidate,stage,config,contrast,space,update,ledger,trial):
        if not self.reject_unresolved_candidates:
            raise NumericalFailure('candidate leaves the frozen numerical-resolution regime')
        cutoff=trace_cutoff(stage.nodes)
        candidate_space=update.prepare(candidate.curve,stage.update_modes,stage.curve_modes)
        failed_frame=self._frame(candidate.curve,stage,config,contrast,candidate_space,update,ledger,cutoff)
        self._check_workspace(failed_frame,stage,config,contrast,candidate_space,update,ledger,trial['damping'])
        if cutoff==self.trace_cap:
            observe(self,'qualification',kind_detail='cap_binding',row=dict(cap=self.trace_cap,
                uncapped_request=next((k for k in TRACE_LADDER if k>cutoff),cutoff+32),
                completed_production=cutoff,reason='candidate field discrepancy'),arrays={},ledger=ledger)
            return False
        return self._promotion(base.curve,stage,config,contrast,space,update,ledger,cutoff,
                               dict(reason='candidate field discrepancy'))

    def qualify_candidate(self,base,candidate,stage,config,contrast,space,update,ledger,trial):
        cutoff=trace_cutoff(stage.nodes)
        higher=self._frame(base.curve,stage,config,contrast,space,update,ledger,cutoff+32)
        bounded,_=self._proposal(higher,config,space,update,trial['damping'],used=trial['damping'])
        fine_step=bounded*.5**trial['backtrack']
        geometry_update=bind_geometry_update(update)
        try:
            finer_curve,finer_geometry=geometry_update(base.curve,fine_step,prepared=space)
            from .continuation.lm_backend import inside_box
            if not inside_box(finer_curve,config.domain_box):
                raise UpdateRefused('outside_domain','higher-cutoff proposal leaves the existing domain')
        except Exception as exc:
            if not isinstance(exc,UpdateRefused): raise
            row=dict(passed=False,reason='witness_geometry_refusal',detail=exc.reason,stage=stage.label)
            observe(self,'qualification',kind_detail='accepted_move',row=row,
                arrays=dict(fine_step=fine_step,base_coefficients=base.curve.coefficients),ledger=ledger)
            if cutoff==self.trace_cap: return False
            return self._promotion(base.curve,stage,config,contrast,space,update,ledger,cutoff,row)
        move,arrays=displacement_comparison(base.curve,candidate.curve.coefficients-base.curve.coefficients,
            finer_curve.coefficients-base.curve.coefficients,update.length_unit_m)
        next_frame=self._frame(base.curve,stage,config,contrast,space,update,ledger,cutoff+64)
        with self.usage('accepted_move_witness'):
            low_candidate=higher['objective'].production(finer_curve,'move_witness')
            high_candidate=next_frame['objective'].production(finer_curve,'move_witness_refinement')
        if low_candidate is None or high_candidate is None:
            raise NumericalFailure('accepted-move witness solve failed')
        check,accurate=resolution_check(higher['evaluation'],low_candidate,next_frame['evaluation'],high_candidate,
            higher['stage'],config)
        row=dict(passed=bool(move['equivalent'] and accurate and check['accepted']),stage=stage.label,
            finite_move=move,witness_acceptance=check,lower_decision='accepted',higher_decision=check['accepted'],
            cutoff=cutoff,trace_cap=self.trace_cap,finer_geometry=finer_geometry)
        arrays.update(base_coefficients=base.curve.coefficients,lower_candidate_coefficients=candidate.curve.coefficients,
            higher_candidate_coefficients=finer_curve.coefficients,higher_step=fine_step,
            higher_prediction=low_candidate.prediction,refined_prediction=high_candidate.prediction)
        observe(self,'qualification',kind_detail='accepted_move',row=row,arrays=arrays,ledger=ledger)
        if row['passed']: return True
        if cutoff==self.trace_cap: return False
        return self._promotion(base.curve,stage,config,contrast,space,update,ledger,cutoff,row)

    def receipt(self):
        value=super().receipt()
        value['independent_accuracy']=dict(trace_cap=self.trace_cap,actual_cutoff=self.actual_cutoff,
            workspace=self.settings.coefficient_workspace,witness_cutoffs='production+32, accepted-move+64',
            cap_semantics='witnesses above cap never supply production moves')
        value['workspace_services']={str(k):v.receipt() for k,v in self._workspace_services.items()}
        value['adaptive_services']=getattr(self,'_adaptive_receipts',[])
        return value
