"""Rebuild TOP-019 reports from saved artifacts; no solver imports or solves."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TRAIN = [.5e9, .75e9, 1e9, 1.25e9]
QUOTAS = [1000, 1250, 1750, 4000]


def read(path): return json.loads(path.read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def state_hash(state): return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
def write(path, value): path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def verify_inputs(bundle, manifest):
    for name, sha in manifest['input_sha256'].items():
        assert digest(bundle/name) == sha, ('input changed', name)
    for name, sha in manifest['historical_sha256'].items():
        assert digest(ROOT/name) == sha, ('historical input changed', name)
    for name, sha in manifest['source_sha256'].items():
        if (ROOT/name).exists() and digest(ROOT/name) == sha: continue
        snapshot = bundle/'measured_sources'/name
        if snapshot.exists(): assert digest(snapshot) == sha, ('source snapshot', name)
        else:
            measured = subprocess.check_output(['git', 'show', manifest['git_revision']+':'+name], cwd=ROOT)
            assert hashlib.sha256(measured).hexdigest() == sha, ('measured source', name)


def score_row(label, score, h, **extra):
    if score is None: return dict(label=label, state_sha256=h, score_status='UNAVAILABLE', **extra)
    assert score['state_sha256'] == h
    return dict(label=label, state_sha256=h,
        boundary_mm=1000*score['geometry']['maximum_matched_hausdorff_m'], iou=score['geometry']['union_iou'],
        errors=score['training_errors']+score['evaluation_errors'], gates=score['gates'],
        original_gates_pass=score['original_gates_pass'], numerically_qualified=score['numerically_qualified'],
        aggregate_objectives_by_nodes=score.get('aggregate_objectives_by_nodes'), **extra)


def verify_prediction_scores(saved, score, training, original):
    """Independently reconstruct frequency errors from saved complex samples."""
    def complex_rows(real, imag):
        return [[complex(r, i) for r, i in zip(rr, ii)] for rr, ii in zip(real, imag)]
    observed = complex_rows(training['observed_real'], training['observed_imag'])
    evaluation = complex_rows(original['observed_real'], original['observed_imag'])
    reference = [a+b[1:] for a, b in zip(observed, evaluation)]
    values = {n: complex_rows(row['real'], row['imag']) for n, row in saved['predictions'].items()}
    def relative(a, b):
        assert len(a) == len(b) == 24 and all(len(row) == 6 for row in a+b)
        return [math.sqrt(sum(abs(x[f]-y[f])**2 for x, y in zip(a, b)) /
                          sum(abs(y[f])**2 for y in b)) for f in range(6)]
    errors = relative(values['512'], reference)
    eta = relative(values['256'], values['512'])
    for a, b in zip(errors, score['training_errors']+score['evaluation_errors']):
        assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-15), ('prediction error differs', a, b)
    for a, b in zip(eta, score['numerical_checks']['training_discrepancy']+score['numerical_checks']['evaluation_discrepancy']):
        assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-15), ('numerical discrepancy differs', a, b)
    assert score['numerically_qualified'] == all(x <= t for x, t in zip(eta, [1e-5, 1e-7, 1e-7, 1e-7, 1e-5, 1e-5]))
    assert score['gates']['original_training'] == (errors[0] <= .003)
    assert score['gates']['evaluation'] == (max(errors[4:]) <= .05)
    assert score['original_gates_pass'] == all(score['gates'].values())
    for nodes, predictions in values.items():
        node_errors = relative(predictions, reference)
        for k in (1, 2, 3, 4):
            objective = .5*sum(x*x for x in node_errors[:k])/k
            assert math.isclose(objective, score['aggregate_objectives_by_nodes'][nodes][str(k)],
                                rel_tol=1e-10, abs_tol=1e-25)


def classify(audit, trials):
    complete = (len(trials) == 2 and all(t.get('schedule_complete') and t.get('numerically_qualified')
                and t.get('source_integrity') and t.get('complete_effective_exposure') for t in trials.values()))
    if audit['status'] != 'PHASE_A_PASS':
        return 'PHASE_A_NOT_QUALIFIED', False, 'Diagnose the recorded audit obstruction before any further inverse.'
    if not complete:
        return 'MATCHED_PAIR_INCOMPLETE', False, 'Diagnose the recorded numerical, exposure or resource obstruction.'
    s, f = (trials[a]['final']['original_gates_pass'] for a in ('S', 'F'))
    if f and not s:
        return 'F_RECOVERED_RELATIVE_TO_MATCHED_S', True, 'Prepare a separately scoped fresh automatic two-star integration contract.'
    if f and s:
        return 'BOTH_ARMS_RECOVERED', True, 'Compare precision and work before selecting a policy for fresh integration.'
    if s:
        return 'ADVERSE_MATCHED_F_CONTROL', True, 'Diagnose the measured F failure before fresh integration.'
    return 'NEITHER_ARM_RECOVERED', True, 'Distinguish optimization stagnation from quota exhaustion in one bounded diagnosis.'


def curve_points(component, count=1024):
    k = component['maximum_mode']; values = component['parameters']
    assert len(values) == 4*k+2
    cosine = [values[2*i:2*i+2] for i in range(k+1)]
    sine = [[0., 0.]]+[values[2*(k+1)+2*i:2*(k+1)+2*i+2] for i in range(k)]
    return [[sum(cosine[j][axis]*math.cos(j*t)+sine[j][axis]*math.sin(j*t) for j in range(k+1))
             for axis in (0, 1)] for t in [2*math.pi*i/count for i in range(count+1)]]


def figure(bundle, common, trials):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    scene = next(s for s in read(bundle/'scene_spec.json')['scenes'] if s['id'] == 'merge')
    truth = scene['truth'][0]; assert truth['kind'] == 'ellipse'
    c, s = math.cos(truth['rotation']), math.sin(truth['rotation'])
    target = [(truth['center'][0]+c*truth['semi_major']*math.cos(t)-s*truth['semi_minor']*math.sin(t),
               truth['center'][1]+s*truth['semi_major']*math.cos(t)+c*truth['semi_minor']*math.sin(t))
              for t in [2*math.pi*i/1024 for i in range(1025)]]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharex=True, sharey=True)
    associations = {}
    for axis, name, state in zip(axes, ('Common start', 'S', 'F'),
            (common, trials.get('S', {}).get('final_state'), trials.get('F', {}).get('final_state'))):
        axis.plot(*zip(*target), '--', color='#475569', linewidth=1.7, label='Target ellipse')
        title = name
        if state is not None:
            for component in state:
                axis.plot(*zip(*curve_points(component)), color='#0d9488', linewidth=1.8, label='Saved boundary')
            associations[name] = dict(state_sha256=state_hash(state), state=state)
            if name in trials:
                title += '\n'+('Stage 4' if trials[name].get('schedule_complete') else 'Stopped / retained state')
        else: title += '\nNot run'
        axis.set(title=title, aspect='equal', xlim=(.39, .61), ylim=(.445, .555), xlabel='x (m)')
        axis.grid(alpha=.2)
    axes[0].set_ylabel('y (m)'); axes[0].legend(loc='upper left', fontsize=8)
    fig.suptitle('TOP-019 · K=17 merge control · saved states', fontsize=14)
    fig.tight_layout(); fig.savefig(bundle/'endpoints.svg', metadata={'Date': None}); plt.close(fig)
    write(bundle/'figure_manifest.json', dict(new_physical_solves=0, states=associations,
        truth_source='scene_spec.json::merge.truth', source_sha256=digest(Path(__file__))))


def summarize(bundle):
    manifest = read(bundle/'manifest.json'); verify_inputs(bundle, manifest)
    audit, campaign = read(bundle/'phase_a/audit.json'), read(bundle/'campaign.json')
    common = read(bundle/'inputs/merge/state.json'); common_hash = state_hash(common)
    training = read(bundle/'inputs/merge/training_observations.json')
    original = read(bundle/'inputs/merge/observations.json')
    for label, row in audit['states'].items():
        assert row['state_sha256'] == state_hash(row['state'])
        if 'score' in row:
            saved = read(bundle/f'phase_a/{label}_predictions.json')
            assert saved['state_sha256'] == state_hash(saved['state']) == row['state_sha256']
            verify_prediction_scores(saved, row['score'], training, original)
    rows = []; trials = {}; works = [audit['work']]; unavailable = []
    if 'common_score' in audit: rows.append(score_row('COMMON', audit['common_score'], common_hash))
    for arm in ('S', 'F'):
        folder = bundle/'runs'/f'{arm}-merge'; path = folder/'metrics.json'
        if not path.exists():
            dispatched = any(w['arm'] == arm and w.get('status') != 'NOT_DISPATCHED' for w in campaign['workers'])
            unavailable.append(dict(arm=arm, status='METRICS_UNAVAILABLE' if dispatched else 'NOT_RUN'))
            if (folder/'work.json').exists(): works.append(read(folder/'work.json'))
            continue
        trial = read(path); trials[arm] = trial; works.append(trial['work'])
        assert audit['status'] == 'PHASE_A_PASS' and audit['gate']['passed']
        assert trial['initial_state_sha256'] == state_hash(trial['initial_state']) == common_hash
        assert trial['final_state_sha256'] == state_hash(trial['final_state'])
        assert [r['stage'] for r in trial['stages']] == [1, 2, 3, 4][:len(trial['stages'])]
        previous = common_hash
        for i, stage in enumerate(trial['stages']):
            terminal = stage['terminal']; h = state_hash(terminal['final_state'])
            active = 1 if arm == 'S' else stage['stage']
            assert stage['start_state_sha256'] == previous
            assert terminal['state_sha256'] == h
            assert terminal['production_nodes'] == 256 and terminal['refined_nodes'] == 512
            assert stage['active_frequencies_hz'] == TRAIN[:active]
            if terminal.get('objective_identity'):
                assert terminal['objective_identity']['state_sha256'] == h
                for key in ('gradient', 'last_measured_gradient'):
                    gradient = terminal.get(key)
                    if gradient is None: continue
                    assert gradient['active_frequencies_hz'] == TRAIN[:active]
                    assert gradient['production_nodes'] == 256 and gradient['refined_nodes'] == 512
                    assert gradient['objective_sha256'] == terminal['objective_identity']['objective_sha256']
                    if key == 'gradient': assert gradient['state_sha256'] == h
            start = terminal['work']['total_attempted']-terminal['work']['stage_attempted']
            if i+1 < len(trial['stages']):
                later = trial['stages'][i+1]['terminal']['work']
                end = later['total_attempted']-later['stage_attempted']
            else: end = trial['work']['total_attempted']
            assert 0 <= end-start <= QUOTAS[stage['stage']-1]
            score = stage.get('score')
            reporting = False
            if score is not None:
                assert stage['score_state_sha256'] == h
                assert score['objective_sha256'] == terminal['objective_identity']['objective_sha256']
            elif i == len(trial['stages'])-1 and trial.get('reporting_score'):
                score = trial['reporting_score']; reporting = True
                assert trial['reporting_score_state_sha256'] == h and trial['reporting_score_releases_stage'] is False
            stage_path = folder/f'stage_{stage["stage"]}'
            if score is not None:
                saved = read(stage_path/'endpoint_predictions.json')
                assert saved['state_sha256'] == state_hash(saved['state']) == h
                verify_prediction_scores(saved, score, training, original)
            losses = [json.loads(line)['loss'] for line in (stage_path/'trajectory.jsonl').read_text().splitlines()] if (stage_path/'trajectory.jsonl').exists() else []
            assert all(b <= a for a, b in zip(losses, losses[1:])), ('nonmonotone trajectory', arm, stage['stage'])
            if (stage_path/'acceptance.json').exists():
                for accepted in read(stage_path/'acceptance.json'):
                    if accepted['accepted']:
                        assert min(accepted['production_gain'], accepted['refined_gain']) > accepted['margin']+accepted['disagreement_allowance']
            if (stage_path/'numerical_failure.json').exists():
                failure = read(stage_path/'numerical_failure.json'); checkpoint = read(stage_path/'accepted_state.json')
                assert failure['accepted'] is False and failure['accepted_state_sha256'] == checkpoint['state_sha256']
                for key in ('production_base', 'production_candidate', 'refined_base', 'refined_candidate'):
                    assert failure[key]['state_sha256'] == state_hash(failure[key]['state'])
            rows.append(score_row(f'{arm} stage {stage["stage"]}', score, h, arm=arm, stage=stage['stage'],
                active_frequencies_hz=stage['active_frequencies_hz'], stop=terminal['stage_outcome'],
                optimizer_stop=terminal['optimizer_stop'], configured_convergence=terminal['convergence'],
                accepted_steps=terminal['accepted_steps'], effective_training_exposure=terminal['effective_training_exposure'],
                solve_attempts_including_endpoint=end-start, gradient=terminal.get('gradient'),
                last_measured_gradient=terminal.get('last_measured_gradient'), reporting_only=reporting,
                stage_complete=stage.get('stage_complete', False), monotone_saved_objectives=True))
            previous = h
    if audit['status'] != 'PHASE_A_PASS': assert not trials and not campaign['workers']
    if 'F' in trials and len(trials['F']['stages']) >= 2:
        assert trials['S']['stages'][0]['score_state_sha256'] == trials['F']['stages'][0]['score_state_sha256']
    totals = {key: Counter() for key in ('attempted', 'completed', 'failed')}
    for work in works:
        assert work['total_attempted'] == sum(work['attempted'].values()) <= work['solve_cap']
        assert work['total_attempted'] == sum(work['completed'].values())+sum(work['failed'].values())
        # Signals may take a small amount of time to persist a terminal record.
        assert work['active_wall_seconds'] <= work['wall_ceiling_seconds']+5
        for key in totals: totals[key].update(work[key])
    assert works[0]['total_attempted'] <= 256 and sum(totals['attempted'].values()) <= 16256
    assert campaign['elapsed_seconds'] <= 15305
    outcome, complete, decision = classify(audit, trials)
    ledger = dict(total_attempted=sum(totals['attempted'].values()), total_completed=sum(totals['completed'].values()),
        total_failed=sum(totals['failed'].values()), by_category={k: dict(v) for k, v in totals.items()},
        phase_a=works[0], trials={a: t['work'] for a, t in trials.items()},
        summed_active_wall_seconds=sum(w['active_wall_seconds'] for w in works),
        campaign_elapsed_seconds=campaign['elapsed_seconds'], historical_prediction_solves_reused=0,
        attempt_counts_complete=all(x['status'] == 'NOT_RUN' for x in unavailable))
    scorecard = dict(outcome=outcome, decision=decision, pair_complete_and_qualified=complete, rows=rows,
        unavailable_arms=unavailable, worker_exit_failures=[w for w in campaign['workers'] if w['exit_code'] != 0],
        trials={a: {k: t.get(k) for k in ('status', 'reason', 'schedule_complete', 'numerically_qualified',
            'source_integrity', 'convergence', 'complete_effective_exposure', 'reconstruction_gates_pass', 'work')}
            for a, t in trials.items()})
    write(bundle/'scorecard.json', scorecard); write(bundle/'work_ledger.json', ledger)
    table = ['| Endpoint | Boundary mm | IoU | 0.5 GHz | 0.75 | 1.0 | 1.25 | 1.5 | 2.5 | Gates | Qualified | Stop | Solves |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|']
    for row in rows:
        if 'boundary_mm' not in row: continue
        table.append(f'| {row["label"]} | {row["boundary_mm"]:.7g} | {row["iou"]:.7g} | '+
            ' | '.join(f'{x:.7g}' for x in row['errors'])+
            f' | {row["original_gates_pass"]} | {row["numerically_qualified"]} | {row.get("optimizer_stop") or row.get("stop", "start")} | {row.get("solve_attempts_including_endpoint", 0)} |')
    figure(bundle, common, trials)
    (bundle/'README.md').write_text(f'''# TOP-019: capacity-qualified merge-control comparison

**{outcome}.** {decision}

Approved 2026-09-15 by the user's “go” response to the named audit/conditional-pair
request. Codex `/root` owns implementation and review; no independent review is
claimed. Existing checkout and branch, one numerical worker, single-thread BLAS.

## Binding audit

Phase A: **{audit['status']}**, {audit['work']['total_attempted']} attempted solves.
Failed requirements: {audit.get('gate', {}).get('failed_requirements', [])}.
All numerical thresholds are unchanged. The fixed truth projection is
evaluation-only; both inverses use the zero-padded original controller endpoint.
[Audit and numerical checks](phase_a/audit.json) · [Input provenance](reuse.json).

## Prescribed endpoints

{chr(10).join(table)}

Unrun or unavailable arms: {unavailable}.
The final endpoint is stage 4; stopped states are explicitly retained states.
The supplied count is not newly recovered. S fits only 0.5 GHz; F fits cumulative
0.5/0.75/1.0/1.25 GHz. The 1.5/2.5-GHz scores are development evaluation.
Both arms use K=17 and 256/512; quota stops do not establish convergence.
See the [full scorecard](scorecard.json) for objective/gradient associations,
stopping, effective exposure and missing scores.

## Work and provenance

**{ledger['total_attempted']} attempted / {ledger['total_completed']} completed /
{ledger['total_failed']} failed frequency solves.** Attempt accounting complete:
{ledger['attempt_counts_complete']}. Active numerical time:
{ledger['summed_active_wall_seconds']:.3f} s; campaign elapsed:
{ledger['campaign_elapsed_seconds']:.3f} s. No historical prediction solves reused.
All audit and per-stage endpoint work is included. Ceilings are 16,256 attempted
solves and 15,300 s; this is not a controlled historical runtime comparison.

[Ledger](work_ledger.json) · [Frozen contract](contract.json) ·
[Manifest](manifest.json) · [Approved plan](approved_plan.md) ·
[Implementation review](implementation_review.md) · [Tests](pre_dispatch_tests.log) ·
[Environment and command](environment.json) · [Workers](campaign.json) ·
[Saved-state figure](endpoints.svg) · [Figure provenance](figure_manifest.json).

Rebuild from saved artifacts, without physical solves:

```bash
python experiments/top019/summarize.py --bundle {bundle}
```

The historical TOP-016 merge regression and earlier central/two-star successes
remain separate evidence. No result automatically releases a successor or suite.
''')
    verification = dict(status='PASS', new_physical_solves=0,
        source_files=len(manifest['source_sha256']), input_files=len(manifest['input_sha256']),
        source_input_state_objective_gradient_acceptance_and_work_checks_pass=True,
        complete_pair=complete, attempt_counts_complete=ledger['attempt_counts_complete'])
    write(bundle/'verification.json', verification)
    write(bundle/'artifact_manifest.json', {str(x.relative_to(bundle)): digest(x) for x in sorted(bundle.rglob('*'))
        if x.is_file() and x.name != 'artifact_manifest.json'})
    return scorecard, ledger


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--bundle', type=Path, required=True)
    scorecard, ledger = summarize(parser.parse_args().bundle.resolve())
    print(json.dumps(dict(outcome=scorecard['outcome'], total_attempted=ledger['total_attempted'])))
