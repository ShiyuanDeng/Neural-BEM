"""Cheap driver-level regressions for the alternating MLP experiment."""

from __future__ import annotations

import csv
from dataclasses import asdict
import json
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("torch")

from sdf_inverse import AlternatingNeuralInverseConfig, NeuralRedistanceConfig
from run_mlp_sdf_inverse_comparison import (
    CONTINUATION_CUMULATIVE_FREQUENCIES,
    CONTINUATION_NONE,
    CONTINUATION_PROGRESSIVE_MODES,
    TRAJECTORY_FIELDNAMES,
    _TrajectoryEntry,
    _build_problem,
    _continuation_metrics_summary,
    _continuation_stage_maximum_mode,
    _effective_stage_budget,
    _frequency_continuation_plan,
    _incremental_redistance_config,
    _jsonable,
    _mode_budget,
    _parse_args,
    _prepare_output,
    _progressive_mode_stage_count,
    _redistance_config,
    _ring_scan,
    _stage_inverse_config,
    _trajectory_row,
    _write_trajectory,
)


def test_default_budget_reaches_past_warmup_and_uses_submillimetre_projection_gates(
    tmp_path,
) -> None:
    args = _parse_args(["--output-dir", str(tmp_path / "bundle")])
    redistance = _redistance_config(args, ((0.3, 0.3), (0.7, 0.7)))

    assert args.outer_iterations == 60
    assert redistance.minimum_steps > redistance.warmup_steps
    assert redistance.boundary_max_tolerance_m == pytest.approx(5.0e-4)
    assert args.maximum_redistance_drift_mm == pytest.approx(1.5)
    assert args.geometry_convergence_tolerance_mm == pytest.approx(0.2)
    assert args.maximum_modal_update_mm == pytest.approx(2.0)
    assert args.maximum_spectral_tail_growth_mm is None
    assert args.continuation_strategy == CONTINUATION_CUMULATIVE_FREQUENCIES
    assert args.frequency_continuation is True


def test_incremental_redistance_keeps_initial_fit_settings_and_changes_only_warm_start_controls(
    tmp_path,
) -> None:
    args = _parse_args(["--output-dir", str(tmp_path / "bundle")])
    initialization = _redistance_config(args, ((0.3, 0.3), (0.7, 0.7)))
    initialization_before = asdict(initialization)

    incremental = _incremental_redistance_config(initialization)

    assert initialization.warmup_steps == 150
    assert initialization.minimum_steps == 151
    assert initialization.boundary_weight == pytest.approx(200.0)
    assert asdict(initialization) == initialization_before
    expected = dict(initialization_before)
    expected.update(
        warmup_steps=0,
        minimum_steps=100,
        boundary_weight=2000.0,
    )
    assert asdict(incremental) == expected


def test_incremental_redistance_caps_minimum_steps_at_short_step_budget() -> None:
    base = NeuralRedistanceConfig(
        bounds=((0.3, 0.3), (0.7, 0.7)),
        max_steps=37,
        minimum_steps=37,
        warmup_steps=9,
        boundary_weight=200.0,
    )

    incremental = _incremental_redistance_config(base)

    assert incremental.minimum_steps == 37
    assert incremental.warmup_steps == 0
    assert incremental.boundary_weight == pytest.approx(2000.0)


def test_distinct_initial_and_incremental_redistance_configs_remain_in_json_provenance(
    tmp_path,
) -> None:
    args = _parse_args(["--output-dir", str(tmp_path / "bundle")])
    initialization = _redistance_config(args, ((0.3, 0.3), (0.7, 0.7)))
    incremental = _incremental_redistance_config(initialization)
    inverse = AlternatingNeuralInverseConfig(redistance=incremental)
    payload = _jsonable(
        {
            "initial_redistance": {"config": asdict(initialization)},
            "inverse_config": asdict(inverse),
        }
    )

    restored = json.loads(json.dumps(payload))

    assert restored["initial_redistance"]["config"]["warmup_steps"] == 150
    assert restored["initial_redistance"]["config"]["boundary_weight"] == 200.0
    assert restored["inverse_config"]["redistance"]["warmup_steps"] == 0
    assert restored["inverse_config"]["redistance"]["minimum_steps"] == 100
    assert restored["inverse_config"]["redistance"]["boundary_weight"] == 2000.0


def test_overwrite_removes_stale_derived_visuals_but_keeps_unrelated_files(
    tmp_path,
) -> None:
    output = tmp_path / "bundle"
    output.mkdir()
    stale_video = output / "contour_evolution.mp4"
    stale_plot = output / "convergence.png"
    unrelated = output / "notes.txt"
    for path in (stale_video, stale_plot, unrelated):
        path.write_text("old", encoding="utf-8")

    _prepare_output(output, overwrite=True)

    assert not stale_video.exists()
    assert not stale_plot.exists()
    assert unrelated.read_text(encoding="utf-8") == "old"


