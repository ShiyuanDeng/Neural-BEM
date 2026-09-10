#!/usr/bin/env python3
"""Direct Cartesian-Fourier inverse in the polar-angle chart, with no MLP.

The accepted optimization state is a Cartesian Fourier curve ``gamma(t)``.  No
neural field participates: there is no extraction, no re-distancing, no Eikonal
term, no representation audit and no conversion gate anywhere in the loop.  The
network argument of the shared optimizer is a parameterless placeholder and the
``curve_only`` policy guarantees it is never evaluated.

The parameter is polar angle at initialization and free thereafter, and nothing
refits to arc length.  That is the point of the experiment: in polar angle the
five-lobed target is exactly ``a_1 cos t + a_4/b_4 + a_6/b_6``, so band six
contains it to machine precision, while in arc length it is not band-limited at
any practical bandwidth.  See docs/iterations/cartesian_fourier/iteration_01.

The reference this is matched to is the radial run
``results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904``.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from typing import Any, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parent
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"
for _path in (REPOSITORY_ROOT, SOLVERS_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from run_sdf_inverse_comparison import (  # noqa: E402
    _build_problem,
    _build_target,
    _comma_separated_floats,
    _objective_metrics,
    _ring_scan,
)
from run_mlp_sdf_inverse_comparison import (  # noqa: E402
    CONTINUATION_CUMULATIVE_FREQUENCIES,
    CONTINUATION_NONE,
    CONTINUATION_STRATEGIES,
    _effective_stage_budget,
    _frequency_continuation_plan,
    _initial_teacher,
    _jsonable,
    _mode_budget,
    _prepare_output,
)
from sdf_inverse import (  # noqa: E402
    AlternatingNeuralInverseConfig,
    ComplexScatteredData,
    NeuralRedistanceConfig,
    build_ordered_sdf_geometry,
    maximum_curve_set_distance,
    predict_paired_curve_response,
    run_alternating_neural_inverse,
)
from sdf_inverse.curve_updates import (  # noqa: E402
    cartesian_fourier_state_curve,
    fit_cartesian_fourier_curve_state,
)

GENERATED_NAMES = (
    "metrics.json",
    "summary.md",
    "kress_trajectory.csv",
    "kress_responses.npz",
)

TRAJECTORY_FIELDNAMES = (
    "iteration",
    "stage",
    "stage_iteration",
    "stage_train_frequencies_ghz",
    "stage_maximum_mode",
    "loss",
    "relative_l2_error",
    "applied_damping",
    "accepted_backtrack_count",
    "maximum_coefficient_step_m",
    "curve_change_m",
    "maximum_boundary_error_m",
    "speed_ratio_before",
    "speed_ratio_after",
    "regauge_rms_m",
    "regauge_maximum_m",
    "radial_spectral_tail_rms_m",
    "trust_region_predicted_relative_change",
    "accepted_step_predicted_relative_change",
    "evaluation_count",
    "maximum_system_residual",
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("circle", "star"), default="star")
    parser.add_argument("--initial-shape", choices=("circle", "ellipse", "star"), default="ellipse")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--train-ghz", type=_comma_separated_floats, default=(0.5, 1.5, 2.5))
    parser.add_argument("--holdout-ghz", type=_comma_separated_floats, default=(0.25, 1.0, 2.0))
    parser.add_argument("--num-pairs", type=int, default=24)
    parser.add_argument("--num-nodes", type=int, default=None)
    parser.add_argument(
        "--maximum-mode",
        type=int,
        default=None,
        help=(
            "Active Cartesian band. Defaults to the radial modal budget plus "
            "one: multiplying radius harmonics through K by (cos t, sin t) "
            "raises the Cartesian bandwidth to K + 1, and for the analytic "
            "star that bound is exact."
        ),
    )
    parser.add_argument("--outer-iterations", type=int, default=150)
    parser.add_argument("--maximum-modal-update-mm", type=float, default=2.0)
    parser.add_argument("--geometry-convergence-tolerance-mm", type=float, default=0.2)
    parser.add_argument(
        "--continuation-strategy",
        choices=CONTINUATION_STRATEGIES,
        default=CONTINUATION_CUMULATIVE_FREQUENCIES,
    )
    parser.add_argument("--tangential-penalty-weight", type=float, default=0.0)
    parser.add_argument("--maximum-speed-ratio", type=float, default=16.0)
    parser.add_argument("--no-regauge", dest="regauge", action="store_false")
    parser.set_defaults(regauge=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    args.train_ghz = tuple(args.train_ghz)
    args.holdout_ghz = tuple(args.holdout_ghz)
    return args


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=REPOSITORY_ROOT, text=True
            ).strip()
        )
    except Exception:  # pragma: no cover - provenance only
        return {"commit": None, "dirty": None}
    return {"commit": commit, "dirty": dirty}


def _cartesian_spectrum(state: object) -> dict[str, Any]:
    cosine = np.asarray(state.cosine_coefficients, dtype=np.float64)
    sine = np.asarray(state.sine_coefficients, dtype=np.float64)
    amplitude = np.sqrt(
        np.sum(cosine * cosine, axis=1) + np.sum(sine * sine, axis=1)
    )
    return {
        "cosine_coefficients_m": cosine.tolist(),
        "sine_coefficients_m": sine.tolist(),
        "mode_amplitude_m": amplitude.tolist(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    target = _build_target(args.target)
    tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    if args.num_nodes is None:
        args.num_nodes = target.default_num_nodes
    geometry_config = target.geometry_config(args.num_nodes)

    teacher = _initial_teacher(args.initial_shape)
    raw_curve = build_ordered_sdf_geometry(teacher, geometry_config).curve

    source_points, receiver_points = _ring_scan(
        center=target.center, standoff=0.30, num_pairs=args.num_pairs
    )
    frequencies = tuple(args.train_ghz) + tuple(args.holdout_ghz)
    all_problem = _build_problem(frequencies, source_points, receiver_points)
    train_problem = _build_problem(args.train_ghz, source_points, receiver_points)

    radial_budget = _mode_budget(train_problem, raw_curve.points, None)
    maximum_mode = (
        radial_budget["maximum_mode"] + 1
        if args.maximum_mode is None
        else int(args.maximum_mode)
    )
    if args.output_dir is None:
        args.output_dir = Path("results/inverse/cartesian_fourier") / (
            f"cartesian-k{maximum_mode}-{args.initial_shape}-to-{target.output_tag}-kress-{tag}"
        )
    output = _prepare_output(
        args.output_dir
        if args.output_dir.is_absolute()
        else REPOSITORY_ROOT / args.output_dir,
        args.overwrite,
    )

    initial_state = fit_cartesian_fourier_curve_state(
        raw_curve,
        maximum_mode=maximum_mode,
        component_id="cartesian_fourier_inverse_curve",
        source_identifier=f"{args.initial_shape}_level_set_extraction",
    )
    initial_curve = cartesian_fourier_state_curve(
        initial_state, geometry_config=geometry_config, full_validation=True
    )
    initial_set_distance = max(
        maximum_curve_set_distance(raw_curve.points, initial_curve.points),
        maximum_curve_set_distance(initial_curve.points, raw_curve.points),
    )
    print(
        f"[initialization] wrong {args.initial_shape} -> Cartesian K{maximum_mode} "
        f"polar-angle state: projection="
        f"{1.0e3 * initial_state.initial_projection_rms_m:.3f}/"
        f"{1.0e3 * initial_state.initial_projection_maximum_m:.3f} mm RMS/max, "
        f"set-max={1.0e3 * initial_set_distance:.3f} mm",
        flush=True,
    )
    print("[initialization] no neural field is constructed or consulted", flush=True)

    print(f"[oracle] {target.truth_oracle}", flush=True)
    truth = target.observations(all_problem)
    oracle_diagnostics = target.oracle_diagnostics(all_problem)

    continuation_plan = _frequency_continuation_plan(
        args.train_ghz, args.outer_iterations, strategy=args.continuation_strategy
    )
    print(
        f"[modes] radial budget {radial_budget['maximum_mode']} at "
        f"ka_max={radial_budget['maximum_exterior_ka']:.2f} -> Cartesian band "
        f"{maximum_mode} ({4 * maximum_mode + 2} coefficients, "
        f"{4 * maximum_mode + 1} after the phase gauge)",
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

    # The redistance configuration is structurally required by the shared
    # optimizer and is never used: ``curve_only`` performs no neural work.
    unused_redistance = NeuralRedistanceConfig(bounds=geometry_config.bounds)
    inverse_config = AlternatingNeuralInverseConfig(
        redistance=unused_redistance,
        max_iterations=args.outer_iterations,
        maximum_mode=maximum_mode,
        maximum_modal_field_update_m=1.0e-3 * args.maximum_modal_update_mm,
        geometry_change_tolerance_m=1.0e-3 * args.geometry_convergence_tolerance_mm,
        direct_curve_retraction="cartesian_fourier",
        distillation_policy="curve_only",
        tangential_penalty_weight=args.tangential_penalty_weight,
        maximum_parameter_speed_ratio=args.maximum_speed_ratio,
        regauge_to_polar_angle=args.regauge,
    )

    solver = "kress"
    placeholder = torch.nn.Identity()
    initial_all = predict_paired_curve_response(
        initial_curve, all_problem, geometry_config, solver=solver
    )
    train_count = len(args.train_ghz)
    initial_train = _objective_metrics(
        initial_all.scattered_response[:, :train_count], truth[:, :train_count]
    )
    initial_holdout = _objective_metrics(
        initial_all.scattered_response[:, train_count:], truth[:, train_count:]
    )
    initial_boundary_error = float(
        np.max(np.abs(target.boundary_distances(initial_curve.points)))
    )
    print(
        f"[initial] train rel={initial_train[1]:.6e} holdout rel={initial_holdout[1]:.6e} "
        f"boundary max={initial_boundary_error:.6e} m",
        flush=True,
    )

    stream = (output / "kress_trajectory.csv").open("w", encoding="utf-8", newline="")
    writer = csv.DictWriter(stream, fieldnames=TRAJECTORY_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    stream.flush()

    rows: list[dict[str, Any]] = []
    stage_metadata: list[dict[str, Any]] = []
    current_curve = initial_curve
    current_state = initial_state
    accepted_before = 0
    evaluation_offset = 0
    cumulative_residual = 0.0

    print("\n[KRESS] direct Cartesian Fourier inverse", flush=True)
    for stage_plan in continuation_plan:
        budget = _effective_stage_budget(
            stage=stage_plan.stage,
            stage_count=len(continuation_plan),
            planned_max_iterations=stage_plan.max_iterations,
            total_iterations=args.outer_iterations,
            accepted_updates_before_stage=accepted_before,
        )
        stage_problem = _build_problem(
            stage_plan.train_frequencies_ghz, source_points, receiver_points
        )
        stage_frequency_count = len(stage_plan.train_frequencies_ghz)
        stage_data = ComplexScatteredData(stage_problem, truth[:, :stage_frequency_count])
        automatic = _mode_budget(stage_problem, current_curve.points, None)
        stage_mode = (
            maximum_mode
            if args.continuation_strategy == CONTINUATION_NONE
            else min(maximum_mode, automatic["maximum_mode"] + 1)
        )
        stage_config = replace(
            inverse_config, max_iterations=budget, maximum_mode=stage_mode
        )
        print(
            f"  stage {stage_plan.stage}/{len(continuation_plan)} "
            f"train={','.join(format(v, 'g') for v in stage_plan.train_frequencies_ghz)} GHz "
            f"band=0..{stage_mode} budget={budget}",
            flush=True,
        )

        def progress(
            item: Any,
            *,
            stage_number: int = stage_plan.stage,
            stage_frequencies: tuple[float, ...] = stage_plan.train_frequencies_ghz,
            band: int = stage_mode,
            prior_evaluations: int = evaluation_offset,
            prior_residual: float = cumulative_residual,
        ) -> None:
            points = np.asarray(item.geometry_points, dtype=np.float64)
            row = {
                "iteration": len(rows),
                "stage": stage_number,
                "stage_iteration": item.iteration,
                "stage_train_frequencies_ghz": ",".join(
                    format(v, "g") for v in stage_frequencies
                ),
                "stage_maximum_mode": band,
                "loss": item.loss,
                "relative_l2_error": item.relative_l2_error,
                "applied_damping": item.applied_damping,
                "accepted_backtrack_count": item.accepted_backtrack_count,
                "maximum_coefficient_step_m": float(
                    np.max(np.abs(np.asarray(item.modal_step, dtype=np.float64)))
                ),
                "curve_change_m": item.curve_change_m,
                "maximum_boundary_error_m": float(
                    np.max(np.abs(target.boundary_distances(points)))
                ),
                "regauge_rms_m": item.arclength_refit_rms_m,
                "regauge_maximum_m": item.arclength_refit_maximum_m,
                "speed_ratio_before": item.arclength_speed_ratio_before,
                "speed_ratio_after": item.arclength_speed_ratio_after,
                "radial_spectral_tail_rms_m": item.radial_spectral_tail_rms_m,
                "trust_region_predicted_relative_change": (
                    item.trust_region_predicted_relative_change
                ),
                "accepted_step_predicted_relative_change": (
                    item.accepted_step_predicted_relative_change
                ),
                "evaluation_count": prior_evaluations + item.evaluation_count,
                "maximum_system_residual": max(
                    prior_residual, item.maximum_system_residual
                ),
            }
            rows.append(row)
            writer.writerow(row)
            stream.flush()
            print(
                f"    KRESS iter={row['iteration']:02d} stage_iter={item.iteration:02d} "
                f"loss={item.loss:.4e} rel={item.relative_l2_error:.4e} "
                f"backtracks={item.accepted_backtrack_count} "
                f"step={1.0e3 * item.curve_change_m:.3f} mm "
                f"boundary={1.0e3 * row['maximum_boundary_error_m']:.4f} mm "
                f"regauge={1.0e6 * item.arclength_refit_maximum_m:.2f} um "
                f"speed={item.arclength_speed_ratio_before:.3f}->"
                f"{item.arclength_speed_ratio_after:.3f}",
                flush=True,
            )

        stage_result = run_alternating_neural_inverse(
            placeholder,
            stage_data,
            geometry_config,
            solver=solver,
            config=stage_config,
            progress_callback=progress,
            initial_curve=current_curve,
            initial_cartesian_curve_state=current_state,
            curve_forward_predictor=predict_paired_curve_response,
        )
        if stage_result.final_cartesian_curve_state is None:
            raise RuntimeError("Cartesian stage did not return its authoritative state.")
        if stage_result.representation_evaluated:
            raise RuntimeError("A neural representation was evaluated; this run must not.")
        current_curve = stage_result.final_curve
        current_state = stage_result.final_cartesian_curve_state
        stage_accepted = len(stage_result.iterations) - 1
        accepted_before += stage_accepted
        evaluation_offset += stage_result.total_evaluation_count
        cumulative_residual = max(
            cumulative_residual, stage_result.final_iteration.maximum_system_residual
        )
        stage_metadata.append(
            {
                "stage": stage_plan.stage,
                "train_frequencies_ghz": list(stage_plan.train_frequencies_ghz),
                "max_iterations": budget,
                "maximum_mode": stage_mode,
                "automatic_radial_mode_budget": _jsonable(automatic),
                "accepted_updates": stage_accepted,
                "converged": stage_result.converged,
                "stop_reason": stage_result.stop_reason,
                "reconstruction_stop_reason": stage_result.reconstruction_stop_reason,
                "initial_loss": stage_result.initial_iteration.loss,
                "final_loss": stage_result.final_iteration.loss,
                "evaluation_count": stage_result.total_evaluation_count,
                "infeasible_evaluation_count": stage_result.infeasible_evaluation_count,
                "full_validation_rejection_count": (
                    stage_result.full_validation_rejection_count
                ),
            }
        )
    stream.close()

    final_all = predict_paired_curve_response(
        current_curve, all_problem, geometry_config, solver=solver
    )
    final_train = _objective_metrics(
        final_all.scattered_response[:, :train_count], truth[:, :train_count]
    )
    final_holdout = _objective_metrics(
        final_all.scattered_response[:, train_count:], truth[:, train_count:]
    )
    final_boundary_error = float(
        np.max(np.abs(target.boundary_distances(current_curve.points)))
    )
    np.savez_compressed(
        output / "kress_responses.npz",
        truth=truth,
        initial_prediction=initial_all.scattered_response,
        final_prediction=final_all.scattered_response,
        initial_points=np.asarray(initial_curve.points, dtype=np.float64),
        final_points=np.asarray(current_curve.points, dtype=np.float64),
        frequencies_ghz=np.asarray(frequencies, dtype=np.float64),
    )

    command = shlex.join([sys.executable, str(Path(__file__).name), *(sys.argv[1:] if argv is None else list(argv))])
    metrics = {
        "schema": 1,
        "experiment": "direct_cartesian_fourier_inverse",
        "neural_field": "absent: curve_only policy with a parameterless placeholder",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "provenance": {
            "git": _git_state(),
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "plan": "docs/iterations/cartesian_fourier/iteration_01/03_plan.md",
        "reference_run": (
            "results/inverse/radial_fourier/"
            "mlp-radial-continuation-k5-ellipse-to-star-kress-20260904"
        ),
        "target": args.target,
        "initial_shape": args.initial_shape,
        "train_frequencies_ghz": list(args.train_ghz),
        "holdout_frequencies_ghz": list(args.holdout_ghz),
        "num_pairs": args.num_pairs,
        "geometry_config": _jsonable(asdict(geometry_config)),
        "chart": {
            "kind": "cartesian_fourier_polar_angle_parameter",
            "maximum_mode": maximum_mode,
            "stored_coefficients": 4 * maximum_mode + 2,
            "active_after_phase_gauge": 4 * maximum_mode + 1,
            "arclength_refit": False,
            "radial_mode_budget": _jsonable(radial_budget),
            "coefficient_order": (
                "c_0x,c_0y,c_1x,c_1y,...,c_Kx,c_Ky,s_1x,s_1y,...,s_Kx,s_Ky"
            ),
            "initial_projection_rms_m": initial_state.initial_projection_rms_m,
            "initial_projection_maximum_m": initial_state.initial_projection_maximum_m,
            "initial_projection_set_distance_m": initial_set_distance,
            "initial_spectrum": _cartesian_spectrum(initial_state),
            "final_spectrum": _cartesian_spectrum(current_state),
        },
        "inverse_config": _jsonable(asdict(inverse_config)),
        "continuation_stages": stage_metadata,
        "oracle_diagnostics": _jsonable(oracle_diagnostics),
        "truth_oracle": target.truth_oracle,
        "results": {
            # Each stage contributes its own iteration-zero baseline row, so
            # the row count overstates accepted updates by one per stage.
            "accepted_updates": sum(
                stage["accepted_updates"] for stage in stage_metadata
            ),
            "trajectory_rows": len(rows),
            "initial_train_relative_l2": initial_train[1],
            "final_train_relative_l2": final_train[1],
            "initial_holdout_relative_l2": initial_holdout[1],
            "final_holdout_relative_l2": final_holdout[1],
            "initial_maximum_boundary_error_m": initial_boundary_error,
            "final_maximum_boundary_error_m": final_boundary_error,
            "stop_reason": stage_metadata[-1]["stop_reason"],
        },
        "parity_reference": {
            "final_train_relative_l2": 1.068e-08,
            "final_holdout_relative_l2": 1.339e-08,
            "final_maximum_boundary_error_m": 2.570e-10,
            "accepted_updates": 44,
        },
        "parity_gates": {
            "train_relative_l2_max": 1.0e-07,
            "holdout_relative_l2_max": 1.0e-07,
            "maximum_boundary_error_max_m": 1.0e-08,
        },
    }
    metrics["parity_achieved"] = bool(
        final_train[1] <= 1.0e-07
        and final_holdout[1] <= 1.0e-07
        and final_boundary_error <= 1.0e-08
    )
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    summary = [
        "# Direct Cartesian Fourier inverse (no MLP)",
        "",
        f"Target: `{args.target}`; initialization contour: wrong `{args.initial_shape}`.",
        "",
        "The accepted optimization state is a Cartesian Fourier curve in the",
        "polar-angle parameter at band "
        f"`K={maximum_mode}` ({4 * maximum_mode + 2} coefficients,",
        f"{4 * maximum_mode + 1} active after the exact phase gauge is removed).",
        "No neural field is constructed, evaluated, trained or audited, and no",
        "arc-length refit occurs at any point.",
        "",
        "| Quantity | Initial | Final | Radial reference final |",
        "|---|---:|---:|---:|",
        f"| Train rel. L2 | {initial_train[1]:.3e} | {final_train[1]:.3e} | 1.068e-08 |",
        f"| Holdout rel. L2 | {initial_holdout[1]:.3e} | {final_holdout[1]:.3e} | 1.339e-08 |",
        f"| Max boundary error | {initial_boundary_error:.3e} m | {final_boundary_error:.3e} m | 2.570e-10 m |",
        f"| Accepted updates | - | {sum(s['accepted_updates'] for s in stage_metadata)} | 44 |",
        "",
        f"Parity gates met: **{metrics['parity_achieved']}** "
        "(train and holdout `<= 1e-07`, boundary error `<= 1e-08 m`).",
        "",
        f"Stop reason: `{stage_metadata[-1]['stop_reason']}`.",
        "",
        "One-time polar-angle projection of the initial contour: "
        f"`{1.0e3 * initial_state.initial_projection_rms_m:.3f}` mm RMS / "
        f"`{1.0e3 * initial_state.initial_projection_maximum_m:.3f}` mm maximum. "
        "Every later state is reached by increment, never by refitting.",
        "",
    ]
    (output / "summary.md").write_text("\n".join(summary))
    print("\n" + "\n".join(summary[10:18]), flush=True)
    print(f"[output] {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
