"""Optional check against the separately downloaded official clean test fields.

Set MOM_ESI_SINGLETX_TEST_ROOT to a trusted directory containing
mnist/mnist_test.pkl and cylinder/cylinder_test.pkl. Never unpickle untrusted files.
"""

import os
import pickle
from pathlib import Path

import numpy as np
import pytest

from mom_esi import points_on_circle, simulate


@pytest.mark.parametrize("dataset,sample", [("mnist", 8), ("cylinder", 2)])
def test_official_clean_fields(dataset: str, sample: int):
    root = os.environ.get("MOM_ESI_SINGLETX_TEST_ROOT")
    if not root:
        pytest.skip("Set MOM_ESI_SINGLETX_TEST_ROOT for optional official-data validation")
    path = Path(root) / dataset / f"{dataset}_test.pkl"
    with path.open("rb") as handle:
        official = pickle.load(handle)
    data = official["data"]
    result = simulate(
        data["epsilon_gt"][sample],
        x_grid=data["x_dom"],
        y_grid=data["y_dom"],
        tx_xy=data["xy_t"],
        rx_xy=points_on_circle(32),
    )
    expected_scattered = data["E_s_real"][sample] + 1j * data["E_s_imag"][sample]
    expected_incident = data["E_inc_real"] + 1j * data["E_inc_imag"]
    for actual, expected in [(result.E_scattered, expected_scattered),
                             (result.E_inc, expected_incident)]:
        relative_error = np.linalg.norm(actual - expected) / np.linalg.norm(expected)
        assert relative_error < 1e-4

