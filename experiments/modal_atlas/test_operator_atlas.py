"""Independent algebra and derivative controls for the MA-006 atlas."""
import numpy as np
from numpy.testing import assert_allclose

from .operator_atlas import cutoff_solve, discrete_tangent, stable_cutoff


def test_schur_reconstructs_full_complex_system_and_feedback_sign():
    rng = np.random.default_rng(361)
    a = rng.normal(size=(12, 12)) + 1j * rng.normal(size=(12, 12))
    a += 14 * np.eye(12)
    b = rng.normal(size=(12, 3)) + 1j * rng.normal(size=(12, 3))
    exact = np.linalg.solve(a, b)
    retained = np.array([0, 2, 5, 7, 9])
    row = cutoff_solve(a, b, exact, retained)
    assert_allclose(row['schur'], exact, atol=2e-15, rtol=2e-14)
    assert_allclose(row['reduced'][retained] - exact[retained], row['feedback'], atol=2e-15)
    assert np.linalg.norm(row['reduced'] - exact) > 0.01


def test_discrete_derivative_differentiates_matrix_rhs_and_readout():
    rng = np.random.default_rng(87)
    draw = lambda shape: rng.normal(size=shape) + 1j * rng.normal(size=shape)
    a, b, c = draw((9, 9)) + 12*np.eye(9), draw((9, 2)), draw((2, 9))
    da, db, dc = draw(a.shape), draw(b.shape), draw(c.shape)
    idx = np.array([0, 1, 4, 6])
    analytic = discrete_tangent(a, b, c, da, db, dc, idx)
    def y(t):
        return (c+t*dc)[:, idx] @ np.linalg.solve((a+t*da)[np.ix_(idx, idx)], (b+t*db)[idx])
    h = 1e-5
    assert_allclose(analytic, (y(h)-y(-h))/(2*h), atol=1e-9, rtol=1e-8)


def test_sufficient_cutoff_requires_all_larger_tested_bands_to_pass():
    rows = [dict(cutoff=k, good=v) for k, v in [(8, False), (12, True), (16, False), (24, True), (32, True)]]
    assert stable_cutoff(rows, lambda r: r['good']) == 24
    assert stable_cutoff(rows[:-2], lambda r: r['good']) is None
