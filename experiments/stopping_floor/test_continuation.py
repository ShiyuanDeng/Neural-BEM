"""The supplemental acceptance gate must reject unresolvable decreases."""
from types import SimpleNamespace

import numpy as np

from experiments.stopping_floor.continue_top010 import gain_check, training_data


def ev(loss):
    return SimpleNamespace(loss=loss, residual=np.array([np.sqrt(2 * loss)]))


def test_agreed_gain_below_historical_absolute_floor_is_allowed():
    row = gain_check(ev(2.3e-9), ev(2.29e-9), ev(2.4e-9), ev(2.39e-9))
    assert row["accepted"]
    assert row["production_gain"] < 1e-10


def test_resolution_disagreement_rejects_apparent_coarse_descent():
    row = gain_check(ev(2.3e-9), ev(2.2e-9), ev(2.4e-9), ev(2.41e-9))
    assert not row["accepted"]
    assert row["refined_gain"] < 0


def test_roundoff_scale_decrease_is_not_certified():
    row = gain_check(ev(2.3e-9), ev(2.3e-9 - 1e-21), ev(2.3e-9), ev(2.3e-9 - 1e-21))
    assert not row["accepted"]


def test_only_training_frequency_enters_problem():
    data = training_data()
    np.testing.assert_array_equal(data.forward_problem.angular_frequencies / (2 * np.pi), [5e8])
    assert data.observed_scattered_response.shape == (24, 1)
