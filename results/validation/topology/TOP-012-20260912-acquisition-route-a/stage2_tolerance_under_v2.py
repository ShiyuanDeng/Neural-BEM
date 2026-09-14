"""TOP-012 stage 2: does the enriched acquisition shrink what the tolerance hides?

This is the cheap half of the falsifiable hypothesis, and it runs before the
twelve-scene suite so that an expensive comparison is never bought to answer a
question a cheap one already settles.

[TOP-011](../TOP-011-20260912-tolerance-sensitivity/README.md) measured, at the
saved K=9 state and per singular direction, how far the boundary may move while
the *measured* relative L2 stays inside the frozen 0.003 tolerance. It found
47 of 68 directions permitting more movement than the 1 mm boundary gate.

Route A doubles the ring to 48 source/receiver pairs at the same 0.5 GHz
training frequency, strictly interleaving the frozen 24 -- so v1's angular
coverage is a subset of v2's, the 1.5 and 2.5 GHz holdout is untouched, and the
only difference is added coverage. Repeating TOP-011's measurement on the same
state under v2 data answers two things at once:

1. Does the v1-fitted state still satisfy the 0.003 tolerance on the richer
   data at all? It was never fitted to the 24 interleaved positions.
2. If it does, does the permitted boundary movement shrink?

The same procedure, the same tolerance, the same state, the same feasible set.
Acquisition is the only difference.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SENSITIVITY = ROOT / 'results/validation/topology/TOP-011-20260912-tolerance-sensitivity'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))
sys.path.insert(0, str(SENSITIVITY))

import tolerance_sensitivity as sensitivity  # noqa: E402  the TOP-011 experiment, unmodified
import run_topology_scene_benchmark as benchmark  # noqa: E402
import run_fourier_topology_controller as driver  # noqa: E402
from sdf_inverse.topology_controller import TopologyControllerConfig  # noqa: E402

SUITE = HERE / 'suite'
V1_DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
PLATEAU = (ROOT / 'results/validation/topology/TOP-010-20260912-stopping-vs-stationarity'
           / 'stageB_restart_continuation.json')
SCENE = 'far-two-stars'
# Declared before execution. One state, one acquisition, same shape of work as
# TOP-011 spent on two states.
SOLVE_CAP = 800
SECONDS_CEILING = 500.0


def audit(label, spec, data_bundle, ledger):
    scene = {s['id']: s for s in spec['scenes']}[SCENE]
    training, _ = benchmark.shared_data(data_bundle, scene, spec)
    state = driver.deserialize_state(benchmark.read(PLATEAU)['final_state'])
    config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True,
                                      feasible_fd_jacobian=True, bandwidth_promotion=True)
    record = sensitivity.Audit(
        label, state, scene, spec, training,
        driver.baseline.iteration01_solve_config(),
        driver.baseline._geometry_config(spec['production_nodes']),
        driver.baseline._geometry_config(spec['refined_nodes']),
        config, ledger).run()
    record['spec_version'] = spec['version']
    record['acquisition'] = spec.get('acquisition')
    record['observations'] = int(len(training.forward_problem.source_points))
    return record


def main():
    v2 = benchmark.read(SUITE / 'scene_spec.json')
    if v2['controller']['relative_error_tolerance'] != sensitivity.DATA_TOLERANCE:
        raise ValueError('v2 must keep the frozen 0.003 tolerance; no gate is re-tuned here')
    v1 = benchmark.read(V1_DATA / 'scene_spec.json')
    if {k: value for k, value in v2.items() if k not in ('version', 'acquisition')} != \
            {k: value for k, value in v1.items() if k != 'version'}:
        raise ValueError('v2 must differ from v1 in acquisition alone')

    ledger = sensitivity.Ledger(SOLVE_CAP, SECONDS_CEILING)
    print('########## enriched acquisition, same state, same tolerance ##########', flush=True)
    enriched = audit('stageB_restart_plateau_under_v2', v2, SUITE, ledger)

    # The v1 reading of this same state is already recorded; quote it rather
    # than re-running it, so nothing about v1 is recomputed here.
    baseline = next(s for s in benchmark.read(SENSITIVITY / 'tolerance_sensitivity.json')['states']
                    if s['state'] == 'stageB_restart_plateau')
    comparison = dict(
        state='stageB_restart_plateau', scene=SCENE, data_tolerance=sensitivity.DATA_TOLERANCE,
        v1=dict(spec_version=v1['version'], observations=24,
                relative_l2_error=baseline['relative_l2_error'],
                inside_tolerance=baseline['relative_l2_error'] <= sensitivity.DATA_TOLERANCE,
                residual_entries=baseline['residual_entries'],
                summary=baseline['summary'], linear_model=baseline['linear_model_summary'],
                spectrum=dict(maximum=baseline['spectra'][0]['singular_value_max'],
                              minimum=baseline['spectra'][0]['singular_value_min'],
                              condition_number=baseline['spectra'][0]['condition_number'],
                              rank=baseline['spectra'][0]['numerical_rank'])),
        v2=dict(spec_version=v2['version'], observations=enriched['observations'],
                relative_l2_error=enriched['relative_l2_error'],
                inside_tolerance=enriched['relative_l2_error'] <= sensitivity.DATA_TOLERANCE,
                residual_entries=enriched.get('residual_entries'),
                summary=enriched.get('summary'), linear_model=enriched.get('linear_model_summary'),
                spectrum=dict(maximum=enriched['spectra'][0]['singular_value_max'],
                              minimum=enriched['spectra'][0]['singular_value_min'],
                              condition_number=enriched['spectra'][0]['condition_number'],
                              rank=enriched['spectra'][0]['numerical_rank'])
                if 'spectra' in enriched else None))
    for name in ('maximum_permitted_displacement_mm', 'median_permitted_displacement_mm',
                 'median_weak_half_displacement_mm', 'median_strong_half_displacement_mm',
                 'directions_permitting_more_than_the_gate'):
        before = comparison['v1']['summary'].get(name)
        after = (comparison['v2']['summary'] or {}).get(name)
        comparison.setdefault('change', {})[name] = dict(
            v1=before, v2=after,
            ratio=(after / before) if before not in (None, 0) and after is not None else None)

    driver.write_json(HERE / 'stage2_tolerance_under_v2.json', dict(
        solve_cap=SOLVE_CAP, seconds_ceiling=SECONDS_CEILING, solves_used=ledger.total,
        work=dict(ledger.counts), geometry_checks=ledger.geometry_checks,
        seconds=ledger.elapsed, within_solve_cap=ledger.total <= SOLVE_CAP,
        comparison=comparison, enriched=enriched))

    print('\n=== stage 2: what the tolerance hides, v1 versus v2 ===')
    print(f"  observations {comparison['v1']['observations']} -> {comparison['v2']['observations']}"
          f"  ·  residual entries {comparison['v1']['residual_entries']} -> "
          f"{comparison['v2']['residual_entries']}")
    print(f"  the v1-fitted state on v2 data: relative L2 "
          f"{comparison['v1']['relative_l2_error']:.4e} -> "
          f"{comparison['v2']['relative_l2_error']:.4e}, still inside the 0.003 tolerance: "
          f"{comparison['v2']['inside_tolerance']}")
    for name, row in comparison['change'].items():
        ratio = 'n/a' if row['ratio'] is None else f"{row['ratio']:.3f}x"
        print(f"  {name}: {row['v1']} -> {row['v2']}  ({ratio})")


if __name__ == '__main__':
    main()
