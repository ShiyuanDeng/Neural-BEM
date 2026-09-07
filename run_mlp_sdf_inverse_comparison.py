#!/usr/bin/env python3
"""Compare MOD and Kress in a curve-state inverse with an MLP-SDF representation.

Unlike the low-dimensional analytic-family baseline, the learned implicit
representation is a generic coordinate MLP.  The accepted optimization state
is an ordered curve: finite differences perturb and solve that curve directly,
then each accepted state is re-distanced into all MLP weights and the extracted
zero set is audited.  The star-shaped benchmark uses a gauge-fixed radial
Fourier state so repeated local updates cannot manufacture modes outside the
declared search band.  Cumulative low-to-high-frequency continuation is the
default because the joint high-frequency objective has a measured wrong-shape
basin from the ellipse start; joint full-band and progressive-mode runs remain
available as explicit ablations.
"""

from __future__ import annotations

import argparse
import copy
import csv
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from typing import Any, Sequence


for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

REPOSITORY_ROOT = Path(__file__).resolve().parent
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"
for _root in (REPOSITORY_ROOT, SOLVERS_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from run_sdf_inverse_comparison import (  # noqa: E402
    DEFAULT_INITIAL_CENTER,
    DEFAULT_INITIAL_RADIUS,
    DEFAULT_STAR_INITIAL_AMPLITUDE,
    DEFAULT_STAR_INITIAL_CENTER,
    DEFAULT_STAR_INITIAL_MEAN_RADIUS,
    DEFAULT_STAR_INITIAL_ROTATION,
    InverseTarget,
    _build_problem,
    _build_target,
    _comma_separated_floats,
    _objective_metrics,
    _ring_scan,
)
from sdf_inverse import (  # noqa: E402
    AlternatingNeuralInverseConfig,
    CircleSDF2D,
    ComplexScatteredData,
    EllipseLevelSet2D,
    NeuralRedistanceConfig,
    PairedForwardProblem,
    SmoothMLPSDF2D,
    StarLevelSet2D,
    build_ordered_sdf_geometry,
    fit_radial_fourier_curve_state,
    maximum_curve_set_distance,
    predict_paired_curve_response,
    radial_spectral_tail_rms,
    radial_fourier_state_curve,
    redistance_neural_sdf_to_curve,
    resolvable_maximum_mode,
    run_alternating_neural_inverse,
)
import config.star_config as star_config  # noqa: E402


GENERATED_NAMES = (
    "metrics.json",
    "summary.md",
    "convergence.png",
    "contour_evolution.mp4",
    "contour_evolution.gif",
    "mod_trajectory.csv",
    "kress_trajectory.csv",
    "mod_responses.npz",
    "kress_responses.npz",
    "mod_model.pt",
    "kress_model.pt",
)
CONTINUATION_PROGRESSIVE_MODES = "full_band_progressive_modes"
CONTINUATION_CUMULATIVE_FREQUENCIES = "cumulative_low_to_high"
CONTINUATION_NONE = "none"
CONTINUATION_STRATEGIES = (
    CONTINUATION_PROGRESSIVE_MODES,
    CONTINUATION_CUMULATIVE_FREQUENCIES,
    CONTINUATION_NONE,
)
TRAJECTORY_FIELDNAMES = (
    "iteration",
    "stage",
    "stage_iteration",
    "stage_train_frequencies_ghz",
    "stage_maximum_mode",
    "modal_step_m",
    "loss",
    "relative_l2_error",
    "applied_damping",
    "accepted_backtrack_count",
    "maximum_modal_field_update_m",
    "curve_change_m",
    "redistance_curve_drift_m",
    "eikonal_rms",
    "eikonal_maximum_deviation",
    "maximum_curve_field_residual",
    "trust_region_predicted_relative_change",
    "accepted_step_predicted_relative_change",
    "arclength_refit_rms_m",
    "arclength_refit_maximum_m",
    "arclength_speed_ratio_before",
    "arclength_speed_ratio_after",
    "radial_spectral_tail_rms_m",
    "radial_spectral_tail_limit_m",
    "spectral_tail_rejection_count",
    "redistance_steps",
    "redistance_stop_reason",
    "evaluation_count",
    "maximum_system_residual",
)


@dataclass(frozen=True)
class FrequencyContinuationStage:
    """One continuation objective and its nominal accepted-update budget."""

    stage: int
    train_frequencies_ghz: tuple[float, ...]
    max_iterations: int


@dataclass(frozen=True)
class _TrajectoryEntry:
    """An accepted state plus the continuation objective that produced it."""

    iteration: Any
    stage: int
    stage_iteration: int
    train_frequencies_ghz: tuple[float, ...]
    maximum_mode: int


@dataclass(frozen=True)
class _FrequencyContinuationResult:
    """Driver-level aggregation of optimizer invocations over continuation stages."""

    solver: str
    entries: tuple[_TrajectoryEntry, ...]
    stage_results: tuple[Any, ...]
    stage_metadata: tuple[dict[str, Any], ...]
    final_curve: Any
    final_representation_curve: Any

    @property
    def iterations(self) -> tuple[Any, ...]:
        return tuple(entry.iteration for entry in self.entries)

    @property
    def initial_iteration(self) -> Any:
        return self.entries[0].iteration

    @property
    def final_iteration(self) -> Any:
        return self.entries[-1].iteration

    @property
    def converged(self) -> bool:
        return bool(self.stage_results[-1].converged)

    @property
    def stop_reason(self) -> str:
        return str(self.stage_results[-1].stop_reason)

    @property
    def total_evaluation_count(self) -> int:
        return sum(int(result.total_evaluation_count) for result in self.stage_results)

    @property
    def infeasible_evaluation_count(self) -> int:
        return sum(int(result.infeasible_evaluation_count) for result in self.stage_results)

    @property
    def spectral_tail_rejection_count(self) -> int:
        return sum(
            int(result.spectral_tail_rejection_count) for result in self.stage_results
        )

    @property
    def maximum_system_residual(self) -> float:
        return max(float(result.maximum_system_residual) for result in self.stage_results)

    @property
    def total_forward_seconds(self) -> float:
        return sum(float(result.total_forward_seconds) for result in self.stage_results)

    @property
    def total_redistance_seconds(self) -> float:
        return sum(float(result.total_redistance_seconds) for result in self.stage_results)

    @property
    def total_bem_seconds(self) -> float:
        return sum(float(result.total_bem_seconds) for result in self.stage_results)

    @property
    def total_curve_update_seconds(self) -> float:
        return sum(
            float(result.total_curve_update_seconds) for result in self.stage_results
        )

    @property
    def redistance_attempt_count(self) -> int:
        return sum(int(result.redistance_attempt_count) for result in self.stage_results)

    @property
    def total_redistance_step_count(self) -> int:
        return sum(
            int(result.total_redistance_step_count) for result in self.stage_results
        )

    @property
    def full_validation_rejection_count(self) -> int:
        return sum(
            int(result.full_validation_rejection_count)
            for result in self.stage_results
        )

    @property
    def redistance_failure_count(self) -> int:
        return sum(
            int(result.redistance_failure_count) for result in self.stage_results
        )

    @property
    def representation_extraction_failure_count(self) -> int:
        return sum(
            int(result.representation_extraction_failure_count)
            for result in self.stage_results
        )

    @property
    def representation_drift_rejection_count(self) -> int:
        return sum(
            int(result.representation_drift_rejection_count)
            for result in self.stage_results
        )

    @property
    def total_geometry_audit_seconds(self) -> float:
        return sum(
            float(result.total_geometry_audit_seconds) for result in self.stage_results
        )

    @property
    def total_seconds(self) -> float:
        return sum(float(result.total_seconds) for result in self.stage_results)


def _frequency_continuation_plan(
    train_frequencies_ghz: Sequence[float],
    total_iterations: int,
    *,
    enabled: bool | None = None,
    strategy: str | None = None,
    stage_count: int | None = None,
) -> tuple[FrequencyContinuationStage, ...]:
    """Allocate the accepted-update budget over continuation objectives.

    For compatibility, this standalone helper defaults to one joint stage
    containing the full sorted training band; the CLI driver passes its
    cumulative-frequency default explicitly.
    ``enabled`` is kept as a compatibility seam for callers of the original
    helper: true selects cumulative low-to-high frequency prefixes and false
    selects one joint stage.  New callers should pass ``strategy`` explicitly
    when selecting an experimental continuation schedule.

    For cumulative-frequency continuation the final stage receives ``2 N``
    times each warm-stage weight, where ``N`` is the number of stages (thus
    ``1:1:6`` for three frequencies).  Progressive-mode continuation retains
    its historical ``1:1:2`` weighting.  These allocations are warm-stage
    caps; unused warm-stage accepted updates are transferred to the final
    stage by :func:`_effective_stage_budget`.
    """

    frequencies = tuple(sorted(float(value) for value in train_frequencies_ghz))
    if not frequencies:
        raise ValueError("train_frequencies_ghz must not be empty.")
    if len(set(frequencies)) != len(frequencies):
        raise ValueError("train_frequencies_ghz must not contain duplicates.")
    if not all(math.isfinite(value) and value > 0.0 for value in frequencies):
        raise ValueError("train frequencies must be finite and positive.")
    if isinstance(total_iterations, bool) or int(total_iterations) != total_iterations:
        raise TypeError("total_iterations must be an integer.")
    budget = int(total_iterations)
    if budget < 1:
        raise ValueError("total_iterations must be positive.")

    if enabled is not None:
        if strategy is not None:
            raise ValueError("enabled and strategy cannot both be supplied.")
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be bool when supplied.")
        strategy = (
            CONTINUATION_CUMULATIVE_FREQUENCIES
            if enabled
            else CONTINUATION_NONE
        )
    elif strategy is None:
        strategy = CONTINUATION_NONE
    if strategy not in CONTINUATION_STRATEGIES:
        raise ValueError(
            "strategy must be one of " + ", ".join(CONTINUATION_STRATEGIES) + "."
        )

    if strategy == CONTINUATION_CUMULATIVE_FREQUENCIES:
        objectives = tuple(
            tuple(frequencies[: index + 1]) for index in range(len(frequencies))
        )
    elif strategy == CONTINUATION_NONE:
        objectives = (frequencies,)
    else:
        if stage_count is None:
            # Preserve a convenient standalone-helper default.  Production
            # passes the stage count implied by the resolved maximum mode.
            count = len(frequencies)
        else:
            if isinstance(stage_count, bool) or int(stage_count) != stage_count:
                raise TypeError("stage_count must be an integer.")
            count = int(stage_count)
        if count < 1:
            raise ValueError("stage_count must be positive.")
        objectives = (frequencies,) * count

    if budget < len(objectives):
        raise ValueError(
            "total_iterations must be at least the number of continuation stages "
            f"({len(objectives)})."
        )

    # Frequency prefixes are homotopy warm starts, not independent inverse
    # problems to over-solve.  Give the final joint objective most of the
    # accepted-update budget (for three frequencies the weights are 1:1:6).
    # Progressive-mode stages share one objective, so retain their less
    # aggressive historical 1:1:2 split.
    if len(objectives) == 1:
        weights = (1,)
    elif strategy == CONTINUATION_CUMULATIVE_FREQUENCIES:
        weights = (1,) * (len(objectives) - 1) + (2 * len(objectives),)
    else:
        weights = (1,) * (len(objectives) - 1) + (2,)
    remaining = budget - len(objectives)
    denominator = sum(weights)
    fractional = [remaining * weight / denominator for weight in weights]
    extras = [int(math.floor(value)) for value in fractional]
    unassigned = remaining - sum(extras)
    order = sorted(
        range(len(weights)),
        key=lambda index: (fractional[index] - extras[index], index),
        reverse=True,
    )
    for index in order[:unassigned]:
        extras[index] += 1
    allocations = tuple(1 + value for value in extras)
    return tuple(
        FrequencyContinuationStage(
            stage=index + 1,
            train_frequencies_ghz=stage_frequencies,
            max_iterations=allocations[index],
        )
        for index, stage_frequencies in enumerate(objectives)
    )


def _continuation_metrics_summary(
    strategy: str,
    stages: Sequence[FrequencyContinuationStage],
    total_outer_iteration_budget: int,
) -> dict[str, Any]:
    """Describe a schedule without changing the legacy frequency flag's meaning."""

    if strategy not in CONTINUATION_STRATEGIES:
        raise ValueError(
            "strategy must be one of " + ", ".join(CONTINUATION_STRATEGIES) + "."
        )
    if not stages:
        raise ValueError("stages must not be empty.")
    continuation_enabled = len(stages) > 1
    frequency_staging_enabled = (
        strategy == CONTINUATION_CUMULATIVE_FREQUENCIES
        and continuation_enabled
    )
    return {
        # ``enabled`` predates modal continuation and therefore remains a
        # frequency-staging flag for compatibility with existing readers.
        "enabled": frequency_staging_enabled,
        "continuation_enabled": continuation_enabled,
        "frequency_staging_enabled": frequency_staging_enabled,
        "strategy": strategy,
        "total_outer_iteration_budget": total_outer_iteration_budget,
        "budget_unit": "accepted_updates",
        "budget_weights": (
            [1]
            if len(stages) == 1
            else [
                *([1] * (len(stages) - 1)),
                (
                    2 * len(stages)
                    if strategy == CONTINUATION_CUMULATIVE_FREQUENCIES
                    else 2
                ),
            ]
        ),
        "unused_warm_stage_budget_policy": "carry_to_final_stage",
        "damping_policy": "reset_to_configured_initial_at_every_stage",
        "stages": [asdict(stage) for stage in stages],
        "stage_losses_are_objective_local": (
            strategy == CONTINUATION_CUMULATIVE_FREQUENCIES
        ),
    }


def _progressive_mode_stage_count(final_maximum_mode: int) -> int:
    """Return the number of distinct ``1, 3, ..., K`` modal stages."""

    if isinstance(final_maximum_mode, bool) or int(final_maximum_mode) != final_maximum_mode:
        raise TypeError("final_maximum_mode must be an integer.")
    maximum_mode = int(final_maximum_mode)
    if maximum_mode < 1:
        raise ValueError("final_maximum_mode must be positive.")
    return maximum_mode // 2 + 1


def _effective_stage_budget(
    *,
    stage: int,
    stage_count: int,
    planned_max_iterations: int,
    total_iterations: int,
    accepted_updates_before_stage: int,
) -> int:
    """Transfer all unused warm-stage accepted-update capacity to the final stage."""

    values = {
        "stage": stage,
        "stage_count": stage_count,
        "planned_max_iterations": planned_max_iterations,
        "total_iterations": total_iterations,
        "accepted_updates_before_stage": accepted_updates_before_stage,
    }
    if any(isinstance(value, bool) or int(value) != value for value in values.values()):
        raise TypeError("stage budget controls must be integers.")
    values = {name: int(value) for name, value in values.items()}
    if values["stage_count"] < 1 or not 1 <= values["stage"] <= values["stage_count"]:
        raise ValueError("stage must lie in 1..stage_count.")
    if values["planned_max_iterations"] < 1 or values["total_iterations"] < 1:
        raise ValueError("iteration budgets must be positive.")
    if not 0 <= values["accepted_updates_before_stage"] < values["total_iterations"]:
        raise ValueError(
            "accepted_updates_before_stage must lie below total_iterations."
        )
    remaining = (
        values["total_iterations"] - values["accepted_updates_before_stage"]
    )
    if values["stage"] == values["stage_count"]:
        return remaining
    return min(values["planned_max_iterations"], remaining)


def _continuation_stage_maximum_mode(
    stage: int,
    stage_count: int,
    *,
    final_maximum_mode: int,
    automatic_maximum_mode: int,
    strategy: str = CONTINUATION_PROGRESSIVE_MODES,
) -> int:
    """Resolve the active geometry band for one continuation stage.

    Progressive-mode continuation deliberately follows ``1, 3, ..., K``.
    Frequency continuation instead uses every mode that the active wave band
    can resolve.  Conflating those policies previously restricted the first
    0.5 GHz stage to K=1 even though its wave budget was K=3, so an ellipse
    start could not reduce its dominant K=2 error before higher-frequency
    local minima entered the objective.
    """

    values = {
        "stage": stage,
        "stage_count": stage_count,
        "final_maximum_mode": final_maximum_mode,
        "automatic_maximum_mode": automatic_maximum_mode,
    }
    if any(isinstance(value, bool) or int(value) != value for value in values.values()):
        raise TypeError("continuation mode controls must be integers.")
    values = {name: int(value) for name, value in values.items()}
    if values["stage_count"] < 1 or not 1 <= values["stage"] <= values["stage_count"]:
        raise ValueError("stage must lie in 1..stage_count.")
    if values["final_maximum_mode"] < 1 or values["automatic_maximum_mode"] < 1:
        raise ValueError("maximum modes must be positive.")
    if strategy not in CONTINUATION_STRATEGIES:
        raise ValueError(
            "strategy must be one of " + ", ".join(CONTINUATION_STRATEGIES) + "."
        )
    if strategy == CONTINUATION_NONE:
        return values["final_maximum_mode"]
    if strategy == CONTINUATION_CUMULATIVE_FREQUENCIES:
        return min(
            values["final_maximum_mode"],
            values["automatic_maximum_mode"],
        )
    if values["stage"] == values["stage_count"]:
        return values["final_maximum_mode"]
    return min(
        values["final_maximum_mode"],
        values["automatic_maximum_mode"],
        2 * values["stage"] - 1,
    )


def _stage_inverse_config(
    base_config: AlternatingNeuralInverseConfig,
    *,
    redistance_config: NeuralRedistanceConfig,
    max_iterations: int,
    maximum_mode: int,
    spectral_tail_reference_rms_m: float,
    audit_seed: int,
) -> AlternatingNeuralInverseConfig:
    """Build an independent stage configuration with freshly reset LM damping."""

    return replace(
        base_config,
        redistance=redistance_config,
        max_iterations=max_iterations,
        maximum_mode=maximum_mode,
        spectral_tail_reference_rms_m=spectral_tail_reference_rms_m,
        # A prior stage's damping scales different normal equations.  Always
        # restart from the configured value when the objective or basis moves.
        initial_damping=base_config.initial_damping,
        audit_seed=audit_seed,
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("circle", "star"), default="star")
    parser.add_argument("--solvers", nargs="+", choices=("mod", "kress"), default=("kress", "mod"))
    parser.add_argument(
        "--initial-shape",
        choices=("circle", "ellipse", "star"),
        default=None,
        help="Topology-valid wrong contour used to initialize the randomly seeded MLP.",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--train-ghz", type=_comma_separated_floats, default=None)
    parser.add_argument("--holdout-ghz", type=_comma_separated_floats, default=None)
    parser.add_argument("--num-pairs", type=int, default=12)
    parser.add_argument("--num-nodes", type=int, default=None)
    parser.add_argument(
        "--outer-iterations",
        type=int,
        default=60,
        help=(
            "Maximum accepted modal/redistance cycles. The former six-cycle "
            "default was shorter than the trust-region travel needed by the "
            "supplied wrong-shape initializations."
        ),
    )
    parser.add_argument(
        "--maximum-mode",
        type=int,
        default=None,
        help=(
            "Highest angular mode in the update basis. Defaults to the smaller "
            "of the training-band wave limit and paired-scan angular Nyquist "
            "limit; a larger value is allowed but reported."
        ),
    )
    parser.add_argument(
        "--maximum-modal-update-mm",
        type=float,
        default=2.0,
        help=(
            "Trust-region cap on the largest Cartesian boundary displacement "
            "proposed by one coefficient update. The 2 mm default avoids the "
            "repeated 4 mm saturation "
            "observed in the ellipse-to-star calibration."
        ),
    )
    parser.add_argument("--hidden-features", type=int, default=64)
    parser.add_argument("--hidden-layers", type=int, default=2)
    parser.add_argument("--mlp-seed", type=int, default=23)
    parser.add_argument("--redistance-steps", type=int, default=1200)
    parser.add_argument("--redistance-samples", type=int, default=2048)
    parser.add_argument(
        "--redistance-boundary-tolerance-mm",
        type=float,
        default=0.5,
        help="Maximum frozen-curve field residual allowed after MLP re-distancing.",
    )
    parser.add_argument(
        "--maximum-redistance-drift-mm",
        type=float,
        default=1.5,
        help=(
            "Safety cap on the largest local MLP zero-contour discrepancy after "
            "re-distancing. The canonical curve remains authoritative; the "
            "stricter geometry convergence tolerance is checked separately."
        ),
    )
    parser.add_argument(
        "--geometry-convergence-tolerance-mm",
        type=float,
        default=0.2,
        help=(
            "Stationarity scale for accepted contour motion. The default "
            "matches the finite-difference/projection resolution."
        ),
    )
    parser.add_argument(
        "--maximum-spectral-tail-growth-mm",
        type=float,
        default=None,
        help=(
            "Optional hard cap on growth of the measured radial tail outside "
            "each stage's active basis. By default it is recorded but not gated; "
            "warm stages deliberately preserve higher coefficients in the "
            "authoritative full-band radial state."
        ),
    )
    continuation = parser.add_mutually_exclusive_group()
    continuation.add_argument(
        "--progressive-mode-continuation",
        "--mode-continuation",
        dest="continuation_strategy",
        action="store_const",
        const=CONTINUATION_PROGRESSIVE_MODES,
        help=(
            "Use the complete training band in every stage while growing the "
            "modal basis through 1, 3, ..., K as an explicit experiment."
        ),
    )
    continuation.add_argument(
        "--frequency-continuation",
        dest="continuation_strategy",
        action="store_const",
        const=CONTINUATION_CUMULATIVE_FREQUENCIES,
        help=(
            "Use cumulative low-to-high training-frequency stages (default)."
        ),
    )
    continuation.add_argument(
        "--joint-full-band",
        "--no-continuation",
        "--no-frequency-continuation",
        dest="continuation_strategy",
        action="store_const",
        const=CONTINUATION_NONE,
        help=(
            "Optimize the complete training band with the full modal basis in "
            "one joint stage as an explicit ablation."
        ),
    )
    # The multi-frequency scattering objective is genuinely non-convex from
    # the deliberately wrong ellipse start.  The completed 0.5/1.5/2.5 GHz
    # calibration measured an initial joint direction away from the target,
    # while the 0.5 GHz direction was strongly target-aligned.  Low-to-high
    # continuation is therefore the safe default; the joint objective remains
    # available as an explicit ablation.
    parser.set_defaults(
        continuation_strategy=CONTINUATION_CUMULATIVE_FREQUENCIES
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help=(
            "Return zero after writing diagnostics even when the progress-only "
            "decrease check fails."
        ),
    )
    args = parser.parse_args(argv)
    target = _build_target(args.target)
    if args.initial_shape is None:
        args.initial_shape = "circle" if args.target == "star" else "ellipse"
    if args.train_ghz is None:
        args.train_ghz = target.default_train_ghz
    if args.holdout_ghz is None:
        args.holdout_ghz = target.default_holdout_ghz
    if args.num_nodes is None:
        args.num_nodes = target.default_num_nodes
    if args.output_dir is None:
        tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.output_dir = Path("results/inverse_solver_comparison") / f"mlp-{args.initial_shape}-to-{target.output_tag}-{tag}"
    if args.num_pairs < 4:
        parser.error("--num-pairs must be at least 4")
    if args.num_nodes < 2 * target.bandwidth + 2 or args.num_nodes % 2:
        parser.error(
            f"--num-nodes must be even and at least {2 * target.bandwidth + 2}"
        )
    for name in ("outer_iterations", "hidden_features", "hidden_layers", "redistance_steps", "redistance_samples"):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    for name in (
        "redistance_boundary_tolerance_mm",
        "maximum_redistance_drift_mm",
        "geometry_convergence_tolerance_mm",
        "maximum_modal_update_mm",
    ):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0.0:
            parser.error(f"--{name.replace('_', '-')} must be finite and positive")
    if args.maximum_spectral_tail_growth_mm is not None and (
        not math.isfinite(args.maximum_spectral_tail_growth_mm)
        or args.maximum_spectral_tail_growth_mm < 0.0
    ):
        parser.error(
            "--maximum-spectral-tail-growth-mm must be finite and non-negative"
        )
    if args.maximum_mode is not None and args.maximum_mode < 1:
        parser.error("--maximum-mode must be positive")
    if set(args.train_ghz) & set(args.holdout_ghz):
        parser.error("training and holdout frequencies must be disjoint")
    # Give response archives and cumulative-frequency prefixes one physical,
    # unambiguous column order regardless of the CLI's comma order.
    args.train_ghz = tuple(sorted(float(value) for value in args.train_ghz))
    if len(set(args.train_ghz)) != len(args.train_ghz):
        parser.error("--train-ghz must not contain duplicates")
    # Compatibility attribute for external wrappers that inspected the old
    # boolean.  It now means frequency staging specifically, not continuation
    # in general.
    args.frequency_continuation = (
        args.continuation_strategy == CONTINUATION_CUMULATIVE_FREQUENCIES
    )
    args.solvers = tuple(dict.fromkeys(args.solvers))
    return args


def _prepare_output(path: Path, overwrite: bool) -> Path:
    resolved = path.resolve()
    if resolved in {REPOSITORY_ROOT, Path(resolved.anchor)}:
        raise ValueError("output directory cannot be the repository or filesystem root")
    if resolved.exists() and not resolved.is_dir():
        raise NotADirectoryError(f"output path exists but is not a directory: {resolved}")
    if resolved.exists() and any(resolved.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for name in GENERATED_NAMES:
            artifact = resolved / name
            if artifact.is_file() or artifact.is_symlink():
                artifact.unlink()
    return resolved


def _initial_teacher(kind: str) -> torch.nn.Module:
    if kind == "circle":
        return CircleSDF2D(
            center=DEFAULT_INITIAL_CENTER,
            radius=DEFAULT_INITIAL_RADIUS,
            dtype=torch.float64,
        )
    if kind == "ellipse":
        return EllipseLevelSet2D(
            center=DEFAULT_INITIAL_CENTER,
            semi_axes=(0.072, 0.038),
            rotation_radians=0.4,
            dtype=torch.float64,
        )
    if kind == "star":
        return StarLevelSet2D(
            center=DEFAULT_STAR_INITIAL_CENTER,
            mean_radius=DEFAULT_STAR_INITIAL_MEAN_RADIUS,
            amplitude=DEFAULT_STAR_INITIAL_AMPLITUDE,
            lobes=int(star_config.TARGET_STAR_LOBES),
            rotation_radians=DEFAULT_STAR_INITIAL_ROTATION,
            dtype=torch.float64,
        )
    raise ValueError(f"unsupported initial shape: {kind!r}")


def _redistance_config(args: argparse.Namespace, bounds: Any) -> NeuralRedistanceConfig:
    warmup_steps = min(150, max(0, args.redistance_steps // 4))
    return NeuralRedistanceConfig(
        bounds=bounds,
        max_steps=args.redistance_steps,
        # The stopping objective contains the Eikonal term, so at least one
        # optimizer update must see that term before a tolerance check can end
        # training.  The trainer enforces the same invariant independently.
        minimum_steps=min(args.redistance_steps, max(100, warmup_steps + 1)),
        warmup_steps=warmup_steps,
        sample_count=args.redistance_samples,
        heldout_sample_count=max(256, args.redistance_samples // 4),
        boundary_max_tolerance_m=1.0e-3
        * args.redistance_boundary_tolerance_mm,
        # Under the outer Eikonal gate, or the inner fit is allowed to stop in
        # a field state the outer loop refuses to call converged and the run
        # can only ever end at maximum_iterations.  Not far under: a wrong
        # ellipse or star needs about 6e-2 to fit at all inside the step
        # budget, so a tighter value only exhausts max_steps.
        eikonal_rms_tolerance=1.0e-1,
        seed=args.mlp_seed + 1000,
    )


def _incremental_redistance_config(
    base: NeuralRedistanceConfig,
) -> NeuralRedistanceConfig:
    """Adapt a from-scratch fit for small, warm-started inverse updates.

    The initial random MLP needs a boundary-loss warm-up before the Eikonal
    objective is introduced.  Once that model represents the accepted curve,
    subsequent curves are only a small modal step away: repeating the warm-up
    temporarily relaxes the signed-distance objective and was measured to
    increase zero-set drift.  A stronger boundary term instead keeps the warm
    start's zero set attached to the new canonical curve.
    """

    if not isinstance(base, NeuralRedistanceConfig):
        raise TypeError("base must be a NeuralRedistanceConfig.")
    return replace(
        base,
        warmup_steps=0,
        minimum_steps=min(base.max_steps, 100),
        boundary_weight=2000.0,
    )


def _mode_budget(
    problem: Any, initial_points: Any, requested: int | None
) -> dict[str, Any]:
    """Resolve the update basis against wave and scan angular resolution.

    A mode the data cannot resolve is not forbidden -- the star target needs
    its lobe mode, which sits near the estimate -- but it is reported, because
    an unresolvable column is the one the regularisation has to carry.
    """

    points = np.asarray(initial_points, dtype=np.float64)
    radius = float(np.mean(np.linalg.norm(points - np.mean(points, axis=0), axis=1)))
    angular = np.asarray(problem.angular_frequencies, dtype=np.float64)
    exterior = problem.exterior
    permittivity = problem.eps0 * exterior.epsr - 1j * exterior.sigma / angular
    wavenumbers = np.abs(angular * np.sqrt(problem.mu0 * exterior.mur * permittivity))
    maximum_wavenumber = float(np.max(wavenumbers))
    wavenumber_resolvable = resolvable_maximum_mode(maximum_wavenumber, radius)
    observation_count = int(np.asarray(problem.source_points).shape[0])
    # An even N-angle scan has one unpaired cosine at its Nyquist mode.  A
    # complete real {cos(k theta), sin(k theta)} update basis is unaliased only
    # through floor((N - 1) / 2).
    angular_resolvable = (observation_count - 1) // 2
    automatic_mode = min(wavenumber_resolvable, angular_resolvable)
    maximum_mode = automatic_mode if requested is None else int(requested)
    return {
        "maximum_mode": maximum_mode,
        # Retain the old key for bundle readers; it now means the joint limit.
        "resolvable_maximum_mode": automatic_mode,
        "wavenumber_resolvable_maximum_mode": wavenumber_resolvable,
        "angular_resolvable_maximum_mode": angular_resolvable,
        "angular_observation_count": observation_count,
        "requested_maximum_mode": requested,
        "initial_mean_radius_m": radius,
        "maximum_exterior_wavenumber_per_m": maximum_wavenumber,
        "maximum_exterior_ka": maximum_wavenumber * radius,
        "exceeds_wavenumber_resolution": maximum_mode > wavenumber_resolvable,
        "exceeds_angular_resolution": maximum_mode > angular_resolvable,
        "exceeds_resolution": maximum_mode > automatic_mode,
        "criterion": (
            "min(ceil(ka + ka**(1/3)), floor((N_angles - 1)/2)) on "
            "the training band, initial mean radius, and paired ring scan"
        ),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, torch.dtype):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _experiment_snapshot(
    problem: PairedForwardProblem, target: InverseTarget
) -> dict[str, Any]:
    """Freeze the physical scene independently of mutable configuration files.

    Complex source strengths use separate real/imaginary arrays in frequency
    order so the JSON artifact can reconstruct the exact forward problem.
    """

    return _jsonable(
        {
            "measurement": "paired_complex_scattered_field",
            "num_pairs": problem.num_pairs,
            "source_points_m": problem.source_points,
            "receiver_points_m": problem.receiver_points,
            "angular_frequencies_rad_s": problem.angular_frequencies,
            "source_strengths": {
                "real": problem.source_strengths.real,
                "imag": problem.source_strengths.imag,
            },
            "exterior": asdict(problem.exterior),
            "interior": asdict(problem.interior),
            "eps0_f_per_m": problem.eps0,
            "mu0_h_per_m": problem.mu0,
            "observation_noise": "none",
            "target_parameters": target.parameter_dict(),
        }
    )


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True, capture_output=True, check=False
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPOSITORY_ROOT, text=True, capture_output=True, check=False
    ).stdout.splitlines()
    return {"commit": commit or None, "dirty_paths": dirty}


def _trajectory_row(entry: _TrajectoryEntry) -> dict[str, Any]:
    item = entry.iteration
    modal_step = np.asarray(item.modal_step, dtype=np.float64)
    expected_modal_count = 2 * entry.maximum_mode + 1
    if modal_step.shape != (expected_modal_count,) or not np.all(
        np.isfinite(modal_step)
    ):
        raise ValueError(
            "modal_step must contain exactly "
            f"{expected_modal_count} finite coefficients for stage maximum mode "
            f"{entry.maximum_mode}."
        )
    driver_fields = {
        "iteration",
        "stage",
        "stage_iteration",
        "stage_train_frequencies_ghz",
        "stage_maximum_mode",
        "modal_step_m",
    }
    row = {
        name: getattr(item, name)
        for name in TRAJECTORY_FIELDNAMES
        if name not in driver_fields
    }
    return {
        "iteration": item.iteration,
        "stage": entry.stage,
        "stage_iteration": entry.stage_iteration,
        "stage_train_frequencies_ghz": ",".join(
            format(value, ".17g") for value in entry.train_frequencies_ghz
        ),
        "stage_maximum_mode": entry.maximum_mode,
        "modal_step_m": ",".join(format(value, ".17g") for value in modal_step),
        **row,
    }


def _write_trajectory(
    path: Path, entries: Sequence[_TrajectoryEntry]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=TRAJECTORY_FIELDNAMES, lineterminator="\n"
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(_trajectory_row(entry))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    output = _prepare_output(args.output_dir if args.output_dir.is_absolute() else REPOSITORY_ROOT / args.output_dir, args.overwrite)
    target = _build_target(args.target)
    geometry_config = target.geometry_config(args.num_nodes)
    initialization_redistance_config = _redistance_config(
        args, geometry_config.bounds
    )
    inverse_redistance_config = _incremental_redistance_config(
        initialization_redistance_config
    )

    teacher = _initial_teacher(args.initial_shape)
    raw_teacher_curve = build_ordered_sdf_geometry(teacher, geometry_config).curve

    source_points, receiver_points = _ring_scan(
        center=target.center, standoff=0.30, num_pairs=args.num_pairs
    )
    frequencies = tuple(args.train_ghz) + tuple(args.holdout_ghz)
    all_problem = _build_problem(frequencies, source_points, receiver_points)
    train_problem = _build_problem(args.train_ghz, source_points, receiver_points)
    experiment_snapshot = _experiment_snapshot(all_problem, target)
    mode_budget = _mode_budget(
        train_problem, raw_teacher_curve.points, args.maximum_mode
    )

    # The direct optimizer has 2 K + 1 controls either way.  A succession of
    # local normal velocities, however, does not define a 2 K + 1-dimensional
    # *shape* space: the completed K5 run accumulated 6.26 mm outside K5 and
    # ceased to be star-shaped.  Project the deliberately wrong initialization
    # once into a gauge-fixed radial chart, then keep that coefficient state
    # authoritative.  The chart represents the K5 truth exactly; for the
    # ellipse start the measured one-time projection is about 0.72 mm RMS.
    initial_radial_curve_state = fit_radial_fourier_curve_state(
        raw_teacher_curve,
        maximum_mode=mode_budget["maximum_mode"],
    )
    initial_curve = radial_fourier_state_curve(
        initial_radial_curve_state,
        geometry_config=geometry_config,
        full_validation=True,
    )
    initial_projection_set_distance = max(
        maximum_curve_set_distance(raw_teacher_curve.points, initial_curve.points),
        maximum_curve_set_distance(initial_curve.points, raw_teacher_curve.points),
    )
    # Recompute the reporting heuristic on the curve actually sent to BEM.
    mode_budget = _mode_budget(
        train_problem, initial_curve.points, args.maximum_mode
    )
    if mode_budget["maximum_mode"] != initial_radial_curve_state.maximum_mode:
        raise RuntimeError(
            "The automatic modal budget changed after canonical radial "
            "projection, so the authoritative state's band would disagree "
            "with the inverse configuration. Re-run with an explicit "
            f"--maximum-mode {initial_radial_curve_state.maximum_mode}."
        )
    initial_model = SmoothMLPSDF2D(
        bounds=geometry_config.bounds,
        hidden_features=args.hidden_features,
        hidden_layers=args.hidden_layers,
        seed=args.mlp_seed,
        geometric_center=DEFAULT_INITIAL_CENTER,
        geometric_radius=DEFAULT_INITIAL_RADIUS,
        dtype=torch.float64,
    )
    print(
        f"[initialization] wrong {args.initial_shape} -> radial K"
        f"{mode_budget['maximum_mode']} state: "
        f"projection={1.0e3 * initial_radial_curve_state.initial_projection_rms_m:.3f}/"
        f"{1.0e3 * initial_projection_set_distance:.3f} mm RMS/set-max",
        flush=True,
    )
    print(f"[initialization] random MLP -> canonical radial contour", flush=True)
    initial_fit = redistance_neural_sdf_to_curve(
        initial_model,
        initial_curve,
        initialization_redistance_config,
    )
    print(
        "[initialization] "
        f"redistance={initial_fit.stop_reason}/{initial_fit.steps}, "
        f"heldout={1.0e3 * initial_fit.final_heldout_distance_rms_m:.3f} mm, "
        f"boundary={1.0e3 * initial_fit.final_boundary_max_abs_m:.3f} mm, "
        f"eikonal={initial_fit.final_eikonal_rms:.3e}, "
        f"best_step={int(initial_fit.diagnostics['best_full_objective_step'])}",
        flush=True,
    )
    if not initial_fit.converged:
        raise RuntimeError(
            "Initial neural re-distancing did not meet its distance/Eikonal gates: "
            f"{initial_fit.stop_reason}, heldout={initial_fit.final_heldout_distance_rms_m:.3e} m, "
            f"eikonal={initial_fit.final_eikonal_rms:.3e}."
        )
    # Topology and Method-B feasibility are checked independently of the fit loss.
    initial_geometry = build_ordered_sdf_geometry(initial_model, geometry_config)
    initial_representation_drift = max(
        maximum_curve_set_distance(initial_curve.points, initial_geometry.curve.points),
        maximum_curve_set_distance(initial_geometry.curve.points, initial_curve.points),
    )
    if initial_representation_drift > 1.0e-3 * args.maximum_redistance_drift_mm:
        raise RuntimeError(
            "Initial MLP contour exceeds the canonical radial-state drift gate: "
            f"{1.0e3 * initial_representation_drift:.3f} mm > "
            f"{args.maximum_redistance_drift_mm:.3f} mm."
        )
    print(
        "[initialization] "
        f"MLP/canonical set drift={1.0e3 * initial_representation_drift:.3f} mm",
        flush=True,
    )

    print(f"[oracle] {target.truth_oracle}", flush=True)
    truth = target.observations(all_problem)
    oracle_diagnostics = target.oracle_diagnostics(all_problem)
    train_count = len(args.train_ghz)
    continuation_stage_count = (
        _progressive_mode_stage_count(mode_budget["maximum_mode"])
        if args.continuation_strategy == CONTINUATION_PROGRESSIVE_MODES
        else None
    )
    continuation_plan = _frequency_continuation_plan(
        args.train_ghz,
        args.outer_iterations,
        strategy=args.continuation_strategy,
        stage_count=continuation_stage_count,
    )
    print(
        f"[modes] ka_max={mode_budget['maximum_exterior_ka']:.2f} on the initial contour "
        f"-> wave limit {mode_budget['wavenumber_resolvable_maximum_mode']}, "
        f"{mode_budget['angular_observation_count']}-angle limit "
        f"{mode_budget['angular_resolvable_maximum_mode']}; "
        f"using {mode_budget['maximum_mode']}"
        + (" (requested, above a limit)" if mode_budget["exceeds_resolution"] else ""),
        flush=True,
    )
    print(
        f"[continuation] strategy={args.continuation_strategy}: "
        + " -> ".join(
            f"stage {stage.stage}: "
            f"{','.join(format(value, 'g') for value in stage.train_frequencies_ghz)} GHz "
            f"({stage.max_iterations} accepted-update cap)"
            for stage in continuation_plan
        ),
        flush=True,
    )
    inverse_config = AlternatingNeuralInverseConfig(
        redistance=inverse_redistance_config,
        max_iterations=args.outer_iterations,
        maximum_mode=mode_budget["maximum_mode"],
        maximum_modal_field_update_m=1.0e-3 * args.maximum_modal_update_mm,
        maximum_redistance_curve_drift_m=1.0e-3
        * args.maximum_redistance_drift_mm,
        geometry_change_tolerance_m=1.0e-3
        * args.geometry_convergence_tolerance_mm,
        maximum_spectral_tail_growth_m=(
            None
            if args.maximum_spectral_tail_growth_mm is None
            else 1.0e-3 * args.maximum_spectral_tail_growth_mm
        ),
        direct_curve_retraction="radial_fourier",
    )

    solver_metrics: dict[str, Any] = {}
    failed_progress_gate = False
    shared_initial_points: np.ndarray | None = None
    for solver in args.solvers:
        model = copy.deepcopy(initial_model)
        model.eval()
        # The ordered boundary is the accepted optimization state.  The MLP is
        # its re-distanced representation, not a second source of geometry for
        # finite-difference probes.
        initial_all = predict_paired_curve_response(
            initial_curve,
            all_problem,
            geometry_config,
            solver=solver,
        )
        initial_points = np.asarray(initial_all.geometry_build.curve.points, dtype=np.float64)
        if shared_initial_points is None:
            shared_initial_points = np.array(initial_points, copy=True)
        elif not np.array_equal(shared_initial_points, initial_points):
            raise RuntimeError(
                "MOD and Kress did not receive bit-identical initial ordered geometry."
            )

        # Flush every accepted state as it arrives.  A long calibration that is
        # interrupted still leaves enough evidence to diagnose its trajectory;
        # the completed result rewrites this same CSV canonically below.
        live_trajectory_stream = (output / f"{solver}_trajectory.csv").open(
            "w", encoding="utf-8", newline=""
        )
        live_trajectory_writer = csv.DictWriter(
            live_trajectory_stream,
            fieldnames=TRAJECTORY_FIELDNAMES,
            lineterminator="\n",
        )
        live_trajectory_writer.writeheader()
        live_trajectory_stream.flush()
        entries: list[_TrajectoryEntry] = []
        stage_results: list[Any] = []
        stage_metadata: list[dict[str, Any]] = []
        current_curve = initial_all.geometry_build.curve
        current_representation_curve = initial_geometry.curve
        current_radial_curve_state = initial_radial_curve_state
        evaluation_offset = 0
        # ``initial_all`` is a driver-level all-frequency audit and is reported
        # separately.  Keep inverse-local cumulative diagnostics restricted to
        # the stage solves included in ``total_evaluation_count``.
        cumulative_maximum_residual = 0.0
        accepted_updates_before_stage = 0
        stage_seed_offset = 0

        print(f"\n[{solver.upper()}] alternating MLP inverse", flush=True)
        try:
            for stage_plan in continuation_plan:
                effective_stage_budget = _effective_stage_budget(
                    stage=stage_plan.stage,
                    stage_count=len(continuation_plan),
                    planned_max_iterations=stage_plan.max_iterations,
                    total_iterations=args.outer_iterations,
                    accepted_updates_before_stage=accepted_updates_before_stage,
                )
                carried_budget = effective_stage_budget - stage_plan.max_iterations
                stage_problem = _build_problem(
                    stage_plan.train_frequencies_ghz,
                    source_points,
                    receiver_points,
                )
                stage_frequency_count = len(stage_plan.train_frequencies_ghz)
                stage_data = ComplexScatteredData(
                    stage_problem,
                    truth[:, :stage_frequency_count],
                )
                automatic_stage_mode = _mode_budget(
                    stage_problem,
                    current_curve.points,
                    requested=None,
                )
                stage_maximum_mode = _continuation_stage_maximum_mode(
                    stage_plan.stage,
                    len(continuation_plan),
                    final_maximum_mode=mode_budget["maximum_mode"],
                    automatic_maximum_mode=automatic_stage_mode["maximum_mode"],
                    strategy=args.continuation_strategy,
                )
                continuation_mode_limit = stage_maximum_mode
                stage_redistance = replace(
                    inverse_redistance_config,
                    seed=inverse_redistance_config.seed + stage_seed_offset,
                )
                stage_tail_reference = radial_spectral_tail_rms(
                    initial_points,
                    stage_maximum_mode,
                )
                stage_config = _stage_inverse_config(
                    inverse_config,
                    redistance_config=stage_redistance,
                    max_iterations=effective_stage_budget,
                    maximum_mode=stage_maximum_mode,
                    spectral_tail_reference_rms_m=stage_tail_reference,
                    audit_seed=inverse_config.audit_seed + stage_seed_offset,
                )
                print(
                    f"  stage {stage_plan.stage}/{len(continuation_plan)} "
                    f"train={','.join(format(value, 'g') for value in stage_plan.train_frequencies_ghz)} GHz "
                    f"modes=0..{stage_maximum_mode} "
                    f"budget={effective_stage_budget}"
                    + (
                        f" (planned={stage_plan.max_iterations}, carry={carried_budget})"
                        if carried_budget
                        else ""
                    ),
                    flush=True,
                )

                def progress(
                    item: Any,
                    *,
                    label: str = solver,
                    stage_number: int = stage_plan.stage,
                    stage_frequencies: tuple[float, ...] = stage_plan.train_frequencies_ghz,
                    stage_mode: int = stage_maximum_mode,
                    prior_evaluations: int = evaluation_offset,
                    prior_maximum_residual: float = cumulative_maximum_residual,
                ) -> None:
                    # Retain every stage's iteration-zero baseline even though
                    # it duplicates the preceding geometry.  Its loss and tail
                    # belong to the newly enlarged objective/basis; omitting it
                    # would leave stale diagnostics when a stage accepts no
                    # update at all.
                    global_item = replace(
                        item,
                        iteration=len(entries),
                        evaluation_count=prior_evaluations + item.evaluation_count,
                        maximum_system_residual=max(
                            prior_maximum_residual, item.maximum_system_residual
                        ),
                    )
                    entry = _TrajectoryEntry(
                        iteration=global_item,
                        stage=stage_number,
                        stage_iteration=item.iteration,
                        train_frequencies_ghz=stage_frequencies,
                        maximum_mode=stage_mode,
                    )
                    entries.append(entry)
                    live_trajectory_writer.writerow(_trajectory_row(entry))
                    live_trajectory_stream.flush()
                    tail_limit_text = (
                        "off"
                        if item.radial_spectral_tail_limit_m is None
                        else (
                            f"{1.0e3 * item.radial_spectral_tail_limit_m:.3f} mm"
                        )
                    )
                    print(
                        f"    {label.upper()} iter={global_item.iteration:02d} "
                        f"stage_iter={item.iteration:02d} loss={item.loss:.4e} "
                        f"rel={item.relative_l2_error:.4e} "
                        f"backtracks={item.accepted_backtrack_count} "
                        f"pred_raw={item.trust_region_predicted_relative_change:.3e} "
                        f"pred_accepted={item.accepted_step_predicted_relative_change:.3e} "
                        f"step={1.0e3 * item.maximum_modal_field_update_m:.3f} mm "
                        f"curve={1.0e3 * item.curve_change_m:.3f} mm "
                        f"arc_refit={1.0e3 * item.arclength_refit_rms_m:.3f}/"
                        f"{1.0e3 * item.arclength_refit_maximum_m:.3f} mm "
                        f"speed_ratio={item.arclength_speed_ratio_before:.3f}->"
                        f"{item.arclength_speed_ratio_after:.3f} "
                        f"projection={1.0e3 * item.redistance_curve_drift_m:.3f} mm "
                        f"tail={1.0e3 * item.radial_spectral_tail_rms_m:.3f} mm/"
                        f"{tail_limit_text} "
                        f"tail_rejects={item.spectral_tail_rejection_count} "
                        f"eikonal={item.eikonal_rms:.3e} "
                        f"redistance={item.redistance_stop_reason}/{item.redistance_steps}",
                        flush=True,
                    )

                stage_result = run_alternating_neural_inverse(
                    model,
                    stage_data,
                    geometry_config,
                    solver=solver,
                    config=stage_config,
                    progress_callback=progress,
                    initial_curve=current_curve,
                    initial_representation_curve=current_representation_curve,
                    initial_radial_curve_state=current_radial_curve_state,
                )
                stage_results.append(stage_result)
                current_curve = stage_result.final_curve
                current_representation_curve = (
                    stage_result.final_representation_curve
                )
                if stage_result.final_radial_curve_state is None:
                    raise RuntimeError(
                        "Radial inverse stage did not return its authoritative state."
                    )
                current_radial_curve_state = stage_result.final_radial_curve_state
                stage_accepted_updates = len(stage_result.iterations) - 1
                if not 0 <= stage_accepted_updates <= effective_stage_budget:
                    raise RuntimeError(
                        "The inverse returned an accepted-update count outside its "
                        "stage budget."
                    )
                accepted_updates_before_stage += stage_accepted_updates
                if accepted_updates_before_stage > args.outer_iterations:
                    raise RuntimeError(
                        "Continuation exceeded the global accepted-update budget."
                    )
                unused_budget_carried_out = (
                    sum(
                        plan.max_iterations
                        for plan in continuation_plan[: stage_plan.stage]
                    )
                    - accepted_updates_before_stage
                    if stage_plan.stage < len(continuation_plan)
                    else 0
                )
                stage_metadata.append(
                    {
                        "stage": stage_plan.stage,
                        "train_frequencies_ghz": stage_plan.train_frequencies_ghz,
                        # Keep ``max_iterations`` as the effective cap used by
                        # the optimizer; the additive fields preserve the
                        # nominal plan and explain a larger final-stage cap.
                        "max_iterations": effective_stage_budget,
                        "planned_max_iterations": stage_plan.max_iterations,
                        "effective_max_iterations": effective_stage_budget,
                        "carried_budget_in": carried_budget,
                        "unused_budget_carried_out": unused_budget_carried_out,
                        "accepted_updates_before_stage": (
                            accepted_updates_before_stage - stage_accepted_updates
                        ),
                        "maximum_mode": stage_maximum_mode,
                        "continuation_mode_limit": continuation_mode_limit,
                        "automatic_mode_budget": automatic_stage_mode,
                        "spectral_tail_reference_rms_m": stage_tail_reference,
                        "spectral_tail_growth_allowance_m": (
                            inverse_config.maximum_spectral_tail_growth_m
                        ),
                        "redistance_seed": stage_redistance.seed,
                        "audit_seed": stage_config.audit_seed,
                        "initial_damping": stage_config.initial_damping,
                        "converged": stage_result.converged,
                        "stop_reason": stage_result.stop_reason,
                        "accepted_updates": stage_accepted_updates,
                        "initial_loss": stage_result.initial_iteration.loss,
                        "final_loss": stage_result.final_iteration.loss,
                        "initial_relative_l2_error": (
                            stage_result.initial_iteration.relative_l2_error
                        ),
                        "final_relative_l2_error": (
                            stage_result.final_iteration.relative_l2_error
                        ),
                        "initial_radial_spectral_tail_rms_m": (
                            stage_result.initial_iteration.radial_spectral_tail_rms_m
                        ),
                        "final_radial_spectral_tail_rms_m": (
                            stage_result.final_iteration.radial_spectral_tail_rms_m
                        ),
                        "radial_spectral_tail_limit_m": (
                            stage_result.final_iteration.radial_spectral_tail_limit_m
                        ),
                        "evaluation_count": stage_result.total_evaluation_count,
                        "infeasible_evaluation_count": (
                            stage_result.infeasible_evaluation_count
                        ),
                        "spectral_tail_rejection_count": (
                            stage_result.spectral_tail_rejection_count
                        ),
                        "forward_seconds": stage_result.total_forward_seconds,
                        "bem_seconds": stage_result.total_bem_seconds,
                        "curve_update_seconds": (
                            stage_result.total_curve_update_seconds
                        ),
                        "redistance_seconds": stage_result.total_redistance_seconds,
                        "redistance_attempt_count": (
                            stage_result.redistance_attempt_count
                        ),
                        "total_redistance_step_count": (
                            stage_result.total_redistance_step_count
                        ),
                        "full_validation_rejection_count": (
                            stage_result.full_validation_rejection_count
                        ),
                        "redistance_failure_count": (
                            stage_result.redistance_failure_count
                        ),
                        "representation_extraction_failure_count": (
                            stage_result.representation_extraction_failure_count
                        ),
                        "representation_drift_rejection_count": (
                            stage_result.representation_drift_rejection_count
                        ),
                        "geometry_audit_seconds": (
                            stage_result.total_geometry_audit_seconds
                        ),
                        "total_seconds": stage_result.total_seconds,
                    }
                )
                evaluation_offset += stage_result.total_evaluation_count
                cumulative_maximum_residual = max(
                    cumulative_maximum_residual,
                    stage_result.maximum_system_residual,
                )
                stage_seed_offset += stage_plan.max_iterations
                print(
                    f"  stage {stage_plan.stage} stop={stage_result.stop_reason} "
                    f"accepted={stage_accepted_updates}",
                    flush=True,
                )
        finally:
            live_trajectory_stream.close()
        inverse = _FrequencyContinuationResult(
            solver=solver,
            entries=tuple(entries),
            stage_results=tuple(stage_results),
            stage_metadata=tuple(stage_metadata),
            final_curve=current_curve,
            final_representation_curve=current_representation_curve,
        )
        final_all = predict_paired_curve_response(
            inverse.final_curve,
            all_problem,
            geometry_config,
            solver=solver,
        )
        final_representation_all = predict_paired_curve_response(
            inverse.final_representation_curve,
            all_problem,
            geometry_config,
            solver=solver,
        )
        holdout = slice(train_count, len(frequencies))
        initial_train_loss, initial_train_relative = _objective_metrics(
            initial_all.scattered_response[:, :train_count], truth[:, :train_count]
        )
        final_train_loss, final_train_relative = _objective_metrics(
            final_all.scattered_response[:, :train_count], truth[:, :train_count]
        )
        _, initial_holdout_relative = _objective_metrics(
            initial_all.scattered_response[:, holdout], truth[:, holdout]
        )
        _, final_holdout_relative = _objective_metrics(
            final_all.scattered_response[:, holdout], truth[:, holdout]
        )
        _, final_representation_train_relative = _objective_metrics(
            final_representation_all.scattered_response[:, :train_count],
            truth[:, :train_count],
        )
        _, final_representation_holdout_relative = _objective_metrics(
            final_representation_all.scattered_response[:, holdout],
            truth[:, holdout],
        )
        _, representation_response_relative = _objective_metrics(
            final_representation_all.scattered_response,
            final_all.scattered_response,
        )
        initial_distance = target.boundary_distances(initial_all.geometry_build.curve.points)
        final_distance = target.boundary_distances(final_all.geometry_build.curve.points)
        final_representation_distance = target.boundary_distances(
            final_representation_all.geometry_build.curve.points
        )
        final_representation_curve_drift = maximum_curve_set_distance(
            final_all.geometry_build.curve.points,
            final_representation_all.geometry_build.curve.points,
        )
        initial_final_basis_tail = radial_spectral_tail_rms(
            initial_all.geometry_build.curve.points,
            mode_budget["maximum_mode"],
        )
        final_final_basis_tail = radial_spectral_tail_rms(
            final_all.geometry_build.curve.points,
            mode_budget["maximum_mode"],
        )
        final_representation_final_basis_tail = radial_spectral_tail_rms(
            final_representation_all.geometry_build.curve.points,
            mode_budget["maximum_mode"],
        )
        accepted_update_count = sum(
            len(result.iterations) - 1 for result in inverse.stage_results
        )
        progress_demonstrated = (
            accepted_update_count > 0 and final_train_loss < initial_train_loss
        )
        failed_progress_gate = failed_progress_gate or not progress_demonstrated
        solver_metrics[solver] = {
            "converged": inverse.converged,
            "stop_reason": inverse.stop_reason,
            "accepted_updates": accepted_update_count,
            "final_radial_fourier_state": {
                "maximum_mode": current_radial_curve_state.maximum_mode,
                "center_m": current_radial_curve_state.center,
                "radius_cosine_coefficients_m": (
                    current_radial_curve_state.radius_cosine_coefficients
                ),
                "radius_sine_coefficients_m": (
                    current_radial_curve_state.radius_sine_coefficients
                ),
                "minimum_radius_lower_bound_m": (
                    current_radial_curve_state.minimum_radius_lower_bound_m
                ),
            },
            "inverse_forward_attempt_count": inverse.total_evaluation_count,
            "inverse_infeasible_forward_attempt_count": inverse.infeasible_evaluation_count,
            "inverse_spectral_tail_rejection_count": inverse.spectral_tail_rejection_count,
            "initial_training_loss": initial_train_loss,
            "final_training_loss": final_train_loss,
            "initial_training_relative_l2": initial_train_relative,
            "final_training_relative_l2": final_train_relative,
            "initial_holdout_relative_l2": initial_holdout_relative,
            "final_holdout_relative_l2": final_holdout_relative,
            "final_mlp_representation_training_relative_l2": (
                final_representation_train_relative
            ),
            "final_mlp_representation_holdout_relative_l2": (
                final_representation_holdout_relative
            ),
            "final_mlp_representation_response_relative_to_canonical_l2": (
                representation_response_relative
            ),
            "initial_maximum_boundary_error_m": float(np.max(initial_distance)),
            "final_maximum_boundary_error_m": float(np.max(final_distance)),
            "final_mlp_representation_maximum_boundary_error_m": float(
                np.max(final_representation_distance)
            ),
            "final_mlp_representation_curve_drift_m": (
                final_representation_curve_drift
            ),
            "radial_spectral_tail_basis_maximum_mode": mode_budget["maximum_mode"],
            "initial_radial_spectral_tail_rms_m": initial_final_basis_tail,
            "final_radial_spectral_tail_rms_m": final_final_basis_tail,
            "final_mlp_representation_radial_spectral_tail_rms_m": (
                final_representation_final_basis_tail
            ),
            "radial_spectral_tail_limit_m": (
                inverse.final_iteration.radial_spectral_tail_limit_m
            ),
            "global_requested_tail_cap_m": (
                None
                if inverse_config.maximum_spectral_tail_growth_m is None
                else (
                    initial_final_basis_tail
                    + inverse_config.maximum_spectral_tail_growth_m
                )
            ),
            "inverse_maximum_system_residual": inverse.maximum_system_residual,
            "initial_all_frequency_maximum_system_residual": float(
                np.max(initial_all.linear_system_relative_residuals)
            ),
            "final_all_frequency_maximum_system_residual": float(
                np.max(final_all.linear_system_relative_residuals)
            ),
            "final_mlp_representation_all_frequency_maximum_system_residual": float(
                np.max(final_representation_all.linear_system_relative_residuals)
            ),
            "inverse_forward_seconds": inverse.total_forward_seconds,
            "inverse_bem_seconds": inverse.total_bem_seconds,
            "inverse_curve_update_seconds": inverse.total_curve_update_seconds,
            "inverse_redistance_seconds": inverse.total_redistance_seconds,
            "inverse_redistance_attempt_count": inverse.redistance_attempt_count,
            "inverse_total_redistance_step_count": (
                inverse.total_redistance_step_count
            ),
            "inverse_full_validation_rejection_count": (
                inverse.full_validation_rejection_count
            ),
            "inverse_redistance_failure_count": inverse.redistance_failure_count,
            "inverse_representation_extraction_failure_count": (
                inverse.representation_extraction_failure_count
            ),
            "inverse_representation_drift_rejection_count": (
                inverse.representation_drift_rejection_count
            ),
            "inverse_geometry_audit_seconds": inverse.total_geometry_audit_seconds,
            "inverse_total_seconds": inverse.total_seconds,
            "frequency_continuation_stages": list(inverse.stage_metadata),
            "progress_gate": {
                "passed": progress_demonstrated,
                "criterion": "at_least_one_accepted_cycle_and_strict_training_loss_decrease",
                "claims_convergence": False,
            },
        }
        _write_trajectory(output / f"{solver}_trajectory.csv", inverse.entries)
        np.savez_compressed(
            output / f"{solver}_responses.npz",
            frequencies_ghz=np.asarray(frequencies),
            truth=truth,
            initial=initial_all.scattered_response,
            final=final_all.scattered_response,
            final_representation=final_representation_all.scattered_response,
            initial_curve=initial_all.geometry_build.curve.points,
            final_curve=final_all.geometry_build.curve.points,
            final_representation_curve=(
                final_representation_all.geometry_build.curve.points
            ),
            # Every accepted canonical state keeps its own contour, so the
            # trajectory can be replayed without re-running the inverse.
            geometry_trajectory=np.stack(
                [item.geometry_points for item in inverse.iterations], axis=0
            ),
            exact_boundary_points=target.exact_boundary_polyline(),
        )
        torch.save(
            {
                "state_dict": model.state_dict(),
                "model_metadata": model.initialization_metadata(),
            },
            output / f"{solver}_model.pt",
        )

    initial_fit_metrics = {
        "config": asdict(initialization_redistance_config),
        "converged": initial_fit.converged,
        "steps": initial_fit.steps,
        "stop_reason": initial_fit.stop_reason,
        "initial_total_loss": initial_fit.initial_total_loss,
        "final_total_loss": initial_fit.final_total_loss,
        "final_distance_rms_m": initial_fit.final_distance_rms_m,
        "final_heldout_distance_rms_m": initial_fit.final_heldout_distance_rms_m,
        "final_boundary_max_abs_m": initial_fit.final_boundary_max_abs_m,
        "final_eikonal_rms": initial_fit.final_eikonal_rms,
        "final_eikonal_maximum_deviation": initial_fit.final_eikonal_maximum_deviation,
        "diagnostics": dict(initial_fit.diagnostics),
    }
    metrics = {
        "schema": "solver-neutral-alternating-mlp-sdf-inverse-v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": shlex.join(sys.argv if argv is None else [sys.argv[0], *argv]),
        "target": args.target,
        "experiment": experiment_snapshot,
        "truth_oracle": target.truth_oracle,
        "oracle_diagnostics": oracle_diagnostics,
        "initial_shape": args.initial_shape,
        "model": initial_model.initialization_metadata(),
        "initial_redistance": initial_fit_metrics,
        "canonical_curve_parameterization": {
            "kind": "gauge_fixed_star_shaped_radial_fourier",
            "coefficient_order": (
                "mean_radius,center_x,center_y,cos_2,sin_2,...,cos_K,sin_K"
            ),
            "maximum_mode": initial_radial_curve_state.maximum_mode,
            "initial_center_m": initial_radial_curve_state.center,
            "initial_radius_cosine_coefficients_m": (
                initial_radial_curve_state.radius_cosine_coefficients
            ),
            "initial_radius_sine_coefficients_m": (
                initial_radial_curve_state.radius_sine_coefficients
            ),
            "initial_projection_radial_rms_m": (
                initial_radial_curve_state.initial_projection_rms_m
            ),
            "initial_projection_radial_maximum_m": (
                initial_radial_curve_state.initial_projection_maximum_m
            ),
            "initial_projection_symmetric_set_distance_m": (
                initial_projection_set_distance
            ),
            "initial_mlp_representation_set_distance_m": (
                initial_representation_drift
            ),
        },
        "initial_geometry_maximum_normalized_residual_m": initial_geometry.maximum_normalized_curve_residual,
        "train_frequencies_ghz": args.train_ghz,
        "holdout_frequencies_ghz": args.holdout_ghz,
        "geometry_config": asdict(geometry_config),
        "inverse_config": asdict(inverse_config),
        "mode_budget": mode_budget,
        # Retain the historical container name for artifact readers.  The
        # summary exposes separate frequency-only and any-continuation flags.
        "frequency_continuation": _continuation_metrics_summary(
            args.continuation_strategy,
            continuation_plan,
            args.outer_iterations,
        ),
        "driver_acceptance": (
            "progress-only: at least one accepted cycle and strict training-loss decrease; "
            "this is not a convergence or accuracy claim"
        ),
        "solvers": solver_metrics,
        "provenance": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "torch": torch.__version__,
            "git": _git_state(),
        },
    }
    with (output / "metrics.json").open("w", encoding="utf-8") as stream:
        json.dump(_jsonable(metrics), stream, indent=2, sort_keys=True)
        stream.write("\n")
    if args.continuation_strategy == CONTINUATION_PROGRESSIVE_MODES:
        continuation_summary = [
            "Training keeps the complete frequency band active while the modal basis",
            "grows stage by stage; losses remain comparable across stage baselines.",
        ]
    elif args.continuation_strategy == CONTINUATION_CUMULATIVE_FREQUENCIES:
        continuation_summary = [
            "Training uses cumulative low-to-high frequency stages (the safe default);",
            "each trajectory row records its objective because stage losses are local.",
        ]
    else:
        continuation_summary = [
            "Training uses the explicitly requested joint-objective ablation: one",
            "complete-band stage with the entire accepted-update budget.",
        ]
    lines = [
        "# Alternating MLP-SDF inverse",
        "",
        f"Target: `{args.target}`; initialization contour: wrong `{args.initial_shape}`.",
        "",
        f"Update basis: modes through `k={mode_budget['maximum_mode']}` at "
        f"`ka = {mode_budget['maximum_exterior_ka']:.2f}`. The wave and "
        f"{mode_budget['angular_observation_count']}-angle limits are respectively "
        f"`k={mode_budget['wavenumber_resolvable_maximum_mode']}` and "
        f"`k={mode_budget['angular_resolvable_maximum_mode']}`"
        + (" (the requested basis exceeds a limit)." if mode_budget["exceeds_resolution"] else "."),
        "",
        "The accepted optimization state is a gauge-fixed star-shaped radial Fourier",
        "curve. Its center, mean radius, and modes 2..K are authoritative, so repeated",
        "finite-difference steps cannot create geometry above K. Every accepted contour",
        "is re-distanced into the tanh MLP and audited, but representation error is not",
        "recycled into the next geometry Jacobian.",
        *continuation_summary,
        "The driver exit check demonstrates strict training progress only; it is not a",
        "convergence or reconstruction-accuracy certificate.",
        "",
        "| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for solver, values in solver_metrics.items():
        lines.append(
            f"| {solver.upper()} | {values['initial_training_relative_l2']:.3e} -> {values['final_training_relative_l2']:.3e} "
            f"| {values['initial_holdout_relative_l2']:.3e} -> {values['final_holdout_relative_l2']:.3e} "
            f"| {values['initial_maximum_boundary_error_m']:.3e} -> {values['final_maximum_boundary_error_m']:.3e} m "
            f"| {values['accepted_updates']} | `{values['stop_reason']}` |"
        )
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nArtifacts: {output}", flush=True)
    if failed_progress_gate and not args.no_gate:
        print(
            "Progress-only check failed: at least one solver accepted no decreasing "
            "canonical-curve update with an acceptable MLP distillation.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
