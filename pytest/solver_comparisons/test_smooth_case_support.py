"""Fast contract tests for shared smooth-scene comparison orchestration."""

from __future__ import annotations

import numpy as np
import pytest

from comparison_contract import validate_cached_pair0_coordinates


def test_gprmax_pair_zero_validation_is_translation_invariant() -> None:
    scene_center = (0.5, 0.5)
    sources = np.asarray(((0.8, 0.5), (0.5, 0.8)))
    receivers = np.asarray(((0.792, 0.559), (0.441, 0.792)))
    cached_center = np.asarray((0.074, 0.074))
    entry = {
        "target_center": cached_center,
        "tx": cached_center + sources[0] - scene_center,
        "rx": cached_center + receivers[0] - scene_center,
    }

    validate_cached_pair0_coordinates(
        entry,
        sources,
        receivers,
        scene_center=scene_center,
    )


def test_gprmax_pair_zero_validation_rejects_a_relative_scan_mismatch() -> None:
    scene_center = (0.5, 0.5)
    sources = np.asarray(((0.8, 0.5),))
    receivers = np.asarray(((0.792, 0.559),))
    entry = {
        "target_center": (0.074, 0.074),
        "tx": (0.374, 0.074),
        "rx": (0.367, 0.133),
    }

    with pytest.raises(ValueError, match="receiver offset"):
        validate_cached_pair0_coordinates(
            entry,
            sources,
            receivers,
            scene_center=scene_center,
        )
