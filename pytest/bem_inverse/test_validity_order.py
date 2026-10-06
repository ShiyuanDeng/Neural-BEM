"""Sampled-first validity accepts the same set, raises the same refusals, and skips certificates."""
import numpy as np
import pytest
import torch

from bem_inverse.certified import CertifiedSpectralUpdate
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.updates import UpdateRefused
from bem_inverse.geometry_selection import make_update
from bem_inverse.physics import Execution

UNIT = .05


def lobed(band=20, lobes=5, depth=.18):
    """A smooth non-convex star at storage band ``band``."""
    t = np.linspace(0, 2*np.pi, 4*band+4, endpoint=False)
    radius = 1+depth*np.cos(lobes*t)
    return FourierCurve.from_samples(radius*np.exp(1j*t), band)


def outcome(update, space, step):
    try:
        candidate, info = update.trial(space, step)
    except UpdateRefused as exc:
        return ('refused', exc.reason)
    return ('accepted', candidate.coefficients.tobytes())


def steps(dimension, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    for scale in (1e-4, 2e-3, 8e-3, 2e-2, 5e-2):
        for _ in range(4):
            out.append(scale*rng.normal(size=dimension))
    return out


def pair(order_first='certificate_first', device='cpu'):
    execution = Execution(device=device, frequency_threads=1)
    first = make_update('certified_spectral', UNIT, execution)
    second = make_update('certified_spectral', UNIT, Execution(device=device, frequency_threads=1,
                                                              validity_order='sampled_first'))
    assert (first.order, second.order) == (order_first, 'sampled_first')
    return first, second


@pytest.mark.parametrize('device', ['cpu'] + (['cuda'] if torch.cuda.is_available() else []))
def test_both_orders_decide_identically(device):
    first, second = pair(device=device)
    curve = lobed()
    a, b = first.prepare(curve, 9, curve.band), second.prepare(curve, 9, curve.band)
    decisions = [(outcome(first, a, s), outcome(second, b, s)) for s in steps(len(a.orders))]
    assert all(x == y for x, y in decisions)
    assert {x[0] for x, _ in decisions} == {'accepted', 'refused'}   # both branches exercised
    # The full certificate now runs only after a sampled refusal.
    full_first = sum(first.counts[f'{r}_full'] for r in ('moved_coarse', 'moved_fine', 'candidate'))
    assert full_first > 0
    assert sum(second.counts[f'{r}_full'] for r in ('moved_coarse', 'moved_fine', 'candidate')) == 0
    assert second.counts['certificate_seconds'] < first.counts['certificate_seconds']


def test_certificates_still_overturn_sampled_refusals():
    """With a sampled test that refuses everything, both orders accept exactly the certified set."""
    first, second = pair()
    for update in (first, second):
        def refuse(test, update=update):
            raise UpdateRefused('self_intersection', 'fixture: sampling refuses every curve')
        update._sampled = refuse
    curve = lobed()
    a, b = first.prepare(curve, 9, curve.band), second.prepare(curve, 9, curve.band)
    decisions = [(outcome(first, a, s), outcome(second, b, s)) for s in steps(len(a.orders), seed=11)]
    assert all(x == y for x, y in decisions)
    accepted = sum(x[0] == 'accepted' for x, _ in decisions)
    assert accepted > 0 and accepted < len(decisions)
    assert sum(second.counts[f'{r}_full_override'] for r in ('moved_coarse', 'moved_fine', 'candidate')) > 0


def test_settings_record_the_order_and_shadow_needs_certificates_first():
    first, second = pair()
    assert first.settings()['validity_order'] == 'certificate_first'
    assert second.settings()['validity_order'] == 'sampled_first'
    assert second.settings()['validity'] != first.settings()['validity']
    with pytest.raises(ValueError, match='shadow'):
        CertifiedSpectralUpdate(UNIT, shadow=True, order='sampled_first')
    with pytest.raises(ValueError):
        Execution(validity_order='never')
