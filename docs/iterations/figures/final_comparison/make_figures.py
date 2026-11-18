"""Plot saved results. From the repo root run with PYTHONPATH=solvers:. and the EMNerf Python."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from scipy.io import loadmat
from shapely.geometry import Point, Polygon

from bem_inverse.io import curve_from
from experiments.baselines.csi.registered_metrics import score_field
from experiments.bem_on_baseline_data.csi_data import LENGTH_M
from experiments.benchmark import campaign
from experiments.benchmark.scenes import LENGTH, SHAPES, truth_fixture
from experiments.comparison.scoring import support_rings

OUT = Path(__file__).resolve().parent
RESULTS = OUT.parents[3] / "results"
BEM = RESULTS / "bem/baseline_data"
CSI = RESULTS / "csi"
BLUE, ORANGE, INK, MUTED = "#126793", "#bd4b1f", "#192f3a", "#4b5e66"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})


def read(path):
    return json.loads(path.read_text())


def nice_name(shape):
    return {"c_shape": "C-shape", "aphex_twin": "Aphex Twin"}.get(shape, shape.capitalize())


def plot_recovery():
    with (RESULTS / "metrics.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    fits = read(BEM / "brg_tg002/2026-11-18/campaign_summary.json")["fits"]
    columns = []
    for family, run in [("bem", "default_clean_uc_fc"), ("gaugal", "default_clean_uc_fs")]:
        columns.append({r["case"]: float(r["area_error"]) for r in rows
                        if r["family"] == family and r["run"] == run})
    for mode in ["known", "recovered"]:
        columns.append({r["case"]: r["area_error"] for r in fits if r["row"] == mode})
    for subdir in ["tg002_shapes/2026-11-17", "tg002_no_curvature/2026-11-18"]:
        columns.append({p.parent.name: read(p)["area_error"]
                        for p in (RESULTS / "brg" / subdir).glob("*/metrics.json")})
    fig, ax = plt.subplots(figsize=(11.6, 5.15))
    fig.subplots_adjust(left=.13, right=.98, top=.97, bottom=.09)
    ax.set(xlim=(-.65, 11.65), ylim=(11.35, -3.65))
    ax.axis("off")
    for left, right, title in [(-.4, 3.4, "Original TG-002"), (3.6, 11.4, "BRG plane-wave data")]:
        ax.text((left+right)/2, -3.05, title, ha="center", weight="bold", fontsize=14)
        ax.plot([left, right], [-2.78, -2.78], color="#91a3ac", lw=1)
    labels = ["BEM", "GauGal", "BEM\ncontrast supplied", "BEM\ncontrast estimated",
              "BRG\ncurvature limit", "BRG\nno limit"]
    groups = list(SHAPES)
    ax.text(-.66, -.85, "Contrast", ha="right", va="center", fontsize=9, color=MUTED)
    for i, scores in enumerate(columns):
        ax.text(2*i+.5, -1.94, labels[i], ha="center", va="center", fontsize=10.5)
        passed = 0
        for k, contrast in enumerate(["0.5", "4"]):
            x = 2*i+k
            ax.text(x, -.85, contrast, ha="center", va="center", fontsize=9, color=MUTED)
            for y, shape in enumerate(groups):
                ok = scores[f"{shape}__c{contrast}"] <= .05
                passed += ok
                ax.plot(x, y, marker="o" if ok else "x", ms=7 if ok else 6,
                        color=BLUE if ok else "#8a8f93", mew=1.3)
        ax.text(2*i+.5, 10.22, f"{passed}/20", ha="center", va="center", weight="bold")
        if i:
            ax.plot([2*i-.5]*2, [-.55, 9.55], color="#a2b1b8" if i == 2 else "#e0e6e8")
    for y, label in enumerate(groups):
        if y % 2 == 0:
            ax.axhspan(y-.48, y+.48, color="#f3f6f7", zorder=-1)
        ax.text(-.66, y, nice_name(label), ha="right", va="center")
    ax.text(-.66, 10.22, "Recovered", ha="right", va="center", weight="bold")
    ax.legend(handles=[Line2D([], [], marker=m, linestyle="none", color=c, label=t)
                       for m, c, t in [("o", BLUE, "Area error ≤ 5%"), ("x", "#8a8f93", "Area error > 5%")]],
              loc="lower center", bbox_to_anchor=(.5, -.08), ncol=2, frameon=False)
    fig.savefig(OUT / "tg002_recovery.png", dpi=165)
    plt.close(fig)


def bem_outline(folder):
    curve = curve_from(read(folder / "fit.json")["final_curve"])
    return LENGTH_M * curve.values(16384), read(folder / "metrics.json")["score"]["area_error"]


def csi_outlines(data, values, truth, saved_error):
    gx, gy = data["grid_x_primary_m"], data["grid_y_primary_m"]
    scores, image = score_field(values, (len(gx), len(gy)), gx, gy, truth, fractions=(.5,))
    assert np.isclose(scores[0]["area_error"], saved_error, atol=1e-7)
    return support_rings(image, .5)[0]


def draw(ax, points, color, **style):
    mm = np.r_[points, points[0]] * 1000
    ax.plot(mm.real, mm.imag, color=color, **style)


def plot_clean_bem():
    root = RESULTS / "bem/default_clean_uc_fc"
    cases = read(root / "run.json")["planned_cases"]
    contrasts = ["0.5", "4", "13.3"]
    endpoints = {}
    for case in cases:
        fit = read(root / case / "fit.json")
        score = read(root / case / "score.json")
        truth_path = campaign.ROOT / campaign.row(case)["truth"]
        samples = score["protocol"]["curve_samples"]
        truth = LENGTH * curve_from(read(truth_path)).values(samples)
        boundary = LENGTH * curve_from(fit["final_curve"]).values(samples)
        endpoints[case] = truth, boundary, score["area_error"]

    # Use one physical frame in every panel, including oversized failed fits.
    outlines = np.concatenate([line for truth, boundary, _ in endpoints.values()
                               for line in (truth, boundary)]) * 1000
    x = (outlines.real.min() + outlines.real.max()) / 2
    y = (outlines.imag.min() + outlines.imag.max()) / 2
    half_span = max(np.ptp(outlines.real), np.ptp(outlines.imag)) * .53
    fig = plt.figure(figsize=(11, 12))
    blocks = fig.add_gridspec(2, 1, left=.07, right=.985, top=.933, bottom=.035, hspace=.23)
    grids = [block.subgridspec(3, 5, hspace=.22, wspace=.07) for block in blocks]
    for i, shape in enumerate(SHAPES):
        block, col = divmod(i, 5)
        for j, contrast in enumerate(contrasts):
            ax = fig.add_subplot(grids[block][j, col])
            truth, boundary, error = endpoints[f"{shape}__c{contrast}"]
            draw(ax, boundary, BLUE, lw=2)
            draw(ax, truth, INK, lw=1.1, ls=(0, (2.3, 2.8)))
            ax.set(aspect="equal", xlim=(x-half_span, x+half_span), ylim=(y-half_span, y+half_span))
            ax.set_facecolor("#f7f9fa")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            if j == 0:
                ax.set_title(nice_name(shape), fontsize=12, weight="bold", pad=7)
            if col == 0:
                ax.set_ylabel(f"Contrast {contrast}", fontsize=11, labelpad=8)
            passed = error <= .05
            display = "<0.01%" if error < .0001 else f"{error:.2%}"
            ax.text(.5, -.035, f"{'Pass' if passed else 'Miss'}   {display}",
                    ha="center", va="top", fontsize=10, color=BLUE if passed else ORANGE,
                    transform=ax.transAxes)
    fig.legend(handles=[Line2D([], [], color=BLUE, lw=2, label="BEM fit"),
                        Line2D([], [], color=INK, ls="--", label="True boundary")],
               loc="upper center", ncol=2, frameon=False, fontsize=11)
    fig.savefig(OUT / "default_clean_uc_fc.png", dpi=180)
    plt.close(fig)


def plot_simulated():
    names = ["star", "asymmetric", "cross", "cog", "c_shape", "hook", "aphex_twin"]
    fig, axes = plt.subplots(2, 4, figsize=(10.6, 5.65))
    fig.subplots_adjust(left=.03, right=.97, top=.90, bottom=.035, hspace=.41, wspace=.14)
    for ax, name in zip(axes.flat, names):
        truth = LENGTH_M * truth_fixture(name).values(8192)
        folder = CSI / "tg002/2026-11-18_five_frequency" / name
        data = loadmat(folder / "final_contrast.mat", simplify_cells=True)
        error = read(folder / "scores.json")["snapshots"][-1]["scores"][0]["area_error"]
        rings = csi_outlines(data, data["snapshots"][-1], Polygon(np.c_[truth.real, truth.imag]), error)
        folder = BEM / "csi_five_frequency/2026-11-18" / f"{name}__c4/cuda/attempt_01"
        boundary, bem_error = bem_outline(folder)
        draw(ax, boundary, BLUE, lw=2.6)
        for ring in rings:
            draw(ax, ring, ORANGE, lw=1.5)
        draw(ax, truth, INK, lw=1.15, ls=(0, (3, 2.7)))
        extent = 1000*np.concatenate([truth, boundary, *rings])
        x = (extent.real.min() + extent.real.max())/2
        y = (extent.imag.min() + extent.imag.max())/2
        assert max(np.ptp(extent.real), np.ptp(extent.imag)) < 138
        ax.set(xlim=(x-69,x+69), ylim=(y-69,y+69), aspect="equal")
        ax.axis("off")
        ax.set_title(nice_name(name), pad=15, weight="bold", fontsize=13)
        ax.text(.5, 1.007, f"{bem_error:.2%}   /   {error:.2%}", transform=ax.transAxes,
                ha="center", va="bottom", fontsize=10)
    key = axes.flat[-1]
    key.set(xlim=(0,138), ylim=(0,138), aspect="equal")
    key.axis("off")
    for y, color, style, name in [(105, INK, "--", "True boundary"), (84, BLUE, "-", "BEM"),
                                   (63, ORANGE, "-", "MF-CC-CSI")]:
        key.plot([0,22],[y,y], color=color, ls=style, lw=2)
        key.text(29,y,name,va="center",fontsize=11)
    key.plot([0,50],[29,29],lw=2,color=INK)
    key.text(25,18,"50 mm",ha="center")
    fig.savefig(OUT / "simulated_boundaries.png", dpi=175)
    plt.close(fig)


def plot_measured():
    registered = read(CSI / "preparation/2026-11-17_frame/registered_scores.json")
    geometry = registered["truth"]
    x, y = np.array(geometry["centre_numerical_mm"])/1000
    truth = Point(x,y).buffer(geometry["radius_mm"]/1000, quad_segs=4096)
    tx, ty = truth.exterior.xy
    reference = np.asarray(tx) + 1j*np.asarray(ty)
    curve, error = bem_outline(BEM / "csi_adapter/2026-11-18/first_fit/dielTM_dec8f/cuda/attempt_01")
    methods = [("BEM", [curve], error, BLUE)]
    data = loadmat(RESULTS.parent / registered["source"], simplify_cells=True)
    for i, row in enumerate(registered["methods"], 1):
        error = row["scores"][0]["area_error"]
        rings = csi_outlines(data, data[f"chi{i}"][-1], truth, error)
        methods.append((row["method"].removeprefix("MF-") if i == 2 else row["method"], rings, error, ORANGE))
    fig, axes = plt.subplots(1, 4, figsize=(10.6, 3.5), sharey=True)
    fig.subplots_adjust(left=.07, right=.985, bottom=.20, top=.81, wspace=.13)
    for ax, (name, rings, error, color) in zip(axes, methods):
        for ring in rings:
            points = ring*1000
            assert points.real.min() > -35 and points.real.max() < 35
            assert points.imag.min() > 0 and points.imag.max() < 70
            draw(ax, ring, color, lw=2)
        draw(ax, reference, INK, lw=1.3, ls=(0,(3,2.7)))
        ax.set(aspect="equal", xlim=(-35,35), ylim=(0,70), xticks=[-30,0,30], yticks=[0,30,60])
        ax.set_title(f"{name}\n{error:.1%}", fontsize=12, pad=7)
        ax.grid(color="#e3e9eb", lw=.6)
        ax.tick_params(length=0, pad=3)
        for spine in ax.spines.values():
            spine.set_color("#c9d4d9")
    axes[0].set_ylabel("y (mm)")
    fig.supxlabel("x (mm)", y=.07, fontsize=10)
    fig.savefig(OUT / "measured_cylinder.png", dpi=175)
    plt.close(fig)


if __name__ == "__main__":
    plot_recovery()
    plot_clean_bem()
    plot_simulated()
    plot_measured()
