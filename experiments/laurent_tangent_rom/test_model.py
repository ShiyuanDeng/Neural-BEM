from types import SimpleNamespace

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from .model import bases, derivative, solve, storage


def fixture(seed=21):
    rng = np.random.default_rng(seed)
    def random(shape):
        return rng.normal(size=shape) + 1j*rng.normal(size=shape)
    a = 8*np.eye(28) + random((28, 28))/5
    b, c = random((28, 3)), random((4, 28))
    factors = lu_factor(a)
    case = SimpleNamespace(a=a, b=b, c=c, factors=factors, u=lu_solve(factors, b))
    ds = [dict(total=random(a.shape), db=random(b.shape), dc=random(c.shape)) for _ in range(5)]
    return case, ds


def exact_derivative(case, d):
    return d['dc'] @ case.u + case.c @ lu_solve(case.factors, d['db']-d['total']@case.u)


def test_full_basis_reproduces_complex_forward_and_tangents():
    case, ds = fixture()
    result = solve(case, np.eye(len(case.a)))
    np.testing.assert_allclose(result['y'], case.c@case.u, rtol=1e-13, atol=1e-13)
    for d in ds:
        np.testing.assert_allclose(derivative(result, d), exact_derivative(case, d), atol=1e-13)


def test_primal_dual_closure_matches_untrained_parameter_derivative():
    case, ds = fixture()
    bank, _ = bases(case, ds[:4])
    result = solve(case, bank['PRIMAL_DUAL']['v'])
    np.testing.assert_allclose(result['y'], case.c@case.u, atol=1e-13)
    # Fifth direction has never been used in basis construction.
    np.testing.assert_allclose(derivative(result, ds[4]), exact_derivative(case, ds[4]), atol=1e-13)
    forward = solve(case, bank['FORWARD']['v'])
    assert np.linalg.norm(derivative(forward, ds[4])-exact_derivative(case, ds[4])) > 1e-2


def test_tangent_enrichment_preserves_training_state_derivatives():
    case, ds = fixture()
    bank, _ = bases(case, ds[:4])
    result = solve(case, bank['TANGENT']['v'])
    for d in ds[:4]:
        np.testing.assert_allclose(derivative(result, d), exact_derivative(case, d), atol=1e-13)


def test_frozen_basis_tangent_includes_operator_rhs_and_receiver_changes():
    case, ds = fixture()
    bank, _ = bases(case, ds[:4])
    v = bank['TANGENT']['v'][:, :8]
    result = solve(case, v)
    d = ds[4]
    errors = []
    for h in (1e-3, 5e-4, 2.5e-4):
        values = [solve(SimpleNamespace(a=case.a+sign*h*d['total'],
                    b=case.b+sign*h*d['db'], c=case.c+sign*h*d['dc']), v)['y']
                  for sign in (1, -1)]
        errors.append(np.linalg.norm((values[0]-values[1])/(2*h)-derivative(result,d)))
    assert 3.8 < errors[0]/errors[1] < 4.2
    assert 3.8 < errors[1]/errors[2] < 4.2


def test_no_evaluation_derivative_affects_basis():
    case, ds = fixture()
    before, _ = bases(case, ds[:4])
    ds[4]['total'] *= 123
    after, _ = bases(case, ds[:4])
    for arm in before:
        np.testing.assert_array_equal(before[arm]['v'], after[arm]['v'])


def test_storage_includes_basis_acquisition_derivatives_and_factorization():
    row = storage(194, 24, 24, 24)
    assert row['reduced_model_slots'] == 194*24+7*(24**2+48*24)+24**2
    assert row['full_model_slots'] == 7*(194**2+48*194)+194**2
