"""Protect explicit derivative routing and accepted neural artifact provenance."""

from __future__ import annotations

import csv
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_sdf_inverse_comparison as driver
import run_implicit_mlp_inverse as implicit_driver
import run_explicit_radial_fourier_inverse as explicit_driver


@pytest.mark.parametrize("initial_model", driver.SIREN_INITIAL_MODELS)
def test_neural_kress_auto_uses_adjoint_and_mod_retains_fd(initial_model):
    assert driver._optimizer_for_solver(initial_model, "kress") == "adjoint"
    assert driver._optimizer_for_solver(initial_model, "mod") == "parameter_fd"
    assert driver._optimizer_for_solver(initial_model, "kress", "parameter_fd") == "parameter_fd"
    args = driver._parse_args([
        "--target", "star" if initial_model == "siren_star" else "circle",
        "--initial-model", initial_model,
    ])
    assert args.output_dir.parent.parent == Path("results/inverse/implicit_mlp")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.output_dir.parent.name)


@pytest.mark.parametrize("initial_model", ["circle", "ellipse", "star", "random_features"])
def test_analytic_and_small_parameter_controls_keep_fd(initial_model):
    for solver in driver.DEFAULT_SOLVERS:
        assert driver._optimizer_for_solver(initial_model, solver) == "parameter_fd"
    for implicit_defaults in (False, True):
        args = driver._parse_args([
            "--target", "star" if initial_model == "star" else "circle",
            "--initial-model", initial_model, "--optimizer", "parameter_fd",
        ], implicit_defaults=implicit_defaults)
        assert args.output_dir.parent == Path("results/legacy/known_shape_family_parameter_inverse")


@pytest.mark.parametrize("arguments", [
    ["--optimizer", "adjoint", "--initial-model", "siren_circle"],
    ["--optimizer", "adjoint", "--solvers", "kress"],
    ["--optimizer", "adjoint", "--initial-model", "siren_circle", "--solvers", "mod"],
])
def test_unsupported_explicit_adjoint_fails_before_work(arguments, capsys):
    with pytest.raises(SystemExit, match="2"):
        driver._parse_args(arguments)
    assert "requires a siren_* initial model and --solvers kress" in capsys.readouterr().err


@pytest.mark.parametrize("target", ["circle", "star"])
def test_preferred_implicit_defaults_are_neural_kress_adjoint(target):
    args = driver._parse_args(["--target", target], implicit_defaults=True)
    assert args.initial_model == f"siren_{target}"
    assert args.solvers == ("kress",)
    assert args.optimizer == "adjoint"
    assert args.max_iterations == 60
    assert driver._parse_args(["--target", target]).max_iterations == driver._build_target(target).default_max_iterations
    assert (args.mlp_hidden_features, args.mlp_hidden_layers) == (64, 2)
    assert args.output_dir.parent.parent == Path("results/inverse/implicit_mlp")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.output_dir.parent.name)
    reference = driver._parse_args([
        "--target", target, "--optimizer", "parameter_fd",
        "--mlp-hidden-features", "16", "--mlp-hidden-layers", "0",
        "--max-iterations", "3",
        "--output-dir", "custom-output",
    ], implicit_defaults=True)
    assert driver._optimizer_for_solver(reference.initial_model, "kress", reference.optimizer) == "parameter_fd"
    assert (reference.mlp_hidden_features, reference.mlp_hidden_layers) == (16, 0)
    assert reference.max_iterations == 3
    assert reference.output_dir == Path("custom-output")


def test_wrapper_names_select_their_own_ownership_contract(monkeypatch):
    calls = []
    monkeypatch.setattr(implicit_driver, "_comparison_main", lambda *a, **kw: calls.append((a, kw)) or 7)
    monkeypatch.setattr(explicit_driver, "_radial_main", lambda *a, **kw: calls.append((a, kw)) or 9)
    assert implicit_driver.main(["--target", "star"]) == 7
    assert calls.pop() == ((["--target", "star"],), {"implicit_defaults": True})
    assert explicit_driver.main(["--target", "star"]) == 9
    assert calls.pop() == ((["--target", "star"],), {})


def test_neural_cli_controls_reach_adjoint_configuration():
    args = driver._parse_args([
        "--initial-model", "siren_circle", "--solvers", "kress",
        "--learning-rate", "0.002", "--eikonal-weight", "0.03",
        "--max-backtracks", "4", "--max-iterations", "2",
    ])
    # The adjoint config must not enumerate the network's FD controls.
    config = driver._optimizer_config_for_solver(args, object(), "kress")
    assert isinstance(config, driver.ImplicitMLPAdjointConfig)
    assert config.learning_rate == 0.002
    assert config.eikonal_weight == 0.03
    assert config.max_backtracks == 4
    assert config.max_iterations == 2


