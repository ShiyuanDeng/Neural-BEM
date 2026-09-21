import numpy as np
import pytest

from .core import (tail_mask, family, fixtures, directions, acquisition, moved,
                   solve, data_derivatives, hadamard, nodal, relative,
                   normal_direction, evaluate, tangent, crop_derivatives)


def test_tail_budget_is_minimal_and_not_lost_to_cumulative_cancellation():
    a = np.array([[1., 1e-5], [1e-9, 0.]])
    for tol in (1e-2, 1e-6, 1e-10):
        mask = tail_mask(a, tol)
        assert np.linalg.norm(a[~mask]) <= tol*np.linalg.norm(a)
        kept = np.sort(np.abs(a[mask]))
        if kept.size:
            assert np.sqrt(np.linalg.norm(a[~mask])**2+kept[0]**2) > tol*np.linalg.norm(a)
    assert not tail_mask(np.zeros((2, 2)), 1e-6).any()


def test_normal_directions_are_pure_normal_and_unit_rms():
    theta = 2*np.pi*np.arange(1024)/1024
    for c in fixtures().values():
        v = evaluate(normal_direction(c, 6, 'sin'), theta)
        t = tangent(c, theta)
        assert np.max(np.abs((v*t.conj()).real)) < 1e-12
        assert abs(np.mean(np.abs(v)**2)-1) < 1e-12


@pytest.mark.parametrize('name', ['circle', 'ellipse', 'crescent'])
def test_analytic_full_family_derivative_matches_reassembly(name):
    c = fixtures()[name]
    src, rec = acquisition(4)
    dz = normal_direction(c, 3, 'sin')
    base, deriv = family(c, 10., 10./np.sqrt(2), 24, 256, src, rec, {'v': dz})
    errors = []
    for h in (2e-4, 1e-4, 5e-5):
        plus, _ = family(moved(c, dz, h), 10., 10./np.sqrt(2), 24, 256, src, rec)
        minus, _ = family(moved(c, dz, -h), 10., 10./np.sqrt(2), 24, 256, src, rec)
        fd = tuple((getattr(plus, f)-getattr(minus, f))/(2*h) for f in ('a', 'b', 'c'))
        errors.append([relative(x, y) for x, y in zip(deriv['v'], fd)])
    assert max(errors[-1]) < 2e-5
    assert max(errors[-1]) < max(errors[0])/8


def test_circle_physical_derivative_and_projected_operator_are_independent():
    c = fixtures()['circle']
    src, rec = acquisition(5)
    dm = {'v': normal_direction(c, 6, 'cos')}
    base, deriv = family(c, 10., 10./np.sqrt(2), 24, 256, src, rec, dm)
    sol = solve(base)
    oracle = nodal(c, 10., 10./np.sqrt(2), 128, src, rec, dm, cutoff=24)
    dy = data_derivatives(base, deriv, sol)['v']
    hdy = hadamard(c, dm, 10., 10./np.sqrt(2), sol, 24)['v']
    assert relative(base.a, oracle['projected']) < 1e-10
    assert relative(sol['y'], oracle['y']) < 1e-11
    assert relative(dy, oracle['derivatives']['v']) < 1e-9
    assert relative(hdy, oracle['derivatives']['v']) < 1e-9


def test_crop_preserves_derivative_of_the_actual_masked_model():
    c = fixtures()['ellipse']
    src, rec = acquisition(4)
    dz = normal_direction(c, 3, 'cos')
    base, dd = family(c, 2., np.sqrt(2), 24, 256, src, rec, {'v': dz})
    base = base.crop(16)
    dd = crop_derivatives(dd, 24, 16)
    remainder = base.a-np.eye(len(base.a))
    mask = tail_mask(remainder, 1e-2)
    analytic = data_derivatives(base, dd, solve(base, mask), mask)['v']
    values = []
    h = 1e-5
    for sign in (1, -1):
        system, _ = family(moved(c, dz, sign*h), 2., np.sqrt(2), 16, 256, src, rec)
        values.append(solve(system, mask)['y'])
    assert relative(analytic, (values[0]-values[1])/(2*h)) < 1e-6
