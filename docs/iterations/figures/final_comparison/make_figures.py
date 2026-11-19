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
SCHEDULES = RESULTS / "bem/stage_scheduling/2026-11-19"
WARMUP = SCHEDULES / "clean_tg002/warmup"
TEAL = "#087962"
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

    def campaign_scores(family, run):
        return {r["case"]: float(r["area_error"]) for r in rows
                if r["family"] == family and r["run"] == run}

    def warmup_scores(folder):
        return {p.stem: read(p)["area_error"] for p in folder.glob("*.json")}

    all_contrasts = ("0.5", "4", "13.3")
    low_contrasts = ("0.5", "4")
    clean = [
        ("BEM\ndefault", all_contrasts, campaign_scores("bem", "default_clean_uc_fc")),
        ("BEM\nwarm-up", all_contrasts, warmup_scores(WARMUP)),
        ("GauGal", low_contrasts, campaign_scores("gaugal", "default_clean_uc_fs")),
    ]
    noisy = [
        ("BEM\ndefault", all_contrasts, campaign_scores("bem", "default_n1d0_uc_fc")),
        ("BEM\nwarm-up", all_contrasts, warmup_scores(SCHEDULES / "noisy_tg002/warmup_n1d0")),
    ]
    plane_wave = []
    for mode, label in [("known", "BEM\nsupplied"), ("recovered", "BEM\nestimated")]:
        plane_wave.append((label, low_contrasts,
                           {r["case"]: r["area_error"] for r in fits if r["row"] == mode}))
    for label, subdir in [("BRG\nlimited", "tg002_shapes/2026-11-17"),
                          ("BRG\nunlimited", "tg002_no_curvature/2026-11-18")]:
        plane_wave.append((label, low_contrasts,
                           {p.parent.name: read(p)["area_error"]
                            for p in (RESULTS / "brg" / subdir).glob("*/metrics.json")}))

    panels = [("Original TG-002 · clean", clean), ("TG-002 · 1% noise, draw 0", noisy),
              ("BRG plane-wave data · clean", plane_wave)]
    widths = [sum(len(contrasts) for _, contrasts, _ in group) for _, group in panels]
    fig, axes = plt.subplots(1, len(panels), figsize=(14.2, 5.5),
                             gridspec_kw={"width_ratios": widths})
    fig.subplots_adjust(left=.085, right=.985, bottom=.12, top=.90, wspace=.085)
    shapes = list(SHAPES)
    for panel, (ax, (title, group), width) in enumerate(zip(axes, panels, widths)):
        ax.axis("off")
        ax.set(xlim=(-.52, width-.48), ylim=(10.95, -2.75))
        ax.set_title(title, fontweight="bold", pad=9, fontsize=13)
        ax.axhline(-2.66, color="#91a3ac", lw=1)
        for y, shape in enumerate(shapes):
            if y % 2 == 0:
                ax.axhspan(y-.46, y+.46, color="#f2f5f6", zorder=-1)
            if panel == 0:
                ax.text(-.60, y, nice_name(shape), ha="right", va="center", fontsize=11)
        if panel == 0:
            ax.text(-.60, -.85, "Contrast", ha="right", va="center", color=MUTED)
            ax.text(-.60, 10.20, "Recovered", ha="right", va="center", weight="bold")

        start = 0
        for label, contrasts, scores in group:
            centre = start + (len(contrasts) - 1) / 2
            ax.text(centre, -1.95, label, ha="center", va="center", fontsize=11)
            passed = 0
            for x, contrast in enumerate(contrasts, start=start):
                ax.text(x, -.85, contrast, ha="center", va="center", color=MUTED)
                for y, shape in enumerate(shapes):
                    ok = scores[f"{shape}__c{contrast}"] <= .05
                    passed += ok
                    ax.plot(x, y, marker="o" if ok else "x", ms=6.3 if ok else 5.3,
                            color=BLUE if ok else "#889399", mew=1.2)
            ax.text(centre, 10.20, f"{passed}/{len(contrasts)*len(shapes)}",
                    ha="center", va="center", weight="bold", fontsize=11)
            if start:
                ax.vlines(start-.5, -2.45, 9.5, color="#d8e0e3", lw=.8)
            start += len(contrasts)

    fig.legend(handles=[Line2D([], [], marker=m, linestyle="none", color=c, label=t)
                        for m, c, t in [("o", BLUE, "Area error ≤ 5%"), ("x", "#889399", "Area error > 5%")]],
               loc="lower center", bbox_to_anchor=(.5, .01), ncol=2, frameon=False)
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
        default = LENGTH * curve_from(fit["final_curve"]).values(samples)
        warmup = read(WARMUP / f"{case}.json")
        last_stage = warmup["stages"][-1]
        assert np.isclose(last_stage["area_error"], warmup["area_error"], rtol=0, atol=1e-12), case
        warmed = LENGTH * curve_from(last_stage["curve"]).values(samples)
        endpoints[case] = (truth, default, warmed), (score["area_error"], warmup["area_error"])

    # Use one physical frame in every panel, including oversized failed fits.
    outlines = np.concatenate([line for curves, _ in endpoints.values() for line in curves]) * 1000
    x = (outlines.real.min() + outlines.real.max()) / 2
    y = (outlines.imag.min() + outlines.imag.max()) / 2
    half_span = max(np.ptp(outlines.real), np.ptp(outlines.imag)) * .53
    fig = plt.figure(figsize=(11, 12))
    blocks = fig.add_gridspec(2, 1, left=.07, right=.985, top=.887, bottom=.035, hspace=.17)
    grids = [block.subgridspec(3, 5, hspace=.22, wspace=.07) for block in blocks]
    for i, shape in enumerate(SHAPES):
        block, col = divmod(i, 5)
        for j, contrast in enumerate(contrasts):
            ax = fig.add_subplot(grids[block][j, col])
            (truth, default, warmed), errors = endpoints[f"{shape}__c{contrast}"]
            draw(ax, warmed, TEAL, lw=3.1)
            draw(ax, default, BLUE, lw=1.6, ls="--")
            draw(ax, truth, INK, lw=1.1, ls=":")
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
            gained = errors[0] > .05 >= errors[1]
            labels = ["<0.01%" if error < .0001 else f"{error:.2%}" for error in errors]
            ax.text(.5, -.035, " → ".join(labels), ha="center", va="top", fontsize=9.5,
                    weight="bold" if gained else "normal", color=TEAL if gained else INK,
                    transform=ax.transAxes)
    fig.suptitle("Clean TG-002 area error by shape and contrast", y=.988, weight="bold", fontsize=15)
    fig.legend(handles=[Line2D([], [], color=BLUE, lw=1.8, ls="--", label="Default"),
                        Line2D([], [], color=TEAL, lw=3.1, label="0.25 GHz warm-up"),
                        Line2D([], [], color=INK, ls=":", label="True boundary")],
               loc="upper center", bbox_to_anchor=(.5,.965), ncol=3, frameon=False, fontsize=11)
    fig.text(.5, .928, "Area errors read from default to warm-up. Bold pairs mark new recoveries.",
             ha="center", color=MUTED, fontsize=10)
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
    methods = []
    for name, folder, color in [
        ("BEM\ndefault", "csi_adapter/2026-11-18/first_fit", BLUE),
        ("BEM\ncircle-first", "measured_schedule/2026-11-19/circle_ladder", TEAL),
    ]:
        curve, error = bem_outline(BEM / folder / "dielTM_dec8f/cuda/attempt_01")
        methods.append((name, [curve], error, color))
    data = loadmat(RESULTS.parent / registered["source"], simplify_cells=True)
    for i, row in enumerate(registered["methods"], 1):
        error = row["scores"][0]["area_error"]
        rings = csi_outlines(data, data[f"chi{i}"][-1], truth, error)
        methods.append((row["method"] if row["method"] != "CSI" else "Classical CSI", rings, error, ORANGE))
    fig, axes = plt.subplots(1, len(methods), figsize=(12, 3.95), sharey=True)
    fig.subplots_adjust(left=.055, right=.985, bottom=.21, top=.75, wspace=.15)
    fig.suptitle("Measured cylinder area error at the nominal position", weight="bold", fontsize=15)
    for ax, (name, rings, error, color) in zip(axes, methods):
        for ring in rings:
            points = ring*1000
            assert points.real.min() > -35 and points.real.max() < 35
            assert points.imag.min() > 0 and points.imag.max() < 70
            draw(ax, ring, color, lw=2)
        draw(ax, reference, INK, lw=1.3, ls=(0,(3,2.7)))
        ax.set(aspect="equal", xlim=(-35,35), ylim=(0,70), xticks=[-30,0,30], yticks=[0,30,60])
        ax.set_title(f"{name}\n{error:.2%}", fontsize=11, pad=7)
        ax.grid(color="#e3e9eb", lw=.6)
        ax.tick_params(length=0, pad=3)
        for spine in ax.spines.values():
            spine.set_color("#c9d4d9")
    axes[0].set_ylabel("y (mm)")
    fig.supxlabel("x (mm)", y=.085, fontsize=10)
    fig.legend(handles=[Line2D([], [], color=INK, ls="--", label="Nominal 15 mm radius")],
               loc="lower center", bbox_to_anchor=(.5, -.007), frameon=False)
    fig.savefig(OUT / "measured_cylinder.png", dpi=175)
    plt.close(fig)


if __name__ == "__main__":
    plot_recovery()
    plot_clean_bem()
    plot_simulated()
    plot_measured()