def test_automatic_mode_budget_honours_scan_angle_nyquist() -> None:
    sources, receivers = _ring_scan(center=(0.5, 0.5), standoff=0.30, num_pairs=12)
    problem = _build_problem((1.5,), sources, receivers)
    theta = np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False)
    points = np.column_stack((0.5 + 0.065 * np.cos(theta), 0.5 + 0.065 * np.sin(theta)))

    automatic = _mode_budget(problem, points, requested=None)
    explicit = _mode_budget(problem, points, requested=7)

    assert automatic["angular_resolvable_maximum_mode"] == 5
    assert automatic["maximum_mode"] <= 5
    assert explicit["maximum_mode"] == 7
    assert explicit["exceeds_angular_resolution"] is True


def test_explicit_progressive_mode_continuation_keeps_full_band_while_modes_grow() -> None:
    args = _parse_args(
        [
            "--output-dir",
            "unused",
            "--train-ghz",
            "2.5,0.5,1.5",
            "--holdout-ghz",
            "0.25,1.0",
            "--outer-iterations",
            "80",
            "--maximum-mode",
            "5",
            "--progressive-mode-continuation",
        ]
    )
    plan = _frequency_continuation_plan(
        args.train_ghz,
        args.outer_iterations,
        strategy=args.continuation_strategy,
        stage_count=_progressive_mode_stage_count(args.maximum_mode),
    )

    assert args.continuation_strategy == CONTINUATION_PROGRESSIVE_MODES
    assert [stage.train_frequencies_ghz for stage in plan] == [
        (0.5, 1.5, 2.5),
        (0.5, 1.5, 2.5),
        (0.5, 1.5, 2.5),
    ]
    assert [stage.max_iterations for stage in plan] == [20, 20, 40]
    assert sum(stage.max_iterations for stage in plan) == 80
    assert [
        _continuation_stage_maximum_mode(
            stage.stage,
            len(plan),
            final_maximum_mode=5,
            automatic_maximum_mode=5,
        )
        for stage in plan
    ] == [1, 3, 5]


def test_default_plan_is_one_joint_full_band_stage() -> None:
    plan = _frequency_continuation_plan((2.5, 0.5, 1.5), 80)

    assert len(plan) == 1
    assert plan[0].train_frequencies_ghz == (0.5, 1.5, 2.5)
    assert plan[0].max_iterations == 80


def test_explicit_frequency_continuation_retains_sorted_prefixes() -> None:
    args = _parse_args(
        [
            "--output-dir",
            "unused",
            "--train-ghz",
            "2.5,0.5,1.5",
            "--holdout-ghz",
            "0.25,1.0",
            "--frequency-continuation",
        ]
    )
    plan = _frequency_continuation_plan(
        args.train_ghz,
        80,
        strategy=args.continuation_strategy,
    )

    assert args.continuation_strategy == CONTINUATION_CUMULATIVE_FREQUENCIES
    assert args.frequency_continuation is True
    assert [stage.train_frequencies_ghz for stage in plan] == [
        (0.5,),
        (0.5, 1.5),
        (0.5, 1.5, 2.5),
    ]
    assert [stage.max_iterations for stage in plan] == [10, 11, 59]


@pytest.mark.parametrize(
    "flag",
    ["--joint-full-band", "--no-continuation", "--no-frequency-continuation"],
)
def test_joint_full_band_accepts_preferred_and_compatibility_flags(flag: str) -> None:
    args = _parse_args(
        [
            "--output-dir",
            "unused",
            "--train-ghz",
            "2.5,0.5,1.5",
            "--holdout-ghz",
            "0.25,1.0",
            flag,
        ]
    )
    plan = _frequency_continuation_plan(
        args.train_ghz,
        80,
        strategy=args.continuation_strategy,
    )

    assert args.continuation_strategy == CONTINUATION_NONE
    assert args.frequency_continuation is False
    assert len(plan) == 1
    assert plan[0].train_frequencies_ghz == (0.5, 1.5, 2.5)
    assert plan[0].max_iterations == 80


def test_original_enabled_boolean_remains_a_compatibility_seam() -> None:
    cumulative = _frequency_continuation_plan((1.5, 0.5), 6, enabled=True)
    disabled = _frequency_continuation_plan((1.5, 0.5), 6, enabled=False)

    assert [stage.train_frequencies_ghz for stage in cumulative] == [
        (0.5,),
        (0.5, 1.5),
    ]
    assert [stage.train_frequencies_ghz for stage in disabled] == [
        (0.5, 1.5)
    ]


