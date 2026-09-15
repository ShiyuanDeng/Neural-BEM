"""TOP-025: fresh, single-policy twelve-scene evaluation requested by the user."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top021 import run as suite

m, p, base, follow = suite.m, suite.p, suite.base, suite.follow
read, write, require = suite.read, suite.write, suite.require
NODES, STAGE_PLAN = suite.NODES, suite.STAGE_PLAN
PLAN = ROOT/'docs/iterations/topology/iteration_17/03_plan.md'
TOTAL_CAP, WALL_SECONDS = 72+12*(4000+8012), 7*3600
WORKERS, SCENE_TIMEOUT = 4, 7900


def source_hashes():
    return {**suite.source_hashes(), **{str(path.relative_to(ROOT)):p.digest(path)
        for path in sorted(Path(__file__).parent.glob('*.py'))}}


def prepare(bundle, validation):
    require(not bundle.exists(), 'output must be fresh')
    tests = read(validation)
    require(tests['status']=='PASS' and tests['source_sha256']==source_hashes(), 'tests do not qualify current source')
    base.verified_hashes(ROOT, tests['test_sha256'])
    require(p.digest(validation.parent/tests['log'])==tests['log_sha256'], 'test log changed')
    spec = read(p.DATA/'scene_spec.json')
    require(spec==read(ROOT/'config/topology_scenes_v1.json') and len(spec['scenes'])==12, 'scene matrix changed')
    bundle.mkdir(parents=True)
    shutil.copyfile(p.DATA/'scene_spec.json',bundle/'scene_spec.json')
    for source,name in [(PLAN,'approved_plan.md'),(validation,'pre_dispatch_validation.json'),
            (validation.parent/tests['log'],'pre_dispatch_tests.log'),
            (Path(__file__).parent/'implementation_review.md','implementation_review.md')]:
        shutil.copyfile(source,bundle/name)
    # Archive every measured file: the live checkout need not remain at this git HEAD.
    for name in {*source_hashes(),*tests['test_sha256']}:
        target=bundle/'measured_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    historical={str((p.DATA/'scene_spec.json').relative_to(ROOT)):p.digest(p.DATA/'scene_spec.json')}
    audit_path=m.SOURCE/'phase1/sensitivity.json'; reused_audit=read(audit_path)
    historical[str(audit_path.relative_to(ROOT))]=p.digest(audit_path)
    for scene in spec['scenes']:
        folder=bundle/'inputs'/scene['id'];folder.mkdir(parents=True)
        for name in ('initial_state.json','observations.json','oracle_check.json'):
            source=p.DATA/'scenes'/scene['id']/name
            shutil.copyfile(source,folder/name);historical[str(source.relative_to(ROOT))]=p.digest(source)
        require(read(folder/'oracle_check.json')['passed'], 'original oracle unqualified')
        if scene['id'] in suite.REUSED:
            source=follow.HISTORY/'inputs'/scene['id']/'training_observations.json'
            shutil.copyfile(source,folder/'training_observations.json')
            historical[str(source.relative_to(ROOT))]=p.digest(source)
    solve=p.driver.baseline.iteration01_solve_config()
    write(bundle/'contract.json',dict(experiment='TOP-025', approval='user requested latest-code all-case evaluation and videos',
        scenes=[s['id'] for s in spec['scenes']],arms=['F'],evaluation_only=True,top021_release_claim=False,
        topology_controller=asdict(p.benchmark.controller_config(spec,'H')),topology_nodes=[64,128],
        topology_solve_cap=4000,topology_seconds=600,continuation_nodes=NODES,stage_plan=STAGE_PLAN,
        continuation_solve_cap=8012,continuation_seconds=7200,oracle_solve_cap=72,oracle_seconds=300,
        campaign_solve_cap=TOTAL_CAP,campaign_seconds=WALL_SECONDS,maximum_workers=WORKERS,
        scene_outer_seconds=SCENE_TIMEOUT,termination_grace_seconds=10,blas_threads=1,
        capacity_rule='K17 for one returned component; K9 per component otherwise',
        damping_reset=False,training_frequencies_hz=p.TRAIN,evaluation_frequencies_hz=p.EVALUATION,
        prediction_tolerances=follow.TOLERANCES,solve_config=asdict(solve),normalization=m.NORMALIZATION,
        supplied_target_count=False,archived_optimized_state_used=False,independent_review=False))
    manifest=dict(git_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256=source_hashes(),historical_input_sha256=historical,command=sys.argv,
        prepared_utc=datetime.now(timezone.utc).isoformat())
    write(bundle/'manifest.json',manifest)
    ledger=m.Ledger(cap=72,seconds=300);audit=dict(status='IN_PROGRESS',scenes={})
    try:
        with ledger.instrument():
            for scene in spec['scenes']:
                name=scene['id'];folder=bundle/'inputs'/name
                if name in suite.REUSED:
                    qualification=reused_audit['oracle_checks'][name]
                    require(qualification['passed'],'reused oracle unqualified')
                    audit['scenes'][name]=dict(reused=True,qualified=True,new_oracle_solves=0,original_qualification=qualification)
                    continue
                ledger.reserve(6)
                values={n:suite.screen.oracle(scene,p.TRAIN[1:],n,solve,ledger) for n in NODES}
                discrepancy=p.relative(values[256],values[512])
                qualified=bool(np.all(np.isfinite(discrepancy)) and np.max(discrepancy)<=spec['oracle_relative_tolerance'])
                audit['scenes'][name]=dict(reused=False,qualified=qualified,relative_discrepancy=discrepancy,
                    predictions={str(n):follow.complex_record(v) for n,v in values.items()},new_oracle_solves=6)
                write(bundle/'oracle_audit.json',{**audit,'work':ledger.snapshot()})
                if not qualified: raise m.NumericalFailure('added oracle unqualified: '+name)
                write(folder/'training_observations.json',suite.training_record(read(folder/'observations.json'),values[256],folder/'observations.json'))
        audit['status']='PASS'
    except Exception as exc:
        audit.update(status='HARD_STOP',reason=getattr(exc,'code',type(exc).__name__),detail=str(exc),traceback=traceback.format_exc())
    audit['work']=ledger.snapshot();write(bundle/'oracle_audit.json',audit)
    if audit['status']=='PASS':
        for scene in spec['scenes']: suite.load_scene(bundle,scene['id'])
    frozen=[bundle/'scene_spec.json',bundle/'contract.json',bundle/'approved_plan.md',bundle/'oracle_audit.json',
            *[path for path in (bundle/'inputs').rglob('*') if path.is_file()]]
    manifest['input_sha256']={str(path.relative_to(bundle)):p.digest(path) for path in frozen}
    write(bundle/'manifest.json',manifest)
    return audit


def verify(bundle):
    manifest=read(bundle/'manifest.json')
    require(source_hashes()==manifest['source_sha256'],'measured source changed')
    base.verified_hashes(ROOT,manifest['historical_input_sha256'])
    base.verified_hashes(bundle,manifest['input_sha256'])


def run_continuation(folder,state,optimizer,observed,evaluation,scene,spec,control,solve):
    ledger=m.Ledger(cap=8012,seconds=7200)
    result=dict(status='IN_PROGRESS',fresh_recovery_pass=False)
    folder.mkdir(parents=True,exist_ok=False)
    try:
        def scorer(current):
            destination=folder/'initial_endpoint_predictions.json' if ledger.stage is None else folder/f'stage_{ledger.stage}'/'endpoint_predictions.json'
            return base.score_endpoint(current,scene,spec,observed,evaluation,solve,ledger,destination)
        with ledger.instrument():
            initial_score=scorer(state)
            if not initial_score['numerically_qualified']: raise m.NumericalFailure('handoff predictions unqualified')
            # Fit interface receives training only. Evaluation stays in the scorer.
            schedule=m.run_schedule(state,'F',observed,NODES,solve,optimizer,control.minimum_component_radius_m,
                ledger,folder,{k:initial_score[k] for k in ('training_errors','numerically_qualified')},scorer,stage_plan=STAGE_PLAN)
        result.update(status=schedule['status'],schedule=schedule,fresh_recovery_pass=bool(schedule['schedule_complete']
            and schedule['complete_effective_exposure'] and schedule['numerically_qualified'] and schedule['reconstruction_gates_pass']))
    except Exception as exc:
        result.update(status='HARD_STOP',reason=getattr(exc,'code',type(exc).__name__),detail=str(exc),traceback=traceback.format_exc())
    result['work']=ledger.snapshot();write(folder/'result.json',result)
    return result


def run_scene(bundle,scene_id):
    verify(bundle)
    require(read(bundle/'oracle_audit.json')['status']=='PASS','oracle gate failed')
    initial,observed,evaluation,scene,spec=suite.load_scene(bundle,scene_id)
    folder=bundle/'runs'/scene_id;folder.mkdir(parents=True,exist_ok=False)
    control=p.benchmark.controller_config(spec,'H');solve=p.driver.baseline.iteration01_solve_config()
    ledger=follow.TopologyLedger(cap=4000,seconds=600);prefix_work=None
    result=dict(scene=scene_id,status='IN_PROGRESS',original_start_sha256=m.state_hash(initial),
        archived_optimized_state_used=False,supplied_target_count=False,fresh_recovery_pass=False)
    try:
        with ledger.instrument():
            state=follow.topology_prefix(initial,p.training_data(p.TRAIN[:1],observed[:,:1]),control,solve,ledger,folder/'topology')
        prefix_work=ledger.snapshot();terminal=read(folder/'topology/terminal.json')
        require(sum(prefix_work['completed'].values())==terminal['controller_work']['totals']['bie_frequency_solve_count'],'prefix work mismatch')
        result['topology_checks']=base.topology_checks(folder/'topology',control)
        state,optimizer,capacity=suite.capacity_start(state,control,solve)
        write(folder/'handoff.json',dict(state=p.driver.serialize_state(state),state_sha256=m.state_hash(state),
            source_state_sha256=m.state_hash(terminal['final_state']),capacity=capacity,optimizer=asdict(optimizer)))
        result.update(capacity=capacity,topology_work=prefix_work)
        write(folder/'result.json',result)
        verify(bundle)
        continuation=run_continuation(folder/'F',state,optimizer,observed,evaluation,scene,spec,control,solve)
        result.update(status=continuation['status'],continuation=continuation,
            fresh_recovery_pass=continuation['fresh_recovery_pass'] and all(result['topology_checks'].values()))
    except Exception as exc:
        result.update(status='HARD_STOP',reason=getattr(exc,'code',type(exc).__name__),detail=str(exc),traceback=traceback.format_exc())
    result['topology_work']=ledger.snapshot() if prefix_work is None else prefix_work
    works=[result['topology_work']]+([result['continuation']['work']] if 'continuation' in result else [])
    result['actual_attempted_calls']=sum(work['total_attempted'] for work in works)
    result['actual_completed_solves']=sum(sum(work['completed'].values()) for work in works)
    result['actual_failed_or_refused_calls']=sum(sum(work['failed'].values()) for work in works)
    result['geometry_refused_calls']=sum(work['calls'].get('preserved_candidate_refusals',0) for work in works)
    try:
        verify(bundle);result['sources_and_inputs_unchanged']=True
    except Exception as exc:
        result.update(status='IMPLEMENTATION_ERROR',fresh_recovery_pass=False,sources_and_inputs_unchanged=False,integrity_error=str(exc))
    if 'continuation' in result:
        result['continuation']['sources_and_inputs_unchanged']=result['sources_and_inputs_unchanged']
        write(folder/'F/result.json',result['continuation'])
    write(folder/'result.json',result)
    print(json.dumps(dict(scene=scene_id,status=result['status'],recovered=result['fresh_recovery_pass'],calls=result['actual_attempted_calls'])),flush=True)
    return result


def run_job(bundle,scene_id,deadline):
    remaining=min(SCENE_TIMEOUT,deadline-time.monotonic())
    if remaining<=0: return dict(scene=scene_id,status='NOT_DISPATCHED_CAMPAIGN_WALL_LIMIT')
    command=['timeout','--signal=TERM','--kill-after=10s',f'{remaining:.3f}s',sys.executable,str(Path(__file__).resolve()),
        'scene','--bundle',str(bundle),'--scene',scene_id]
    started=time.monotonic()
    env={**os.environ,**{k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}}
    with (bundle/f'{scene_id}.log').open('w') as log:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
    return dict(scene=scene_id,status='WORKER_RETURN' if result.returncode==0 else 'WORKER_FAILURE',
        exit_code=result.returncode,elapsed_seconds=time.monotonic()-started,command=command)


def campaign(bundle,validation):
    started=time.monotonic();audit=prepare(bundle,validation)
    record=dict(status='IN_PROGRESS',workers=[],oracle_status=audit['status'],started_utc=datetime.now(timezone.utc).isoformat())
    write(bundle/'campaign.json',record)
    if audit['status']=='PASS':
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures=[pool.submit(run_job,bundle,name,started+WALL_SECONDS) for name in read(bundle/'contract.json')['scenes']]
            for future in as_completed(futures):
                worker=future.result();record['workers'].append(worker)
                write(bundle/'campaign.json',record);print(json.dumps(worker),flush=True)
        record['status']='DISPATCH_COMPLETE'
    else: record['status']='ORACLE_GATE_STOP'
    record['elapsed_wall_seconds']=time.monotonic()-started
    verify(bundle);write(bundle/'campaign.json',record)
    write(bundle/'artifact_manifest.json',{str(path.relative_to(bundle)):p.digest(path)
        for path in sorted(bundle.rglob('*')) if path.is_file() and path.name!='artifact_manifest.json'})
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('campaign','scene'));parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--validation',type=Path);parser.add_argument('--scene')
    args=parser.parse_args()
    require(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')),'BLAS must be one thread')
    if args.mode=='campaign':
        require(args.validation is not None,'validation required');campaign(args.bundle.resolve(),args.validation.resolve())
    else: run_scene(args.bundle.resolve(),args.scene)
