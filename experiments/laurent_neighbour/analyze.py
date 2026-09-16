"""Report both preselected mechanisms without conflating their gains."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from experiments.laurent_calibration.design import uniform_plan
from experiments.laurent_calibration.run import save, PRIOR_POINTS, TRUTHS
from .model import Body, Evaluator, information
from .run import OUTPUT, ARMS, selected_bodies, NEIGHBOUR_TRUTHS, manifest


LABELS = dict(absent="No neighbour", known_coupled="Known neighbour, coupled",
              unknown_coupled="Unknown neighbour, coupled", known_additive="Known neighbour, additive",
              unknown_additive="Unknown neighbour, additive")


def paired(rows, first, second):
    """Negative difference means the first arm has lower error."""
    a = {(r["scene"], r["seed"]): r["shape_harmonic_radial_rms_mm"] for r in rows if r["method"] == first}
    b = {(r["scene"], r["seed"]): r["shape_harmonic_radial_rms_mm"] for r in rows if r["method"] == second}
    keys = sorted(a.keys() & b.keys())
    delta = np.array([a[k]-b[k] for k in keys])
    rng = np.random.default_rng(65)
    groups = [np.array([i for i,k in enumerate(keys) if k[0] == scene]) for scene in sorted({k[0] for k in keys})]
    draws = np.concatenate([rng.choice(g, size=(10000, len(g)), replace=True) for g in groups], axis=1)
    ci = np.quantile(delta[draws].mean(axis=1), [.025, .975])
    return dict(first=first, second=second, pairs=len(keys), lower_error_count=int(np.sum(delta < 0)),
                mean_error_difference_mm=float(delta.mean()), bootstrap_95pct_mean_difference_mm=ci.tolist())


def selection_record(screen):
    s = screen["selected"]
    return next(r for r in screen["candidates"] if all(r[k] == s[k] for k in ("distance_m", "angle_degrees", "epsr")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    root = args.output
    sets = []
    for path, name in [(root, "Overall-information selection"), (root/"coupling_control", "Interaction-specific selection")]:
        screen = json.loads((path/"screen.json").read_text())
        rows = json.loads((path/"recoveries.json").read_text())
        summary = json.loads((path/"summary.json").read_text())
        comparisons = [paired(rows, "unknown_coupled", "absent"),
                       paired(rows, "unknown_coupled", "unknown_additive"),
                       paired(rows, "unknown_additive", "absent")]
        save(path/"paired_comparisons.json", dict(rows=comparisons,
            caveat="Bootstrap conditions on two fixed target/neighbour shape pairs and resamples gain/noise seeds within each pair."))
        with (path/"summary.csv").open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summary["rows"][0]))
            writer.writeheader()
            writer.writerows(summary["rows"])
        base_known = []
        for p in PRIOR_POINTS:
            e = Evaluator([Body()])
            info = information(e.forward(p), e.jacobian(p), uniform_plan(), np.array(screen["sigma"]), gains_unknown=False)
            base_known.append(info["radial_rms_crlb_mm"])
        selection = selection_record(screen)
        audit = dict(worst_recovered_forward_error=max(r["oracle_forward_error"] for r in rows),
            total_trials=sum(len(r["trials"]) for r in rows),
            converged_trials=sum(t["success"] for r in rows for t in r["trials"]),
            max_two_start_cost_gap=max(abs(r["trials"][0]["cost"]-r["trials"][1]["cost"]) for r in rows),
            isolated_known_gain_crlb_mm=base_known,
            selected_nominal_known_gain_crlb_mm={k: selection["priors"][0]["arms"][k]["known_gain_radial_rms_crlb_mm"] for k in ARMS[1:]})
        save(path/"audit.json", audit)
        sets.append(dict(path=path, name=name, screen=screen, rows=rows, summary=summary,
                         comparisons=comparisons, selection=selection, audit=audit))
    # The repeated absent arm must use exactly the same data/protocol in both runs.
    absent = [{(r["scene"], r["seed"]): r for r in s["rows"] if r["method"] == "absent"} for s in sets]
    assert absent[0].keys() == absent[1].keys()
    assert all(abs(absent[0][k]["shape_harmonic_radial_rms_mm"]-absent[1][k]["shape_harmonic_radial_rms_mm"]) < 1e-8 for k in absent[0])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
    display = ["absent", "unknown_additive", "unknown_coupled", "known_additive", "known_coupled"]
    short = ["Absent", "Unknown\nadditive", "Unknown\ncoupled", "Known\nadditive", "Known\ncoupled"]
    rng = np.random.default_rng(99)
    for i, dataset in enumerate(sets):
        bodies = selected_bodies(dataset["screen"])
        ax = axes[i, 0]
        for bi, body in enumerate(bodies):
            x = TRUTHS[0] if bi == 0 else NEIGHBOUR_TRUTHS[0]
            z = body.chart.boundary(x)
            ax.fill(1000*z.real, 1000*z.imag, color="#287f9e" if bi == 0 else "#ba7837", alpha=.7)
            ax.text(1000*body.chart.anchor.real, 1000*body.chart.anchor.imag, "Target" if bi == 0 else "Neighbour", ha="center", va="center", fontsize=8)
        f = bodies[0].chart
        ax.scatter(1000*f.sources[:, 0], 1000*f.sources[:, 1], marker="v", s=20, color="#333333")
        ax.axhline(0, color="#777777", linewidth=.7)
        ax.set_aspect("equal")
        s = dataset["screen"]["selected"]
        ax.set(title=f"{dataset['name']}\nDistance {s['distance_m']*1000:g} mm; neighbour epsr={s['epsr']:g}", xlabel="x (mm)", ylabel="y (mm)", ylim=(-270, 25))
        ax = axes[i, 1]
        selection = dataset["selection"]
        expected = [dataset["screen"]["baseline_information"][0]["radial_rms_crlb_mm"]]
        expected += [selection["priors"][0]["arms"][k]["radial_rms_crlb_mm"] for k in display[1:]]
        ax.bar(np.arange(5), expected, color=["#777777", "#ba7837", "#287f9e", "#d8b48b", "#9dc7d3"])
        ax.set_xticks(range(5), short, fontsize=8)
        ax.set(title="Prior prediction with unknown antenna gains", ylabel="Local shape RMS lower bound (mm)")
        ax = axes[i, 2]
        for k, name in enumerate(display):
            errors = [r["shape_harmonic_radial_rms_mm"] for r in dataset["rows"] if r["method"] == name]
            ax.scatter(k+rng.uniform(-.12, .12, len(errors)), errors,
                       color="#287f9e" if name == "unknown_coupled" else ("#ba7837" if name == "unknown_additive" else "#777777"), s=24, alpha=.85)
            ax.plot([k-.23, k+.23], [np.median(errors)]*2, color="black", linewidth=2)
        ax.axhline(.5, linestyle="--", color="#777777", linewidth=.8)
        ax.set_xticks(range(5), short, fontsize=8)
        ax.set(title="Nonlinear recovery: 10 paired cases per arm", ylabel="Shape harmonic radial RMS error (mm)")
    fig.suptitle("A neighbouring scatterer: calibration reference or extra illumination?", fontsize=15)
    fig.savefig(root/"findings.png", dpi=180)
    fig.savefig(root/"findings.svg")
    plt.close(fig)

    tables, paragraphs = [], []
    for dataset in sets:
        table = [f"### {dataset['name']}", "", "| Physical world / available knowledge | Median shape error (mm) | Ensemble RMS error (mm) | Below 0.5 mm |", "|---|---:|---:|---:|"]
        for name in display:
            r = next(r for r in dataset["summary"]["rows"] if r["method"] == name)
            table.append(f"| {LABELS[name]} | {r['median_shape_rms_mm']:.3f} | {r['ensemble_shape_rms_mm']:.3f} | {r['recovered']}/{r['cases']} |")
        tables.append("\n".join(table))
        lines = [f"**{dataset['name']}:**"]
        for r in dataset["comparisons"]:
            lo, hi = r["bootstrap_95pct_mean_difference_mm"]
            lines.append(f"- {LABELS[r['first']]} minus {LABELS[r['second']]}: paired mean "
                         f"{r['mean_error_difference_mm']:+.3f} mm, conditional 95% bootstrap interval "
                         f"[{lo:+.3f}, {hi:+.3f}] mm; lower error in {r['lower_error_count']}/{r['pairs']} cases.")
        paragraphs.append("\n\n".join([lines[0], "\n".join(lines[1:])]))
    primary, secondary = sets
    all_rows = primary["rows"]+secondary["rows"]
    max_error = max(r["oracle_forward_error"] for r in all_rows)
    medians = {s["name"]: {r["method"]: r["median_shape_rms_mm"] for r in s["summary"]["rows"]} for s in sets}
    m = medians[secondary["name"]]
    interaction_comparison = secondary["comparisons"][1]
    known_gain = secondary["audit"]["selected_nominal_known_gain_crlb_mm"]
    trials = sum(s["audit"]["total_trials"] for s in sets)
    converged = sum(s["audit"]["converged_trials"] for s in sets)
    report = f"""# Neighbour-assisted Laurent shape recovery: two mechanisms

