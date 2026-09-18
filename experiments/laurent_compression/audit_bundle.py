"""Check that saved gates, per-direction evidence, masks and source hashes agree."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def audit(path):
    summary = json.loads((path / 'summary.json').read_text())
    config = json.loads((path / 'config.json').read_text())
    manifest = json.loads((path / 'manifest.json').read_text())
    assert summary['status'] == 'COMPLETE', summary['status']
    assert not summary['source_drift']
    for filename, digest in manifest['source_sha256'].items():
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == digest, filename
    def rows(name):
        return list(csv.DictReader((path / f'{name}.csv').open()))
    detail = defaultdict(list)
    for row in rows('derivatives'):
        detail[row['comparison_id']].append(row)
    checked, passed, seen, masks = 0, 0, set(), {}
    for table in ('compression', 'refinement', 'heldout'):
        for row in rows(table):
            if row.get('reason'):
                assert row['qualified'] == 'False'
                continue
            identifier = row['comparison_id']
            assert identifier not in seen
            seen.add(identifier)
            local = detail[identifier]
            assert sorted(int(d['direction_index']) for d in local) == list(range(6)), identifier
            for field in ('case', 'split', 'arm', 'cutoff', 'bandwidth', 'bessel_terms', 'mask_sha256'):
                assert all(d[field] == row[field] for d in local), (identifier, field)
            assert (row['objective_derivative_all_pass'] == 'True') == all(d['passes'] == 'True' for d in local)
            assert np.isclose(float(row['worst_data_derivative_error']),
                              max(float(d['data_derivative_error']) for d in local), rtol=1e-13, atol=0)
            errors = [('data_error', 'receiver', 'passes_receiver'),
                      ('lifted_residual', 'lifted_residual', 'passes_residual'),
                      ('worst_training_derivative_error', 'data_derivative', 'passes_data_derivative'),
                      ('worst_heldout_derivative_error', 'data_derivative', 'passes_heldout_derivative')]
            for field, gate, flag in errors:
                value = float(row[field])
                assert np.isfinite(value)
                assert (row[flag] == 'True') == (value <= config['gates'][gate]), (identifier, field)
            predicate = all(row[k] == 'True' for k in ['reference_qualified',
                            'objective_derivative_all_pass'] + [a[2] for a in errors])
            assert (row['passes_all'] == 'True') == predicate, identifier
            digest = row['mask_sha256']
            if digest not in masks:
                with np.load(path / 'masks' / f'{digest}.npz') as file:
                    mask = file['mask']
                assert hashlib.sha256(mask.tobytes()).hexdigest() == digest
                masks[digest] = (int(mask.sum()), mask.size)
            count, size = masks[digest]
            assert count == int(row['retained_count']) and size == int(row['candidate_count'])
            assert size == (2 * (2 * int(row['cutoff']) + 1))**2
            checked += 1
            passed += predicate
    assert set(detail) == seen, 'Orphaned per-direction measurements'
    work = summary['work']
    for key in ('assemblies', 'factorizations', 'rhs_batches'):
        assert work['counts'][key] <= work['ceilings'][key]
    assert work['numerical_wall_seconds'] <= work['ceilings']['seconds']
    assert work['peak_rss_gib'] <= work['ceilings']['peak_gib']
    return dict(passed=True, comparisons_checked=checked, numerical_gate_passes=passed,
                derivative_rows_checked=sum(map(len, detail.values())), distinct_masks=len(masks),
                source_files_checked=len(manifest['source_sha256']),
                note='Numerical gate passes do not establish storage, runtime, or inverse benefit.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    result = audit(args.bundle)
    (args.bundle / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
