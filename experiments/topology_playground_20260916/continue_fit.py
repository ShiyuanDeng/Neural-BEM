"""Continue a saved experimental topology endpoint with the existing four stages."""
from __future__ import annotations
import argparse
from dataclasses import asdict,replace
from pathlib import Path
import time
import traceback
from .run import p,m,suite,pipeline,SOURCE,write,read
from sdf_inverse import runtime
from sdf_inverse.runtime import inverse_execution


@inverse_execution
def run(args):
    if args.true_jacobian:
        runtime.PROFILES['fast']=replace(runtime.PROFILES['fast'],analytic_constraint_policy='true')
    config=read(args.source/'config.json')
    result=read(args.source/'result.json')
    state=p.driver.deserialize_state(read(args.source/'retained_state.json'))
    _,observed,evaluation,scene,spec=suite.load_scene(SOURCE,config['scene'])
    control=p.benchmark.controller_config(spec,'H')
    solve=p.driver.baseline.iteration01_solve_config()
    state,optimizer,capacity=suite.capacity_start(state,control,solve)
    output=args.output;output.mkdir(parents=True,exist_ok=False)
    write(output/'input.json',dict(source=str(args.source),source_status=result['status'],
        scene=config['scene'],state=p.driver.serialize_state(state),capacity=capacity,
        runtime=runtime.runtime_metadata(),quotas=args.quotas,nodes=args.nodes,
        stage_numbers=args.stages,
        optimizer=asdict(optimizer),no_truth_supplied_to_optimizer=True))
    ledger=m.Ledger(cap=sum(args.quotas)+100,seconds=args.seconds)
    record=dict(status='IN_PROGRESS');started=time.monotonic()
    try:
        def scorer(current):
            destination=output/'initial_predictions.json' if ledger.stage is None else output/f'stage_{ledger.stage}'/'endpoint_predictions.json'
            return pipeline.base.score_endpoint(current,scene,spec,observed,evaluation,solve,ledger,destination)
        with ledger.instrument():
            initial_score=scorer(state)
            if not initial_score['numerically_qualified']:raise m.NumericalFailure('initial endpoint unqualified')
            schedule=m.run_schedule(state,'F',observed,tuple(args.nodes),solve,optimizer,
                control.minimum_component_radius_m,ledger,output,initial_score,scorer,
                stage_plan=tuple(zip(args.stages,args.quotas)))
        record.update(status=schedule['status'],schedule=schedule,
            recovered=bool(schedule['schedule_complete'] and schedule['numerically_qualified']
                           and schedule['reconstruction_gates_pass']))
    except Exception as exc:
        record.update(status='STOPPED',error=repr(exc),traceback=traceback.format_exc())
    record.update(work=ledger.snapshot(),seconds=time.monotonic()-started)
    write(output/'result.json',record)
    print({k:record.get(k) for k in ('status','recovered','seconds')},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--quotas',type=int,nargs='+',default=[1000,1250,1750,4000])
    parser.add_argument('--stages',type=int,nargs='+',default=[1,2,3,4])
    parser.add_argument('--nodes',type=int,nargs=2,default=[256,512])
    parser.add_argument('--seconds',type=float,default=1800)
    parser.add_argument('--true-jacobian',action='store_true')
    args=parser.parse_args()
    if len(args.stages)!=len(args.quotas):parser.error('one quota per stage required')
    run(args)
