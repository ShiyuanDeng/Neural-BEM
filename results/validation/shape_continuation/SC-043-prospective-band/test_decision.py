import importlib.util
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('sc043_test', Path(__file__).with_name('run.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def test_band_subselection_preserves_cos_sin_orders():
    low, high = 2, 5
    labels = ['constant']+[f'cos{i}' for i in range(1,high+1)]+[f'sin{i}' for i in range(1,high+1)]
    assert [labels[i] for i in r.columns(low,high)] == ['constant','cos1','cos2','sin1','sin2']


def test_release_requires_material_increment_not_just_larger_space():
    assert not r.choose(.80, .85, 1.)
    assert r.choose(.10, .80, 1.)
    assert not r.choose(0., 1e-16, 1e-16)


def test_complete_physical_metric_subspace_matches_separate_preparation():
    curve, stages, config, _, _ = r.c.stages_for('circle_to_star', 'cap')
    curve, _ = r.c.treatment(curve, 'cap', 0)
    update = r.c.reference.ProjectedUpdate(r.c.sc.LENGTH)
    low, high = 3, 5
    a,b = [update.prepare(curve,m,64) for m in (low,high)]
    nodes = curve.nodes(512)
    subset = r.columns(low,high)
    assert np.allclose(update.velocities(a,nodes),update.velocities(b,nodes)[:,subset],rtol=1e-8,atol=1e-8)
    assert np.allclose(update.metric(a,'mass'),update.metric(b,'mass')[np.ix_(subset,subset)],rtol=1e-8,atol=1e-8)