def test_truth_control_and_diagnostic_depth_preserve_analytic_defaults():
    args = driver._parse_args(["--target", "star", "--start-at-truth"], implicit_defaults=True)
    assert args.start_at_truth
    config = driver._optimizer_config_for_solver(args, object(), "kress")
    assert config.max_backtracks == 14
    assert config.meaningful_boundary_step_m == pytest.approx(1e-4)
    assert driver._parse_args(["--target", "star"]).max_backtracks == 8
    with pytest.raises(SystemExit, match="2"):
        driver._parse_args(["--target", "star", "--start-at-truth"])
    with pytest.raises(SystemExit, match="2"):
        driver._parse_args(["--start-at-truth", "--optimizer", "parameter_fd"], implicit_defaults=True)
    with pytest.raises(SystemExit, match="2"):
        driver._parse_args(["--record-accepted-holdout"])


def test_completed_holdout_replay_isolates_failures_and_restores_final_weights(monkeypatch):
    from sdf_inverse.models import TorchParameterController
    model = torch.nn.Linear(1, 1, bias=False, dtype=torch.float64)
    controller = TorchParameterController(model, lower_bounds=-10, upper_bounds=10)
    controller.assign(np.array([2.]))
    result = SimpleNamespace(
        iterations=tuple(SimpleNamespace(iteration=i, parameter_vector=np.array([float(i)])) for i in range(3)),
        stop_reason="maximum_iterations", total_seconds=7.0)
    seen = []

    def forward(*args, **kwargs):
        value = float(controller.parameter_vector()[0]); seen.append(value)
        if value == 1.:
            raise RuntimeError("Deliberate evaluation-only holdout failure")
        return SimpleNamespace(scattered_response=np.array([[1. + value]], dtype=complex), total_seconds=.25)

    monkeypatch.setattr(driver, "predict_paired_response", forward)
    replay = driver._replay_accepted_holdout(model, controller, result, object(), np.ones((1, 1), dtype=complex), object(), solver="kress")
    assert seen == [0., 1., 2.]
    assert replay["forward_evaluations"] == 3 and replay["failure_count"] == 1
    assert replay["records"][1]["holdout_relative_l2"] is None
    assert "Deliberate evaluation-only" in replay["records"][1]["holdout_evaluation_error"]
    assert replay["records"][2]["holdout_relative_l2"] == pytest.approx(2.)
    np.testing.assert_array_equal(controller.parameter_vector(), [2.])
    assert result.stop_reason == "maximum_iterations" and result.total_seconds == 7.


@pytest.mark.parametrize("extra,adjoint_depth,fd_depth", [([], 14, 8), (["--max-backtracks", "4"], 4, 4)])
def test_mixed_neural_comparison_retains_per_optimizer_backtrack_defaults(extra, adjoint_depth, fd_depth):
    args = driver._parse_args(["--initial-model", "siren_circle", "--solvers", "mod", "kress", *extra])
    _, controller = driver._build_initial_model("circle")
    assert driver._optimizer_config_for_solver(args, controller, "kress").max_backtracks == adjoint_depth
    assert driver._optimizer_config_for_solver(args, controller, "mod").max_backtracks == fd_depth


def test_adjoint_dispatch_cannot_silently_fall_back_to_parameter_fd(monkeypatch):
    calls = []
    sentinel = object()
    monkeypatch.setattr(driver, "run_implicit_mlp_adjoint_inverse", lambda *a, **kw: calls.append((a, kw)) or sentinel)
    monkeypatch.setattr(driver, "run_parameter_fd_inverse", lambda *a, **kw: pytest.fail("FD fallback"))
    inputs = tuple(object() for _ in range(4))
    config = driver.ImplicitMLPAdjointConfig(max_iterations=1)
    assert driver._run_inverse(*inputs, solver="kress", method="adjoint", config=config) is sentinel
    assert calls == [(inputs, {"config": config, "progress_callback": None})]
    with pytest.raises(ValueError, match="requires Kress"):
        driver._run_inverse(*inputs, solver="mod", method="adjoint", config=config)


def test_reference_dispatch_preserves_solver_and_configuration(monkeypatch):
    calls = []
    sentinel = object()
    monkeypatch.setattr(driver, "run_parameter_fd_inverse", lambda *a, **kw: calls.append((a, kw)) or sentinel)
    monkeypatch.setattr(driver, "run_implicit_mlp_adjoint_inverse", lambda *a, **kw: pytest.fail("unexpected adjoint"))
    inputs = tuple(object() for _ in range(4))
    config = driver.ParameterFDConfig(max_iterations=1)
    assert driver._run_inverse(*inputs, solver="mod", method="parameter_fd", config=config) is sentinel
    assert calls == [(inputs, {"solver": "mod", "config": config, "progress_callback": None})]


