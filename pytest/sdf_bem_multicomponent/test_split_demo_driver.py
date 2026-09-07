"""Contract tests for the checked one-to-two demo driver."""

from __future__ import annotations

import numpy as np
import pytest

from run_multicomponent_split_demo import (
    build_demo_trajectory,
    render_split_video,
    split_progress_schedule,
)
from sdf_bem_multicomponent import (
    BoundaryTrajectoryFrame,
    CassiniSplitTrajectory2D,
    MultiComponentOrderedSDFGeometryConfig,
    RaggedBoundaryTrajectory,
    SOLVER_READY,
    TOPOLOGY_TRANSITION,
)


def _quick_config() -> MultiComponentOrderedSDFGeometryConfig:
    return MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.20, 0.20), (0.80, 0.80)),
        expected_num_components=None,
        grid_shape=(129, 129),
        projected_samples=64,
        bandwidth=10,
        num_nodes=64,
        arclength_dense_resolution=128,
        validation_resolution=128,
        minimum_intercomponent_clearance=0.0,
    )


def test_progress_schedule_contains_one_exact_noninterpolated_event() -> None:
    progress = split_progress_schedule(60, 0.55)

    assert progress.shape == (60,)
    assert np.all(np.diff(progress) > 0.0)
    assert progress[0] == 0.0
    assert progress[-1] == 1.0
    assert np.count_nonzero(progress == 0.55) == 1


def test_demo_uses_auto_extraction_on_both_sides_and_raw_data_only_at_pinch() -> None:
    analytic = CassiniSplitTrajectory2D()
    progress = split_progress_schedule(7, analytic.critical_progress)

    artifact, diagnostics, endpoint = build_demo_trajectory(
        analytic,
        progress,
        _quick_config(),
    )

    assert artifact.num_frames == 7
    assert len(diagnostics) == 7
    critical = artifact.statuses.index(TOPOLOGY_TRANSITION)
    assert all(
        status == SOLVER_READY
        for index, status in enumerate(artifact.statuses)
        if index != critical
    )
    assert tuple(artifact.frame(index).num_components for index in range(critical)) == (
        1,
    ) * critical
    assert tuple(
        artifact.frame(index).num_components
        for index in range(critical + 1, artifact.num_frames)
    ) == (2,) * (artifact.num_frames - critical - 1)
    assert diagnostics[critical]["detected_num_components"] is None
    assert all(
        diagnostics[index]["grid_parity_confirmation"] is not None
        for index in range(artifact.num_frames)
        if index != critical
    )
    assert endpoint.num_components == 2
    np.testing.assert_array_equal(endpoint.component_offsets, (0, 64, 128))

    event = artifact.frame(critical)
    center = np.asarray(analytic.config.center)
    assert event.parent_ids == ("object", "object")
    for lobe in event.components:
        np.testing.assert_array_equal(lobe[0], center)
        np.testing.assert_array_equal(lobe[-1], center)

    first_post_split = artifact.frame(critical + 1)
    left, right = first_post_split.components
    # Two independently stored loops: no artificial segment spans their gap.
    assert float(np.max(left[:, 0])) < float(np.min(right[:, 0]))


def test_fixture_renderer_never_silently_omits_a_third_component(tmp_path) -> None:
    components = tuple(
        np.asarray(
            (
                (0.1 + 0.2 * index, 0.1),
                (0.14 + 0.2 * index, 0.1),
                (0.12 + 0.2 * index, 0.14),
            ),
            dtype=np.float64,
        )
        for index in range(3)
    )
    artifact = RaggedBoundaryTrajectory.from_frames(
        (
            BoundaryTrajectoryFrame(
                parameter=0.0,
                status=SOLVER_READY,
                components=components,
            ),
        )
    )

    with pytest.raises(ValueError, match="accepts at most two components"):
        render_split_video(
            artifact,
            CassiniSplitTrajectory2D(),
            tmp_path / "must-not-be-written.mp4",
            fps=5,
            dpi=50,
        )
    assert not (tmp_path / "must-not-be-written.mp4").exists()