2026-09-16. Follow-up to the negative calibration-loop acquisition test.

## Finding

The controlled feasibility test is positive. With neighbour geometry/material and antenna
gains all estimated, the interaction-specific configuration reduces median target-harmonic
error from **{m['absent']:.3f} mm without a neighbour**, to **{m['unknown_additive']:.3f} mm with additive
echoes**, to **{m['unknown_coupled']:.3f} mm with full multiple scattering**. Full interactions improve
on additive echoes in {interaction_comparison['lower_error_count']}/{interaction_comparison['pairs']} paired cases.

The useful research hypothesis is **scattering-assisted separation of shape and calibration**.
The known-gain local control below does not predict an interaction benefit for this
configuration. Thus these results support an effect on joint identifiability, while leaving
the stronger claim of improved shape sensing with perfect calibration unsupported.
This is evidence from two selected synthetic configurations, not field GPR validation.

## What the experiment separates

A neighbour can help in two different ways: its directly observed echo can constrain
unknown transmitter/receiver gains, and its interaction with the target can change
illumination. Both are tested with a fully unknown neighbour as well as a known-neighbour
upper reference. The additive control retains both direct echoes but switches off
inter-object scattering. It has its own correctly matched synthetic observations and
inverse; it does not fit coupled data with an inaccurate additive model.

