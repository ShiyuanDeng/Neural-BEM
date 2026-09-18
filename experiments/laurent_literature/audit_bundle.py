"""Read-back verification of frozen numerical evidence, masks, and gate rows."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def read_rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def close(a,b):
    return np.isclose(float(a),float(b),rtol=1e-12,atol=1e-300)


def audit(path):
    path=Path(path)
    manifest=json.loads((path/'manifest.json').read_text())
    summary=json.loads((path/'summary.json').read_text())
    config=json.loads((path/'config.json').read_text())
    assert summary['status']=='COMPLETE' and not summary['source_drift']
    assert not (path/'failure.json').exists()
    for name,digest in json.loads((path/'artifact_hashes.json').read_text()).items():
        assert hashlib.sha256((path/name).read_bytes()).hexdigest()==digest, name
    for name,digest in manifest['source_hashes'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest, name
    ceilings=manifest['ceilings']
    assert summary['seconds']<=ceilings['seconds'] and summary['peak_gib']<=ceilings['peak_gib']
    for key in ('assemblies','factorizations'):
        assert summary['work'][key]<=ceilings[key]
    if (path/'transfer.csv').exists():
        rows=read_rows(path/'transfer.csv')
        derivatives=read_rows(path/'derivatives.csv')
        details=defaultdict(list)
        for row in derivatives:
            details[row['comparison_id']].append(row)
            assert close(row['absolute_error'],abs(float(row['candidate_value'])-float(row['reference_value'])))
            assert (row['passes']=='True')==(float(row['absolute_error'])<=float(row['allowed']))
        assert len({r['comparison_id'] for r in rows})==len(rows)
        assert set(details)=={r['comparison_id'] for r in rows}
        gates=config['gates']
        controls=read_rows(path/'controls.csv')
        qualified={(r['case'],r['cutoff']) for r in controls if r['qualified']=='True'}
        fd=read_rows(path/'finite_differences.csv')
        for row in fd:
            assert (row['passes']=='True')==(float(row['relative_error'])<1e-4)
        assert summary['finite_differences']==len(fd)
        assert summary['finite_difference_passed']==sum(r['passes']=='True' for r in fd)
        for row in rows:
            ds=sorted(details[row['comparison_id']],key=lambda x:int(x['direction_index']))
            assert [int(d['direction_index']) for d in ds]==list(range(6))
            assert [d['heldout']=='True' for d in ds]==[False]*4+[True]*2
            assert close(row['worst_training_derivative_error'],max(float(d['data_derivative_error']) for d in ds[:4]))
            assert close(row['worst_heldout_derivative_error'],max(float(d['data_derivative_error']) for d in ds[4:]))
            checks=dict(reference_qualified=(row['case'],row['cutoff']) in qualified,
                passes_receiver=float(row['data_error'])<=gates['receiver'],
                passes_residual=float(row['lifted_residual'])<=gates['lifted_residual'],
                passes_data_derivative=float(row['worst_training_derivative_error'])<=gates['data_derivative'],
                passes_heldout_derivative=float(row['worst_heldout_derivative_error'])<=gates['data_derivative'],
                objective_derivative_all_pass=all(d['passes']=='True' for d in ds))
            for key,value in checks.items():
                assert (row[key]=='True')==value,(row['comparison_id'],key)
            assert (row['passes_all']=='True')==all(checks.values())
            cutoff,n,mu=int(row['cutoff']),int(row['mask_n']),float(row['mu'])
            # Independently use the paper's double-kernel indices, reversing the
            # input sign only after building its index set.
            k=np.arange(-cutoff,cutoff+1)[:,None]
            l=k.T
            literal=(1+(k+l)**2)**mu*np.minimum(1+k*k,1+l*l)<=n*n
            mask=np.load(path/f"mask-{row['mask_sha256']}.npz")['mask']
            assert np.array_equal(mask,np.tile(literal[:,::-1],(2,2)))
            assert hashlib.sha256(mask.tobytes()).hexdigest()==row['mask_sha256']
            assert int(mask.sum())==int(row['retained'])
            assert mask.size==int(row['candidate'])
        assert summary['passed']==sum(r['passes_all']=='True' for r in rows)
        compact=[dict(comparison_id=r['comparison_id'],
                      retained_to_original=float(r['stored_slots'])/float(r['original_dense_slots']))
                 for r in rows if r['passes_all']=='True' and int(r['stored_slots'])<int(r['original_dense_slots'])]
        assert compact==summary['compact_passes']
        result=dict(comparisons=len(rows),derivative_rows=len(derivatives),
                    finite_differences=len(fd),controls=len(controls),compact_passes=len(compact))
    else:
        rows=read_rows(path/'convergence.csv')
        for row in rows:
            assert close(row['error_l2'],np.hypot(float(row['resolved_density_error']),float(row['tail_l2'])))
            n=int(row['n'])
            assert int(row['total'])==(2*n-1)**2
            assert close(row['retained_fraction'],int(row['retained'])/int(row['total']))
        counts=read_rows(path/'counts.csv')
        for row in counts:
            size=int(row['size'])
            assert close(row['cr'],int(row['retained'])/size**2)
            assert close(row['cc'],int(row['retained'])/size)
            assert close(row['published_identity_discrepancy'],float(row['published_cr'])*size-float(row['published_cc']))
        assert summary['operator_refinement']<=config['scalar_reference_relative_gate']
        assert summary['reference_qualified']
        result=dict(comparisons=len(rows),index_counts=len(counts))
    assert summary['comparisons']==len(rows)
    result.update(status='PASS',source_files=len(manifest['source_hashes']))
    (path/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('bundle')
    print(audit(parser.parse_args().bundle))
