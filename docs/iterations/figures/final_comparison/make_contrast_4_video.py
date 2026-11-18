"""Render the four early stops from saved stages. Run with PYTHONPATH=solvers:. in EMNerf."""
import subprocess
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path as PlotPath
from shapely.geometry.polygon import orient

from bem_inverse.io import curve_from
from experiments.benchmark import campaign
from experiments.benchmark.scenes import LENGTH
from experiments.comparison.scoring import polygons, region, region_scores
from make_figures import BLUE, INK, MUTED, ORANGE, OUT, RESULTS, draw, nice_name, read

RUN = "default_clean_uc_fc"
CASES = ("kite", "c_shape", "aphex_twin", "cog")
STOP_LABELS = {"TRIAL_WALL_LIMIT": "Time limit", "NUMERICAL_FAILURE": "Numerical stop",
               "COMPLETED_SCHEDULE": "Schedule complete"}
EXTRA, MISSING = "#fac79b", "#c9bce8"


def load_case(shape, run=RUN):
    case = f"{shape}__c4"
    folder = RESULTS / "bem" / run / case
    fit = read(folder / "fit.json")
    score = read(folder / "score.json")
    row = campaign.row(case)
    samples = score["protocol"]["curve_samples"]
    truth = LENGTH * curve_from(read(campaign.ROOT / row["truth"])).values(samples)
    true_region, _ = region([truth])
    stages = fit["stages"]
    endpoints = [(read(campaign.ROOT / row["initial"]), fit["contrast_start"].get("start_contrast", fit["contrast"]))]
    endpoints.extend((stage["curve"], stage.get("contrast", fit["contrast"])) for stage in stages)
    states = []
    for curve, contrast in endpoints:
        points = LENGTH * curve_from(curve).values(samples)
        found, _ = region([points])
        metrics = region_scores(found, true_region)
        states.append(dict(outline=points, contrast=contrast, error=metrics["area_error"],
                           extra=found.difference(true_region), missing=true_region.difference(found),
                           centre_mm=metrics["centroid_mm"], extra_fraction=metrics["excess_area"],
                           missing_fraction=metrics["missing_area"]))
    assert stages[-1]["curve"] == fit["final_curve"]
    np.testing.assert_allclose(states[-1]["error"], score["area_error"], rtol=1e-9)
    operations = {step["operation"]["label"]: step["operation"]["stage"]
                  for step in fit["decisions"] if step["operation"].get("stage")}
    schedule = [operations[stage["stage"]] for stage in stages]
    return dict(shape=shape, truth=truth, states=states, schedule=schedule, stop=STOP_LABELS[fit["outcome"]])


def stage_title(index, case):
    if index == 0:
        return "Start   ·   Centred circle, 65 mm radius"
    stage = case["schedule"][index-1]
    frequencies = np.array(stage["frequencies_hz"]) / 1e9
    if len(frequencies) <= 4:
        band = ", ".join(f"{f:g}" for f in frequencies) + " GHz"
    else:
        band = f"{len(frequencies)} frequencies from {frequencies.min():g} to {frequencies.max():g} GHz"
    return f"Stage {index} of {len(case['schedule'])}   ·   {band}   ·   {stage['M']} shape modes"


def viewport(cases):
    points = 1000 * np.concatenate([p for case in cases for p in
                                    [case["truth"], *(state["outline"] for state in case["states"])]])
    x = (points.real.max() + points.real.min()) / 2
    y = (points.imag.max() + points.imag.min()) / 2
    half = max(np.ptp(points.real), np.ptp(points.imag)) * .54
    return (x-half, x+half), (y-half, y+half)


def show_outline(ax, state, truth, limits):
    for geometry, color in [(state["extra"], EXTRA), (state["missing"], MISSING)]:
        for part in polygons(geometry):
            polygon = orient(part, sign=1)
            rings = [PlotPath(np.asarray(ring.coords)*1000, closed=True)
                     for ring in (polygon.exterior, *polygon.interiors)]
            ax.add_patch(PathPatch(PlotPath.make_compound_path(*rings), facecolor=color, edgecolor="none"))
    draw(ax, state["outline"], BLUE, lw=1.8)
    draw(ax, truth, INK, lw=1.3, ls=(0, (3, 2.5)))
    ax.set(aspect="equal", xlim=limits[0], ylim=limits[1], xticks=[], yticks=[], facecolor="#f4f7f8")
    for spine in ax.spines.values():
        spine.set_visible(False)


def legend(fig):
    fig.legend(handles=[Line2D([], [], color=BLUE, lw=2.5, label="BEM fit"),
                        Line2D([], [], color=INK, lw=1.3, ls="--", label="True boundary"),
                        Patch(color=EXTRA, label="Extra area"), Patch(color=MISSING, label="Missing area")],
               bbox_to_anchor=(.97,.984), loc="upper right", ncol=2, frameon=False, fontsize=11)