The primary prior-selected configuration predicts a large overall gain, but nearly all
of it is also present in the additive world. The second, separately prior-selected
configuration predicts an interaction-specific improvement and only about 6% more total
received field RMS than the isolated target. These two candidates were selected before
any nonlinear recovery outcomes were available.

## Measured nonlinear results

Each configuration has two fixed noncircular target/neighbour pairs, five independent
gain/noise seeds, five arms, and two initializations per fit. The same absolute noise,
antenna gains, source power, frequencies, and measurement mask are used across all arms.
The noise level is 1% relative to the nominal isolated target; it is NOT rescaled upward
when the neighbour makes the scene brighter.

{chr(10).join(tables)}

The error is angular RMS in target radial harmonics 2 and 3, excluding center and mean
radius. Center, radius, material, full corresponding-boundary, and held-out trace errors
are retained in the raw records. The 0.5 mm threshold is an experiment-specific tolerance.
Known-neighbour arms know its complete truth geometry/material. All other arms estimate
all eight physical coordinates of every included object, plus unknown gains. All fits
use the same nonlinear least-squares implementation and choose the lower training loss
of two starts, without using truth in selection.

![The two selected geometries, prior predictions, and every recovery](findings.png)

## Paired comparisons

{chr(10).join(paragraphs)}

