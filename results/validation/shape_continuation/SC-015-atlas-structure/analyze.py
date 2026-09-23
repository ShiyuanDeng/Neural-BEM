"""Reduce the saved atlases to the claims this record makes, and draw them.

Run from the repository root with the package importable:

    PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-015-atlas-structure/analyze.py
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ARMS = ("A-circle-c033-paperacq", "B-circle-c033-fixedacq", "C-circle-c10-paperacq",
        "D-truth-c033-paperacq", "E-iterate-c033-paperacq")


def load(name):
    arrays = np.load(HERE / name / "atlas.npz")
    summary = json.loads((HERE / name / "summary.json").read_text())
    return arrays, summary


def per_harmonic(values, harmonics):
    """Combine each harmonic's cosine and sine columns in quadrature."""
    band = int(harmonics.max())
    out = np.zeros((len(values), band + 1))
    for index in range(len(values)):
        np.add.at(out[index], harmonics, values[index] ** 2)
    return np.sqrt(out)


def frontier(sensitivity, perimeter, threshold):
    """Highest harmonic detectable at an RMS displacement of `threshold`."""
    detectable = 1.0 / (np.sqrt(perimeter) * np.maximum(sensitivity, 1e-300)) <= threshold
    return np.array([np.max(np.nonzero(row)[0]) if row.any() else 0 for row in detectable])


def counts(arrays, summary, threshold):
    """Harmonics the diagonal calls detectable, against directions actually determined."""
    perimeter = summary["perimeter"]
    limit = 1.0 / (threshold ** 2 * perimeter)
    columns = (arrays["sensitivity"] ** 2 >= limit).sum(axis=1)
    directions = (arrays["eigenvalues"] >= limit).sum(axis=1)
    return columns, directions


def gauge_mixing(coefficients, harmonics=(1, 5, 10, 20, 40, 60), observable=5, samples=16384):
    """How much of an arclength harmonic lands in low ANGULAR orders.

    A harmonic index names a different function on every curve. On a circle
    the arclength harmonic is exactly the angular harmonic; on a wiggly curve
    it is a chirp, and part of it lives in the low angular orders the far
    field can actually see. Any claim that a high harmonic is "visible" at a
    non-circular boundary has to be read against this number, because the
    axis itself has changed meaning.
    """
    import sys
    sys.path.insert(0, str(HERE.parents[3]))
    from experiments.shape_continuation.geometry import FourierCurve, arclength_angles
    shape = FourierCurve(coefficients)
    nodes = shape.nodes(samples)
    angles, _ = arclength_angles(nodes)
    polar = np.unwrap(np.angle(nodes.points[:, 0] + 1j * nodes.points[:, 1]))
    grid = np.linspace(polar[0], polar[0] + 2 * np.pi, samples, endpoint=False)
    orders = np.fft.fftfreq(samples, 1 / samples).astype(int)
    out = {}
    for harmonic in harmonics:
        resampled = np.interp(grid, polar, np.cos(harmonic * angles), period=2 * np.pi)
        energy = np.abs(np.fft.fft(resampled) / samples) ** 2
        out[str(harmonic)] = float(np.sqrt(np.sum(energy[np.abs(orders) <= observable])
                                           / np.sum(energy)))
    return dict(observable_order=observable, low_order_amplitude_fraction=out)


