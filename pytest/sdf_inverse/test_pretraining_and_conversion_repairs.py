"""Protect compatible warm-start penalties and raw/converted geometry fidelity."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from sdf_inverse.models import CircleSDF2D, StarLevelSet2D
from sdf_inverse.geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError, build_ordered_sdf_geometry


@pytest.mark.parametrize("kind,expected",[("siren_circle",.1),("siren_ellipse",.1),("siren_star",0.)])
def test_initialization_penalty_matches_supervisor_and_can_be_overridden(monkeypatch,kind,expected):
    import run_sdf_inverse_comparison as driver
    calls=[]
    monkeypatch.setattr(driver,"pretrain_implicit_field",lambda *a,**kw:calls.append(kw))
    driver._build_initial_model(kind,hidden_features=8,pretrain_steps=1)
    assert calls[-1]["eikonal_weight"] == expected
    driver._build_initial_model(kind,hidden_features=8,pretrain_steps=1,pretrain_eikonal_weight=.03)
    assert calls[-1]["eikonal_weight"] == .03


def test_pretraining_and_inverse_penalties_are_independent_cli_controls():
    import run_sdf_inverse_comparison as driver
    args=driver._parse_args(["--mlp-pretrain-eikonal-weight","0","--eikonal-weight",".04"],implicit_defaults=True)
    assert args.mlp_pretrain_eikonal_weight == 0.
    assert driver._optimizer_config_for_solver(args,object(),"kress").eikonal_weight == .04
    with pytest.raises(SystemExit):
        driver._parse_args(["--mlp-pretrain-eikonal-weight","-1"],implicit_defaults=True)


def test_conversion_guard_preserves_a_resolved_curve_and_rejects_lost_lobes():
    config = OrderedSDFGeometryConfig(bounds=((.3,.3),(.7,.7)),grid_shape=(129,129),
        projected_samples=128,bandwidth=3,num_nodes=64,arclength_dense_resolution=512,
        validation_resolution=256)
    circle = CircleSDF2D(center=(.5,.5),radius=.05)
    original = build_ordered_sdf_geometry(circle,config)
    guarded = build_ordered_sdf_geometry(circle,replace(config,conversion_tolerance_m=.0002))
    np.testing.assert_array_equal(original.curve.points,guarded.curve.points)
    assert guarded.maximum_conversion_error_m < 1e-5
    star = StarLevelSet2D(center=(.5,.5),mean_radius=.05,amplitude=.12,lobes=7)
    build_ordered_sdf_geometry(star,config)
    with pytest.raises(OrderedSDFGeometryError,match="conversion fidelity"):
        build_ordered_sdf_geometry(star,replace(config,conversion_tolerance_m=.0002))


@pytest.mark.parametrize("tolerance",[0.,-1.,float('inf'),float('nan')])
def test_invalid_conversion_budget_is_rejected(tolerance):
    with pytest.raises(ValueError):
        OrderedSDFGeometryConfig(bounds=((0.,0.),(1.,1.)),conversion_tolerance_m=tolerance)


@pytest.mark.parametrize("errors,reasons", [
    ((.00021, .00021), ("conversion_distance",)),
    ((.00010, .00012), ("conversion_refinement_change",)),
    ((.00018, .00022), ("conversion_distance", "conversion_refinement_change")),
])
def test_conversion_distance_and_refinement_failures_have_independent_metadata(monkeypatch, errors, reasons):
    import sdf_inverse.geometry as geometry
    import sdf_inverse.neural_optimization as neural
    distances = iter(errors)
    points = np.array([[0., 0.], [1., 0.], [0., 1.]])
    monkeypatch.setattr(geometry, "prepare_single_component", lambda *a, **kw: SimpleNamespace(projected_points=points))
    monkeypatch.setattr(neural, "maximum_curve_set_distance", lambda *a: next(distances))
    parameterization = SimpleNamespace(discretize=lambda n: SimpleNamespace(points=points))
    field = SimpleNamespace(dtype=torch.float64)
    config = OrderedSDFGeometryConfig(bounds=((.3, .3), (.7, .7)), conversion_tolerance_m=.0002)
    with pytest.raises(OrderedSDFGeometryError) as failure:
        geometry._check_conversion_fidelity(field, parameterization, config)
    assert failure.value.rejection_reasons == reasons
    assert failure.value.conversion_error_m == max(errors)
    assert failure.value.conversion_refinement_change_m == abs(errors[1] - errors[0])


def test_conversion_resolution_defaults_to_the_target_and_is_overridable():
    import run_sdf_inverse_comparison as driver
    default = driver._parse_args(["--target", "star"], implicit_defaults=True)
    target = driver._build_target("star")
    assert (default.bandwidth, default.projected_samples) == (target.bandwidth, target.projected_samples)
    assert default.grid_resolution == target.grid_shape[0]
    # The 2026-09-07 star rerun resolution; bandwidth 96 needs 194 nodes/samples.
    raised = driver._parse_args(
        ["--target", "star", "--bandwidth", "96", "--num-nodes", "194",
         "--projected-samples", "256", "--grid-resolution", "513"], implicit_defaults=True,
    )
    assert (raised.bandwidth, raised.grid_resolution, raised.projected_samples) == (96, 513, 256)


@pytest.mark.parametrize("argv", [
    ["--bandwidth", "0"],                      # not a usable Fourier order
    ["--target", "star", "--bandwidth", "96"],  # 128 default nodes cannot sample it
    ["--grid-resolution", "512"],              # extraction grids are odd
    ["--bandwidth", "20", "--projected-samples", "10"],  # aliases the fitted curve
])
def test_unsamplable_conversion_resolution_is_rejected(argv):
    import run_sdf_inverse_comparison as driver
    with pytest.raises(SystemExit):
        driver._parse_args(argv, implicit_defaults=True)
