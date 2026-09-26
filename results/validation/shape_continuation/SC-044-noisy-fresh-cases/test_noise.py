import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('sc044_test',Path(__file__).with_name('run.py'))
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def test_noise_seed_reproduction_and_variance_convention():
    clean=np.ones((100000,3),complex)*np.array([1,2,3])
    a,sigma=r.perturb(clean,.01,44000)
    b,_=r.perturb(clean,.01,44000)
    assert np.array_equal(a,b)
    assert np.allclose(np.sqrt(np.mean(abs(a-clean)**2,axis=0)),.01*np.array([1,2,3]),rtol=.01)
    assert np.allclose(sigma,.01*np.array([1,2,3])/np.sqrt(2))


def test_weights_whiten_known_channel_noise_up_to_common_scale():
    from types import SimpleNamespace
    obs=[SimpleNamespace(scattered=np.array([1,2,3],complex)),SimpleNamespace(scattered=np.array([3,1,1],complex))]
    sigma=np.array([.01,.03])
    weights,expected=r.whitened_weights(obs,sigma)
    norms=np.array([np.linalg.norm(o.scattered) for o in obs])
    whiten=np.sqrt(weights)/norms*sigma
    assert np.allclose(whiten,whiten[0])
    assert np.isclose(expected,sum(o.scattered.size for o in obs)*whiten[0]**2)


def test_fresh_shapes_are_regular_closed_and_distinct():
    for case in r.CASES:
        curve=r.truth(case)
        nodes=curve.validate()
        assert nodes.signed_area>0 and np.min(nodes.speeds)>0
        assert len(curve.coefficients)>3