def analyse(name):
    arrays, summary = load(name)
    wavenumbers, harmonics = arrays["wavenumbers"], arrays["harmonics"]
    sensitivity = per_harmonic(arrays["sensitivity"], harmonics)
    perimeter = summary["perimeter"]
    record = dict(name=name, geometry=summary["geometry_label"], contrast=summary["contrast"],
                  acquisition=summary["acquisition"], perimeter=perimeter,
                  atlas_gate_passed=summary["atlas_gate_passed"],
                  wavenumbers=[float(wavenumbers[0]), float(wavenumbers[-1])])
    record["frontier"] = {}
    for threshold in (0.1, 0.01, 0.001):
        heights = frontier(sensitivity, perimeter, threshold)
        mask = wavenumbers >= 2
        slope, intercept = np.polyfit(wavenumbers[mask], heights[mask], 1)
        record["frontier"][f"{threshold:g}"] = dict(
            slope=float(slope), intercept=float(intercept),
            at_k4=int(heights[np.isclose(wavenumbers, 4)][0]) if (wavenumbers == 4).any() else None,
            at_k8=int(heights[np.isclose(wavenumbers, 8)][0]) if (wavenumbers == 8).any() else None,
            heights=heights.tolist())
    columns, directions = counts(arrays, summary, 0.01)
    overcount = columns / np.maximum(directions, 1)
    record["cross_talk"] = dict(
        threshold=0.01, columns=columns.tolist(), directions=directions.tolist(),
        median_overcount=float(np.median(overcount)), max_overcount=float(overcount.max()))
    gradient = arrays["gradient"]
    norms = np.linalg.norm(gradient, axis=1)
    unit = gradient / np.where(norms > 0, norms, 1.0)[:, None]
    alignment = unit @ unit.T
    record["alignment"] = dict(
        to_lowest=alignment[:, 0].tolist(),
        decorrelation_k=next((float(wavenumbers[i]) for i in range(len(wavenumbers))
                              if alignment[i, 0] < 0.5), None),
        adjacent_median=float(np.median(np.diag(alignment, 1))),
        negative_pairs=float(np.mean(alignment < 0)))
    if "leakage" in arrays:
        leakage = arrays["leakage"]
        channels = np.array([max(4, int(10 * k)) if summary["acquisition"] == "paper"
                             else int(summary["acquisition"]) for k in wavenumbers])
        observable = arrays["sensitivity"] > 1e-3 * arrays["sensitivity"].max(axis=1, keepdims=True)
        on_line = np.array([np.nanmean(1 - leakage[i][observable[i]]) if observable[i].any() else np.nan
                            for i in range(len(wavenumbers))])
        # A column spread evenly over the data modes would put 2/nd of its
        # energy on the selection line, so this ratio is 1 for no structure.
        record["selection"] = dict(
            mean_on_line_fraction=on_line.tolist(),
            concentration=(on_line / (2.0 / channels)).tolist(),
            median_concentration=float(np.nanmedian(on_line / (2.0 / channels))),
            maximum_possible=(channels / 2.0).tolist())
    record["gauge_mixing"] = gauge_mixing(arrays["geometry"])
    record["residual"] = [s["relative_residual"] for s in summary["stages"]]
    record["effective_rank"] = [s["effective_rank"] for s in summary["stages"]]
    return record, arrays, summary, sensitivity


