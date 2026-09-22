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
CASES = (("0.33", "run-contrast-0.33", "contrast_0.33"),
         ("10", "run-contrast-10", "contrast_10"))


def radial_spectrum(shape, modes=10, count=8192):
    """Polar coefficients of a star-shaped curve, for comparison with §4.1."""
    z = shape.values(count)
    order = np.argsort(np.angle(z))
    grid = np.linspace(-np.pi, np.pi, count, endpoint=False)
    radius = np.interp(grid, np.angle(z)[order], np.abs(z)[order], period=2 * np.pi)
    spectrum = np.fft.rfft(radius) / count
    return radius, np.abs(np.r_[spectrum[0].real, 2 * spectrum[1:modes + 1]])


def audit(bundle, leaf):
    """Re-derive every claim from the saved bundle, asserting its invariants."""
    campaign = json.loads((bundle / "summary.json").read_text())
    case = bundle / leaf
    manifest = json.loads((case / "manifest.json").read_text())
    summary = json.loads((case / "summary.json").read_text())
    assert summary["status"] == "ladder_completed"
    assert all(c["passed"] and c["relative_difference"] <= 1e-7
               for c in summary["observation_checks"])
    rows = []
    for record in summary["decisions"]:
        history = record["history"]
        assert record["committed"] and record["qualification"]["passed"]
        check = record["qualification"]["diagnostics"]
        assert max(check["field_relative"], check["jacobian_relative"]) <= check["tolerance"]
        # Every accepted update strictly decreased its own stage residual.
        assert all(b["relative_residual"] < a["relative_residual"]
                   for a, b in zip(history, history[1:]))
        with np.load(case / f"decision_{record['index']:03d}.npz") as states:
            assert len([key for key in states if key.startswith("state_")]) == len(history)
            assert np.array_equal(states[f"state_{len(history)-1}"], states["committed_shape"])
        stage = record["decision"]["stage"]
        rows.append(dict(k=stage["wavenumber"], update_modes=stage["update_modes"],
            curve_modes=stage["curve_modes"], curvature_modes=stage["curvature_modes"],
            nodes=stage["nodes"], stop=record["stop_reason"],
            accepted_updates=len(history) - 1,
            relative_residual=record["relative_residual"],
            relative_symmetric_area_error=record["area_error"]["relative_symmetric_difference"],
            trial_counts=dict(Counter(t["status"] for t in record["trials"]))))
    with np.load(case / "endpoint.npz") as arrays:
        final = FourierCurve(arrays["shape"])
    with np.load(case / "observation_000.npz") as arrays:
        truth = FourierCurve(arrays["truth"])
    true_radius, true_modes = radial_spectrum(truth)
    final_radius, final_modes = radial_spectrum(final)
    report = dict(source_commit=manifest["commit"],
        source_hash_mismatches=[p for p, h in manifest["source_sha256"].items()
            if hashlib.sha256((repo / p).read_bytes()).hexdigest() != h],
        elapsed_seconds=campaign["elapsed_seconds"], work=campaign["work"],
        all_saved_resolution_checks_pass=True,
        accepted_updates=sum(r["accepted_updates"] for r in rows),
        rejected_trials=sum(v for r in rows for k, v in r["trial_counts"].items()
                            if k != "accepted"),
        final_wavenumber=rows[-1]["k"], stages=rows,
        # Truth is an evaluation input only; it never enters the optimizer.
        radial_modes=dict(truth=true_modes.tolist(), recovered=final_modes.tolist()),
        maximum_radial_error=float(np.max(np.abs(true_radius - final_radius))),
        rms_radial_error=float(np.sqrt(np.mean((true_radius - final_radius) ** 2))),
        final_relative_symmetric_area_error=rows[-1]["relative_symmetric_area_error"],
        extra_forward_or_inverse_solves=0)
    return report, truth, final


reports = {}
shapes = {}
for label, folder, leaf in CASES:
    reports[label], truth, shapes[label] = audit(directory / folder, leaf)
(directory / "analysis.json").write_text(json.dumps(reports, indent=2) + "\n")

figure, axes = plt.subplots(1, 3, figsize=(14.5, 4.4))
circle = FourierCurve.circle().values(4096)
axes[0].plot(np.r_[circle.real, circle.real[0]], np.r_[circle.imag, circle.imag[0]],
             color="0.7", ls=":", label="Initial circle")
for label, style in (("0.33", "C0-"), ("10", "C1-")):
    z = shapes[label].values(4096)
    axes[0].plot(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]], style,
                 label=f"Recovered, $\\eta$={label} (k={reports[label]['final_wavenumber']:g})")
z = truth.values(4096)
axes[0].plot(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]], "k--", lw=1, label="True glider")
axes[0].set(aspect="equal", xlabel="x", ylabel="y", title="Figure 1 reconstructions")
axes[0].legend(fontsize=8)

for label, style in (("0.33", "C0o-"), ("10", "C1s-")):
    rows = reports[label]["stages"]
    axes[1].semilogy([r["k"] for r in rows],
                     [r["relative_symmetric_area_error"] for r in rows], style,
                     label=f"$\\eta$={label}")
axes[1].set(xlabel="Wavenumber k", ylabel=r"$\varepsilon_\Gamma$",
            title="Area error against frequency")
axes[1].legend(fontsize=8)
axes[1].grid(alpha=.2)

index = np.arange(len(reports["0.33"]["radial_modes"]["truth"]))
axes[2].bar(index - .27, reports["0.33"]["radial_modes"]["truth"], .27, label="True $r_n$", color="k")
axes[2].bar(index, reports["0.33"]["radial_modes"]["recovered"], .27, label=r"$\eta$=0.33", color="C0")
axes[2].bar(index + .27, reports["10"]["radial_modes"]["recovered"], .27, label=r"$\eta$=10", color="C1")
axes[2].set(xlabel="Polar mode n", ylabel="Amplitude", xticks=index,
            title="§4.1 radial coefficients")
axes[2].legend(fontsize=8)
figure.tight_layout()
figure.savefig(directory / "reconstruction.png", dpi=160)
plt.close(figure)
print(json.dumps({c: {k: v for k, v in r.items() if k != "stages"}
                  for c, r in reports.items()}, indent=2))
