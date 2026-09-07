"""Component-aware trajectory storage tests."""

from __future__ import annotations

import numpy as np
import pytest

from ordered_boundary import OrderedBoundary2D, circle
from sdf_bem_multicomponent.trajectory import (
    BoundaryTrajectoryFrame,
    RaggedBoundaryTrajectory,
    SOLVER_READY,
    TOPOLOGY_TRANSITION,
)


def _circle_boundary(*centers: tuple[float, float]) -> OrderedBoundary2D:
    return OrderedBoundary2D(
        tuple(
            circle(
                center,
                0.04,
                component_id=f"component_{index:03d}",
            ).discretize(16, require_even=True)
            for index, center in enumerate(centers)
        )
    )


def test_ragged_trajectory_roundtrip_preserves_one_to_two_split(tmp_path) -> None:
    one = BoundaryTrajectoryFrame.from_boundary(
        _circle_boundary((0.5, 0.5)),
        parameter=0.0,
        component_ids=("object",),
    )
    critical = BoundaryTrajectoryFrame(
        parameter=0.5,
        status=TOPOLOGY_TRANSITION,
        components=(
            np.asarray(((0.5, 0.5), (0.45, 0.54), (0.4, 0.5), (0.5, 0.5))),
            np.asarray(((0.5, 0.5), (0.55, 0.46), (0.6, 0.5), (0.5, 0.5))),
        ),
        component_ids=("object.left", "object.right"),
        parent_ids=("object", "object"),
        message="The zero set is singular at the shared pinch point.",
    )
    two = BoundaryTrajectoryFrame.from_boundary(
        _circle_boundary((0.43, 0.5), (0.57, 0.5)),
        parameter=1.0,
        component_ids=("object.left", "object.right"),
        parent_ids=("object", "object"),
    )

    trajectory = RaggedBoundaryTrajectory.from_frames(
        (one, critical, two),
        parameter_name="split_progress",
    )

    assert trajectory.num_frames == 3
    assert trajectory.num_stored_components == 5
    np.testing.assert_array_equal(trajectory.frame_component_offsets, (0, 1, 3, 5))
    np.testing.assert_array_equal(
        trajectory.component_point_offsets,
        (0, 16, 20, 24, 40, 56),
    )
    assert tuple(trajectory.frame(index).num_components for index in range(3)) == (
        1,
        2,
        2,
    )
    assert not trajectory.frame(1).solver_ready
    assert trajectory.frame(1).parent_ids == ("object", "object")

    path = trajectory.save_npz(tmp_path / "trajectory.npz")
    loaded = RaggedBoundaryTrajectory.load_npz(path)
    np.testing.assert_array_equal(loaded.points, trajectory.points)
    np.testing.assert_array_equal(
        loaded.component_point_offsets,
        trajectory.component_point_offsets,
    )
    np.testing.assert_array_equal(
        loaded.frame_component_offsets,
        trajectory.frame_component_offsets,
    )
    assert loaded.statuses == trajectory.statuses
    assert loaded.component_ids == trajectory.component_ids
    assert loaded.component_parent_ids == trajectory.component_parent_ids
    assert loaded.parameter_name == "split_progress"
    assert not loaded.points.flags.writeable

    extensionless_path = trajectory.save_npz(tmp_path / "extensionless")
    assert extensionless_path.name == "extensionless.npz"
    assert extensionless_path.is_file()
    assert RaggedBoundaryTrajectory.load_npz(extensionless_path).num_frames == 3


def test_frame_index_requires_an_integer() -> None:
    trajectory = RaggedBoundaryTrajectory.from_frames(
        (
            BoundaryTrajectoryFrame.from_boundary(
                _circle_boundary((0.5, 0.5)),
                parameter=0.0,
            ),
        )
    )

    with pytest.raises(TypeError, match="must be an integer"):
        trajectory.frame(0.9)
    with pytest.raises(TypeError, match="not bool"):
        trajectory.frame(True)
    assert trajectory.frame(np.int64(0)).num_components == 1


def test_frame_requires_explicit_reason_for_non_solver_geometry() -> None:
    with pytest.raises(ValueError, match="must explain"):
        BoundaryTrajectoryFrame(
            parameter=0.5,
            status=TOPOLOGY_TRANSITION,
            components=(np.asarray(((0.0, 0.0), (1.0, 1.0))),),
        )


def test_dense_shape_assumptions_are_not_reintroduced() -> None:
    frames = (
        BoundaryTrajectoryFrame(
            parameter=0.0,
            status=SOLVER_READY,
            components=(np.zeros((8, 2)),),
        ),
        BoundaryTrajectoryFrame(
            parameter=1.0,
            status=SOLVER_READY,
            components=(np.zeros((10, 2)), np.ones((14, 2))),
        ),
    )
    trajectory = RaggedBoundaryTrajectory.from_frames(frames)

    assert trajectory.frame(0).components[0].shape == (8, 2)
    assert tuple(component.shape for component in trajectory.frame(1).components) == (
        (10, 2),
        (14, 2),
    )


def test_corrupt_offsets_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least two points"):
        RaggedBoundaryTrajectory(
            points=np.zeros((3, 2)),
            component_point_offsets=np.asarray((0, 1, 3)),
            frame_component_offsets=np.asarray((0, 2)),
            parameters=np.asarray((0.0,)),
            statuses=(SOLVER_READY,),
            component_ids=("a", "b"),
            component_parent_ids=("", ""),
            messages=("",),
        )
