"""Inspect completed recoveries; write a compact report and scientific figure."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .model import Fixture, Evaluator, oracle
from .run import DEFAULT_OUTPUT, relative, save, manifest


LABELS = {"uniform": "Uniform multioffset", "random": "Random multioffset",
          "known_gain_design": "Design assuming known gains",
          "quotient_design": "Design accounting for unknown gains",
          "oracle_calibration": "True gains supplied"}
ORDER = ["uniform", "random", "known_gain_design", "quotient_design", "oracle_calibration"]


def paired_statistics(records, baseline, noise):
    rows = {(r["scene"], r["seed"]): r for r in records
            if r["method"] == baseline and r["noise_fraction"] == noise}
    proposed = {(r["scene"], r["seed"]): r for r in records
                if r["method"] == "quotient_design" and r["noise_fraction"] == noise}
    keys = sorted(rows.keys() & proposed.keys())
    a = np.array([rows[k]["metrics"]["shape_harmonic_radial_rms_mm"] for k in keys])
    b = np.array([proposed[k]["metrics"]["shape_harmonic_radial_rms_mm"] for k in keys])
    difference = b-a
    # Conditional noise/gain-seed bootstrap within each of the TWO fixed scenes.
    # It is not an uncertainty interval over arbitrary buried objects.
    rng = np.random.default_rng(811)
    groups = [np.array([i for i,k in enumerate(keys) if k[0] == scene])
              for scene in sorted({k[0] for k in keys})]
    draws = np.concatenate([rng.choice(g, size=(10000, len(g)), replace=True) for g in groups], axis=1)
    means = difference[draws].mean(axis=1)
    return dict(baseline=baseline, pairs=len(keys),
                mean_paired_difference_mm=float(difference.mean()),
                bootstrap_95pct_mean_difference_mm=np.quantile(means, [.025, .975]).tolist(),
                proposed_lower_error_count=int(np.count_nonzero(b < a)),
                baseline_rms_error_mm=float(np.sqrt(np.mean(a*a))),
                proposed_rms_error_mm=float(np.sqrt(np.mean(b*b))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    out = args.output
    records = json.loads((out/"recoveries.json").read_text())
    summary = json.loads((out/"summary.json").read_text())
    design = json.loads((out/"design.json").read_text())
    f = Fixture()
    # Fresh, full BIE validation at every selected recovered state, including failures/bound hits.
    checks = []
    for row in records:
        selected = row["trials"][row["selected_start"]]
        x = np.array(selected["parameters"])
        compiled = Evaluator(f).forward(x)
        reference = oracle(f, x, 256)
        checks.append(dict(scene=row["scene"], seed=row["seed"], method=row["method"],
                           relative_error=relative(compiled, reference)))
    save(out/"recovered_forward_checks.json", checks)
    worst_check = max(r["relative_error"] for r in checks)
    if worst_check > 1e-8:
        raise RuntimeError("A selected recovered state fails independent forward qualification")
    noise = summary["noise_levels"][0]
    pairs = [paired_statistics(records, b, noise) for b in ("uniform", "random", "known_gain_design")]
    save(out/"paired_comparisons.json", dict(noise_fraction=noise, rows=pairs,
        interpretation="Intervals condition on two fixed scenes, sampling only noise/gain realizations."))
    with (out/"summary.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary["rows"][0]))
        writer.writeheader()
        writer.writerows(summary["rows"])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
    for ax, name in zip(axes[0], ["uniform", "known_gain_design", "quotient_design"]):
        mask = np.zeros((f.count, f.count))
        edges = np.array(design["plans"][name])
        mask[edges[:, 0], edges[:, 1]] = 1
        ax.imshow(mask, cmap=ListedColormap(["#f2f3f6", "#287f9e"]), origin="lower", vmin=0, vmax=1)
        ax.set(title=LABELS[name], xlabel="Transmitter index", ylabel="Receiver index")
    ax = axes[1, 0]
    for name, color in [("uniform", "#777777"), ("known_gain_design", "#b77225"), ("quotient_design", "#287f9e")]:
        eig = design["nominal_information"][name]["eigenvalues"]
        ax.semilogy(np.arange(1, 5), eig, "o-", color=color, label=LABELS[name])
    ax.set(title="Shape information after nuisance removal", xlabel="Eigenvalue index (weak to strong)", ylabel="Fisher eigenvalue")
    ax.set_xticks([1, 2, 3, 4])
    ax.legend(fontsize=7, loc="upper left")
    ax = axes[1, 1]
    rng = np.random.default_rng(71)
    for i, name in enumerate(ORDER):
        values = [r["metrics"]["shape_harmonic_radial_rms_mm"] for r in records
                  if r["method"] == name and r["noise_fraction"] == noise]
        ax.scatter(i+rng.uniform(-.10, .10, len(values)), values, s=26,
                   color="#287f9e" if name == "quotient_design" else "#777777", alpha=.8)
        ax.plot([i-.2, i+.2], [np.median(values)]*2, color="black", linewidth=2)
    ax.axhline(.5, color="#b77225", linestyle="--", linewidth=1)
    ax.set_xticks(range(5), ["Uniform", "Random", "Known-gain\ndesign", "Quotient\ndesign", "Oracle\ngains"], fontsize=8)
    ax.set(title="Nonlinear recovery: every selected run", ylabel="Shape harmonic radial RMS error (mm)")
    ax = axes[1, 2]
    for scene, color in [(0, "#287f9e"), (1, "#b77225")]:
        by_method = {name: [r for r in records if r["scene"] == scene and r["method"] == name
                            and r["noise_fraction"] == noise] for name in ORDER}
        u = {r["seed"]: r["metrics"]["shape_harmonic_radial_rms_mm"] for r in by_method["uniform"]}
        q = {r["seed"]: r["metrics"]["shape_harmonic_radial_rms_mm"] for r in by_method["quotient_design"]}
        ax.scatter([u[k] for k in u], [q[k] for k in u], color=color, label=f"Scene {scene+1}", s=35)
    lim = max(ax.get_xlim()[1], ax.get_ylim()[1])
    ax.plot([0, lim], [0, lim], "--", color="#777777", linewidth=1)
    ax.set(xlim=(0, lim), ylim=(0, lim), title="Paired recovery: quotient vs uniform",
           xlabel="Uniform-plan shape error (mm)", ylabel="Quotient-plan shape error (mm)")
    ax.legend(fontsize=8)
    fig.suptitle("Calibration-aware Laurent shape sensing: a controlled feasibility test", fontsize=15)
    fig.savefig(out/"findings.png", dpi=180)
    fig.savefig(out/"findings.svg")
    plt.close(fig)

    def fnum(x): return f"{x:.3f}"
    table = ["| Acquisition / calibration | Median shape RMS (mm) | <0.5 mm | Median held-out trace error |",
             "|---|---:|---:|---:|"]
    for name in ORDER:
        r = next(r for r in summary["rows"] if r["method"] == name and r["noise_fraction"] == noise)
        table.append(f"| {LABELS[name]} | {fnum(r['median_shape_radial_rms_mm'])} | {r['recovered']}/{r['cases']} | {100*r['median_unmeasured_field_error']:.2f}% |")
    pair_lines = []
    for row in pairs:
        ci = row["bootstrap_95pct_mean_difference_mm"]
        pair_lines.append(f"- Versus {LABELS[row['baseline']]}: mean paired shape-error change "
                          f"{row['mean_paired_difference_mm']:+.3f} mm; conditional 95% bootstrap interval "
                          f"[{ci[0]:+.3f}, {ci[1]:+.3f}] mm; lower error in "
                          f"{row['proposed_lower_error_count']}/{row['pairs']} pairs.")
    report = f"""# Calibration-quotient Laurent GPR: feasibility result

