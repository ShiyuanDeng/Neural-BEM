"""Read and hash saved full runs; no physical solves or new inverse runs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from .gate import training_readiness

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT/'results/validation/topology/TOP-025-20260915-210356-all-scenes-current'


def audit(destination):
    consumed = {}
    archive_hashes = json.loads((HISTORY/'artifact_manifest.json').read_text())

    def read(path):
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        relative = str(path.relative_to(HISTORY))
        if relative in archive_hashes and digest != archive_hashes[relative]:
            raise ValueError('Historical artifact hash mismatch: '+relative)
        consumed[str(path.relative_to(ROOT))] = digest
        return json.loads(raw)

    def values(record):
        return np.array(record['real'])+1j*np.array(record['imag'])

    rows = []
    for scene in read(HISTORY/'scene_spec.json')['scenes']:
        name = scene['id']
        folder = HISTORY/'runs'/name
        full = read(folder/'result.json')
        row = dict(scene=name, final_recovered=full['fresh_recovery_pass'],
                   final_status=full['status'], available=False, ready=None)
        terminal_path = folder/'topology/terminal.json'
        if terminal_path.exists():
            terminal = read(terminal_path)
            row['topology_stages'] = terminal.get('controller_work', {}).get('stages', {})
            modes = [c['maximum_mode'] for c in terminal.get('final_state') or []]
            row['topology_modes'] = modes
            row['topology_directions'] = sum(3 if k <= 2 else 2*k-1 for k in modes)
        path = folder/'F/initial_endpoint_predictions.json'
        if path.exists():
            endpoint = read(path)
            observation = read(HISTORY/'inputs'/name/'training_observations.json')
            observed = np.array(observation['observed_real'])+1j*np.array(observation['observed_imag'])
            low, high = (values(endpoint['predictions'][str(n)])[:, :4] for n in (256, 512))
            gate = training_readiness(observed, low, high)
            # Assessment is deliberately read AFTER the training-only decision.
            score = endpoint['score']
            row.update(available=True, ready=gate['ready'], gate=gate,
                independent_handoff_pass=bool(score['original_gates_pass'] and score['numerically_qualified']),
                handoff_gates=score['gates'], handoff_boundary_m=score['geometry']['maximum_matched_hausdorff_m'],
                handoff_evaluation_max=score['maximum_evaluation_error'],
                looser_003_fit_only=bool(max(*gate['production_errors'], *gate['refined_errors']) <= .003))
            metrics = read(folder/'F/metrics.json')
            row['continuation_seconds_historical'] = metrics['work']['active_wall_seconds']
            row['accepted_steps'] = [r['terminal']['accepted_steps'] for r in metrics['stages']]
            handoff = read(folder/'handoff.json')
            row['padded_directions'] = handoff['capacity']['reduced_directions'] if 'capacity' in handoff else full['capacity']['reduced_directions']
        rows.append(row)
    report = dict(rows=rows, consumed_sha256=consumed, physical_solves=0,
                  status='PASS' if all(not r.get('ready') or r['independent_handoff_pass'] for r in rows) else 'FALSE_EARLY_STOP',
                  scope='retrospective development audit; no timing extrapolation')
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    fields = ['scene','available','ready','independent_handoff_pass','final_recovered',
              'topology_directions','padded_directions','accepted_steps','handoff_boundary_m',
              'handoff_evaluation_max','continuation_seconds_historical']
    with (destination/'audit.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('destination', type=Path)
    report = audit(parser.parse_args().destination)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','consumed_sha256')}))
    for row in report['rows']:
        print(row['scene'], 'ready=',row['ready'], 'independent=',row.get('independent_handoff_pass'),
              'steps=',row.get('accepted_steps'), 'dimensions=',row.get('topology_directions'),row.get('padded_directions'))
