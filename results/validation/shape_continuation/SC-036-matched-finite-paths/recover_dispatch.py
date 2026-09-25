"""Resume campaign coverage after external SIGTERM; preserve completed/partial evidence."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json
import time
import traceback
from run_inverse import worker,CASES,HERE
from experiments.shape_continuation import spd_cases as sc


def main():
    jobs=[(c,a) for c in CASES for a in ('normal','ray') if not (HERE/'inverse'/c/a/'result.json').exists()]
    interruption=sc.read(HERE/'inverse/interruption.json')
    known=sum(sc.read(p)['work']['work_units'] for p in (HERE/'inverse').glob('*/*/result.json'))
    reserve=len(jobs)*(2400+19)+known+sum(r['work_upper_bound'] for r in interruption['interrupted'])+8*19
    assert reserve<20000,(reserve,'aggregate ceiling')
    sc.write(HERE/'inverse/recovery_manifest.json',dict(jobs=jobs,reserved_upper_bound=reserve,
        source_sha256=sc.digest(Path(__file__)),method='same initial states; interrupted attempts retained; no numerical changes'))
    try:
        with ProcessPoolExecutor(max_workers=2) as pool:
            list(pool.map(worker,jobs))
        rows=[]
        for case in CASES:
            for arm in ('normal','ray'):
                d=sc.read(HERE/'inverse'/case/arm/'result.json')
                rows.append(dict(case=case,arm=arm,status=d['status'],reason=d['reason'],units=d['work']['work_units'],
                                 seconds=d['inverse_seconds'],score=d['score']))
        sc.write(HERE/'inverse/summary.json',dict(rows=rows,total_inverse_units=sum(r['units'] for r in rows),
            interruption=interruption,retained_attempts=True))
        sc.write(HERE/'inverse/completion.json',dict(status='COMPLETE',timestamp=time.strftime('%Y-%m-%dT%H:%M:%S%z')))
    except Exception:
        sc.write(HERE/'inverse/completion.json',dict(status='FAILED',traceback=traceback.format_exc()))
        raise


if __name__=='__main__':
    main()
