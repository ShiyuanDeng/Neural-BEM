"""Read back physical, defect-bound, rank-selection and refresh decisions."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.laurent_compression.adapters import relative
from experiments.laurent_compression.metrics import (acceptance,cancellation_allowance,
    objective,objective_derivative,objective_derivative_passes)
from .model import GUARD_LIMITS,relative_bound
from .run import hashes


def audit(output):
    out = Path(output)
    def read(name):
        return json.loads((out/name).read_text())
    def csv_rows(name):
        with (out/name).open() as stream:
            return list(csv.DictReader(stream))
    def close(a,b):
        np.testing.assert_allclose(a,b,rtol=2e-10,atol=1e-25)
    for name,digest in read('artifact_hashes.json').items():
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest,name
    manifest,summary,config = read('manifest.json'),read('summary.json'),read('config.json')
    assert manifest['source_hashes']==hashes(),'Source drift'
    assert summary['status']=='COMPLETE' and not summary['source_drift']
    rows,details = csv_rows('comparisons.csv'),csv_rows('derivatives.csv')
    by_id = {r['comparison_id']:r for r in rows}
    assert len(by_id)==len(rows)==summary['comparisons']
    assert len(details)==6*len(rows)
    for row in rows:
        cid = row['comparison_id']
        data = np.load(out/f'outputs-{cid}.npz')
        errors = [relative(a,b) for a,b in zip(data['dy'],data['reference_dy'])]
        field = relative(data['y'],data['reference_y'])
        _,r = objective(data['y'],data['observed'])
        _,rr = objective(data['reference_y'],data['observed'])
        objectives = [objective_derivative_passes(objective_derivative(r,a),objective_derivative(rr,b),
            cancellation_allowance(rr,b)) for a,b in zip(data['dy'],data['reference_dy'])]
        linked = sorted([d for d in details if d['comparison_id']==cid],key=lambda d:int(d['direction_index']))
        assert [int(d['direction_index']) for d in linked]==list(range(6))
        for detail,error,check in zip(linked,errors,objectives):
            close(error,float(detail['data_derivative_error']))
            assert (detail['passes']=='True')==check['passes']
        gates = acceptance(field,float(row['lifted_residual']),max(errors[:4]),max(errors[4:]),
            all(c['passes'] for c in objectives),qualified=row['reference_qualified']=='True')
        for k,v in gates.items():
            assert v==(row[k]=='True'),(cid,k)
    ranks = csv_rows('rank_selection.csv')
    groups = {}
    for r in ranks:
        key = r['case'],r['location'],r['arm']
        groups.setdefault(key,[]).append(r)
        eligible = (float(r['field_error'])<=1e-8 and float(r['native_residual'])<=1e-8
                    and float(r['training_derivative_error'])<=1e-5)
        assert eligible==(r['eligible']=='True')
        assert int(r['rank'])>=int(r['protected_rank'])
    for (case,location,arm),group in groups.items():
        eligible = [int(r['rank']) for r in group if r['eligible']=='True']
        rank = min(eligible) if eligible else max(int(r['rank']) for r in group)
        v = np.load(out/f'basis-{case}-{location}-{arm}.npz')['v']
        assert v.shape[1]==rank
        np.testing.assert_allclose(v.conj().T@v,np.eye(rank),atol=5e-12)
    guards = read('guards.json')
    by_guard = {g['comparison_id']:g for g in guards}
    assert len(by_guard)==len(guards)==summary['guard_evaluations']
    for g in guards:
        data = np.load(out/f"outputs-{g['comparison_id']}.npz")
        native = np.load(out/f"native-{g['case']}-{g['scenario']}.npz")
        sigma = g['sigma_min']
        e = np.asarray(g['primal_pair_residual_norms'])/sigma
        s = np.asarray(g['dual_pair_residual_norms'])
        field_abs = np.linalg.norm(np.asarray(g['dual_primal_contractions'])+s*e)
        absolute = []
        for d in g['derivative_bound_ingredients']:
            bound = np.asarray(d['effective_receiver_norms'])*e+np.asarray(d['dual_tangent_contractions'])
            bound += s/sigma*(np.asarray(d['tangent_residual_norms'])+d['derivative_operator_norm']*e)
            absolute.append(float(np.linalg.norm(bound)))
        rel = [relative_bound(a,y) for a,y in zip(absolute,data['dy'][:4])]
        field_rel = relative_bound(field_abs,data['y'])
        close(field_abs,g['field_absolute_bound'])
        close(absolute,g['derivative_absolute_bounds'])
        close(rel,g['derivative_relative_bounds'])
        close(field_rel,g['field_relative_bound'])
        actual = np.linalg.norm(data['y']-native['y'])
        actual_ds = [np.linalg.norm(a-b) for a,b in zip(data['dy'][:4],native['dy'])]
        close(actual,g['field_absolute_error'])
        close(actual_ds,g['derivative_absolute_errors'])
        allowance = config['bound_readback_roundoff_allowance']
        cover = (actual<=field_abs+allowance*np.linalg.norm(native['y']) and
            all(error<=bound+allowance*np.linalg.norm(y) for error,bound,y in zip(actual_ds,absolute,native['dy'])))
        assert cover==g['bounds_cover']
        accepted = (g['primal_residual']<=GUARD_LIMITS['primal_residual']
            and field_rel<=GUARD_LIMITS['field_relative_bound'] and max(rel)<=GUARD_LIMITS['derivative_relative_bound'])
        assert accepted==g['accepted']
        assert g['physical_pass']==(by_id[g['comparison_id']]['passes_all']=='True')
    policies = csv_rows('policies.csv')
    for p in policies:
        frozen,delivered = by_id[p['frozen_id']],by_id[p['delivered_id']]
        if by_guard[p['frozen_id']]['accepted']:
            assert p['action']=='REUSE' and p['frozen_id']==p['delivered_id']
        else:
            rebuilt = by_guard[f"{p['case']}-{p['scenario']}__rebuilt-{p['arm']}"]
            assert p['action']==('REBUILD' if rebuilt['accepted'] else 'FULL_FALLBACK')
        assert p['frozen_pass']==frozen['passes_all'] and p['delivered_pass']==delivered['passes_all']
        assert p['frozen_rank']==frozen['rank'] and p['delivered_rank']==delivered['rank']
    controls = csv_rows('controls.csv')
    fds,windows = csv_rows('finite_differences.csv'),csv_rows('windows.csv')
    false_accepts = [g['comparison_id'] for g in guards if g['accepted'] and not g['physical_pass']]
    reuses = [p['delivered_id'] for p in policies if p['action']=='REUSE' and p['scenario']!='anchor'
        and p['arm']!='JOINT_TANGENT' and int(p['frozen_rank'])<=int(p['dimension'])/2 and p['delivered_pass']=='True']
    release = (all(c['qualified']=='True' for c in controls) and all(float(f['relative_error'])<1e-4 for f in fds)
        and all(g['bounds_cover'] for g in guards) and not false_accepts and bool(reuses)
        and all(w['qualified']=='True' and float(w['field_error'])<1e-8 and float(w['derivative_error'])<1e-6 for w in windows))
    assert release==summary['campaign_released']
    assert false_accepts==summary['guard_false_accepts']
    assert reuses==summary['compact_nonanchor_reuses']
    assert sum(g['bounds_cover'] for g in guards)==summary['bounds_covered']
    assert sum(r['passes_all']=='True' for r in rows)==summary['passed']
    assert len(policies)==summary['policy_count']
    assert sum(p['delivered_pass']=='True' for p in policies)==summary['delivered_passed']
    for action,count in summary['policy_actions'].items():
        assert sum(p['action']==action for p in policies)==count
    limits = manifest['ceilings']
    for k in ('assemblies','factorizations','rhs_batches'):
        assert summary['work'][k]<=limits[k]
    assert summary['seconds']<=limits['seconds'] and summary['peak_gib']<=limits['peak_gib']
    return dict(status='PASS',comparisons=len(rows),guards=len(guards),policies=len(policies))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    print(json.dumps(audit(parser.parse_args().output),indent=2))
