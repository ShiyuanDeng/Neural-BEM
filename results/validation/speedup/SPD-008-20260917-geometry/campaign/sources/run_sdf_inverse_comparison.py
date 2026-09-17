#!/usr/bin/env python3
"""Recover an analytic target from wrong implicit initializations with MOD/Kress.

The observation data always come from an independent source -- the analytic
penetrable-cylinder Mie series for the circle target, and the from-scratch
``nystrom_ref`` oracle for the five-lobe star target -- never from either
solver under test. The implicit field owns the geometry, and every candidate
is re-extracted through Method B. Neural Kress runs use boundary adjoint
sensitivities to update the network by default. Analytic controls and MOD use
the parameter finite-difference reference optimizer; ``--optimizer
parameter_fd`` also enables that reference for neural Kress runs.
"""

from __future__ import annotations

import argparse
import csv
import copy
from datetime import datetime, timezone
from dataclasses import replace
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from time import perf_counter
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
    SirenImplicitField2D,
    StarLevelSet2D,
    StarShape,
    build_circle_parameter_controller,
    build_ellipse_parameter_controller,
    build_radial_random_feature_parameter_controller,
    build_siren_parameter_controller,
    build_star_parameter_controller,
    first_order_distance_supervisor,
    normalized_complex_residual,
    pretrain_implicit_field,
    nystrom_paired_response,
    nystrom_self_convergence,
    predict_paired_response,
    run_parameter_fd_inverse,
)
from sdf_inverse.geometry import Bounds2D, build_ordered_sdf_geometry  # noqa: E402
from sdf_inverse.implicit_adjoint import (  # noqa: E402
    ImplicitMLPAdjointConfig,
    run_implicit_mlp_adjoint_inverse,
)


DEFAULT_INITIAL_CENTER = (0.48, 0.52)
DEFAULT_INITIAL_RADIUS = 0.065
DEFAULT_TRAIN_FREQUENCIES_GHZ = (0.25, 0.50)
DEFAULT_HOLDOUT_FREQUENCIES_GHZ = (1.0, 1.5, 2.5)
DEFAULT_SOLVERS = ("mod", "kress")
OPTIMIZER_CHOICES = ("auto", "adjoint", "parameter_fd")
DEFAULT_TARGET = "circle"
TARGET_CHOICES = ("circle", "star")
INITIAL_MODEL_CHOICES = (
    "circle",
    "ellipse",
    "random_features",
    "star",
    "siren_circle",
    "siren_ellipse",
    "siren_star",
)
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

