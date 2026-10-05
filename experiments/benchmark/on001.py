"""ON-001 bounded TG-002 campaign, scoring only after fit and audit return."""
import argparse
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tarfile
from time import perf_counter
import traceback

import numpy as np
from bem_inverse.io import read, write, digest, curve_from, portable
from bem_inverse.physics import Execution
from bem_inverse.policy import CumulativePolicy
from bem_inverse.runner import fit
from . import campaign as c, scenes as S
from experiments.cleaned_interface import benchmark as ci

OUTPUT = c.ROOT/"results/validation/cleaned_interfaces/ON-001"
SCREEN = ("aphex_twin__c0.5", "aphex_twin__c4", "aphex_twin__c13.3", "hook__c13.3",
          "circle__c4", "c_shape__c13.3", "kite__c0.5", "star__c13.3")
ARMS = {"B": {}, "G": dict(reach_fraction=.8), "G04": dict(reach_fraction=.4),
        "E": dict(required_accuracy=.003), "E001": dict(required_accuracy=.001),
        "GE": dict(reach_fraction=.8, required_accuracy=.003),
        "EW": dict(required_accuracy=.003, working_anchors=5),
        "EW9": dict(required_accuracy=.003, working_anchors=9),
        "EF": dict(required_accuracy=.003, geometry_update="gaussian_lipschitz")}
EXECUTION = Execution(device="cuda", frequency_threads=4)
COORD = Path("/tmp/neural-sdf-bem-ad-coordination")


def source_paths():
    return sorted([*c.ROOT.glob("solvers/**/*.py"), *(c.ROOT/"experiments/benchmark"/name for name in
                       ("__init__.py", "campaign.py", "scenes.py", "on001.py")),
                   c.ROOT/"experiments/cleaned_interface/benchmark.py"])


def source_hashes():
    return {str(p.relative_to(c.ROOT)): digest(p) for p in source_paths()}


def run_case(arm, case, folder):
    if folder.exists():
        raise FileExistsError(f"Preserve completed/failed run: {folder}")
    folder.mkdir(parents=True)
    started = perf_counter()
    options = dict(ARMS[arm])
    geometry = options.pop("geometry_update", "certified_spectral")
    policy = CumulativePolicy(fit_seconds=120., audit_seconds=30., audit_aggregate_seconds=30.,
                              log_model=True, **options)
    row = c.row(case)
    try:
        result = fit(ci.fitting_problem(row, c.INPUTS), solver="modal_muller", execution=EXECUTION,
                     physics=c._physics("modal_muller", EXECUTION), policy=policy, output=folder,
                     geometry_update=geometry, localization_adapter=c.keep_start,
                     on_event=lambda e: print(case, e["operation"]["label"], e["reason"], flush=True))
        returned = perf_counter()
        metrics = ci.score(row, curve_from(result["final_curve"]))
        limits = ci.residual_limits(row)
        residual = result.get("relative_residual")
        result.update(case=row, metrics=metrics, residual_limits=limits,
            recovered=bool(result["final_audit_passed"] and metrics["rms_mm"] <= 1. and
                metrics["hausdorff_upper_mm"] <= 2. and residual is not None and np.all(residual <= limits)),
            maximum_residual=None if residual is None else float(max(residual)),
            scoring_seconds=perf_counter()-returned)
    except Exception:
        result = dict(case=row, outcome="WORKER_EXCEPTION", recovered=False, traceback=traceback.format_exc())
    result.update(arm=arm, on001_settings=asdict(policy), case_seconds=perf_counter()-started)
    write(folder/"result.json", result)
    print("RESULT", case, result["outcome"], result["recovered"], result.get("metrics"), flush=True)
    return result


