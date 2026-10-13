"""MA-007 immutable data-space recording, with serialization outside compute.

The observer receives solver/optimizer evidence and cannot return an acceptance
decision. A single writer serializes immutable copies. Waiting for that writer
at completed numerical batches is pure I/O and suspends only the current ledger.
Transient LU handles of the latest four curves permit refusal trace capture;
additional reciprocal batches are performed and charged offline after the fit.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
from threading import RLock, current_thread, main_thread
from time import perf_counter

import numpy as np
from scipy.linalg import lu_solve
from bem_inverse.io import write
from .ma007 import Chunks


def key(coefficients):
    return hashlib.sha256(np.ascontiguousarray(coefficients).tobytes()).hexdigest()


def trace_tails(values, cutoff):
    modes=np.arange(-cutoff,cutoff+1)
    width=len(modes)
    tails=[]
    for block in range(2):
        x=values[block*width:(block+1)*width]
        tails.append(np.stack([np.sum(np.abs(x[mask])**2,axis=0) for mask in
            (np.ones(width,bool),(abs(modes)>cutoff-32),
             (abs(modes)>cutoff-64)&(abs(modes)<=cutoff-32))]))
    return np.stack(tails)


class Recorder:
    def __init__(self, folder, epoch):
        self.folder=folder
        self.chunks=Chunks(folder/'chunks')
        self.epoch=epoch
        self.lock=RLock()
        self.writer=ThreadPoolExecutor(max_workers=1,thread_name_prefix='MA007-serialization')
        self.futures=[]
        self.events=[]
        self.context={}
        self.handles=OrderedDict()
        self.refusal_handles={}
        self.pinned_curve=None
        self.ledger_io_wait_seconds=0.
        self.capture_seconds=0.
        self.io_wait_seconds=0.
        self.offline_reciprocal_seconds=0.
        self.offline_reciprocal_units=0

    def queue(self, kind, arrays, metadata):
        arrays={name:np.array(value,copy=True) for name,value in arrays.items()}
        with self.lock:
            index=len(self.events)
            row=dict(index=index,kind=kind,**metadata)
            self.events.append(row)
            if arrays:
                future=self.writer.submit(self.chunks.save,f'event_{index:06d}',arrays,
                    dict(epoch=self.epoch,**row))
                self.futures.append((index,future))
            return index

    def flush(self, ledger=None):
        started=perf_counter()
        with self.lock:
            pending,self.futures=self.futures,[]
        for index,future in pending:
            receipt=future.result()
            self.events[index]['artifact']=receipt['path']
        elapsed=perf_counter()-started
        self.io_wait_seconds+=elapsed
        if ledger is not None:
            ledger.started+=elapsed
            self.ledger_io_wait_seconds+=elapsed

    def __call__(self, kind, record):
        started=perf_counter()
        if kind=='objective_setup':
            self.flush(record['ledger'])
            stage=record['stage']
            self.context=dict(stage=stage.label,M=stage.update_modes,K=stage.curve_modes,
                weights=list(stage.weights),frequencies_hz=[o.frequency_hz for o in stage.observations],
                config=asdict(record['config']))
        elif kind=='field':
            state=record['state']; observation=record['observation']
            identity=dict(state_sha256=key(state.coefficients),K_u=state.cutoff,B_work=record['workspace'],
                frequency_hz=observation.frequency_hz,wavenumber=state.wavenumber,
                trace_order='Dirichlet, flux; modes -Ku..Ku; 24 source columns',
                tail_axes='unknown block, total/last32/preceding32, source',
                channels='paired diagonal R@X_s; strength in B_s only',
                calculation_role=record.get('calculation_role','production'),
                actual_K=len(state.coefficients)//2,
                system_residual=record['system_residual'],operator_status='regenerable',**self.context)
            self.queue(kind,dict(coefficients=state.coefficients,prediction=record['prediction'],
                observed=observation.scattered,residual=record['prediction']-observation.scattered,
                source_trace_tail_energies=trace_tails(state.traces,state.cutoff)),identity)
            with self.lock:
                curve_key=identity['state_sha256']
                if curve_key not in self.handles:
                    self.handles[curve_key]={}
                self.handles.move_to_end(curve_key)
                self.handles[curve_key][(state.wavenumber,state.cutoff)]=(state,identity,observation,
                    record.get('execution'),record.get('contrast'))
                while len(self.handles)>4:
                    drop=next(k for k in self.handles if k!=self.pinned_curve)
                    self.handles.pop(drop)
        elif kind=='reciprocal':
            state=record['state']
            self.queue(kind,dict(J_complex=record['J'],
                reciprocal_trace_tail_energies=trace_tails(record['X_r'],state.cutoff)),
                dict(state_sha256=key(state.coefficients),K_u=state.cutoff,wavenumber=state.wavenumber,
                    coordinate_order='package grouped constant, cos1..M, sin1..M',**self.context))
        elif kind=='objective':
            self.flush(record['ledger'])
            evaluation=record['evaluation']; stage=record['stage']
            self.queue(kind,dict(coefficients=evaluation.curve.coefficients,prediction=evaluation.prediction,
                observed=record['observed'],assembled_residual=evaluation.residual,
                weights=np.asarray(stage.weights)),dict(state_sha256=key(evaluation.curve.coefficients),
                stage=stage.label,loss=evaluation.loss,residual_order='frequency-fast C-order real rows then imaginary',
                floor=record['config'].residual_floor,work=record['ledger'].snapshot()))
        elif kind=='linearization':
            self.flush(record['ledger'])
            evaluation=record['evaluation']
            self.pinned_curve=key(evaluation.curve.coefficients)
            self.queue(kind,dict(J_normalized=record['J'],gradient=record['gradient'],
                assembled_residual=evaluation.residual),dict(state_sha256=key(evaluation.curve.coefficients),
                    stage=record['stage'].label,M=record['stage'].update_modes,K=record['stage'].curve_modes,
                    work=record['ledger'].snapshot()))
        elif kind=='proposal':
            self.flush(record['ledger'])
            self.queue(kind,{n:record[n] for n in ('J','gradient','normal','metric','raw_proposed','bounded_proposed')},
                dict(state_sha256=key(record['evaluation'].curve.coefficients),stage=record['stage'].label,
                    damping=record['damping'],controller_floor=record['controller_floor'],
                    work=record['ledger'].snapshot(),config=asdict(record['config'])))
        elif kind=='geometry_trial':
            arrays=dict(base_coefficients=record['base'].coefficients,step_m=record['step'])
            if record['candidate'] is not None:
                arrays['candidate_coefficients']=record['candidate'].coefficients
            self.queue(kind,arrays,dict(base_sha256=key(record['base'].coefficients),
                candidate_sha256=None if record['candidate'] is None else key(record['candidate'].coefficients),
                trial=dict(record['trial']),certificates=record.get('certificates',[]),
                traceback=record.get('traceback'),
                work=record['ledger'].snapshot()))
        elif kind=='resolution_refusal':
            self.queue(kind,{},dict(stage=record['stage'].label,check=record['check'],
                states={role:key(record[role].curve.coefficients) for role in
                    ('base','candidate','refined_base','refined_candidate') if record[role] is not None},
                work=record['ledger'].snapshot()))
            with self.lock:
                for role in ('base','candidate','refined_base','refined_candidate'):
                    evaluation=record[role]
                    if evaluation is None:
                        continue
                    identity=key(evaluation.curve.coefficients)
                    states=self.handles.get(identity)
                    if states is None:
                        raise ValueError('Refusal trace handle lost before retention: '+role)
                    for (wave,cutoff),value in states.items():
                        if (identity,wave,cutoff) not in self.refusal_handles:
                            state,metadata,observation,execution,contrast=value
                            event=self.queue('refusal_forward_capture',dict(coefficients=state.coefficients,
                                X_s=state.traces),dict(metadata,timing_class='original forward traces'))
                            self.refusal_handles[(identity,wave,cutoff)]=(event,metadata,observation,execution,contrast)
        elif kind=='qualification':
            arrays=dict(record['arrays'])
            def metadata(value,prefix='row'):
                if isinstance(value,np.ndarray):
                    name='qualification_'+prefix
                    arrays[name]=value
                    return dict(array_in_chunk=name)
                if isinstance(value,dict): return {k:metadata(v,prefix+'_'+k) for k,v in value.items()}
                if isinstance(value,(tuple,list)): return [metadata(v,prefix+'_'+str(i)) for i,v in enumerate(value)]
                return value
            self.queue(kind,arrays,dict(kind_detail=record['kind_detail'],row=metadata(record['row']),
                work=record['ledger'].snapshot()))
        elif kind=='accepted_history':
            self.queue(kind,{},dict(row=dict(record['row'])))
        elif kind=='physics_failure':
            self.queue(kind,{},dict(failure=record['failure'],work=record['ledger'].snapshot()))
        else:
            raise ValueError('Unrecognized MA-007 numerical record: '+kind)
        self.capture_seconds+=perf_counter()-started

    def finish(self):
        # These extra reciprocal traces are post-return diagnostic work. They
        # cannot change the original fit or its fitting budget/accepted decisions.
        self.flush()
        from bem_inverse.modal_muller import ModalMuller,ModalSettings,token
        from bem_inverse.physics import Execution
        from bem_inverse.continuation.geometry import FourierCurve
        services={}; offline_forward_units=0
        for (identity,wave,cutoff),(event,metadata,observation,execution,contrast) in self.refusal_handles.items():
            artifact=self.events[event]['artifact']
            from . import campaign as c
            with np.load(c.ROOT/artifact,allow_pickle=False) as original:
                coefficients=original['coefficients']; traces=original['X_s']
            workspace=metadata['B_work']
            if workspace not in services:
                services[workspace]=ModalMuller(Execution(**execution),ModalSettings(
                    coefficient_workspace=workspace,cached_geometries=1))
            started=perf_counter()
            service=services[workspace]
            offline_forward_units+=1
            prediction=service.evaluate(FourierCurve(coefficients),observation,contrast,token(cutoff))
            state=prediction._handle
            regenerated_error=float(np.linalg.norm(traces-state.traces)/max(np.linalg.norm(traces),1e-14))
            reciprocal=lu_solve(state.factors,state.reciprocal_rhs)
            self.offline_reciprocal_seconds+=perf_counter()-started
            self.offline_reciprocal_units+=1
            self.queue('refusal_complete_traces',dict(X_s=traces,X_s_regenerated=state.traces,X_r=reciprocal),
                dict(metadata,state_sha256=identity,K_u=cutoff,wavenumber=wave,
                     regeneration_relative=regenerated_error,regeneration_passed=regenerated_error<=1e-10,
                     timing_class='offline post-return regeneration and reciprocity work',work_units=2))
        self.flush()
        self.writer.shutdown(wait=True)
        value=dict(schema='MA007-work-1',events=self.events,events_count=len(self.events),
            raw_array_bytes=sum(x['bytes'] for x in self.chunks.rows),
            serialization_seconds=self.chunks.seconds,capture_inclusive_seconds=self.capture_seconds,
            pure_io_wait_seconds=self.io_wait_seconds,
            ledger_io_wait_seconds=self.ledger_io_wait_seconds,
            offline_refusal_forward_units=offline_forward_units,
            offline_refusal_reciprocal_seconds=self.offline_reciprocal_seconds,
            offline_refusal_reciprocal_units=self.offline_reciprocal_units,
            raw_retention='local machine only; committed hash manifests',
            operator_retention='regenerable; snapshots are separate offline atlas artifacts')
        write(self.folder/'index.json',value)
        self.handles.clear(); self.refusal_handles.clear()
        return value
