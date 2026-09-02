"""Geometry-only orchestration/CLI checks; no BIE/PDE solver errors."""

from __future__ import annotations

import csv
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import run_sdf_boundary_parameterization_comparison as comparison_cli
from sdf_to_ordered_boundary import experiment
from sdf_to_ordered_boundary.experiment import (
    analytic_comparison_shapes,
    comparison_profile,
    run_comparison_experiment,
)


_COMMON_CURVE_ARRAYS = {
    "gamma",
    "d1",
    "d2",
    "speed",
    "normal",
    "curvature",
    "shared_raw_contour",
    "shared_projected_contour",
}

_SCALAR_METRIC_COLUMNS = {
    "max_sdf_residual",
    "rms_sdf_residual",
    "minimum_speed",
    "speed_ratio",
    "self_intersections",
    "area",
    "perimeter",
    "reference_contour_discrepancy",
    "normal_discrepancy",
    "coefficient_tail",
    "coefficient_tail_order_1",
    "coefficient_tail_order_2",
    "runtime_seconds",
}


def test_builtin_shapes_and_profiles_define_the_requested_comparison_axes() -> None:
    shapes = analytic_comparison_shapes()
    assert tuple(shape.name for shape in shapes) == (
        "circle",
        "rotated_ellipse",
        "radial_fourier_star",
    )
    assert shapes[0].field.is_signed_distance
    assert not shapes[1].field.is_signed_distance
    assert not shapes[2].field.is_signed_distance
    assert shapes[1].parameters["rotation"] != 0.0
    assert shapes[2].parameters["lobes"] == 5

    smoke = comparison_profile("smoke")
    study = comparison_profile("study")
    assert smoke.grid_shapes == ((65, 65),)
    assert smoke.projected_sample_counts == (64,)
    assert smoke.bandwidths == (4, 8)
    assert len(study.grid_shapes) > len(smoke.grid_shapes)
    assert len(study.projected_sample_counts) > len(smoke.projected_sample_counts)
    assert len(study.bandwidths) > len(smoke.bandwidths)
    assert smoke.metrics.kress_sample_counts == (32, 64, 128)
    assert study.metrics.kress_sample_counts == (64, 128, 256, 512, 1024)


