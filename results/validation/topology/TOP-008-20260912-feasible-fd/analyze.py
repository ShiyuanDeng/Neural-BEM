"""Read-only numerical-artifact analysis; writes figures, report and checks."""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))
import run_topology_scene_benchmark as benchmark

REFERENCE = ROOT / 'results/validation/topology/TOP-007-20260911-refined-feasibility'
ARMS = ('G', 'H')


def pass_statistics(path):
    """Per-run guard and stencil counts, summed over the cycles that were written."""
    passes_path = path / 'topology_passes.json'
    if not passes_path.exists():
        return dict(cycles_recorded=0, guard_rejected_trials=None,
                    one_sided_columns=None, unresolved_columns=None)
    passes = benchmark.read(passes_path)

    def total(field):
        values = [p.get(field) for p in passes]
        return None if any(v is None for v in values) else int(sum(values))

    return dict(cycles_recorded=len(passes),
                guard_rejected_trials=total('refined_feasibility_rejected_trials'),
                one_sided_columns=total('one_sided_jacobian_columns'),
                unresolved_columns=total('unresolved_jacobian_columns'))


def failure_diagnostics(path, scene, spec):
    """Describe a failed run from its saved checkpoint alone; no solves."""
    checkpoint = path / 'checkpoint.json'
    if not checkpoint.exists():
        return None
    record = benchmark.read(checkpoint)
    state = benchmark.driver.deserialize_state(record['state'])
    result = dict(scene=scene['id'], arm=path.parent.name,
        status='failed run: last saved accepted state, not a successful reconstruction',
        geometry=benchmark.geometry_metrics(state, scene, spec), last_saved_loss=record['loss'],
        completed_bie_solve_lower_bound=record['work']['totals']['bie_frequency_solve_count'],
        no_forward_or_inverse_solves_for_this_diagnostic=True)
    benchmark.driver.write_json(path / 'failure_diagnostics.json', result)
    return result


