"""Rebuild gate decisions from saved output vectors and scalar residuals."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.laurent_compression.adapters import relative
from experiments.laurent_compression.metrics import (acceptance, cancellation_allowance,
    objective, objective_derivative, objective_derivative_passes)
from .run import hashes


def audit(output):
    out = Path(output)
    def rows(name):
        with (out/name).open() as stream:
            return list(csv.DictReader(stream))
    def js(name):
        return json.loads((out/name).read_text())
    for name,digest in js('artifact_hashes.json').items():
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest,name
    assert js('manifest.json')['source_hashes']==hashes(),'Source drift'
    summary = js('summary.json')
    assert summary['status']=='COMPLETE'
    comparisons = rows('comparisons.csv')
    directional = rows('derivatives.csv')
    assert len(comparisons)==summary['comparisons']
    assert len(directional)==6*len(comparisons)
    for row in comparisons:
        cid = row['comparison_id']
        data = np.load(out/f'outputs-{cid}.npz')
        field = relative(data['y'],data['reference_y'])
        errors = [relative(a,b) for a,b in zip(data['dy'],data['reference_dy'])]
        _,r = objective(data['y'],data['observed'])
        _,rr = objective(data['reference_y'],data['observed'])
        checks = [objective_derivative_passes(objective_derivative(r,a),
            objective_derivative(rr,b),cancellation_allowance(rr,b))
            for a,b in zip(data['dy'],data['reference_dy'])]
        linked = sorted([d for d in directional if d['comparison_id']==cid],key=lambda d:int(d['direction_index']))
        assert [int(d['direction_index']) for d in linked]==list(range(6))
        for i,(item,error,check) in enumerate(zip(linked,errors,checks)):
            np.testing.assert_allclose(error,float(item['data_derivative_error']),rtol=1e-12,atol=1e-15)
            assert (item['passes']=='True')==check['passes']
        gates = acceptance(field,float(row['lifted_residual']),max(errors[:4]),max(errors[4:]),
            all(c['passes'] for c in checks),qualified=row['reference_qualified']=='True')
        for key,value in gates.items():
            assert value==(row[key]=='True'),(cid,key)
        assert int(row['reduced_matrix_slots'])==int(row['rank'])**2
        selected = [r for r in rows('rank_selection.csv') if r['case']==row['case'] and r['arm']==row['arm']]
        eligible = [r for r in selected if r['eligible']=='True']
        expected = min(int(r['rank']) for r in eligible) if eligible else max(int(r['rank']) for r in selected)
        assert int(row['rank'])==expected
    assert sum(r['passes_all']=='True' for r in comparisons)==summary['passed']
    assert sum(r['qualified']=='True' for r in rows('controls.csv'))==summary['controls_qualified']
    fd = rows('finite_differences.csv')
    assert len(fd)==summary['finite_differences']
    assert sum(float(r['relative_error'])<1e-4 for r in fd)==summary['finite_difference_passed']
    limits = js('manifest.json')['ceilings']
    for key in ('assemblies','factorizations','rhs_batches'):
        assert summary['work'][key]<=limits[key]
    assert summary['seconds']<=limits['seconds'] and summary['peak_gib']<=limits['peak_gib']
    return dict(status='PASS',comparisons=len(comparisons),directions=len(directional))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    print(json.dumps(audit(parser.parse_args().output),indent=2))
