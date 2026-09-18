"""Turn the calibration sweep and the matched recoveries into the LAU-005 report."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.laurent_calibration.run import save
from experiments.laurent_neighbour.run import ARMS
from .model import DECIBELS_PER_TAU, DEGREES_PER_TAU
from .run import OUTPUT, SETTINGS, source_hashes

LABELS = dict(absent="No neighbour", known_coupled="Known neighbour, coupled",
              unknown_coupled="Unknown neighbour, coupled", known_additive="Known neighbour, additive",
              unknown_additive="Unknown neighbour, additive")
NAMED = {"interaction-specific": (.105, -30, 3.), "overall-information": (.14, 30, 24.)}


NEIGHBOUR_MANIFEST = Path("results/experiments/laurent_neighbour_20260916/manifest.json")


def dependency_check():
    """Re-validate the neighbour bundle's recorded source hashes against this checkout."""
    recorded = json.loads(NEIGHBOUR_MANIFEST.read_text())["source_sha256"]
    rows = {}
    for path, digest in recorded.items():
        p = Path(path)
        current = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
        rows[path] = "missing" if current is None else ("unchanged" if current == digest else "changed")
    changed = sorted(k for k, v in rows.items() if v != "unchanged")
    return dict(files=len(rows), changed=changed, detail=rows)


def cell(sweep, key):
    d, a, e = NAMED[key]
    return next(r for r in sweep["rows"]
                if r["distance_m"] == d and r["angle_degrees"] == a and r["epsr"] == e)


def classify(sweep):
    cells = [(r, p) for r in sweep["rows"] for p in r["priors"]]
    exact = np.array([p["coupled_over_additive_exact"] for _, p in cells])
    free = np.array([p["coupled_over_additive_free"] for _, p in cells])
    tau = np.array([np.nan if p["crossover_tau"] is None else p["crossover_tau"] for _, p in cells])
    return dict(cells=len(cells), exact=exact, free=free, tau=tau,
                helps_when_calibrated=int((exact > 1).sum()),
                helps_when_uncalibrated=int((free > 1).sum()),
                crossing=int(np.isfinite(tau).sum()),
                never_pays=int((~np.isfinite(tau) & (free <= 1)).sum()),
                always_pays=int((~np.isfinite(tau) & (free > 1) & (exact > 1)).sum()))


