"""A/E full Cartesian controller qualification, with evaluation-only holdout."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from types import SimpleNamespace

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import run_fourier_topology_controller as driver
import run_radial_fourier_topology_inverse as baseline
from ordered_boundary import OrderedBoundary2D
from sdf_bem_multicomponent import predict_multicomponent_kress_paired_boundary_response
from sdf_inverse import ComplexScatteredData
from sdf_inverse.experiment_record import source_provenance
from sdf_inverse.work_accounting import accounted_call, collect_work


def run_pair(case):
    started = perf_counter()
    _, truth, circles = driver.case_spec(case, chart='cartesian')
    frequencies = np.array([1.5e9, 2.5e9])
    problem = baseline._problem(frequencies)
    solve = baseline.iteration01_solve_config()
    if circles is None:
        observed = predict_multicomponent_kress_paired_boundary_response(
            OrderedBoundary2D(tuple(c.discretize(256) for c in truth)), problem, solve_config=solve).scattered_response
        oracle = 'analytic truth at 256 Kress nodes; independent mesh, same solver'
    else:
        observed = baseline._oracle_response(np.array([c.center for c in circles]),
            np.array([c.mean_radius_m for c in circles]), frequencies,
            component_ids=tuple(c.component_id for c in circles))
        oracle = 'independent cylindrical harmonics'
    data = ComplexScatteredData(problem, observed)
    results = {}
    for arm, count, steps in [('A', 1, 3), ('E', 3, 1)]:
        if perf_counter() - started > 3600:
            raise TimeoutError('Controller qualification wall ceiling')
        args = SimpleNamespace(chart='cartesian', profile='full', demonstration='original', skip_video=True,
            candidates_refined_per_group=count, candidate_refinement_iterations=steps)
        metric = driver.run_case(case, OUTPUT / arm, args)
        state = driver.deserialize_state(metric['final_state'])
        with collect_work() as audit:
            loss, relative = accounted_call('holdout', driver.topology_objective, state, data,
                                            baseline._geometry_config(128), solve)
        supplement = dict(holdout_relative_error=relative, holdout_loss=loss, oracle=oracle,
                          holdout_work=audit.snapshot(), truth_component_count=len(truth))
        driver.write_json(OUTPUT / arm / case / 'holdout.json', supplement)
        driver.write_json(OUTPUT / arm / case / 'holdout_observations.json',
            dict(problem=asdict(problem), observed_real=observed.real, observed_imag=observed.imag))
        results[arm] = dict(**metric, **supplement)
    a, e = results['A'], results['E']
    gates = dict(recovered=all(r['stop_reason'] == 'recovered' for r in results.values()),
        correct_count=all(len(r['final_state']) == len(truth) for r in results.values()),
        geometry=e['hausdorff_m'] <= max(1.1*a['hausdorff_m'], 1e-6),
        training=e['final_relative_error'] <= max(1.1*a['final_relative_error'], 1e-6),
        holdout=e['holdout_relative_error'] <= max(1.1*a['holdout_relative_error'], 1e-5))
    result = dict(case=case, arms=results, gates=gates, passed=all(gates.values()))
    driver.write_json(OUTPUT / f'{case}_comparison.json', result)
    print(json.dumps(dict(case=case, gates=gates,
        costs={arm: result['work']['totals']['bie_frequency_solve_count'] for arm, result in results.items()})), flush=True)
    return result


if __name__ == '__main__':
    provenance = source_provenance(ROOT)
    declared = json.loads((ROOT / 'results/validation/topology/TOP-001-20260911-comparison/manifest.json').read_text())
    assert provenance['source_sha256'] == declared['source_provenance']['source_sha256']
    driver.write_json(OUTPUT / 'manifest.json', dict(experiment='TOP-001E controller qualification',
        created_utc=datetime.now(timezone.utc).isoformat(), source_provenance=provenance,
        launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), workers=3,
        concurrency='three single-thread case-pair processes; may overlap split replays',
        cases=driver.CASES, maximum_full_inversions=10, maximum_seconds=3600))
    with ProcessPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(run_pair, driver.CASES))
    costs = {arm: sum(row['arms'][arm]['work']['totals']['bie_frequency_solve_count'] for row in rows) for arm in ('A','E')}
    driver.write_json(OUTPUT / 'qualification.json', dict(cases=rows, all_quality_gates=all(r['passed'] for r in rows),
        total_bie_solves=costs, aggregate_cost_gate=costs['E'] <= costs['A']))