# Neural initializations.  The network is the repository's SIREN, warm started
# onto the same wrong analytic shapes the parametric cases start from.  Its
# small architecture retains the historical controls. Parameter finite
# differences cost 2 N + 1 forward solves per Jacobian; neural Kress defaults
# now use the adjoint and avoid that network-parameter scaling.
DEFAULT_SIREN_HIDDEN_FEATURES = 32
DEFAULT_SIREN_HIDDEN_LAYERS = 0
# SIREN's omega_0 assumes inputs in [-1, 1]; 30 is tuned for wide networks and
# leaves a small one unable to fit a smooth cone at all.
DEFAULT_SIREN_OMEGA_0 = 10.0
DEFAULT_SIREN_SEED = 0
DEFAULT_SIREN_PRETRAIN_STEPS = 6000
DEFAULT_SIREN_EIKONAL_WEIGHT = 0.1
DEFAULT_SIREN_WEIGHT_BOUND = 5.0
SIREN_INITIAL_MODELS = ("siren_circle", "siren_ellipse", "siren_star")
GENERATED_ARTIFACT_NAMES = (
    "metrics.json",
    "summary.md",
    "convergence.png",
    "mod_trajectory.csv",
    "mod_responses.npz",
    "kress_trajectory.csv",
    "kress_responses.npz",
    "mod_model.pt",
    "kress_model.pt",
    "kress_trials.jsonl",
    "kress_accepted_iterates.json",
    "initial_model.pt", "target_control_initial_model.pt",
    "execution_stage.json", "failure_traceback.txt",
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

    def shape_errors(
        self,
        physical_parameters: Mapping[str, float],
        curve_points: np.ndarray,
    ) -> dict[str, float]:
        raise NotImplementedError

    def shape_error_gates(self) -> tuple[tuple[str, float, str], ...]:
        """Return ``(metric_key, threshold, requirement)`` gate specifications."""

        raise NotImplementedError

    @staticmethod
    def shape_measurement_source(physical_parameters: Mapping[str, float]) -> str:
        """Whether shape quantities come from controls or from the contour.

        A parametric field carries its own center and size; a neural field
        does not, so its shape is measured from the extracted zero set.
        """

        has_geometry = "center_x" in physical_parameters and "radius" in physical_parameters
        return "parameters" if has_geometry else "contour"

    def measured_shape(
        self,
        physical_parameters: Mapping[str, float],
        curve_points: np.ndarray,
    ) -> dict[str, float]:
        if self.shape_measurement_source(physical_parameters) == "parameters":
            return {str(k): float(v) for k, v in physical_parameters.items()}
        return _contour_shape_summary(curve_points)

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
    initial_model_choices = (
        "circle",
        "ellipse",
        "random_features",
        "siren_circle",
        "siren_ellipse",
    )
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

    def shape_errors(
        self,
        physical_parameters: Mapping[str, float],
        curve_points: np.ndarray,
    ) -> dict[str, float]:
        measured = self.measured_shape(physical_parameters, curve_points)
        return {
            "final_center_error_m": math.hypot(
                measured["center_x"] - self.center[0],
                measured["center_y"] - self.center[1],
            ),
            "final_radius_error_m": abs(
                measured["radius"] - self.reference_radius
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
    initial_model_choices = ("star", "siren_star")
    default_initial_model = "star"
    # Retain the historical band that recovered the five-parameter star.
    # Physical/modal Jacobian studies must quantify its observability for
    # general neural boundaries and alternative acquisition patterns.
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

    def measured_shape(
        self,
        physical_parameters: Mapping[str, float],
        curve_points: np.ndarray,
    ) -> dict[str, float]:
        if self.shape_measurement_source(physical_parameters) == "parameters":
            return {str(k): float(v) for k, v in physical_parameters.items()}
        return _fit_radial_star_parameters(curve_points, lobes=self.shape.lobes)

    def shape_errors(
        self,
        physical_parameters: Mapping[str, float],
        curve_points: np.ndarray,
    ) -> dict[str, float]:
        measured = self.measured_shape(physical_parameters, curve_points)
        rotation_error = abs(
            measured["rotation_radians"] - self.shape.rotation_radians
        )
        # A fitted phase is only defined modulo the star's own symmetry.
        period = self.shape.symmetry_period_radians
        rotation_error = min(rotation_error % period, period - rotation_error % period)
        return {
            "final_center_error_m": math.hypot(
                measured["center_x"] - self.center[0],
                measured["center_y"] - self.center[1],
            ),
            "final_radius_error_m": abs(
                measured["radius"] - self.shape.mean_radius
            ),
            "final_amplitude_error": abs(
                measured["amplitude"] - self.shape.amplitude
            ),
            "final_rotation_error_radians": rotation_error,
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


def _parse_args(
    argv: Sequence[str] | None = None, *, implicit_defaults: bool = False
) -> argparse.Namespace:
    started_utc = datetime.now(timezone.utc)
    run_tag = started_utc.strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(
        description=(
            "Recover an analytic target from a deliberately wrong implicit "
            "initialization using independent observations and Method B. "
            "Neural Kress runs default to adjoint weight updates; MOD and "
            "analytic controls use parameter finite differences."
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
        default=["kress"] if implicit_defaults else list(DEFAULT_SOLVERS),
        help=(
            "Forward branches to run (default: kress)."
            if implicit_defaults else "Forward branches to run (default: mod kress)."
        ),
    )
    parser.add_argument(
        "--initial-model",
        choices=INITIAL_MODEL_CHOICES,
        default=None,
        help=(
            "Implicit initialization: exact circle SDF, non-distance ellipse, "
            "topology-constrained random-feature neural field, or wrong star. "
            + ("Defaults to a SIREN fitted to the wrong initial target-family shape."
               if implicit_defaults else "Defaults to the target's own family.")
        ),
    )
    parser.add_argument(
        "--optimizer",
        choices=OPTIMIZER_CHOICES,
        default="adjoint" if implicit_defaults else "auto",
        help=(
            "auto: adjoint for siren_* with Kress, parameter_fd otherwise; "
            "adjoint requires a siren_* initial model and --solvers kress; "
            "parameter_fd explicitly selects the numerical reference."
        ),
    )
    parser.add_argument(
        "--learning-rate", type=float, default=1.0e-3,
        help="Initial Adam step size for the adjoint optimizer.",
    )
    parser.add_argument(
        "--eikonal-weight", type=float, default=0.01,
        help="SDF gradient regularization during adjoint inverse updates.",
    )
    parser.add_argument("--eikonal-sampling", choices=("uniform_box", "contour_band"), default="uniform_box")
    parser.add_argument("--max-candidate-evaluations", type=int, default=None)
    parser.add_argument("--max-wall-seconds", type=float, default=None,
                        help="Inverse wall cap; checked between evaluations, excluding pretraining and controls.")
    parser.add_argument(
        "--conversion-tolerance-mm", type=float, default=0.2,
        help="Maximum audited raw/Method-B contour disagreement for neural fields, in mm.",
    )
    # Method-B conversion resolution. The 2026-09-07 reruns showed the
    # bandwidth, not the grid or sample density, sets the achievable raw/
    # converted agreement, so it must be reachable without editing a target.
    parser.add_argument(
        "--bandwidth", type=int, default=None,
        help="Method-B arc-length Fourier bandwidth (default: the target's own value).",
    )
    parser.add_argument(
        "--grid-resolution", type=int, default=None,
        help="Square zero-set extraction grid resolution (default: the target's own value).",
    )
    parser.add_argument(
        "--projected-samples", type=int, default=None,
        help="Projected zero-set samples fitted by Method B (default: the target's own value).",
    )
    parser.add_argument(
        "--mlp-hidden-features", type=int,
        default=64 if implicit_defaults else DEFAULT_SIREN_HIDDEN_FEATURES,
        help="SIREN width shared by the initialization and target-fit control.",
    )
    parser.add_argument(
        "--mlp-hidden-layers", type=int,
        default=2 if implicit_defaults else DEFAULT_SIREN_HIDDEN_LAYERS,
        help="SIREN hidden-layer count shared by all neural controls.",
    )
    parser.add_argument(
        "--mlp-pretrain-steps", type=int, default=DEFAULT_SIREN_PRETRAIN_STEPS,
        help="Supervised initialization steps, before inverse weight updates.",
    )
    parser.add_argument(
        "--mlp-pretrain-eikonal-weight", type=float, default=None,
        help="Pretraining penalty override: defaults to 0 for the validated star proxy, 0.1 for circle/ellipse. Independent of --eikonal-weight.",
    )
    parser.add_argument(
        "--max-backtracks", type=int, default=None,
        help="Maximum line-search halvings (14 for neural adjoint, 8 for parameter FD).",
    )
    parser.add_argument(
        "--start-at-truth", action="store_true",
        help="Initialize from the exact-target neural fit and record accepted holdout metrics; diagnostic only.",
    )
    parser.add_argument(
        "--record-accepted-holdout", action="store_true",
        help="Evaluate the fixed holdout after every accepted neural iterate; also enabled by --start-at-truth.",
    )
    parser.add_argument(
        "--meaningful-boundary-step-mm", type=float, default=0.1,
        help="Reporting floor for meaningful neural boundary movement; does not change acceptance.",
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
        args.initial_model = (
            f"siren_{args.target}" if implicit_defaults else target.default_initial_model
        )
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
    if args.bandwidth is None:
        args.bandwidth = int(target.bandwidth)
    if args.grid_resolution is None:
        args.grid_resolution = int(target.grid_shape[0])
    if args.projected_samples is None:
        args.projected_samples = int(target.projected_samples)
    if args.max_iterations is None:
        args.max_iterations = 60 if implicit_defaults else target.default_max_iterations
    args.max_backtracks_was_explicit = args.max_backtracks is not None
    if args.max_backtracks is None:
        args.max_backtracks = (
            14 if args.initial_model in SIREN_INITIAL_MODELS
            and args.optimizer != "parameter_fd" and "kress" in args.solvers else 8
        )
    if args.start_at_truth and args.initial_model not in SIREN_INITIAL_MODELS:
        parser.error("--start-at-truth requires a siren_* initial model")
    if not math.isfinite(args.meaningful_boundary_step_mm) or args.meaningful_boundary_step_mm <= 0:
        parser.error("--meaningful-boundary-step-mm must be finite and positive")
    if args.num_pairs < 4:
        parser.error("--num-pairs must be at least 4")
    if args.num_nodes < 32 or args.num_nodes % 2:
        parser.error("--num-nodes must be an even integer of at least 32")
    if args.bandwidth < 1:
        parser.error("--bandwidth must be a positive integer")
    if args.grid_resolution < 33 or not args.grid_resolution % 2:
        parser.error("--grid-resolution must be an odd integer of at least 33")
    if args.projected_samples < 2 * args.bandwidth + 2:
        parser.error(
            f"--projected-samples must be at least {2 * args.bandwidth + 2} to fit "
            f"a bandwidth-{args.bandwidth} Method-B curve without aliasing"
        )
    if args.num_nodes < 2 * args.bandwidth + 2:
        parser.error(
            f"--num-nodes must be at least {2 * args.bandwidth + 2} to sample "
            f"the bandwidth-{args.bandwidth} Method-B curve"
        )
    if args.max_iterations < 1:
        parser.error("--max-iterations must be positive")
    if not math.isfinite(args.loss_tolerance) or args.loss_tolerance <= 0.0:
        parser.error("--loss-tolerance must be finite and positive")
    if not math.isfinite(args.learning_rate) or args.learning_rate <= 0.0:
        parser.error("--learning-rate must be finite and positive")
    if not math.isfinite(args.eikonal_weight) or args.eikonal_weight < 0.0:
        parser.error("--eikonal-weight must be finite and non-negative")
    if args.max_candidate_evaluations is not None and args.max_candidate_evaluations < 1:
        parser.error("--max-candidate-evaluations must be positive")
    if args.max_wall_seconds is not None and (not math.isfinite(args.max_wall_seconds) or args.max_wall_seconds <= 0):
        parser.error("--max-wall-seconds must be finite and positive")
    if not math.isfinite(args.conversion_tolerance_mm) or args.conversion_tolerance_mm <= 0.0:
        parser.error("--conversion-tolerance-mm must be finite and positive")
    if args.max_backtracks < 1:
        parser.error("--max-backtracks must be positive")
    if args.mlp_hidden_features < 1:
        parser.error("--mlp-hidden-features must be positive")
    if args.mlp_hidden_layers < 0:
        parser.error("--mlp-hidden-layers must be non-negative")
    if args.mlp_pretrain_steps < 1:
        parser.error("--mlp-pretrain-steps must be positive")
    if args.mlp_pretrain_eikonal_weight is not None and (
        not math.isfinite(args.mlp_pretrain_eikonal_weight) or args.mlp_pretrain_eikonal_weight < 0.0
    ):
        parser.error("--mlp-pretrain-eikonal-weight must be finite and non-negative")
    if set(args.train_ghz) & set(args.holdout_ghz):
        parser.error("training and holdout frequencies must be disjoint")
    # Preserve user order while preventing accidental duplicate work.
    args.solvers = tuple(dict.fromkeys(args.solvers))
    try:
        for solver in args.solvers:
            _optimizer_for_solver(args.initial_model, solver, args.optimizer)
    except ValueError as error:
        parser.error(str(error))
    if (args.start_at_truth or args.record_accepted_holdout) and any(
        _optimizer_for_solver(args.initial_model, solver, args.optimizer) != "adjoint"
        for solver in args.solvers
    ):
        parser.error("--start-at-truth and --record-accepted-holdout require neural Kress adjoint optimization")
    if args.output_dir is None:
        case_tag = f"{args.initial_model}-to-{target.output_tag}"
        if args.initial_model in SIREN_INITIAL_MODELS:
            # Neural bundles are filed by run date so one day's cases sit together.
            args.output_dir = (
                Path("results/inverse/implicit_mlp")
                / started_utc.strftime("%Y-%m-%d")
                / f"{case_tag}-{started_utc.strftime('%H%M%SZ')}"
            )
        else:
            args.output_dir = (
                Path("results/legacy/known_shape_family_parameter_inverse")
                / f"{case_tag}-{run_tag}"
            )
    return args


def _analytic_shape_for_siren(kind: str) -> torch.nn.Module:
    """Return the analytic field a neural initialization is warm started onto.

    Each neural case imitates exactly the wrong shape its parametric sibling
    starts from, so the two differ only in representation.
    """

    if kind == "siren_circle":
        return CircleSDF2D(
            center=DEFAULT_INITIAL_CENTER,
            radius=DEFAULT_INITIAL_RADIUS,
            dtype=torch.float64,
            device="cpu",
        )
    if kind == "siren_ellipse":
        return EllipseLevelSet2D(
            center=DEFAULT_INITIAL_CENTER,
            semi_axes=(0.072, 0.038),
            rotation_radians=0.4,
            dtype=torch.float64,
            device="cpu",
        )
    if kind == "siren_star":
        return StarLevelSet2D(
            center=DEFAULT_STAR_INITIAL_CENTER,
            mean_radius=DEFAULT_STAR_INITIAL_MEAN_RADIUS,
            amplitude=DEFAULT_STAR_INITIAL_AMPLITUDE,
            lobes=int(star_config.TARGET_STAR_LOBES),
            rotation_radians=DEFAULT_STAR_INITIAL_ROTATION,
            dtype=torch.float64,
            device="cpu",
        )
    raise ValueError(f"Unsupported neural initialization: {kind!r}.")


def _build_siren_field(
    target_field: torch.nn.Module,
    *,
    random_seed: int = DEFAULT_SIREN_SEED,
    hidden_features: int = DEFAULT_SIREN_HIDDEN_FEATURES,
    hidden_layers: int = DEFAULT_SIREN_HIDDEN_LAYERS,
    pretrain_steps: int = DEFAULT_SIREN_PRETRAIN_STEPS,
    pretrain_eikonal_weight: float | None = None,
) -> SirenImplicitField2D:
    """Warm start one SIREN onto an analytic field's zero set."""

    box = np.asarray(DEFAULT_GEOMETRY_BOUNDS, dtype=np.float64)
    if pretrain_eikonal_weight is None:
        # Only the star ablation established an improved, valid zero contour.
        # Removing this penalty for the ellipse produced extra components.
        pretrain_eikonal_weight = 0.0 if isinstance(target_field, StarLevelSet2D) else DEFAULT_SIREN_EIKONAL_WEIGHT
    model = SirenImplicitField2D(
        bounds=DEFAULT_GEOMETRY_BOUNDS,
        hidden_features=hidden_features,
        hidden_layers=hidden_layers,
        omega_0=DEFAULT_SIREN_OMEGA_0,
        random_seed=random_seed,
        dtype=torch.float64,
        device="cpu",
    )
    report = pretrain_implicit_field(
        model,
        first_order_distance_supervisor(
            target_field,
            maximum_distance=float(np.linalg.norm(box[1] - box[0])),
        ),
        bounds=DEFAULT_GEOMETRY_BOUNDS,
        steps=pretrain_steps,
        eikonal_weight=pretrain_eikonal_weight,
        random_seed=random_seed,
    )
    model.pretraining_report = report
    return model


def _contour_shape_summary(points: np.ndarray) -> dict[str, float]:
    """Center and size of a contour, for fields with no geometric parameters.

    A neural field has no center or radius to read off, so these are measured
    from the extracted zero set: the node centroid, and the mean radius about
    it.  Both are averages over the whole contour, so a representation's local
    wobble largely cancels rather than being reported as a placement error.
    """

    nodes = np.asarray(points, dtype=np.float64)
    if nodes.ndim != 2 or nodes.shape[1] != 2 or nodes.shape[0] < 3:
        raise ValueError("points must have shape (num_nodes >= 3, 2).")
    centroid = nodes.mean(axis=0)
    radii = np.linalg.norm(nodes - centroid[None, :], axis=1)
    return {
        "center_x": float(centroid[0]),
        "center_y": float(centroid[1]),
        "radius": float(np.mean(radii)),
    }


def _fit_radial_star_parameters(
    points: np.ndarray, *, lobes: int
) -> dict[str, float]:
    """Least-squares star parameters of a contour, however it was represented.

    Writing ``r(theta) = c0 + c1 cos(m theta) + c2 sin(m theta)`` makes the fit
    linear, and the amplitude and rotation follow from ``c1`` and ``c2``.  This
    measures the same four numbers for a parametric star and for a neural
    field, so the two representations can be compared on one scale.
    """

    summary = _contour_shape_summary(points)
    centroid = np.asarray([summary["center_x"], summary["center_y"]])
    offsets = np.asarray(points, dtype=np.float64) - centroid[None, :]
    radii = np.linalg.norm(offsets, axis=1)
    angles = np.arctan2(offsets[:, 1], offsets[:, 0])
    design = np.column_stack(
        (
            np.ones_like(angles),
            np.cos(lobes * angles),
            np.sin(lobes * angles),
        )
    )
    coefficients, *_ = np.linalg.lstsq(design, radii, rcond=None)
    mean_radius = float(coefficients[0])
    magnitude = float(math.hypot(coefficients[1], coefficients[2]))
    return {
        "center_x": summary["center_x"],
        "center_y": summary["center_y"],
        "radius": mean_radius,
        "mean_radius": mean_radius,
        "amplitude": magnitude / max(mean_radius, np.finfo(np.float64).tiny),
        "rotation_radians": float(
            math.atan2(coefficients[2], coefficients[1]) / lobes
        ),
    }


def _build_initial_model(
    kind: str,
    *,
    hidden_features: int = DEFAULT_SIREN_HIDDEN_FEATURES,
    hidden_layers: int = DEFAULT_SIREN_HIDDEN_LAYERS,
    pretrain_steps: int = DEFAULT_SIREN_PRETRAIN_STEPS,
    pretrain_eikonal_weight: float | None = None,
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
    if kind in SIREN_INITIAL_MODELS:
        model = _build_siren_field(
            _analytic_shape_for_siren(kind), hidden_features=hidden_features,
            hidden_layers=hidden_layers, pretrain_steps=pretrain_steps,
            pretrain_eikonal_weight=pretrain_eikonal_weight,
        )
        controller = build_siren_parameter_controller(
            model, weight_bound=DEFAULT_SIREN_WEIGHT_BOUND
        )
        return model, controller
    raise ValueError(f"Unsupported initial model: {kind!r}.")


def _inverse_config_for_controller(
    controller: Any,
    *,
    max_iterations: int,
    loss_tolerance: float = 1.0e-12,
    infeasible_trial_policy: str = "error",
    max_backtracks: int = 8,
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
        elif name.startswith("network."):
            # A single SIREN weight moves the contour by 1e-5 to 2e-4 m at this
            # step, which stays above MOD's forward error floor; the smaller
            # physical-control step would leave many columns as pure noise.
            finite_difference_steps.append(1.0e-2)
            maximum_steps.append(2.5e-1)
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
        max_backtracks=max_backtracks,
        gradient_tolerance=1.0e-9,
        loss_tolerance=loss_tolerance,
        relative_step_tolerance=1.0e-9,
        max_parameters=controller.num_parameters,
        infeasible_trial_policy=infeasible_trial_policy,
    )


def _optimizer_for_solver(
    initial_model: str, solver: str, optimizer: str = "auto"
) -> str:
    """Resolve derivative routing without substituting MOD's cloud adjoint."""
    if optimizer not in OPTIMIZER_CHOICES:
        raise ValueError(f"Unsupported optimizer: {optimizer!r}.")
    if solver not in DEFAULT_SOLVERS:
        raise ValueError(f"Unsupported solver: {solver!r}.")
    supported_adjoint = initial_model in SIREN_INITIAL_MODELS and solver == "kress"
    if optimizer == "adjoint" and not supported_adjoint:
        raise ValueError(
            "--optimizer adjoint requires a siren_* initial model and "
            "--solvers kress. Use auto or parameter_fd for MOD or analytic controls."
        )
    if optimizer == "auto":
        return "adjoint" if supported_adjoint else "parameter_fd"
    return optimizer


def _optimizer_config_for_solver(
    args: argparse.Namespace, controller: Any, solver: str
) -> ImplicitMLPAdjointConfig | ParameterFDConfig:
    method = _optimizer_for_solver(args.initial_model, solver, args.optimizer)
    if method == "adjoint":
        return ImplicitMLPAdjointConfig(
            max_iterations=args.max_iterations,
            learning_rate=args.learning_rate,
            loss_tolerance=args.loss_tolerance,
            eikonal_weight=args.eikonal_weight,
            max_backtracks=args.max_backtracks,
            meaningful_boundary_step_m=args.meaningful_boundary_step_mm * 1.0e-3,
            max_candidate_evaluations=getattr(args, "max_candidate_evaluations", None),
            max_wall_seconds=getattr(args, "max_wall_seconds", None),
            eikonal_sampling=getattr(args, "eikonal_sampling", "uniform_box"),
        )
    return _inverse_config_for_controller(
        controller,
        max_iterations=args.max_iterations,
        loss_tolerance=args.loss_tolerance,
        infeasible_trial_policy=(
            "reject" if args.initial_model in SIREN_INITIAL_MODELS else "error"
        ),
        max_backtracks=(args.max_backtracks if getattr(args, "max_backtracks_was_explicit", True) else 8),
    )


def _run_inverse(
    model: Any,
    controller: Any,
    data: Any,
    geometry_config: Any,
    *,
    solver: str,
    method: str,
    config: ImplicitMLPAdjointConfig | ParameterFDConfig,
    progress_callback: Any = None,
    trial_callback: Any = None,
    optimizer_callback: Any = None,
) -> Any:
    if method == "adjoint":
        if solver != "kress":
            raise ValueError("The implicit neural adjoint requires Kress.")
        extra = {} if trial_callback is None else {"trial_callback": trial_callback}
        if optimizer_callback is not None:
            extra["optimizer_callback"] = optimizer_callback
        return run_implicit_mlp_adjoint_inverse(
            model, controller, data, geometry_config,
            config=config, progress_callback=progress_callback, **extra,
        )
    if method != "parameter_fd":
        raise ValueError(f"Unresolved optimizer method: {method!r}.")
    return run_parameter_fd_inverse(
        model, controller, data, geometry_config,
        solver=solver, config=config, progress_callback=progress_callback,
    )


def _replay_accepted_holdout(
    model: Any, controller: Any, result: Any, holdout_problem: Any,
    holdout_truth: np.ndarray, geometry_config: Any, *, solver: str,
) -> dict[str, Any]:
    """Evaluate completed accepted iterates without entering the optimizer.

    Failures belong to this evaluation report. They cannot change an inverse
    stopping decision, and the accepted final weights are restored even when
    one or more holdout predictions fail.
    """
    final_parameters = controller.parameter_vector()
    records = []
    started = perf_counter()
    forward_seconds = 0.0
    try:
        for iteration in result.iterations:
            controller.assign(iteration.parameter_vector)
            record = {"iteration": iteration.iteration, "holdout_relative_l2": None,
                      "holdout_evaluation_error": None}
            try:
                forward = predict_paired_response(model, holdout_problem, geometry_config, solver=solver)
                forward_seconds += forward.total_seconds
                _, record["holdout_relative_l2"] = _objective_metrics(forward.scattered_response, holdout_truth)
            except Exception as error:
                record["holdout_evaluation_error"] = f"{type(error).__name__}: {error}"
            records.append(record)
    finally:
        controller.assign(final_parameters)
    return {"records": records, "forward_evaluations": len(records),
            "forward_seconds": forward_seconds, "wall_seconds": perf_counter() - started,
            "failure_count": sum(record["holdout_evaluation_error"] is not None for record in records)}


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
        for artifact in resolved.glob("kress_optimizer_[0-9][0-9][0-9][0-9].pt"):
            artifact.unlink()


def _write_neural_checkpoint(
    path: Path,
    model: SirenImplicitField2D,
    *,
    initial_model: str,
    geometry_config: OrderedSDFGeometryConfig,
    optimizer: str,
    config: ImplicitMLPAdjointConfig | ParameterFDConfig,
    result: Any,
) -> None:
    """Preserve the accepted network and the constructor needed to reload it."""
    torch.save(
        {
            "schema_version": 1,
            "model_class": "sdf_inverse.models.SirenImplicitField2D",
            "state_dict": {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            },
            "constructor": {
                "bounds": DEFAULT_GEOMETRY_BOUNDS,
                "hidden_features": model.hidden_features,
                "hidden_layers": model.hidden_layers,
                "omega_0": model.omega_0,
                "random_seed": model.random_seed,
                "dtype": str(next(model.parameters()).dtype),
            },
            "initial_model": initial_model,
            "initialization": _jsonable(model.initialization_metadata()),
            "geometry_config": _jsonable(vars(geometry_config)),
            "geometry_owner": "mlp_weights",
            "optimizer": optimizer,
            "optimizer_config": _jsonable(vars(config)),
            "optimizer_diagnostics": _jsonable(_optimizer_diagnostic_summary(result)),
            "optimizer_state_dict": getattr(result, "diagnostics", {}).get("optimizer_state_dict"),
            "accepted_iteration": result.iterations[-1].iteration,
            "training_loss": result.iterations[-1].loss,
            "accepted_geometry_points": torch.as_tensor(
                np.array(result.iterations[-1].geometry_points, copy=True)
            ),
        },
        path,
    )


def _optimizer_diagnostic_summary(result):
    return {key: value for key, value in getattr(result, "diagnostics", {}).items()
            if key not in ("optimizer_records", "optimizer_state_dict")}


def _write_initial_neural_checkpoint(path, model, initial_model, geometry_config):
    """Save freshly pretrained weights before even the first geometry build."""
    torch.save({
        "schema_version": 2, "stage": "pretrained_before_geometry",
        "model_class": "sdf_inverse.models.SirenImplicitField2D",
        "state_dict": {name: value.detach().cpu().clone() for name, value in model.state_dict().items()},
        "constructor": {"bounds": DEFAULT_GEOMETRY_BOUNDS, "hidden_features": model.hidden_features,
                        "hidden_layers": model.hidden_layers, "omega_0": model.omega_0,
                        "random_seed": model.random_seed, "dtype": str(next(model.parameters()).dtype)},
        "initial_model": initial_model, "initialization": _jsonable(model.initialization_metadata()),
        "geometry_config": _jsonable(vars(geometry_config)), "geometry_owner": "mlp_weights",
    }, path)


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
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
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


def _write_trajectory(
    path: Path, result: Any, *, optimizer: str = "parameter_fd"
) -> None:
    parameter_names = tuple(result.parameter_names)
    fieldnames = [
        "iteration",
        "optimizer",
        "gradient_evaluated",
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
        "gradient_seconds",
        "line_search_seconds",
    ]
    fieldnames.extend(f"raw_{name}" for name in parameter_names)
    fieldnames.extend(f"gradient_{name}" for name in parameter_names)
    fieldnames.extend(f"step_{name}" for name in parameter_names)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for iteration in result.iterations:
            physical = iteration.physical_parameters
            if "center_x" not in physical or "radius" not in physical:
                # A neural field has no center or radius control; report the
                # same columns measured from that iterate's own contour.
                physical = _contour_shape_summary(iteration.geometry_points)
            row = {
                "iteration": iteration.iteration,
                "optimizer": optimizer,
                "gradient_evaluated": getattr(iteration, "gradient_evaluated", True),
                "loss": iteration.loss,
                "relative_l2_error": iteration.relative_l2_error,
                "center_x_m": physical["center_x"],
                "center_y_m": physical["center_y"],
                "radius_m": physical["radius"],
                "damping": iteration.damping,
                "evaluation_count": iteration.evaluation_count,
                "maximum_system_residual": iteration.maximum_system_residual,
                "iteration_seconds": iteration.timings.get("iteration_seconds"),
                "jacobian_seconds": iteration.timings.get("jacobian_seconds", 0.0),
                "gradient_seconds": iteration.timings.get("gradient_seconds"),
                "line_search_seconds": iteration.timings.get("line_search_seconds"),
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
                    for name, value in zip(
                        parameter_names,
                        iteration.gradient if iteration.gradient is not None
                        else [None] * len(parameter_names),
                    )
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
        # A neural iterate has no center or radius control, so the plotted
        # geometry comes from that iterate's own contour instead.
        summaries = [
            item.physical_parameters
            if "center_x" in item.physical_parameters
            else _contour_shape_summary(item.geometry_points)
            for item in inverse.iterations
        ]
        center_errors_mm = 1.0e3 * np.asarray(
            [
                math.hypot(
                    summary["center_x"] - target.center[0],
                    summary["center_y"] - target.center[1],
                )
                for summary in summaries
            ]
        )
        radius_errors_mm = 1.0e3 * np.abs(
            np.asarray([summary["radius"] for summary in summaries])
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
    representation_floor: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the acceptance set for one run.

    When ``representation_floor`` is supplied, shape and accuracy gates are
    relative to the same architecture and fitting procedure applied directly
    to the exact target. The historical key names a measured fitting control,
    not a theoretical lower bound on network representation error.
    """

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
        if representation_floor is None:
            for metric_key, threshold, requirement in target.shape_error_gates():
                # "final_amplitude_error" gates as "<solver>_amplitude_error".
                gate_name = metric_key.removeprefix("final_").removesuffix("_m")
                gate_name = gate_name.removesuffix("_radians")
                gates[f"{solver}_{gate_name}"] = {
                    "passed": metrics[metric_key] <= threshold,
                    "value": metrics[metric_key],
                    "requirement": requirement,
                }
        else:
            floor_boundary = float(
                representation_floor["maximum_node_to_exact_boundary_distance_m"]
            )
            final_boundary = metrics["maximum_node_to_exact_boundary_distance_m"]
            initial_boundary = metrics[
                "initial_maximum_node_to_exact_boundary_distance_m"
            ]
            gates[f"{solver}_boundary_error_within_representation"] = {
                "passed": final_boundary <= 2.0 * floor_boundary,
                "value": {"final": final_boundary, "floor": floor_boundary},
                "requirement": "<= 2x the same network fitted to the exact target",
            }
            gates[f"{solver}_boundary_error_improved"] = {
                "passed": final_boundary <= 0.25 * initial_boundary,
                "value": {"final": final_boundary, "initial": initial_boundary},
                "requirement": "<= 0.25x the initial contour error",
            }
            floor_holdout = float(
                representation_floor["holdout_relative_l2"][solver]
            )
            gates[f"{solver}_holdout_within_representation"] = {
                "passed": metrics["final_holdout_relative_l2"] <= 2.0 * floor_holdout,
                "value": {
                    "final": metrics["final_holdout_relative_l2"],
                    "floor": floor_holdout,
                },
                "requirement": "<= 2x the same network fitted to the exact target",
            }
        if representation_floor is None:
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
        if representation_floor is not None:
            # The Eikonal penalty is the neural case's only claim to a
            # distance-like field, so the warm start has to deliver one.  The
            # drift over the inverse is reported beside it, because nothing
            # re-imposes the constraint once the weights start moving.
            gates[f"{solver}_warm_start_is_eikonal"] = {
                "passed": (
                    metrics["initial_maximum_unit_gradient_deviation"] <= 2.5e-1
                ),
                "value": metrics["initial_maximum_unit_gradient_deviation"],
                "requirement": "<= 0.25",
            }
        elif not bool(metrics["initial_claims_signed_distance"]):
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
    if "kress" in solver_metrics and representation_floor is None:
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
    if initialization["kind"] == "siren_neural_implicit":
        initial_values = (
            f"{initialization['network_parameters']} trainable weights, "
            f"width {initialization['hidden_features']}, "
            f"{initialization['hidden_layers']} hidden layers"
        )
    else:
        initial_values = ", ".join(
            f"{name}={float(value):.6g}"
            for name, value in initialization["physical_parameters"].items()
        )
    optimizer_methods = {
        solver: row.get("optimizer", "parameter_fd")
        for solver, row in solver_metrics.items()
    }
    optimizer_description = "; ".join(
        f"{solver.upper()}: " + (
            "Kress discrete adjoint → branch-local extraction/Method-B reverse "
            "→ Adam weight update"
            if method == "adjoint"
            else "bounded parameter finite differences → damped Gauss–Newton"
        )
        for solver, method in optimizer_methods.items()
    )
    comparison_description = (
        "The optimizer policy is shared across solvers."
        if len(set(optimizer_methods.values())) == 1 and len(solver_metrics) > 1
        else "The solver branches use different optimizer policies; their timings "
        "compare complete pipelines."
        if len(solver_metrics) > 1
        else "One solver branch is evaluated."
    )
    lines = [
        "# Implicit-field Method-B inverse comparison",
        "",
        (
            f"A `{initialization['kind']}` field initialized with `{initial_values}` "
            + target.summary_sentence()
        ),
        "",
        (
            "Every candidate is evaluated from its own implicit field after "
            "extraction and Method-B conversion. "
            + optimizer_description + ". " + comparison_description
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
                "The accepted geometry belongs to the implicit model. Neural updates "
                "propagate discrete Kress geometry sensitivities into network weights "
                "through a differentiable, branch-local extraction and Method-B "
                "conversion. Topology changes and interpolation branch switches are "
                "not differentiated. Every candidate is re-extracted and evaluated "
                "before acceptance. Parameter finite differences remain explicit "
                "reference controls. These results concern smooth, topology-valid "
                "single-component fields at the recorded conversion resolution."
            ),
        ]
    )
    model_artifacts = [
        f"[{row['model_checkpoint']}]({row['model_checkpoint']})"
        for row in solver_metrics.values() if row.get("model_checkpoint")
    ]
    if model_artifacts:
        lines.extend([
            "", "Accepted neural weights, architecture and run metadata: "
            + ", ".join(model_artifacts) + ".",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(
    argv: Sequence[str] | None = None, *, implicit_defaults: bool = False
) -> int:
    args = _parse_args(argv, implicit_defaults=implicit_defaults)
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = REPOSITORY_ROOT / output_dir
    _prepare_output_directory(output_dir, overwrite=args.overwrite)

    try:
        return _execute_comparison(args, argv, output_dir)
    except Exception as error:
        import traceback
        (output_dir / "failure_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        stage_path = output_dir / "execution_stage.json"
        stage = json.loads(stage_path.read_text()) if stage_path.exists() else {}
        stage.update(status="failed", error=f"{type(error).__name__}: {error}")
        stage_path.write_text(json.dumps(stage, indent=2) + "\n", encoding="utf-8")
        raise


def _execute_comparison(args, argv, output_dir):
    def stage(name):
        (output_dir / "execution_stage.json").write_text(
            json.dumps({"stage": name, "status": "running"}, indent=2) + "\n", encoding="utf-8")

    stage("observation_oracle")

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
    # A no-op unless --bandwidth/--grid-resolution/--projected-samples was given:
    # each defaults to the target's own value during argument parsing.
    geometry_config = replace(
        geometry_config,
        bandwidth=args.bandwidth,
        grid_shape=(args.grid_resolution, args.grid_resolution),
        projected_samples=args.projected_samples,
    )
    if args.initial_model in SIREN_INITIAL_MODELS:
        geometry_config = replace(
            geometry_config, conversion_tolerance_m=args.conversion_tolerance_mm * 1.0e-3,
        )
    neural_factory_options = {
        "hidden_features": args.mlp_hidden_features,
        "hidden_layers": args.mlp_hidden_layers,
        "pretrain_steps": args.mlp_pretrain_steps,
        "pretrain_eikonal_weight": args.mlp_pretrain_eikonal_weight,
    }
    stage("initial_pretraining")
    template_model, template_controller = (None, None) if args.start_at_truth else _build_initial_model(
        args.initial_model, **neural_factory_options
    )
    if template_model is not None and args.initial_model in SIREN_INITIAL_MODELS:
        _write_initial_neural_checkpoint(output_dir / "initial_model.pt", template_model, args.initial_model, geometry_config)

    # Measure the same fitting procedure on the known target. This is a
    # representation control, not an intrinsic capacity floor of the network.
    representation_control_model: torch.nn.Module | None = None
    representation_floor: dict[str, Any] | None = None
    if args.initial_model in SIREN_INITIAL_MODELS:
        stage("target_control_pretraining")
        print(
            "[control] warm starting the same network onto the exact target",
            flush=True,
        )
        representation_control_model = _build_siren_field(
            target.exact_model(), **neural_factory_options
        )
        _write_initial_neural_checkpoint(output_dir / "target_control_initial_model.pt", representation_control_model, args.initial_model, geometry_config)
        stage("target_control_geometry")
        control_geometry = build_ordered_sdf_geometry(
            representation_control_model, geometry_config
        )
        control_distances = target.boundary_distances(
            np.asarray(control_geometry.curve.points)
        )
        representation_floor = {
            "network": representation_control_model.initialization_metadata(),
            "mean_node_to_exact_boundary_distance_m": float(
                np.mean(control_distances)
            ),
            "maximum_node_to_exact_boundary_distance_m": float(
                np.max(control_distances)
            ),
            "holdout_relative_l2": {},
            "all_frequency_relative_l2": {},
        }
        print(
            "[control] the same network fitted to the exact target lands "
            f"{representation_floor['maximum_node_to_exact_boundary_distance_m']:.3e} m "
            "from it",
            flush=True,
        )
        if args.start_at_truth:
            template_model = copy.deepcopy(representation_control_model)
            template_controller = build_siren_parameter_controller(template_model)
    optimizer_methods = {
        solver: _optimizer_for_solver(args.initial_model, solver, args.optimizer)
        for solver in args.solvers
    }
    inverse_configs = {
        solver: _optimizer_config_for_solver(args, template_controller, solver)
        for solver in args.solvers
    }
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
    initialization_metadata["inverse_initialization"] = (
        "exact_target_fitting_control" if args.start_at_truth else "wrong_shape_initialization"
    )
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
        optimizer_method = optimizer_methods[solver]
        print(
            f"\n[{solver.upper()}] {args.initial_model} implicit recovery "
            f"with {optimizer_method}",
            flush=True,
        )
        if args.start_at_truth:
            model = copy.deepcopy(representation_control_model)
            controller = build_siren_parameter_controller(model)
        else:
            model, controller = _build_initial_model(
                args.initial_model, **neural_factory_options
            )
        if controller.names != template_controller.names or not np.array_equal(
            controller.parameter_vector(), initial_raw_parameters
        ):
            raise RuntimeError("Initial model factory is not deterministic across solvers.")

        stage(f"{solver}_initial_geometry_forward")
        initial_all = predict_paired_response(
            model, all_problem, geometry_config, solver=solver
        )
        stage(f"{solver}_exact_target_forward")
        target_model = target.exact_model()
        target_geometry_forward = predict_paired_response(
            target_model, all_problem, geometry_config, solver=solver
        )
        stage(f"{solver}_representation_control_forward")
        representation_forward = (
            None
            if representation_control_model is None
            else predict_paired_response(
                representation_control_model,
                all_problem,
                geometry_config,
                solver=solver,
            )
        )

        accepted_diagnostics = []
        holdout_evaluations = 0
        holdout_seconds = 0.0
        holdout_wall_seconds = 0.0
        holdout_failures = 0
        holdout_problem = _build_problem(args.holdout_ghz, source_points, receiver_points)

        def progress(iteration: Any, *, _solver: str = solver) -> None:
            physical = iteration.physical_parameters
            if "center_x" not in physical or "radius" not in physical:
                physical = _contour_shape_summary(iteration.geometry_points)
            print(
                f"  {_solver.upper()} iter={iteration.iteration:02d} "
                f"loss={iteration.loss:.4e} rel={iteration.relative_l2_error:.4e} "
                f"center=({physical['center_x']:.6f},{physical['center_y']:.6f}) "
                f"radius={physical['radius']:.6f}",
                flush=True,
            )
            if optimizer_method == "adjoint":
                fitted = (_fit_radial_star_parameters(iteration.geometry_points, lobes=target.shape.lobes)
                          if isinstance(target, StarTarget) else physical)
                accepted_diagnostics.append({
                    "iteration": iteration.iteration, "loss": iteration.loss,
                    "relative_l2_error": iteration.relative_l2_error,
                    "objective": iteration.objective, "eikonal_loss": iteration.eikonal_loss,
                    "fitted_shape": fitted,
                    "maximum_node_to_exact_boundary_distance_m": float(np.max(target.boundary_distances(iteration.geometry_points))),
                    "holdout_relative_l2": None,
                    "holdout_frequencies_ghz": args.holdout_ghz,
                    "conversion_error_m": iteration.conversion_error_m,
                    "conversion_refinement_change_m": iteration.conversion_refinement_change_m,
                    "boundary_movement_m": iteration.boundary_movement_m,
                    "meaningful_boundary_step": iteration.meaningful_boundary_step,
                    "data_gradient_norm": iteration.data_gradient_norm,
                    "weighted_eikonal_gradient_norm": iteration.weighted_eikonal_gradient_norm,
                    "eikonal_gradient_norm": iteration.eikonal_gradient_norm,
                    "sample_set_hash": iteration.sample_set_hash,
                    "acceptance_objective_on_previous_samples": iteration.acceptance_objective,
                    "evaluation_count": iteration.evaluation_count,
                    "backtracks": iteration.backtracks, "step_method": iteration.step_method,
                })
                (output_dir / f"{solver}_accepted_iterates.json").write_text(
                    json.dumps(_jsonable(accepted_diagnostics), indent=2) + "\n", encoding="utf-8")

        def trial_progress(trial):
            with (output_dir / f"{solver}_trials.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(_jsonable(trial)) + "\n")

        def optimizer_progress(record):
            torch.save(record, output_dir / f"{solver}_optimizer_{record['iteration']:04d}.pt")

        stage(f"{solver}_inverse")
        inverse_result = _run_inverse(
            model,
            controller,
            training_data,
            geometry_config,
            solver=solver,
            method=optimizer_method,
            config=inverse_configs[solver],
            progress_callback=progress,
            trial_callback=trial_progress if optimizer_method == "adjoint" else None,
            optimizer_callback=optimizer_progress if optimizer_method == "adjoint" else None,
        )
        # Save the accepted result before any optional holdout replay. Neither
        # evaluation failures nor its elapsed time can alter the inverse.
        if args.initial_model in SIREN_INITIAL_MODELS:
            _write_neural_checkpoint(
                output_dir / f"{solver}_model.pt", model,
                initial_model=args.initial_model, geometry_config=geometry_config,
                optimizer=optimizer_method, config=inverse_configs[solver], result=inverse_result)
        stage(f"{solver}_post_optimization_evaluation")
        if args.record_accepted_holdout or args.start_at_truth:
            replay = _replay_accepted_holdout(
                model, controller, inverse_result, holdout_problem,
                all_truth[:, len(args.train_ghz):], geometry_config, solver=solver)
            holdout_evaluations, holdout_seconds = replay["forward_evaluations"], replay["forward_seconds"]
            holdout_wall_seconds, holdout_failures = replay["wall_seconds"], replay["failure_count"]
            by_iteration = {record["iteration"]: record for record in replay["records"]}
            for record in accepted_diagnostics:
                record.update(by_iteration[record["iteration"]])
            (output_dir / f"{solver}_accepted_iterates.json").write_text(
                json.dumps(_jsonable(accepted_diagnostics), indent=2) + "\n", encoding="utf-8")
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
        representation_floor_metrics: dict[str, float] = {}
        if representation_forward is not None and representation_floor is not None:
            _, floor_all_relative = _objective_metrics(
                representation_forward.scattered_response, all_truth
            )
            _, floor_holdout_relative = _objective_metrics(
                representation_forward.scattered_response[:, holdout_columns],
                all_truth[:, holdout_columns],
            )
            representation_floor["holdout_relative_l2"][solver] = floor_holdout_relative
            representation_floor["all_frequency_relative_l2"][solver] = floor_all_relative
            representation_floor_metrics = {
                "representation_floor_holdout_relative_l2": floor_holdout_relative,
                "representation_floor_all_frequency_relative_l2": floor_all_relative,
                "representation_floor_maximum_node_to_exact_boundary_distance_m": (
                    representation_floor[
                        "maximum_node_to_exact_boundary_distance_m"
                    ]
                ),
            }
        final_physical = controller.physical_parameter_dict()
        shape_errors = target.shape_errors(
            final_physical, final_all.geometry_build.curve.points
        )
        losses = np.asarray([item.loss for item in inverse_result.iterations])
        initial_curve_metrics = target.curve_distance_metrics(
            initial_all.geometry_build.curve.points
        )
        curve_metrics = target.curve_distance_metrics(
            final_all.geometry_build.curve.points
        )
        initial_summary = (
            initial_physical_parameters
            if "center_x" in initial_physical_parameters
            else _contour_shape_summary(initial_all.geometry_build.curve.points)
        )
        initial_center = (
            float(initial_summary["center_x"]),
            float(initial_summary["center_y"]),
        )
        initial_gradient_metrics = _field_gradient_metrics(
            model=template_model,
            points=initial_all.geometry_build.curve.points,
        )
        final_gradient_metrics = _field_gradient_metrics(
            model=model,
            points=final_all.geometry_build.curve.points,
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
            "optimizer": optimizer_method,
            "optimizer_config": _jsonable(vars(inverse_configs[solver])),
            "optimizer_diagnostics": _jsonable(
                _optimizer_diagnostic_summary(inverse_result)
            ),
            "accepted_iterate_diagnostics": accepted_diagnostics,
            "evaluation_only_holdout_forward_evaluations": holdout_evaluations,
            "evaluation_only_holdout_forward_seconds": holdout_seconds,
            "evaluation_only_holdout_wall_seconds": holdout_wall_seconds,
            "evaluation_only_holdout_failures": holdout_failures,
            "accepted_holdout_policy": "post_optimization_replay; errors reported per iterate; final accepted weights restored",
            "geometry_owner": "implicit_model_parameters",
            "neural_update": (
                "kress_boundary_adjoint_to_sdf_weights"
                if optimizer_method == "adjoint"
                else "parameter_finite_difference_gauss_newton"
            ),
            "model_checkpoint": (
                f"{solver}_model.pt" if args.initial_model in SIREN_INITIAL_MODELS
                else None
            ),
            "final_regularized_objective": getattr(
                inverse_result.iterations[-1], "objective", None
            ),
            "final_eikonal_loss": getattr(
                inverse_result.iterations[-1], "eikonal_loss", None
            ),
            "final_conversion_error_m": final_all.geometry_build.maximum_conversion_error_m,
            "final_conversion_refinement_change_m": final_all.geometry_build.conversion_refinement_change_m,
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
            "shape_measurement_source": target.shape_measurement_source(
                final_physical
            ),
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
            "infeasible_trials": inverse_result.infeasible_trial_count,
            "maximum_frozen_jacobian_columns": (
                inverse_result.maximum_frozen_jacobian_columns
            ),
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
            **representation_floor_metrics,
            # Measure field regularity separately from geometry/data accuracy;
            # only the adjoint optimizer includes inverse Eikonal regularization.
            "final_maximum_unit_gradient_deviation": (
                final_gradient_metrics["maximum_unit_gradient_deviation"]
            ),
            "final_minimum_field_gradient_norm": (
                final_gradient_metrics["minimum_field_gradient_norm"]
            ),
            "final_maximum_field_gradient_norm": (
                final_gradient_metrics["maximum_field_gradient_norm"]
            ),
        }
        solver_results[solver] = {
            "inverse_result": inverse_result,
            "initial_forward": initial_all,
            "final_forward": final_all,
            "target_geometry_forward": target_geometry_forward,
        }
        serializable_solver_metrics[solver] = metrics
        _write_trajectory(
            output_dir / f"{solver}_trajectory.csv", inverse_result,
            optimizer=optimizer_method,
        )
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

    gates = _acceptance_gates(
        serializable_solver_metrics,
        target=target,
        representation_floor=representation_floor,
    )
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
            "same_optimizer": len(set(optimizer_methods.values())) == 1,
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
        "schema_version": 2,
        "benchmark": target.benchmark(args.initial_model),
        "truth_oracle": target.truth_oracle,
        "train_frequencies_ghz": tuple(args.train_ghz),
        "holdout_frequencies_ghz": tuple(args.holdout_ghz),
        "target_shape": target.name,
        "target": target.parameter_dict(),
        "observation_oracle_diagnostics": oracle_diagnostics,
        "representation_floor": representation_floor,
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
            "optimizer_request": args.optimizer,
            "optimizer_by_solver": optimizer_methods,
            "inverse_configs_by_solver": {
                solver: _jsonable(vars(config))
                for solver, config in inverse_configs.items()
            },
            "controlled_parameters": template_controller.names,
            "forward_difference": "Solver dispatch: MOD vs Kress",
            "comparison_scope": (
                "Single solver pipeline"
                if len(optimizer_methods) == 1
                else "Matched optimizer; different forward solvers"
                if len(set(optimizer_methods.values())) == 1
                else "Different forward solvers and optimizer methods; see optimizer_by_solver"
            ),
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
    (output_dir / "execution_stage.json").write_text(
        json.dumps({"stage": "complete", "status": "complete", "scientific_acceptance": acceptance_passed}) + "\n")
    return 0 if acceptance_passed or args.no_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
