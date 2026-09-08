"""Plot archived iteration-2 long trajectories; no new inverse or forward work."""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
SOURCE = ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final/long-acquisition-20260908T174300326691Z"
metrics = json.loads((SOURCE / "metrics.json").read_text())
motion = json.loads((OUTPUT / "motion-review/motion_review.json").read_text())
geometry = {a: json.loads((SOURCE / a / "geometry_trajectory.json").read_text()) for a in ("E0", "E1")}
colors = {"E0": "#2474ad", "E1": "#de7826"}
labels = {"E0": "Paired-8 (42 updates)", "E1": "Multistatic-8 (31 updates)"}
fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
theta = np.linspace(0, 2*np.pi, 1201)
radius = .05 + .0125*np.cos(5*theta)
target = 1000*radius[:, None]*np.column_stack((np.cos(theta), np.sin(theta)))
axes[0, 0].plot(*target.T, "k-", lw=1.5, label="Target")
initial = np.asarray(geometry["E0"][0]["raw_contour"])
axes[0, 0].plot(*(1000*(np.vstack((initial, initial[0]))-.5)).T, "--", color="0.65", lw=1, label="Shared start")
for arm in ("E0", "E1"):
    rows = metrics["arms"][arm]["trajectory"]
    points = np.asarray(geometry[arm][-1]["raw_contour"])
    axes[0, 0].plot(*(1000*(np.vstack((points, points[0]))-.5)).T, color=colors[arm], label=labels[arm])
    states = [r["iteration"] for r in rows]
    reviewed = motion["arms"][arm]["trajectory"]
    attempts = [r["attempted_candidates_through_accept"] for r in reviewed]
    axes[0, 1].plot(attempts, [1000*r["raw_distances"]["symmetric_rms_m"] for r in reviewed], color=colors[arm], label=labels[arm])
    axes[0, 2].plot(states, [r["evaluation_3ghz_relative_l2"] for r in rows], color=colors[arm])
    amplitudes = [1000*r["polar_m5_amplitude_m"] if r.get("polar_m5_interpretable", True) else np.nan for r in reviewed]
    axes[1, 0].plot(states, amplitudes, color=colors[arm])
    axes[1, 1].plot(states, [r["field_statistics"]["spread"] for r in geometry[arm]], color=colors[arm])
    axes[1, 2].plot(states, [1e6*r["conversion_error_m"] for r in rows], color=colors[arm])
axes[0, 0].set(title="Final raw contours", xlabel="x relative to target center (mm)", ylabel="y relative to target center (mm)", aspect="equal")
axes[0, 0].legend(fontsize=8, loc="lower left")
axes[0, 1].set(title="Geometric progress versus attempted work", xlabel="Candidates through each accepted update", ylabel="Raw symmetric RMS boundary error (mm)")
axes[0, 1].legend(fontsize=8)
axes[0, 2].set(title="Disjoint 3 GHz evaluation", ylabel="Relative L2 error")
axes[1, 0].axhline(12.5, color="black", ls=":", label="Target amplitude")
axes[1, 0].annotate("Paired: polar spectrum invalid\nfrom update 25 onward", xy=(24, 7.27), xytext=(11, 9.4), fontsize=8,
                    arrowprops={"arrowstyle": "->", "color": ".4"})
axes[1, 0].set(title="Five-lobe amplitude remains unrecovered", ylabel="Polar mode-5 amplitude (mm)", ylim=(0, 14))
axes[1, 0].legend(fontsize=8, loc="upper right")
axes[1, 1].set(title="On-contour gradient conditioning", ylabel="Maximum / minimum gradient magnitude")
axes[1, 2].axhline(200, color="black", ls=":", label="Unchanged distance limit")
axes[1, 2].set(title="Accepted raw-to-converted discrepancy", ylabel="Maximum conversion error (µm)")
axes[1, 2].legend(fontsize=8)
for ax in (axes[0, 2], *axes[1]):
    ax.set_xlabel("Accepted update")
for ax in axes.flat:
    ax.grid(alpha=.2)
fig.suptitle("Iteration 3: multistatic improves geometry; both searches stop before full star recovery", fontsize=13)
fig.savefig(OUTPUT / "comparison.png", dpi=170)
fig.savefig(OUTPUT / "comparison.pdf")
print(OUTPUT / "comparison.png")