Bootstrap intervals resample gain/noise seeds within each of the two fixed shape pairs.
They do not describe generalization to arbitrary shapes, materials, or neighbour locations.
The absent arm is identical across the two configuration studies; those repeated controls
are not additional independent evidence.

## Prior-only selection and physical controls

The scan has 63 locations/material combinations: center separation 105 or 140 mm,
angles on a 30-degree grid (excluding positions too close to the acquisition line),
and neighbour relative permittivity 3, 12, or 24. The target reference radius is 30 mm,
and the neighbour's is 20 mm. Three fixed target/neighbour prior pairs are used.
The selected configuration does not use recovery truth or observed noise.

- Overall-information selection: separation 140 mm, angle +30 degrees, neighbour
  permittivity 24. Worst-prior target RMS precision gain over absence is
  {primary['screen']['selected']['robust_score']:.2f}x after profiling all neighbour and calibration uncertainty.
  Nominal coupled/additive bounds are
  {primary['selection']['priors'][0]['arms']['unknown_coupled']['radial_rms_crlb_mm']:.3f}/
  {primary['selection']['priors'][0]['arms']['unknown_additive']['radial_rms_crlb_mm']:.3f} mm.
  Total field RMS is about {primary['selection']['priors'][0]['coupled_to_isolated_signal_rms_ratio']:.2f}x the isolated target's.
- Interaction-specific selection: separation 105 mm, angle -30 degrees, neighbour
  permittivity 3. It maximizes the worst-prior improvement over the additive control,
  among candidates that also improve over absence. The predicted worst-prior
  coupled-versus-additive precision factor is
  {secondary['screen']['selected']['interaction_precision_gain']:.2f}x. Nominal coupled/additive bounds are
  {secondary['selection']['priors'][0]['arms']['unknown_coupled']['radial_rms_crlb_mm']:.3f}/
  {secondary['selection']['priors'][0]['arms']['unknown_additive']['radial_rms_crlb_mm']:.3f} mm.

The second criterion was introduced after inspecting the first **prior-only** scan,
to distinguish mechanisms, and before either configuration's nonlinear recoveries.
The sweep is a selected-case feasibility study, not an unbiased performance benchmark.
Every candidate and prior result is retained in `screen.json`.

All arms use the previous study's competitive uniform multioffset plan: 48 measurements
per frequency, 12 transmitters and 12 receivers, four measurements per endpoint. The
frequencies are 0.5 and 1.25 GHz. There are no extra antennas or measurements for neighbour
cases. Unknown physical coordinates per object are x/y position, mean radius, four shape
harmonics, and uniform real permittivity. Antenna gains have independent complex log
coordinates at each frequency with one transmitter reference fixing parameter redundancy.

## Information-geometry interpretation

Shape information is computed by noise-whitening and projecting out complex gain tangents,
then the real target position/radius/material tangents and, when unknown, all neighbour
tangents. This is the efficient Fisher information, not raw Jacobian norm. The nonlinear
inverse simultaneously fits exactly those nuisance coordinates.

There is a useful mathematical check on the mechanism: with gains known and fixed
additive noise, a known additive neighbour does not change the target Jacobian or its
information at all. An unknown additive neighbour only adds nuisance directions, so
cannot increase that information. A numerical test checks both statements. Improvement
from additive echoes with unknown gains is therefore a calibration-ambiguity effect,
not extra illumination. `audit.json` also reports known-gain Fisher controls.

