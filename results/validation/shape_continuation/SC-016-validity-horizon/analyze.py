"""Fit and draw the linearization horizon, and test its predicted form.

Run from the repository root with the package importable:

    PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-016-validity-horizon/analyze.py
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ATLAS = HERE.parent / "SC-015-atlas-structure"
ARMS = {"H1-circle-c033": "A-circle-c033-paperacq",
        "H2-circle-c10": "C-circle-c10-paperacq",
        "H3-iterate-c033": "E-iterate-c033-paperacq",
        "H4-truth-c033": "D-truth-c033-paperacq",
        "H5-circle-c033-fine": "A-circle-c033-paperacq"}
SATURATION = 2.0


def load(name):
    return json.loads((HERE / name / "summary.json").read_text())


def harmonic_rows(summary):
    return [row for row in summary["horizons"] if row["harmonic"] is not None]


def power_fit(pairs):
    pairs = [(x, y) for x, y in pairs if np.isfinite(y) and y > 0 and x > 0]
    if len(pairs) < 3:
        return None
    slope, intercept = np.polyfit(np.log([p[0] for p in pairs]), np.log([p[1] for p in pairs]), 1)
    return dict(exponent=float(slope), coefficient=float(np.exp(intercept)), points=len(pairs))


def sensitivity_table(atlas_name):
    path = ATLAS / atlas_name / "atlas.npz"
    if not path.exists():
        return None
    arrays = np.load(path)
    harmonics, columns = arrays["harmonics"], arrays["sensitivity"]
    band = int(harmonics.max())
    table = np.zeros((len(columns), band + 1))
    for index in range(len(columns)):
        np.add.at(table[index], harmonics, columns[index] ** 2)
    return arrays["wavenumbers"], np.sqrt(table)


def law_test(summary, atlas_name):
    """Compare measured per-harmonic horizons with the diagonal's prediction."""
    table = sensitivity_table(atlas_name)
    if table is None:
        return None
    wavenumbers, sensitivity = table
    rows = harmonic_rows(summary)
    measured, predicted = [], []
    for row in rows:
        index = np.nonzero(np.isclose(wavenumbers, row["wavenumber"]))[0]
        reference = next((r["horizon_10"] for r in rows
                          if r["wavenumber"] == row["wavenumber"] and r["harmonic"] == 1), None)
        if (not len(index) or reference is None or not np.isfinite(reference)
                or reference <= 0 or not np.isfinite(row["horizon_10"]) or row["horizon_10"] <= 0):
            continue
        profile = sensitivity[int(index[0])]
        ratio = profile[row["harmonic"]] / profile.max()
        measured.append(row["horizon_10"])
        predicted.append(reference * min(1.0, SATURATION * ratio))
    measured, predicted = np.array(measured), np.array(predicted)
    keep = (predicted > 0) & (measured > 0)
    if keep.sum() < 5:
        return None
    error = np.abs(np.log10(measured[keep] / predicted[keep]))
    return dict(points=int(keep.sum()), median_dex=float(np.median(error)),
                percentile90_dex=float(np.percentile(error, 90)),
                within_a_factor_of_two=float(np.mean(error < np.log10(2))))


def analyse(name, atlas_name):
    summary = load(name)
    rows = harmonic_rows(summary)
    record = dict(name=name, geometry=summary["geometry_label"], contrast=summary["contrast"],
                  wavenumbers=sorted({row["wavenumber"] for row in rows}),
                  order_median=float(np.median([row["order"] for row in rows
                                                if np.isfinite(row["order"])])))
    record["ceiling_fit"] = power_fit([(row["wavenumber"], row["horizon_10"])
                                       for row in rows if row["harmonic"] in (1, 2)])
    record["per_harmonic_fit"] = {
        str(harmonic): power_fit([(row["wavenumber"], row["horizon_10"])
                                  for row in rows if row["harmonic"] == harmonic])
        for harmonic in sorted({row["harmonic"] for row in rows})}
    record["law"] = law_test(summary, atlas_name)
    quality = summary["step_quality"]
    record["model_ratio"] = {}
    for entry in quality:
        steps = np.asarray(entry["steps"])
        index = int(np.argmin(np.abs(steps - 1.0)))
        ratio = entry["ratio"][index]
        record["model_ratio"].setdefault(str(entry["band_limit"]), []).append(
            dict(wavenumber=entry["wavenumber"],
                 ratio=None if ratio is None else float(ratio),
                 step_rms=entry["achieved"][index]))
    gauss = [row for row in summary["horizons"] if row["harmonic"] is None]
    record["gauss_newton_fit"] = {
        row: power_fit([(entry["wavenumber"], entry["horizon_10"])
                        for entry in gauss if entry["direction"] == row])
        for row in sorted({entry["direction"] for entry in gauss})}
    return record, summary


