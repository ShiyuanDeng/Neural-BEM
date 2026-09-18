"""Mathematical and numerical controls for the calibration-uncertainty family."""
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.laurent_calibration.design import uniform_plan
from experiments.laurent_calibration.model import apply_gains
from experiments.laurent_calibration.run import PRIOR_POINTS
from experiments.laurent_neighbour.model import Body, Evaluator, JointObjective, bodies_at, information
from experiments.laurent_neighbour.run import NEIGHBOUR_PRIORS
from .model import (CalibratedObjective, GAIN_SD, crossover_tau, design_blocks,
                    marginal_gram, prior_precision, radial_rms_crlb_mm)

SCREEN = Path("results/experiments/laurent_neighbour_20260916/screen.json")


@pytest.fixture(scope="module")
def recorded():
    return json.loads(SCREEN.read_text())


@pytest.fixture(scope="module")
def scene(recorded):
    """The interaction-specific configuration, with its recorded reference values."""
    bodies = bodies_at(.105, np.deg2rad(-30), 3.)
    mask, sigma = uniform_plan(), np.array(recorded["sigma"])
    x = np.r_[PRIOR_POINTS[0], NEIGHBOUR_PRIORS[0]]
    out = {}
    for name, interactions in (("coupled", True), ("additive", False)):
        ev = Evaluator(bodies, interactions=interactions)
        out[name] = (ev.forward(x), ev.jacobian(x))
    match = [c for c in recorded["candidates"]
             if c["distance_m"] == .105 and c["angle_degrees"] == -30 and c["epsr"] == 3.][0]
    return bodies, mask, sigma, x, out, match["priors"][0]["arms"]


def test_endpoints_reproduce_the_recorded_screen(scene):
    """tau -> inf is the free-gain arm; tau = 0 is the known-gain arm."""
    _, mask, sigma, _, fields, arms = scene
    for name in ("coupled", "additive"):
        y, jac = fields[name]
        free = radial_rms_crlb_mm(marginal_gram(y, jac, mask, sigma, np.inf)[0])
        known = radial_rms_crlb_mm(marginal_gram(y, jac, mask, sigma, 0.)[0])
        assert free == pytest.approx(arms[f"unknown_{name}"]["radial_rms_crlb_mm"], rel=1e-8)
        assert known == pytest.approx(arms[f"unknown_{name}"]["known_gain_radial_rms_crlb_mm"], rel=1e-8)


def test_crlb_is_monotone_in_calibration_uncertainty(scene):
    """A looser prior cannot add information, at any tau, in either world."""
    _, mask, sigma, _, fields, _ = scene
    taus = np.r_[0., np.logspace(-4, 3, 40), np.inf]
    for y, jac in fields.values():
        values = np.array([radial_rms_crlb_mm(marginal_gram(y, jac, mask, sigma, t)[0]) for t in taus])
        assert np.all(np.diff(values) > -1e-9*values[:-1])


def test_large_tau_converges_to_the_free_gain_projection(scene):
    _, mask, sigma, _, fields, _ = scene
    y, jac = fields["coupled"]
    free = radial_rms_crlb_mm(marginal_gram(y, jac, mask, sigma, np.inf)[0])
    assert radial_rms_crlb_mm(marginal_gram(y, jac, mask, sigma, 1e6)[0]) == pytest.approx(free, rel=1e-6)


def test_known_gains_leave_an_additive_neighbour_unable_to_help(scene):
    """The study's inequality: with gains fixed, additive echoes add only nuisance."""
    _, mask, sigma, x, fields, _ = scene
    isolated = Evaluator([Body()])
    absent = radial_rms_crlb_mm(marginal_gram(
        isolated.forward(x[:8]), isolated.jacobian(x[:8]), mask, sigma, 0.)[0])
    y, jac = fields["additive"]
    known = radial_rms_crlb_mm(marginal_gram(y, jac, mask, sigma, 0., neighbour_unknown=False)[0])
    unknown = radial_rms_crlb_mm(marginal_gram(y, jac, mask, sigma, 0.)[0])
    # A known additive neighbour leaves the target Jacobian untouched.
    assert known == pytest.approx(absent, rel=1e-10)
    # An unknown one can only add nuisance directions.
    assert unknown >= absent*(1-1e-12)


def test_schur_elimination_matches_an_explicit_gaussian_posterior():
    """Independent algebra: block inversion of the full penalised normal matrix."""
    rng = np.random.default_rng(11)
    j = rng.normal(size=(60, 9))
    lam = np.abs(rng.normal(size=5))+.3
    target, gains = j[:, :4], j[:, 4:]
    normal = j.T@j+np.diag(np.r_[np.zeros(4), lam])
    explicit = np.linalg.inv(np.linalg.inv(normal)[:4, :4])
    cross = gains.T@target
    schur = target.T@target-cross.T@np.linalg.solve(gains.T@gains+np.diag(lam), cross)
    assert np.allclose(schur, explicit, rtol=1e-10, atol=1e-12)


