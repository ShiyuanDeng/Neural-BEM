"""Recorded TOP-001 launch: two processes, one serial arm sequence per chart."""
from concurrent.futures import ProcessPoolExecutor
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


def run_chart(chart):
    saved = json.loads((OUTPUT / 'manifest.json').read_text())
    for name, path in saved['references'].items():
        experiment.REFERENCES[name] = ROOT / path
    provenance = source_provenance(ROOT)
    assert provenance['source_sha256'] == saved['source_provenance']['source_sha256']
    started = perf_counter()
    for magnitude in experiment.MAGNITUDES:
        for seed in (experiment.SEEDS[0],) if magnitude == 0 else experiment.SEEDS:
            for arm in experiment.ARMS:
                if perf_counter() - started > 7200:
                    raise TimeoutError('Declared two-hour ceiling reached.')
                path = OUTPUT / 'comparison' / chart / arm / f'm{magnitude:g}-s{seed if magnitude else 0}' / 'metrics.json'
                if path.exists():
                    continue
                experiment.run_replay(OUTPUT, chart, arm, magnitude, seed, provenance=provenance)
    return chart


if __name__ == '__main__':
    for chart in experiment.REFERENCES:
        qualification = json.loads((OUTPUT / 'historical' / chart / 'A/m0-s0/metrics.json').read_text())
        assert qualification['historical_event_match']
    launch = dict(workers=2, scheduling='one serial replay sequence per chart',
                  launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  wall_time_comparison=False, maximum_seconds_per_process=7200)
    (OUTPUT / 'execution.json').write_text(json.dumps(launch, indent=2) + '\n')
    with ProcessPoolExecutor(max_workers=2) as pool:
        list(pool.map(run_chart, ('radial', 'cartesian')))
    experiment.write_summary(OUTPUT)
