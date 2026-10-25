"""Exact-geometry reuse and the band-matched nodal profile seed."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import numpy as np
import pytest
from bem_inverse.physics import Execution, NodalKress
from bem_inverse.nodal_geometry import GeometryCache
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.geometry_update_methods.spline import ProjectedUpdate
from bem_inverse.continuation.geometry import resize
from bem_inverse.continuation.geometry_runtime import geometry_runtime
from gpr_bem_kress import cuda_assembly as CA


def test_exact_keys_concurrent_publication_and_eviction():
    cache = GeometryCache(capacity=2)
    shape = FourierCurve.circle(.065)
    with ThreadPoolExecutor(4) as pool:
        rows = list(pool.map(lambda _: cache.get(shape, 130, 'cpu', enabled=True), range(8)))
    assert all(row[0] is rows[0][0] for row in rows)
    assert cache.receipt()['builds'] == 1 and cache.receipt()['hits'] == 7
    changed = FourierCurve(shape.coefficients+np.array([0, 1e-15, 0]))
    cache.get(changed, 130, 'cpu', enabled=True)
    cache.get(shape, 194, 'cpu', enabled=True)
    assert cache.receipt()['builds'] == 3 and cache.receipt()['evictions'] == 1
    cache.clear()
    assert cache.receipt()['entries'] == cache.receipt()['retained_host_bytes'] == 0
    tiny = GeometryCache(byte_limit=1)
    tiny.get(shape, 130, 'cpu', enabled=True)
    assert tiny.receipt()['bypasses'] == 1 and tiny.receipt()['entries'] == 0


def test_profile_seed_resolves_geometry_and_defaults_keep_floor():
    with pytest.raises(ValueError):
        Execution(resolution=130)
    physics = NodalKress(Execution(nodal_resolution_profile='band_matched', resolution=130))
    assert physics.resolution_profile(8)['production'] == 130
    assert physics.resolution_profile(192)['production'] == 386
    assert NodalKress(Execution()).resolution_profile(8)['production'] == 512



@pytest.mark.skipif(not CA.available(), reason='CUDA unavailable')
@pytest.mark.parametrize('damped', [False, True])
def test_cached_fields_jacobian_and_full_trial_match_reference(damped):
    from experiments.benchmark import campaign as c
    problem = c.problem('peanut__c13.3')
    curve = resize(problem.initial, 8)
    update = ProjectedUpdate(problem.length_unit_m)
    space = update.prepare(curve, 3, 8)
    settings = Execution(device='cuda', frequency_threads=4)
    uncached = NodalKress(settings)
    cached = NodalKress(replace(settings, nodal_geometry_reuse='per_curve'))
    cpu = NodalKress(Execution(device='cpu', acceleration='reference'))
    catalog = problem.damped if damped else problem.real
    with geometry_runtime('both'):
        for observation in (catalog[0], catalog[-1]):
            a = uncached.evaluate(curve, observation, problem.contrast, 194)
            b = cached.evaluate(curve, observation, problem.contrast, 194)
            reference = cpu.evaluate(curve, observation, problem.contrast, 194)
            np.testing.assert_allclose(b.prediction, a.prediction, rtol=1e-11, atol=1e-12)
            np.testing.assert_allclose(b.prediction, reference.prediction, rtol=1e-9, atol=1e-11)
            ja, jb = (p.derivative(x, update, space) for p,x in ((uncached,a),(cached,b)))
            np.testing.assert_allclose(jb, ja, rtol=1e-10, atol=1e-10)
            direction = np.array([1., .2, -.1, .15, -.2, .1, .05]); direction /= np.linalg.norm(direction)
            eps = 1e-7
            predictions = [cached.evaluate(update.geometry_update(sign*eps*direction, prepared=space)[0], observation,
                                           problem.contrast, 194).prediction for sign in (1, -1)]
            fd = (predictions[0]-predictions[1])/(2*eps)
            assert np.linalg.norm(fd-jb@direction)/np.linalg.norm(fd) < 1e-3
    assert cached.receipt()['geometry_cache']['hits'] >= 1