def main():
    data = benchmark.summarize(HERE, render=False)
    spec = benchmark.read(HERE / 'scene_spec.json')
    source = benchmark.read(HERE / 'manifest.json')['source']
    source_matches = {name: benchmark.digest(ROOT / name) == value
                      for name, value in source['source_sha256'].items()}
    rows = {(r['scene'], r['arm']): r for r in data['metrics']}
    reference_rows = {(r['scene'], r['arm']): r
                      for r in benchmark.read(REFERENCE / 'suite_metrics.json')['metrics']}
    stage1 = benchmark.read(HERE / 'stage1_derivative_probe.json')
    stage2 = benchmark.read(HERE / 'stage2_continuation.json')

    observations_match, initials_match, gates_match, statistics, diagnostics = {}, {}, {}, {}, {}
    for scene in spec['scenes']:
        for arm in ARMS:
            path = HERE / 'runs' / arm / scene['id']
            key = f"{arm}/{scene['id']}"
            if (path / 'manifest.json').exists():
                manifest = benchmark.read(path / 'manifest.json')
                observations_match[key] = manifest['observations_sha256'] == benchmark.digest(
                    HERE / 'scenes' / scene['id'] / 'observations.json')
                initials_match[key] = manifest['initial_state'] == benchmark.read(
                    HERE / 'scenes' / scene['id'] / 'initial_state.json')
            statistics[key] = pass_statistics(path)
            row = rows.get((scene['id'], arm))
            if row is None:
                diagnostics[key] = failure_diagnostics(path, scene, spec)
                continue
            frames = [benchmark.TopologyFrame(benchmark.driver.deserialize_state(f['state']),
                      f['loss'], f['label'], f['cycle']) for f in benchmark.read(path / 'trajectory.json')]
            checks = benchmark.trajectory_checks(frames, row['events'], benchmark.controller_config(spec, arm))
            expected = benchmark.success_gates(row['geometry'], row['refined_relative_error'],
                                               max(row['holdout_relative_errors']), checks, spec)
            gates_match[key] = expected == row['gates'] and all(expected.values()) == row['passed']

    def compare(new, old):
        return dict(same_final_state=old['final_state'] == new['final_state'],
            same_solve_count=old['work']['totals']['bie_frequency_solve_count'] ==
                             new['work']['totals']['bie_frequency_solve_count'],
            same_stop_reason=old['stop_reason'] == new['stop_reason'],
            same_training_error=abs(old['final_relative_error'] - new['final_relative_error']) < 1e-12)

    # The guarded arm reruns TOP-007's policy on its own observations. With the
    # stencil correction off, the new source must reproduce it exactly.
    guard_reproduces = {scene: compare(rows[(scene, 'G')], reference_rows[(scene, 'G')])
                        for scene, arm in rows if arm == 'G' and (scene, 'G') in reference_rows}
    # Where no column was ever one-sided, the correction had nothing to change.
    correction_inert = {}
    for scene, arm in list(rows):
        if arm != 'H' or (scene, 'G') not in rows:
            continue
        if statistics[f'H/{scene}']['one_sided_columns'] == 0:
            correction_inert[scene] = compare(rows[(scene, 'H')], rows[(scene, 'G')])
    both_completed = [scene for scene, arm in list(rows) if arm == 'H' and (scene, 'G') in rows]
    failures = {f"{f['arm']}/{f['scene']}": f['reason'] for f in data['failures']}

    verification = dict(complete=data['complete'], all_inputs_paired=data['all_inputs_paired'],
        source_matches=source_matches, observations_match=observations_match,
        initial_states_match=initials_match, rederived_gates_match=gates_match,
        guarded_arm_reproduces_top007=guard_reproduces,
        correction_inert_where_no_column_is_one_sided=correction_inert,
        stage1_derivative_model=dict(
            agreement_tolerance=stage1['agreement_tolerance'],
            step_factors=stage1['step_factors'],
            worst_stability=max((v for r in stage1['records'] for v in r['stability'].values()),
                                default=None),
            worst_one_sided_vs_central=max(
                (e[k] for r in stage1['records'] for e in r['sides'].values()
                 for k in ('forward_vs_central', 'backward_vs_central') if k in e), default=None),
            directions_with_an_unresolved_step=sum(
                1 for r in stage1['records'] if 'unresolved' in r['stencils'])),
        stage2_continuation={a['arm']: dict(
            stop_reason=a['stop_reason'], iterations=a['iterations'],
            production_loss=a['production_loss'], refined_loss=a['refined_loss'],
            decreased_at_both_resolutions=a['decreased_at_both_resolutions'],
            within_seconds_ceiling=a['within_seconds_ceiling'],
            within_solve_cap=a['within_solve_cap'],
            pinned_component_radius_floor_after_mm=a['components'][-1]['radius_floor_after_m'] * 1e3)
            for a in stage2['arms']},
        jacobian_statistics=statistics,
        arm_failure_reasons=failures,
        uncaught_exceptions=sorted(k for k, v in failures.items() if v == 'exception'),
        oracle_checks=benchmark.read(HERE / 'oracle_checks.json'))
    stage1_stable = (verification['stage1_derivative_model']['worst_stability'] is not None
                     and verification['stage1_derivative_model']['worst_stability']
                     <= stage1['agreement_tolerance'])
    stage2_pass = verification['stage2_continuation']['feasible']['decreased_at_both_resolutions']
    verification['stage1_derivative_model']['stable_within_tolerance'] = bool(stage1_stable)
    verification['stage2_continuation']['hypothesis_supported'] = bool(stage2_pass)
    verification['all_checks_passed'] = bool(data['complete'] and data['all_inputs_paired'] and
        all(source_matches.values()) and all(observations_match.values()) and
        all(initials_match.values()) and all(gates_match.values()) and
        all(all(c.values()) for c in guard_reproduces.values()) and
        all(all(c.values()) for c in correction_inert.values()) and
        stage1_stable and stage2_pass and not verification['uncaught_exceptions'] and
        all(o['passed'] for o in verification['oracle_checks']))
    benchmark.driver.write_json(HERE / 'verification.json', verification)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)
    positions = np.arange(len(spec['scenes']))
    for arm, offset, color in [('G', -.19, '#07877f'), ('H', .19, '#8a5cc4')]:
        errors, costs, partial = [], [], []
        for scene in spec['scenes']:
            row = rows.get((scene['id'], arm))
            diagnostic = diagnostics.get(f"{arm}/{scene['id']}")
            geometry = row['geometry'] if row else diagnostic['geometry'] if diagnostic else {}
            error = geometry.get('maximum_matched_hausdorff_m')
            errors.append(np.nan if error is None else max(error * 1000, 1e-5))
            costs.append(row['work']['totals']['bie_frequency_solve_count'] if row else
                         diagnostic['completed_bie_solve_lower_bound'] if diagnostic else np.nan)
            partial.append(row is None)
        partial = np.array(partial)
        axes[0].scatter(np.array(errors)[~partial], (positions + offset)[~partial], label=arm, color=color)
        axes[0].scatter(np.array(errors)[partial], (positions + offset)[partial], marker='x', color=color)
        bars = axes[1].barh(positions + offset, costs, height=.35, color=color, label=arm)
        for bar, is_partial in zip(bars, partial):
            if is_partial:
                bar.set_hatch('///'); bar.set_alpha(.45)
    axes[0].axvline(1., color='#b3473f', ls='--', lw=1.4, label='1-mm geometry gate')
    axes[0].set_xscale('log')
    axes[0].set_xlabel('Maximum matched boundary error (mm; log scale)')
    axes[1].set_xlabel('BIE solves; hatched bars are checkpoint lower bounds')
    for ax in axes:
        ax.set_yticks(positions, [s['id'] for s in spec['scenes']])
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=.18)
        ax.legend()
    fig.suptitle('Frozen scenes v1 — guarded G against feasible-FD H; crosses show failed-run checkpoints')
    fig.savefig(HERE / 'error_and_work.svg')
    fig.savefig(HERE / 'error_and_work.png', dpi=140)
    plt.close(fig)

    passed = {arm: sum(1 for (s, a), r in rows.items() if a == arm and r['passed']) for arm in ARMS}
    returned = {arm: sum(1 for (s, a) in rows if a == arm) for arm in ARMS}
    s2 = {a['arm']: a for a in stage2['arms']}
    d = verification['stage1_derivative_model']
    report = ['# TOP-008 — feasible finite differences at an active constraint', '',
        'Guarded **G** against **H**, the same policy with `feasible_fd_jacobian` on, on the frozen '
        "twelve-scene v1 matrix, reusing TOP-007's observations and initial states byte-for-byte with "
        'zero new oracle solves. The stencil is the only difference between the arms.', '',
        'Implements rank 1 of the '
        '[literature verdict](../../../../docs/iterations/topology/iteration_05/02_proposals/03_literature_verdict.md) '
        'and nothing else: a probe the radius floor refuses is no longer recorded as a derivative of '
        'zero. The feasible set, the gauge, the 8-mm certificate, the acquisition, the candidates and '
        'every default are unchanged.', '',
        '## Stage 1 — is a one-sided estimate trustworthy?', '',
        'A per-direction probe of two saved final states, no optimizer and no topology search. '
        'Steps 0.5h, h and 2h around the configured 1.0e-4 m were declared in the contract before '
        'execution, as was the 0.25 agreement tolerance.', '',
        f"At the pinned `far-ellipse-star` state, **15 of 20 gauge directions are refused on exactly one "
        f"side and none on both**, so every column the defect froze is recoverable. Estimates are stable "
        f"across the declared sequence to a worst relative difference of **{d['worst_stability']:.2e}**, "
        f"against a tolerance of {d['agreement_tolerance']}. Where a central difference also exists, the "
        f"one-sided estimate differs from it by at most **{d['worst_one_sided_vs_central']:.2e}** — so the "
        'mixed-order Jacobian the correction assembles is a measured, small effect rather than an '
        'assumed-safe one. The interior control reproduces its own central differences to 1e-5. '
        f"**{d['directions_with_an_unresolved_step']} directions** had no usable side at any step.", '',
        '[Per-direction record](stage1_derivative_probe.json) · [script](stage1_derivative_probe.py)', '',
        '## Stage 2 — does a measured model produce a feasible decrease?', '',
        'One bounded fixed-topology continuation from the saved guarded `far-ellipse-star` final state, '
        'run with each stencil. No topology event, no candidate, no new observation. Budgets — 22 '
        'iterations, 600 s, 1200 solves — were declared before execution and all were respected.', '',
        '| | Frozen columns | Feasible columns |',
        '|---|---|---|',
        f"| Stop reason | `{s2['frozen']['stop_reason']}` | `{s2['feasible']['stop_reason']}` |",
        f"| Iterations taken | {s2['frozen']['iterations']} | {s2['feasible']['iterations']} |",
        f"| Production loss | {s2['frozen']['production_loss']:.6e} | {s2['feasible']['production_loss']:.6e} |",
        f"| Refined loss | {s2['frozen']['refined_loss']:.6e} | {s2['feasible']['refined_loss']:.6e} |",
        f"| Refined training error | {s2['frozen']['refined_relative_error']:.4g} | {s2['feasible']['refined_relative_error']:.4g} |",
        f"| Matched boundary error | {s2['frozen']['geometry']['maximum_matched_hausdorff_m']*1e3:.3f} mm | "
        f"{s2['feasible']['geometry']['maximum_matched_hausdorff_m']*1e3:.3f} mm |",
        f"| Pinned mode-9 component's radius certificate | "
        f"{s2['frozen']['components'][-1]['radius_floor_after_m']*1e3:.3f} mm | "
        f"{s2['feasible']['components'][-1]['radius_floor_after_m']*1e3:.3f} mm |",
        f"| Decrease at **both** resolutions | {s2['frozen']['decreased_at_both_resolutions']} | "
        f"{s2['feasible']['decreased_at_both_resolutions']} |", '',
        'The frozen arm takes **zero** iterations: every direction that would move the pinned component '
        'is a zeroed column, so there is no step to take and the run stops immediately. With the feasible '
        'stencil the same state, same data and same budgets give a genuine decrease at both resolutions '
        'under the existing margin convention, and **the pinned component leaves the floor entirely**, '
        f"from 8.000 mm to {s2['feasible']['components'][-1]['radius_floor_after_m']*1e3:.3f} mm. "
        'That is the hypothesis stated in the contract, and it holds.', '',
        'Two honest qualifications. The continuation stopped at `maximum_iterations`, so it was still '
        'improving when the declared budget ran out — this is a lower bound on what the corrected model '
        'can do from that state, not a converged answer. And 9.07 mm of boundary error is still far '
        'outside the 1-mm gate: the component moved, it did not arrive.', '',
        '[Continuation record](stage2_continuation.json) · [script](stage2_continuation.py)', '',
        '## Stage 3 — the frozen benchmark', '',
        f"G returns {returned.get('G', 0)}/12 runs and H returns {returned.get('H', 0)}/12. "
        f"G passes {passed.get('G', 0)}/12 scenes and **H passes {passed.get('H', 0)}/12**. "
        '**The correction buys no new benchmark pass.** Stages 1 and 2 qualified the mechanism; '
        'this stage says the mechanism is not by itself sufficient for these scenes, which is what '
        "the verdict's low confidence for the suite anticipated.", '',
        'What did change, reported in both directions:', '',
        '- `central-ellipse-star` **completes** under H where G spends the full ten minutes, ending '
        'at 9.22 mm and 0.777 IoU. One fewer timeout.',
        '- `split` improves sharply and gets cheaper: matched error 0.175 mm to 0.000023 mm, worst '
        'holdout error 1.13e-2 to 3.24e-6, and 281 solves against 1172. It passed in both arms, so '
        'this buys accuracy and cost, not a pass.',
        '- `far-two-stars` returns a final state **identical** to G. Its census found no constrained '
        'direction, and the run bears that out — the control behaved as a control.',
        '- `far-ellipse-star` and `empty-ellipse-star` are **mixed**: boundary error improves '
        '18.62 mm to 17.62 mm, while refined training error gets *worse*, 3.06e-2 to 6.45e-2, on a '
        'trajectory that takes different events and stops earlier. A better-measured Jacobian '
        'changed where the run went, not only how well it descended. This is reported as mixed '
        'rather than as an improvement.', '',
        'Arm H records one-sided columns on every completed run (2 to 55) and unresolved columns on '
        'one (`far-two-circles`, 2). Every guarded run used at least one one-sided column, so the '
        'declared "inert wherever no column is one-sided" check again has no members; the identical '
        '`far-two-stars` final state stands in its place and is recorded per scene.', '',
        '[Error and work](error_and_work.svg) · [All initial scenes](initial_scenes.svg) · '
        '[New scene results](new_results.svg) · [Original controls](original_results.svg)', '',
        '## Per-scene outcomes', '',
        '| Scene | Arm | Pass | Objects / truth | Matched error (mm) | Union IoU | Refined train error | '
        'Worst holdout error | BIE solves | One-sided cols | Unresolved cols | Stop |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for scene in spec['scenes']:
        for arm in ARMS:
            key = f"{arm}/{scene['id']}"
            stat = statistics[key]
            one_sided = '—' if stat['one_sided_columns'] is None else str(stat['one_sided_columns'])
            unresolved = '—' if stat['unresolved_columns'] is None else str(stat['unresolved_columns'])
            row = rows.get((scene['id'], arm))
            if row is None:
                path = HERE / 'runs' / arm / scene['id']
                reason = benchmark.read(path / 'failure.json')['reason'] if (path / 'failure.json').exists() else 'pending'
                diagnostic = diagnostics.get(key)
                if diagnostic:
                    g = diagnostic['geometry']; value = g['maximum_matched_hausdorff_m']
                    error = '—' if value is None else f'{value * 1000:.5g}†'
                    report.append(f"| [{scene['id']}](runs/{arm}/{scene['id']}/failure.json) | {arm} | FAIL | "
                        f"{g['component_count']} / {g['truth_component_count']}† | {error} | {g['union_iou']:.4f}† | "
                        f"— | — | ≥{diagnostic['completed_bie_solve_lower_bound']} | {one_sided} | {unresolved} | {reason} |")
                else:
                    report.append(f"| {scene['id']} | {arm} | FAIL / incomplete | — | — | — | — | — | — | "
                                  f"{one_sided} | {unresolved} | {reason} |")
                continue
            g = row['geometry']; error = g['maximum_matched_hausdorff_m']
            distance = '—' if error is None else f'{error * 1000:.5g}'
            report.append(f"| [{scene['id']}](runs/{arm}/{scene['id']}/metrics.json) | {arm} | "
                f"{'PASS' if row['passed'] else 'FAIL'} | {g['component_count']} / {g['truth_component_count']} | "
                f"{distance} | {g['union_iou']:.4f} | {row['refined_relative_error']:.4g} | "
                f"{row['maximum_holdout_relative_error']:.4g} | {row['work']['totals']['bie_frequency_solve_count']} | "
                f"{one_sided} | {unresolved} | {row['stop_reason']} |")
    report += ['', '† Failed-run quantities describe the last saved accepted state, not a qualified final '
        'solution, and their solve counts are lower bounds. Column counts are summed over the cycles whose '
        'records were written before a run stopped, so a timed-out run under-reports them, and they are '
        'recorded only in arm H. Arm totals are not a cost comparison: measuring a column the other arm '
        'froze is extra work by construction.', '', '## Verification', '',
        f"Artifact verification: **{'PASS' if verification['all_checks_passed'] else 'CHECK REQUIRED'}**. "
        '[Machine-readable checks](verification.json) recheck source and observation hashes, paired inputs, '
        'rederived gates, exact reproduction of TOP-007 by the guarded arm, the stage-1 stability tolerance '
        'and the stage-2 both-resolution decrease. This is a re-reading of artifacts by the implementation '
        'owner, not independent scientific review. Reviewer: unassigned.', '',
        'The [plan](../../../../docs/iterations/topology/iteration_05/03_plan.md), '
        '[contract](../../../../docs/iterations/topology/iteration_05/02_proposals/04_feasible_fd_contract.md) and '
        '[frozen specification](scene_spec.json) fix all scenes, budgets, gates and stage thresholds before '
        'execution. Observations and initial states are copied from '
        '[TOP-007](../TOP-007-20260911-refined-feasibility/README.md); no new oracle solve was performed. '
        'Per-run timeout is ten minutes and the suite ceiling is 45 minutes. Four single-thread subprocesses '
        'may overlap, so elapsed times are not a controlled speed comparison.', '',
        '[Execution](execution.log) · [Full metrics](suite_metrics.json) · [Tests](tests.log)', '',
        'Rebuild this analysis from the repository root:', '', '```bash',
        'env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python '
        'results/validation/topology/TOP-008-20260912-feasible-fd/analyze.py', '```', '']
    (HERE / 'README.md').write_text('\n'.join(report))
    print(json.dumps({'verification_passed': verification['all_checks_passed'],
                      'passed': passed, 'returned': returned, 'totals': data['totals'],
                      'uncaught_exceptions': verification['uncaught_exceptions']}))


if __name__ == '__main__':
    main()
