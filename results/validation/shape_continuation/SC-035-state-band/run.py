"""SC-035 pilot with a binding gate and matched continuation/release."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace,asdict
from pathlib import Path
import sys
import time
import traceback
import numpy as np
from ordered_boundary.validation_cache import geometry_validation
from state_update import ProjectedUpdate,resize
from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.finite_path_study import geometric_score,frozen_sources
from experiments.shape_continuation.lm_backend import Ledger,fit_stage,NORMAL_RETURN,STAGE_QUOTA,Stop,stage_record

HERE=Path(__file__).resolve().parent
CASES=('peanut','circle_to_c','circle_to_star','kite')
PLAN=sc.ROOT/'docs/iterations/shape_frequency_continuation/iteration_17/03_plan.md'


def hashes():
    return dict(**frozen_sources(),**{str(p.relative_to(sc.ROOT)):sc.digest(p) for p in
        (HERE/'state_update.py',HERE/'qualify.py',Path(__file__),PLAN)})


def run_stages(curve,stages,update,config,ledger,folder):
    rows=[]
    status,reason='COMPLETED_SCHEDULE',None
    with geometry_validation('cache'):
        for stage in stages:
            curve=resize(curve,stage.curve_modes)
            ledger.begin_stage(stage.label,stage.quota)
            record=fit_stage(curve,stage,ac.contrast(),update,config,ledger)
            curve=record.curve
            rows.append(dict(stage=stage.label,outcome=record.outcome,stop=record.stop_reason,
                accepted_steps=record.accepted_steps,initial_loss=record.initial_loss,final_loss=record.final_loss,
                work=record.work,seconds=record.seconds))
            sc.write(folder/f'{stage.label}_history.json',dict(history=record.history,trials=record.trials,
                 acceptance_checks=record.acceptance_checks))
            sc.write(folder/'checkpoint.json',dict(curve=ast.curve_record(curve),stages=rows,work=ledger.snapshot()))
            print(folder.parent.name,folder.name,stage.label,record.outcome,record.stop_reason,
                  record.accepted_steps,record.final_loss,ledger.units,flush=True)
            if record.outcome not in (NORMAL_RETURN,STAGE_QUOTA):
                status,reason='HARD_STOP',record.outcome
                break
    return curve,rows,status,reason


def worker(job):
    phase,case,arm=job
    folder=HERE/'runs'/case/arm
    ledger=None
    try:
        catalog=ast.catalog_only(case)
        stages,config=ast.schedules(catalog,'baseline')
        stages=[replace(s,curve_modes=2*s.update_modes+2 if arm=='low' else 192) for s in stages]
        update=ProjectedUpdate(sc.LENGTH)
        if phase=='pilot':
            folder.mkdir(parents=True,exist_ok=False)
            ledger=Ledger(cap=600,seconds=900)
            curve,_=update.regauge(ac.start_curve(),stages[0].curve_modes)
            sc.write(folder/'configuration.json',dict(case=case,arm=arm,update=update.settings(),backend=asdict(config),
                stages=[stage_record(s) for s in stages],initial=ast.curve_record(curve)))
            current_stages=stages[:1]
            previous=None
        else:
            previous=sc.read(folder/'pilot.json')
            if previous['status']!='COMPLETED_SCHEDULE':
                return dict(case=case,arm=arm,phase=phase,status='PILOT_HARD_STOP',reason=previous['reason'])
            curve=ast.curve_from(previous['curve'])
            ledger=Ledger(cap=3000,seconds=max(0,2700-previous['seconds']))
            old=previous['work']
            ledger.units=old['work_units']
            ledger.solves=dict(old['solves']);ledger.reciprocal=dict(old['reciprocal_batches']);ledger.failed=dict(old['failed'])
            release=replace(stages[-1],label='stage_5_release_repeat',curve_modes=192,quota=1000)
            current_stages=stages[1:]+[release]
        started=time.perf_counter()
        before=hashes()
        curve,rows,status,reason=run_stages(curve,current_stages,update,config,ledger,folder)
        seconds=time.perf_counter()-started
        # Scoring is isolated here, only after fit returns.
        truth=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
        result=dict(case=case,arm=arm,phase=phase,status=status,reason=reason,
            curve=ast.curve_record(curve),stages=rows,work=ledger.snapshot(),seconds=seconds,
            total_inverse_seconds=seconds+(previous['seconds'] if previous else 0),
            geometry=geometric_score(curve,truth),geometry_work=update.counts)
        if phase=='continue':
            result['score']=ast.score(case,curve,catalog)
            # Stage-4 state is scored without changing the chosen endpoint.
            p=folder/'stage_4_history.json'
            if p.exists():
                state=ast.curve_from(sc.read(p)['history'][-1]['coefficients'])
                result['before_release_geometry']=geometric_score(state,truth)
        assert hashes()==before,'frozen source changed during a path'
        sc.write(folder/f'{phase}.json',result)
        print('DONE',case,arm,phase,status,result['geometry'],ledger.units,flush=True)
        return {k:result[k] for k in ('case','arm','phase','status','reason','geometry','work','total_inverse_seconds')}
    except Exception:
        failure=dict(case=case,arm=arm,phase=phase,status='EXCEPTION',traceback=traceback.format_exc(),
                     work=ledger.snapshot() if ledger else None)
        folder.mkdir(parents=True,exist_ok=True)
        sc.write(folder/f'{phase}_failure.json',failure)
        print(failure,flush=True)
        return failure


def dispatch(phase):
    rows=[]
    jobs=[(phase,case,arm) for case in CASES for arm in ('low','high')]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for row in pool.map(worker,jobs):
            rows.append(row)
            sc.write(HERE/f'{phase}_summary.json',dict(rows=rows))
    return rows


def main():
    assert sc.read(HERE/'qualification.json')['passed'],'qualification gate failed'
    (HERE/'runs').mkdir(exist_ok=False)
    sc.write(HERE/'manifest.json',dict(experiment='SC-035',sources=hashes(),command=sys.argv,workers=2,
        plan_sha256=sc.digest(PLAN),cases=CASES,bands=dict(low=[8,12,16,20,192],high=[192]*5),
        inputs={str(p.relative_to(sc.ROOT)):sc.digest(p) for case in CASES for p in
            (ast.source_folder(case)/'observations.json',ast.source_folder(case)/'truth.json')},
        pilot_cap=600,total_path_cap=3000,continuation_reserve=24000,final_evaluation_reserve=152))
    rows=dispatch('pilot')
    completed=all(r['status']=='COMPLETED_SCHEDULE' for r in rows)
    ratios={}
    if completed:
        for case in CASES:
            low=next(r for r in rows if r['case']==case and r['arm']=='low')['geometry']['rms_mm']
            high=next(r for r in rows if r['case']==case and r['arm']=='high')['geometry']['rms_mm']
            ratios[case]=low/high
    passed=completed and min(ratios['peanut'],ratios['circle_to_c'])<=.8 and max(
        ratios['circle_to_star'],ratios['kite'])<=1.25
    sc.write(HERE/'gate.json',dict(passed=passed,ratios=ratios,all_completed=completed))
    print('GATE',passed,ratios,flush=True)
    if passed:
        dispatch('continue')


if __name__=='__main__':
    main()
