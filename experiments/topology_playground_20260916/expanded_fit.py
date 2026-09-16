"""Fit additional training frequencies, keeping 1.5 and 2.5 GHz untouched."""
from __future__ import annotations
import argparse
from dataclasses import replace
from pathlib import Path
import time
import traceback
import numpy as np
from .run import p,m,suite,pipeline,SOURCE,write,read
from sdf_inverse import runtime
from sdf_inverse.runtime import inverse_execution


@inverse_execution
def run(args):
    runtime.PROFILES['fast']=replace(runtime.PROFILES['fast'],analytic_constraint_policy='true')
    output=args.output;output.mkdir(parents=True,exist_ok=False)
    config=read(args.source/'config.json')
    state=p.driver.deserialize_state(read(args.source/'retained_state.json'))
    _,observed,evaluation,scene,spec=suite.load_scene(SOURCE,config['scene'])
    control=p.benchmark.controller_config(spec,'H');solve=p.driver.baseline.iteration01_solve_config()
    state,optimizer,capacity=suite.capacity_start(state,control,solve)
    optimizer=replace(optimizer,max_iterations=args.iterations)
    frequencies=np.array(args.frequencies)*1e9
    if any(np.isclose(f,list(p.EVALUATION),atol=1.,rtol=0).any() for f in frequencies):
        raise ValueError('1.5 and 2.5 GHz are reserved for evaluation')
    ledger=m.Ledger(cap=args.cap+100,seconds=args.seconds)
    record=dict(scene=config['scene'],source=str(args.source),frequencies_hz=frequencies,
                status='IN_PROGRESS',runtime=runtime.runtime_metadata(),iterations=args.iterations)
    write(output/'config.json',record);started=time.monotonic()
    try:
        with ledger.instrument():
            oracle={n:suite.screen.oracle(scene,frequencies,n,solve,ledger) for n in (256,512)}
            discrepancy=p.relative(oracle[256],oracle[512])
            write(output/'oracle.json',dict(frequencies_hz=frequencies,discrepancy=discrepancy,
                observed_real=oracle[512].real,observed_imag=oracle[512].imag))
            if max(discrepancy)>1e-5:raise m.NumericalFailure('extra-frequency oracle fails refinement')
            data=p.ComplexScatteredData(p.driver.baseline._problem(frequencies),oracle[512],np.ones(len(frequencies))/len(frequencies))
            ledger.begin_stage(1,args.cap)
            final,terminal=m.fit_stage(state,data,tuple(args.nodes),solve,optimizer,
                control.minimum_component_radius_m,ledger,output/'fit')
            record.update(status=terminal['stage_outcome'],terminal=terminal)
            if terminal['stage_outcome'] in ('NORMAL_OPTIMIZER_RETURN','STAGE_QUOTA_REACHED'):
                record['score']=pipeline.base.score_endpoint(final,scene,spec,observed,evaluation,
                    solve,ledger,output/'endpoint.json')
        write(output/'retained_state.json',p.driver.serialize_state(final))
    except Exception as exc:
        record.update(status='STOPPED',error=repr(exc),traceback=traceback.format_exc())
    record.update(seconds=time.monotonic()-started,work=ledger.snapshot())
    write(output/'result.json',record)
    print({k:record.get(k) for k in ('status','seconds','score','error')},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frequencies',type=float,nargs='+',default=[.5,.75,1,1.25,1.75,2.])
    parser.add_argument('--nodes',type=int,nargs=2,default=[256,512])
    parser.add_argument('--iterations',type=int,default=60)
    parser.add_argument('--cap',type=int,default=16000)
    parser.add_argument('--seconds',type=float,default=1800)
    run(parser.parse_args())