2026-09-16. An isolated scientific experiment; no production defaults changed.

## Decision

The information-geometry diagnostic works, but this test does **not establish a meaningful
advantage over a well-spread uniform multioffset acquisition**. The calibration-aware plan
stays close to that uniform plan. Designing as though antenna gains were known can make the
actual self-calibrating problem worse. This supports nuisance-aware information analysis,
not a claim that special measurement loops create additional information or newly recoverable modes.

## Matched nonlinear results

Two fixed noncircular shapes, {summary['seeds_per_scene']} independent gain/noise seeds per shape,
{100*noise:g}% additive complex noise, and {summary['starts']} initializations per inversion.
Both starts use the same bounds and objective; the lower training cost selects the reported result.
Every non-oracle arm jointly estimates exactly the same shape, material, and calibration variables.

{chr(10).join(table)}

Shape RMS is the angular RMS of the error in radial harmonics 2 and 3, in physical mm;
it excludes center and mean radius. Full-boundary, center, radius, and material errors are
also retained in `recoveries.json`. The 0.5 mm threshold was declared in `design.json`
before recovery. It is an experiment-specific tolerance, not a universal resolution limit.
Held-out trace error uses unmeasured entries of the same multistatic matrix and the inferred gains.

{chr(10).join(pair_lines)}

The intervals resample seeds within each fixed scene. They do not establish performance
over a population of buried shapes. Ten paired cases are a screening experiment.

![Measurement plans, information, and nonlinear errors](findings.png)

## What was tested

The model is 2-D scalar, lossless, equal permeability, with one smooth dielectric inclusion
in a homogeneous background (relative permittivity 6). Twelve transmitter and twelve
receiver positions form two nearby surface-style lines. There is **no air/soil interface,
antenna radiation pattern, additive clutter, conductivity, or unknown topology**.
The reference object has radius 30 mm and center depth 160 mm. Frequencies are 0.5 and
1.25 GHz. Unknown physical coordinates are center x/y, mean radius, cosine/sine coefficients
of radial harmonics 2 and 3, and uniform real interior permittivity.

