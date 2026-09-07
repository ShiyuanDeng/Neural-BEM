"""Physical experiment artifacts must survive changes to default materials."""

from __future__ import annotations

import json

import numpy as np
import pytest

pytest.importorskip("torch")

from run_mlp_sdf_inverse_comparison import _build_target, _experiment_snapshot
from run_sdf_inverse_comparison import physical_config
from sdf_inverse import MaterialSpec, PairedForwardProblem


@pytest.mark.parametrize("target_name", ["circle", "star"])
def test_experiment_json_replays_physics_after_defaults_change(
    target_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _build_target(target_name)
    problem = PairedForwardProblem(
        source_points=np.array([[0.1, 0.2], [0.8, 0.7]]),
        receiver_points=np.array([[0.1, 0.25], [0.8, 0.75]]),
        angular_frequencies=2.0 * np.pi * np.array([0.5e9, 1.5e9]),
        source_strengths=np.array([1.0e-6 + 2.0e-6j, -3.0e-6 - 4.0e-6j]),
        exterior=MaterialSpec(epsr=5.3, sigma=0.004, mur=1.1),
        interior=MaterialSpec(epsr=2.7, sigma=0.006, mur=1.2),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )
    snapshot = _experiment_snapshot(problem, target)
    serialized = json.dumps(snapshot, allow_nan=False)

    monkeypatch.setattr(physical_config, "SAND_EPSR", 19.0)
    monkeypatch.setattr(physical_config, "PLASTIC_EPSR", 29.0)
    monkeypatch.setattr(physical_config, "EPS0", 1.0)
    monkeypatch.setattr(physical_config, "MU0", 2.0)
    restored = json.loads(serialized)
    replay = PairedForwardProblem(
        source_points=restored["source_points_m"],
        receiver_points=restored["receiver_points_m"],
        angular_frequencies=restored["angular_frequencies_rad_s"],
        source_strengths=(
            np.asarray(restored["source_strengths"]["real"])
            + 1j * np.asarray(restored["source_strengths"]["imag"])
        ),
        exterior=MaterialSpec(**restored["exterior"]),
        interior=MaterialSpec(**restored["interior"]),
        eps0=restored["eps0_f_per_m"],
        mu0=restored["mu0_h_per_m"],
    )

    for name in (
        "source_points", "receiver_points", "angular_frequencies", "source_strengths"
    ):
        np.testing.assert_array_equal(getattr(replay, name), getattr(problem, name))
    assert replay.exterior == problem.exterior
    assert replay.interior == problem.interior
    assert replay.eps0 == problem.eps0
    assert replay.mu0 == problem.mu0
    assert restored["num_pairs"] == problem.num_pairs
    assert restored["observation_noise"] == "none"
    assert restored["measurement"] == "paired_complex_scattered_field"
    assert restored["target_parameters"] == target.parameter_dict()
