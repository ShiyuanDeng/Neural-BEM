"""Additional disjoint future Cartesian cohorts; original workers skip completed metrics."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
sys.path.insert(0, str(ROOT))
import run_topology_allocation_experiment as experiment
from sdf_inverse.experiment_record import source_provenance

COHORTS = ((.001, 29), (.001, 47), (.01, 11), (.01, 29), (.01, 47))


def run_cohort(cohort):
    magnitude, seed = cohort
    original = json.loads((OUTPUT / 'manifest.json').read_text())
    provenance = source_provenance(ROOT)
    assert provenance['source_sha256'] == original['source_provenance']['source_sha256']
    for chart, path in original['references'].items():
        experiment.REFERENCES[chart] = ROOT / path
    for arm in experiment.ARMS:
        path = OUTPUT / 'comparison/cartesian' / arm / f'm{magnitude:g}-s{seed}'
        if path.exists():
            print(f'SKIP already owned: {path}', flush=True)
            continue
        experiment.run_replay(OUTPUT, 'cartesian', arm, magnitude, seed, provenance=provenance)


if __name__ == '__main__':
    # These cohorts are deliberately ahead of the original Cartesian worker,
    # which is still processing magnitude 1e-4. No cohort is duplicated.
    for magnitude, seed in COHORTS:
        for arm in experiment.ARMS:
            assert not (OUTPUT / 'comparison/cartesian' / arm / f'm{magnitude:g}-s{seed}').exists()
    launch = dict(created_utc=datetime.now(timezone.utc).isoformat(), workers=5, cohorts=COHORTS,
        maximum_combined_processes=8, primary_scheduling='original two workers skip completed cohorts',
        launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), wall_time_comparison=False)
    (OUTPUT / 'additional_shards.json').write_text(json.dumps(launch, indent=2) + '\n')
    with ProcessPoolExecutor(max_workers=5) as pool:
        list(pool.map(run_cohort, COHORTS))
