"""Provenance for the TOP-011 bundle, written after the run."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_fourier_topology_controller as driver
from sdf_inverse.experiment_record import source_provenance

driver.write_json(HERE / 'manifest.json', dict(
    experiment_id='TOP-011',
    source=source_provenance(ROOT),
    data_bundle='results/validation/topology/TOP-008-20260912-feasible-fd',
    state_sources=[
        'results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage4_uncapped_ladder.json',
        'results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/'
        'stageB_restart_continuation.json'],
    stages_executed=['tolerance_sensitivity'],
    source_change_required='none; diagnostic only, unmodified objective and feasible set',
    declared_budget=dict(forward_frequency_solves=1200, seconds=600.0),
    scene='far-two-stars', data_tolerance=0.003,
    controller_default_changed=False, benchmark_changed=False, new_arm=False,
    state_advanced_or_saved_as_reconstruction=False))
print('manifest written')
