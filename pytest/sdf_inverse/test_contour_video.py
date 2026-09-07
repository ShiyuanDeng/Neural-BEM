"""Fast checks for visual interpolation of stored inverse contours."""

from __future__ import annotations

import numpy as np

from run_sdf_inverse_contour_video import _read_trajectory, _stage_contour


def test_periodic_morph_aligns_phase_and_retains_stored_endpoints() -> None:
    angles = np.linspace(0.0, 2.0 * np.pi, 12, endpoint=False)
    current = np.column_stack((np.cos(angles), np.sin(angles)))
    following_in_current_phase = 1.15 * current + np.array([0.2, -0.1])
    stored_following = np.roll(following_in_current_phase, 4, axis=0)
    geometry = np.stack((current, stored_following))

    start, start_index = _stage_contour(geometry, stage=0, alpha=0.0)
    midpoint, midpoint_index = _stage_contour(geometry, stage=0, alpha=0.5)
    end, end_index = _stage_contour(geometry, stage=0, alpha=1.0)

    np.testing.assert_array_equal(start, current)
    np.testing.assert_allclose(
        midpoint,
        0.5 * (current + following_in_current_phase),
        rtol=0.0,
        atol=1.0e-15,
    )
    np.testing.assert_array_equal(end, stored_following)
    assert (start_index, midpoint_index, end_index) == (0, 0, 1)


def test_continuation_stage_metadata_survives_trajectory_loading(tmp_path) -> None:
    path = tmp_path / "trajectory.csv"
    path.write_text(
        "iteration,loss,relative_l2_error,stage,stage_iteration,"
        "stage_maximum_mode,stage_train_frequencies_ghz\n"
        "0,1.0,1.0,1,0,1,0.5\n"
        '1,0.8,0.9,2,0,3,"0.5,1.5"\n',
        encoding="utf-8",
    )

    trajectory = _read_trajectory(path)

    np.testing.assert_array_equal(trajectory["stage"], (1.0, 2.0))
    np.testing.assert_array_equal(trajectory["stage_iteration"], (0.0, 0.0))
    np.testing.assert_array_equal(trajectory["stage_maximum_mode"], (1.0, 3.0))
    assert trajectory["stage_train_frequencies_ghz"].tolist() == [
        "0.5",
        "0.5,1.5",
    ]