@pytest.mark.parametrize(
    ("strategy", "stage_count", "expected_frequency", "expected_any"),
    [
        (CONTINUATION_NONE, None, False, False),
        (CONTINUATION_PROGRESSIVE_MODES, 3, False, True),
        (CONTINUATION_CUMULATIVE_FREQUENCIES, None, True, True),
    ],
)
def test_continuation_metrics_preserve_legacy_frequency_enabled_meaning(
    strategy: str,
    stage_count: int | None,
    expected_frequency: bool,
    expected_any: bool,
) -> None:
    plan = _frequency_continuation_plan(
        (0.5, 1.5, 2.5),
        80,
        strategy=strategy,
        stage_count=stage_count,
    )

    summary = _continuation_metrics_summary(strategy, plan, 80)

    assert summary["enabled"] is expected_frequency
    assert summary["frequency_staging_enabled"] is expected_frequency
    assert summary["continuation_enabled"] is expected_any


def test_continuation_cli_selectors_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        _parse_args(
            [
                "--output-dir",
                "unused",
                "--frequency-continuation",
                "--joint-full-band",
            ]
        )


def test_continuation_exposes_center_then_ellipse_then_star_modes() -> None:
    modes = [
        _continuation_stage_maximum_mode(
            stage,
            3,
            final_maximum_mode=5,
            automatic_maximum_mode=5,
        )
        for stage in (1, 2, 3)
    ]

    assert modes == [1, 3, 5]


def test_frequency_continuation_uses_the_active_wave_budget_not_odd_mode_stages() -> None:
    modes = [
        _continuation_stage_maximum_mode(
            stage,
            3,
            final_maximum_mode=5,
            automatic_maximum_mode=automatic,
            strategy=CONTINUATION_CUMULATIVE_FREQUENCIES,
        )
        for stage, automatic in ((1, 3), (2, 7), (3, 9))
    ]

    # The 0.5 GHz stage must contain K=2 so it can remove an ellipse's leading
    # anisotropy; 1,3,5 is reserved for explicit modal continuation.
    assert modes == [3, 5, 5]


@pytest.mark.parametrize(
    ("maximum_mode", "expected_count", "expected_modes"),
    [
        (1, 1, [1]),
        (2, 2, [1, 2]),
        (4, 3, [1, 3, 4]),
        (5, 3, [1, 3, 5]),
    ],
)
def test_progressive_mode_stage_count_covers_odd_and_even_limits(
    maximum_mode: int,
    expected_count: int,
    expected_modes: list[int],
) -> None:
    count = _progressive_mode_stage_count(maximum_mode)
    modes = [
        _continuation_stage_maximum_mode(
            stage,
            count,
            final_maximum_mode=maximum_mode,
            automatic_maximum_mode=maximum_mode,
        )
        for stage in range(1, count + 1)
    ]

    assert count == expected_count
    assert modes == expected_modes


def test_unused_warm_stage_budget_is_reserved_for_final_stage() -> None:
    plan = _frequency_continuation_plan(
        (0.5, 1.5, 2.5),
        80,
        strategy=CONTINUATION_PROGRESSIVE_MODES,
        stage_count=3,
    )
    accepted_before = 0
    effective = []
    accepted_by_warm_stage = (12, 0)
    for stage_plan, accepted in zip(plan[:2], accepted_by_warm_stage):
        effective.append(
            _effective_stage_budget(
                stage=stage_plan.stage,
                stage_count=len(plan),
                planned_max_iterations=stage_plan.max_iterations,
                total_iterations=80,
                accepted_updates_before_stage=accepted_before,
            )
        )
        accepted_before += accepted
    effective.append(
        _effective_stage_budget(
            stage=3,
            stage_count=3,
            planned_max_iterations=plan[-1].max_iterations,
            total_iterations=80,
            accepted_updates_before_stage=accepted_before,
        )
    )

    assert effective == [20, 20, 68]
    assert sum(accepted_by_warm_stage) + effective[-1] == 80


@pytest.mark.parametrize(
    ("accepted_before", "expected_final_budget"),
    [(0, 80), (12, 68), (40, 40)],
)
def test_final_stage_budget_is_exactly_the_remaining_global_budget(
    accepted_before: int,
    expected_final_budget: int,
) -> None:
    assert _effective_stage_budget(
        stage=3,
        stage_count=3,
        planned_max_iterations=40,
        total_iterations=80,
        accepted_updates_before_stage=accepted_before,
    ) == expected_final_budget


