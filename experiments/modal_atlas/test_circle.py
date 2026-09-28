import warnings

import numpy as np

from . import circle as c
from .circle_study import horizon, pole


def test_modal_hadamard_matches_exact_dilation_difference():
    k, contrast, rho = 3.0, 10.0, 3.0
    phi = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    U = c.trace_coefficients(k, contrast, rho, phi, 80)
    eps = 1e-6
    fd = (c.scattered(k, contrast, rho, phi, rho, phi, 60, 1 + eps)
          - c.scattered(k, contrast, rho, phi, rho, phi, 60, 1 - eps)) / (2 * eps)
    J = c.sensitivity(U, U, 0, k, contrast)
    assert np.linalg.norm(fd - J) / np.linalg.norm(fd) < 1e-7


def test_single_pole_horizon_constant():
    warnings.simplefilter('ignore', RuntimeWarning)
    ks = pole(8, 3.478, 10.0)
    for detune in (0.0, 3.0):
        k = ks.real + detune * abs(ks.imag)
        eps, _ = horizon(k, 10.0)
        assert 0.08 < eps * abs(ks) / abs(k - ks) < 0.14
