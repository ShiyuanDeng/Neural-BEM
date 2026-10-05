"""Read-only ON-001 comparison, inventories, galleries and phase-cost summaries."""
from pathlib import Path
from statistics import median
import numpy as np
from bem_inverse.io import read, write, curve_from, digest
from . import campaign as c, on001 as O, scenes as S


def short_result(folder, case):
    path = folder/"runs"/case/"result.json"
    if not path.exists():
        return dict(status="unrun")
    r = read(path)
    trials = []
    for s in r.get("stages", []):
        trials += read(path.parent/(s["stage"]+".json")).get("trials", [])
    refused = [t for t in trials if t.get("reason") in
               ("self_intersection", "irregular_parameterization", "unresolved_projection")]
    seconds = r.get("audited_output_seconds", r.get("total_seconds"))
    return dict(recovered=r["recovered"], outcome=r["outcome"], detail=r.get("detail"), metrics=r.get("metrics"),
        maximum_residual=r.get("maximum_residual"), audit=r.get("final_audit_passed"),
        audited_output_seconds=seconds, fit_seconds=r.get("fit_and_localization_seconds"),
        audit_seconds=r.get("audit_seconds"), case_seconds=r.get("case_seconds"), units=r.get("total_units"),
        fit_units=(r.get("fit_work") or {}).get("work_units"),
        proposals=len(trials), accepted=sum(t.get("status") == "accepted" for t in trials),
        geometry_refusals=len(refused), geometry_refusal_seconds=sum(t.get("geometry_seconds", 0) for t in refused),
        geometry=r.get("geometry_work"), physics=r.get("physics"), result=str(path.relative_to(c.ROOT)))