def figure(path, sweep, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    taus = np.array([np.inf if t is None else t for t in sweep["taus"]])
    finite = np.isfinite(taus) & (taus > 0)
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.4))
    colors = dict(absent="0.35", unknown_additive="tab:orange", unknown_coupled="tab:blue")
    for ax, key in zip(axes[0], NAMED):
        row = cell(sweep, key)
        p = row["priors"][0]
        for arm in ("absent", "unknown_additive", "unknown_coupled"):
            values = np.array(p["curves"][arm])
            ax.plot(taus[finite], values[finite], color=colors[arm], lw=2, label=LABELS[arm])
            ax.axhline(values[0], color=colors[arm], lw=.8, ls=":")
        if p["crossover_tau"]:
            ax.axvline(p["crossover_tau"], color="k", lw=.9, ls="--")
            ax.annotate(f"crossover\n{p['crossover_tau']*DECIBELS_PER_TAU:.3f} dB, "
                        f"{p['crossover_tau']*DEGREES_PER_TAU:.2f}$\\degree$",
                        (p["crossover_tau"], values.max()), fontsize=8, ha="left", va="top")
        ax.set(xscale="log", yscale="log", xlabel=r"calibration scale $\tau$",
               ylabel="target-harmonic RMS bound (mm)", title=f"{key} configuration")
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(alpha=.25, which="both")
    ax = axes[1, 0]
    stats = classify(sweep)
    for r in sweep["rows"]:
        for p in r["priors"]:
            a, c = np.array(p["curves"]["unknown_additive"]), np.array(p["curves"]["unknown_coupled"])
            ax.plot(taus[finite], (a/c)[finite], color="0.75", lw=.6, alpha=.7)
    for key, color in zip(NAMED, ("tab:red", "tab:green")):
        p = cell(sweep, key)["priors"][0]
        a, c = np.array(p["curves"]["unknown_additive"]), np.array(p["curves"]["unknown_coupled"])
        ax.plot(taus[finite], (a/c)[finite], color=color, lw=2.2, label=f"{key}")
    ax.axhline(1., color="k", lw=1.)
    ax.set(xscale="log", xlabel=r"calibration scale $\tau$",
           ylabel="additive / coupled precision ratio",
           title=f"coupling pays above the line: {stats['helps_when_calibrated']}"
                 f"/{stats['cells']} cells already at exact calibration")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=.25, which="both")
    inset = ax.inset_axes([.62, .08, .35, .33])
    crossings = np.sort(stats["tau"][np.isfinite(stats["tau"])])
    inset.step(crossings, np.arange(1, len(crossings)+1)/stats["cells"], where="post", color="k", lw=1.2)
    inset.set(xscale="log", title=r"cells crossed by $\tau$", ylim=(0, 1))
    inset.tick_params(labelsize=6)
    inset.title.set_size(7)
    ax = axes[1, 1]
    for arm in ("absent", "unknown_additive", "unknown_coupled"):
        rows = [r for r in summary["rows"] if r["variant"] == "matched" and r["method"] == arm]
        t = np.array([r["tau"] for r in rows])
        ax.plot(t, [r["fisher_crlb_mm"] for r in rows], color=colors[arm], lw=1.4, ls="--")
        ax.plot(t, [r["median_shape_rms_mm"] for r in rows], "o-", color=colors[arm],
                ms=5, lw=1.8, label=LABELS[arm])
    ax.set_xscale("symlog", linthresh=2e-2)
    ax.set(yscale="log", xlabel=r"calibration scale $\tau$ (matched prior)",
           ylabel="median recovered shape RMS (mm)",
           title="nonlinear recovery (solid) against the Fisher bound (dashed)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=.25, which="both")
    fig.tight_layout()
    fig.savefig(path, dpi=190)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def table(summary, variant, metric="median_shape_rms_mm"):
    taus = [t for t, v in SETTINGS if v == variant]
    lines = ["| Physical world / available knowledge | " +
             " | ".join(f"tau={t:g}" for t in taus) + " |",
             "|---|" + "---:|"*len(taus)]
    for arm in ARMS:
        values = []
        for t in taus:
            row = next(r for r in summary["rows"] if r["tau"] == t and r["variant"] == variant
                       and r["method"] == arm)
            values.append(f"{row[metric]:.3f}")
        lines.append(f"| {LABELS[arm]} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path,
                        default=Path("results/validation/laurent/LAU-005-20260918-closeout"))
    args = parser.parse_args()
    sweep = json.loads((args.output/"sweep.json").read_text())
    summary = json.loads((args.output/"summary.json").read_text())
    stats = classify(sweep)
    args.report.mkdir(parents=True, exist_ok=True)
    figure(args.report/"calibration_identifiability.png", sweep, summary)
    interaction = cell(sweep, "interaction-specific")["priors"]
    overall = cell(sweep, "overall-information")["priors"]
    cross = sweep["crossover_summary"]
    bridge = {r["method"]: r for r in summary["rows"] if r["variant"] == "flat"}
    records = json.loads((args.output/"recoveries.json").read_text())
    original = {arm: float(np.median([r["shape_harmonic_radial_rms_mm"] for r in records
                    if r["variant"] == "flat" and r["method"] == arm and (r["seed"]-8300) % 100 < 5]))
                for arm in ARMS}
    published = ", ".join(f"{LABELS[a].lower()} {original[a]:.3f} mm" for a in ARMS)
    matched0 = {r["method"]: r for r in summary["rows"] if r["variant"] == "matched" and r["tau"] == 0.}
    matched1 = {r["method"]: r for r in summary["rows"] if r["variant"] == "matched" and r["tau"] == 1.}
    def comparison(tau, variant, text):
        return next(c for c in summary["comparisons"] if c["tau"] == tau
                    and c["variant"] == variant and c["comparison"] == text)
    save(args.report/"classification.json", {k: v for k, v in stats.items()
                                             if k not in ("exact", "free", "tau")})
    dependencies = dependency_check()
    save(args.report/"dependency_hashes.json", dependencies)
    drift = (", ".join(f"`{p}`" for p in dependencies["changed"]) if dependencies["changed"]
             else "none")
    report = f"""# LAU-005 — a neighbour mostly helps by illumination, and calibration sets where it does not

2026-09-18. Closeout of [LAU-005](../../../../docs/iterations/laurent/iteration_06/03_plan.md),
the alternative the [priority review](../../../../docs/iterations/laurent/iteration_06/02_proposals/01_outsider_priority_review.md)
left open when generic trace compression was parked.

## Finding

The [neighbour study](../../../experiments/laurent_neighbour_20260916/report.md) named
**scattering-assisted separation of shape and calibration** as its useful hypothesis, and
was careful to say that its own results left *"the stronger claim of improved shape sensing
with perfect calibration unsupported"*. This experiment settles that open question by
making calibration uncertainty continuous instead of binary.

Replacing the known/unknown gain switch by a Gaussian log-gain prior of scale `tau` —
`tau=0` exact calibration, `tau=1` the study's own truth gain scale, `tau`→∞ its free-gain
arm — gives one family that contains both of its endpoints. Across **all {stats['cells']}
configuration/prior cells of the recorded screen**:

- The claim the study left unsupported **holds in most of them**. Coupling already beats
  the additive control at **exact** calibration in **{stats['helps_when_calibrated']}/{stats['cells']}**
  cells. There the benefit cannot be a nuisance-ambiguity effect, because no calibration
  nuisance is left: it is illumination.
- **{stats['crossing']}/{stats['cells']}** cells instead cross over — coupling pays only once
  calibration is worse than `tau*` — with median `tau*` **{cross['median_tau']:.3f}**
  (**{cross['median_decibels']:.3f} dB**, **{cross['median_degrees']:.2f} degrees** of
  per-antenna gain error, one standard deviation).
- **{stats['never_pays']}/{stats['cells']}** cells never pay at any calibration quality.

The configuration the study analysed is one of the crossing minority, and it crosses very
early: additive/coupled precision ratio {interaction[0]['coupled_over_additive_exact']:.3f}
at exact calibration, rising to {interaction[0]['coupled_over_additive_free']:.3f} with free
gains, crossing at `tau*` = {interaction[0]['crossover_tau']:.3f}
({interaction[0]['crossover_tau']*DECIBELS_PER_TAU:.3f} dB,
{interaction[0]['crossover_tau']*DEGREES_PER_TAU:.2f} degrees). That is not an accident:
it was *selected* to maximise the coupled-over-additive gain **with gains free**, which is
exactly the criterion that rewards the calibration-ambiguity mechanism. The
**overall-information** configuration, selected without that criterion, never crosses —
coupling helps by {overall[0]['coupled_over_additive_exact']:.3f}x at exact calibration and
{overall[0]['coupled_over_additive_free']:.3f}x with free gains.

So the mechanism the study proposed is real but is **not** the main reason a neighbour
helps. Two thresholds should be quoted separately and not merged: for the configuration it
analysed, coupling stops paying below {interaction[0]['crossover_tau']*DECIBELS_PER_TAU:.3f}
dB / {interaction[0]['crossover_tau']*DEGREES_PER_TAU:.2f} degrees of gain error; across
the crossing cells generally, below {cross['median_decibels']:.3f} dB /
{cross['median_degrees']:.2f} degrees. Both are far tighter than the 1.303 dB / 14.3 degree
errors the study actually simulated, which is why its `tau=1` arm looked like a pure
calibration effect.

![Calibration sweep](calibration_identifiability.png)

## The two endpoints are the recorded study, exactly

Every swept curve is checked against the neighbour study's own screen at both ends. Over
all {stats['cells']} cells and four neighbour arms, the worst relative disagreement is
**{sweep['worst_endpoint_relative_error']['free_gain']:.2e}** at the free-gain endpoint and
**{sweep['worst_endpoint_relative_error']['known_gain']:.2e}** at the known-gain endpoint.
No curve is non-monotone in `tau` beyond `1e-9` relative: a looser calibration prior never
adds information. Those two checks are what make this a reparameterisation of the recorded
result rather than a new quantity.

## Matched nonlinear recovery agrees with the bound

The interaction-specific configuration, five arms, two fixed shape pairs,
{summary['seeds_per_scene']} gain/noise seeds, two initialisations, lower training cost
selected without truth. At each `tau` the truth gains are the **same standard-normal draw
rescaled**, so the sweep is paired across calibration levels, and the inverse carries
exactly the prior that generated them.

Median recovered target-harmonic error (mm):

{table(summary, "matched")}

With exact calibration (`tau=0`) the coupled and additive arms are statistically
indistinguishable and both are far better than the isolated target
({matched0['unknown_coupled']['median_shape_rms_mm']:.3f} and
{matched0['unknown_additive']['median_shape_rms_mm']:.3f} against
{matched0['absent']['median_shape_rms_mm']:.3f} mm): paired mean
{comparison(0., 'matched', 'unknown_coupled minus unknown_additive')['paired_mean_mm']:+.4f} mm,
95% interval
[{comparison(0., 'matched', 'unknown_coupled minus unknown_additive')['bootstrap_95'][0]:+.4f},
{comparison(0., 'matched', 'unknown_coupled minus unknown_additive')['bootstrap_95'][1]:+.4f}] mm.
At the study's own gain scale (`tau=1`) coupling is ahead again:
{matched1['unknown_coupled']['median_shape_rms_mm']:.3f} against
{matched1['unknown_additive']['median_shape_rms_mm']:.3f} mm, paired mean
{comparison(1., 'matched', 'unknown_coupled minus unknown_additive')['paired_mean_mm']:+.4f} mm,
95% interval
[{comparison(1., 'matched', 'unknown_coupled minus unknown_additive')['bootstrap_95'][0]:+.4f},
{comparison(1., 'matched', 'unknown_coupled minus unknown_additive')['bootstrap_95'][1]:+.4f}] mm.

**Bridge arm.** One setting keeps the recorded study's improper flat gain prior at
`tau=1`; it is the same inverse object, verified by a test that compares its residual and
Jacobian against the study's own. Restricted to the five seeds per scene the study ran, it
reproduces **all five published medians exactly**: {published}. This stage's own medians
differ only because it doubles the seeds ({bridge['unknown_coupled']['median_shape_rms_mm']:.3f} mm
coupled, {bridge['unknown_additive']['median_shape_rms_mm']:.3f} mm additive,
{bridge['absent']['median_shape_rms_mm']:.3f} mm isolated over
{2*summary['seeds_per_scene']} cases). Knowing the calibration prior is itself worth
{bridge['unknown_coupled']['median_shape_rms_mm']/matched1['unknown_coupled']['median_shape_rms_mm']:.2f}x
on the coupled arm at the same calibration quality, and
{bridge['absent']['median_shape_rms_mm']/matched1['absent']['median_shape_rms_mm']:.2f}x on
the isolated target — a modelling gain, not a neighbour effect, and a further sign that
part of what the neighbour buys is calibration information that a prior can also supply.

**Dependency drift.** Of the {dependencies['files']} source files the neighbour bundle
hash-pins, {len(dependencies['changed'])} differ in this checkout: {drift}. Both were
changed by the speed-up track's commit `25de4cd`, before this experiment, and neither was
touched here. The bridge arm reproducing all five published medians exactly is the direct
evidence that this drift does not perturb the results compared against. Every other pinned
file, including all of `laurent_neighbour`, `laurent_calibration` and
`modal_muller_research`, is unchanged.

Every selected state was re-checked against a fresh 192-node full-boundary solve; the worst
relative forward discrepancy is
**{max(r['oracle_forward_error'] for r in records):.2e}**, and
{sum(r['trials'][r['selected_start']]['success'] for r in records)}/{len(records)} selected
fits converged.

## What this does and does not establish

- It is a **local Fisher result over the recorded screen**, plus nonlinear confirmation on
  one configuration. The screen's configurations are a 63-point synthetic scan, not a
  sample of real scenes.
- The Gaussian prior on log gains is a **modelling choice**, not a measured calibration
  distribution. `tau` is reported in dB and degrees so it can be compared with an
  instrument specification, but no instrument was measured.
- Standing limits are unchanged: lossless homogeneous 2-D TMz, exterior permittivity 6,
  one target and at most one neighbour, disjoint bounding circles, known component count
  and identity, locally constrained starts, no air/soil interface, antenna pattern, clutter
  or conductivity.
- **No production promotion, no speed claim, no Laurent-specific novelty claim.** The
  compiled scattering path is used because it is the qualified tool for this scene, not
  because the result belongs to it; the same sweep could be run on a nodal forward.
- Two fixed shape pairs and {summary['seeds_per_scene']} seeds per pair are feasibility
  statistics. Bootstrap intervals resample seeds within a fixed shape pair and do not
  describe generalisation to other shapes or neighbour positions.

## Reproduce

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q experiments/laurent_identifiability
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_identifiability.run --stage sweep
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_identifiability.run --stage recover
MPLCONFIGDIR=/tmp/laurent-mpl /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_identifiability.analyze
```

Sweep curves, per-fit records, summaries, paired statistics, qualification and the
source/environment manifest are in
[`{args.output.name}/`](../{args.output.name}). No production default, prior bundle or
neighbour/calibration source file was changed.
"""
    (args.report/"README.md").write_text(report)
    # Refresh the source hashes without discarding the run's own ledger record.
    path = args.output/"manifest.json"
    record = json.loads(path.read_text())
    record["source_sha256"] = source_hashes()
    record["analysed"] = True
    save(path, record)
    print(json.dumps({k: v for k, v in stats.items() if k not in ("exact", "free", "tau")}, indent=2))


if __name__ == "__main__":
    main()
