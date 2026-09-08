"""Plot the saved short acquisition comparison; no geometry or forward solves."""
from pathlib import Path
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from config import star_config

SOURCE = ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final/inverse-20260908T170732213677Z"
OUTPUT = Path(__file__).resolve().parent
metrics = json.loads((SOURCE / "metrics.json").read_text())
geometry = {arm: json.loads((SOURCE / arm / "geometry_trajectory.json").read_text()) for arm in ("E0", "E1")}
labels = {"E0": "Paired-8", "E1": "Multistatic-8"}
colors = {"E0": "#2474ad", "E1": "#de7826"}
fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
theta = np.linspace(0, 2*np.pi, 1001)
radius = star_config.TARGET_MEAN_RADIUS * (1 + star_config.TARGET_STAR_AMPLITUDE * np.cos(star_config.TARGET_STAR_LOBES * theta))
# Target geometry is used only for this posthoc figure.
center = np.asarray((star_config.TARGET_CENTER_X, star_config.TARGET_CENTER_Y))
target = center + radius[:, None] * np.column_stack((np.cos(theta), np.sin(theta)))
axes[0, 0].plot(*(1000 * (target - center)).T, color="black", lw=1.5, label="Target")
initial = np.asarray(geometry["E0"][0]["raw_contour"])
axes[0, 0].plot(*(1000 * (np.vstack((initial, initial[0])) - center)).T, "--", color="0.55", lw=1, label="Shared start")
for arm, records in geometry.items():
    curve = np.asarray(records[-1]["raw_contour"])
    axes[0, 0].plot(*(1000 * (np.vstack((curve, curve[0])) - center)).T, color=colors[arm], lw=1.5, label=labels[arm])
    rows = metrics["arms"][arm]["trajectory"]
    iteration = [r["iteration"] for r in rows]
    axes[0, 1].plot(iteration, [1000*r["mean_node_to_exact_boundary_distance_m"] for r in rows], "o-", color=colors[arm], label=labels[arm])
    axes[0, 2].plot(iteration, [r["evaluation_3ghz_relative_l2"] for r in rows], "o-", color=colors[arm])
    axes[1, 0].plot(iteration, [r["field_statistics"]["minimum"] for r in records], "o--", color=colors[arm], label=labels[arm]+" min")
    axes[1, 0].plot(iteration, [r["field_statistics"]["maximum"] for r in records], "o-", color=colors[arm], label=labels[arm]+" max")
    errors = []
    for record in records:
        coefficient = record["radial_spectrum"]["radial_complex_coefficients"][5]
        # The FFT samples begin at -pi, so the physical mode-5 coefficient
        # has the opposite sign. Compare both quadratures, not just magnitude.
        cosine, sine = -2*coefficient["real"], 2*coefficient["imag"]
        errors.append(1000*np.hypot(cosine - star_config.TARGET_MEAN_RADIUS*star_config.TARGET_STAR_AMPLITUDE, sine))
    axes[1, 1].plot(iteration, errors, "o-", color=colors[arm], label=labels[arm])
    axes[1, 2].plot(iteration, [1e6*r["conversion_error_m"] for r in rows], "o-", color=colors[arm])
axes[0, 0].set(title="Raw contours after five updates", xlabel="x relative to target center (mm)", ylabel="y relative to target center (mm)", aspect="equal")
axes[0, 0].legend(fontsize=8, loc="lower left")
axes[0, 1].set(title="Converted boundary: mean target distance", ylabel="One-sided node-to-target distance (mm)")
axes[0, 1].legend(fontsize=9)
axes[0, 2].set(title="Disjoint 3 GHz evaluation", ylabel="Relative L2 error")
axes[1, 0].set(title="On-contour field gradient", ylabel="Unclipped gradient magnitude")
axes[1, 0].legend(fontsize=8, ncol=2)
axes[1, 1].set(title="Five-lobe shape error, including phase", ylabel="Mode-5 coefficient error (mm)")
axes[1, 1].legend(fontsize=8)
axes[1, 2].set(title="Accepted conversion error (limit: 200 µm)", ylabel="Maximum conversion distance (µm)")
for ax in axes.flat:
    ax.grid(alpha=.18)
for ax in (axes[0, 1], axes[0, 2], axes[1, 0], axes[1, 1], axes[1, 2]):
    ax.set(xlabel="Accepted update", xticks=range(6))
fig.suptitle("Short star inverse: acquisition improves early geometric motion; full lobe recovery remains untested", fontsize=13)
fig.savefig(OUTPUT / "comparison.png", dpi=170)
fig.savefig(OUTPUT / "comparison.pdf")
print(OUTPUT / "comparison.png")
