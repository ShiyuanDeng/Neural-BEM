"""The expanded benchmark must preserve controls and reject misleading fits."""
import numpy as np
import pytest

import run_fourier_topology_controller as old
import run_topology_scene_benchmark as benchmark


@pytest.mark.parametrize('case', old.CASES)
def test_frozen_original_scenes_preserve_initial_states_and_truth(case):
    spec = benchmark.read(benchmark.DEFAULT_SPEC)
    scene = next(s for s in spec['scenes'] if s['id']==case)
    original, truth, _ = old.case_spec(case, chart='cartesian')
    current = benchmark.initial_state(scene)
    if original is None:
        assert current is None
    if original is not None:
        assert current.component_ids == original.component_ids
        np.testing.assert_array_equal(current.parameter_vector(), original.parameter_vector())
    for a, b in zip(benchmark.truth_curves(scene), truth):
        np.testing.assert_allclose(a.discretize(256).points, b.discretize(256).points, atol=1e-15, rtol=0)


def test_requested_initial_circle_is_large_disjoint_and_inside_search_domain():
    spec = benchmark.read(benchmark.DEFAULT_SPEC)
    scene = next(s for s in spec['scenes'] if s['id']=='far-ellipse-star')
    check = benchmark.scene_geometry_check(scene, spec)
    assert check['valid']
    assert check['minimum_initial_truth_boundary_gap_m'] > .06
    assert scene['initial'][0]['cosine'][0] == .075
    assert [s['kind'] for s in scene['truth']] == ['ellipse', 'star']


def test_count_and_geometry_are_required_even_with_zero_prediction_error():
    spec = benchmark.read(benchmark.DEFAULT_SPEC)
    checks = dict(monotone_accepted_states=True, all_event_margins_pass=True)
    geometry = dict(component_count=1, truth_component_count=2,
        maximum_matched_hausdorff_m=0., union_iou=1.)
    gates = benchmark.success_gates(geometry, 0., 0., checks, spec)
    assert not gates['correct_count']
    assert not all(gates.values())
    geometry.update(component_count=2, maximum_matched_hausdorff_m=.002, union_iou=.8)
    gates = benchmark.success_gates(geometry, 0., 0., checks, spec)
    assert gates['correct_count'] and not gates['boundary'] and not gates['overlap']


def test_geometry_assignment_is_independent_of_ids_and_component_order():
    spec = benchmark.read(benchmark.DEFAULT_SPEC)
    spec.update(geometry_samples=128, iou_grid_size=101)
    scene = dict(truth=[dict(kind='circle', center=[.44,.5], radius=.033, component_id='a'),
                       dict(kind='circle', center=[.56,.5], radius=.033, component_id='b')])
    state = old.MultiRadialFourierState((old.circle(.56,.5,.033,'first'), old.circle(.44,.5,.033,'second')))
    metrics = benchmark.geometry_metrics(state, scene, spec)
    assert metrics['maximum_matched_hausdorff_m'] < 1e-14
    assert metrics['union_iou'] == 1.
    assert [r['truth_component'] for r in metrics['matched_components']] == ['b', 'a']


def test_empty_reconstruction_is_a_finite_failure_and_arms_differ_only_in_policy():
    spec = benchmark.read(benchmark.DEFAULT_SPEC)
    spec.update(geometry_samples=64, iou_grid_size=51)
    metrics = benchmark.geometry_metrics(None, spec['scenes'][0], spec)
    assert metrics['component_count']==0 and metrics['union_iou']==0
    assert metrics['maximum_matched_hausdorff_m'] is None
    a = benchmark.asdict(benchmark.controller_config(spec, 'A'))
    f = benchmark.asdict(benchmark.controller_config(spec, 'F'))
    assert {key for key in a if a[key] != f[key]} == {'include_simplest_candidate'}


