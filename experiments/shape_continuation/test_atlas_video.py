import numpy as np

from experiments.shape_continuation import atlas_video as av


def test_removable_without_cap_is_the_sequential_projection():
    rng = np.random.default_rng(0)
    A = rng.normal(size=(48, 2 * av.BAND + 1))
    r = rng.normal(size=48)
    d, sensitivity = av.removable(A, r, np.inf)
    Q, _ = np.linalg.qr(A)
    assert np.isclose(d.sum(), np.sum((Q.T @ r) ** 2))           # whole column span, split by order
    assert np.isclose(d[0], (Q[:, 0] @ r) ** 2)                    # order 0 claims its direction first
    assert sensitivity[24] > 0 and np.all(sensitivity[25:] == 0)    # 48 rows: order 24's cosine is the last new column


def test_legacy_cap_arithmetic_is_preserved_without_a_physical_step_claim():
    A = np.diag([1.0, 1e-3, 1e-3] + [1e-6] * (2 * av.BAND - 2))
    r = np.ones(len(A))
    d, _ = av.removable(A, r, amplitude=10.0)
    assert np.isclose(d[0], 1.0)                                    # needs a 1 mm step: allowed
    assert np.isclose(d[1], 2 * (1e-3 * 10) ** 2)                   # needs 1000 mm: capped at 10 mm


def test_frontier_is_last_order_before_first_drop_below_noise():
    sensitivity = np.array([1.0, .5, .2, .005, .5])
    assert av.frontier(sensitivity, amplitude=1.0) == 2             # stops at the first drop, not the rebound


def test_position_spectrum_reads_a_single_ripple_on_a_circle():
    band, m, a = 12, 5, 0.01                                        # r = 1 + a cos(m s) about the unit circle
    c = np.zeros(2 * band + 1, complex)
    c[band + 1] = 1.0
    c[band + 1 + m] = c[band + 1 - m] = a / 2
    shown, tail = av.position_spectrum(c, unit_mm=1.0)
    assert np.isclose(shown[0], 1.0)
    assert np.isclose(shown[m], a / np.sqrt(2))                     # RMS of a cos(m s)
    assert np.allclose(np.delete(shown, [0, m]), 0) and not any(tail)
