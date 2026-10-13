"""Independent four-control continuation schedules (experimental, opt-in).

Only numerical controls live here. Campaign IDs, scene selection, scoring and
cap-extension/winner decisions belong to the experiment driver.
"""
from dataclasses import dataclass, replace
import math
from .policy import CumulativePolicy, Operation
from .modal_muller import token

LEVELS=((.5,.75,1.,1.25,1.5,1.75,2.,2.25,2.5),
        (3,5,7,9,11,15,19,25,31,37,49,61,79,95,127),
        (8,12,16,20,24,32,40,52,64,96,128,192,256,384),
        (64,96,128,160,192,256,320))
NOMINAL=((.5,3,8,64),(.75,5,12,64),(1.,7,16,64),(1.25,9,20,64),
         (1.5,11,24,64),(1.75,19,40,64),(2.,37,96,64),(2.5,95,192,64))
FIRST_PAIRS={'O1':(0,3),'O2':(1,2),'O3':(0,1),'O4':(2,3),'O5':(0,2),'O6':(1,3)}


def truncated_levels(axis,cap):
    values=[x for x in LEVELS[axis] if x<=cap]
    if not values or values[-1]!=cap:
        values.append(cap)
    return tuple(values)


def ordered_vector(order,slot,target):
    if order not in (*FIRST_PAIRS,'O7'):
        raise ValueError('A fixed ordering is O1 through O7.')
    first=FIRST_PAIRS.get(order)
    out=[]
    for axis,cap in enumerate(target):
        q=slot/8 if order=='O7' else min(slot/4,1) if axis in first else max((slot-4)/4,0)
        levels=truncated_levels(axis,cap)
        out.append(levels[math.floor(q*(len(levels)-1))])
    return tuple(out)