def report():
    paired = read(O.OUTPUT/"all_paired.json")
    rows = [dict(id=case, B=short_result(O.OUTPUT/"all_B", case), E=short_result(O.OUTPUT/"all_E", case))
            for case in S.CASES]
    complete = all("recovered" in r[a] for r in rows for a in ("B", "E"))
    historical = {r["id"] for r in read(c.ROOT/"results/validation/cleaned_interfaces/PC-001/M1/summary.json")["rows"] if r["recovered"]}
    actual = {a: {r["id"] for r in rows if r[a].get("recovered")} for a in ("B", "E")}
    regressions = sorted(actual["B"]-actual["E"])
    additions = sorted(actual["E"]-actual["B"])
    baseline_mismatch = sorted(historical-actual["B"])
    ratio = paired["median_speedup"]
    major = complete and not regressions and not baseline_mismatch and ratio >= 2 and paired["p10_speedup"] >= 1
    partial = complete and not regressions and not baseline_mismatch and (bool(additions) or ratio >= 1.25)
    classification = "major speed success" if major else "useful partial result" if partial else "closed negative" if complete else "incomplete"
    repetitions = {}
    for prefix in ("repeat1", "repeat2", "repeat_circle_uncontended"):
        path = O.OUTPUT/(prefix+"_paired.json")
        if path.exists():
            repetitions[prefix] = read(path)
    excluded_timing_samples = [{"prefix": "repeat1", "case": "circle__c4",
        "reason": "Read-only gallery generation overlapped this pair; preserve numerical evidence, exclude timing and replace within confirmation allowance."}]
    repeated_case_stats = {}
    for case in ("circle__c4", "kite__c0.5", "star__c13.3"):
        batches = [paired, *repetitions.values()]
        ratios = [b["paired_speedups"][case] for b in batches if case in b["paired_speedups"]
                  and not (b["prefix"] == "repeat1" and case == "circle__c4")]
        repeated_case_stats[case] = dict(paired_repetitions=len(ratios), speedups=ratios,
            median_speedup=median(ratios), minimum_speedup=min(ratios), maximum_speedup=max(ratios))
    development = {}
    for arm in ("B", "G", "E", "EW"):
        receipts = [read(p) for p in (O.OUTPUT/("screen_"+arm)/"runs").glob("*/result.json")]
        development["screen_"+arm] = dict(cases=len(receipts),
            internal_audited_seconds=sum(r["total_seconds"] for r in receipts),
            case_seconds=sum(r["case_seconds"] for r in receipts))
    for batch in ("qualification_F", "qualification_F_exact"):
        receipts = read(O.OUTPUT/batch/"qualification.json")["rows"]
        development[batch] = dict(states=len(receipts), passed=sum(r["passed"] for r in receipts),
                                 state_seconds=sum(r["seconds"] for r in receipts))
    caps = []
    source_checks = []
    for arm in ("B", "E"):
        for case in S.CASES:
            path = O.OUTPUT/f"all_{arm}"/"runs"/case/"result.json"
            if not path.exists():
                continue
            r = read(path)
            if r.get("fit_and_localization_seconds", 0) > 120 or r.get("audit_seconds", 0) > 30:
                caps.append(dict(case=case, arm=arm, fit_seconds=r.get("fit_and_localization_seconds"),
                                 audit_seconds=r.get("audit_seconds"), outcome=r["outcome"]))
            source_checks.append(read(O.OUTPUT/f"all_{arm}"/"pairs"/(case+".json"))["source_check_passed"])
    phases = {}
    for arm in ("B", "E"):
        values = [r[arm] for r in rows if "recovered" in r[arm]]
        successes = [r for r in values if r["recovered"]]
        def total(key):
            return sum(r.get(key) or 0 for r in values)
        phases[arm] = dict(
            total_audited_output_seconds=total("audited_output_seconds"),
            total_fit_seconds=total("fit_seconds"), total_audit_seconds=total("audit_seconds"),
            median_success_fit_seconds=median(r["fit_seconds"] for r in successes),
            median_success_output_seconds=median(r["audited_output_seconds"] for r in successes),
            maximum_fit_seconds=max(r["fit_seconds"] for r in values),
            maximum_audit_seconds=max(r["audit_seconds"] for r in values),
            maximum_fit_units=max(r.get("fit_units") or 0 for r in values),
            total_work_units=total("units"), proposals=total("proposals"), accepted=total("accepted"),
            geometry_refusals=total("geometry_refusals"),
            geometry_refusal_seconds=total("geometry_refusal_seconds"),
            geometry_seconds={k: sum((r.get("geometry") or {}).get(k, 0) for r in values)
                for k in ("preparation_seconds", "trial_seconds", "certificate_seconds", "projection_seconds")},
            physics_seconds={k: sum((r.get("physics") or {}).get("seconds", {}).get(k, 0) for r in values)
                for k in ("geometry", "assembly", "waves", "factorization", "fields", "jacobian")},
            fallback_counts={k: sum((r.get("geometry") or {}).get(k, 0) for r in values)
                for k in ("prepare_fallbacks", "device_certificate_fallbacks", "sampled_seconds")})
    value = dict(classification=classification, complete=complete, paired=paired, rows=rows,
        phase_totals=phases, phase_accounting="Geometry timers overlap; physics timers sum threaded calls and are not additive wall-time partitions",
        historical_baseline_mismatch=baseline_mismatch, recovery_regressions=regressions, recovery_additions=additions,
        by_contrast={a: {S.tag(k): sum(r["id"].endswith("__"+S.tag(k)) and r[a].get("recovered", False) for r in rows)
                         for k in S.CONTRASTS} for a in ("B", "E")},
        repeats=repetitions, excluded_timing_samples=excluded_timing_samples, repeated_case_stats=repeated_case_stats, development_costs=development, cap_overshoots=caps, all_pair_source_checks_passed=all(source_checks),
        analysis_source_sha256=digest(Path(__file__)), frozen_recipe=read(O.OUTPUT/"frozen_finalist.json"))
    write(O.OUTPUT/"final_comparison.json", value)
    lines = ["# ON-001 confirmed comparison", "", "Classification: **"+classification+"**.", "",
             "| Case | B recovered | E recovered | B/E time | E RMS mm | E Hausdorff upper mm | E max residual | E audit |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        e = r["E"]; m = e.get("metrics") or {}
        speed = paired["paired_speedups"].get(r["id"])
        values = [r["id"], str(r["B"].get("recovered", "unrun")), str(e.get("recovered", "unrun")),
                  "—" if speed is None else format(speed, ".3f"),
                  format(m.get("rms_mm", np.nan), ".5f"), format(m.get("hausdorff_upper_mm", np.nan), ".5f"),
                  format(e.get("maximum_residual") or np.nan, ".6g"), str(e.get("audit", "unrun"))]
        lines.append("| "+" | ".join(values)+" |")
    lines += ["", "Timing distributions contain only common recovered cases; failures remain in the inventory and suite totals."]
    (O.OUTPUT/"final_table.md").write_text("\n".join(lines)+"\n")
    plots(rows, paired)
    return value


def plots(rows, paired):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"B": "#2465a3", "E": "#e88720"}
    fig, axes = plt.subplots(10, 3, figsize=(10, 27))
    for row, ax in zip(rows, axes.ravel()):
        case = row["id"]
        descriptor = c.row(case)
        truth = curve_from(read(c.ROOT/descriptor["truth"])).values(2048)*S.LENGTH*1000
        ax.plot(truth.real, truth.imag, "k--", lw=1.2, label="truth")
        for arm in ("B", "E"):
            r = row[arm]
            if r.get("status") == "unrun":
                continue
            raw = read(c.ROOT/r["result"])
            if "final_curve" not in raw:
                continue
            z = curve_from(raw["final_curve"]).values(2048)*S.LENGTH*1000
            status = "recovered" if r["recovered"] else "failed"
            ax.plot(z.real, z.imag, lw=.9, color=colors[arm], label=arm+": "+status)
        ax.set_title(case, fontsize=8)
        ax.set_aspect("equal")
        ax.legend(fontsize=5)
        ax.set_xlabel("mm relative to scene centre", fontsize=6)
    fig.tight_layout()
    fig.savefig(O.OUTPUT/"confirmation_boundaries.png", dpi=110)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [2, 1]})
    x = np.arange(len(rows))
    for arm, offset in (("B", -.18), ("E", .18)):
        times = [r[arm].get("audited_output_seconds", np.nan) for r in rows]
        axes[0].bar(x+offset, times, .36, color=colors[arm], label=arm)
        for i, r in enumerate(rows):
            if "recovered" in r[arm] and not r[arm]["recovered"]:
                axes[0].plot(i+offset, times[i], "kx", markersize=8)
    axes[0].set_ylabel("Seconds through audited fit output; x marks failure")
    axes[0].legend()
    ratios = [paired["paired_speedups"].get(r["id"], np.nan) for r in rows]
    axes[1].bar(x, ratios, color="#527b4a")
    axes[1].axhline(1., color="black", lw=.8)
    axes[1].axhline(2., color="gray", lw=.8, ls="--")
    axes[1].set_ylabel("B/E on common recoveries")
    axes[0].set_xticks(x, [""]*len(rows))
    axes[1].set_xticks(x, [r["id"] for r in rows], rotation=60, ha="right", fontsize=7)
    fig.tight_layout()
    fig.savefig(O.OUTPUT/"confirmation_timings.png", dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    value = report()
    print(value["classification"], value["paired"]["completed_pairs"], value["paired"]["median_speedup"])
