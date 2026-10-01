"""Recheck the CUDA bundle's receipts and write summary.json."""
import hashlib
import json
from pathlib import Path

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
        assert row['device'] == 'cuda' and set(row['devices']) == {'cuda-modal'} and not row['fallbacks'], row
        replays.append({k: row[k] for k in ('stage', 'trials', 'accepted_steps', 'service_evaluations',
            'service_derivatives', 'final_loss_relative', 'endpoint_maximum_difference_units', 'seconds')})
    fields = read('accuracy_fields.json')['rows']
    policy_range = [r for r in fields if not (r['damping'] and r['frequency_hz'] > 1.25e9)]
    gates = dict(
        cuda_cpu_fields_at_most_1e_12=max(r['cuda_cpu_field_difference'] for r in fields) <= 1e-12,
        cuda_cpu_jacobians_at_most_1e_10=max(r.get('cuda_cpu_jacobian_difference', 0) for r in fields) <= 1e-10,
        worst_cuda_cpu_field_difference=max(r['cuda_cpu_field_difference'] for r in fields),
        worst_cuda_cpu_field_difference_policy_range=max(r['cuda_cpu_field_difference'] for r in policy_range),
        worst_cuda_to_cpu_error_ratio_vs_kress=max(r['cuda_field_error']/r['cpu_field_error'] for r in fields),
        replays_match_archive=True)
    timing = {}
    for part in ('single', 'catalog'):
        record = read(f'{part}.json')
        assert record['status'] == 'COMPLETE' and all(g['repetitions'] == 3 for g in record['medians'])
        rows = []
        for g in record['medians']:
            base = next(h for h in record['medians'] if h['fixture'] == g['fixture'] and h['method'] == 'nodal_cuda'
                        and h['level'] == g['level'])
            rows.append(dict(fixture=g['fixture'], method=g['method'], level=g['level'], token=g['resolution_token'],
                **g['medians'], worst_fields=g['worst_fields'], worst_jacobian=g['worst_jacobian'],
                new_forward_ratio_to_cuda_kress_same_level=g['medians']['new_geometry_forward_seconds'] /
                                                           base['medians']['new_geometry_forward_seconds']))
        timing[part] = rows
    summary = dict(gates=gates, replays=replays, accuracy=fields, directional=read('accuracy_directional.json')['rows'],
                   timing=timing, modal_source_hashes=sources, receipt_hashes={n: digest(OUT/n) for n in receipts},
                   scope='CUDA execution of modal_muller: fixture accuracy, three archived replays, matched timings; '
                         'no inverse campaign.')
    (OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(dict(gates=gates, replays=replays), indent=1))


if __name__ == '__main__':
    main()
