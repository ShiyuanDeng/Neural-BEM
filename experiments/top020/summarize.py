"""TOP-020 artifact replay and figures, with no solver imports or calls."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top019 import summarize as saved

read, write, digest, state_hash = saved.read, saved.write, saved.digest, saved.state_hash


def verify(output):
    manifest = read(output/'manifest.json')
    saved.verify_inputs(output, {**manifest, 'historical_sha256': manifest['historical_input_sha256']})
    for name, sha in read(output/'artifact_manifest.json').items():
        assert digest(output/name) == sha, name
    central = manifest['central_control']
    assert digest(ROOT/central['path']/'result.json') == central['result_sha256']
    result = read(output/'result.json')
    contract = read(output/'contract.json')
    stage_quotas = dict(contract['stage_plan'])
    train = read(output/'inputs/training_observations.json')
    original = read(output/'inputs/observations.json')
    endpoints = []
    if (output/'initial_endpoint_predictions.json').exists():
        initial = read(output/'initial_endpoint_predictions.json')
        endpoints.append(('Automatic endpoint', initial))
    schedule = result.get('schedule', {})
    previous = read(output/'handoff.json')['state_sha256'] if (output/'handoff.json').exists() else None
    for stage in schedule.get('stages', []):
        number = stage['stage']; terminal = stage['terminal']
        folder = output/'continuation'/f'stage_{number}'
        assert stage['start_state_sha256'] == previous
        assert terminal['state_sha256'] == state_hash(terminal['final_state'])
        assert terminal['production_nodes'] == 256 and terminal['refined_nodes'] == 512
        assert stage['active_frequencies_hz'] == saved.TRAIN[:number]
        assert state_hash(read(folder/'initial_state.json')) == previous
        assert read(folder/'terminal.json') == terminal
        gradient = terminal.get('gradient')
        if gradient is not None:
            assert gradient['state_sha256'] == terminal['state_sha256']
            assert gradient['active_frequencies_hz'] == saved.TRAIN[:number]
        previous = terminal['state_sha256']
        if 'score' in stage:
            record = read(folder/'endpoint_predictions.json')
            assert record['score'] == stage['score']
            assert stage['score_state_sha256'] == previous
            endpoints.append((f'Stage {number}', record))
            assert stage['work_after_endpoint']['stage_attempted'] <= stage_quotas[number]
        if (folder/'acceptance.json').exists():
            for row in read(folder/'acceptance.json'):
                if row['accepted']:
                    assert min(row['production_gain'], row['refined_gain']) > row['margin'] + row['disagreement_allowance']
        trajectory = folder/'trajectory.jsonl'
        if trajectory.exists():
            rows = [json.loads(line) for line in trajectory.read_text().splitlines()]
            assert all(b['loss'] <= a['loss']+1e-15 for a, b in zip(rows, rows[1:]))
    for label, record in endpoints:
        assert record['state_sha256'] == state_hash(record['state']) == record['score']['state_sha256']
        saved.verify_prediction_scores(record, record['score'], train, original)
    if schedule.get('schedule_complete'):
        assert [s['stage'] for s in schedule['stages']] == [number for number, _ in contract['stage_plan']]
        assert schedule['final'] == endpoints[-1][1]['score']
        assert schedule['final_state_sha256'] == previous == state_hash(schedule['final_state'])
    if (output/'topology/terminal.json').exists():
        terminal = read(output/'topology/terminal.json')
        events = read(output/'topology/events.json')
        rows = [json.loads(line) for line in (output/'topology/trajectory.jsonl').read_text().splitlines()]
        assert all(b['loss'] <= a['loss']+1e-12*max(1, abs(a['loss'])) for a, b in zip(rows, rows[1:]))
        control = contract['topology_controller']
        for event in events:
            dp = event['production_before']-event['production_after']
            dr = event['refined_before']-event['refined_after']
            margin = control['acceptance_absolute_margin'] + control['acceptance_relative_margin']*event['production_before']
            assert min(dp, dr) > margin + control['cross_resolution_factor']*abs(dp-dr)
        if (output/'handoff.json').exists():
            handoff = read(output/'handoff.json')
            assert handoff['source_state_sha256'] == state_hash(terminal['final_state'])
            assert handoff['state_sha256'] == state_hash(handoff['state'])
            assert handoff['zero_padding_maximum_point_change_m'] <= 1e-10
    works = [result['topology_work']] + ([] if result['continuation_work'] is None else [result['continuation_work']])
    for work, cap, seconds in zip(works, (4000, 8012), (600, 7200)):
        assert work['total_attempted'] == sum(work['attempted'].values()) == sum(work['per_frequency_attempted'].values()) <= cap
        assert work['total_attempted'] == sum(work['completed'].values())+sum(work['failed'].values())
        for key in ('completed', 'failed'):
            assert sum(work[key].values()) == sum(work['per_frequency_'+key].values())
        assert work['active_wall_seconds'] <= seconds + 1  # serialization/timer unwind allowance only
    assert result['total_attempted_frequency_calls'] == sum(w['total_attempted'] for w in works) <= 12012
    assert result['completed_frequency_solves'] == sum(sum(w['completed'].values()) for w in works)
    assert result['failed_or_refused_calls'] == sum(sum(w['failed'].values()) for w in works)
    expected = bool(schedule.get('schedule_complete') and schedule.get('complete_effective_exposure') and
        schedule.get('numerically_qualified') and schedule.get('reconstruction_gates_pass') and
        all(result.get('topology_checks', {}).values()) and result['sources_and_inputs_unchanged'])
    assert result['fresh_recovery_pass'] == expected
    return dict(status='PASS', endpoints_verified=len(endpoints), source_files=len(manifest['source_sha256']),
        new_physical_solves=0, fresh_recovery_pass=expected,
        total_attempted_frequency_calls=result['total_attempted_frequency_calls']), endpoints


def figure(output, endpoints, experiment='TOP-020'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    scene = next(s for s in read(output/'inputs/scene_spec.json')['scenes'] if s['id']=='far-two-stars')
    targets = []
    for item in scene['truth']:
        assert item['kind'] == 'star'
        points = []
        for i in range(1025):
            t = 2*math.pi*i/1024
            radius = item['mean_radius']*(1+item['amplitude']*math.cos(item['lobes']*(t-item['rotation'])))
            points.append((item['center'][0]+radius*math.cos(t), item['center'][1]+radius*math.sin(t)))
        targets.append(points)
    states = [('Original circle', read(output/'inputs/initial_state.json'))]
    if endpoints:
        states += [(endpoints[0][0], endpoints[0][1]['state']), (endpoints[-1][0], endpoints[-1][1]['state'])]
    fig, axes = plt.subplots(1, len(states), figsize=(5*len(states), 4.6), squeeze=False)
    for axis, (label, state) in zip(axes[0], states):
        for i, target in enumerate(targets):
            axis.plot(*zip(*target), '--', color='#475569', linewidth=1.5, label='Target' if i==0 else None)
        for i, component in enumerate(state or []):
            axis.plot(*zip(*saved.curve_points(component)), color='#0d9488', linewidth=1.6,
                label='Saved boundary' if i==0 else None)
        axis.set(title=label, aspect='equal', xlim=(.30, .67), ylim=(.37, .66), xlabel='x (m)', ylabel='y (m)')
        axis.grid(alpha=.2); axis.legend(fontsize=8)
    fig.suptitle(experiment+' · Fresh automatic two-star recovery')
    fig.tight_layout()
    fig.savefig(output/'endpoints.svg', metadata={'Date': None})
    fig.savefig(output/'endpoints.png', dpi=140)
    plt.close(fig)
    write(output/'figure_manifest.json', dict(new_physical_solves=0,
        states={name: state_hash(state) for name, state in states}, truth_source='inputs/scene_spec.json'))


def summarize(output):
    verification, endpoints = verify(output)
    result = read(output/'result.json')
    rows = [saved.score_row(label, record['score'], record['state_sha256']) for label, record in endpoints]
    write(output/'scorecard.json', dict(outcome='FRESH_RECOVERY_PASS' if result['fresh_recovery_pass'] else
        'FRESH_RECOVERY_NOT_QUALIFIED', rows=rows, work={key: result[key] for key in
        ('total_attempted_frequency_calls', 'completed_frequency_solves', 'geometry_refused_calls',
         'failed_or_refused_calls', 'active_wall_seconds')}))
    write(output/'verification.json', verification)
    figure(output, endpoints, read(output/'contract.json').get('experiment', 'TOP-020'))
    write(output/'artifact_manifest.json', {str(x.relative_to(output)): digest(x)
        for x in sorted(output.rglob('*')) if x.is_file() and x.name != 'artifact_manifest.json'})
    return verification


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(summarize(parser.parse_args().output.resolve())))