def run(arm, cases, batch):
    COORD.mkdir(exist_ok=True)
    requested = perf_counter()
    with (COORD/"compute.lock").open("a") as compute, (COORD/"source.lock").open("a") as source:
        fcntl.flock(compute, fcntl.LOCK_EX)
        fcntl.flock(source, fcntl.LOCK_SH)
        wait = perf_counter()-requested
        c.verify(require_inputs=True)
        folder = OUTPUT/batch
        folder.mkdir(parents=True, exist_ok=False)
        hashes = source_hashes()
        with tarfile.open(folder/"sources.tar.gz", "w:gz") as archive:
            for p in source_paths():
                archive.add(p, arcname=str(p.relative_to(c.ROOT)), recursive=False)
        write(folder/"manifest.json", dict(experiment="ON-001", arm=arm, cases=cases, settings=ARMS[arm],
            execution=asdict(EXECUTION), workers=1, blas_threads=1, source_hashes=hashes,
            archive_sha256=digest(folder/"sources.tar.gz"), inputs_sha256=digest(c.INPUTS/"manifest.json"),
            compute_wait_seconds=wait, imported_source_root=str(c.ROOT/"solvers"),
            commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            status=subprocess.check_output(["git", "status", "--short"], text=True), environment=ci.environment(),
            warmup="no excluded warmup; initial audit and CUDA startup included in output boundary"))
        for case in cases:
            # Fresh interpreter per case, common import/startup convention.
            subprocess.run([os.sys.executable, "-m", "experiments.benchmark.on001", "case",
                            "--arm", arm, "--batch", batch, "--cases", case], check=True)
            c.summarize(folder)
        write(folder/"source_check.json", dict(passed=source_hashes() == hashes))
        if source_hashes() != hashes:
            raise RuntimeError("Sources changed during measured batch")
        report()
    return c.summarize(folder)


def report():
    batches = {}
    for manifest in sorted(OUTPUT.glob("*/manifest.json")):
        name = manifest.parent.name
        batches[name] = dict(arm=read(manifest)["arm"], rows={})
        for p in sorted((manifest.parent/"runs").glob("*/result.json")):
            r = read(p)
            trials = [t for s in r.get("stages", []) for t in read(p.parent/(s["stage"]+".json")).get("trials", [])]
            geometry_refused = [t for t in trials if t.get("reason") in
                ("self_intersection", "irregular_parameterization", "unresolved_projection")]
            batches[name]["rows"][r["case"]["id"]] = dict(recovered=r["recovered"],
                outcome=r["outcome"], audit=r.get("final_audit_passed"),
                fit_seconds=r.get("fit_and_localization_seconds"), seconds=r.get("total_seconds"),
                case_seconds=r.get("case_seconds"), maximum_residual=r.get("maximum_residual"),
                metrics=r.get("metrics"), geometry=r.get("geometry_work"),
                proposals=len(trials), geometry_refusals=len(geometry_refused),
                geometry_refusal_seconds=sum(t.get("geometry_seconds", 0) for t in geometry_refused),
                alpha_below_point1=sum(t.get("reach_alpha", 1) < .1 for t in trials),
                clipped_proposals=sum(t.get("reach_alpha", 1) < 1 for t in trials),
                reach_seconds=sum(t.get("reach_seconds", 0) for t in trials),
                result=str(p.relative_to(c.ROOT)))
    inventory = [dict(id=case, **{b: v["rows"].get(case, {"status": "unrun"}) for b, v in batches.items()})
                 for case in S.CASES]
    comparisons = {}
    baseline = batches.get("screen_B", {}).get("rows", {})
    for name, batch in batches.items():
        if name == "screen_B":
            continue
        rows = batch["rows"]
        common = [k for k in baseline if baseline[k]["recovered"] and rows.get(k, {}).get("recovered")]
        speeds = [baseline[k]["seconds"]/rows[k]["seconds"] for k in common]
        comparisons[name] = dict(common_successes=common,
            recovery_regressions=[k for k in baseline if baseline[k]["recovered"] and not rows.get(k, {}).get("recovered")],
            new_recoveries=[k for k in rows if rows[k]["recovered"] and not baseline.get(k, {}).get("recovered")],
            paired_speedups=dict(zip(common, speeds)),
            median_speedup=float(np.median(speeds)) if speeds else None,
            p10_speedup=float(np.percentile(speeds, 10)) if speeds else None)
    parents = {}
    for name, batch in batches.items():
        if batch['arm'] not in ('EW', 'EW9') or 'screen_E' not in batches:
            continue
        parent = batches['screen_E']['rows']
        rows = batch['rows']
        common = [k for k in parent if parent[k]['recovered'] and rows.get(k, {}).get('recovered')]
        ratios = [parent[k]['seconds']/rows[k]['seconds'] for k in common]
        parents[name] = dict(parent='screen_E', common_successes=common,
            regressions=[k for k in parent if parent[k]['recovered'] and not rows.get(k, {}).get('recovered')],
            paired_speedups=dict(zip(common, ratios)),
            median_speedup=float(np.median(ratios)) if ratios else None)
    value = dict(batches=batches, inventory=inventory, comparisons=comparisons, parent_comparisons=parents)
    write(OUTPUT/"report.json", value)
    lines = ["# ON-001 live evidence", "", "All times include the unchanged endpoint audit. Unrun cases remain unrun.", "",
             "| Case | "+" | ".join(batches)+" |", "|---|"+"---|"*len(batches)]
    for row in inventory:
        cells = []
        for batch in batches:
            r = row[batch]
            recovered, seconds, outcome = r.get("recovered"), r.get("seconds") or 0, r.get("outcome")
            cells.append("unrun" if r.get("status") == "unrun" else
                         f"{recovered} / {seconds:.2f}s / {outcome}")
        lines.append("| "+row["id"]+" | "+" | ".join(cells)+" |")
    (OUTPUT/"table.md").write_text("\n".join(lines)+"\n")
    if batches:
        plots(batches)
    return comparisons