def test_holdout_reports_each_frequency_instead_of_hiding_bad_column():
    observed = np.array([[1., 100.]])
    predicted = np.array([[2., 100.]])
    np.testing.assert_array_equal(benchmark.relative_columns(predicted, observed), [1., 0.])


def test_failed_run_keeps_last_geometry_and_complete_progress_records(tmp_path):
    import json
    state = old.MultiRadialFourierState((old.circle(.5,.5,.03,'last'),))
    record = dict(state=old.serialize_state(state), loss=.1, cycle=2, label='refine 1')
    old.write_json(tmp_path/'checkpoint.json', record)
    old.write_json(tmp_path/'failure.json', dict(reason='timeout'))
    line = json.dumps(record, default=lambda value: value.tolist())
    (tmp_path/'progress.jsonl').write_text(line+'\n'+line+'\n{"state":')
    loaded = benchmark.saved_run_state(tmp_path, None)
    np.testing.assert_array_equal(loaded.parameter_vector(), state.parameter_vector())
    frames = benchmark.saved_run_frames(tmp_path)
    assert len(frames)==2 and frames[-1].label.startswith('FAILED')
    np.testing.assert_array_equal(frames[-1].state.parameter_vector(), state.parameter_vector())


def test_reference_reuse_copies_exact_observations_without_oracle_calls(tmp_path, monkeypatch):
    spec = benchmark.read(benchmark.DEFAULT_SPEC)
    spec['scenes'] = spec['scenes'][:1]
    reference, output = tmp_path/'reference', tmp_path/'output'
    reference.mkdir(); output.mkdir()
    old.write_json(reference/'scene_spec.json', spec)
    old.write_json(reference/'manifest.json', dict(source='test fixture'))
    scene = spec['scenes'][0]
    path = reference/'scenes'/scene['id']
    path.mkdir(parents=True)
    frequencies = spec['training_frequencies_hz']+spec['holdout_frequencies_hz']
    problem = old.baseline._problem(np.asarray(frequencies))
    observed = np.ones((len(problem.source_points), len(frequencies)), dtype=complex)
    record = dict(frequencies_hz=frequencies, source_points=problem.source_points,
        receiver_points=problem.receiver_points, source_strengths_real=problem.source_strengths.real,
        source_strengths_imag=problem.source_strengths.imag,
        observed_real=observed.real, observed_imag=observed.imag,
        exterior=benchmark.asdict(problem.exterior), interior=benchmark.asdict(problem.interior),
        eps0=problem.eps0, mu0=problem.mu0)
    for name, value in [('scene',scene), ('observations',record), ('initial_state',None),
                        ('oracle_check',dict(passed=True)), ('geometry_check',dict(valid=True))]:
        old.write_json(path/f'{name}.json',value)
    def no_oracle(*args, **kwargs):
        raise AssertionError('Reference reuse must not generate new observations.')
    monkeypatch.setattr(benchmark,'predict_multicomponent_kress_paired_boundary_response',no_oracle)
    monkeypatch.setattr(old.baseline,'_oracle_response',no_oracle)
    benchmark.reuse_reference_data(output,reference,spec)
    assert (path/'observations.json').read_bytes()==(output/'scenes'/scene['id']/'observations.json').read_bytes()
    assert benchmark.read(output/'reference_data.json')['new_oracle_solves']==0
    record['exterior']['epsr'] = 99.
    old.write_json(output/'scenes'/scene['id']/'observations.json',record)
    with pytest.raises(ValueError, match='material'):
        benchmark.shared_data(output,scene,spec)


def test_reference_reuse_refuses_changed_scene_specification(tmp_path):
    reference, output = tmp_path/'reference', tmp_path/'output'
    reference.mkdir(); output.mkdir()
    old.write_json(reference/'scene_spec.json',dict(version='different'))
    with pytest.raises(ValueError, match='identical frozen scene'):
        benchmark.reuse_reference_data(output,reference,dict(version='v1'))