def test_network_capacity_is_forwarded_without_changing_global_defaults(monkeypatch):
    training_calls = []
    monkeypatch.setattr(driver, "pretrain_implicit_field", lambda *a, **kw: training_calls.append(kw) or None)
    model, controller = driver._build_initial_model(
        "siren_circle", hidden_features=7, hidden_layers=1, pretrain_steps=11,
    )
    assert model.hidden_features == 7 and model.hidden_layers == 1
    assert controller.num_parameters == model.num_network_parameters
    assert training_calls[0]["steps"] == 11
    assert (driver.DEFAULT_SIREN_HIDDEN_FEATURES, driver.DEFAULT_SIREN_HIDDEN_LAYERS) == (32, 0)


def test_neural_checkpoint_reloads_the_accepted_field_and_metadata(tmp_path):
    model = driver.SirenImplicitField2D(
        bounds=driver.DEFAULT_GEOMETRY_BOUNDS, hidden_features=5, hidden_layers=1,
        dtype=torch.float64,
    )
    geometry = np.array([[0.45, 0.5], [0.5, 0.45], [0.55, 0.5], [0.5, 0.55]])
    result = SimpleNamespace(
        iterations=[SimpleNamespace(iteration=3, loss=0.012, geometry_points=geometry)],
        diagnostics={"finite_difference_probes": 0},
    )
    output = tmp_path / "kress_model.pt"
    driver._write_neural_checkpoint(
        output, model, initial_model="siren_circle",
        geometry_config=driver._build_target("circle").geometry_config(32),
        optimizer="adjoint", config=driver.ImplicitMLPAdjointConfig(), result=result,
    )
    saved = torch.load(output, weights_only=True)
    constructor = dict(saved["constructor"])
    constructor["dtype"] = getattr(torch, constructor["dtype"].removeprefix("torch."))
    restored = driver.SirenImplicitField2D(**constructor)
    restored.load_state_dict(saved["state_dict"])
    points = torch.tensor(geometry, dtype=torch.float64)
    torch.testing.assert_close(restored(points), model(points), rtol=0, atol=0)
    assert saved["geometry_owner"] == "mlp_weights"
    assert saved["optimizer"] == "adjoint"
    assert saved["accepted_iteration"] == 3
    torch.testing.assert_close(saved["accepted_geometry_points"], points)


def test_terminal_unevaluated_gradient_stays_blank_in_trajectory(tmp_path):
    iteration = SimpleNamespace(
        iteration=0, physical_parameters={"center_x": .5, "center_y": .5, "radius": .05},
        loss=.1, relative_l2_error=.2, damping=0., evaluation_count=1,
        maximum_system_residual=1e-12, timings={}, parameter_vector=np.array([.3]),
        gradient=None, gradient_evaluated=False, step=np.array([0.]),
    )
    result = SimpleNamespace(parameter_names=("network.weight",), iterations=(iteration,))
    output = tmp_path / "trajectory.csv"
    driver._write_trajectory(output, result, optimizer="adjoint")
    with output.open() as stream:
        row = next(csv.DictReader(stream))
    assert row["optimizer"] == "adjoint"
    assert row["gradient_evaluated"] == "False"
    assert row["gradient_network.weight"] == ""
    assert row["gradient_seconds"] == ""


def test_summary_declares_mixed_optimizers_without_dumping_neural_weights(tmp_path):
    row = dict.fromkeys([
        "initial_training_relative_l2", "final_training_relative_l2",
        "training_loss_drop_factor", "final_holdout_relative_l2",
        "target_geometry_holdout_relative_l2", "final_center_error_m",
        "final_radius_error_m", "maximum_node_to_exact_boundary_distance_m",
        "inverse_wall_seconds", "accepted_updates", "total_forward_evaluations",
    ], 1.0)
    row["stop_reason"] = "max_iterations"
    rows = {
        "mod": {**row, "optimizer": "parameter_fd"},
        "kress": {**row, "optimizer": "adjoint", "model_checkpoint": "kress_model.pt"},
    }
    metrics = {
        "initialization": {
            "kind": "siren_neural_implicit", "network_parameters": 8577,
            "hidden_features": 64, "hidden_layers": 2,
            "physical_parameters": {"network.weight[0]": 0.12345},
        },
        "train_frequencies_ghz": [.25], "holdout_frequencies_ghz": [.5],
        "truth_oracle": "independent Mie", "acceptance_gates": {},
        "acceptance_passed": False, "provenance": {"command": "run_implicit_mlp_inverse.py"},
    }
    output = tmp_path / "summary.md"
    driver._write_summary(output, metrics=metrics, solver_metrics=rows, target=driver._build_target("circle"))
    summary = output.read_text()
    assert "8577 trainable weights" in summary
    assert "network.weight[0]" not in summary
    assert "different optimizer policies" in summary
    assert "Kress discrete adjoint" in summary and "parameter finite differences" in summary
    assert "branch-local extraction/Method-B reverse" in summary
    assert "not autograd operations" not in summary
    assert "[kress_model.pt](kress_model.pt)" in summary
