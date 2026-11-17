"""Check compact shipped-example records and render the requested handoff."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results/brg/examples/shipped_cavity_full"
FIGURES = ROOT / "docs/iterations/brg_adaptation/01_run_published_examples/figures/shipped_cavity_full"


def main():
    records = []
    for index, path in enumerate(sorted(OUT.glob("frequency_*.mat")), 1):
        record = loadmat(path, simplify_cells=True)["record"]
        history = np.atleast_1d(record["residual_history"])
        assert record["index"] == index and record["k"] == 1 + (index - 1) * 0.25
        assert len(history) == record["iterations"]
        assert np.all(np.isfinite(history)) and history[-1] == record["residual"]
        assert len(record["xs"]) == len(record["ys"])
        assert np.all(np.isfinite(record["xs"])) and np.all(np.isfinite(record["ys"]))
        records.append(record)
    summary = json.loads((OUT / "summary.json").read_text())
    assert len(records) == summary["inverse_frequencies"]
    if summary["status"] == "complete":
        assert len(records) == 117 and summary["data_frequencies"] == 117
    assert records, "No completed inverse frequency to summarize."
    keys = ["index", "k", "iterations", "residual", "exit_flag", "wall_seconds"]
    with (OUT / "frequency_summary.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys + ["boundary_points"])
        writer.writeheader()
        for row in records:
            writer.writerow({**{k: row[k] for k in keys}, "boundary_points": len(row["xs"])})
    attempts = [json.loads(p.read_text()) for p in sorted(OUT.glob("attempt_*.json"))]
    data = json.loads((OUT / "data_summary.json").read_text())
    metrics = {"label": summary["label"], "status": summary["status"],
               "data_frequencies": len(data), "inverse_frequencies": len(records),
               "last_k": records[-1]["k"], "iterations": sum(int(r["iterations"]) for r in records),
               "exit_flag_counts": {str(flag): sum(r["exit_flag"] == flag for r in records)
                                    for flag in sorted({r["exit_flag"] for r in records})},
               "data_compute_seconds": sum(r["wall_seconds"] for r in data),
               "inverse_compute_seconds": sum(r["wall_seconds"] for r in records),
               "attempt_wall_seconds": sum(r.get("wall_seconds", 0) for r in attempts),
               "final_residual": records[-1]["residual"],
               "driver_area_error": summary["driver_area_error"],
               "true_area": summary["true_area"],
               "relative_area_error": summary["relative_area_error"],
               "compact_records_checked": True}
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    truth = loadmat(OUT / "truth_curve.mat", simplify_cells=True)["truth_curve"]
    selected = [records[0]]
    if len(records) >= 57:
        selected.append(records[56])
    if records[-1]["index"] != selected[-1]["index"]:
        selected.append(records[-1])
    fig, axes = plt.subplots(1, len(selected), figsize=(4 * len(selected), 4), squeeze=False,
                             constrained_layout=True)
    extent = 1.12 * max(float(np.max(np.abs(curve[key])))
                        for curve in [truth, *selected] for key in ["xs", "ys"])
    for ax, row in zip(axes[0], selected):
        for curve, color, name in [(truth, "#252525", "True cavity"),
                                    (row, "#ce4b16", "BRG recovered")]:
            ax.plot(np.r_[curve["xs"], curve["xs"][0]], np.r_[curve["ys"], curve["ys"][0]],
                    color=color, linewidth=1.6, label=name)
        ax.set(xlim=(-extent, extent), ylim=(-extent, extent), xlabel="x", ylabel="y",
               title=f"k = {row['k']:g} · residual {row['residual']:.3f}")
        ax.set_aspect("equal"); ax.grid(alpha=0.2)
    axes[0, 0].legend(loc="upper left", fontsize=9)
    fig.suptitle("BRG shipped cavity example — known material ratio 2.25 — not Table B", fontsize=12)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "cavity_at_paper_frequencies.png", dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(8, 5), sharex=True, constrained_layout=True)
    ks = [r["k"] for r in records]
    axes[0].plot(ks, [r["residual"] for r in records], color="#ce4b16")
    axes[0].set(ylabel="Relative data residual", title="BRG shipped example · frequency history")
    axes[1].plot(ks, [r["iterations"] for r in records], color="#256c8e")
    axes[1].set(xlabel="Exterior wavenumber k", ylabel="Iterations")
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.savefig(FIGURES / "frequency_history.png", dpi=160)
    plt.close(fig)
    # Commit concise progress lines; the complete MATLAB log stays local.
    lines = []
    for path in sorted((OUT / "local").glob("matlab_*.log")):
        lines.extend(line for line in path.read_text(errors="replace").splitlines()
                     if line.startswith(("BRG DATA ", "BRG INVERSE ")))
    (OUT / "progress.log").write_text("\n".join(lines) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