def figures(records, data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    figure, axes = plt.subplots(2, 2, figsize=(12, 9))
    for axis, name, title in ((axes[0, 0], "A-circle-c033-paperacq", "unit circle, contrast 0.33"),
                              (axes[0, 1], "C-circle-c10-paperacq", "unit circle, contrast 10"),
                              (axes[1, 0], "D-truth-c033-paperacq", "glider truth, contrast 0.33"),
                              (axes[1, 1], "E-iterate-c033-paperacq", "mid-inversion iterate, contrast 0.33")):
        if name not in data:
            axis.set_axis_off()
            continue
        arrays, summary, sensitivity = data[name]
        wavenumbers = arrays["wavenumbers"]
        relative = sensitivity / sensitivity.max(axis=1, keepdims=True)
        image = axis.pcolormesh(wavenumbers, np.arange(sensitivity.shape[1]),
                                np.maximum(relative.T, 1e-12), norm=LogNorm(1e-12, 1),
                                shading="nearest", cmap="magma")
        contrast = summary["contrast"]
        axis.plot(wavenumbers, 3 * wavenumbers * max(1, np.sqrt(contrast)), "c--", lw=1.5,
                  label=r"$3\max(k,k_i)$ (paper)")
        axis.plot(wavenumbers, 3 * wavenumbers, "w:", lw=1.5, label="$3k$")
        heights = np.array(records[name]["frontier"]["0.01"]["heights"])
        axis.plot(wavenumbers, heights, "lime", lw=2, label=r"detectable at $10^{-2}$")
        mixing = records[name]["gauge_mixing"]["low_order_amplitude_fraction"].get("60")
        if not np.isclose(summary["perimeter"], 2 * np.pi, atol=1e-6):
            title += f"\n(arclength gauge: {100 * mixing:.1f}% of $p=60$ sits below angular order 5)"
        axis.set(title=title, xlabel="wavenumber $k$", ylabel="shape harmonic $p$",
                 ylim=(0, sensitivity.shape[1] - 1))
        axis.legend(loc="upper left", fontsize=8, framealpha=0.6)
        figure.colorbar(image, ax=axis, label="whitened sensitivity / peak")
    figure.suptitle("Frequency $\\times$ shape-harmonic sensitivity, and the bands that are prescribed")
    figure.tight_layout()
    figure.savefig(HERE / "sensitivity.png", dpi=150)
    plt.close(figure)

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for name, style in (("A-circle-c033-paperacq", "C0-o"), ("E-iterate-c033-paperacq", "C3-s"),
                        ("C-circle-c10-paperacq", "C2-^")):
        if name not in data:
            continue
        record = records[name]
        wavenumbers = data[name][0]["wavenumbers"]
        axes[0].plot(wavenumbers, record["cross_talk"]["columns"], style[:2] + "-",
                     label=f"{record['geometry']} diagonal", ms=3)
        axes[0].plot(wavenumbers, record["cross_talk"]["directions"], style[:2] + "--",
                     label=f"{record['geometry']} spectrum", ms=3)
        axes[1].plot(wavenumbers, record["alignment"]["to_lowest"], style, ms=3,
                     label=f"{record['geometry']}, contrast {record['contrast']:g}")
        if "selection" in record:
            axes[2].semilogy(wavenumbers, record["selection"]["concentration"], style, ms=3,
                             label=f"{record['geometry']}")
    axes[0].set(xlabel="wavenumber $k$", ylabel="count above one noise unit at $10^{-2}$",
                title="Apparently visible harmonics\nagainst directions actually determined")
    axes[0].legend(fontsize=7)
    axes[1].axhline(0, color="k", lw=0.8)
    axes[1].axhline(0.5, color="gray", ls=":", lw=0.8)
    axes[1].set(xlabel="wavenumber $k$", ylabel=r"$\cos$ angle with the $k=1$ gradient",
                title="Signed cross-frequency agreement\n(a magnitude atlas cannot see this)")
    axes[1].legend(fontsize=7)
    axes[2].axhline(1, color="k", lw=0.8)
    axes[2].set(xlabel="wavenumber $k$", ylabel="on-line energy / unstructured share",
                title="Concentration on the circle's exact\nselection line $a+b=\\pm p$")
    axes[2].legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(HERE / "structure.png", dpi=150)
    plt.close(figure)


def main():
    records, data = {}, {}
    for name in ARMS:
        if not (HERE / name / "summary.json").exists():
            continue
        record, arrays, summary, sensitivity = analyse(name)
        records[name] = record
        data[name] = (arrays, summary, sensitivity)
    (HERE / "analysis.json").write_text(json.dumps(records, indent=2) + "\n")
    figures(records, data)
    for name, record in records.items():
        print(f"{name}: frontier slope {record['frontier']['0.01']['slope']:.2f} k"
              f" + {record['frontier']['0.01']['intercept']:.1f};"
              f" median diagonal/spectrum overcount {record['cross_talk']['median_overcount']:.2f};"
              f" gradient decorrelates at k={record['alignment']['decorrelation_k']}")


if __name__ == "__main__":
    main()