def figures(records, summaries):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    colours = plt.get_cmap("viridis")(np.linspace(0, 0.85, 8))
    summary = summaries.get("H1-circle-c033")
    if summary is not None:
        rows = harmonic_rows(summary)
        for colour, harmonic in zip(colours, sorted({r["harmonic"] for r in rows})):
            points = [(r["wavenumber"], r["horizon_10"]) for r in rows
                      if r["harmonic"] == harmonic and np.isfinite(r["horizon_10"]) and r["horizon_10"] > 0]
            if points:
                axes[0].loglog([p[0] for p in points], [p[1] for p in points], "o-",
                               color=colour, ms=3, label=f"$p={harmonic}$")
        grid = np.array([1, 20])
        axes[0].loglog(grid, 0.12 / grid, "k--", lw=1.5, label=r"$0.12/k$")
        axes[0].set(xlabel="wavenumber $k$", ylabel=r"horizon $\varepsilon^*$ (RMS displacement)",
                    title="Where $J h$ stops predicting the data\n(10% criterion, unit circle, contrast 0.33)")
        axes[0].legend(fontsize=7, ncol=2)

    for name, style in (("H1-circle-c033", "C0o"), ("H4-truth-c033", "C1s"), ("H2-circle-c10", "C3^")):
        summary = summaries.get(name)
        table = sensitivity_table(ARMS[name]) if summary else None
        if summary is None or table is None:
            continue
        wavenumbers, sensitivity = table
        rows = harmonic_rows(summary)
        xs, ys = [], []
        for row in rows:
            index = np.nonzero(np.isclose(wavenumbers, row["wavenumber"]))[0]
            reference = next((r["horizon_10"] for r in rows
                              if r["wavenumber"] == row["wavenumber"] and r["harmonic"] == 1), None)
            if (not len(index) or reference is None or not np.isfinite(reference) or reference <= 0
                    or not np.isfinite(row["horizon_10"]) or row["horizon_10"] <= 0):
                continue
            profile = sensitivity[int(index[0])]
            xs.append(profile[row["harmonic"]] / profile.max())
            ys.append(row["horizon_10"] / reference)
        axes[1].loglog(xs, ys, style, ms=4, alpha=0.7,
                       label=f"{records[name]['geometry'][:22]}, c={records[name]['contrast']:g}")
    grid = np.geomspace(1e-5, 1.2, 50)
    axes[1].loglog(grid, np.minimum(1.0, SATURATION * grid), "k--", lw=1.5,
                   label=r"$\min(1,\,2\,s_p/s_{\max})$")
    axes[1].set(xlabel=r"relative column sensitivity $s_p/s_{\max}$",
                ylabel=r"$\varepsilon^*(k,p)\,/\,\varepsilon^*(k,1)$", ylim=(1e-4, 3),
                title="The per-harmonic horizon is predicted\nby the free atlas diagonal")
    axes[1].legend(fontsize=7, loc="lower right")

    summary = summaries.get("H1-circle-c033")
    if summary is not None:
        for colour, (band, entries) in zip(colours, sorted(records["H1-circle-c033"]["model_ratio"].items(),
                                                           key=lambda item: int(item[0]))):
            good = [(e["wavenumber"], e["ratio"]) for e in entries if e["ratio"] is not None]
            axes[2].plot([g[0] for g in good], [g[1] for g in good], "o-", color=colour, ms=3,
                         label=f"$M={band}$")
        axes[2].axhline(1, color="k", lw=0.8)
        axes[2].set(xlabel="wavenumber $k$", ylim=(0, 1.1),
                    ylabel="measured / predicted misfit decrease",
                    title="A full Gauss-Newton step delivers a third\nof its promise at low $k$")
        axes[2].legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(HERE / "horizon.png", dpi=150)
    plt.close(figure)


def main():
    records, summaries = {}, {}
    for name, atlas_name in ARMS.items():
        if not (HERE / name / "summary.json").exists():
            continue
        record, summary = analyse(name, atlas_name)
        records[name], summaries[name] = record, summary
    (HERE / "analysis.json").write_text(json.dumps(records, indent=2) + "\n")
    figures(records, summaries)
    for name, record in records.items():
        fit = record["ceiling_fit"] or {}
        law = record["law"] or {}
        print(f"{name}: order {record['order_median']:.2f}; "
              f"ceiling {fit.get('coefficient', float('nan')):.3f} k^{fit.get('exponent', float('nan')):+.2f}; "
              f"law median {law.get('median_dex', float('nan')):.3f} dex over {law.get('points', 0)} cells")


if __name__ == "__main__":
    main()
