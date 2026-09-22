"""Compare every saved arm against the digitized Figure 1. No solves.

Two readings of the published y axis are reported side by side: `normalized`
takes the plotted value as §4's eps_Gamma = dA/A, and `raw` divides it by the
true area first, on the reading that the plot plots what every driver in the
reference repository computes, the un-normalized symmetric-difference area.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


directory = Path(__file__).resolve().parent
PUBLISHED = directory.parent / "SC-013-paper-glider-recovery/figure1_comparison.json"
# Exact polar integration of the section 4.1 glider: A = (1/2) int r^2 dtheta.
TRUE_AREA = float(np.pi * .9**2 * (1 + .5 * (.2**2 + .02**2 + .1**2 + .1**2)))


def arm(folder, contrast):
    case = directory / folder / f"contrast_{contrast}"
    summary = json.loads((case / "summary.json").read_text())
    assert summary["status"] == "ladder_completed", (folder, summary["status"])
    for record in summary["decisions"]:
        assert record["committed"] and record["qualification"]["passed"]
    campaign = json.loads((directory / folder / "summary.json").read_text())
    return dict(
        settings=summary["case"], forwards=campaign["work"]["attempted"],
        elapsed_seconds=campaign["elapsed_seconds"],
        stages=[dict(k=r["decision"]["stage"]["wavenumber"],
                     update_modes=r["decision"]["stage"]["update_modes"],
                     nodes=r["decision"]["stage"]["nodes"],
                     stop=r["stop_reason"], accepted_updates=len(r["history"]) - 1,
                     relative_residual=r["relative_residual"],
                     area_error=r["area_error"]["relative_symmetric_difference"])
                for r in summary["decisions"]])


def agreement(stages, published):
    """Ratio published/ours under each reading; 1.0 means the curves coincide."""
    out = {}
    for reading, scale in (("normalized", 1.), ("raw", 1. / TRUE_AREA)):
        ratios = {}
        for stage in stages:
            value = published.get(str(stage["k"]))
            if value is not None:
                ratios[stage["k"]] = value * scale / stage["area_error"]
        series = np.array(list(ratios.values()))
        out[reading] = dict(ratios=ratios, median=float(np.median(series)),
                            minimum=float(series.min()), maximum=float(series.max()),
                            # Symmetric in over/under-shooting, unlike a plain mean.
                            log10_rms=float(np.sqrt(np.mean(np.log10(series) ** 2))))
    return out


def band_rules_coincide_below_unit_contrast():
    """'scaled' only differs from 'driver' when ki > k, so eta=0.33 needs one arm."""
    from experiments.shape_continuation.geometry import FourierCurve
    from experiments.shape_continuation.paper import Figure1Case
    circle = FourierCurve.circle()
    for k in (1., 2.5, 5.):
        driver = Figure1Case(.33, update_band_rule="driver").stage(circle, k)
        scaled = Figure1Case(.33, update_band_rule="scaled").stage(circle, k)
        if driver != scaled:
            return False
    return True


published = json.loads(PUBLISHED.read_text())
assert band_rules_coincide_below_unit_contrast()
report = {}
for folder in sorted(p.name for p in directory.iterdir()
                     if p.is_dir() and p.name.startswith("run-")):
    profile, contrast = folder[len("run-"):].rsplit("-contrast-", 1)
    data = arm(folder, contrast)
    data["agreement"] = agreement(data["stages"], published[contrast]["published"])
    report.setdefault(contrast, {})[profile] = data

(directory / "comparison.json").write_text(json.dumps(
    dict(true_area=TRUE_AREA, published_source=PUBLISHED.name,
         driver_and_scaled_bands_coincide_at_contrast_0_33=True, arms=report), indent=2) + "\n")

STYLE = {"paper": ("C0", "o"), "driver": ("C1", "s"), "scaled": ("C2", "^")}
figure, axes = plt.subplots(1, len(report), figsize=(6.4 * len(report), 4.4), squeeze=False)
for axis, (contrast, arms) in zip(axes[0], sorted(report.items())):
    points = published[contrast]["published"]
    wavenumbers = sorted(float(k) for k in points)
    axis.semilogy(wavenumbers, [points[str(k)] / TRUE_AREA for k in wavenumbers],
                  "k.-", lw=1, ms=9, label="Published / A (raw reading)")
    axis.semilogy(wavenumbers, [points[str(k)] for k in wavenumbers],
                  color="0.6", ls=":", lw=1, label="Published as printed")
    for profile, data in sorted(arms.items()):
        colour, marker = STYLE[profile]
        axis.semilogy([s["k"] for s in data["stages"]],
                      [s["area_error"] for s in data["stages"]],
                      color=colour, marker=marker, ms=4, lw=1.4,
                      label=f"{profile} profile")
    axis.set(xlabel="Wavenumber k", ylabel=r"$\varepsilon_\Gamma$",
             title=f"Contrast $k_i^2/k^2$ = {contrast}")
    axis.grid(alpha=.2)
    axis.legend(fontsize=7)
figure.tight_layout()
figure.savefig(directory / "comparison.png", dpi=160)
plt.close(figure)

for contrast, arms in sorted(report.items()):
    print(f"\n=== contrast ki^2/k^2 = {contrast} ===")
    print(f"{'profile':>8} {'stages':>7} {'forwards':>9} {'final area':>11} | "
          f"{'raw: median':>12} {'log10 RMS':>10} | {'norm: median':>13} {'log10 RMS':>10}")
    for profile, data in sorted(arms.items()):
        raw, norm = data["agreement"]["raw"], data["agreement"]["normalized"]
        print(f"{profile:>8} {len(data['stages']):7d} {data['forwards']:9d} "
              f"{data['stages'][-1]['area_error']:11.4g} | "
              f"{raw['median']:12.3f} {raw['log10_rms']:10.3f} | "
              f"{norm['median']:13.3f} {norm['log10_rms']:10.3f}")
