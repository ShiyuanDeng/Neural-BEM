"""Reconcile complete SPD-004 arms and report measured architecture savings."""
import argparse
import csv
from pathlib import Path
from statistics import median
import numpy as np
from scipy.spatial import cKDTree
from . import run as r


def summarize(parent):
    r.verify_all(parent)
    timings=r.read(parent/'timings.json')
    complete=r.read(parent/'execution_status.json')['status']=='COMPLETE'
    rows=[]
    for scene in ('death','split','merge'):
        repetitions=(0,) if scene=='merge' else (0,1)
        for rep in repetitions:
            labels=[f'{arm}_{rep}' for arm in ('baseline','readiness')]
            measured=[next((t for t in timings if t['arm']==label and t['scene']==scene),None) for label in labels]
            if not all(measured):
                continue
            results=[];metrics=[];states=[];derivatives=[]
            for label in labels:
                directory=parent/label/'runs'/scene
                result=r.read(directory/'result.json');results.append(result)
                assert result['sources_and_inputs_unchanged']
                metric=r.read(directory/'F/metrics.json');metrics.append(metric)
                states.append(r.p.driver.deserialize_state(metric['final_state']))
                works=[result['topology_work'],result['continuation']['work']]
                for work in works:
                    assert work['total_attempted']==sum(work['attempted'].values())
                    assert work['total_attempted']==sum(work['completed'].values())+sum(work['failed'].values())
                    da=sum(work['derivative_assemblies_attempted'].values())
                    assert da==sum(work['derivative_assemblies_completed'].values())+sum(work['derivative_assemblies_failed'].values())
                    assert work['budget_work_units']==work['total_attempted']+da
                    assert work['within_solve_cap']
                derivatives.append(sum(sum(w['derivative_assemblies_attempted'].values()) for w in works))
            assert states[0].component_ids==states[1].component_ids
            delta=max(max(cKDTree(a).query(b)[0].max(),cKDTree(b).query(a)[0].max())
                for a,b in zip(r.p.boundary_points(states[0]),r.p.boundary_points(states[1])))
            coeff=float(np.max(np.abs(states[0].parameter_vector()-states[1].parameter_vector())))
            events=[[e['kind'] for e in r.read(parent/label/'runs'/scene/'topology/events.json')] for label in labels]
            quality=all(x['fresh_recovery_pass'] for x in results) and delta<=1e-6 and coeff<=1e-6 and events[0]==events[1]
            assert quality,(scene,rep,'quality regression')
            row=dict(scene=scene,repetition=rep,baseline_seconds=measured[0]['seconds'],
                readiness_seconds=measured[1]['seconds'],speedup=measured[0]['seconds']/measured[1]['seconds'],
                both_recovered=quality,boundary_difference_m=float(delta),coefficient_difference_m=coeff,
                skipped=results[1]['continuation'].get('skipped_continuation',False),
                baseline_systems=results[0]['actual_attempted_calls'],readiness_systems=results[1]['actual_attempted_calls'],
                baseline_derivatives=derivatives[0],readiness_derivatives=derivatives[1])
            rows.append(row)
    aggregates=[]
    for scene in ('death','split','merge'):
        selected=[row for row in rows if row['scene']==scene]
        if not selected:
            continue
        baseline=median(row['baseline_seconds'] for row in selected)
        ready=median(row['readiness_seconds'] for row in selected)
        aggregates.append(dict(scene=scene,repetitions=len(selected),baseline_seconds=baseline,
            readiness_seconds=ready,speedup=baseline/ready,
            benefit_gate=baseline/ready>=1.5 if scene!='merge' else ready/baseline<=1.10))
    expected=len(rows)==5
    report=dict(status='PASS' if complete and expected and all(a['benefit_gate'] for a in aggregates) else 'INCOMPLETE_OR_BENEFIT_GATE_MISSED',
        complete=complete,rows=rows,aggregate=aggregates,scope='two repeated full easy cases and one full fallback pair',
        host_isolation='not established outside the experiment PID namespace')
    r.write(parent/'summary.json',report)
    if rows:
        with (parent/'comparison.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    r.write(parent/'verification.json',dict(status='PASS' if complete and expected else 'INCOMPLETE',
        full_case_quality_pass=all(row['both_recovered'] for row in rows),
        counts_reconciled=True,sources_and_inputs_unchanged=True,
        original_stage_exposure_claimed_for_skipped_stages=False))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path)
    print(summarize(parser.parse_args().bundle.resolve()))
