"""Analytic controls for graph continuation and attached monodromy loops."""
import numpy as np
import pytest

from bem_inverse.complex_paths import lollipop_path, radius_graph
from bem_inverse.complex_radius import Cubic, track


class CubicGraph(Cubic):
    def ab(self, q):
        return np.array([q**3-3*q, 3*q*q-3, 6*q]), np.array([1., 0., 0.]), 1.


class ReciprocalGraph:
    """F=1-t*q, so the stationary graph has a known pole t=1/q."""
    def ab(self, q):
        return np.array([1., 0., 0.]), np.array([q, 1., 0.]), 1.

    def state(self, q, t):
        return dict(F=1-t*q, Fq=-t, Fqq=0., Ft=-q,
                    scale=max(1., abs(t*q)), margin=1.)


def test_radius_graph_crosses_fold_with_real_radius_and_parameter_reversal():
    result = radius_graph(CubicGraph(), -1.1, direction=1, q_bounds=(-1.2, -.9),
                          t_bounds=(-3., 3.), max_dq=.005, steps=1000)
    assert result['status'] == 'Q_DOMAIN_BOUNDARY'
    q = np.array([s['q'].real for s in result['states']])
    t = np.array([s['t'].real for s in result['states']])
    assert np.all(np.diff(q) > 0)
    assert q[0] < -1 < q[-1]
    assert max(t) > 1.99999
    assert np.any(np.diff(t) > 0) and np.any(np.diff(t) < 0)
    np.testing.assert_allclose(t, q**3-3*q, atol=1e-14)
    assert max(abs(s['F']) for s in result['states']) < 1e-14


def test_radius_graph_returns_only_tracked_bracket_containing_known_target_root():
    result = radius_graph(CubicGraph(), 0., direction=-1, q_bounds=(-.5, .1),
                          t_bounds=(-3., 3.), max_dq=.01, steps=2000)
    assert result['status'] == 'Q_DOMAIN_BOUNDARY'
    assert len(result['t1_brackets']) == 1
    bracket = result['t1_brackets'][0]
    exact = -2*np.sin(np.pi/18)
    assert min(bracket['q_left'], bracket['q_right']) <= exact <= max(bracket['q_left'], bracket['q_right'])
    assert bracket['right_index'] == bracket['left_index']+1
    assert result['states'][bracket['left_index']]['q'].real == bracket['q_left']
    assert result['states'][bracket['right_index']]['q'].real == bracket['q_right']


def test_radius_graph_refuses_a_denominator_pole_without_reconnecting():
    result = radius_graph(ReciprocalGraph(), .1, direction=-1, q_bounds=(-.1, .1),
                          t_bounds=(-np.inf, np.inf), max_dq=.2, max_dt=1e9,
                          min_dq=1e-4, steps=1000)
    assert result['status'] == 'B_DENOMINATOR_REFUSAL'
    assert all(s['q'].real > 0 for s in result['states'])
    assert result['rejected']
    assert any(row['reason'].startswith(('B_ZERO:', 'B_SIGN:')) for row in result['rejected'])
    assert result['last_reason'].startswith('B_')


def test_radius_graph_stops_at_declared_real_parameter_boundary():
    result = radius_graph(ReciprocalGraph(), .1, direction=-1, q_bounds=(.01, .2),
                          t_bounds=(-20., 20.), max_dq=.01, max_dt=.1, steps=2000)
    assert result['status'] == 'T_DOMAIN_BOUNDARY'
    assert all(10-1e-12 <= s['t'].real <= 20 for s in result['states'])
    assert abs(result['states'][-1]['q'].real-.05) < 1e-8


def test_lollipop_stem_is_retraced_and_cubic_sheet_exchange_is_reversible():
    path = lollipop_path(2., .05, base=0., height=.2, points=128)
    np.testing.assert_array_equal(path[-3:], path[:3][::-1])
    first = track(Cubic(), 0., path)
    assert first['status'] == 'COMPLETED'
    np.testing.assert_allclose(first['states'][-1]['q'], -np.sqrt(3), atol=1e-8)
    reverse = track(Cubic(), first['states'][-1]['q'], path[::-1])
    assert reverse['status'] == 'COMPLETED'
    np.testing.assert_allclose(reverse['states'][-1]['q'], 0., atol=1e-8)


@pytest.mark.parametrize('radius,height', [(0., .1), (.1, .1), (.2, .1)])
def test_lollipop_rejects_degenerate_attachment(radius, height):
    with pytest.raises(ValueError):
        lollipop_path(2., radius, height=height)
