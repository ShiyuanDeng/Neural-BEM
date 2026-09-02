#!/usr/bin/env python3
"""Recover an analytic target from wrong implicit initializations with MOD/Kress.

The observation data always come from an independent source -- the analytic
penetrable-cylinder Mie series for the circle target, and the from-scratch
``nystrom_ref`` oracle for the five-lobe star target -- never from either
solver under test.  Both inverse branches use the same Torch implicit field,
ordered Method-B geometry, frequency-domain objective, bounded
finite-difference Jacobian, and damped Gauss--Newton policy.  Only the forward
solver changes.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from typing import Any, Mapping, Sequence


# Establish deterministic, comparable CPU timing before NumPy/SciPy import.
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_variable, "1")

import numpy as np
import torch


REPOSITORY_ROOT = Path(__file__).resolve().parent
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"
for _import_root in (REPOSITORY_ROOT, SOLVERS_ROOT):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

import config.circle_config as physical_config  # noqa: E402
import config.star_config as star_config  # noqa: E402
import gpr_bem_ref  # noqa: E402
from sdf_inverse import (  # noqa: E402
    CircleSDF2D,
    ComplexScatteredData,
    EllipseLevelSet2D,
    MaterialSpec,
    OrderedSDFGeometryConfig,
    PairedForwardProblem,
    ParameterFDConfig,
    RadialRandomFeatureImplicit2D,
    StarLevelSet2D,
    StarShape,
    build_circle_parameter_controller,
    build_ellipse_parameter_controller,
    build_radial_random_feature_parameter_controller,
    build_star_parameter_controller,
    normalized_complex_residual,
    nystrom_paired_response,
    nystrom_self_convergence,
    predict_paired_response,
    run_parameter_fd_inverse,
)
from sdf_inverse.geometry import Bounds2D  # noqa: E402


DEFAULT_INITIAL_CENTER = (0.48, 0.52)
DEFAULT_INITIAL_RADIUS = 0.065
DEFAULT_TRAIN_FREQUENCIES_GHZ = (0.25, 0.50)
DEFAULT_HOLDOUT_FREQUENCIES_GHZ = (1.0, 1.5, 2.5)
DEFAULT_SOLVERS = ("mod", "kress")
DEFAULT_TARGET = "circle"
TARGET_CHOICES = ("circle", "star")
INITIAL_MODEL_CHOICES = ("circle", "ellipse", "random_features", "star")
DEFAULT_CENTER_BOUNDS = ((0.40, 0.60), (0.40, 0.60))
DEFAULT_RADIUS_BOUNDS = (0.025, 0.090)
DEFAULT_GEOMETRY_BOUNDS = ((0.30, 0.30), (0.70, 0.70))

# Star case.  The initialization is wrong in all five controls: the center is
# 28.3 mm away, the mean radius is 20% too large, the lobe depth is less than
# half, and the lobe phase is rotated by a fifth of the symmetry period.
DEFAULT_STAR_INITIAL_CENTER = (0.48, 0.52)
DEFAULT_STAR_INITIAL_MEAN_RADIUS = 0.060
DEFAULT_STAR_INITIAL_AMPLITUDE = 0.12
DEFAULT_STAR_INITIAL_ROTATION = 0.25
# Tighter than the circle center bounds because a star of the largest allowed
# mean radius and lobe depth reaches 0.109 m from its center.
DEFAULT_STAR_CENTER_BOUNDS = ((0.44, 0.56), (0.44, 0.56))
DEFAULT_STAR_MEAN_RADIUS_BOUNDS = (0.030, 0.075)
# The lower amplitude bound is positive so the lobe phase stays identifiable,
# and the upper bound keeps the concave notches extractable on the grid.
DEFAULT_STAR_AMPLITUDE_BOUNDS = (0.05, 0.35)
# Narrower than the 2 pi / 5 symmetry period, so one shape has one parameter.
DEFAULT_STAR_ROTATION_BOUNDS = (-0.60, 0.60)
DEFAULT_STAR_TRAIN_FREQUENCIES_GHZ = (0.50, 1.50)
DEFAULT_STAR_HOLDOUT_FREQUENCIES_GHZ = (0.25, 1.0, 2.5)
DEFAULT_STAR_ORACLE_NODES = 512
GENERATED_ARTIFACT_NAMES = (
    "metrics.json",
    "summary.md",
    "convergence.png",
    "mod_trajectory.csv",
    "mod_responses.npz",
    "kress_trajectory.csv",
    "kress_responses.npz",
)


class InverseTarget:
    """One analytic target: its observations, its exact field, its geometry error.

    A target owns everything about the experiment that changes when the shape
    changes, so the objective, the optimizer, the artifacts, and the solver
    dispatch stay literally the same code for every case.  Subclasses must not
    hold optimizer state; they are constructed once and queried.
    """

    name: str
    truth_oracle: str
    initial_model_choices: tuple[str, ...]
    default_initial_model: str
    default_train_ghz: tuple[float, ...]
    default_holdout_ghz: tuple[float, ...]
    default_num_nodes: int
    default_max_iterations: int
    geometry_bounds: Bounds2D
    grid_shape: tuple[int, int]
    projected_samples: int
    bandwidth: int
    arclength_dense_resolution: int
    validation_resolution: int
    center: tuple[float, float]
    reference_radius: float
    kress_holdout_accuracy_threshold: float
    kress_holdout_accuracy_requirement: str
    output_tag: str

    def benchmark(self, initial_model: str) -> str:
        raise NotImplementedError

    def summary_sentence(self) -> str:
        raise NotImplementedError

    def parameter_dict(self) -> dict[str, float]:
        raise NotImplementedError

    def observations(self, problem: PairedForwardProblem) -> np.ndarray:
        raise NotImplementedError

    def oracle_diagnostics(self, problem: PairedForwardProblem) -> dict[str, Any] | None:
        """Return oracle quality evidence, or ``None`` for an analytic series."""

        return None

    def exact_model(self) -> torch.nn.Module:
        raise NotImplementedError

    def boundary_distances(self, points: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def exact_boundary_polyline(self, num_samples: int = 1024) -> np.ndarray:
        raise NotImplementedError

    def shape_errors(self, physical_parameters: Mapping[str, float]) -> dict[str, float]:
        raise NotImplementedError

    def shape_error_gates(self) -> tuple[tuple[str, float, str], ...]:
        """Return ``(metric_key, threshold, requirement)`` gate specifications."""

        raise NotImplementedError

    def geometry_config(self, num_nodes: int) -> OrderedSDFGeometryConfig:
        return OrderedSDFGeometryConfig(
            bounds=self.geometry_bounds,
            grid_shape=self.grid_shape,
            projected_samples=self.projected_samples,
            bandwidth=self.bandwidth,
            num_nodes=num_nodes,
            arclength_dense_resolution=self.arclength_dense_resolution,
            validation_resolution=self.validation_resolution,
        )

    def curve_distance_metrics(self, points: np.ndarray) -> dict[str, float]:
        distances = self.boundary_distances(np.asarray(points, dtype=np.float64))
        return {
            "mean_node_to_exact_boundary_distance_m": float(np.mean(distances)),
            "maximum_node_to_exact_boundary_distance_m": float(np.max(distances)),
        }


class CircleTarget(InverseTarget):
    """The analytic penetrable cylinder, observed through an exact Mie series."""

    name = "circle"
    truth_oracle = "gpr_bem_ref analytic penetrable-cylinder Mie series"
    initial_model_choices = ("circle", "ellipse", "random_features")
    default_initial_model = "circle"
    default_train_ghz = DEFAULT_TRAIN_FREQUENCIES_GHZ
    default_holdout_ghz = DEFAULT_HOLDOUT_FREQUENCIES_GHZ
    default_num_nodes = 64
    default_max_iterations = 6
    # Each model factory chooses bounds that retain one closed contour in this
    # box throughout finite-difference and line-search trials.
    geometry_bounds = DEFAULT_GEOMETRY_BOUNDS
    grid_shape = (129, 129)
    projected_samples = 64
    bandwidth = 10
    arclength_dense_resolution = 512
    validation_resolution = 256
    kress_holdout_accuracy_threshold = 1.0e-6
    kress_holdout_accuracy_requirement = "<= 1e-6"
    output_tag = "circle-mie"

    def __init__(self) -> None:
        self.center = (
            float(physical_config.TARGET_CENTER_X),
            float(physical_config.TARGET_CENTER_Y),
        )
        self.reference_radius = float(physical_config.TARGET_RADIUS)

    def benchmark(self, initial_model: str) -> str:
        return f"{initial_model}-implicit-to-circle-from-independent-mie-data"

    def summary_sentence(self) -> str:
        return (
            "was fit to independent analytic Mie scattered-field data for the "
            f"true `({self.center[0]:.2f}, {self.center[1]:.2f}) m`, radius "
            f"`{self.reference_radius:.3f} m` cylinder."
        )

    def parameter_dict(self) -> dict[str, float]:
        return {
            "center_x_m": self.center[0],
            "center_y_m": self.center[1],
            "radius_m": self.reference_radius,
        }

    def observations(self, problem: PairedForwardProblem) -> np.ndarray:
        exterior = gpr_bem_ref.Material(
            epsr=problem.exterior.epsr,
            sigma=problem.exterior.sigma,
            mur=problem.exterior.mur,
        )
        interior = gpr_bem_ref.Material(
            epsr=problem.interior.epsr,
            sigma=problem.interior.sigma,
            mur=problem.interior.mur,
        )
        return gpr_bem_ref.penetrable_cylinder_frequency_response(
            problem.receiver_points,
            problem.source_points,
            problem.angular_frequencies,
            problem.source_strengths,
            exterior=exterior,
            interior=interior,
            eps0=problem.eps0,
            mu0=problem.mu0,
            radius=self.reference_radius,
            center=self.center,
            include_incident=False,
        )

    def exact_model(self) -> torch.nn.Module:
        return CircleSDF2D(
            center=self.center,
            radius=self.reference_radius,
            dtype=torch.float64,
            device="cpu",
        )

    def boundary_distances(self, points: np.ndarray) -> np.ndarray:
        # Distance from any point to the analytic circle is exact.  A symmetric
        # point-cloud Hausdorff distance would instead report the finite node
        # spacing as geometry error, even when every node lies on the true curve.
        return np.abs(
            np.linalg.norm(points - np.asarray(self.center)[None, :], axis=1)
            - self.reference_radius
        )

    def exact_boundary_polyline(self, num_samples: int = 1024) -> np.ndarray:
        angles = np.linspace(0.0, 2.0 * np.pi, num_samples, endpoint=False)
        return np.column_stack(
            (
                self.center[0] + self.reference_radius * np.cos(angles),
                self.center[1] + self.reference_radius * np.sin(angles),
            )
        )

    def shape_errors(self, physical_parameters: Mapping[str, float]) -> dict[str, float]:
        return {
            "final_center_error_m": math.hypot(
                physical_parameters["center_x"] - self.center[0],
                physical_parameters["center_y"] - self.center[1],
            ),
            "final_radius_error_m": abs(
                physical_parameters["radius"] - self.reference_radius
            ),
        }

    def shape_error_gates(self) -> tuple[tuple[str, float, str], ...]:
        return (
            ("final_center_error_m", 5.0e-4, "<= 5e-4 m"),
            ("final_radius_error_m", 1.0e-3, "<= 1e-3 m"),
        )


class StarTarget(InverseTarget):
    """The smooth five-lobe star, observed through the independent Nystrom oracle.

    This is the same curve, at the same placement and materials, that the
    checked forward comparison study already treats as truth, so the inverse
    and the forward evidence describe one shape.  Observations are generated
    by ``nystrom_ref``: an implementation that shares only the problem
    definition with MOD and Kress, so neither solver is inverting its own
    discretisation error.
    """

    name = "star"
    truth_oracle = "nystrom_ref independent Nystrom/Muller solution of the exact star"
    initial_model_choices = ("star",)
    default_initial_model = "star"
    # The lobe amplitude and phase are nearly invisible below about 1 GHz for a
    # 0.05 m star in sand, so the training band is chosen where they are
    # observable rather than copied from the circle case.
    default_train_ghz = DEFAULT_STAR_TRAIN_FREQUENCIES_GHZ
    default_holdout_ghz = DEFAULT_STAR_HOLDOUT_FREQUENCIES_GHZ
    # An arc-length Fourier curve needs a high bandwidth for a five-lobe star:
    # the truncation floor is 9.7e-4 m at bandwidth 10 but 2.9e-5 m at 48.
    default_num_nodes = 128
    default_max_iterations = 14
    geometry_bounds = DEFAULT_GEOMETRY_BOUNDS
    grid_shape = (257, 257)
    projected_samples = 128
    bandwidth = 48
    arclength_dense_resolution = 2048
    validation_resolution = 1024
    # Kress is limited here by the shared Method-B representation, not by its
    # own quadrature, so this threshold is the geometry floor and not 1e-6.
    kress_holdout_accuracy_threshold = 1.0e-3
    kress_holdout_accuracy_requirement = "<= 1e-3"
    output_tag = "star-nystrom"

    def __init__(self, *, oracle_nodes: int = DEFAULT_STAR_ORACLE_NODES) -> None:
        self.shape = StarShape(
            center=(
                float(star_config.TARGET_CENTER_X),
                float(star_config.TARGET_CENTER_Y),
            ),
            mean_radius=float(star_config.TARGET_MEAN_RADIUS),
            amplitude=float(star_config.TARGET_STAR_AMPLITUDE),
            lobes=int(star_config.TARGET_STAR_LOBES),
            rotation_radians=0.0,
        )
        self.center = self.shape.center
        self.reference_radius = self.shape.mean_radius
        self.oracle_nodes = int(oracle_nodes)

    def benchmark(self, initial_model: str) -> str:
        return f"{initial_model}-implicit-to-star-from-independent-nystrom-data"

    def summary_sentence(self) -> str:
        return (
            "was fit to independent Nystrom scattered-field data for the true "
            f"`({self.center[0]:.2f}, {self.center[1]:.2f}) m` star "
            f"`r(t) = {self.shape.mean_radius:g} (1 + {self.shape.amplitude:g} "
            f"cos({self.shape.lobes}t))`."
        )

    def parameter_dict(self) -> dict[str, float]:
        return self.shape.parameter_dict()

    def observations(self, problem: PairedForwardProblem) -> np.ndarray:
        return nystrom_paired_response(
            problem,
            self.shape.parameterization(),
            num_nodes=self.oracle_nodes,
            curve_name="target-star",
        ).scattered_response

    def oracle_diagnostics(self, problem: PairedForwardProblem) -> dict[str, Any]:
        return nystrom_self_convergence(
            problem,
            self.shape.parameterization(),
            num_nodes=self.oracle_nodes,
            curve_name="target-star",
        )

    def exact_model(self) -> torch.nn.Module:
        return self.shape.implicit_model(dtype=torch.float64, device="cpu")

    def boundary_distances(self, points: np.ndarray) -> np.ndarray:
        return self.shape.distance_to_boundary(points)

    def exact_boundary_polyline(self, num_samples: int = 1024) -> np.ndarray:
        return self.shape.sample_boundary(num_samples)

    def shape_errors(self, physical_parameters: Mapping[str, float]) -> dict[str, float]:
        return {
            "final_center_error_m": math.hypot(
                physical_parameters["center_x"] - self.center[0],
                physical_parameters["center_y"] - self.center[1],
            ),
            "final_radius_error_m": abs(
                physical_parameters["radius"] - self.shape.mean_radius
            ),
            "final_amplitude_error": abs(
                physical_parameters["amplitude"] - self.shape.amplitude
            ),
            "final_rotation_error_radians": abs(
                physical_parameters["rotation_radians"] - self.shape.rotation_radians
            ),
        }

    def shape_error_gates(self) -> tuple[tuple[str, float, str], ...]:
        return (
            ("final_center_error_m", 5.0e-4, "<= 5e-4 m"),
            ("final_radius_error_m", 1.0e-3, "<= 1e-3 m"),
            # Eight percent of the true lobe depth, and one sixtieth of the
            # star's 2 pi / 5 rotational symmetry period.
            ("final_amplitude_error", 2.0e-2, "<= 2e-2"),
            ("final_rotation_error_radians", 2.0e-2, "<= 2e-2 rad"),
        )


def _build_target(name: str) -> InverseTarget:
    if name == "circle":
        return CircleTarget()
    if name == "star":
        return StarTarget()
    raise ValueError(f"Unsupported target: {name!r}.")


def _comma_separated_floats(value: str) -> tuple[float, ...]:
    try:
        result = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from exc
    if not result or not all(math.isfinite(item) and item > 0.0 for item in result):
        raise argparse.ArgumentTypeError("frequencies must be finite and positive")
    return result


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    run_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(
        description=(
            "Recover an analytic target from a deliberately wrong implicit "
            "initialization using independent observations and the same "
            "inverse with MOD and/or Kress."
        )
    )
    parser.add_argument(
        "--target",
        choices=TARGET_CHOICES,
        default=DEFAULT_TARGET,
        help=(
            "Analytic target and observation oracle: the Mie circle, or the "
            "five-lobe Nystrom star."
        ),
    )
    parser.add_argument(
        "--solvers",
        nargs="+",
        choices=DEFAULT_SOLVERS,
        default=list(DEFAULT_SOLVERS),
        help="Forward branches to run (default: mod kress).",
    )
    parser.add_argument(
        "--initial-model",
        choices=INITIAL_MODEL_CHOICES,
        default=None,
        help=(
            "Implicit initialization: exact circle SDF, non-distance ellipse, "
            "topology-constrained random-feature neural field, or wrong star. "
            "Defaults to the target's own family."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    # The remaining resolution and frequency defaults depend on the target, so
    # they are resolved after parsing rather than fixed to the circle case.
    parser.add_argument(
        "--train-ghz",
        type=_comma_separated_floats,
        default=None,
        help="Comma-separated inversion frequencies in GHz.",
    )
    parser.add_argument(
        "--holdout-ghz",
        type=_comma_separated_floats,
        default=None,
        help="Comma-separated evaluation-only frequencies in GHz.",
    )
    parser.add_argument("--num-pairs", type=int, default=12)
    parser.add_argument("--num-nodes", type=int, default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--loss-tolerance", type=float, default=1.0e-12)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace this driver's known artifacts in a nonempty output directory.",
    )
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help="Write diagnostics without returning an error for failed acceptance gates.",
    )
    args = parser.parse_args(argv)
    target = _build_target(args.target)
    if args.initial_model is None:
        args.initial_model = target.default_initial_model
    if args.initial_model not in target.initial_model_choices:
        parser.error(
            f"--initial-model={args.initial_model} is not available for "
            f"--target={args.target}; choose from "
            + ", ".join(target.initial_model_choices)
        )
    if args.train_ghz is None:
        args.train_ghz = target.default_train_ghz
    if args.holdout_ghz is None:
        args.holdout_ghz = target.default_holdout_ghz
    if args.num_nodes is None:
        args.num_nodes = target.default_num_nodes
    if args.max_iterations is None:
        args.max_iterations = target.default_max_iterations
    if args.num_pairs < 4:
        parser.error("--num-pairs must be at least 4")
    if args.num_nodes < 32 or args.num_nodes % 2:
        parser.error("--num-nodes must be an even integer of at least 32")
    if args.num_nodes < 2 * target.bandwidth + 2:
        parser.error(
            f"--num-nodes must be at least {2 * target.bandwidth + 2} to sample "
            f"the target's bandwidth-{target.bandwidth} Method-B curve"
        )
    if args.max_iterations < 1:
        parser.error("--max-iterations must be positive")
    if not math.isfinite(args.loss_tolerance) or args.loss_tolerance <= 0.0:
        parser.error("--loss-tolerance must be finite and positive")
    if set(args.train_ghz) & set(args.holdout_ghz):
        parser.error("training and holdout frequencies must be disjoint")
    # Preserve user order while preventing accidental duplicate work.
    args.solvers = tuple(dict.fromkeys(args.solvers))
    if args.output_dir is None:
        args.output_dir = (
            Path("results/inverse_solver_comparison")
            / f"{args.initial_model}-to-{target.output_tag}-{run_tag}"
        )
    return args


def _build_initial_model(
    kind: str,
) -> tuple[torch.nn.Module, Any]:
    """Build one deterministic initialization and its bounded controller."""

    if kind == "circle":
        model = CircleSDF2D(
            center=DEFAULT_INITIAL_CENTER,
            radius=DEFAULT_INITIAL_RADIUS,
            dtype=torch.float64,
            device="cpu",
        )
        controller = build_circle_parameter_controller(
            model,
            center_bounds=DEFAULT_CENTER_BOUNDS,
            radius_bounds=DEFAULT_RADIUS_BOUNDS,
        )
        return model, controller
    if kind == "ellipse":
        model = EllipseLevelSet2D(
            center=DEFAULT_INITIAL_CENTER,
            semi_axes=(0.072, 0.038),
            rotation_radians=0.4,
            dtype=torch.float64,
            device="cpu",
        )
        controller = build_ellipse_parameter_controller(
            model,
            center_bounds=DEFAULT_CENTER_BOUNDS,
            semi_axis_bounds=DEFAULT_RADIUS_BOUNDS,
        )
        return model, controller
    if kind == "random_features":
        model = RadialRandomFeatureImplicit2D(
            center=DEFAULT_INITIAL_CENTER,
            radius=0.060,
            hidden_features=4,
            random_seed=17,
            relative_amplitude=0.15,
            output_weights=(0.8, -0.6, 0.7, -0.5),
            dtype=torch.float64,
            device="cpu",
        )
        controller = build_radial_random_feature_parameter_controller(
            model,
            center_bounds=DEFAULT_CENTER_BOUNDS,
            radius_bounds=(0.025, 0.075),
            output_weight_bounds=(-1.0, 1.0),
        )
        return model, controller
    if kind == "star":
        model = StarLevelSet2D(
            center=DEFAULT_STAR_INITIAL_CENTER,
            mean_radius=DEFAULT_STAR_INITIAL_MEAN_RADIUS,
            amplitude=DEFAULT_STAR_INITIAL_AMPLITUDE,
            lobes=int(star_config.TARGET_STAR_LOBES),
            rotation_radians=DEFAULT_STAR_INITIAL_ROTATION,
            dtype=torch.float64,
            device="cpu",
        )
        controller = build_star_parameter_controller(
            model,
            center_bounds=DEFAULT_STAR_CENTER_BOUNDS,
            mean_radius_bounds=DEFAULT_STAR_MEAN_RADIUS_BOUNDS,
            amplitude_bounds=DEFAULT_STAR_AMPLITUDE_BOUNDS,
            rotation_bounds=DEFAULT_STAR_ROTATION_BOUNDS,
        )
        return model, controller
    raise ValueError(f"Unsupported initial model: {kind!r}.")


def _inverse_config_for_controller(
    controller: Any,
    *,
    max_iterations: int,
    loss_tolerance: float = 1.0e-12,
) -> ParameterFDConfig:
    finite_difference_steps = []
    maximum_steps = []
    for name in controller.names:
        if name in {"center_x", "center_y"}:
            finite_difference_steps.append(5.0e-5)
            maximum_steps.append(1.0e-2)
        elif name.startswith("log_"):
            finite_difference_steps.append(4.0e-4)
            maximum_steps.append(1.0e-1)
        else:
            finite_difference_steps.append(2.0e-3)
            maximum_steps.append(2.5e-1)
    return ParameterFDConfig(
        max_iterations=max_iterations,
        finite_difference_steps=np.asarray(finite_difference_steps),
        max_steps=np.asarray(maximum_steps),
        initial_damping=1.0e-3,
        damping_increase=10.0,
        damping_decrease=0.3,
        max_damping_trials=6,
        max_backtracks=8,
        gradient_tolerance=1.0e-9,
        loss_tolerance=loss_tolerance,
        relative_step_tolerance=1.0e-9,
        max_parameters=controller.num_parameters,
    )


def _prepare_output_directory(path: Path, *, overwrite: bool) -> None:
    """Create a fresh artifact directory or explicitly replace known outputs."""

    resolved = path.resolve()
    if resolved == REPOSITORY_ROOT or resolved == Path(resolved.anchor):
        raise ValueError("output directory must not be the repository or filesystem root")
    if resolved.exists() and not resolved.is_dir():
        raise NotADirectoryError(f"output path exists but is not a directory: {resolved}")
    if resolved.exists() and any(resolved.iterdir()) and not overwrite:
        raise FileExistsError(
            f"output directory is not empty: {resolved}. Choose a new path or pass "
            "--overwrite to replace this driver's known artifacts."
        )
    resolved.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for name in GENERATED_ARTIFACT_NAMES:
            artifact = resolved / name
            if artifact.is_file() or artifact.is_symlink():
                artifact.unlink()


def _ring_scan(
    *, center: tuple[float, float], standoff: float, num_pairs: int
) -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0.0, 2.0 * np.pi, num_pairs, endpoint=False)
    separation_angle = float(physical_config.TX_RX_OFFSET) / standoff
    source_points = np.column_stack(
        (
            center[0] + standoff * np.cos(angles),
            center[1] + standoff * np.sin(angles),
        )
    )
    receiver_points = np.column_stack(
        (
            center[0] + standoff * np.cos(angles + separation_angle),
            center[1] + standoff * np.sin(angles + separation_angle),
        )
    )
    return source_points, receiver_points


def _build_problem(
    frequencies_ghz: Sequence[float],
    source_points: np.ndarray,
    receiver_points: np.ndarray,
) -> PairedForwardProblem:
    frequencies_hz = 1.0e9 * np.asarray(frequencies_ghz, dtype=np.float64)
    return PairedForwardProblem(
        source_points=source_points,
        receiver_points=receiver_points,
        angular_frequencies=2.0 * np.pi * frequencies_hz,
        source_strengths=np.full(frequencies_hz.shape, 1.0e-6 + 0.0j),
        exterior=MaterialSpec(
            epsr=float(physical_config.SAND_EPSR),
            sigma=float(physical_config.SAND_SIGMA),
        ),
        interior=MaterialSpec(
            epsr=float(physical_config.PLASTIC_EPSR),
            sigma=float(physical_config.PLASTIC_SIGMA),
        ),
        eps0=float(physical_config.EPS0),
        mu0=float(physical_config.MU0),
    )


def _per_frequency_relative_error(
    prediction: np.ndarray, truth: np.ndarray
) -> np.ndarray:
    numerator = np.linalg.norm(prediction - truth, axis=0)
    denominator = np.maximum(
        np.linalg.norm(truth, axis=0), np.finfo(np.float64).tiny
    )
    return numerator / denominator


def _objective_metrics(
    prediction: np.ndarray, truth: np.ndarray
) -> tuple[float, float]:
    residual, relative_l2 = normalized_complex_residual(prediction, truth)
    return 0.5 * float(residual @ residual), relative_l2


def _radial_span(points: np.ndarray, center: tuple[float, float]) -> float:
    radii = np.linalg.norm(
        np.asarray(points, dtype=np.float64)
        - np.asarray(center, dtype=np.float64)[None, :],
        axis=1,
    )
    return float(np.ptp(radii))


def _field_gradient_metrics(
    model: torch.nn.Module,
    points: np.ndarray,
) -> dict[str, float]:
    reference = next(model.parameters())
    tensor = torch.as_tensor(
        np.array(points, dtype=np.float64, copy=True),
        dtype=reference.dtype,
        device=reference.device,
    ).detach().requires_grad_(True)
    with torch.enable_grad():
        values = model(tensor).reshape(-1)
        gradients = torch.autograd.grad(values.sum(), tensor)[0]
    norms = gradients.detach().cpu().to(dtype=torch.float64).norm(dim=1).numpy()
    return {
        "minimum_field_gradient_norm": float(np.min(norms)),
        "maximum_field_gradient_norm": float(np.max(norms)),
        "maximum_unit_gradient_deviation": float(np.max(np.abs(norms - 1.0))),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _git_provenance() -> dict[str, Any]:
    def run_git(*arguments: str) -> str:
        completed = subprocess.run(
            ("git",) + arguments,
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip() if completed.returncode == 0 else "unavailable"

    return {
        "commit": run_git("rev-parse", "HEAD"),
        "branch": run_git("branch", "--show-current"),
        "working_tree_status_before_run": run_git("status", "--short"),
    }


def _thread_provenance() -> dict[str, str]:
    return {
        name: os.environ.get(name, "unset")
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        )
    }


def _package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _write_trajectory(path: Path, result: Any) -> None:
    parameter_names = tuple(result.parameter_names)
    fieldnames = [
        "iteration",
        "loss",
        "relative_l2_error",
        "center_x_m",
        "center_y_m",
        "radius_m",
        "damping",
        "evaluation_count",
        "maximum_system_residual",
        "iteration_seconds",
        "jacobian_seconds",
        "line_search_seconds",
    ]
    fieldnames.extend(f"raw_{name}" for name in parameter_names)
    fieldnames.extend(f"gradient_{name}" for name in parameter_names)
    fieldnames.extend(f"step_{name}" for name in parameter_names)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for iteration in result.iterations:
            row = {
                "iteration": iteration.iteration,
                "loss": iteration.loss,
                "relative_l2_error": iteration.relative_l2_error,
                "center_x_m": iteration.physical_parameters["center_x"],
                "center_y_m": iteration.physical_parameters["center_y"],
                "radius_m": iteration.physical_parameters["radius"],
                "damping": iteration.damping,
                "evaluation_count": iteration.evaluation_count,
                "maximum_system_residual": iteration.maximum_system_residual,
                "iteration_seconds": iteration.timings["iteration_seconds"],
                "jacobian_seconds": iteration.timings["jacobian_seconds"],
                "line_search_seconds": iteration.timings["line_search_seconds"],
            }
            row.update(
                {
                    f"raw_{name}": value
                    for name, value in zip(parameter_names, iteration.parameter_vector)
                }
            )
            row.update(
                {
                    f"gradient_{name}": value
                    for name, value in zip(parameter_names, iteration.gradient)
                }
            )
            row.update(
                {
                    f"step_{name}": value
                    for name, value in zip(parameter_names, iteration.step)
                }
            )
            writer.writerow(row)


def _write_plot(
    path: Path,
    solver_results: dict[str, dict[str, Any]],
    *,
    target: InverseTarget,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.2), constrained_layout=True)
    for solver, record in solver_results.items():
        inverse = record["inverse_result"]
        iterations = np.asarray([item.iteration for item in inverse.iterations])
        relative = np.asarray([item.relative_l2_error for item in inverse.iterations])
        center_errors_mm = 1.0e3 * np.asarray(
            [
                math.hypot(
                    item.physical_parameters["center_x"] - target.center[0],
                    item.physical_parameters["center_y"] - target.center[1],
                )
                for item in inverse.iterations
            ]
        )
        radius_errors_mm = 1.0e3 * np.abs(
            np.asarray(
                [item.physical_parameters["radius"] for item in inverse.iterations]
            )
            - target.reference_radius
        )
        axes[0].semilogy(iterations, relative, marker="o", label=solver.upper())
        axes[1].semilogy(
            iterations,
            np.maximum(center_errors_mm, 1.0e-12),
            marker="o",
            label=f"{solver.upper()} center",
        )
        axes[1].semilogy(
            iterations,
            np.maximum(radius_errors_mm, 1.0e-12),
            marker="s",
            linestyle="--",
            label=f"{solver.upper()} radius",
        )
    axes[0].set(title="Training-data convergence", xlabel="accepted iteration")
    axes[0].set_ylabel("relative complex L2")
    axes[1].set(title="Recovered geometry", xlabel="accepted iteration")
    axes[1].set_ylabel("absolute error (mm)")
    for axis in axes:
        axis.grid(True, which="both", alpha=0.25)
        axis.legend()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _acceptance_gates(
    solver_metrics: dict[str, dict[str, Any]],
    *,
    target: InverseTarget,
) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    for solver, metrics in solver_metrics.items():
        gates[f"{solver}_optimizer_converged"] = {
            "passed": bool(metrics["converged"]),
            "value": metrics["stop_reason"],
            "requirement": "converged stop condition",
        }
        gates[f"{solver}_accepted_losses_monotone"] = {
            "passed": bool(metrics["accepted_losses_monotone"]),
            "value": metrics["accepted_losses_monotone"],
            "requirement": True,
        }
        gates[f"{solver}_training_loss_drop"] = {
            "passed": metrics["training_loss_drop_factor"] >= 100.0,
            "value": metrics["training_loss_drop_factor"],
            "requirement": ">= 100",
        }
        for metric_key, threshold, requirement in target.shape_error_gates():
            # "final_amplitude_error" gates as "<solver>_amplitude_error".
            gate_name = metric_key.removeprefix("final_").removesuffix("_m")
            gate_name = gate_name.removesuffix("_radians")
            gates[f"{solver}_{gate_name}"] = {
                "passed": metrics[metric_key] <= threshold,
                "value": metrics[metric_key],
                "requirement": requirement,
            }
        gates[f"{solver}_final_boundary_error"] = {
            "passed": (
                metrics["maximum_node_to_exact_boundary_distance_m"] <= 1.0e-3
            ),
            "value": metrics["maximum_node_to_exact_boundary_distance_m"],
            "requirement": "<= 1e-3 m",
        }
        gates[f"{solver}_linear_system_residual"] = {
            "passed": metrics["maximum_linear_system_relative_residual"] <= 1.0e-10,
            "value": metrics["maximum_linear_system_relative_residual"],
            "requirement": "<= 1e-10",
        }
        gates[f"{solver}_holdout_relative_l2"] = {
            "passed": metrics["final_holdout_relative_l2"] <= 1.5e-1,
            "value": metrics["final_holdout_relative_l2"],
            "requirement": "<= 0.15",
        }
        if not bool(metrics["initial_claims_signed_distance"]):
            gates[f"{solver}_initial_shape_non_circular"] = {
                "passed": metrics["initial_radial_span_m"] >= 2.0e-3,
                "value": metrics["initial_radial_span_m"],
                "requirement": ">= 2e-3 m",
            }
            gates[f"{solver}_initial_field_non_distance"] = {
                "passed": (
                    metrics["initial_maximum_unit_gradient_deviation"] >= 5.0e-2
                ),
                "value": metrics["initial_maximum_unit_gradient_deviation"],
                "requirement": ">= 5e-2",
            }
    if "kress" in solver_metrics:
        kress_error = solver_metrics["kress"]["final_holdout_relative_l2"]
        gates["kress_holdout_accuracy"] = {
            "passed": kress_error <= target.kress_holdout_accuracy_threshold,
            "value": kress_error,
            "requirement": target.kress_holdout_accuracy_requirement,
        }
    if {"mod", "kress"} <= set(solver_metrics):
        kress_error = solver_metrics["kress"]["final_holdout_relative_l2"]
        mod_error = solver_metrics["mod"]["final_holdout_relative_l2"]
        gates["kress_holdout_beats_mod"] = {
            "passed": kress_error < mod_error,
            "value": {"kress": kress_error, "mod": mod_error},
            "requirement": "Kress < MOD",
        }
        kress_target_error = solver_metrics["kress"][
            "target_geometry_holdout_relative_l2"
        ]
        mod_target_error = solver_metrics["mod"][
            "target_geometry_holdout_relative_l2"
        ]
        gates["kress_target_geometry_holdout_beats_mod"] = {
            "passed": kress_target_error < mod_target_error,
            "value": {"kress": kress_target_error, "mod": mod_target_error},
            "requirement": "Kress < MOD on the identical true boundary",
        }
    return gates


def _write_summary(
    path: Path,
    *,
    metrics: dict[str, Any],
    solver_metrics: dict[str, dict[str, Any]],
    target: InverseTarget,
) -> None:
    initialization = metrics["initialization"]
    initial_values = ", ".join(
        f"{name}={float(value):.6g}"
        for name, value in initialization["physical_parameters"].items()
    )
    lines = [
        "# Solver-neutral implicit-initialization inverse comparison",
        "",
        (
            f"A `{initialization['kind']}` field initialized with `{initial_values}` "
            + target.summary_sentence()
        ),
        "",
        (
            "MOD and Kress received the same ordered Method-B boundary at each "
            "parameter evaluation and used the same bounded central-FD damped "
            "Gauss--Newton inverse. Only the forward solver differed."
        ),
        "",
        "## Outcome",
        "",
        (
            "| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | "
            "Final holdout rel. L2 | True-boundary holdout rel. L2 | "
            "Center error (mm) | Radius error (mm) | "
            "Max node-to-boundary (mm) | Inverse wall time |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for solver, row in solver_metrics.items():
        lines.append(
            f"| {solver.upper()} | {row['initial_training_relative_l2']:.3e} | "
            f"{row['final_training_relative_l2']:.3e} | "
            f"{row['training_loss_drop_factor']:.3e}x | "
            f"{row['final_holdout_relative_l2']:.3e} | "
            f"{row['target_geometry_holdout_relative_l2']:.3e} | "
            f"{1.0e3 * row['final_center_error_m']:.4f} | "
            f"{1.0e3 * row['final_radius_error_m']:.4f} | "
            f"{1.0e3 * row['maximum_node_to_exact_boundary_distance_m']:.4f} | "
            f"{row['inverse_wall_seconds']:.2f} s |"
        )
    extra_shape_keys = tuple(
        key
        for key, _threshold, _requirement in target.shape_error_gates()
        if key not in {"final_center_error_m", "final_radius_error_m"}
    )
    if extra_shape_keys:
        lines.extend(
            [
                "",
                "| Solver | "
                + " | ".join(
                    key.removeprefix("final_").replace("_", " ")
                    for key in extra_shape_keys
                )
                + " |",
                "|---" * (len(extra_shape_keys) + 1) + "|",
            ]
        )
        for solver, row in solver_metrics.items():
            values = " | ".join(f"{row[key]:.3e}" for key in extra_shape_keys)
            lines.append(f"| {solver.upper()} | {values} |")
    stop_descriptions = "; ".join(
        f"{solver.upper()}: `{row['stop_reason']}` after "
        f"{row['accepted_updates']} accepted updates / "
        f"{row['total_forward_evaluations']} forward evaluations"
        for solver, row in solver_metrics.items()
    )
    comparison_summary = metrics.get("comparison_summary", {})
    comparison_sentence = ""
    if comparison_summary:
        evaluation_counts = {
            solver: int(row["total_forward_evaluations"])
            for solver, row in solver_metrics.items()
        }
        if len(set(evaluation_counts.values())) == 1:
            evaluation_clause = (
                f"For the same {next(iter(evaluation_counts.values()))} inverse "
                "evaluations, "
            )
        else:
            evaluation_clause = (
                "With "
                + " and ".join(
                    f"{solver.upper()} at {count} inverse evaluations"
                    for solver, count in evaluation_counts.items()
                )
                + ", "
            )
        comparison_sentence = (
            evaluation_clause
            + "MOD/Kress wall time was "
            f"`{comparison_summary['inverse_wall_time_ratio_mod_over_kress']:.2f}x`; "
            "the final held-out MOD/Kress error ratio was "
            f"`{comparison_summary['final_holdout_error_ratio_mod_over_kress']:.3e}x`."
        )
    lines.extend(
        [
            "",
            stop_descriptions + ".",
            "",
            comparison_sentence,
            "" if comparison_sentence else "",
            "Training frequencies: "
            + ", ".join(f"{value:g} GHz" for value in metrics["train_frequencies_ghz"])
            + ". Holdout frequencies: "
            + ", ".join(
                f"{value:g} GHz" for value in metrics["holdout_frequencies_ghz"]
            )
            + ".",
            "",
            f"Observations: {metrics['truth_oracle']}.",
            "",
            "## Acceptance",
            "",
        ]
    )
    for name, gate in metrics["acceptance_gates"].items():
        marker = "PASS" if gate["passed"] else "FAIL"
        lines.append(
            f"- **{marker}** `{name}`: value `{gate['value']}`, required "
            f"`{gate['requirement']}`."
        )
    lines.extend(
        [
            "",
            f"Overall: **{'PASS' if metrics['acceptance_passed'] else 'FAIL'}**.",
            "",
            "## Reproduce",
            "",
            "```bash",
            "OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\",
            "NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \\",
            "/home/drdeng/miniconda3/envs/EMNerf/bin/python \\",
            f"  {metrics['provenance']['command']}",
            "```",
            "",
            (
                "`metrics.json` contains per-frequency errors, geometry distances, "
                "linear-solve residuals, timings, configuration, and provenance. "
                "The CSV files contain every accepted iterate. Timings are one-run "
                "engineering measurements, not a formal benchmark."
            ),
            "",
            "## Scope",
            "",
            (
                "This establishes an auditable low-dimensional inverse baseline for "
                "smooth single-component Torch implicit fields. The field-to-curve "
                "seam crosses "
                "NumPy and is not autograd-differentiable. A large randomly initialized "
                "SIREN therefore needs a topology-valid initialization and derivatives "
                "of the actual Kress weighted operators before it is a scalable inverse."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = REPOSITORY_ROOT / output_dir
    _prepare_output_directory(output_dir, overwrite=args.overwrite)

    target = _build_target(args.target)
    target_center = target.center
    source_points, receiver_points = _ring_scan(
        center=target_center,
        standoff=0.30,
        num_pairs=args.num_pairs,
    )
    all_frequencies_ghz = tuple(args.train_ghz) + tuple(args.holdout_ghz)
    all_problem = _build_problem(
        all_frequencies_ghz, source_points, receiver_points
    )
    train_problem = _build_problem(args.train_ghz, source_points, receiver_points)
    print(f"[oracle] {target.truth_oracle}", flush=True)
    all_truth = target.observations(all_problem)
    train_truth = all_truth[:, : len(args.train_ghz)]
    training_data = ComplexScatteredData(train_problem, train_truth)
    # Data quality is gated before any inverse runs: a small final residual
    # against unresolved observations would mean nothing.
    oracle_diagnostics = target.oracle_diagnostics(all_problem)
    if oracle_diagnostics is not None:
        print(
            "[oracle] self-convergence "
            f"{oracle_diagnostics['coarse_num_nodes']} vs "
            f"{oracle_diagnostics['num_nodes']} nodes: "
            f"{oracle_diagnostics['maximum_relative_difference']:.3e}",
            flush=True,
        )

    geometry_config = target.geometry_config(args.num_nodes)
    template_model, template_controller = _build_initial_model(args.initial_model)
    inverse_config = _inverse_config_for_controller(
        template_controller,
        max_iterations=args.max_iterations,
        loss_tolerance=args.loss_tolerance,
    )
    initialization_metadata_function = getattr(
        template_model, "initialization_metadata", None
    )
    initialization_metadata = (
        initialization_metadata_function()
        if callable(initialization_metadata_function)
        else {
            "kind": "exact_circle_signed_distance",
            "claims_signed_distance": True,
        }
    )
    initial_physical_parameters = template_controller.physical_parameter_dict()
    initial_raw_parameters = template_controller.parameter_vector()

    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": shlex.join(sys.argv if argv is None else [sys.argv[0], *argv]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": _package_version("scipy"),
        "scikit_image": _package_version("scikit-image"),
        "matplotlib": _package_version("matplotlib"),
        "torch": torch.__version__,
        "thread_environment": _thread_provenance(),
        "git": _git_provenance(),
    }
    solver_results: dict[str, dict[str, Any]] = {}
    serializable_solver_metrics: dict[str, dict[str, Any]] = {}

    for solver in args.solvers:
        print(
            f"\n[{solver.upper()}] {args.initial_model} implicit recovery",
            flush=True,
        )
        model, controller = _build_initial_model(args.initial_model)
        if controller.names != template_controller.names or not np.array_equal(
            controller.parameter_vector(), initial_raw_parameters
        ):
            raise RuntimeError("Initial model factory is not deterministic across solvers.")

        initial_all = predict_paired_response(
            model, all_problem, geometry_config, solver=solver
        )
        target_model = target.exact_model()
        target_geometry_forward = predict_paired_response(
            target_model, all_problem, geometry_config, solver=solver
        )

        def progress(iteration: Any, *, _solver: str = solver) -> None:
            physical = iteration.physical_parameters
            print(
                f"  {_solver.upper()} iter={iteration.iteration:02d} "
                f"loss={iteration.loss:.4e} rel={iteration.relative_l2_error:.4e} "
                f"center=({physical['center_x']:.6f},{physical['center_y']:.6f}) "
                f"radius={physical['radius']:.6f}",
                flush=True,
            )

        inverse_result = run_parameter_fd_inverse(
            model,
            controller,
            training_data,
            geometry_config,
            solver=solver,
            config=inverse_config,
            progress_callback=progress,
        )
        final_all = predict_paired_response(
            model, all_problem, geometry_config, solver=solver
        )

        train_columns = slice(0, len(args.train_ghz))
        holdout_columns = slice(len(args.train_ghz), len(all_frequencies_ghz))
        initial_train_loss, initial_train_relative = _objective_metrics(
            initial_all.scattered_response[:, train_columns], train_truth
        )
        final_train_loss, final_train_relative = _objective_metrics(
            final_all.scattered_response[:, train_columns], train_truth
        )
        _, initial_holdout_relative = _objective_metrics(
            initial_all.scattered_response[:, holdout_columns],
            all_truth[:, holdout_columns],
        )
        _, final_holdout_relative = _objective_metrics(
            final_all.scattered_response[:, holdout_columns],
            all_truth[:, holdout_columns],
        )
        _, target_geometry_all_relative = _objective_metrics(
            target_geometry_forward.scattered_response,
            all_truth,
        )
        _, target_geometry_holdout_relative = _objective_metrics(
            target_geometry_forward.scattered_response[:, holdout_columns],
            all_truth[:, holdout_columns],
        )
        final_physical = controller.physical_parameter_dict()
        shape_errors = target.shape_errors(final_physical)
        losses = np.asarray([item.loss for item in inverse_result.iterations])
        initial_curve_metrics = target.curve_distance_metrics(
            initial_all.geometry_build.curve.points
        )
        curve_metrics = target.curve_distance_metrics(
            final_all.geometry_build.curve.points
        )
        initial_center = (
            float(initial_physical_parameters["center_x"]),
            float(initial_physical_parameters["center_y"]),
        )
        initial_gradient_metrics = _field_gradient_metrics(
            model=template_model,
            points=initial_all.geometry_build.curve.points,
        )
        per_frequency_initial = _per_frequency_relative_error(
            initial_all.scattered_response, all_truth
        )
        per_frequency_final = _per_frequency_relative_error(
            final_all.scattered_response, all_truth
        )
        per_frequency_target_geometry = _per_frequency_relative_error(
            target_geometry_forward.scattered_response, all_truth
        )
        metrics = {
            "initial_parameters": initial_physical_parameters,
            "initial_claims_signed_distance": bool(
                initialization_metadata["claims_signed_distance"]
            ),
            "initial_radial_span_m": _radial_span(
                initial_all.geometry_build.curve.points,
                initial_center,
            ),
            "initial_mean_node_to_exact_boundary_distance_m": (
                initial_curve_metrics["mean_node_to_exact_boundary_distance_m"]
            ),
            "initial_maximum_node_to_exact_boundary_distance_m": (
                initial_curve_metrics["maximum_node_to_exact_boundary_distance_m"]
            ),
            "initial_maximum_unit_gradient_deviation": (
                initial_gradient_metrics["maximum_unit_gradient_deviation"]
            ),
            "initial_minimum_field_gradient_norm": (
                initial_gradient_metrics["minimum_field_gradient_norm"]
            ),
            "initial_maximum_field_gradient_norm": (
                initial_gradient_metrics["maximum_field_gradient_norm"]
            ),
            "initial_geometry_maximum_raw_field_residual": (
                initial_all.geometry_build.maximum_curve_sdf_residual
            ),
            "initial_geometry_maximum_normalized_residual_m": (
                initial_all.geometry_build.maximum_normalized_curve_residual
            ),
            "final_parameters": final_physical,
            **shape_errors,
            **curve_metrics,
            "initial_training_loss": initial_train_loss,
            "final_training_loss": final_train_loss,
            "training_loss_drop_factor": initial_train_loss
            / max(final_train_loss, np.finfo(np.float64).tiny),
            "initial_training_relative_l2": initial_train_relative,
            "final_training_relative_l2": final_train_relative,
            "initial_holdout_relative_l2": initial_holdout_relative,
            "final_holdout_relative_l2": final_holdout_relative,
            "target_geometry_all_frequency_relative_l2": target_geometry_all_relative,
            "target_geometry_holdout_relative_l2": target_geometry_holdout_relative,
            "per_frequency_initial_relative_l2": {
                f"{frequency:g}_GHz": float(error)
                for frequency, error in zip(
                    all_frequencies_ghz, per_frequency_initial
                )
            },
            "per_frequency_final_relative_l2": {
                f"{frequency:g}_GHz": float(error)
                for frequency, error in zip(all_frequencies_ghz, per_frequency_final)
            },
            "per_frequency_target_geometry_relative_l2": {
                f"{frequency:g}_GHz": float(error)
                for frequency, error in zip(
                    all_frequencies_ghz, per_frequency_target_geometry
                )
            },
            "accepted_losses_monotone": bool(
                np.all(losses[1:] <= losses[:-1] + 64.0 * np.finfo(float).eps)
            ),
            "accepted_updates": len(inverse_result.iterations) - 1,
            "converged": inverse_result.converged,
            "stop_reason": inverse_result.stop_reason,
            "total_forward_evaluations": inverse_result.total_evaluation_count,
            "cache_hits": inverse_result.cache_hit_count,
            "inverse_forward_seconds": inverse_result.total_forward_seconds,
            "inverse_wall_seconds": inverse_result.total_seconds,
            "initial_all_frequency_forward_seconds": initial_all.total_seconds,
            "final_all_frequency_forward_seconds": final_all.total_seconds,
            "target_geometry_all_frequency_forward_seconds": (
                target_geometry_forward.total_seconds
            ),
            "maximum_linear_system_relative_residual": max(
                float(np.max(initial_all.linear_system_relative_residuals)),
                float(np.max(final_all.linear_system_relative_residuals)),
                inverse_result.maximum_system_residual,
                float(
                    np.max(
                        target_geometry_forward.linear_system_relative_residuals
                    )
                ),
            ),
            "final_geometry_maximum_raw_field_residual": (
                final_all.geometry_build.maximum_curve_sdf_residual
            ),
            "final_geometry_maximum_normalized_residual_m": (
                final_all.geometry_build.maximum_normalized_curve_residual
            ),
            "final_geometry_speed_ratio": final_all.geometry_build.speed_ratio,
        }
        solver_results[solver] = {
            "inverse_result": inverse_result,
            "initial_forward": initial_all,
            "final_forward": final_all,
            "target_geometry_forward": target_geometry_forward,
        }
        serializable_solver_metrics[solver] = metrics
        _write_trajectory(output_dir / f"{solver}_trajectory.csv", inverse_result)
        np.savez_compressed(
            output_dir / f"{solver}_responses.npz",
            frequencies_ghz=np.asarray(all_frequencies_ghz),
            exact_scattered_response=all_truth,
            initial_scattered_response=initial_all.scattered_response,
            final_scattered_response=final_all.scattered_response,
            target_geometry_scattered_response=(
                target_geometry_forward.scattered_response
            ),
            initial_curve_points=initial_all.geometry_build.curve.points,
            final_curve_points=final_all.geometry_build.curve.points,
            target_curve_points=target_geometry_forward.geometry_build.curve.points,
            exact_boundary_points=target.exact_boundary_polyline(),
            geometry_trajectory=np.stack(
                [item.geometry_points for item in inverse_result.iterations], axis=0
            ),
        )

    gates = _acceptance_gates(serializable_solver_metrics, target=target)
    if oracle_diagnostics is not None:
        gates["observation_oracle_self_convergence"] = {
            "passed": oracle_diagnostics["maximum_relative_difference"] <= 1.0e-8,
            "value": oracle_diagnostics["maximum_relative_difference"],
            "requirement": "<= 1e-8",
        }
    comparison_controls: dict[str, Any] = {}
    if {"mod", "kress"} <= set(solver_results):
        initial_boundary_delta = float(
            np.max(
                np.abs(
                    solver_results["mod"]["initial_forward"]
                    .geometry_build.curve.points
                    - solver_results["kress"]["initial_forward"]
                    .geometry_build.curve.points
                )
            )
        )
        target_boundary_delta = float(
            np.max(
                np.abs(
                    solver_results["mod"]["target_geometry_forward"]
                    .geometry_build.curve.points
                    - solver_results["kress"]["target_geometry_forward"]
                    .geometry_build.curve.points
                )
            )
        )
        comparison_controls = {
            "maximum_initial_boundary_coordinate_delta_m": initial_boundary_delta,
            "maximum_target_boundary_coordinate_delta_m": target_boundary_delta,
        }
        gates["common_initial_boundary_identical"] = {
            "passed": initial_boundary_delta <= 1.0e-14,
            "value": initial_boundary_delta,
            "requirement": "<= 1e-14 m",
        }
        gates["common_target_boundary_identical"] = {
            "passed": target_boundary_delta <= 1.0e-14,
            "value": target_boundary_delta,
            "requirement": "<= 1e-14 m",
        }
    comparison_summary: dict[str, float] = {}
    if {"mod", "kress"} <= set(serializable_solver_metrics):
        mod_metrics = serializable_solver_metrics["mod"]
        kress_metrics = serializable_solver_metrics["kress"]
        comparison_summary = {
            "inverse_wall_time_ratio_mod_over_kress": (
                mod_metrics["inverse_wall_seconds"]
                / max(
                    kress_metrics["inverse_wall_seconds"],
                    np.finfo(np.float64).tiny,
                )
            ),
            "final_holdout_error_ratio_mod_over_kress": (
                mod_metrics["final_holdout_relative_l2"]
                / max(
                    kress_metrics["final_holdout_relative_l2"],
                    np.finfo(np.float64).tiny,
                )
            ),
            "target_geometry_holdout_error_ratio_mod_over_kress": (
                mod_metrics["target_geometry_holdout_relative_l2"]
                / max(
                    kress_metrics["target_geometry_holdout_relative_l2"],
                    np.finfo(np.float64).tiny,
                )
            ),
        }
    acceptance_passed = all(bool(gate["passed"]) for gate in gates.values())
    metrics_document = {
        "schema_version": 1,
        "benchmark": target.benchmark(args.initial_model),
        "truth_oracle": target.truth_oracle,
        "train_frequencies_ghz": tuple(args.train_ghz),
        "holdout_frequencies_ghz": tuple(args.holdout_ghz),
        "target_shape": target.name,
        "target": target.parameter_dict(),
        "observation_oracle_diagnostics": oracle_diagnostics,
        "initialization": {
            **initialization_metadata,
            "physical_parameters": initial_physical_parameters,
            "raw_parameter_names": template_controller.names,
            "raw_parameter_vector": initial_raw_parameters,
            "raw_lower_bounds": template_controller.lower_bounds,
            "raw_upper_bounds": template_controller.upper_bounds,
        },
        "experiment": {
            "num_pairs": args.num_pairs,
            "ring_standoff_m": 0.30,
            "tx_rx_offset_m": float(physical_config.TX_RX_OFFSET),
            "source_strength": "1e-6+0j at every frequency",
            "source_points_m": source_points,
            "receiver_points_m": receiver_points,
            "angular_frequencies_rad_s": all_problem.angular_frequencies,
            "observation_noise": "none",
            "exterior": _jsonable(vars(all_problem.exterior)),
            "interior": _jsonable(vars(all_problem.interior)),
            "geometry_config": _jsonable(vars(geometry_config)),
            "inverse_config": _jsonable(vars(inverse_config)),
            "controlled_parameters": template_controller.names,
            "forward_difference": "Only solver dispatch: MOD vs Kress",
        },
        "comparison_controls": comparison_controls,
        "comparison_summary": comparison_summary,
        "solvers": serializable_solver_metrics,
        "acceptance_gates": gates,
        "acceptance_passed": acceptance_passed,
        "provenance": provenance,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(_jsonable(metrics_document), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_summary(
        output_dir / "summary.md",
        metrics=metrics_document,
        solver_metrics=serializable_solver_metrics,
        target=target,
    )
    _write_plot(output_dir / "convergence.png", solver_results, target=target)

    print(f"\nArtifacts: {output_dir}", flush=True)
    for name, gate in gates.items():
        print(f"  {'PASS' if gate['passed'] else 'FAIL'} {name}", flush=True)
    print(f"Overall acceptance: {'PASS' if acceptance_passed else 'FAIL'}", flush=True)
    return 0 if acceptance_passed or args.no_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