def test_tiny_circle_experiment_reuses_one_frontend_and_writes_complete_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    settings = replace(
        comparison_profile("smoke"),
        grid_shapes=((49, 49),),
        projected_sample_counts=(48,),
        bandwidths=(4,),
    )
    circle = analytic_comparison_shapes()[0]
    frontend_calls = 0
    original_prepare = experiment.prepare_single_component

    def counted_prepare(*args, **kwargs):
        nonlocal frontend_calls
        frontend_calls += 1
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(experiment, "prepare_single_component", counted_prepare)
    output = tmp_path / "artifacts"
    result = run_comparison_experiment(
        output,
        profile=settings,
        shapes=(circle,),
        make_plots=True,
    )

    assert frontend_calls == 1
    assert result.frontend_count == 1
    assert len(result.records) == 3
    assert tuple(record.method_label for record in result.records) == ("A", "B", "C")
    assert tuple(record.bandwidth for record in result.records) == (None, 4, 4)
    assert all(record.status == "success" for record in result.records)
    frontend_ids = {record.frontend_id for record in result.records}
    assert frontend_ids == {"circle__g49x49__m48"}
    assert {record.to_dict()["shared_frontend_id"] for record in result.records} == frontend_ids
    assert len({record.frontend_field_counts for record in result.records}) == 1
    counts = result.records[0].frontend_field_counts
    assert counts is not None
    assert counts.value_calls > 0
    assert counts.value_points > 49 * 49
    assert counts.gradient_calls > 0
    assert counts.gradient_points > 0
    method_b_record = result.records[1]
    method_c_record = result.records[2]
    assert method_c_record.initializer_field_counts == method_b_record.method_field_counts
    method_c_payload = method_c_record.to_dict()
    assert method_c_payload["converter_value_points"] == sum(
        item.value_points
        for item in (
            method_c_record.frontend_field_counts,
            method_c_record.initializer_field_counts,
            method_c_record.method_field_counts,
        )
    )

    assert result.manifest_path.is_file()
    assert result.metrics_json_path.is_file()
    assert result.metrics_csv_path.is_file()
    assert len(list((output / "frontends").glob("*.npz"))) == 1
    assert len(list((output / "frontends").glob("*.json"))) == 1
    assert len(list((output / "runs").glob("*.json"))) == 3
    assert len(list((output / "curves").glob("*.npz"))) == 3
    assert len(list((output / "plots").glob("*.png"))) == 3

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["active_solver_pipeline_modified"] is False
    assert manifest["measurement_scope"] == "geometry_parameterization"
    assert manifest["contains_bie_assembly"] is False
    assert manifest["contains_linear_solve"] is False
    assert manifest["contains_solver_error_metrics"] is False
    assert manifest["frontend_count"] == 1
    assert manifest["run_count"] == 3
    assert manifest["status_counts"] == {"success": 3}

    metrics_text = result.metrics_json_path.read_text(encoding="utf-8")
    assert "NaN" not in metrics_text
    assert "Infinity" not in metrics_text
    metrics_rows = json.loads(metrics_text)
    assert len(metrics_rows) == 3
    solver_only_fields = {
        "condition_number",
        "linear_system_residual",
        "relative_scattered_field_error",
        "scattered_field",
        "solved_density",
    }
    for row in metrics_rows:
        assert _SCALAR_METRIC_COLUMNS <= row.keys()
        assert solver_only_fields.isdisjoint(row)
        assert row["frontend_id"] == row["shared_frontend_id"]
        assert row["frontend_value_calls"] == counts.value_calls
        assert row["frontend_gradient_calls"] == counts.gradient_calls
        assert row["self_intersections"] == 0
        assert row["minimum_speed"] > 0.0
        assert row["runtime_seconds"] >= 0.0

    with result.metrics_csv_path.open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert len(csv_rows) == 3
    assert _SCALAR_METRIC_COLUMNS <= csv_rows[0].keys()
    assert {row["shared_frontend_id"] for row in csv_rows} == frontend_ids

    shared_raw = None
    shared_projected = None
    for record in result.records:
        npz_path = Path(record.artifact_paths["curve_npz"])
        plot_path = Path(record.artifact_paths["plot"])
        assert npz_path.is_file()
        assert plot_path.is_file()
        with np.load(npz_path, allow_pickle=False) as arrays:
            assert _COMMON_CURVE_ARRAYS <= set(arrays.files)
            if record.method_label == "A":
                assert {"spline_knots", "spline_coefficients"} <= set(arrays.files)
            else:
                assert {"cosine_coefficients", "sine_coefficients"} <= set(arrays.files)
            if shared_raw is None:
                shared_raw = arrays["shared_raw_contour"].copy()
                shared_projected = arrays["shared_projected_contour"].copy()
            else:
                np.testing.assert_array_equal(arrays["shared_raw_contour"], shared_raw)
                np.testing.assert_array_equal(
                    arrays["shared_projected_contour"], shared_projected
                )

    with pytest.raises(FileExistsError, match="must be empty"):
        run_comparison_experiment(
            output,
            profile=settings,
            shapes=(circle,),
            make_plots=False,
        )


def test_cli_applies_axis_overrides_and_shape_selection(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_run(output_directory, *, profile, shapes, make_plots):
        captured.update(
            output_directory=Path(output_directory),
            profile=profile,
            shapes=shapes,
            make_plots=make_plots,
        )
        record = SimpleNamespace(status="success", metrics_failure_reason=None)
        return SimpleNamespace(
            output_directory=Path(output_directory),
            frontend_count=1,
            records=(record,),
            status_counts={"success": 1},
            metrics_csv_path=Path(output_directory) / "metrics.csv",
            manifest_path=Path(output_directory) / "manifest.json",
        )

    monkeypatch.setattr(comparison_cli, "run_comparison_experiment", fake_run)
    destination = tmp_path / "cli"
    exit_code = comparison_cli.main(
        (
            "--profile",
            "smoke",
            "--output-dir",
            str(destination),
            "--shapes",
            "rotated_ellipse",
            "--grid-resolutions",
            "33x41",
            "--projected-samples",
            "32",
            "--bandwidths",
            "2,4",
            "--kress-samples",
            "32,64,128",
            "--no-plots",
        )
    )

    assert exit_code == 0
    assert captured["output_directory"] == destination
    assert captured["profile"].grid_shapes == ((33, 41),)
    assert captured["profile"].projected_sample_counts == (32,)
    assert captured["profile"].bandwidths == (2, 4)
    assert captured["profile"].metrics.kress_sample_counts == (32, 64, 128)
    assert tuple(shape.name for shape in captured["shapes"]) == ("rotated_ellipse",)
    assert captured["make_plots"] is False
