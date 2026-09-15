"""Replay the bounded damping pair from saved arrays; no solver imports."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top020 import summarize as prior

saved = prior.saved
read, write, digest, state_hash = saved.read, saved.write, saved.digest, saved.state_hash


def classify(rows):
    if not all(row.get('status') == 'COMPLETED_SCHEDULE' for row in rows):
        return 'MATCHED_PAIR_INCOMPLETE'
    passed = [row['arm'] for row in rows if row['reconstruction_pass']]
    return 'BOTH_ARMS_RECOVERED' if len(passed) == 2 else (passed[0]+'_RECOVERED' if passed else 'NEITHER_ARM_RECOVERED')


def verify(output):
    manifest = read(output/'manifest.json')
    saved.verify_inputs(output, manifest)
    contract, campaign = read(output/'contract.json'), read(output/'campaign.json')
    assert campaign['status'] == 'COMPLETED'
    assert [w['arm'] for w in campaign['workers']] == ['A', 'B']
    assert contract['stage_plan'] == [[4, 4000]] and contract['maximum_updates'] == 12
    configs = read(output/'arm_configs.json')
    assert {k for k in configs['A'] if configs['A'][k] != configs['B'][k]} == {'initial_damping'}
    train, original = (read(output/'inputs'/name) for name in ('training_observations.json', 'observations.json'))
    initial = read(output/'initial_endpoint_predictions.json')
    initial_hash = state_hash(read(output/'inputs/terminal_state.json'))
    assert initial_hash == initial['state_sha256'] == contract['initial_state_sha256']
    endpoints = [('Shared failed endpoint', initial)]
    rows, total, complete_counts = [], 0, True
    for worker in campaign['workers']:
        arm = worker['arm']; folder = output/'runs'/arm
        row = dict(arm=arm, status='WORKER_RESULT_UNAVAILABLE', reconstruction_pass=False, exit_code=worker['exit_code'])
        if not (folder/'result.json').exists():
            checkpoints = [folder/'stage_4'/name for name in ('terminal.json', 'accepted_state.json')]
            work = next((read(path)['work'] for path in checkpoints if path.exists()), None)
            lower = 0 if work is None else work['total_attempted']
            row.update(attempted_calls_lower_bound=lower, accounting_complete=False)
            total += lower; complete_counts = False; rows.append(row); continue
        for name, sha in read(folder/'artifact_manifest.json').items():
            assert digest(folder/name) == sha, name
        result = read(folder/'result.json'); schedule = result.get('schedule', {})
        assert result['sources_and_inputs_unchanged'] and result['initial_state_sha256'] == initial_hash
        assert read(folder/'arm_config.json')['optimizer'] == configs[arm]
        work = result['work']
        assert work['total_attempted'] == sum(work['attempted'].values()) == sum(work['per_frequency_attempted'].values()) <= 4000
        assert work['total_attempted'] == sum(work['completed'].values())+sum(work['failed'].values())
        for category in ('completed', 'failed'):
            assert sum(work[category].values()) == sum(work['per_frequency_'+category].values())
        assert work['active_wall_seconds'] <= 3601
        total += work['total_attempted']
        row.update(status=result['status'], reconstruction_pass=result['reconstruction_pass'], work=work, accounting_complete=True)
        for stage in schedule.get('stages', []):
            terminal = stage['terminal']; stage_folder = folder/'stage_4'
            assert stage['stage'] == 4 and stage['active_frequencies_hz'] == saved.TRAIN
            assert stage['start_state_sha256'] == initial_hash == state_hash(read(stage_folder/'initial_state.json'))
            assert terminal == read(stage_folder/'terminal.json')
            assert terminal['state_sha256'] == state_hash(terminal['final_state'])
            assert terminal['production_nodes'] == 256 and terminal['refined_nodes'] == 512
            assert terminal['accepted_steps'] <= 12
            gradient = terminal.get('gradient')
            if gradient:
                assert gradient['state_sha256'] == terminal['state_sha256'] and gradient['active_frequencies_hz'] == saved.TRAIN
            row.update(accepted_steps=terminal['accepted_steps'], optimizer_stop=terminal['optimizer_stop'],
                       convergence=terminal['convergence'], terminal_gradient=gradient)
            if (stage_folder/'acceptance.json').exists():
                for acceptance in read(stage_folder/'acceptance.json'):
                    if acceptance['accepted']:
                        assert min(acceptance['production_gain'], acceptance['refined_gain']) > acceptance['margin']+acceptance['disagreement_allowance']
            if (stage_folder/'trajectory.jsonl').exists():
                trajectory = [json.loads(line) for line in (stage_folder/'trajectory.jsonl').read_text().splitlines()]
                assert all(b['loss'] <= a['loss']+1e-15 for a,b in zip(trajectory, trajectory[1:]))
            if 'score' in stage:
                record = read(stage_folder/'endpoint_predictions.json')
                assert stage['score'] == record['score'] and record['state_sha256'] == terminal['state_sha256'] == stage['score_state_sha256']
                assert schedule['final'] == record['score'] and schedule['final_state_sha256'] == terminal['state_sha256']
                endpoints.append((arm, record))
                row['endpoint'] = saved.score_row(arm, record['score'], record['state_sha256'])
        if (folder/'first_step_reproducibility.json').exists():
            check = read(folder/'first_step_reproducibility.json'); witness = read(output/'witnesses.json')[arm]
            assert check['witness_state_sha256'] == state_hash(witness['state'])
            assert check['state_sha256'] == state_hash(check['state'])
            delta = max(abs(a-b) for ca,cb in zip(check['state'],witness['state']) for a,b in zip(ca['parameters'],cb['parameters']))
            relative = abs(check['production_loss']-witness['production_loss'])/abs(witness['production_loss'])
            assert math.isclose(delta, check['maximum_coefficient_difference_m'], abs_tol=1e-18)
            assert math.isclose(relative, check['relative_objective_difference'], abs_tol=1e-18)
            assert check['status'] == ('PASS' if max(delta, check['maximum_boundary_point_difference_m']) <= 1e-10 and relative <= 1e-8 else 'FAIL')
            row['first_step'] = check['status']
        if result['status'] == 'COMPLETED_SCHEDULE':
            assert worker['exit_code'] == 0 and row['first_step'] == 'PASS'
            assert schedule['schedule_complete'] and [s['stage'] for s in schedule['stages']] == [4]
        expected = bool(schedule.get('schedule_complete') and schedule.get('complete_effective_exposure') and
                        schedule.get('numerically_qualified') and schedule.get('reconstruction_gates_pass'))
        assert result['reconstruction_pass'] == expected
        rows.append(row)
    for _, record in endpoints:
        assert record['state_sha256'] == state_hash(record['state']) == record['score']['state_sha256']
        saved.verify_prediction_scores(record, record['score'], train, original)
    assert total <= 8000
    return dict(status='PASS', outcome=classify(rows), new_physical_solves=0, rows=rows,
        total_attempted_calls=total, accounting_complete=complete_counts, endpoints_verified=len(endpoints),
        source_files=len(manifest['source_sha256']), fresh_recovery_claim=False, full_suite_released=False), endpoints


def figure(output, endpoints):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    scene = next(s for s in read(output/'inputs/scene_spec.json')['scenes'] if s['id']=='far-two-stars')
    fig, axes = plt.subplots(1, len(endpoints), figsize=(5*len(endpoints),4.6), squeeze=False)
    for axis, (label, record) in zip(axes[0], endpoints):
        for index, item in enumerate(scene['truth']):
            t = [2*math.pi*i/1024 for i in range(1025)]
            radius = [item['mean_radius']*(1+item['amplitude']*math.cos(item['lobes']*(x-item['rotation']))) for x in t]
            axis.plot([item['center'][0]+r*math.cos(x) for r,x in zip(radius,t)],
                      [item['center'][1]+r*math.sin(x) for r,x in zip(radius,t)], '--', color='#475569', label='Target' if index==0 else None)
        for index, component in enumerate(record['state']):
            axis.plot(*zip(*saved.curve_points(component)), color='#0d9488', label='Saved boundary' if index==0 else None)
        score = record['score']
        axis.set(title=f"{label}\nBoundary {1000*score['geometry']['maximum_matched_hausdorff_m']:.3f} mm; IoU {score['geometry']['union_iou']:.3f}",
                 aspect='equal', xlim=(.30,.67), ylim=(.37,.66), xlabel='x (m)', ylabel='y (m)')
        axis.grid(alpha=.2); axis.legend(fontsize=8)
    fig.suptitle('TOP-024 · 12-update archived-terminal damping comparison')
    fig.tight_layout(); fig.savefig(output/'endpoints.png', dpi=140); fig.savefig(output/'endpoints.svg', metadata={'Date':None}); plt.close(fig)


def summarize(output):
    result, endpoints = verify(output)
    write(output/'verification.json', result); write(output/'scorecard.json', result)
    figure(output, endpoints)
    write(output/'artifact_manifest.json', {str(path.relative_to(output)):digest(path)
        for path in sorted(output.rglob('*')) if path.is_file() and path.name != 'artifact_manifest.json'})
    return {key:value for key,value in result.items() if key != 'rows'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(summarize(parser.parse_args().output.resolve())))
