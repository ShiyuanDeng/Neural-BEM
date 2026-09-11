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
from gpr_bem_kress.multicomponent import adapt_multicomponent_boundary, MultiComponentKressGeometryError
from sdf_inverse.geometry import OrderedSDFGeometryError

REFERENCE = ROOT / 'results/validation/topology/TOP-006-20260911-scenes-v1'
ARMS = ('A', 'G')
SOLVE = benchmark.driver.baseline.iteration01_solve_config()


def refined_clearance(state, spec):
    """Minimum inter-component clearance of a saved state at the refined nodes."""
    if state is None or len(state.components) < 2:
        return None
    config = benchmark.driver.baseline._geometry_config(spec['refined_nodes'])
    try:
        adapter = adapt_multicomponent_boundary(state.boundary(config), config=SOLVE.assembly)
    except (OrderedSDFGeometryError, MultiComponentKressGeometryError):
        return 'inadmissible'
    return adapter.minimum_intercomponent_clearance


def guard_statistics(path):
    passes_path = path / 'topology_passes.json'
    if not passes_path.exists():
        return dict(cycles_recorded=0, guard_rejected_trials=None, rollbacks=None)
    passes = benchmark.read(passes_path)
    rejected = [p.get('refined_feasibility_rejected_trials') for p in passes]
    rollbacks = [p.get('refined_infeasible_rollback') for p in passes]
    return dict(cycles_recorded=len(passes),
                guard_rejected_trials=None if any(r is None for r in rejected) else int(sum(rejected)),
                rollbacks=None if any(r is None for r in rollbacks) else int(sum(bool(r) for r in rollbacks)))


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
        minimum_refined_clearance_m=refined_clearance(state, spec),
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

    observations_match, initials_match, gates_match, guard = {}, {}, {}, {}
    clearances, diagnostics = {}, {}
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
            guard[key] = guard_statistics(path)
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
            clearances[key] = refined_clearance(
                benchmark.driver.deserialize_state(row['final_state']), spec)

    def compare(new, old):
        return dict(same_final_state=old['final_state'] == new['final_state'],
            same_solve_count=old['work']['totals']['bie_frequency_solve_count'] ==
                             new['work']['totals']['bie_frequency_solve_count'],
            same_stop_reason=old['stop_reason'] == new['stop_reason'],
            same_training_error=abs(old['final_relative_error'] - new['final_relative_error']) < 1e-12)

    # The default arm reruns TOP-006's policy on its own observations: with the
    # guard off, the new source must reproduce it exactly.
    default_reproduces = {scene: compare(rows[(scene, 'A')], reference_rows[(scene, 'A')])
                          for scene, arm in rows if arm == 'A' and (scene, 'A') in reference_rows}
    # Where the guard rejects nothing it must change nothing.
    guard_inert = {}
    for scene, arm in list(rows):
        if arm != 'G' or (scene, 'A') not in rows:
            continue
        rejected = guard[f'G/{scene}']['guard_rejected_trials']
        if rejected == 0:
            guard_inert[scene] = compare(rows[(scene, 'G')], rows[(scene, 'A')])
    # Both arms completing a scene is the case where they can be compared at all.
    same_where_both_completed = {scene: compare(rows[(scene, 'G')], rows[(scene, 'A')])
                                 for scene, arm in list(rows) if arm == 'G' and (scene, 'A') in rows}
    guarded_failures = {f"{f['arm']}/{f['scene']}": f['reason'] for f in data['failures'] if f['arm'] == 'G'}

    verification = dict(complete=data['complete'], all_inputs_paired=data['all_inputs_paired'],
        source_matches=source_matches, observations_match=observations_match,
        initial_states_match=initials_match, rederived_gates_match=gates_match,
        default_arm_reproduces_top006=default_reproduces,
        guard_inert_where_it_rejects_nothing=guard_inert,
        same_final_state_where_both_arms_completed={
            scene: checks['same_final_state'] for scene, checks in same_where_both_completed.items()},
        solve_count_difference_where_both_arms_completed={
            scene: rows[(scene, 'G')]['work']['totals']['bie_frequency_solve_count'] -
                   rows[(scene, 'A')]['work']['totals']['bie_frequency_solve_count']
            for scene in same_where_both_completed},
        guarded_arm_failure_reasons=guarded_failures,
        guarded_arm_uncaught_exceptions=sorted(k for k, v in guarded_failures.items() if v == 'exception'),
        guard_statistics=guard, minimum_refined_clearance_m=clearances,
        oracle_checks=benchmark.read(HERE / 'oracle_checks.json'))
    verification['all_checks_passed'] = bool(data['complete'] and data['all_inputs_paired'] and
        all(source_matches.values()) and all(observations_match.values()) and
        all(initials_match.values()) and all(gates_match.values()) and
        all(all(c.values()) for c in default_reproduces.values()) and
        all(all(c.values()) for c in guard_inert.values()) and
        all(c['same_final_state'] and c['same_stop_reason'] for c in same_where_both_completed.values()) and
        not verification['guarded_arm_uncaught_exceptions'] and
        all(o['passed'] for o in verification['oracle_checks']))
    benchmark.driver.write_json(HERE / 'verification.json', verification)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)
    positions = np.arange(len(spec['scenes']))
    for arm, offset, color in [('A', -.19, '#62778a'), ('G', .19, '#07877f')]:
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
    fig.suptitle('Frozen scenes v1 — default A against guarded G; crosses show failed-run checkpoints')
    fig.savefig(HERE / 'error_and_work.svg')
    fig.savefig(HERE / 'error_and_work.png', dpi=140)
    plt.close(fig)

    passed = {arm: sum(1 for (s, a), r in rows.items() if a == arm and r['passed']) for arm in ARMS}
    report = ['# TOP-007 — refined-discretization feasibility inside the optimizer', '',
        'Default **A** against guarded **G** on the frozen twelve-scene v1 matrix, reusing '
        "TOP-006's observations and initial states byte-for-byte with zero new oracle solves. "
        'The guard is the only difference between the arms.', '',
        f"**No guarded run aborts.** A returns {sum(1 for (s, a) in rows if a == 'A')}/12 runs and "
        f"G returns {sum(1 for (s, a) in rows if a == 'G')}/12; the two runs that ended TOP-006 with an "
        'uncaught `MultiComponentTopologyError` now finish. Both arms still pass '
        f"{passed.get('A', 0)}/12 scenes: the guard removes the crash, not the shape error.", '',
        'Arm A reproduces TOP-006 exactly — identical final states, solve counts, stop reasons and '
        'training errors on every completed scene, and the same two aborts with the same '
        '9.971374e-03 m clearance against the 1.0e-02 m floor. On **every scene both arms completed, '
        'the two final states are identical**; five also match solve-for-solve, while repeated-birth '
        'costs 30 more solves and far-two-circles 9 more for the same answer.', '',
        'The guard rejected between 1 and 216 trial states per guarded run, and the controller-level '
        'rollback never fired: refusing the step was enough, and no accepted state ever had to be '
        'withdrawn. Guarded runs do not merely park on the floor either — the two newly completing '
        'scenes end with 38.1 mm of refined clearance.', '',
        '`far-ellipse-star` is the requested case. Guarded, it runs birth, birth, death, birth and then '
        '**merge** — merging the two components whose approach ended the unguarded run — and stops '
        '`topology_stationary` with the **correct 2/2 object count**, 18.62 mm matched boundary error, '
        '0.704 IoU, 3.06% refined training error and 140% worst holdout error. `empty-ellipse-star` '
        'starts from an empty domain and converges to the same two components to within 1e-8 m. '
        'Two very different initializations reaching the same wrong shapes places the remaining error '
        'in the representation and the objective, not in the start.', '',
        'That reconstruction is a mode-1 circle where the star is and a mode-9 curve where the ellipse '
        'is. The ellipse component already carries nine modes and still stops 18.6 mm away with 3.06% '
        'training error, so bandwidth alone is not the missing ingredient — the optimizer is not '
        'exploiting the bandwidth it has. Any shape-capacity experiment has to account for that.', '',
        'Three scenes still reach the ten-minute ceiling in both arms '
        '(central, enclosing and far-three-shapes), unchanged from TOP-006. How far a timed-out run gets '
        'depends on machine load, so those rows differ from their TOP-006 counterparts in progress and in '
        'their solve lower bounds; only completed runs are exactly reproducible.', '',
        '[Requested distant-circle comparison](far_ellipse_star.svg) · [All initial scenes](initial_scenes.svg) · '
        '[New scene results](new_results.svg) · [Original controls](original_results.svg) · '
        '[Error and work](error_and_work.svg)', '',
        '**[All videos](videos.md)** — every guarded scene, plus the default arm on the two scenes whose '
        'outcome changed. The before/after pair is '
        '[default](runs/A/far-ellipse-star/inversion.mp4) against '
        '[guarded](runs/G/far-ellipse-star/inversion.mp4) on the requested scene.', '',
        '## Per-scene outcomes', '',
        '| Scene | Arm | Pass | Objects / truth | Matched error (mm) | Union IoU | Refined train error | '
        'Worst holdout error | BIE solves | Guard-rejected trials | Stop |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---:|---|']
    for scene in spec['scenes']:
        for arm in ARMS:
            key = f"{arm}/{scene['id']}"
            rejected = guard[key]['guard_rejected_trials']
            rejected = '—' if rejected is None else str(rejected)
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
                        f"— | — | ≥{diagnostic['completed_bie_solve_lower_bound']} | {rejected} | {reason} |")
                else:
                    report.append(f"| {scene['id']} | {arm} | FAIL / incomplete | — | — | — | — | — | — | {rejected} | {reason} |")
                continue
            g = row['geometry']; error = g['maximum_matched_hausdorff_m']
            distance = '—' if error is None else f'{error * 1000:.5g}'
            report.append(f"| [{scene['id']}](runs/{arm}/{scene['id']}/metrics.json) | {arm} | "
                f"{'PASS' if row['passed'] else 'FAIL'} | {g['component_count']} / {g['truth_component_count']} | "
                f"{distance} | {g['union_iou']:.4f} | {row['refined_relative_error']:.4g} | "
                f"{row['maximum_holdout_relative_error']:.4g} | {row['work']['totals']['bie_frequency_solve_count']} | "
                f"{rejected} | {row['stop_reason']} |")
    report += ['', '† Failed-run quantities describe the last saved accepted state, not a qualified final '
        'solution, and their solve counts are lower bounds. Guard-rejected trials are counted only in the '
        'guarded arm and only for cycles whose records were written before the run stopped, so a timed-out '
        'run reports none. Arm totals are not a cost comparison: G spends more in total precisely because '
        'two of its runs survive to finish.', '',
        'Every guarded run that completed rejected at least one trial, so the declared '
        '"identical wherever the guard rejects nothing" check has no members. The stronger observed fact '
        'stands in its place and is recorded per scene: wherever both arms completed, their final states '
        'are identical.', '', '## Verification', '',
        f"Artifact verification: **{'PASS' if verification['all_checks_passed'] else 'CHECK REQUIRED'}**. "
        '[Machine-readable checks](verification.json) recheck source and observation hashes, paired inputs, '
        'rederived gates, exact reproduction of TOP-006 by the default arm, and identical final states and stop '
        'reasons wherever both arms completed. This is a re-reading of artifacts by the implementation owner, '
        'not independent scientific review. Reviewer: unassigned.', '',
        'The [plan](../../../../docs/iterations/topology/iteration_04/03_plan.md) and '
        '[frozen specification](scene_spec.json) fix all scenes, budgets and gates before execution. '
        'Observations and initial states are copied from '
        '[TOP-006](../TOP-006-20260911-scenes-v1/README.md); no new oracle solve was performed. '
        'Per-run timeout is ten minutes and the suite ceiling is 45 minutes. Four single-thread subprocesses '
        'may overlap, so elapsed times are not a controlled speed comparison.', '',
        '[Execution](execution.log) · [Full metrics](suite_metrics.json) · [Tests](tests.log)', '',
        'Rebuild this analysis from the repository root:', '', '```bash',
        'env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python '
        'results/validation/topology/TOP-007-20260911-refined-feasibility/analyze.py', '```', '']
    (HERE / 'README.md').write_text('\n'.join(report))
    print(json.dumps({'verification_passed': verification['all_checks_passed'],
                      'passed': passed, 'totals': data['totals'],
                      'guarded_uncaught_exceptions': verification['guarded_arm_uncaught_exceptions']}))


if __name__ == '__main__':
    main()
