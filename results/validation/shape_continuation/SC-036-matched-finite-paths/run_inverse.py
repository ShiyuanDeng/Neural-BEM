"""SC-036 conditional complete inverses. Two processes, one BLAS thread each."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
import sys
import time
import traceback

from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.finite_paths import RayUpdate
from experiments.shape_continuation.finite_path_study import frozen_sources
from experiments.shape_continuation.lm_backend import Ledger, stage_record
from experiments.shape_continuation.updates import BorgesUpdate

HERE=Path(__file__).resolve().parent
CASES=('peanut','kite','circle_to_star','circle_to_c')


def worker(job):
    case,arm=job
    folder=HERE/'inverse'/case/arm
    folder.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    ledger=Ledger(cap=2400,seconds=2700)
    try:
        catalog=ast.catalog_only(case)
        stages,config=ast.schedules(catalog,'baseline')
        update=(BorgesUpdate(sc.LENGTH,projection_tolerance=1e-5) if arm=='normal'
                else RayUpdate(sc.LENGTH,fallback=True))
        initial,_=update.regauge(ac.start_curve(),stages[0].curve_modes)
        sc.write(folder/'configuration.json',dict(case=case,arm=arm,update=update.settings(),
            backend=asdict(config),stages=[stage_record(s) for s in stages],
            initial_curve=ast.curve_record(initial),cap=ledger.cap,seconds=ledger.seconds))
        sources=frozen_sources()
        with geometry_validation('cache'):
            curve,records,status,reason=ast.optimize_segment(initial,stages,ac.contrast(),config,update,ledger,folder)
        elapsed=time.perf_counter()-started
        # Truth and unused frequencies only enter evaluation after fit returns.
        result=dict(case=case,arm=arm,status=status,reason=reason,inverse_seconds=elapsed,
            work=ledger.snapshot(),final_curve=ast.curve_record(curve),
            stages=[dict(stage=r.stage_label,outcome=r.outcome,stop=r.stop_reason,
                         accepted_steps=r.accepted_steps,initial_loss=r.initial_loss,final_loss=r.final_loss,
                         work=r.work,seconds=r.seconds) for r in records],
            score=ast.score(case,curve,catalog))
        assert frozen_sources()==sources,'sources changed during inverse'
        sc.write(folder/'result.json',result)
        print(case,arm,status,reason,result['score']['symmetric_rms_mm'],ledger.units,flush=True)
        return dict(case=case,arm=arm,status=status,reason=reason,units=ledger.units,
                    seconds=elapsed,score=result['score'])
    except Exception:
        failure=dict(case=case,arm=arm,status='EXCEPTION',traceback=traceback.format_exc(),work=ledger.snapshot())
        sc.write(folder/'failure.json',failure)
        print(failure,flush=True)
        return failure


def main():
    screen=sc.read(HERE/'summary.json')
    assert screen['release_inverse'], 'matched-path gate has not passed'
    jobs=[(case,arm) for case in CASES for arm in ('normal','ray')]
    (HERE/'inverse').mkdir(exist_ok=False)
    sc.write(HERE/'inverse/manifest.json',dict(jobs=jobs,workers=2,per_path_cap=2400,
        total_reserved_inverse_units=19200,evaluation_units=8*19,screen_work=screen['work'],
        command=sys.argv,sources=frozen_sources(),driver_sha256=sc.digest(Path(__file__)),
        inputs=sc.read(HERE/'manifest.json')['inputs']))
    rows=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for row in pool.map(worker,jobs):
            rows.append(row)
            sc.write(HERE/'inverse/summary.json',dict(rows=rows,
                total_inverse_units=sum(r.get('units',r.get('work',{}).get('work_units',0)) for r in rows)))


if __name__=='__main__':
    main()
