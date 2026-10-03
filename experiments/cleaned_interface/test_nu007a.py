"""Threshold, refusal, fallback and public-selection coverage for NU-007a."""
import numpy as np
import pytest
import torch

from bem_inverse.batched import BatchedCertifiedUpdate
from bem_inverse.device_certified import DeviceCertifiedUpdate, device_certificate
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.certified import regularity_floor
from bem_inverse.n_update import curve_certificate
from bem_inverse.physics import Execution
from bem_inverse.geometry_selection import make_update
from .nu007a import compare_records


def record(bound, lower=1., floor=1e-12):
    return dict(role='candidate', tier='increment', increment_bound=bound,
                increment_lower=lower, regularity_floor=floor)


def test_threshold_scaled_gate_handles_roundoff_floor_without_hiding_crossings():
    row = compare_records([record(1e-8)], [record(1e-8+1e-14)])
    assert row['bounds_agree'] and row['same_threshold_sides']
    row = compare_records([record(1-1e-12)], [record(1+1e-12)])
    assert row['bounds_agree'] and not row['same_threshold_sides']
    row = compare_records([record(.5, 2e-12)], [record(.5, .5e-12)])
    assert row['bounds_agree'] and not row['same_regularity_sides']
    assert not compare_records([record(.5)], [])['same_bound_keys']


@pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA qualification')
@pytest.mark.parametrize('target', [1-1e-8, 1-4e-12, 1-1e-12, 1+1e-8])
def test_real_certificate_decisions_near_bound_and_regularity_thresholds(target):
    curve = FourierCurve.circle(1.)
    host, device = BatchedCertifiedUpdate(.05, device='cuda'), DeviceCertifiedUpdate(.05, device='cuda')
    spaces = [u.prepare(curve, 3, curve.band) for u in (host, device)]
    base = host._base(spaces[0])
    delta = -base['nu']+np.sqrt(base['nu']**2+(target-base['rho']-base['allowance'])/base['reciprocal_l1'])
    coefficients = curve.coefficients*(1+delta)
    records = []
    for update, space in zip((host, device), spaces):
        tier, row = update.certify(space, coefficients)
        records.append(dict(row, role='candidate', tier=tier, regularity_floor=regularity_floor(coefficients)))
    result = compare_records(records[:1], records[1:])
    assert result['same_tiers'] and result['same_bound_keys'] and result['bounds_agree']
    assert result['same_threshold_sides'] and result['same_regularity_sides']
    assert abs(records[0]['increment_bound']-target) < 1e-13


@pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA qualification')
@pytest.mark.parametrize('amplitude', [.45, .499, .5, 1.])
def test_simple_near_cusp_cusp_and_crossing_family(amplitude):
    # z(t)=e^it+a e^(2it), analytic cusp at a=1/2; bounded diagnostic degree.
    coefficients = np.zeros(5, complex)
    coefficients[3:] = [1, amplitude]
    curve = FourierCurve(coefficients)
    results = []
    for call in (lambda: curve_certificate(curve, 16, max_degree=400),
                 lambda: device_certificate(curve, 16, 'cuda', max_degree=400)):
        try:
            cert = call()
            results.append('certified')
            if amplitude < .5:
                lower = (1-cert['rho']-cert['allowance'])/cert['reciprocal_l1']
                assert lower <= (1-2*amplitude)**2+1e-12
        except ValueError:
            results.append('inconclusive')
    assert results[0] == results[1]
    if amplitude >= .5:
        assert results == ['inconclusive']*2


def test_device_oom_uses_counted_host_certificate(monkeypatch):
    import bem_inverse.device_certified as module
    def exhausted(*args, **kwargs):
        raise torch.OutOfMemoryError('injected allocation failure')
    monkeypatch.setattr(module, 'device_certificate', exhausted)
    monkeypatch.setattr(torch.cuda, 'empty_cache', lambda: None)
    update = DeviceCertifiedUpdate(.05, device='cpu')
    curve = FourierCurve.circle(1.)
    actual, expected = update._certificate(curve, 16), curve_certificate(curve, 16)
    for key in ('rho','allowance','reciprocal_l1','beta','Lambda','log_degree'):
        assert actual[key] == expected[key]
    assert update.counts['device_certificate_fallbacks'] == 1


def test_public_selection_preserves_cpu_prepare_and_uses_cuda_certificates():
    assert type(make_update('certified_spectral', .05, Execution('cpu'))) is BatchedCertifiedUpdate
    # Construction records the requested device; availability is checked on use.
    assert type(make_update('certified_spectral', .05, Execution('cuda'))) is DeviceCertifiedUpdate


@pytest.mark.parametrize('device', ['cpu','cuda'])
def test_clockwise_curve_is_refused_before_certificate_work(device):
    curve = FourierCurve.circle(1.)
    update = DeviceCertifiedUpdate(.05, device=device)
    tier, record = update.certify(None, curve.coefficients[::-1])
    assert tier == 'refused' and record['signed_area'] < 0
    assert update.counts['certificate_seconds'] == 0
