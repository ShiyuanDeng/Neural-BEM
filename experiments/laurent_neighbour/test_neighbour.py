"""Check new mixed-material coupling and the information/control comparisons."""
import numpy as np

from experiments.laurent_calibration.model import apply_gains
from experiments.laurent_calibration.design import uniform_plan
from .model import bodies_at, Evaluator, oracle, information, JointObjective


def point():
    return np.array([.2, -.2, .1, .3, -.2, .2, .1, .4,
                     -.1, .2, -.2, -.2, .15, .1, -.2, -.3])


def test_mixed_material_full_boundary_oracle_and_native_compiler():
    bodies = bodies_at(count=6)
    x = point()
    reference = oracle(bodies, x, nodes=192)
    coarser = oracle(bodies, x, nodes=128)
    for backend in ("nodal", "native"):
        actual = Evaluator(bodies, backend=backend).forward(x)
        assert np.linalg.norm(actual-reference)/np.linalg.norm(reference) < 1e-8
    assert np.linalg.norm(coarser-reference)/np.linalg.norm(reference) < 1e-10


def test_all_sixteen_coupled_shape_pose_material_columns():
    bodies = bodies_at(count=6)
    x = point()
    e = Evaluator(bodies)
    j = e.jacobian(x)
    h = 2e-4
    fd = np.stack([(e.forward(x+h*d)-e.forward(x-h*d))/(2*h) for d in np.eye(16)], axis=-1)
    relative = np.linalg.norm((j-fd).reshape(-1, 16), axis=0)/np.linalg.norm(fd.reshape(-1, 16), axis=0)
    assert relative.max() < 2e-6


def test_additive_control_is_sum_of_independent_objects_and_jacobians():
    bodies = bodies_at(count=6)
    x = point()
    control = Evaluator(bodies, interactions=False)
    a, b = Evaluator(bodies[:1]), Evaluator(bodies[1:])
    expected = a.forward(x[:8])+b.forward(x[8:])
    jac = np.concatenate((a.jacobian(x[:8]), b.jacobian(x[8:])), axis=-1)
    assert np.allclose(control.forward(x), expected, rtol=1e-12, atol=1e-15)
    assert np.allclose(control.jacobian(x), jac, rtol=1e-10, atol=1e-13)
    assert np.linalg.norm(oracle(bodies, x, interactions=False, nodes=128)-expected)/np.linalg.norm(expected) < 1e-8


def test_estimating_neighbour_cannot_increase_efficient_information():
    bodies = bodies_at()
    e = Evaluator(bodies)
    x = point()
    y, j = e.forward(x), e.jacobian(x)
    sigma = np.ones(2)
    known = information(y, j, uniform_plan(), sigma, neighbour_unknown=False)["gram"]
    unknown = information(y, j, uniform_plan(), sigma, neighbour_unknown=True)["gram"]
    assert np.linalg.eigvalsh(known-unknown).min() > -1e-12*np.linalg.norm(known)
    assert np.trace(unknown) < np.trace(known)


def test_joint_gain_and_neighbour_jacobian():
    bodies = bodies_at(count=6)
    x = point()
    e = Evaluator(bodies)
    rng = np.random.default_rng(41)
    gains = rng.normal(0, .1, (2, 2, 11))
    observed = apply_gains(e.forward(x), gains)
    objective = JointObjective(e, np.ones((6, 6), bool), observed, np.ones(2), x)
    z = np.r_[x, gains.ravel()]
    direction = rng.normal(size=len(z))
    direction /= np.linalg.norm(direction)
    j = objective.jacobian(z)
    h = 2e-5
    fd = (objective.residual(z+h*direction)-objective.residual(z-h*direction))/(2*h)
    assert np.linalg.norm(fd-j@direction)/np.linalg.norm(fd) < 1e-7


def test_additive_echo_cannot_improve_shape_information_when_gains_are_known():
    # Fixed additive noise: a known extra echo has zero target derivative.
    # An unknown extra echo adds nuisance directions, never target information.
    bodies = bodies_at()
    x = point()
    isolated, additive = Evaluator(bodies[:1]), Evaluator(bodies, interactions=False)
    yi, ji = isolated.forward(x[:8]), isolated.jacobian(x[:8])
    ya, ja = additive.forward(x), additive.jacobian(x)
    mask, sigma = uniform_plan(), np.ones(2)
    base = information(yi, ji, mask, sigma, gains_unknown=False)["gram"]
    known = information(ya, ja, mask, sigma, neighbour_unknown=False, gains_unknown=False)["gram"]
    unknown = information(ya, ja, mask, sigma, neighbour_unknown=True, gains_unknown=False)["gram"]
    assert np.allclose(base, known, rtol=1e-10, atol=1e-15)
    assert np.linalg.eigvalsh(base-unknown).min() > -1e-12*np.linalg.norm(base)
