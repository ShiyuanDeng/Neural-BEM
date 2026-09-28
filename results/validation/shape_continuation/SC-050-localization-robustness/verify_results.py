"""Independent saved-evidence checks; run after all timed attempts."""
from pathlib import Path
import importlib.util
import json
import numpy as np
from ordered_boundary import sampled_self_intersection_count
from ordered_boundary.validation_cache import intersection_validation

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc050_verify',HERE/'run.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
read=lambda p:json.loads(Path(p).read_text())
m.verify()
selection=read(HERE/'selection.json')
checks=[];geometry=[]
results=list((HERE/'runs').glob('*/*/result.json'))
assert len(results)==18
assert len(list((HERE/'pre_amendment').glob('*/result.json')))==2
for path in sorted(results):
    row=read(path);folder=path.parent
    assert row['outcome'] not in ('EXCEPTION','WITHHELD_INPUT'), str(path)
    assert row['fit_and_localization_units']<=m.FIT_CAP
    assert row['fit_and_localization_seconds']<=m.FIT_SECONDS+1
    initial,final=[read(folder/f'{name}_audit.json') for name in ('initial','final')]
    assert initial['passed']
    assert row['final_audit_passed']==final['passed']
    for name,record in (('initial',initial),('final',final)):
        assert record['work']['work_units']<=130
        assert record['seconds']<=300
    locpath=folder/'localization.json'
    if locpath.exists():
        loc=read(locpath)
        assert sum(r['attempted_units'] for r in loc['rows'])==loc['units']<=2000
        assert loc['seconds']<=600
        selected=[r for r in loc['rows'] if np.allclose(r['parameters_m'],loc['parameters_m'],rtol=0,atol=1e-11)]
        assert selected and all(r['qualified'] for r in selected)
        assert any(r['nodes']==[512,1024] for r in selected)
        for r in loc['rows']:
            if r['qualified']:
                assert r['exterior_clearance_m']>0 and max(r['field_relative'])<=1e-7
        checks.append(dict(scene=row['scene'],arm=row['arm'],localization_units=loc['units'],
            inadmissible_candidates=sum(r['reason']=='source_or_receiver_not_exterior' for r in loc['rows']),
            resolution_refusals=sum(r['reason']=='resolution_disagreement' for r in loc['rows'])))
    curve=m.ast.curve_from(row['final_curve'])
    for nodes in (512,1024,2048):
        points=curve.nodes(nodes).points
        counts=[]
        for backend in ('reference','spatial'):
            with intersection_validation(backend):
                counts.append(sampled_self_intersection_count(points))
        assert counts[0]==counts[1]==0
        geometry.append(dict(scene=row['scene'],arm=row['arm'],nodes=nodes,reference=counts[0],spatial=counts[1]))
    metrics=row['metrics']
    success=bool(final['passed'] and metrics['rms_mm']<=1 and metrics['hausdorff_upper_mm']<=2
                 and np.all(np.array(row['relative_residual'])<=row['residual_limits']))
    assert success==row['recovered']
    assert row['total_units']==row['fit_and_localization_units']+initial['work']['work_units']+final['work']['work_units']+19
    for stage in row['stages']:
        for check in read(folder/f"{stage['stage']}.json")['acceptance_checks']:
            if check.get('accepted'):
                assert not check.get('numerical_obstruction',False)
                assert check['production_gain']>check['margin'] and check['refined_gain']>check['margin']
summary=read(HERE/'summary.json')
assert summary['baseline_exact_accepted_replay']
assert all(r['initial_separating_axis_gap_mm']>0 for r in summary['fixtures'])
manifest=read(HERE/'manifest.json')
assert m.sc.digest(HERE/'initial_domain_amendment.json')==manifest['amendments'][-1]['input_amendment_sha256']
# Recompute the frozen selection rule from data-only endpoints, not truth metrics.
development=[read(p) for p in (HERE/'runs/development_c').glob('*/result.json') if p.parent.name!='baseline']
def rank(r):
    group=0 if r['outcome']=='COMPLETED_SCHEDULE' and r['final_audit_passed'] else 1 if r['final_audit_passed'] else 2
    return (group,r['maximum_residual'],r['fit_and_localization_units'],r['arm'])
assert min(development,key=rank)['arm']==selection['arm']
outputs={str(p.relative_to(HERE)):m.sc.digest(p) for p in sorted(HERE.rglob('*'))
         if p.is_file() and p.name!='verification.json' and '__pycache__' not in p.parts and p.suffix not in ('.tmp',)}
m.write(HERE/'verification.json',dict(passed=True,attempts=18,retained_setup_failures=2,
    frozen_sources_inputs=True,all_budgets=True,baseline_exact=True,selection_rule_reproduced=True,
    geometry_comparisons=geometry,localization_checks=checks,output_sha256=outputs))
print('PASS: 18 attempts, 2 preserved setup failures, 54 exact endpoint geometry comparisons, all budgets and selection rule')