def test_every_stage_resets_lm_damping_to_the_base_configuration() -> None:
    redistance = NeuralRedistanceConfig(
        bounds=((0.3, 0.3), (0.7, 0.7)),
        eikonal_rms_tolerance=0.1,
    )
    base = AlternatingNeuralInverseConfig(
        redistance=redistance,
        initial_damping=1.0e-3,
    )

    first = _stage_inverse_config(
        base,
        redistance_config=base.redistance,
        max_iterations=20,
        maximum_mode=1,
        spectral_tail_reference_rms_m=1.0e-3,
        audit_seed=1,
    )
    # A preceding solve may finish with an unrelated large damping.  It is
    # intentionally absent from the next-stage construction.
    previous_final_damping = 18.7
    second = _stage_inverse_config(
        base,
        redistance_config=base.redistance,
        max_iterations=20,
        maximum_mode=3,
        spectral_tail_reference_rms_m=2.0e-3,
        audit_seed=2,
    )

    assert previous_final_damping != base.initial_damping
    assert first.initial_damping == pytest.approx(base.initial_damping)
    assert second.initial_damping == pytest.approx(base.initial_damping)


def test_spectral_tail_guard_is_opt_in() -> None:
    args = _parse_args(
        [
            "--output-dir",
            "unused",
            "--maximum-spectral-tail-growth-mm",
            "0.2",
        ]
    )

    assert args.maximum_spectral_tail_growth_mm == pytest.approx(0.2)


def test_modal_update_cap_is_configurable_and_must_be_positive() -> None:
    args = _parse_args(
        [
            "--output-dir",
            "unused",
            "--maximum-modal-update-mm",
            "1.25",
        ]
    )

    assert args.maximum_modal_update_mm == pytest.approx(1.25)
    with pytest.raises(SystemExit):
        _parse_args(
            [
                "--output-dir",
                "unused",
                "--maximum-modal-update-mm",
                "0",
            ]
        )


def test_continuation_rejects_budget_that_cannot_visit_every_stage() -> None:
    with pytest.raises(ValueError, match="at least the number"):
        _frequency_continuation_plan(
            (0.5, 1.5, 2.5),
            2,
            strategy=CONTINUATION_PROGRESSIVE_MODES,
            stage_count=3,
        )

    single = _frequency_continuation_plan(
        (0.5, 1.5, 2.5),
        1,
        strategy=CONTINUATION_NONE,
    )
    assert single[0].max_iterations == 1


def _trajectory_item(
    global_iteration: int,
    maximum_mode: int,
    modal_step: np.ndarray | None = None,
) -> SimpleNamespace:
    values = {name: 0.0 for name in TRAJECTORY_FIELDNAMES[6:]}
    values["iteration"] = global_iteration
    values["modal_step"] = (
        np.asarray(modal_step, dtype=np.float64)
        if modal_step is not None
        else np.linspace(
            -float(maximum_mode),
            float(maximum_mode),
            2 * maximum_mode + 1,
        )
    )
    values["redistance_stop_reason"] = "initialized"
    return SimpleNamespace(**values)


def test_trajectory_records_consecutive_global_indices_and_stage_baselines(
    tmp_path,
) -> None:
    entries = (
        _TrajectoryEntry(_trajectory_item(0, 3), 1, 0, (0.5,), 3),
        # A new objective keeps its iteration-zero baseline while receiving a
        # new consecutive index in the combined trajectory.
        _TrajectoryEntry(_trajectory_item(1, 5), 2, 0, (0.5, 1.5), 5),
    )
    path = tmp_path / "trajectory.csv"

    _write_trajectory(path, entries)

    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["iteration"] for row in rows] == ["0", "1"]
    assert [row["stage"] for row in rows] == ["1", "2"]
    assert [row["stage_iteration"] for row in rows] == ["0", "0"]
    assert rows[1]["stage_train_frequencies_ghz"] == "0.5,1.5"
    assert rows[1]["stage_maximum_mode"] == "5"
    np.testing.assert_allclose(
        np.fromstring(rows[0]["modal_step_m"], sep=","),
        np.linspace(-3.0, 3.0, 7),
    )
    np.testing.assert_allclose(
        np.fromstring(rows[1]["modal_step_m"], sep=","),
        np.linspace(-5.0, 5.0, 11),
    )


@pytest.mark.parametrize("coefficient_count", [6, 8])
def test_trajectory_row_rejects_wrong_length_modal_step(
    coefficient_count: int,
) -> None:
    entry = _TrajectoryEntry(
        _trajectory_item(0, 3, np.zeros(coefficient_count)),
        1,
        0,
        (0.5, 1.5, 2.5),
        3,
    )

    with pytest.raises(ValueError, match="exactly 7 finite coefficients"):
        _trajectory_row(entry)


@pytest.mark.parametrize("nonfinite", [np.nan, np.inf, -np.inf])
def test_write_trajectory_rejects_nonfinite_modal_step(
    tmp_path,
    nonfinite: float,
) -> None:
    modal_step = np.zeros(7)
    modal_step[3] = nonfinite
    entry = _TrajectoryEntry(
        _trajectory_item(0, 3, modal_step),
        1,
        0,
        (0.5, 1.5, 2.5),
        3,
    )

    with pytest.raises(ValueError, match="exactly 7 finite coefficients"):
        _write_trajectory(tmp_path / "trajectory.csv", (entry,))