Multiple-scattering enhancement itself is established physics. This test explores its
survival under simultaneous shape/material/calibration uncertainty; it makes no novelty
claim for the underlying T-matrix method or Fisher-information projection. Relevant
foundations include scattering-matrix Fisher information in
[Maximum information states for coherent scattering measurements](https://www.nature.com/articles/s41567-020-01137-4)
and the experimentally studied transport of information in complex microwave environments in
[Continuity equation for the flow of Fisher information in wave scattering](https://www.nature.com/articles/s41567-024-02519-8).
Neither paper establishes the particular uncertain-neighbour shape-recovery claim tested here.

For the interaction-specific configuration, the nominal shape RMS lower bounds are:

| Antenna calibration | No neighbour | Unknown additive neighbour | Unknown coupled neighbour |
|---|---:|---:|---:|
| Unknown gains | {secondary['screen']['baseline_information'][0]['radial_rms_crlb_mm']:.4f} mm | {secondary['selection']['priors'][0]['arms']['unknown_additive']['radial_rms_crlb_mm']:.4f} mm | {secondary['selection']['priors'][0]['arms']['unknown_coupled']['radial_rms_crlb_mm']:.4f} mm |
| Known gains | {secondary['audit']['isolated_known_gain_crlb_mm'][0]:.4f} mm | {known_gain['unknown_additive']:.4f} mm | {known_gain['unknown_coupled']:.4f} mm |

With known gains, the coupled unknown neighbour is slightly worse than the additive one
and the isolated target. This is a local Fisher prediction, not an additional nonlinear
recovery study. Our interpretation is that interactions change which shape perturbations
can be mimicked by nuisance parameters. A targeted next check is to vary calibration
uncertainty continuously, before introducing a layered conductive GPR background.

## Validation and limits

Six new mathematical/numerical tests passed: mixed-material full-boundary/native agreement,
all 16 coupled derivatives, additive equivalence, monotonicity under nuisance uncertainty,
joint gain derivatives, and the known-gain additive-information inequality. Selected
initial/truth scenes pass boundary-node refinement and both native/nodal compiler checks.
Each selected recovered state was freshly checked against a full 192-node-per-object
boundary solve. Worst relative forward discrepancy across both studies: **{max_error:.3g}**.
All {converged}/{trials} optimization trials converged; the largest difference in final
training cost between the two starts was
{max(s['audit']['max_two_start_cost_gap'] for s in sets):.3g}. This checks local repeatability,
not global uniqueness. One isolated-target selected fit reached a physical parameter bound;
no neighbour-arm fit or gain coordinate reached a bound.

The independent reference reuses exterior-only cross blocks from the existing full BIE
and replaces each diagonal self block with its own interior-material Muller block. It
uses no cylindrical translation or source/receiver truncation. Inverses use the faster
nodal compiler on the same Laurent chart; native compilation is separately qualified.
No intrinsic Laurent speed advantage is claimed. Runtime numbers are diagnostic only;
the two configuration studies ran concurrently with one BLAS thread each.

The model is one target plus an optional neighbour in a 2-D homogeneous, lossless medium
with relative permittivity 6. It has surface-style acquisition but no air/soil boundary,
real antenna pattern, clutter, conductivity, unknown object count, or field validation.
Initial positions are locally constrained, component identity is known, and all bounding
circles remain disjoint. The neighbour is selected as a synthetic physical scenario;
this is not a claim that surveyors can place or move arbitrary buried objects.

## Reproduce

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q experiments/laurent_neighbour/test_neighbour.py
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_neighbour.run --stage screen
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_neighbour.run_coupling_control --select-only
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_neighbour.run --stage recover
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_neighbour.run --output results/experiments/laurent_neighbour_20260916/coupling_control --stage recover
MPLCONFIGDIR=/tmp/laurent-neighbour-mpl /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_neighbour.analyze
```

Raw selection, qualification, two-start inverse records, summaries, paired statistics,
and source/environment manifests are saved beside this report and in `coupling_control/`.
No production defaults or prior experiment outputs were changed.
"""
    (root/"report.md").write_text(report)
    for dataset in sets:
        manifest(dataset["path"])
    print(json.dumps([{k:s[k] for k in ("name", "comparisons", "audit")} for s in sets], indent=2))


if __name__ == "__main__":
    main()
