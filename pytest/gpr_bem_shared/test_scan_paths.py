from __future__ import annotations

import numpy as np

import config.simulation_config as cfg
from gpr_bem.scan_paths import build_rectangular_bistatic_scan, subset_rectangular_loop_scan


def test_rectangular_bistatic_scan_matches_canonical_configuration() -> None:
    scan = build_rectangular_bistatic_scan(
        left=cfg.SCAN_RECT_LEFT,
        right=cfg.SCAN_RECT_RIGHT,
        top=cfg.SCAN_RECT_TOP,
        bottom=cfg.SCAN_RECT_BOTTOM,
        separation=cfg.TX_RX_OFFSET,
        top_count=cfg.SCAN_RECT_TOP_COUNT,
        right_count=cfg.SCAN_RECT_RIGHT_COUNT,
        bottom_count=cfg.SCAN_RECT_BOTTOM_COUNT,
        left_count=cfg.SCAN_RECT_LEFT_COUNT,
    )

    expected_count = (
        int(cfg.SCAN_RECT_TOP_COUNT)
        + int(cfg.SCAN_RECT_RIGHT_COUNT)
        + int(cfg.SCAN_RECT_BOTTOM_COUNT)
        + int(cfg.SCAN_RECT_LEFT_COUNT)
    )
    assert scan.center_points.shape == (expected_count, 2)
    assert scan.source_points.shape == (expected_count, 2)
    assert scan.receiver_points.shape == (expected_count, 2)
    np.testing.assert_allclose(
        np.linalg.norm(scan.receiver_points - scan.source_points, axis=1),
        float(cfg.TX_RX_OFFSET),
        rtol=0.0,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(scan.center_points[0], np.array([0.27, 0.32], dtype=float), atol=1.0e-12)
    np.testing.assert_allclose(scan.center_points[-1], np.array([0.24, 0.35], dtype=float), atol=1.0e-12)
    assert tuple(scan.edge_names) == ("top", "right", "bottom", "left")
    assert scan.edge_boundaries.shape == (3,)


def test_subset_rectangular_loop_scan_recomputes_boundaries() -> None:
    scan = build_rectangular_bistatic_scan(
        left=cfg.SCAN_RECT_LEFT,
        right=cfg.SCAN_RECT_RIGHT,
        top=cfg.SCAN_RECT_TOP,
        bottom=cfg.SCAN_RECT_BOTTOM,
        separation=cfg.TX_RX_OFFSET,
        top_count=cfg.SCAN_RECT_TOP_COUNT,
        right_count=cfg.SCAN_RECT_RIGHT_COUNT,
        bottom_count=cfg.SCAN_RECT_BOTTOM_COUNT,
        left_count=cfg.SCAN_RECT_LEFT_COUNT,
    )

    subset = subset_rectangular_loop_scan(scan, np.arange(0, scan.center_points.shape[0], 4, dtype=int))
    assert subset.center_points.shape[0] == int(np.arange(0, scan.center_points.shape[0], 4, dtype=int).size)
    assert subset.edge_boundaries.shape == (3,)
    assert np.all(np.diff(subset.path_coordinate) > 0.0)
