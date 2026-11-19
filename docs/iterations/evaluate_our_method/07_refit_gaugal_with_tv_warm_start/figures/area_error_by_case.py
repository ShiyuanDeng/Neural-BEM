"""Render on CPU with PYTHONPATH=solvers:. from the repository root."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator, PercentFormatter
import numpy as np

from experiments.benchmark.scenes import SCENES, case_id

OUT = Path(__file__).resolve().parent
RESULTS = OUT.parents[4] / "results" / "gaugal"
LIMIT = 5
INK, MUTED = "#192f3a", "#4b5e66"
RUNS = (
    ("Default", "default_clean_uc_fs", "#126793", "o"),
    ("First continuation", "converged_clean_uc_fc", "#bd4b1f", "s"),
    ("TV warm start", "tvwarm_clean_uc_fc", "#087962", "D"),
)


def errors_percent(run, contrast):
    errors = []
    for scene in SCENES:
        case = case_id(contrast, scene)
        score = json.loads((RESULTS / run / case / "score.json").read_text())
        if score["case"] != case or score["run"] != f"gaugal/{run}":
            raise ValueError(f"Score does not match {run}/{case}")
        errors.append(100 * score["area_error"])
    return np.array(errors)


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                         "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})
    fig, axes = plt.subplots(2, 1, figsize=(11.6, 7.4), sharey=True)
    fig.subplots_adjust(left=.083, right=.91, bottom=.08, top=.84, hspace=.54)
    fig.suptitle("Clean GauGal area error by shape", x=.083, y=.982, ha="left",
                 fontsize=19, weight="bold")
    x = np.arange(len(SCENES))
    names = {"c_shape": "C-shape", "aphex_twin": "Aphex Twin"}
    for ax, contrast in zip(axes, (0.5, 4)):
        counts = []
        for offset, (label, run, color, marker) in zip((-.21, 0, .21), RUNS):
            errors = errors_percent(run, contrast)
            ax.scatter(x + offset, errors, label=label, color=color, marker=marker,
                       s=46, edgecolors="white", linewidths=.65, zorder=3)
            counts.append(f"{label} {np.count_nonzero(errors <= LIMIT)}/{len(errors)}")
        ax.set_title(f"Contrast {contrast:g}    ·    Recovered: " + "    ·    ".join(counts),
                     loc="left", fontsize=12, weight="bold", pad=10)
        ax.set_yscale("log")
        ax.set_ylim(1, 300)
        ax.set_yticks([1, 2, 5, 10, 20, 50, 100, 200])
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.set_ylabel("Area error")
        ax.set_xlim(-.52, len(SCENES) - .48)
        ax.set_xticks(x)
        ax.set_xticklabels([names.get(s, s.capitalize()) for s in SCENES])
        ax.grid(axis="y", color="#d8e0e3", linewidth=.7)
        ax.axhline(LIMIT, color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2)
        ax.text(1.008, LIMIT, "5% recovery\nlimit", transform=ax.get_yaxis_transform(),
                va="center", color=MUTED, fontsize=9)
        ax.tick_params(length=0, pad=6)
        for side in ("right", "top", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#91a3ac")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(.079, .94),
               ncol=3, frameon=False, borderaxespad=0, handletextpad=.35)
    fig.savefig(OUT / "area_error_by_case.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