def plots(batches):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(10, 3, figsize=(10, 28))
    for case, ax in zip(S.CASES, axes.ravel()):
        row = c.row(case)
        truth = curve_from(read(c.ROOT/row["truth"])).values(2048)*S.LENGTH
        ax.plot(truth.real*1000, truth.imag*1000, "k--", lw=1., label="truth")
        for name, batch in batches.items():
            if case not in batch["rows"]:
                continue
            result = read(c.ROOT/batch["rows"][case]["result"])
            if "final_curve" not in result:
                continue
            z = curve_from(result["final_curve"]).values(2048)*S.LENGTH
            ax.plot(z.real*1000, z.imag*1000, lw=.8, label=name)
        executed = any(case in b["rows"] for b in batches.values())
        ax.set_title(case+("" if executed else " — unrun"), fontsize=8)
        ax.set_aspect("equal")
        ax.legend(fontsize=5)
    fig.tight_layout()
    fig.savefig(OUTPUT/"boundaries.png", dpi=100)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, batch in batches.items():
        times = [batch["rows"].get(k, {}).get("seconds", np.nan) for k in SCREEN]
        ax.plot(range(len(SCREEN)), times, "o-", label=name)
    ax.set_xticks(range(len(SCREEN)), SCREEN, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Seconds to independently audited output (failures included)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT/"timings.png", dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "case", "report"))
    parser.add_argument("--arm", choices=tuple(ARMS), default="B")
    parser.add_argument("--batch", default="screen_B")
    parser.add_argument("--cases", default="screen")
    args = parser.parse_args()
    cases = list(SCREEN) if args.cases == "screen" else list(S.CASES) if args.cases == "all" else args.cases.split(",")
    if not all(k in S.CASES for k in cases):
        parser.error("TG-002 cases only")
    if args.command == "run":
        value = run(args.arm, cases, args.batch)
    elif args.command == "case":
        if len(cases) != 1:
            parser.error("one case per fresh interpreter")
        value = run_case(args.arm, cases[0], OUTPUT/args.batch/"runs"/cases[0])
    else:
        value = report()
    print(json.dumps(portable(value if args.command != "case" else {"outcome": value["outcome"]}), indent=2))


if __name__ == "__main__":
    main()
