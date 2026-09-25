"""SC-037: one later-state ladder, reusing SC-035's exact low-K prefix."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace,asdict
from pathlib import Path
import importlib.util
import sys
import time
import traceback
from experiments.shape_continuation import atlas_cases as ac,atlas_strategy_tests as ast,spd_cases as sc
from experiments.shape_continuation.lm_backend import Ledger,stage_record
from experiments.shape_continuation.finite_path_study import frozen_sources,geometric_score

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'SC-035-state-band'
sys.path.insert(0,str(BASE))
from state_update import ProjectedUpdate
spec=importlib.util.spec_from_file_location('sc035_driver',BASE/'run.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
CASES=('peanut','circle_to_c','circle_to_star','kite')
PLAN=sc.ROOT/'docs/iterations/shape_frequency_continuation/iteration_18/03_plan.md'


def hashes():
    return dict(**frozen_sources(),**{str(p.relative_to(sc.ROOT)):sc.digest(p) for p in
         (BASE/'state_update.py',BASE/'run.py',Path(__file__),PLAN)})


def worker(case):
    folder=HERE/'runs'/case;folder.mkdir(parents=True,exist_ok=False)
    ledger=None
    try:
        prefix=sc.read(BASE/'runs'/case/'low/pilot.json')
        assert prefix['status']=='COMPLETED_SCHEDULE'
        catalog=ast.catalog_only(case)
        stages,config=ast.schedules(catalog,'baseline')
        stages=[replace(s,curve_modes=k) for s,k in zip(stages,(8,16,32,64))]
        release=replace(stages[-1],label='stage_5_release_repeat',curve_modes=192,quota=1000)
        curve=ast.curve_from(prefix['curve'])
        ledger=Ledger(cap=3000,seconds=max(0,2700-prefix['seconds']))
        snapshot=prefix['work'];ledger.units=snapshot['work_units']
        ledger.solves=dict(snapshot['solves']);ledger.reciprocal=dict(snapshot['reciprocal_batches']);ledger.failed=dict(snapshot['failed'])
        update=ProjectedUpdate(sc.LENGTH)
        before=hashes()
        sc.write(folder/'configuration.json',dict(case=case,band_ladder=[8,16,32,64,192],
             prefix_sha256=sc.digest(BASE/'runs'/case/'low/pilot.json'),backend=asdict(config),
             stages=[stage_record(s) for s in stages+[release]],update=update.settings()))
        started=time.perf_counter()
        curve,rows,status,reason=old.run_stages(curve,stages[1:]+[release],update,config,ledger,folder)
        elapsed=time.perf_counter()-started
        truth=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
        result=dict(case=case,status=status,reason=reason,curve=ast.curve_record(curve),stages=rows,
             work=ledger.snapshot(),seconds=elapsed,total_inverse_seconds=elapsed+prefix['seconds'],
             geometry_work=update.counts,score=ast.score(case,curve,catalog),
             geometry=geometric_score(curve,truth),prefix_units=prefix['work']['work_units'])
        state4=folder/'stage_4_history.json'
        if state4.exists():
            h=sc.read(state4)['history']
            if h:result['before_release_geometry']=geometric_score(ast.curve_from(h[-1]['coefficients']),truth)
        assert hashes()==before,'sources changed'
        sc.write(folder/'result.json',result)
        print('DONE',case,status,result['score']['symmetric_rms_mm'],ledger.units,flush=True)
        return dict(case=case,status=status,reason=reason,score=result['score'],units=ledger.units)
    except Exception:
        failure=dict(case=case,status='EXCEPTION',traceback=traceback.format_exc(),work=ledger.snapshot() if ledger else None)
        sc.write(folder/'failure.json',failure);print(failure,flush=True);return failure


def main():
    (HERE/'runs').mkdir(exist_ok=False)
    sc.write(HERE/'manifest.json',dict(experiment='SC-037',sources=hashes(),command=sys.argv,workers=4,
        cases=CASES,inverse_cap=12000,evaluation_fields=76,ladder=[8,16,32,64,192],
        inputs={str(p.relative_to(sc.ROOT)):sc.digest(p) for c in CASES for p in
            (BASE/'runs'/c/'low/pilot.json',ast.source_folder(c)/'observations.json',ast.source_folder(c)/'truth.json')}))
    rows=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for row in pool.map(worker,CASES):
            rows.append(row);sc.write(HERE/'summary.json',dict(rows=rows))
    sc.write(HERE/'completion.json',dict(status='COMPLETE' if all(r['status']!='EXCEPTION' for r in rows) else 'FAILED'))


if __name__=='__main__':
    main()
