"""Independently observe actual complex batched linear solves for one replay."""
from collections import Counter
from pathlib import Path
import sys
from unittest.mock import patch
import hashlib

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import run_topology_allocation_experiment as experiment
from sdf_inverse.work_accounting import _stage
from sdf_inverse.experiment_record import source_provenance

if __name__ == '__main__':
    experiment.REFERENCES['cartesian'] = ROOT / 'results/validation/topology/TOP-001-20260911-B0-qualification/cartesian/split'
    state, config, data, _, _ = experiment.load_reference('cartesian')
    counts, dimensions = Counter(), Counter()
    original = np.linalg.solve
    def observe(matrix, rhs):
        value = original(matrix, rhs)
        if np.iscomplexobj(matrix) and np.ndim(rhs) == 2:
            counts[_stage.get()] += 1
            dimensions[(matrix.shape[0], rhs.shape[1])] += 1
        return value
    with patch('numpy.linalg.solve', observe):
        result = experiment.run_topology_aware_fourier_inverse(state, data,
            experiment.baseline._geometry_config(64), experiment.baseline._geometry_config(128),
            solve_config=experiment.baseline.iteration01_solve_config(), config=config, replay_first_event=True)
    declared = {stage: row.get('forward_frequency_solve_count', 0) + row.get('td_frequency_solve_count', 0)
                for stage, row in result.work['stages'].items()}
    payload = dict(passed=dict(counts) == declared,
        observed_batched_complex_solves=dict(counts), reported_bie_solves=declared,
        total_observed=sum(counts.values()), total_reported=result.work['totals']['bie_frequency_solve_count'],
        dimensions={f'{nodes} unknowns / {rhs} RHS': count for (nodes,rhs),count in dimensions.items()},
        scope='Unperturbed Cartesian A replay; observer does not alter solves or policy',
        provenance=source_provenance(ROOT), launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    experiment.write_json(OUT / 'verification.json', payload)
    print(payload['passed'], payload['total_observed'], payload['total_reported'], flush=True)
    raise SystemExit(0 if payload['passed'] else 1)