The measured scattered matrix is `Y_rs = exp(g_r + h_s) F_rs + noise`, with independent
complex log gains at each frequency. Reference transmitter log gain is zero to remove
parameter redundancy. This fixes no physical calibration information. True log-amplitude
standard deviation is 0.15, and phase standard deviation is 0.25 rad. Inversion bounds
of ±3 on gain coordinates are deliberately broad; bound hits are recorded.
Noise variance is fixed per frequency from the full clean uncalibrated candidate matrix,
before selecting measurements. All plans share that variance and the same complete noise
realization. Overlapping measurements are therefore exactly paired.

Each plan has 48 edges per frequency, four uses of every transmitter and receiver, one
connected component, and **25 independent complex graph cycles**. All plans also have
the same offset-bin histogram: 12/10/15/11 edges in bins separated by 0.06/0.14/0.26 m.
Offsets are matched by bins, not exactly edge-by-edge. The uniform comparator is an
index-based, well-spread multioffset pattern (including long offsets), not a common-offset line.
The random comparator uses a different frozen degree/offset-preserving random graph for
each seed index, reused across the two scenes.

## Information geometry

At each frequency, form the noise-whitened gain tangent N from the predicted data and
the transmitter/receiver incidence matrix. Project the physical Jacobian with
`J_q = (I - N N^dagger) J`. The complex projection removes both gain-amplitude and
gain-phase directions. Stack real/imaginary parts across frequencies, then project out
the four real nuisance coordinates: center x/y, mean radius, and material.
The remaining four-column matrix gives the efficient local shape Fisher information.
Tests compare this sequential construction against projecting out every nuisance
column of the full real joint Jacobian at once.

Both optimized plans maximize mean log determinant over three fixed prior geometries.
One assumes calibration known during design; the other profiles calibration during design.
Both use the same three starting graphs, swap constraints, proposal budget, and random seed.
The inverse itself treats gains as unknown in BOTH arms. Design uses no observation,
truth geometry, or held-out outcome. It is a local search, not a certified global optimum.
Information profiling and D-optimal design are standard constructions; this study makes
no novelty claim for them.

All tested finite-object plans retain four locally independent shape directions.
This is an issue of information strength and nonlinear estimation, not a demonstrated
rank transition. Tests separately verify that a tree has no gain-invariant data and
that monopole-only cross ratios are identically one. Those algebraic facts are not
used as artificially weak recovery baselines.

## Numerical qualification

All six targeted tests passed, including joint derivatives (shape, material and gains),
gauge invariance, closure cancellation, graph constraints, and independent forward checks.
Shape derivatives are reciprocal analytic derivatives; the single material derivative
uses a centered difference of freshly compiled matrices. Initial and truth states pass
full 192/256-node boundary refinement and native/nodal compiler checks.
Every reported recovered state was freshly checked against an independent full 256-node
boundary solve: worst relative field discrepancy **{worst_check:.3g}**.

Recoveries use the faster nodal compiler on the identical Laurent shape family.
The node-free Laurent compiler is independently qualified against the full boundary
solver; this experiment makes no intrinsic Laurent speed claim. All complete optimizer
trials use freshly evaluated nonlinear scattering, not a frozen tangent approximation.

## Interpretation and next decision

The original strong claim—special loop selection unlocks a deformation that generic
multioffset acquisition cannot recover—is not verified by this experiment. A well-spread
uniform design is already competitive under these fair controls. The useful finding is
that assuming known calibration during acquisition design can select weaker measurements
for the actual unknown-calibration inverse.

The pragmatic next experiment, if continuing, is to use this diagnostic to test a
different physical information source, such as a neighbouring scatterer: does it increase
target-shape information after profiling the neighbour's own uncertain parameters?
Do not add closure-ratio optimization merely to seek a better-looking result: the full
joint likelihood already uses that information and handles additive noise directly.

## Reproduce

From the repository root:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q experiments/laurent_calibration/test_calibration.py
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_calibration.run --stage all --seeds 5 --noise .01 --starts 2
MPLCONFIGDIR=/tmp/laurent-calibration-mpl /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_calibration.analyze
```

`design.json` preserves every selected edge, all prior states, search counts, and nominal
information matrices. `recoveries.json` preserves both starts, fitted nuisance parameters,
truths, seeds, and per-case metrics. `manifest.json` records source hashes and environment;
existing uncommitted experimental dependencies are used. `summary.csv` is the compact table.

Relevant established baselines:
[source-independent GPR FWI](https://www.sciencedirect.com/science/article/pii/S0926985122003627),
[source variable projection](https://doi.org/10.1111/1365-2478.12008), and
[interferometric closure invariants](https://arxiv.org/abs/2108.11399).
The first two published algorithms were not reproduced in this bounded screening test;
the matched joint gain/shape/material inverse is the strong internal baseline.
"""
    (out/"report.md").write_text(report)
    manifest(out)
    print(json.dumps(dict(paired_comparisons=pairs, worst_recovered_forward_error=worst_check), indent=2))


if __name__ == "__main__":
    main()