def test_prior_precision_matches_the_declared_gain_scale():
    p = prior_precision(3, 2, .5)
    assert p.shape == (12,)
    assert np.allclose(p[:3], (.5*GAIN_SD[0])**-2)
    assert np.allclose(p[3:6], (.5*GAIN_SD[1])**-2)
    assert np.allclose(p[:6], p[6:])


def test_free_prior_reproduces_the_neighbour_study_objective(scene):
    """The bridge arm must be the recorded study's inverse, not an approximation."""
    bodies, mask, sigma, x, _, _ = scene
    rng = np.random.default_rng(5)
    observed = Evaluator(bodies).forward(x)+sigma[:, None, None]*rng.normal(size=(2, 12, 12))
    initial = np.r_[PRIOR_POINTS[1], NEIGHBOUR_PRIORS[1]]
    old = JointObjective(Evaluator(bodies), mask, observed, sigma, initial)
    new = CalibratedObjective(Evaluator(bodies), mask, observed, sigma, initial, gain_prior=None)
    z = np.r_[initial, .05*rng.normal(size=old.nf*2*old.k)]
    assert np.allclose(new.residual(z), old.residual(z), rtol=0, atol=1e-14)
    assert np.allclose(new.jacobian(z), old.jacobian(z), rtol=0, atol=1e-14)


@pytest.mark.parametrize("prior", [0., .1, 1.])
def test_penalised_jacobian_matches_finite_differences(scene, prior):
    bodies, mask, sigma, x, _, _ = scene
    rng = np.random.default_rng(7)
    observed = apply_gains(Evaluator(bodies).forward(x), .1*rng.normal(size=(2, 2, 23)))
    initial = np.r_[PRIOR_POINTS[1], NEIGHBOUR_PRIORS[1]]
    obj = CalibratedObjective(Evaluator(bodies), mask, observed, sigma, initial, gain_prior=prior)
    z = np.r_[initial, .05*rng.normal(size=obj.gain_count)]
    analytic = obj.jacobian(z)
    assert analytic.shape == (len(obj.residual(z)), len(z))
    step = 1e-6
    for column in (0, 3, 7, obj.p-1, *( [obj.p, obj.p+obj.k] if obj.free_gains else [])):
        shift = np.zeros(len(z))
        shift[column] = step
        fd = (obj.residual(z+shift)-obj.residual(z-shift))/(2*step)
        scale = max(np.linalg.norm(fd), 1e-12)
        assert np.linalg.norm(fd-analytic[:, column])/scale < 2e-6


def test_zero_prior_removes_the_gain_parameters(scene):
    bodies, mask, sigma, x, _, _ = scene
    observed = Evaluator(bodies).forward(x)
    obj = CalibratedObjective(Evaluator(bodies), mask, observed, sigma, np.zeros(16), gain_prior=0.)
    assert obj.gain_count == 0 and not obj.free_gains
    assert np.allclose(obj.residual(np.zeros(16)), 0., atol=1e-12)


def test_crossover_is_bracketed_and_consistent_with_the_sweep(scene):
    """The coupled advantage must appear at exactly one calibration scale."""
    _, mask, sigma, _, fields, _ = scene

    def bound(tau):
        return tuple(radial_rms_crlb_mm(marginal_gram(*fields[k], mask, sigma, tau)[0])
                     for k in ("coupled", "additive"))

    tau = crossover_tau(bound)
    assert tau is not None and 1e-4 < tau < 1e3
    below, above = bound(tau*.5), bound(tau*2)
    assert below[1] < below[0]      # better calibration: coupling does not pay
    assert above[1] > above[0]      # worse calibration: coupling pays
    assert bound(tau)[0] == pytest.approx(bound(tau)[1], rel=1e-6)


def test_design_blocks_match_the_inverse_gain_parameterisation(scene):
    """Fisher gain columns and optimiser gain columns must be the same object."""
    bodies, mask, sigma, x, fields, _ = scene
    y, jac = fields["coupled"]
    physical, gains, _, _ = design_blocks(y, jac, mask, sigma)
    obj = CalibratedObjective(Evaluator(bodies), mask, y, sigma, x, gain_prior=1.)
    z = np.r_[x, np.zeros(obj.gain_count)]
    rows = obj.jacobian(z)[:physical.shape[0]]
    # The two builders order their real rows differently; the information they
    # carry must be identical, which is all the Fisher analysis uses.
    mine, theirs = np.c_[physical, gains], rows
    assert np.allclose(mine.T@mine, theirs.T@theirs, rtol=1e-10, atol=1e-12)
