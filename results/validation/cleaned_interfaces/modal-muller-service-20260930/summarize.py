"""Recheck every receipt in this bundle and write summary.json."""
import hashlib
import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent


def read(name):
    return json.loads((OUT/name).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    sources = {str(p): digest(p) for p in sorted(Path('experiments/cleaned_interface').glob('modal_*.py'))}
    receipts = [p.name for p in sorted(OUT.glob('*.json')) if p.name != 'summary.json']
    for name in receipts:
        for path, value in read(name).get('source_hashes', {}).items():
            if path.startswith('experiments/cleaned_interface/modal_'):
                assert sources[path] == value, (name, path)
    replays = []
    for stage in ('stage_2_damped', 'release_M11', 'fixed_M43'):
        row = read(f'replay_{stage}.json')['comparison']
        assert row['trials_equal'] and row['accepted_indices_equal'] and row['same_exit'] and row['stage_work_equal'], row
        replays.append({k: row[k] for k in ('stage', 'trials', 'accepted_steps', 'service_evaluations', 'service_derivatives',
            'final_loss_relative', 'endpoint_maximum_difference_units', 'endpoint_maximum_difference_metres', 'resolution')})
    accuracy = {}
    for part in ('c', 'endpoint', 'damped', 'directional'):
        rows = read(f'accuracy_{part}.json')['rows']
        accuracy[part] = [{k: r.get(k) for k in ('frequency_hz', 'damping', 'shape', 'step_m', 'K', 'M', 'K_trace', 'window',
                           'field_error', 'jacobian_error', 'worst_column', 'relative_error', 'oracle_1024_2048',
                           'review_prototype') if k in r} for r in rows]
    timing = {}
    for part in ('single', 'catalog'):
        if not (OUT/f'{part}.json').exists():
            continue
        record = read(f'{part}.json')
        assert record['status'] == 'COMPLETE'
        groups = record['medians']
        assert all(g['repetitions'] == 3 for g in groups)
        rows = []
        for g in groups:
            base = next(h for h in groups if h['fixture'] == g['fixture'] and h['method'] == 'nodal_cuda' and h['level'] == 'production')
            proto = next((h for h in groups if h['fixture'] == g['fixture'] and h['method'] == 'modal_prototype'
                          and h['level'] == g['level']), None)
            m = g['medians']
            rows.append(dict(fixture=g['fixture'], method=g['method'], level=g['level'], token=g['resolution_token'],
                **m, worst_fields=g['worst_fields'], worst_jacobian=g['worst_jacobian'],
                new_forward_ratio_to_cuda_kress_512=m['new_geometry_forward_seconds']/base['medians']['new_geometry_forward_seconds'],
                prototype_new_forward_speedup=(proto['medians']['new_geometry_forward_seconds']/m['new_geometry_forward_seconds']
                                               if g['method'].startswith('modal_service') else None)))
        timing[part] = rows
    summary = dict(replays_match_archive=True, replays=replays, accuracy=accuracy, timing=timing,
                   modal_source_hashes=sources, receipt_hashes={n: digest(OUT/n) for n in receipts},
                   scope='Fixture accuracy, three archived stage replays and matched timings; no 36-case campaign.')
    (OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(dict(replays=replays, timing=timing), indent=1, default=str)[:6000])


if __name__ == '__main__':
    main()
