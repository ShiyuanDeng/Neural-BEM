"""Startup failures preserve exact pretrained weights and their failing stage."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

import run_implicit_mlp_ellipse_startup as startup
from sdf_inverse.geometry import OrderedSDFGeometryConfig
from sdf_inverse.implicit_adjoint import ImplicitMLPAdjointConfig
from sdf_inverse.models import CircleSDF2D
from sdf_inverse.eikonal_sampling import regularization_points


def test_contour_sampling_uses_dtype_qualified_projection_for_float32():
    model = CircleSDF2D(center=(.5, .5), radius=.058).float()
    config = OrderedSDFGeometryConfig(bounds=((.3, .3), (.7, .7)), grid_shape=(65, 65))
    points = regularization_points(model, config, ImplicitMLPAdjointConfig(eikonal_sampling="contour_band"))
    assert points.dtype == torch.float32
    assert points.shape == (512, 2)
    assert torch.isfinite(points).all()


def test_production_refinement_distance_does_not_reject_identical_phase_shifted_circle():
    t = np.arange(64) * 2*np.pi / 64
    first = .05 * np.column_stack((np.cos(t), np.sin(t)))
    second = .05 * np.column_stack((np.cos(t + np.pi/64), np.sin(t + np.pi/64)))
    assert startup.maximum_curve_set_distance(first, second) > .00001
    assert startup._production_refinement_distance(first, second) < 1.e-6


def test_unexpected_geometry_failure_records_stage_and_saved_weights(monkeypatch, tmp_path):
    model = CircleSDF2D(center=(.5, .5), radius=.058)
    output = tmp_path / "startup"
    monkeypatch.setattr(startup.driver, "_build_initial_model", lambda *a, **kw: (model, object()))
    def save_initial(path, saved_model, *args):
        torch.save(saved_model.state_dict(), path)
    monkeypatch.setattr(startup.driver, "_write_initial_neural_checkpoint", save_initial)
    def fail_geometry(saved_model, config):
        assert (output / "initial_model.pt").exists()
        assert config.conversion_audit_grid_shape == (513, 513)
        assert config.conversion_audit_samples == 512
        raise RuntimeError("deliberate failing geometry stage")
    monkeypatch.setattr(startup, "build_ordered_sdf_geometry", fail_geometry)
    assert startup.main(["--output-dir", str(output), "--pretrain-steps", "1"]) == 1
    report = json.loads((output / "qualification.json").read_text())
    assert report["stage"] == "geometry_qualification"
    assert report["status"] == "failed"
    assert "deliberate failing geometry stage" in (output / "failure_traceback.txt").read_text()
    assert "deliberate failing geometry stage" in (output / "stderr.log").read_text()
    saved = torch.load(output / "initial_model.pt", weights_only=True)
    for key, value in model.state_dict().items():
        torch.testing.assert_close(saved[key], value, rtol=0, atol=0)


def test_initial_contour_diagnostic_compares_prescribed_ellipse_not_inverse_truth():
    model = startup.driver._analytic_shape_for_siren("siren_ellipse")
    config = OrderedSDFGeometryConfig(bounds=((.3, .3), (.7, .7)), conversion_tolerance_m=.0002)
    report = startup._initial_contour_characterization(model, config)
    assert report["raw_to_intended_ellipse_set_distance_m"] < 1.e-6
    assert report["initial_shape_mismatch_exceeds_conversion_budget"] is False
    assert report["component_count"] == 1


def test_failed_conversion_sweep_reports_numeric_gates_and_never_starts_smoke(monkeypatch, tmp_path):
    from sdf_inverse.geometry import OrderedSDFGeometryError
    output = tmp_path / "unqualified"
    model = CircleSDF2D(center=(.5, .5), radius=.058)
    monkeypatch.setattr(startup.driver, "_build_initial_model", lambda *a, **kw: (model, object()))
    monkeypatch.setattr(startup.driver, "_write_initial_neural_checkpoint",
                        lambda path, saved_model, *args: torch.save(saved_model.state_dict(), path))
    monkeypatch.setattr(startup, "_initial_contour_characterization",
                        lambda *a: {"initial_shape_mismatch_exceeds_conversion_budget": True})
    settings = []
    def reject_geometry(model, config):
        settings.append(config)
        error = OrderedSDFGeometryError("conversion distance exceeds fixed limit")
        error.rejection_reasons = ("conversion_distance",)
        error.conversion_error_m = .00051
        error.conversion_refinement_change_m = .0000047
        raise error
    monkeypatch.setattr(startup, "build_ordered_sdf_geometry", reject_geometry)
    monkeypatch.setattr(startup, "run_implicit_mlp_adjoint_inverse",
                        lambda *a, **kw: pytest.fail("An unqualified field must never start the inverse"))
    assert startup.main(["--output-dir", str(output), "--pretrain-steps", "1", "--smoke-updates", "1"]) == 2
    report = json.loads((output / "qualification.json").read_text())
    assert settings[-1].projected_samples == 512
    assert settings[-1].arclength_dense_resolution == 2048
    assert report["resolutions"][-1]["conversion_error_m"] == .00051
    assert report["resolutions"][-1]["conversion_refinement_change_m"] == .0000047
    assert report["smoke_status"] == "not_run_unqualified_or_wall_cap"
    assert "cannot repair" in report["mechanism"]
