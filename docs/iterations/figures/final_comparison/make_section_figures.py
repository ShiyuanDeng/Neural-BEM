"""Rebuild the four simulated comparison figures from the repository root.

PYTHONPATH=solvers:. python docs/iterations/figures/final_comparison/make_section_figures.py
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from scipy.io import loadmat
from shapely.geometry import Polygon

from make_figures import (BEM, BLUE, CSI, INK, LENGTH, MUTED, ORANGE, OUT, RESULTS,
                          WARMUP, bem_outline, csi_outlines, curve_from, nice_name,
                          read, region, support_rings, truth_fixture)


def saved_curve(folder):
    return curve_from(read(folder / "fit.json")["final_curve"]).values(16384)


def percent(error):
    if error < .00001:
        return "<0.001%"
    return f"{error:.3%}" if error < .001 else f"{error:.2%}"


def recovered(errors, size):
    assert len(errors) == size
    return f"{sum(error <= .05 for error in errors)}/{size} recovered"


def figure(filename, title, columns, examples, units="mm", other_cases=()):
    """One case per row, with its scored final outline in each method column."""
    n = len(columns)
    widths = [1] * n + ([1.75] if other_cases else [])
    fig = plt.figure(figsize=(1.9 * sum(widths) + 1.25, 4.8))
    grid = fig.add_gridspec(2, len(widths), width_ratios=widths, left=.12, right=.985,
                            top=.76, bottom=.155, wspace=.12, hspace=.22)
    fig.suptitle(title, y=.98, fontsize=15, weight="bold")
    scale = 1000 if units == "mm" else 1
    points = scale * np.concatenate([ring for _, target, fits in examples
                                     for ring in [target] + [r for rings, _ in fits for r in rings]])
    span = max(np.ptp(points.real), np.ptp(points.imag)) * .56
    x = (points.real.max() + points.real.min()) / 2
    y = (points.imag.max() + points.imag.min()) / 2
    for i, (label, target, fits) in enumerate(examples):
        assert len(fits) == n
        reference, _ = region([target])
        for j, ((method, summary), (rings, error)) in enumerate(zip(columns, fits)):
            found, _ = region(rings)
            drawn_error = found.symmetric_difference(reference).area / reference.area
            # The paper's MATLAB reference is a sampled polygon. BEM scored an analytic glider.
            assert np.isclose(drawn_error, error, atol=2e-5 if units == "paper" else 1e-6), (label, method, drawn_error, error)
            ax = fig.add_subplot(grid[i, j])
            color = BLUE if method.startswith("BEM") else ORANGE
            for ring in rings:
                closed = scale * np.append(ring, ring[0])
                ax.plot(closed.real, closed.imag, color=color, lw=2.7)
            closed = scale * np.append(target, target[0])
            ax.plot(closed.real, closed.imag, color=INK, lw=1.1, ls=(0, (3, 3)))
            ax.set(aspect="equal", xlim=(x-span, x+span), ylim=(y-span, y+span), xticks=[], yticks=[])
            ax.set_facecolor("#f6f8f9")
            for spine in ax.spines.values():
                spine.set_color("#d9e1e4")
            ax.set_xlabel(percent(error), color=color, weight="bold", fontsize=10, labelpad=2)
            if j == 0:
                ax.set_ylabel(label, rotation=0, ha="right", va="center", fontsize=10, labelpad=8)
            if i == 0:
                ax.set_title(method, color=color, fontsize=11, pad=30 if "\n" in summary else 21, weight="bold")
                ax.text(.5, 1.035, summary, transform=ax.transAxes, ha="center", va="bottom",
                        fontsize=9, linespacing=1.3)
    if other_cases:
        ax = fig.add_subplot(grid[:, -1])
        ax.axis("off")
        ax.text(.05, .87, "Other paper cases", weight="bold", fontsize=11)
        header = ("Case", "BEM", "BRG")
        for i, values in enumerate([header, *other_cases]):
            v = .73 - i * .135
            for pos, align, value in zip((.05, .72, .99), ("left", "right", "right"), values):
                ax.text(pos, v, value, ha=align, va="center", fontsize=10,
                        weight="bold" if i == 0 else "normal")
            if i == 0:
                ax.axhline(v-.05, xmin=.05, xmax=.99, lw=.7, color="#b9c6cd")
        ax.text(.05, .055, "Final area error at wavenumber 15", fontsize=9, color=MUTED)
    side = 2 * span
    handles = [Line2D([], [], ls="--", color=INK, label="True boundary"),
               Line2D([], [], color=BLUE, label="BEM"),
               Line2D([], [], color=ORANGE, label=columns[-1][0].split(" · ")[0])]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, .044),
               frameon=False, ncol=3, fontsize=9)
    fig.text(.5, .015, f"Percentages below outlines are area errors. Each panel spans {side:.0f} mm."
             if units == "mm" else
             f"Percentages below outlines are area errors. Each panel spans {side:.2f} paper length units.",
             ha="center", fontsize=9, color=MUTED)
    fig.savefig(OUT / filename, dpi=175)
    plt.close(fig)


def native():
    root = RESULTS / "bem/default_clean_uc_fc"
    gaugal = RESULTS / "gaugal/default_clean_uc_fs"
    cases = [case for case in read(root / "run.json")["planned_cases"] if case.endswith(("__c0.5", "__c4"))]
    orig = {c: read(root / c / "score.json")["area_error"] for c in cases}
    warm = {c: read(WARMUP / f"{c}.json")["area_error"] for c in cases}
    image = {c: read(gaugal / c / "score.json")["area_error"] for c in cases}
    cols = [(method, recovered(scores.values(), 20)) for method, scores in
            [("BEM · original", orig), ("BEM · warm-up", warm), ("GauGal · untuned", image)]]
    examples = []
    for shape in ("circle", "kite"):
        case = f"{shape}__c4"
        stage = read(WARMUP / f"{case}.json")["stages"][-1]
        with np.load(gaugal / case / "fit.npz") as data:
            rings, _ = support_rings(data["image"], .5)
        target = LENGTH * truth_fixture(shape).values(16384)
        fits = [([LENGTH * saved_curve(root / case)], orig[case]),
                ([LENGTH * curve_from(stage["curve"]).values(16384)], warm[case]),
                (rings, image[case])]
        examples.append((nice_name(shape), target, fits))
    figure("a_native_tg002.png", "A. Original TG-002 acquisition", cols, examples)


def plane_waves():
    root = BEM / "brg_tg002/2026-11-18"
    summary = read(root / "campaign_summary.json")["fits"]
    cases = [row["case"] for row in summary if row["row"] == "known"]
    methods = [("BEM · supplied", root, "known"), ("BEM · estimated", root, "recovered"),
               ("BRG · limited", RESULTS / "brg/tg002_shapes/2026-11-17", None),
               ("BRG · unlimited", RESULTS / "brg/tg002_no_curvature/2026-11-18", None)]
    cols, by_case = [], {"kite__c4": [], "aphex_twin__c4": []}
    for method, base, material in methods:
        folders = {c: base / c / material / "attempt_01" if material else base / c for c in cases}
        errors = {c: read(p / "metrics.json")["area_error"] for c, p in folders.items()}
        cols.append((method, recovered(errors.values(), 20)))
        for c, fits in by_case.items():
            fits.append(([LENGTH * saved_curve(folders[c])], errors[c]))
    examples = []
    for case, fits in by_case.items():
        shape = case.split("__")[0]
        examples.append((nice_name(shape).replace(" ", "\n"), LENGTH * truth_fixture(shape).values(16384), fits))
    figure("b1_plane_waves.png", "B1. BRG plane waves on TG-002 shapes", cols, examples)


def paper():
    base = RESULTS / "brg/paper_examples/2026-11-17"
    bem = BEM / "brg_paper/2026-11-18"
    examples, others = [], []
    for case, label in [("glider_033", "Glider\ncontrast 0.33"), ("glider_10", "Glider\ncontrast 10"),
                        ("star_full", "Star, full view"), ("star_limited", "Star, limited view"),
                        ("cavity_09", "Cavity, 0.9"), ("cavity_2", "Cavity, 2")]:
        brg = base / case / "shipped"
        fit = bem / case / "cuda_fit/attempt_01"
        endpoint = read(brg / "metrics_k15.json")
        final = endpoint["final"]
        assert final["k"] == 15
        error = final["relative_area_error"]
        if case.startswith("glider"):
            known = read(fit / "metrics.json")
            last = loadmat(brg / f"frequency_{endpoint['frequencies']:03d}.mat", simplify_cells=True)["record"]
            assert last["k"] == 15 and np.isclose(last["relative_area_error"], error)
            truth = loadmat(brg / "truth_curve.mat", simplify_cells=True)["truth_curve"]
            target = truth["xs"] + 1j * truth["ys"]
            fits = [([saved_curve(fit)], known["area_error"]), ([last["xs"] + 1j * last["ys"]], error)]
            examples.append((label, target, fits))
        else:
            value = "Skipped" if case.startswith("cavity") else percent(read(fit / "metrics.json")["area_error"])
            others.append((label, value, percent(error)))
    cols = [("BEM", "Last wavenumber\n15 (top), 12 (bottom)"), ("BRG", "Last wavenumber\n15 for both gliders")]
    figure("b2_paper_cases.png", "B2. BRG paper cases", cols, examples, units="paper", other_cases=others)


def fresnel_simulations():
    shapes = ("star", "aphex_twin")
    targets = {s: LENGTH * truth_fixture(s).values(16384) for s in shapes}
    by_shape = {s: [] for s in shapes}
    cols = []
    for band, count in (("five", 7), ("ten", 10)):
        base = CSI / f"tg002/2026-11-18_{band}_frequency"
        bem = BEM / f"csi_{band}_frequency/2026-11-18"
        errors_bem, errors_csi = [], []
        for p in sorted(base.glob("*/scores.json")):
            shape = p.parent.name
            folder = bem / f"{shape}__c4/cuda/attempt_01"
            final = read(p)["snapshots"][-1]
            assert final["iterations"] == 2048
            err = next(s["area_error"] for s in final["scores"] if s["fraction"] == .5)
            errors_csi.append(err)
            errors_bem.append(read(folder / "metrics.json")["score"]["area_error"])
            if shape in by_shape:
                curve, area = bem_outline(folder)
                target = targets[shape]
                truth = Polygon(np.c_[target.real, target.imag])
                d = loadmat(p.parent / "final_contrast.mat", simplify_cells=True)
                rings = csi_outlines(d["grid_x_primary_m"], d["grid_y_primary_m"], d["snapshots"][-1], truth, err)
                by_shape[shape].extend([([curve], area), (rings, err)])
        for name, errors in (("BEM", errors_bem), ("MF-CC-CSI", errors_csi)):
            cols.append((f"{name} · {band}", f"{recovered(errors, count)}\n{np.mean(errors):.2%} mean error"))
    examples = [(nice_name(s).replace(" ", "\n"), targets[s], by_shape[s]) for s in shapes]
    figure("c_simulated_fresnel.png", "C. Simulated Fresnel data at five and ten frequencies", cols, examples)


if __name__ == "__main__":
    native()
    plane_waves()
    paper()
    fresnel_simulations()