def render(cases, folder):
    longest = max(cases, key=lambda case: len(case["schedule"]))
    limits = viewport(cases)
    for i in range(len(longest["states"])):
        fig = plt.figure(figsize=(12.8, 8), dpi=100, facecolor="white")
        fig.text(.044, .930, "Four early stops at contrast 4", weight="bold", fontsize=23)
        fig.text(.045, .879, stage_title(i, longest), fontsize=15, color=MUTED)
        legend(fig)
        fig.add_artist(Line2D([.045, .955], [.850, .850], color="#d4dfe2", transform=fig.transFigure))
        for position, case in enumerate(cases):
            row, col = divmod(position, 2)
            left, top = .045 + .478*col, .79 - .372*row
            fig.text(left, top, nice_name(case["shape"]), fontsize=16, weight="bold")
            end = len(case["states"])-1
            state = case["states"][min(i, end)]
            ax = fig.add_axes((left, top-.308, .222, .285))
            show_outline(ax, state, case["truth"], limits)
            tx = left + .236
            fig.text(tx, top-.060, "Area error", color=MUTED, fontsize=12)
            fig.text(tx, top-.111, f"{state['error']:.2%}", weight="bold", fontsize=23)
            fig.text(tx, top-.149, f"Extra {state['extra_fraction']:.1%}   /   Missing {state['missing_fraction']:.1%}", fontsize=11)
            fig.text(tx, top-.194, f"Estimated contrast   {state['contrast']:.3f}", fontsize=12)
            if i >= end:
                fig.text(tx, top-.228, f"{case['stop']} at stage {end}", fontsize=12)
                passed = state["error"] <= .05
                fig.text(tx, top-.268, "Passed the 5% cutoff" if passed else "Missed the 5% cutoff",
                         color=BLUE if passed else ORANGE, fontsize=12, weight="bold")
        fig.text(.045, .038, "Saved stage ends. Each stopped fit stays at its final outline.", fontsize=12, color=MUTED)
        fig.text(.955, .038, "TG-002   /   default_clean_uc_fc", ha="right", fontsize=11, color=MUTED)
        fig.savefig(folder / f"stage_{i:02d}.png", dpi=100)
        plt.close(fig)


def compare_kite(base, path):
    known = load_case("kite", "default_clean_kc_fc")
    damped = load_case("kite", "default_cleandamped_uc_fc")
    cases = [base, known, damped]
    limits = viewport(cases)
    fig = plt.figure(figsize=(12.8, 8), dpi=100, facecolor="white")
    fig.text(.04, .935, "Where the kite fit goes wrong", weight="bold", fontsize=23)
    fig.text(.04, .887, "Same target and starting circle. True contrast 4.", fontsize=14, color=MUTED)
    legend(fig)
    for j, label in enumerate(["Entering 0.5 GHz", "After fitting at 0.5 GHz", "Final outline"]):
        fig.text(.39+.225*j, .817, label, ha="center", weight="bold", fontsize=14)
    labels = ["Real data\nContrast estimated", "Real data\nContrast fixed at 4",
              "Damped warm-up\nand early stages\nContrast estimated"]
    for row, (case, label) in enumerate(zip(cases, labels)):
        bottom = .60-.266*row
        fig.text(.04, bottom+.09, label, va="center", fontsize=15)
        first = next(i for i, stage in enumerate(case["schedule"], 1)
                     if stage["frequencies_hz"] == [5e8])
        for col, state in enumerate([case["states"][first-1], case["states"][first], case["states"][-1]]):
            centre = .39+.225*col
            ax = fig.add_axes((centre-.1, bottom, .2, .194))
            show_outline(ax, state, case["truth"], limits)
            fig.text(centre, bottom-.024, f"Area error {state['error']:.2%}", ha="center", fontsize=11.5)
            fig.text(centre, bottom-.050, f"Centre off by {state['centre_mm']:.1f} mm", ha="center", fontsize=10.5, color=MUTED)
    fig.savefig(path)
    plt.close(fig)


def main():
    cases = [load_case(shape) for shape in CASES]
    destination = OUT / "contrast_4_fit_history.mp4"
    with tempfile.TemporaryDirectory(dir=OUT) as tmp:
        folder = Path(tmp)
        render(cases, folder)
        comparison = folder / f"stage_{max(len(c['states']) for c in cases):02d}.png"
        compare_kite(cases[0], comparison)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-framerate", "1/2",
                        "-i", str(folder / "stage_%02d.png"), "-vf", "fps=24,tpad=stop_mode=clone:stop_duration=6",
                        "-c:v", "libx264", "-threads", "2", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(folder / destination.name)], check=True)
        (folder / destination.name).replace(destination)
        comparison.replace(OUT / "contrast_4_kite_controls.png")


if __name__ == "__main__":
    main()
