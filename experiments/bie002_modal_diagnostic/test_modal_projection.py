"""Algebra-only tests; physical solves/JVPs are counted in the campaign ledger."""
from types import SimpleNamespace
import numpy as np
from .modal_projection import (synthesis, modes, centered_mask, mask_operator,
                               project, scale_maps, oracle_retention)


def test_native_grid_unitarity_and_unique_nyquist():
    curves = [SimpleNamespace(num_nodes=n, period=p,
                              parameters=.3 + np.arange(n) * p / n)
              for n, p in [(8, 2 * np.pi), (12, 3.7)]]
    q, labels, components = synthesis(curves)
    np.testing.assert_allclose(q.conj().T @ q, np.eye(40), atol=3e-15)
    assert list(modes(8)) == [-4, -3, -2, -1, 0, 1, 2, 3]
    for fraction in (.25, .5, .75):
        p, _, _ = synthesis(curves, fraction)
        np.testing.assert_allclose(p.conj().T @ p, np.eye(p.shape[1]), atol=3e-15)


def test_scaling_and_projection_preserve_actions():
    rng = np.random.default_rng(20260915)
    a, b, c, u = [rng.normal(size=s) + 1j*rng.normal(size=s)
                  for s in [(8, 8), (8, 2), (3, 8), (8, 2)]]
    aa, bb, cc, s = scale_maps(a, b, c, .07)
    np.testing.assert_allclose(aa @ (s[:, None] * u), s[:, None] * (a @ u))
    np.testing.assert_allclose(cc @ (s[:, None] * u), c @ u)
    q, _, _ = synthesis([SimpleNamespace(num_nodes=4, period=2*np.pi,
                                        parameters=np.arange(4)*np.pi/2)])
    ar, br, cr = project(aa, bb, cc, q)
    np.testing.assert_allclose(q @ ar @ q.conj().T, aa, atol=1e-12)
    np.testing.assert_allclose(q @ br, bb, atol=1e-14)
    np.testing.assert_allclose(cr @ q.conj().T, cc, atol=1e-12)


def test_fixed_band_does_not_wrap_and_keeps_cross_blocks():
    labels = np.array([-4, -3, 2, 3, -4, 3])
    component = np.array([0, 0, 0, 0, 1, 1])
    mask = centered_mask(labels, component, 1)
    assert mask[0, 1] and not mask[0, 3] and mask[0, 5]
    a = np.full((6, 6), .02) + np.eye(6)
    out = mask_operator(a, mask)
    np.testing.assert_allclose(np.diag(out), np.diag(a))
    assert out[0, 3] == 0 and out[0, 5] == .02


def test_oracle_removes_identity_and_handles_zero_block():
    assert oracle_retention(np.zeros((3, 3)), 1e-6) == 0
    assert oracle_retention(np.diag([1., 1e-4, 1e-8]), 1e-3) == 1
