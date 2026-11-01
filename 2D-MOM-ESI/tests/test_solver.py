import numpy as np
import pytest

from mom_esi import make_domain, points_on_circle, simulate
from mom_esi.solver import EPSILON_0


def test_vacuum_has_no_scattered_field():
    result = simulate(np.ones((8, 8)), tx_count=3, rx_count=5)
    assert result.E_inc.shape == (64, 3)
    assert result.E_scattered.shape == (5, 3)
    np.testing.assert_array_equal(result.J, 0)
    np.testing.assert_array_equal(result.E_scattered, 0)
    np.testing.assert_array_equal(result.E_total, result.E_inc)


def test_current_constitutive_relation_and_image_order():
    epsilon = np.ones((10, 10))
    epsilon[2:6, 3:8] = 2.0
    result = simulate(epsilon, tx_count=2, rx_count=4)
    x_step = result.x_grid[0, 1] - result.x_grid[0, 0]
    xi = -1j * 2 * np.pi * 0.4e9 * EPSILON_0 * x_step**2 * (epsilon.T.reshape(-1) - 1)
    np.testing.assert_allclose(result.J, xi[:, None] * result.E_total, rtol=1e-11, atol=1e-11)
    np.testing.assert_array_equal(result.field_image("J"), result.J[:, 0].reshape(10, 10).T)
    assert np.linalg.norm(result.E_scattered) > 0


def test_geometry_and_input_validation():
    x, y = make_domain(4)
    assert x[0, 0] == -1 and y[0, 0] == 1
    np.testing.assert_allclose(points_on_circle(4)[0], [3, 0], atol=1e-15)
    with pytest.raises(ValueError, match="square"):
        simulate(np.ones((4, 5)))
    with pytest.raises(ValueError, match="positive"):
        simulate(np.zeros((4, 4)))
    with pytest.raises(ValueError, match="real"):
        simulate(np.ones((4, 4)) + 0.1j)
    with pytest.raises(ValueError, match="both"):
        simulate(np.ones((4, 4)), x_grid=x)
    with pytest.raises(ValueError, match="coincides"):
        simulate(np.ones((4, 4)), tx_xy=np.array([[x[0, 0], y[0, 0]]]))
