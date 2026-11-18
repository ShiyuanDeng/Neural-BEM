"""Read the clean TG-002 contrast-4 records and score their saved curves on CPU."""
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from bem_inverse.continuation.geometry import resize
from bem_inverse.io import curve_from, read
from experiments.benchmark import campaign, scenes
from experiments.comparison.scoring import PROTOCOL, region, region_scores

ROOT = campaign.ROOT
BASE = ROOT / "results/bem/default_clean_uc_fc"
ARMS = ROOT / "results/bem/stage_stops/2026-11-18"
OUT = ROOT / "results/bem/stage_scheduling/2026-11-18/stage_stops"
NOTE = ROOT / "docs/iterations/investigate_bem_stage_scheduling/01_trace_stage_stops_and_shape_bands"
NAMES = {"kite": "Kite", "c_shape": "C-shape", "aphex_twin": "Aphex Twin", "cog": "Cog"}


def shape_region(curve):
    return region([scenes.LENGTH * curve.values(PROTOCOL["curve_samples"])])[0]


def write_rows(name, rows):
    with (OUT / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def stop_cause(stage, cap, seconds_limit):
    work = stage["work"]
    outcome = stage["outcome"]
    if outcome == "NORMAL_OPTIMIZER_RETURN":
        if stage["stop"] == "maximum_iterations":
            assert stage["accepted_steps"] == cap
            return "iteration cap"
        if stage["stop"] == "no_decreasing_step":
            assert stage["accepted_steps"] < cap
            return "exhausted trial steps"
        return stage["stop"]  # Other controls also have gradient/loss tolerance returns.
    if outcome == "STAGE_QUOTA_REACHED":
        assert "stage quota" in stage["detail"] and work["seconds"] < seconds_limit
        return "stage work quota"
    if outcome == "TRIAL_WALL_LIMIT":
        assert work["seconds"] >= seconds_limit and work["work_units"] < work["cap"]
        return "whole-fit time limit"
    if outcome == "NUMERICAL_FAILURE" and stage["physics_failures"]:
        return "forward-solver refusal"
    raise ValueError((outcome, stage["detail"]))


def original(path, seconds_limit):
    fit = read(path)
    scene = fit["scene"]
    case = campaign.row(fit["case"])
    curve = curve_from(read(ROOT / case["initial"]))
    truth_curve = curve_from(read(ROOT / case["truth"]))
    truth = shape_region(truth_curve)

    def score(curve):
        return 100 * region_scores(shape_region(curve), truth)["area_error"]

    stages = {s["stage"]: s for s in fit["stages"]}
    rows, adverse, last_moving = [], None, None
    for event in fit["decisions"]:
        if event["reason"] == "policy cleanup entered":
            curve = curve_from(event["curve"])
        if event["reason"] != "resolved stage entered":
            continue
        op = event["operation"]["stage"]
        label = op["label"]
        stage = stages[label]
        work = stage["work"]
        entry = resize(curve, op["curve_modes"])
        curve = curve_from(stage["curve"])
        area_in, area_out = score(entry), score(curve)
        loss_in, loss_out = stage["initial_loss"], stage["final_loss"]
        number = len(rows) + 1
        if stage["accepted_steps"]:
            last_moving = (number, entry, curve)
        if (adverse is None and loss_in is not None and loss_out < loss_in
                and area_out > area_in + 1e-6):
            adverse = (number, entry, curve)
        frequencies = len(op["frequencies_hz"])
        cause = stop_cause(stage, op["iterations"], seconds_limit)
        charged = work["solves"].get(label + ":candidate", 0)
        proposals = stage["geometry_proposals"]
        refused = None
        if scene in NAMES:
            # A quota after a complete post-acceptance tangent blocks a constructed
            # candidate before the first frequency is charged. All target candidate
            # batches that *started* charged every frequency (including one failure).
            assert charged % frequencies == 0
            tangents = work["solves"].get(label + ":contrast_derivative", 0)
            blocked_candidate = (cause == "stage work quota"
                                 and tangents == frequencies * (stage["accepted_steps"] + 1))
            refused = proposals - charged // frequencies - int(blocked_candidate)
            if cause == "stage work quota":
                next_batch = frequencies if blocked_candidate else 2 * frequencies
                assert work["stage_units"] + next_batch + 12 > work["stage_quota"]
            assert refused >= 0
        rows.append(dict(shape=scene, stage=number, label=label, frequencies=frequencies,
                         update_band=stage["M"], storage_band=stage["K_geometry"],
                         steps=stage["accepted_steps"], cap=op["iterations"],
                         loss_in=loss_in, loss_out=loss_out, area_in_pct=area_in, area_out_pct=area_out,
                         units=work["stage_units"], quota=work["stage_quota"],
                         stage_seconds=stage["seconds"], elapsed_entry_s=event["work"]["seconds"],
                         elapsed_exit_s=work["seconds"], seconds_limit=seconds_limit,
                         geometry_proposals=proposals, slider_refused=refused,
                         physics_failures=len(stage["physics_failures"]),
                         charged_failures=sum(n for key, n in work["failed"].items()
                                              if key.startswith(label + ":")),
                         outcome=stage["outcome"], stop=stage["stop"], cause=cause,
                         source=str(path.relative_to(ROOT))))
    assert len(rows) == len(stages)
    if scene in NAMES:
        assert sum(r["slider_refused"] for r in rows) == fit["geometry_work"]["refused_trials"]
        assert sum(r["physics_failures"] for r in rows) == fit["physics"]["counts"]["failed_evaluations"]
        assert sum(r["charged_failures"] for r in rows) == sum(fit["fit_work"]["failed"].values())
    assert np.isclose(rows[-1]["area_out_pct"], 100 * read(path.with_name("score.json"))["area_error"])
    return rows, adverse or last_moving, truth_curve


def matched_points(scene, initial_area):
    # Outer join on stage and number of accepted steps. Leave unsampled areas empty.
    points = {}
    arms = ["reference", "longer", "wider", "both", "aphex_fourth"]
    for arm in arms:
        path = ARMS / arm / f"{scene}__c4.json"
        if not path.exists():
            continue
        data = read(path)
        if arm == "aphex_fourth":
            for sample in data["history"]:
                points.setdefault((4, sample["iteration"]), {})[arm] = (
                    sample["loss"], 100 * sample["area_error"], sample["contrast"])
            continue
        entry_area = initial_area
        for i, stage in enumerate(data["stages"][:4], 1):
            samples = {int(k): 100 * value for k, value in stage["sampled_area_error"].items()}
            samples[0] = entry_area
            end = stage["accepted_steps"]
            entry_area = samples[end] = 100 * stage["area_error"]
            history = stage["accepted_iteration_loss_contrast"]
            for step, loss, contrast in history:
                points.setdefault((i, step), {})[arm] = (loss, samples.get(step), contrast)
            if not history:
                assert end == 0 and stage["initial_loss"] is None
                points.setdefault((i, 0), {})[arm] = (None, entry_area, stage["contrast"])
    rows = []
    for (i, step), values in sorted(points.items()):
        row = dict(shape=scene, stage=i, accepted_step=step)
        for arm in arms:
            loss, area, contrast = values.get(arm, (None, None, None))
            row.update({arm + "_loss": loss, arm + "_area_pct": area, arm + "_contrast": contrast})
        rows.append(row)
    return rows


def plot_first_adverse(curves):
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.4), facecolor="#fcfcfb")
    for ax, (scene, title) in zip(axes, NAMES.items()):
        (number, entry, exit_curve), truth = curves[scene]
        for curve, label, color, style in [(entry, "Stage entry", "#428391", "-"),
                                           (exit_curve, "Stage exit", "#0b0b0b", "-"),
                                           (truth, "Truth", "#52514e", "--")]:
            ring = curve.values(1024)
            z = np.r_[ring, ring[:1]] * scenes.LENGTH * 1000
            ax.plot(z.real, z.imag, label=label, color=color, linestyle=style)
        ax.set_aspect("equal")
        ax.set_facecolor("#fcfcfb")
        ax.set_title(f"{title} · stage {number}", fontsize=11, color="#0b0b0b")
        ax.set_axis_off()
    fig.legend(*axes[0].get_legend_handles_labels(), ncol=3, loc="lower center",
               bbox_to_anchor=(0.5, 0.08), frameon=False)
    fig.suptitle("How the outline moved while loss fell", color="#0b0b0b")
    fig.subplots_adjust(top=0.81, bottom=0.22, wspace=0.17)
    fig.text(0.5, 0.04, "Clean TG-002, contrast 4 · saved stage boundaries · first setback, or last moving stage for Aphex Twin · scales vary · no new solves",
             ha="center", color="#52514e", fontsize=9)
    figdir = NOTE / "figures"
    figdir.mkdir(exist_ok=True)
    fig.savefig(figdir / "stage_stops_first_adverse.png", dpi=160)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stages, points, curves = [], [], {}
    limit = read(BASE / "run.json")["settings"]["policy"]["fit_seconds"]
    for path in sorted(BASE.glob("*__c4/fit.json")):
        rows, adverse, truth = original(path, limit)
        stages.extend(rows)
        scene = rows[0]["shape"]
        if scene in NAMES:
            curves[scene] = (adverse, truth)
            points.extend(matched_points(scene, rows[0]["area_in_pct"]))
    write_rows("original_stages.csv", stages)
    write_rows("matched_steps.csv", points)
    plot_first_adverse(curves)


if __name__ == "__main__":
    main()
