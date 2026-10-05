"""RG-001 stage orchestration and independent receipt checks; no numerical edits."""
from datetime import datetime, timezone
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
from bem_inverse.io import read,write,curve_from
from experiments.benchmark import rg001 as R
from experiments.benchmark import scenes as S


def check_full_P1(case,batch='all'):
    old=read(R.B.ROOT/'results/validation/cleaned_interfaces/ON-001/final_comparison.json')
    expected=next(r for r in old['rows'] if r['id']==case)['E']['recovered']
    c=read(R.OUT/batch/'C/runs'/case/'result.json')
    rg=read(R.OUT/batch/'RG/runs'/case/'result.json')
    if not expected:
        return dict(case=case,applicable=False)
    rows=read(R.OUT/batch/'pairs'/f'{case}.json')
    endpoints=[(c['final_curve'],rg['final_curve'])]
    if len(c['stages'])==len(rg['stages']):
        endpoints += [(a['curve'],b['curve']) for a,b in zip(c['stages'],rg['stages'])]
    matching=len(c['stages'])==len(rg['stages']) and all(
        len(a['real'])==len(b['real']) for a,b in endpoints)
    difference=max((float(np.max(abs(curve_from(a).coefficients-curve_from(b).coefficients)))
                    for a,b in endpoints),default=0.) if matching else None
    passed=bool(c['recovered'] and rg['recovered'] and rows.get('P1',{}).get('passed') and matching and difference==0.)
    return dict(case=case,applicable=True,passed=passed,matching_stage_topology=matching,
                maximum_stage_endpoint_coefficient_difference=difference,coefficient_tolerance=0.)


def main():
    stage=sys.argv[1]
    cutoff=datetime(2026,10,5,12,39,tzinfo=timezone.utc)
    if datetime.now(timezone.utc)>=cutoff:
        raise TimeoutError('No new stage opens after 12:39 UTC')
    if stage=='stage2':
        for name in ('replay','baseline','tests','saved_control_replay'):
            assert read(R.OUT/'qualification'/f'{name}.json')['passed']
        started=perf_counter();checks=[]
        for case in S.CASES:
            if perf_counter()-started>=3600:
                raise TimeoutError('Stage 2 one-hour compute cap')
            R.pair(case)
            extra=check_full_P1(case)
            checks.append(extra)
            if extra['applicable'] and not extra['passed']:
                write(R.OUT/'qualification/P1_stop.json',extra)
                R.publish(f'Preserve RG-001 P1 stop at {case}')
                raise RuntimeError('P1 fails: all remaining stages stopped')
        write(R.OUT/'qualification/full_P1.json',dict(passed=all(r.get('passed',True) for r in checks),rows=checks))
        R.publish('Verify RG-001 P1 across complete accepted paths and stage endpoints')
    elif stage=='stage3':
        assert read(R.OUT/'qualification/full_P1.json')['passed']
        summary=R.report();started=perf_counter()
        for case in summary['additions']:
            with R.locked():
                result=R.independent(case)
                R.check_sources()
            R.publish(f'Record RG-001 independent nodal qualification {case}')
            with R.locked():
                result=R.child('RG',case,'recovery_repeat')
                R.check_sources()
            R.publish(f'Record RG-001 fresh recovery repeat {case}')
        for batch in ('timing1','timing2'):
            for case in R.TIMING:
                if perf_counter()-started>=1800:
                    raise TimeoutError('Stage 3 thirty-minute cap')
                R.pair(case,batch)
                extra=check_full_P1(case,batch)
                if not extra.get('passed',True):
                    write(R.OUT/'qualification/P1_stop.json',extra)
                    R.publish(f'Preserve RG-001 P1 timing-repeat stop {case}')
                    raise RuntimeError('P1 fails in timing repeat')
        write(R.OUT/'qualification/stage3_complete.json',dict(passed=True,additions=summary['additions'],
            independent={case:read(R.OUT/'independent'/f'{case}.json')['passed'] for case in summary['additions']},
            fresh_recovery_repeats={case:read(R.OUT/'recovery_repeat/RG/runs'/case/'result.json')['recovered'] for case in summary['additions']},
            timing_pairs=6,seconds=perf_counter()-started))
        R.publish('Complete RG-001 independent checks and timing repeats')
    elif stage=='stage4':
        started=perf_counter()
        for case in R.FAILURES:
            if perf_counter()-started>=3600:
                raise TimeoutError('Stage 4 one-hour compute cap')
            with R.locked():
                R.child('RG',case,'extended',True)
                R.check_sources()
            R.publish(f'Record RG-001 extended-budget diagnostic {case}')
        write(R.OUT/'qualification/stage4_complete.json',dict(complete=True,seconds=perf_counter()-started,
            extended_fit_seconds=900.,extended_work_units=67060,benchmark_evidence=False))
        R.publish('Complete RG-001 extended-budget diagnostics')
    else:
        raise ValueError(stage)


if __name__=='__main__':
    main()
