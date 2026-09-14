"""Provenance for the TOP-012 bundle, written after the runs."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_fourier_topology_controller as driver
import run_topology_scene_benchmark as benchmark
from sdf_inverse.experiment_record import source_provenance

suite = HERE / 'suite'
spec = benchmark.read(suite / 'scene_spec.json')
v1 = benchmark.read(ROOT / 'config/topology_scenes_v1.json')

driver.write_json(HERE / 'manifest.json', dict(
    experiment_id='TOP-012',
    route='A — more spatial diversity at the existing 0.5 GHz training frequency',
    source=source_provenance(ROOT),
    benchmark_version=spec['version'],
    acquisition=spec['acquisition'],
    v1_acquisition=dict(ring_positions=24, standoff_m=0.30),
    holdout_frequencies_hz=spec['holdout_frequencies_hz'],
    holdout_untouched=spec['holdout_frequencies_hz'] == v1['holdout_frequencies_hz'],
    differs_from_v1_only_in=sorted(k for k in set(spec) | set(v1)
                                   if spec.get(k) != v1.get(k)),
    v1_specification_sha256=benchmark.digest(ROOT / 'config/topology_scenes_v1.json'),
    v2_specification_sha256=benchmark.digest(suite / 'scene_spec.json'),
    arm='H',
    v1_comparison_bundle='results/validation/topology/TOP-008-20260912-feasible-fd',
    v1_bundle_rerun=False, v1_bundle_rescored=False, gates_retuned=False,
    data_tolerance=spec['controller']['relative_error_tolerance'],
    stages_executed=['stage1_prepare', 'stage2_tolerance_under_v2', 'stage3_suite',
                     'stage4_compare'],
    declared_budget=dict(
        stage2=dict(forward_frequency_solves=800, seconds=500.0),
        stage3=dict(workers=4, per_scene_timeout_seconds=600,
                    suite_wall_ceiling_seconds=2700)),
    source_change=('run_radial_fourier_topology_inverse._ring_scan gained '
                   'positions/standoff arguments defaulting to the frozen v1 '
                   'acquisition, and the benchmark threads a specification\'s '
                   'optional acquisition block through oracle generation and '
                   'data loading. A specification without the block reproduces '
                   'v1 exactly.')))
print('manifest written')
