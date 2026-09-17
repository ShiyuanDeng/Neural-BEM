"""Promoted defaults reach workers, readiness, reporting, and comparison paths."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from experiments.top025 import run as pipeline, readiness, summarize, render
from sdf_inverse.runtime import (add_runtime_argument, configure_runtime_argument,
                                 inverse_runtime, runtime_metadata)
from test_spd004 import stubbed

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT/'results/validation/speedup/SPD-006-20260916-full-inverse/compiled_0'


def test_default_cli_context_and_fresh_process_select_compiled_readiness(monkeypatch):
    monkeypatch.delenv('SDF_INVERSE_RUNTIME', raising=False)
    parser = argparse.ArgumentParser()
    add_runtime_argument(parser)
    selected = configure_runtime_argument(parser.parse_args([]))
    assert selected['profile'] == selected['continuation_backend'] == 'compiled'
    assert selected['shape_derivative'] == 'reciprocal' and selected['continuation_readiness']
    assert selected['analytic_constraint_policy'] == 'fd_compatible'
    with inverse_runtime():
        assert runtime_metadata() == selected
    spawned = json.loads(subprocess.check_output([sys.executable, '-c',
        'import json; from sdf_inverse.runtime import runtime_metadata; print(json.dumps(runtime_metadata()))'],
        env=os.environ, text=True))
    assert spawned == selected
    for profile in ('fast', 'reciprocal', 'reference'):
        explicit = configure_runtime_argument(parser.parse_args(['--inverse-runtime', profile]))
        assert explicit['profile'] == profile and not explicit['continuation_readiness']


def test_default_full_continuation_routes_once_and_keeps_independent_checks(tmp_path, monkeypatch, stubbed):
    monkeypatch.delenv('SDF_INVERSE_RUNTIME', raising=False)
    monkeypatch.setattr(pipeline, 'run_scheduled_continuation', lambda *a:pytest.fail('ready state fitted'))
    monkeypatch.setattr(pipeline.base, 'score_predictions',
                        lambda *a:dict(original_gates_pass=True, numerically_qualified=True))
    result = pipeline.run_continuation(tmp_path/'F', object(), None, np.ones((24, 4)),
        object(), object(), object(), SimpleNamespace(minimum_component_radius_m=.008), None)
    assert result['skipped_continuation'] and result['fresh_recovery_pass']
    assert result['work']['total_attempted'] == 12
    assert [c[0] for c in stubbed].count('readiness') == 2
    assert [c[0] for c in stubbed].count('endpoint') == 2


@pytest.mark.parametrize('profile', ['fast', 'reciprocal', 'reference'])
def test_explicit_comparison_profiles_bypass_readiness(profile, monkeypatch):
    monkeypatch.setattr(readiness, 'readiness_continuation', lambda *a:pytest.fail('comparison screened'))
    sentinel = object()
    monkeypatch.setattr(pipeline, 'run_scheduled_continuation', lambda *a:sentinel)
    with inverse_runtime(profile):
        assert pipeline.run_continuation(*([None]*9)) is sentinel


def test_context_profile_propagates_to_campaign_worker(tmp_path, monkeypatch):
    monkeypatch.setenv('SDF_INVERSE_RUNTIME', 'reference')
    seen = []
    def worker(command, **kwargs):
        seen.append(kwargs['env'])
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(pipeline.subprocess, 'run', worker)
    with inverse_runtime('compiled'):
        pipeline.write(tmp_path/'contract.json', dict(inverse_runtime=runtime_metadata()))
        pipeline.run_job(tmp_path, 'death', pipeline.time.monotonic()+60)
    assert seen[0]['SDF_INVERSE_RUNTIME'] == 'compiled'
    assert seen[0]['OPENBLAS_NUM_THREADS'] == '1'
    assert os.environ['SDF_INVERSE_RUNTIME'] == 'reference'


def test_saved_ready_endpoint_replays_and_corrupt_decision_fails(tmp_path):
    scene = EVIDENCE/'runs/death'
    result = pipeline.read(scene/'F/result.json')
    train = pipeline.read(EVIDENCE/'inputs/death/training_observations.json')
    original = pipeline.read(EVIDENCE/'inputs/death/observations.json')
    assert summarize.verify_readiness(scene/'F', result, train, original)
    folder = tmp_path/'F'
    folder.mkdir()
    screening = pipeline.read(scene/'readiness.json')
    screening['predictions']['256']['real'][0][-1] += 1.
    pipeline.write(tmp_path/'readiness.json', screening)
    pipeline.write(folder/'endpoint_predictions.json', pipeline.read(scene/'F/endpoint_predictions.json'))
    with pytest.raises(AssertionError):
        summarize.verify_readiness(folder, result, train, original)


def test_combined_accounting_reconciles_real_compiled_and_reciprocal_work():
    for name in ('death', 'merge', 'central-ellipse-star'):
        saved = pipeline.read(EVIDENCE/'runs'/name/'F/result.json')['work']
        work = readiness.combine_work(saved['parts'], saved['active_wall_seconds'])
        summarize.verify_work(work)
        assert work['budget_work_units'] == saved['budget_work_units']
        if name == 'merge':
            assert sum(work['reciprocal_batches_completed'].values()) > 0
        if name == 'central-ellipse-star':
            assert sum(work['compiled_batches_completed'].values()) > 0
    broken = copy.deepcopy(work)
    broken['compiled_batches_completed'] = {}
    with pytest.raises(AssertionError):
        summarize.verify_work(broken)


def test_ready_video_ends_at_scored_padded_handoff(tmp_path):
    source = EVIDENCE/'runs/death'
    inputs = tmp_path/'inputs/death'
    folder = tmp_path/'runs/death'
    inputs.mkdir(parents=True)
    (folder/'F').mkdir(parents=True)
    pipeline.write(inputs/'initial_state.json', pipeline.read(EVIDENCE/'inputs/death/initial_state.json'))
    record = pipeline.read(source/'F/result.json')
    pipeline.write(folder/'F/result.json', record)
    data = render.collect(tmp_path, 'death')
    assert data['catalog'][-1]['state_sha256'] == record['schedule']['final_state_sha256']
    assert any('Training readiness' in phase for _, phase in data['timeline'])
