import numpy as np
import pytest
import torch

from experiments.cleaned_interface.n_update_audit import relative_columns
from experiments.cleaned_interface.nu005 import CertifiedSpectralUpdate
from experiments.cleaned_interface.nu006 import BatchedCertifiedUpdate
from experiments.shape_continuation.geometry import FourierCurve


def kite(K=24):
    t = 2*np.pi*np.arange(1024)/1024
    z = (np.cos(t)+.65*np.cos(2*t)-.65)+1.5j*np.sin(t)
    return FourierCurve.from_samples(z, K)


@pytest.mark.parametrize('device', ['cpu', pytest.param('cuda', marks=pytest.mark.skipif(
    not torch.cuda.is_available(), reason='no CUDA'))])
def test_batched_prepare_matches_sequential(device):
    curve, unit = kite(), .05
    sequential, batched = CertifiedSpectralUpdate(unit), BatchedCertifiedUpdate(unit, device=device)
    a, g = sequential.prepare(curve, 5, curve.band), batched.prepare(curve, 5, curve.band)
    assert np.max(relative_columns(g.derivatives, a.derivatives)) < 1e-7
    assert np.max(np.abs(g.base_projection-a.base_projection)) < 1e-13
    assert np.max(np.abs(g.fine_base_projection-a.fine_base_projection)) < 1e-13
    assert batched.counts['batched_preparations'] == 1 and batched.counts['prepare_fallbacks'] == 0
    step = np.random.default_rng(2).normal(size=11)*1e-5
    x, _ = sequential.trial(a, step)
    y, info = batched.trial(g, step)
    assert np.max(np.abs(x.coefficients-y.coefficients)) < 1e-12
    assert set(info['validity_tiers'].values()) <= {'increment', 'full'}
