"""Draw the C-shape band comparison from saved fits. Use PYTHONPATH=solvers:. in EMNerf."""
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from bem_inverse.io import curve_from
from experiments.benchmark.scenes import LENGTH
from experiments.comparison.scoring import PROTOCOL, region
from make_contrast_4_video import EXTRA, MISSING, load_case, show_outline, viewport
from make_figures import BLUE, INK, OUT, RESULTS, read


def main():
    baseline = load_case("c_shape")
    truth = baseline["truth"]
    target = region([truth])[0]
    wider = read(RESULTS / "bem/stage_stops/2026-11-18/wider/c_shape__c4.json")
    original = [baseline["states"][i] for i in (1, 3, -1)]
    changed = []
    for i in (0, 2, -1):
        stage = wider["stages"][i]
        outline = LENGTH * curve_from(stage["curve"]).values(PROTOCOL["curve_samples"])
        found = region([outline])[0]
        changed.append(dict(outline=outline, extra=found.difference(target),
                            missing=target.difference(found), error=stage["area_error"]))
    limits = viewport([dict(truth=truth, states=original+changed)])

    fig, axes = plt.subplots(2, 3, figsize=(7.3, 5.1))
    fig.subplots_adjust(left=.18, right=.98, bottom=.16, top=.90, hspace=.34, wspace=.12)
    for ax, title in zip(axes[0], ("Stage 1", "Stage 3", "Final fit")):
        ax.set_title(title, fontweight="bold", fontsize=11)
    for row, states, label in zip(axes, (original, changed), ("Default\nbands", "Wider\nbands")):
        row[0].set_ylabel(label, rotation=0, va="center", ha="right", labelpad=9, fontweight="bold")
        for ax, state in zip(row, states):
            show_outline(ax, state, truth, limits)
            ax.set_xlabel(f"{state['error']:.2%} area error")
    fig.legend(handles=[Line2D([], [], color=BLUE, lw=2, label="BEM fit"),
                        Line2D([], [], color=INK, ls="--", label="True boundary"),
                        Patch(color=EXTRA, label="Extra area"), Patch(color=MISSING, label="Missing area")],
               loc="lower center", bbox_to_anchor=(.55,.013), ncol=4, frameon=False, fontsize=9)
    folder = OUT.parents[1] / "evaluate_our_method/04_check_stage_stops_and_shape_bands/figures"
    folder.mkdir(exist_ok=True)
    fig.savefig(folder / "c_shape_update_bands.png", dpi=170, bbox_inches="tight", pad_inches=.12)
    plt.close(fig)


if __name__ == "__main__":
    main()
