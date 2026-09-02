"""Geometry/readiness metrics for SDF conversion, not solver errors."""

from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from ordered_boundary import PeriodicParameterization2D, circle, ellipse
from sdf_to_ordered_boundary.artifacts import (
    plot_boundary_diagnostics,
    write_metrics_csv,
    write_npz,
    write_strict_json,
)
from sdf_to_ordered_boundary.fields import CallableImplicitField2D, CircleSDF
from sdf_to_ordered_boundary.metrics import (
    BoundaryMetricConfig,
    compute_boundary_metrics,
    frozen_curve_sampling_metrics,
    sample_parameterization,
    sampled_topology_metrics,
    sdf_residual_metrics,
)


def _metric_config(**updates) -> BoundaryMetricConfig:
    values = {
        "dense_resolution": 512,
        "reference_resolution": 512,
        "topology_resolution": 256,
        "fft_resolution": 512,
        "fft_tail_start_mode": 2,
        "kress_resolution": 128,
        "kress_sample_counts": (16, 32, 64),
        "kress_offsets": (
            2.0 * np.pi / 32.0,
            2.0 * np.pi / 64.0,
            2.0 * np.pi / 128.0,
            2.0 * np.pi / 256.0,
        ),
    }
    values.update(updates)
    return BoundaryMetricConfig(**values)


def test_exact_circle_metrics_cover_geometry_topology_spectrum_and_kress_limit() -> None:
    center = (0.2, -0.1)
    radius = 0.7
    field = CircleSDF(center, radius)
    reference = field.reference_parameterization(component_id="reference")
    candidate = field.reference_parameterization(component_id="candidate")
    metrics = compute_boundary_metrics(
        candidate,
        field=field,
        reference=reference,
        config=_metric_config(),
        winding_test_points=(center, (2.0, 2.0)),
    )

    assert metrics.sdf_residual is not None
    assert metrics.sdf_residual.maximum_absolute < 3.0e-15
    assert metrics.sdf_residual.normalized_maximum < 3.0e-15
    assert metrics.sdf_residual.minimum_gradient_norm == pytest.approx(1.0, abs=2.0e-15)

    geometry = metrics.integral_geometry
    assert geometry.signed_area == pytest.approx(np.pi * radius**2, rel=3.0e-14)
    assert geometry.perimeter == pytest.approx(2.0 * np.pi * radius, rel=3.0e-14)
    assert geometry.relative_area_error == pytest.approx(0.0, abs=1.0e-15)
    assert geometry.relative_perimeter_error == pytest.approx(0.0, abs=1.0e-15)

    comparison = metrics.reference_set
    assert comparison is not None
    assert comparison.symmetric_hausdorff < 2.0e-15
    assert comparison.symmetric_rms < 2.0e-15
    assert comparison.normal_angle_maximum_radians is not None
    assert comparison.normal_angle_maximum_radians < 3.0e-8
    assert comparison.curvature_absolute_maximum is not None
    assert comparison.curvature_absolute_maximum < 3.0e-15

    assert metrics.seam.position_error < 3.0e-15
    assert metrics.seam.first_derivative_error < 3.0e-15
    assert metrics.seam.second_derivative_error < 3.0e-15
    assert metrics.speed.minimum == pytest.approx(radius, rel=2.0e-15)
    assert metrics.speed.maximum == pytest.approx(radius, rel=2.0e-15)
    assert metrics.speed.ratio == pytest.approx(1.0, abs=2.0e-15)
    assert metrics.speed.coefficient_of_variation is not None
    assert metrics.speed.coefficient_of_variation < 3.0e-16

    assert metrics.topology.sampled_self_intersection_count == 0
    assert metrics.topology.minimum_nonlocal_distance is not None
    assert metrics.topology.minimum_nonlocal_distance > 0.0
    assert metrics.topology.winding[0].winding_number == pytest.approx(1.0, abs=2.0e-15)
    assert metrics.topology.winding[1].winding_number == pytest.approx(0.0, abs=2.0e-15)

    assert metrics.spectral_tail.order_0 is not None
    assert metrics.spectral_tail.order_1 is not None
    assert metrics.spectral_tail.order_2 is not None
    assert metrics.spectral_tail.order_0 < 1.0e-25
    assert metrics.spectral_tail.order_1 < 1.0e-21
    assert metrics.spectral_tail.order_2 < 1.0e-17
    assert all(item.maximum_absolute is not None for item in metrics.kress_diagonal)
    assert max(item.maximum_absolute for item in metrics.kress_diagonal) < 2.0e-12

    frozen = metrics.frozen_curve_sampling
    assert tuple(item.num_nodes for item in frozen) == (16, 32, 64)
    for item in frozen:
        assert item.parameter_step == pytest.approx(2.0 * np.pi / item.num_nodes)
        assert item.maximum_parameter_grid_error < 2.0e-15
        assert not item.includes_repeated_endpoint
        assert item.all_finite
        assert item.positive_speed
        assert item.counterclockwise
        assert item.minimum_speed == pytest.approx(radius, rel=2.0e-15)
        assert item.maximum_speed == pytest.approx(radius, rel=2.0e-15)
        assert item.speed_ratio == pytest.approx(1.0, abs=2.0e-15)
        assert item.minimum_log_speed == pytest.approx(np.log(radius), abs=2.0e-15)
        assert item.maximum_log_speed == pytest.approx(np.log(radius), abs=2.0e-15)
        expected_weight = 2.0 * np.pi * radius / item.num_nodes
        assert item.minimum_ds_weight == pytest.approx(expected_weight, rel=2.0e-15)
        assert item.maximum_ds_weight == pytest.approx(expected_weight, rel=2.0e-15)
        assert item.ds_weight_perimeter == pytest.approx(2.0 * np.pi * radius, rel=2.0e-15)
        assert item.dense_reference_perimeter == pytest.approx(
            metrics.integral_geometry.perimeter,
            rel=0.0,
            abs=0.0,
        )
        assert item.perimeter_absolute_error < 3.0e-15
        assert item.perimeter_relative_error < 8.0e-16
        assert item.signed_area == pytest.approx(np.pi * radius**2, rel=3.0e-14)