@dataclass(frozen=True)
class FourControlPolicy(CumulativePolicy):
    name: str='independent_four_control_research'
    version: str='0.1.0'
    caps: tuple=(2.5,95,192,192)
    generous_target: tuple=(2.5,95,192,192)
    order: str='S0'
    historical_exit: bool=False
    required_accuracy: object=.003
    damping_rule: str='agreement'
    avoid_terminal_linearization: bool=True
    log_model: bool=True
    fit_seconds: float=120.
    audit_seconds: float=30.
    audit_aggregate_seconds: object=30.

    def __post_init__(self):
        super().__post_init__()
        if self.order not in ('S0',*FIRST_PAIRS,'O7','O8'):
            raise ValueError('Schedule must be S0 or O1 through O8.')
        if len(self.caps)!=4 or len(self.generous_target)!=4:
            raise ValueError('Four independent controls are required.')
        for axis,(value,maximum) in enumerate(zip(self.caps,(2.5,127,384,320))):
            if value<LEVELS[axis][0] or value>maximum:
                raise ValueError('Cap outside the declared four-control range.')

    def _config(self,problem,observations):
        config,weights,expected=super()._config(problem,observations)
        return replace(config,plain_progress_exit=not self.historical_exit),weights,expected

    def operations(self,problem,physics):
        if physics.name!='modal_muller':
            raise ValueError('Independent four-control research requires modal Müller.')
        operations=[Operation('audit','initial_audit','Qualify prescribed original start',
            'before initialization','failure returns original start',details=dict(seconds=self.audit_seconds)),
            Operation('localize','keep_start','Retain the prescribed centered start',
                'initial audit passed','no data-based localization')]
        target=tuple(min(a,b) for a,b in zip(self.caps,self.generous_target))
        if self.order=='O8':
            operations.append(self.control_operation(problem,physics,'warmup',(.25,1,4,64),'damped',44,600))
            for slot in range(1,9):
                operations.append(Operation('adaptive',f'slot_{slot}','Complete charged branch contest',
                    'same saved base and default lambda','saved branch endpoint or unchanged base',
                    details=dict(slot=slot,catalog='damped' if slot<=4 else 'real',caps=self.caps,
                        candidates=['HOLD','next F','next M','next K'],branch_iterations=2,
                        branch_work_units=200,slot_work_units=3000,monitor_cutoffs=[320,352],
                        reservation='n*(200+38)+38 before any candidate',lambda_rule='reset each decision slot',
                        selection='both monitor scores agree; useful >=1% and >=1e-8; gain/work; within1% tie raw work then HOLD,F,M,K')))
                if slot==4:
                    operations.append(Operation('adaptive_bridge','bridge','Real bridge at current controls',
                        'after slot 4','common rung exit',details=dict(catalog='real')))
            operations.append(self.control_operation(problem,physics,'terminal',target,'real',self.fit_units,None))
            operations.append(Operation('audit','final_audit','Independent full-real-catalog endpoint audit',
                'fit returned','score only returned endpoint',details=dict(seconds=self.audit_seconds)))
            return operations
        stages=[('warmup',(.25,1,4,64),(.25,1,4,64),'damped',44,600)]
        for slot in range(1,9):
            requested=NOMINAL[slot-1] if self.order=='S0' else ordered_vector(self.order,slot,target)
            uncapped=requested
            requested=tuple(min(a,b) for a,b in zip(uncapped,self.caps))
            stages.append((f'slot_{slot}',requested,uncapped,'damped' if slot<=4 else 'real',
                           22 if self.historical_exit else 60,1200 if self.historical_exit else 3000))
            if slot==4:
                stages.append(('bridge',requested,uncapped,'real',22 if self.historical_exit else 60,
                               1200 if self.historical_exit else 3000))
        stages.append(('terminal',target,self.generous_target,'real',44 if self.historical_exit else self.fit_units,None))
        previous=None
        for label,vector,uncapped,kind,iterations,quota in stages:
            frequency,band,storage,cutoff=vector
            observations=tuple(o for o in getattr(problem,kind) if o.frequency_hz<=frequency*1e9)
            identity=(tuple(o.frequency_hz for o in observations),kind,band,storage,cutoff)
            if identity==previous and not self.historical_exit:
                operations.append(Operation('skip',label,'Skip identical resolved rung',
                    'identical previous frequency/catalog/M/K/Ku floor','SKIPPED_IDENTICAL',
                    details=dict(requested_controls=vector,uncapped_controls=uncapped,catalog=kind)))
                continue
            op=self._fit(problem,physics,label,observations,band,storage,quota,iterations,
                purpose='Independent four-control research rung')
            profile=dict(production=token(cutoff),refined=token(cutoff+32),kind='modal_muller',
                K_trace=cutoff,K_trace_refined=cutoff+32,token='8*K_trace',
                coefficient_workspace=dict(production=physics.settings.coefficient_workspace,
                                           refined=physics.settings.coefficient_workspace),
                refinement='fixed coefficient workspace; monotone trace qualification within cap')
            op=replace(op,stage=replace(op.stage,nodes=token(cutoff),refined_nodes=token(cutoff+32),
                                      resolution_kind='modal'),
                details=dict(op.details,accuracy_profile=profile,requested_controls=vector,uncapped_controls=uncapped,
                    catalog=kind,trace_cap=self.caps[3],rung_exit='historical' if self.historical_exit else 'progress'))
            operations.append(op);previous=identity
        operations.append(Operation('audit','final_audit','Independent full-real-catalog endpoint audit',
            'fit returned','score only returned endpoint',details=dict(seconds=self.audit_seconds)))
        return operations

    def control_operation(self,problem,physics,label,vector,kind,iterations=60,quota=3000):
        frequency,band,storage,cutoff=vector
        observations=tuple(o for o in getattr(problem,kind) if o.frequency_hz<=frequency*1e9)
        op=self._fit(problem,physics,label,observations,band,storage,quota,iterations,
            purpose='Independent four-control research rung')
        profile=dict(production=token(cutoff),refined=token(cutoff+32),kind='modal_muller',
            K_trace=cutoff,K_trace_refined=cutoff+32,token='8*K_trace',
            coefficient_workspace=dict(production=physics.settings.coefficient_workspace,
                refined=physics.settings.coefficient_workspace),refinement='fixed common workspace')
        return replace(op,stage=replace(op.stage,nodes=token(cutoff),refined_nodes=token(cutoff+32),
            resolution_kind='modal'),details=dict(op.details,accuracy_profile=profile,
                requested_controls=vector,uncapped_controls=vector,catalog=kind,trace_cap=self.caps[3]))

    def resolve_adaptive(self,operation,problem,physics,state):
        if state is None:
            state=dict(controls=tuple(truncated_levels(axis,cap)[0] for axis,cap in enumerate(self.caps)))
        resolved=self.control_operation(problem,physics,operation.label,state['controls'],
            operation.details['catalog'])
        return replace(resolved,details=dict(resolved.details,**operation.details,
            adaptive_decision=operation.kind=='adaptive')),state
