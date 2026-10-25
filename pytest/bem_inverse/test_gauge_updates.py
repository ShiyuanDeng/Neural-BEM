"""GU-001 geometry updates and the level penalty: each keeps its stated mathematical property."""
from functools import partial

import numpy as np

from bem_inverse import Execution, FourierCurve
from bem_inverse.continuation.geometry import normal_basis, resize, speed_ratio
from bem_inverse.geometry_selection import make_update
from bem_inverse.geometry_update_methods import slider
from bem_inverse.level_penalty import LevelPenalty, unevenness

UNIT = .05


def uneven_curve(band=24):
    """A smooth convex curve whose parameter speed varies by about 30%."""
    t = 2*np.pi*np.arange(512)/512
    s = t+.15*np.sin(t)  # reparameterise an ellipse-like curve unevenly
    return resize(FourierCurve.from_samples(np.cos(s)+.8j*np.sin(s)+.05*np.cos(3*s), 12), band)


def test_uncentred_refit_returns_an_arclength_curve_with_spectral_slope():
    curve = uneven_curve()
    assert speed_ratio(curve) > 1.3
    update, trial = make_update('uncentred_spectral', UNIT, Execution(device='cpu'))
    prepared = update.prepare(curve, 3, curve.band)
    step = 1e-4*np.array([1, -2, 1, 1.5, 0, 1, -1])
    candidate, report = trial(step, prepared=prepared)
    assert speed_ratio(candidate) < 1.01
    assert report['zero_step_jump_mm'] > 1
    # Its slope in a is the prepared derivative (spectral's), by central difference.
    direction = np.eye(7)[2]*1e-7
    plus, minus = (trial(sign*direction, prepared=prepared)[0].coefficients for sign in (1, -1))
    np.testing.assert_allclose((plus-minus)/2e-7, prepared.derivatives[:, 2], atol=1e-6)


def test_n_update_is_the_sampled_normal_and_tangential_move():
    curve = uneven_curve()
    update, trial = make_update('n_update', UNIT, Execution(device='cpu'))
    prepared = update.prepare(curve, 2, curve.band)
    a = 1e-3*np.array([1, -2, 1, 1.5, 0, .5, 1, 0, -1, 2])  # h then s, metres
    candidate, _ = trial(a, prepared=prepared)
    count = 256
    t = 2*np.pi*np.arange(count)/count
    series = np.column_stack((np.ones(count), np.cos(t), np.cos(2*t), np.sin(t), np.sin(2*t)))
    z, dz = curve.values(count), curve.values(count, 1)
    mean_speed = np.mean(np.abs(dz))
    eta, tau = (series@part/(mean_speed*UNIT) for part in (a[:5], a[5:]))
    np.testing.assert_allclose(candidate.values(count), z+eta*(-1j*dz)+tau*dz, atol=1e-12)
    np.testing.assert_allclose(candidate.coefficients-curve.coefficients, prepared.derivatives@a, atol=1e-14)


def test_slider_moves_normally_and_keeps_the_relative_speed_change_even():
    curve = uneven_curve()
    a = 1e-3*np.array([1, -2, 1, 1.5, 0, 1, -1])
    nodes = curve.nodes(512)
    requested = normal_basis(nodes, 3)@a/UNIT
    normal, tangent = nodes.normals@np.array([1, 1j]), nodes.tangents@np.array([1, 1j])
    weights = nodes.arc_length_weights/nodes.perimeter

    def errors(update, trial):
        prepared = update.prepare(curve, 3, curve.band)
        candidate, _ = trial(a, prepared=prepared)
        step = FourierCurve(candidate.coefficients-curve.coefficients)  # no refit, no crop: c + A a
        np.testing.assert_allclose(step.coefficients, prepared.derivatives@a, atol=1e-15)
        moved = (step.values(512)*np.conj(normal)).real
        relative = (step.values(512, 1)*np.conj(tangent)).real/nodes.speeds
        uneven = relative-weights@relative
        return np.sqrt(weights@(moved-requested)**2/(weights@requested**2)), np.sqrt(weights@uneven**2)

    normal_error, uneven = errors(*make_update('slider', UNIT, Execution(device='cpu')))
    plain = slider.SliderUpdate(UNIT, xi=0.)  # plain least-squares normal move, which drifts
    _, plain_uneven = errors(plain, partial(slider.geometry_update, settings=plain))
    assert normal_error < .1
    assert uneven < .2*plain_uneven


def test_level_penalty_is_the_speed_spread_and_its_rows_have_the_right_slope():
    curve = uneven_curve()
    speed2 = np.abs(curve.values(4*curve.band+1, 1))**2  # J^2 has band 2K, its square 4K
    np.testing.assert_allclose(unevenness(curve.coefficients), np.mean((speed2/np.mean(speed2)-1)**2), rtol=1e-12)
    penalty = LevelPenalty()
    weight = penalty.weight(3.)
    rows = penalty.rows(curve.coefficients, weight)
    np.testing.assert_allclose(.5*rows@rows, .03*unevenness(curve.coefficients), rtol=1e-12)
    update, _ = make_update('n_update', UNIT, Execution(device='cpu'))
    derivatives = update.prepare(curve, 2, curve.band).derivatives
    step = np.eye(10)[7]*1e-7
    plus, minus = (penalty.rows(curve.coefficients+sign*derivatives@step, weight) for sign in (1, -1))
    np.testing.assert_allclose(penalty.jacobian(curve.coefficients, derivatives, weight)[:, 7],
                               (plus-minus)/2e-7, atol=1e-7)