def test_frozen_v1_acquisition_is_the_default_and_did_not_move():
    """v1 names no acquisition, so every v1 bundle must reproduce from defaults."""
    spec = benchmark.read(benchmark.DEFAULT_SPEC)
    assert 'acquisition' not in spec
    sources, receivers = old.baseline._ring_scan()
    assert sources.shape == (old.baseline.RING_POSITIONS, 2) == (24, 2)
    default_sources, default_receivers = old.baseline._acquisition_scan(None)
    np.testing.assert_array_equal(sources, default_sources)
    np.testing.assert_array_equal(receivers, default_receivers)
    radii = np.linalg.norm(sources - np.asarray(old.baseline.SCENE_CENTER), axis=1)
    np.testing.assert_allclose(radii, old.baseline.RING_STANDOFF_M)


def test_v2_acquisition_adds_positions_without_moving_the_v1_ones():
    """Route A must be added angular coverage, not relocated coverage."""
    v1 = benchmark.read(benchmark.DEFAULT_SPEC)
    v2 = benchmark.read(benchmark.ROOT/'config/topology_scenes_v2.json')
    assert v2['acquisition'] == dict(ring_positions=48, standoff_m=0.30)
    assert {k: v for k, v in v2.items() if k not in ('version', 'acquisition')} == \
           {k: v for k, v in v1.items() if k != 'version'}
    assert v2['training_frequencies_hz'] == v1['training_frequencies_hz']
    assert v2['holdout_frequencies_hz'] == v1['holdout_frequencies_hz']
    assert v2['gates'] == v1['gates'] and v2['controller'] == v1['controller']
    base_sources, base_receivers = old.baseline._acquisition_scan(None)
    sources, receivers = old.baseline._acquisition_scan(v2['acquisition'])
    assert len(sources) == 48
    np.testing.assert_allclose(sources[::2], base_sources)
    np.testing.assert_allclose(receivers[::2], base_receivers)


def test_unknown_acquisition_key_is_refused_rather_than_ignored():
    with pytest.raises(ValueError, match='Unknown acquisition keys'):
        old.baseline._acquisition_scan(dict(ring_position=48))
    with pytest.raises(ValueError, match='positive number'):
        old.baseline._ring_scan(positions=0)
    with pytest.raises(ValueError, match='finite positive radius'):
        old.baseline._ring_scan(standoff=0.0)


def test_shared_data_rebuilds_the_specification_acquisition(tmp_path):
    """Observations saved under one acquisition must not load under another."""
    spec = benchmark.read(benchmark.ROOT/'config/topology_scenes_v2.json')
    spec['scenes'] = spec['scenes'][:1]
    scene = spec['scenes'][0]
    path = tmp_path/'scenes'/scene['id']
    path.mkdir(parents=True)
    frequencies = spec['training_frequencies_hz']+spec['holdout_frequencies_hz']
    problem = old.baseline._problem(np.asarray(frequencies), acquisition=spec['acquisition'])
    assert len(problem.source_points) == 48
    observed = np.ones((len(problem.source_points), len(frequencies)), dtype=complex)
    old.write_json(path/'observations.json', dict(frequencies_hz=frequencies,
        source_points=problem.source_points, receiver_points=problem.receiver_points,
        source_strengths_real=problem.source_strengths.real,
        source_strengths_imag=problem.source_strengths.imag,
        observed_real=observed.real, observed_imag=observed.imag,
        exterior=benchmark.asdict(problem.exterior), interior=benchmark.asdict(problem.interior),
        eps0=problem.eps0, mu0=problem.mu0))
    training, holdout = benchmark.shared_data(tmp_path, scene, spec)
    assert len(training.forward_problem.source_points) == 48
    assert len(holdout.forward_problem.angular_frequencies) == len(spec['holdout_frequencies_hz'])
    v1_spec = dict(spec)
    v1_spec.pop('acquisition')
    with pytest.raises(AssertionError):
        benchmark.shared_data(tmp_path, scene, v1_spec)
