"""Audit and plot saved outputs only. No forward or inverse calls."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experiments.shape_continuation.geometry import FourierCurve


directory = Path(__file__).resolve().parent
repo = directory.parents[3]
bundle = directory / "run"
case = bundle / "contrast_0.33"
summary = json.loads((case / "summary.json").read_text())
campaign = json.loads((bundle / "summary.json").read_text())
manifest = json.loads((case / "manifest.json").read_text())
rows = []
for record in summary["decisions"]:
    history = record["history"]
    assert record["committed"] and record["qualification"]["passed"]
    check = record["qualification"]["diagnostics"]
    assert max(check["field_relative"], check["jacobian_relative"]) <= check["tolerance"]
    assert all(b["relative_residual"] < a["relative_residual"] for a, b in zip(history, history[1:]))
    with np.load(case / f"decision_{record['index']:03d}.npz") as states:
        assert len([key for key in states if key.startswith("state_")]) == len(history)
        assert np.array_equal(states[f"state_{len(history)-1}"], states["committed_shape"])
    rows.append(dict(k=record["decision"]["stage"]["wavenumber"],
        stop=record["stop_reason"], accepted_updates=len(history)-1,
        relative_residual=record["relative_residual"],
        relative_symmetric_area_error=record["area_error"]["relative_symmetric_difference"],
        trial_counts=dict(Counter(t["status"] for t in record["trials"]))))

assert len(rows) == 5 and rows[-1]["k"] == 2.
assert all(c["passed"] and c["relative_difference"] <= 1e-7 for c in summary["observation_checks"])
with np.load(case / "endpoint.npz") as arrays:
    final = FourierCurve(arrays["shape"])
with np.load(case / "decision_004.npz") as arrays:
    assert np.array_equal(final.coefficients, arrays["committed_shape"])
with np.load(case / "observation_000.npz") as arrays:
    truth = FourierCurve(arrays["truth"])

report = dict(source_commit=manifest["commit"],
    source_hash_mismatches=[p for p, h in manifest["source_sha256"].items()
        if hashlib.sha256((repo / p).read_bytes()).hexdigest() != h],
    elapsed_seconds=campaign["elapsed_seconds"], work=campaign["work"],
    all_saved_resolution_checks_pass=True, accepted_updates=sum(r["accepted_updates"] for r in rows),
    stages=rows, successful_recovery=False, extra_forward_or_inverse_solves=0)
(directory / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")

figure, axes = plt.subplots(1, 2, figsize=(10, 4.2))
for shape, label, style in ((FourierCurve.circle(), "Initial circle", "--"),
                             (truth, "True glider", "k-"), (final, "Recovered at k=2", "C1-")):
    z = shape.values(4096)
    axes[0].plot(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]], style, label=label)
axes[0].set(aspect="equal", xlabel="x", ylabel="y", title="Contrast 0.33: partial reconstruction")
axes[0].legend(fontsize=8)
k = [r["k"] for r in rows]
axes[1].semilogy(k, [r["relative_symmetric_area_error"] * 100 for r in rows], "o-", label="Symmetric area error")
axes[1].semilogy(k, [r["relative_residual"] * 100 for r in rows], "s-", label="Stage data residual")
axes[1].axvspan(1.75, 2, alpha=.1, color="red", label="No accepted updates")
axes[1].set(xlabel="Wavenumber k", ylabel="Error (%)", xticks=k,
            title="Data objective changes at each frequency")
axes[1].legend(fontsize=8)
axes[1].grid(alpha=.2)
figure.tight_layout()
figure.savefig(directory / "reconstruction.png", dpi=160)
plt.close(figure)
print(json.dumps(report, indent=2))