@pytest.mark.parametrize(
    ("counts", "error_type", "message"),
    (
        ((), ValueError, "at least one"),
        ((8, 15, 32), ValueError, "must be even"),
        ((2, 4, 8), ValueError, "at least 4"),
        ((8, 8, 16), ValueError, "duplicates"),
        ("8,16,32", TypeError, "sequence of even integers"),
    ),
)
def test_frozen_curve_sample_count_configuration_rejects_invalid_counts(
    counts,
    error_type,
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        BoundaryMetricConfig(kress_sample_counts=counts)


def test_frozen_curve_even_node_perimeter_converges_without_refitting() -> None:
    curve = ellipse(
        (0.1, -0.2),
        1.7,
        0.4,
        rotation=0.27,
        component_id="frozen-ellipse",
    )
    dense = sample_parameterization(curve, 65_536)
    dense_perimeter = curve.period * float(np.mean(dense.speeds))
    records = frozen_curve_sampling_metrics(
        curve,
        sample_counts=(8, 16, 32),
        dense_reference_perimeter=dense_perimeter,
    )

    assert tuple(item.num_nodes for item in records) == (8, 16, 32)
    errors = np.asarray([item.perimeter_absolute_error for item in records])
    assert np.all(errors[1:] < errors[:-1])
    assert errors[1] < 0.1 * errors[0]
    assert errors[2] < 0.01 * errors[1]
    assert all(item.dense_reference_perimeter == dense_perimeter for item in records)
    assert all(item.positive_speed and item.counterclockwise for item in records)

    configured = _metric_config(
        dense_resolution=4096,
        reference_resolution=256,
        topology_resolution=128,
        fft_resolution=256,
        kress_sample_counts=(8, 16, 32),
    )
    metrics = compute_boundary_metrics(
        curve,
        config=configured,
        winding_test_points=((0.1, -0.2),),
    )
    assert tuple(item.num_nodes for item in metrics.frozen_curve_sampling) == (8, 16, 32)
    payload = metrics.to_dict()["frozen_curve_sampling"][0]
    assert {
        "num_nodes",
        "parameter_step",
        "includes_repeated_endpoint",
        "positive_speed",
        "counterclockwise",
        "minimum_log_speed",
        "maximum_log_speed",
        "minimum_ds_weight",
        "maximum_ds_weight",
        "ds_weight_perimeter",
        "dense_reference_perimeter",
        "perimeter_absolute_error",
        "perimeter_relative_error",
    } <= payload.keys()


def test_reference_set_metrics_are_phase_invariant_instead_of_same_parameter_errors() -> None:
    radius = 0.9
    reference = circle((0.1, -0.2), radius, component_id="reference")
    shift = 0.371
    candidate = reference.with_parameter_shift(shift, component_id="phase-shifted")
    config = _metric_config(
        dense_resolution=4096,
        reference_resolution=8192,
        topology_resolution=128,
    )
    metrics = compute_boundary_metrics(
        candidate,
        reference=reference,
        config=config,
        winding_test_points=((0.1, -0.2),),
    )
    comparison = metrics.reference_set
    assert comparison is not None

    parameters = 2.0 * np.pi * np.arange(config.dense_resolution) / config.dense_resolution
    naive_same_parameter_error = float(
        np.max(
            np.linalg.norm(
                candidate.evaluate(parameters).points - reference.evaluate(parameters).points,
                axis=1,
            )
        )
    )
    assert naive_same_parameter_error > 0.2
    # The remaining error is only the deliberately reported discrete cKDTree
    # reference-sampling floor, not the O(shift) same-parameter discrepancy.
    assert comparison.symmetric_hausdorff < 6.0e-4
    assert comparison.symmetric_hausdorff < 0.005 * naive_same_parameter_error
    assert comparison.normal_angle_maximum_radians is not None
    assert comparison.normal_angle_maximum_radians < 3.0e-4
    assert comparison.curvature_absolute_maximum is not None
    assert comparison.curvature_absolute_maximum < 2.0e-15


def test_normalized_implicit_residual_is_invariant_to_field_scaling() -> None:
    radius = 0.7
    offset_curve = circle((0.0, 0.0), radius + 0.03, component_id="offset")
    points = sample_parameterization(offset_curve, 256).points

    def make_field(scale: float) -> CallableImplicitField2D:
        def value(xy: np.ndarray) -> np.ndarray:
            return scale * (np.linalg.norm(xy, axis=-1) - radius)

        def gradient(xy: np.ndarray) -> np.ndarray:
            norm = np.linalg.norm(xy, axis=-1)
            return scale * xy / norm[..., None]

        return CallableImplicitField2D(value, gradient, name=f"scaled_{scale:g}")

    unscaled = sdf_residual_metrics(make_field(1.0), points)
    scaled = sdf_residual_metrics(make_field(7.0), points)
    assert scaled.maximum_absolute == pytest.approx(7.0 * unscaled.maximum_absolute)
    assert scaled.rms == pytest.approx(7.0 * unscaled.rms)
    assert scaled.normalized_maximum == pytest.approx(
        unscaled.normalized_maximum, rel=2.0e-13
    )
    assert scaled.normalized_rms == pytest.approx(unscaled.normalized_rms, rel=2.0e-13)


def test_sampled_topology_detects_a_smooth_self_intersection() -> None:
    def gerono(parameters: np.ndarray):
        points = np.stack(
            (np.sin(parameters), np.sin(parameters) * np.cos(parameters)),
            axis=-1,
        )
        first = np.stack((np.cos(parameters), np.cos(2.0 * parameters)), axis=-1)
        second = np.stack((-np.sin(parameters), -2.0 * np.sin(2.0 * parameters)), axis=-1)
        return points, first, second

    curve = PeriodicParameterization2D("gerono", gerono)
    points = sample_parameterization(curve, 256).points
    topology = sampled_topology_metrics(
        points,
        nonlocal_exclusion_fraction=0.02,
        winding_test_points=((0.2, 0.1),),
    )
    assert topology.sampled_self_intersection_count > 0
    assert topology.minimum_nonlocal_distance == pytest.approx(0.0, abs=1.0e-15)


def test_artifact_writers_are_strict_and_plot_the_required_panels(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    field = CircleSDF((0.0, 0.0), 0.8)
    curve = field.reference_parameterization(component_id="circle")
    config = _metric_config(
        dense_resolution=256,
        reference_resolution=256,
        topology_resolution=128,
        fft_resolution=256,
        kress_resolution=64,
    )
    metrics = compute_boundary_metrics(
        curve,
        field=field,
        reference=curve,
        config=config,
        winding_test_points=((0.0, 0.0),),
    )

    json_path = write_strict_json(
        tmp_path / "metrics.json",
        {"status": "success", "metrics": metrics, "missing": np.nan},
    )
    text = json_path.read_text(encoding="utf-8")
    assert "NaN" not in text
    assert "Infinity" not in text
    payload = json.loads(text)
    assert payload["missing"] is None
    assert payload["metrics"]["component_id"] == "circle"

    csv_path = write_metrics_csv(
        tmp_path / "metrics.csv",
        ({"run_id": "circle", "metrics": metrics.to_dict(), "failed_value": np.inf},),
    )
    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["run_id"] == "circle"
    assert rows[0]["failed_value"] == ""
    assert "metrics.sdf_residual.maximum_absolute" in rows[0]
    assert b"\r\n" not in csv_path.read_bytes()

    samples = sample_parameterization(curve, 64).points
    npz_path = write_npz(
        tmp_path / "curve_samples.npz",
        points=samples,
        parameters=np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False),
    )
    with np.load(npz_path, allow_pickle=False) as archive:
        np.testing.assert_allclose(archive["points"], samples)
        assert archive["parameters"].shape == (64,)
    with pytest.raises(TypeError, match="object dtype"):
        write_npz(tmp_path / "unsafe.npz", values=np.asarray([{"unsafe": True}], dtype=object))

    raw = 1.01 * samples
    figure_path = plot_boundary_diagnostics(
        tmp_path / "diagnostics.png",
        curve,
        field=field,
        reference=curve,
        raw_contour=raw,
        projected_contour=samples,
        config=config,
        title="circle metric artifact",
    )
    assert figure_path.is_file()
    assert figure_path.stat().st_size > 10_000
