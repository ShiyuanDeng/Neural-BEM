"""Algebra, information geometry, measurement constraints, and derivative checks."""
import numpy as np

from .model import Fixture, Evaluator, JointObjective, apply_gains, oracle, incidence, realify, TARGET, NUISANCE
from .design import project_out, shape_information, uniform_plan, random_plan, offset_categories, graph_record


def test_joint_jacobian_including_material_and_complex_gains():
    f = Fixture(count=6)
    mask = np.ones((6, 6), bool)
    rng = np.random.default_rng(21)
    physical = rng.uniform(-.2, .2, 8)
    gains = rng.normal(0, .12, (2, 2, 11))
    x = np.r_[physical, gains.ravel()]
    e = Evaluator(f)
    obs = apply_gains(e.forward(physical), gains)
    objective = JointObjective(e, mask, obs, np.ones(2))
    j = objective.jacobian(x)
    direction = rng.normal(size=len(x))
    direction /= np.linalg.norm(direction)
    h = 2e-5
    fd = (objective.residual(x+h*direction)-objective.residual(x-h*direction))/(2*h)
    assert np.linalg.norm(fd-j@direction)/np.linalg.norm(fd) < 2e-7


def test_profile_information_matches_joint_real_nuisance_projection():
    f = Fixture(count=6)
    e = Evaluator(f)
    x = np.array([.1, -.1, .2, .3, -.2, .1, .2, .4])
    y, jac = e.forward(x), e.jacobian(x)
    mask = uniform_plan(6)
    sigma = np.array([.03, .02])
    obj = JointObjective(e, mask, y, sigma)
    full = obj.jacobian(np.r_[x, np.zeros(44)])
    nuisance = full[:, np.r_[NUISANCE, np.arange(8, full.shape[1])]]
    projected, _ = project_out(full[:, TARGET], nuisance)
    expected = projected.T@projected
    actual = shape_information(y, jac, mask, sigma)["gram"]
    assert np.linalg.norm(actual-expected)/np.linalg.norm(expected) < 1e-8


def test_closure_cancels_gains_but_monopole_contains_no_closure_information():
    rng = np.random.default_rng(8)
    y = rng.normal(size=(2, 6, 6))+1j*rng.normal(size=(2, 6, 6))
    gains = rng.normal(0, .3, (2, 2, 11))
    def closure(v):
        return v[:, :-1, :-1]*v[:, 1:, 1:]/(v[:, :-1, 1:]*v[:, 1:, :-1])
    assert np.allclose(closure(y), closure(apply_gains(y, gains)), rtol=1e-12)
    a = rng.normal(size=(2, 6))+1j*rng.normal(size=(2, 6))
    b = rng.normal(size=(2, 6))+1j*rng.normal(size=(2, 6))
    assert np.allclose(closure(a[:, :, None]*b[:, None, :]), 1.)


def test_tree_has_no_gain_quotient_but_connected_regular_plans_have_equal_cycles():
    rng = np.random.default_rng(91)
    n = 6
    tree = np.zeros((n, n), bool)
    tree[0, :] = True
    tree[:, 0] = True
    b = incidence(np.argwhere(tree), n)
    y = rng.normal(size=len(b))+1j*rng.normal(size=len(b))
    j = rng.normal(size=(len(b), 3))+1j*rng.normal(size=(len(b), 3))
    p, rank = project_out(j, y[:, None]*b)
    assert rank == len(b)
    assert np.linalg.norm(p)/np.linalg.norm(j) < 1e-12
    f = Fixture()
    base = uniform_plan()
    bins = offset_categories(f)
    randomized = random_plan(base, bins, 12, accepted_swaps=50)
    assert graph_record(base, bins) == graph_record(randomized, bins)
    assert graph_record(base)["cycle_dimension"] == 25
    assert not np.array_equal(base, randomized)


def test_native_and_nodal_compilers_agree_with_independent_full_boundary_solve():
    f = Fixture(count=6)
    x = np.array([.2, -.3, .2, .6, -.25, .3, .2, .4])
    native = Evaluator(f, backend="native")
    nodal = Evaluator(f)
    reference = oracle(f, x, nodes=192)
    assert np.linalg.norm(nodal.forward(x)-reference)/np.linalg.norm(reference) < 1e-8
    assert np.linalg.norm(native.forward(x)-reference)/np.linalg.norm(reference) < 1e-8
    jn, jk = native.jacobian(x), nodal.jacobian(x)
    assert np.linalg.norm(jn-jk)/np.linalg.norm(jk) < 1e-7


def test_calibration_quotient_is_invariant_to_gain_gauge_choice():
    # Reference-Tx fixing removes only a parameter redundancy; it must not add information.
    rng = np.random.default_rng(3)
    mask = uniform_plan(6)
    edges = np.argwhere(mask)
    y = rng.normal(size=len(edges))+1j*rng.normal(size=len(edges))
    j = rng.normal(size=(len(edges), 4))+1j*rng.normal(size=(len(edges), 4))
    b = incidence(edges, 6)
    all_gains = np.c_[b, (edges[:, 1] == 0)]
    p, _ = project_out(j, y[:, None]*b)
    q, _ = project_out(j, y[:, None]*all_gains)
    assert np.allclose(p, q, atol=1e-12)
