"""Bounded checks for replay units, adapters, inverse reference and vector accounting."""
import numpy as np
import pytest
import torch

from bem_inverse.continuation.geometry import FourierCurve, normal_basis
from bem_inverse import geometry as G, spectral as F
from . import gc001 as gc


def test_common_moves_share_physical_units():
    curve = G.resize(FourierCurve.circle(1.3, 10+10j), 8)
    moves = gc.common_moves(curve, 3, 1024)
    basis = normal_basis(curve.nodes(1024), 3)
    assert len(moves) == 9
    for move in moves:
        np.testing.assert_allclose(np.max(np.abs(basis@move['coefficients'])), move['size_m'], rtol=1e-14)
    np.testing.assert_allclose(moves[0]['coefficients']/1e-7, moves[3]['coefficients']/.001)


def test_coefficient_only_ablation_is_exact():
    curve = G.resize(FourierCurve(np.array([0j, 10+10j, 1.3])), 8)
    moved = gc.moved_curve(curve, np.array([.001,.0003,-.0002]), 1024)
    coefficients = gc.coefficients_only(moved, moved.nodes(1024), 8)
    np.testing.assert_array_equal(coefficients, F.arclength_quadrature(moved, moved.nodes(1024), 8)[0])


def test_inverse_reference_and_factorial_vectors():
    curve = FourierCurve(np.array([.08j, 10+10j, 1.3]))
    moved = gc.moved_curve(curve,np.array([.001,.0003,-.0002]),1024)
    results, check = gc.inverse_panel(moved,1024,8)
    assert check['inverse_residual_max'] < 1e-10
    assert check['inverse_4N_8N_max'] < 1e-10
    expected = G.project(curve,np.array([.001,.0003,-.0002]),8,1024,gc.UNIT)[0]
    np.testing.assert_allclose(results['native'],expected,atol=1e-14,rtol=0)
    interaction = results['both']-results['inverse']-results['position']+results['native']
    np.testing.assert_allclose(results['inverse']-results['native']+results['position']-results['native']+interaction,
                               results['both']-results['native'],atol=1e-14,rtol=0)


@pytest.mark.skipif(not torch.cuda.is_available(),reason='CUDA required')
def test_cuda_adapter_matches_maintained_trial():
    assert gc.validate_adapter()['passed']


def test_profiled_quadrature_preserves_production_result():
    curve = G.resize(FourierCurve.circle(1.3,10+10j),8)
    moved = gc.moved_curve(curve,np.array([.001,.0003,-.0002]),1024)
    expected = F.arclength_quadrature(moved,moved.nodes(1024),8)
    profile = gc.Profile()
    with gc.instrument(profile):
        actual = F.arclength_quadrature(moved,moved.nodes(1024),8)
    np.testing.assert_array_equal(actual[0],expected[0])
    assert actual[1] == expected[1]
    assert profile.calls['crop_diagnostic']==1
    assert all(x>=0 for x in profile.seconds.values())
