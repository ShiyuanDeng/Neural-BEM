"""Fresh integration contracts and artifact boundaries; no physical solves."""
import copy
import inspect
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.top020 import run as r
from experiments.top019 import summarize as replay


@pytest.fixture
def inputs(tmp_path):
    for name, source in {'scene_spec.json':r.p.DATA/'scene_spec.json',
        'initial_state.json':r.p.DATA/'scenes'/r.SCENE/'initial_state.json',
        'observations.json':r.follow.HISTORY/'inputs'/r.SCENE/'observations.json',
        'training_observations.json':r.follow.HISTORY/'inputs'/r.SCENE/'training_observations.json'}.items():
        shutil.copyfile(source, tmp_path/name)
    return tmp_path


def test_original_circle_and_observation_provenance(inputs):
    initial, observed, evaluation, scene, spec = r.load_inputs(inputs)
    assert initial.component_ids == ('initial.circle',)
    assert observed.shape == (24, 4) and evaluation.shape == (24, 2)
    assert scene['initial'][0]['center'] == [.4, .57]
    assert r.verify_central()['fresh_recovery_pass']


@pytest.mark.parametrize('filename', ['initial_state.json', 'observations.json', 'training_observations.json'])
def test_modified_frozen_input_is_refused(inputs, filename):
    data = r.read(inputs/filename)
    if filename == 'initial_state.json': data[0]['parameters'][0] += .001
    else: data['observed_real'][0][0] += 1
    r.write(inputs/filename, data)
    with pytest.raises((r.m.ImplementationError, AssertionError)):
        r.load_inputs(inputs)


def test_count_independent_handoff_qualifies_the_declared_nodes(inputs, monkeypatch):
    initial, _, _, _, spec = r.load_inputs(inputs)
    control = r.p.benchmark.controller_config(spec, 'H')
    seen = []
    def feasible(state, nodes, solve, floor):
        seen.append((nodes, floor)); return True
    monkeypatch.setattr(r.p, 'feasible', feasible)
    padded, optimizer, delta = r.continuation_start(initial, control, None)
    assert len(padded.components) == 1 and padded.components[0].maximum_mode == 9
    assert seen == [((256, 512), .008)] and delta <= 1e-10
    assert optimizer.max_parameters >= padded.parameter_count
    assert len(optimizer.max_steps) == padded.parameter_count and optimizer.loss_tolerance == 1e-14
    assert not {'truth', 'scene', 'count', 'evaluation'} & set(inspect.signature(r.continuation_start).parameters)
    monkeypatch.setattr(r.p, 'feasible', lambda *args:False)
    with pytest.raises(r.m.NumericalFailure): r.continuation_start(initial, control, None)


@pytest.mark.parametrize('bad', ['loss', 'margin'])
def test_event_checks_fail_closed(tmp_path, inputs, bad):
    _, _, _, _, spec = r.load_inputs(inputs)
    control = r.p.benchmark.controller_config(spec, 'H')
    rows = [{'loss': 1.}, {'loss': 2. if bad == 'loss' else .5}]
    (tmp_path/'trajectory.jsonl').write_text('\n'.join(json.dumps(x) for x in rows))
    r.write(tmp_path/'events.json', [dict(production_before=1, production_after=.5,
        refined_before=1, refined_after=.9 if bad == 'margin' else .5)])
    with pytest.raises(r.m.ImplementationError): r.topology_checks(tmp_path, control)


def test_scores_replay_saved_predictions_and_separate_geometry_from_numerics(inputs, monkeypatch):
    initial, observed, evaluation, scene, spec = r.load_inputs(inputs)
    geometry = dict(component_count=1, truth_component_count=2, maximum_matched_hausdorff_m=.1,
        union_iou=.1, matched_components=[])
    monkeypatch.setattr(r.p.benchmark, 'geometry_metrics', lambda *args:geometry)
    full = np.hstack((observed, evaluation))
    predictions = {256: full.copy(), 512: full.copy()}
    score = r.score_predictions(initial, scene, spec, observed, evaluation, predictions)
    assert score['numerically_qualified'] and not score['original_gates_pass']
    record = dict(predictions={str(n):dict(real=v.real.tolist(), imag=v.imag.tolist()) for n, v in predictions.items()})
    r.write(inputs/'score.json', score); score = r.read(inputs/'score.json')
    replay.verify_prediction_scores(record, score, r.read(inputs/'training_observations.json'), r.read(inputs/'observations.json'))
    bad = copy.deepcopy(score); bad['training_errors'][1] = .2
    with pytest.raises(AssertionError):
        replay.verify_prediction_scores(record, bad, r.read(inputs/'training_observations.json'), r.read(inputs/'observations.json'))
    predictions[256] = full*1.00001
    score = r.score_predictions(initial, scene, spec, observed, evaluation, predictions)
    assert not score['numerically_qualified']


def test_initial_scoring_reserves_twelve_solves_before_call(inputs, monkeypatch):
    initial, observed, evaluation, scene, spec = r.load_inputs(inputs)
    monkeypatch.setattr(r.p, 'prediction', lambda *args:pytest.fail('unreserved physical work'))
    with pytest.raises(r.m.TrialSolveCap):
        r.score_endpoint(initial, scene, spec, observed, evaluation, None,
            r.m.Ledger(cap=11), inputs/'predictions.json')


def test_dispatch_refuses_unqualified_sources_before_creating_output(tmp_path):
    r.write(tmp_path/'validation.json', dict(status='PASS', source_sha256={}))
    output = tmp_path/'run'
    with pytest.raises(r.m.ImplementationError, match='sources'):
        r.prepare(output, tmp_path/'validation.json')
    assert not output.exists()


def test_output_and_source_guards(tmp_path):
    with pytest.raises(r.m.ImplementationError, match='fresh'):
        r.prepare(tmp_path, tmp_path/'absent.json')
    source = tmp_path/'input'; source.write_text('original')
    hashes = {'input':r.p.digest(source)}
    r.verified_hashes(tmp_path, hashes)
    source.write_text('changed')
    with pytest.raises(r.m.ImplementationError): r.verified_hashes(tmp_path, hashes)
