"""Exploratory TOP-001E: three raw candidates, one LM iteration each."""
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
sys.path.insert(0, str(ROOT))
import run_topology_allocation_experiment as experiment
from sdf_inverse.experiment_record import source_provenance

if __name__ == '__main__':
    reference = ROOT / 'results/validation/topology/TOP-001-20260911-comparison'
    original = json.loads((reference / 'manifest.json').read_text())
    provenance = source_provenance(ROOT)
    assert provenance['source_sha256'] == original['source_provenance']['source_sha256']
    for chart, path in original['references'].items():
        experiment.REFERENCES[chart] = ROOT / path
    experiment.ARMS = {'E': (3, 1)}
    experiment.write_json(OUTPUT / 'manifest.json', dict(experiment_id='TOP-001E',
        role='exploratory follow-up; declared after unperturbed A/B/C',
        arm=experiment.ARMS, source_provenance=provenance, baseline_comparison=str(reference.relative_to(ROOT)),
        launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        maximum_replays=20, maximum_seconds=3600, concurrency='one E process; may overlap two A/B/C processes'))
    started = perf_counter()
    rows = []
    for chart in ('cartesian', 'radial'):
        for magnitude in experiment.MAGNITUDES:
            for seed in (experiment.SEEDS[0],) if magnitude == 0 else experiment.SEEDS:
                if perf_counter() - started > 3600:
                    raise TimeoutError('Expanded-shortlist diagnostic wall ceiling reached')
                metric = experiment.run_replay(OUTPUT, chart, 'E', magnitude, seed, provenance=provenance)
                rows.append(metric)
                experiment.write_json(OUTPUT / 'metrics.json', rows)
                if chart == 'cartesian' and magnitude == 0:
                    control = json.loads((reference / 'comparison/cartesian/A/m0-s0/metrics.json').read_text())
                    passed = metric['hausdorff_m'] < control['hausdorff_m'] and metric['holdout_relative_error'] < control['holdout_relative_error']
                    experiment.write_json(OUTPUT / 'qualification.json', dict(passed=passed,
                        geometry_ratio=metric['hausdorff_m']/control['hausdorff_m'],
                        holdout_ratio=metric['holdout_relative_error']/control['holdout_relative_error']))
                    if not passed:
                        raise SystemExit(2)
