"""Post-run evaluation and reporting; no optimizer or experiment settings change."""
import csv
from pathlib import Path
import json

import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as st

HERE = Path(__file__).resolve().parent
LABELS = dict(wrong_circle="Circle",circle_to_star="Star",circle_to_c="C",kite="Kite",peanut="Peanut",hook="Hook")


def criterion(rows, candidate, reference):
    ratios, raw, extra_stops, incomplete = {}, {}, [], []
    for case in st.CASES:
        a,b = rows[(case,*candidate)],rows[(case,*reference)]
        ea,eb = a["score"]["symmetric_rms_mm"],b["score"]["symmetric_rms_mm"]
        ratios[case] = max(ea,.01)/max(eb,.01)
        raw[case] = ea/eb
        if a["status"] != "COMPLETED_SCHEDULE" and b["status"] == "COMPLETED_SCHEDULE":
            extra_stops.append(case)
        if a["status"]!="COMPLETED_SCHEDULE" or b["status"]!="COMPLETED_SCHEDULE":
            incomplete.append(dict(case=case,candidate_status=a["status"],reference_status=b["status"],
                candidate_reason=a["reason"],reference_reason=b["reason"]))
    gm = float(np.exp(np.mean(np.log(list(ratios.values())))))
    return dict(candidate=candidate,reference=reference,floored_rms_ratios=ratios,raw_rms_ratios=raw,
                geometric_mean_ratio=gm,worst_ratio=max(ratios.values()),additional_hard_stops=extra_stops,
                incomplete_comparisons=incomplete,
                qualifies_for_fresh_case_test=bool(gm <= .8 and max(ratios.values()) <= 1.5 and not extra_stops))


def validate(rows):
    st.verify(HERE)
    manifest=st.sc.read(HERE/"manifest.json")
    assert st.ad.digest(HERE/"frozen_plan.txt")==manifest["plan_sha256"]
    assert all(st.ad.digest(st.sc.ROOT/p)==h for p,h in manifest["qualification_evidence"].items())
    checked,checks,stage_count=0,[],0
    wall_stops=[]
    for (case,prefix,suffix),result in rows.items():
        folder=HERE/"runs"/prefix/case/suffix
        work=result["work"]
        assert work["work_units"]==sum(work["solves"].values())+sum(work["reciprocal_batches"].values())
        assert work["work_units"]<=work["cap"]
        if result["reason"]=="TRIAL_WALL_LIMIT":
            # Ledger checks between operations, so an in-flight operation
            # can cross the wall deadline before the stop is returned.
            wall_stops.append(dict(case=case,prefix=prefix,suffix=suffix,
                inverse_seconds=result["inverse_seconds"],
                deadline_overrun_seconds=max(0.,result["inverse_seconds"]-st.PATH_SECONDS)))
        else:
            assert result["inverse_seconds"]<=st.PATH_SECONDS
        assert all(np.isfinite(result["score"][m]) for m in ("symmetric_rms_mm","hausdorff_mm"))
        if suffix!="none":
            parent=folder.parent/"none/result.json"
            assert st.ad.digest(parent)==result["parent_result_sha256"]
            first=st.sc.read(folder/"stage_5_history.json")["history"][0]["coefficients"]
            np.testing.assert_array_equal(st.curve_from(first).coefficients,
                st.curve_from(rows[case,prefix,"none"]["final_curve"]).coefficients)
        for path in folder.glob("stage_*_history.json"):
            history=st.sc.read(path)
            losses=np.array([h["loss"] for h in history["history"]])
            assert np.all(np.diff(losses)<0), str(path)
            assert len(history["history"])>=1
            checks.extend(c for c in history["acceptance_checks"] if c["accepted"])
            checked+=len(losses)-1
            stage_count+=1
    replay=[]
    for case in st.CASES:
        old=st.sc.read(st.ad.BASE/"SC-025-band-policies/runs/ladder"/case/"result.json")
        a=st.curve_from(rows[case,"baseline","none"]["final_curve"]).coefficients
        b=st.curve_from(old["final_curve"]).coefficients
        error=float(np.linalg.norm(a-b)/np.linalg.norm(b))
        np.testing.assert_array_equal(a,b)
        assert a.tobytes()==b.tobytes()
        assert old["work"]["work_units"]==rows[case,"baseline","none"]["work"]["work_units"]
        replay.append(dict(case=case,coefficient_relative=error,
            same_work=old["work"]["work_units"]==rows[case,"baseline","none"]["work"]["work_units"]))
    for check in checks:
        discrepancy=np.asarray(check["prediction_discrepancy"])
        assert np.all(discrepancy<=np.array([1e-5]+[1e-7]*(len(discrepancy)-1)))
        assert check["production_gain"]>0 and check["refined_gain"]>0
    assert len(checks)==checked
    return dict(passed=True,endpoints=len(rows),stages=stage_count,accepted_steps=checked,
        accepted_cross_resolution_checks=len(checks),baseline_replays=replay,
        max_accepted_field_discrepancy=max(max(c["prediction_discrepancy"]) for c in checks),
        work_ledger_sums_and_caps=True,wall_limit_stops=wall_stops,parent_hashes_and_identical_starts=True,
        monotonic_loss_within_stages=True,source_input_evidence_hashes=True)


def figures(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(2,3,figsize=(12,7.5),constrained_layout=True)
    for case,ax in zip(st.CASES,axes.flat):
        for prefix,color,label in (("baseline","#3269ad","M=3 first stage"),("protect","#d27716","M=2 first stage")):
            y=[rows[case,prefix,s]["score"]["symmetric_rms_mm"] for s in ("none","repeat","extend")]
            xs=np.arange(3)+(-.08 if prefix=="baseline" else .08)
            ax.plot(xs,y,"o",color=color,label=label,ms=6)
            for x,v in enumerate(y):
                stopped=rows[case,prefix,("none","repeat","extend")[x]]["status"]!="COMPLETED_SCHEDULE"
                if stopped:
                    ax.scatter([xs[x]],[v],marker="x",s=90,c="#ad2525",linewidths=2,zorder=5)
                ax.annotate(f"{v:.3g}"+("*" if stopped else ""),(xs[x],v),xytext=(0,7 if prefix=="baseline" else -13),
                            textcoords="offset points",ha="center",fontsize=8,color=color)
        ax.set_title(LABELS[case]);ax.set_yscale("log");ax.set_ylabel("Symmetric RMS error (mm)")
        ax.margins(x=.16,y=.16)
        ax.set_xticks(range(3),["Four-stage\nendpoint","Extra work\nold data","Extra work\nto 2.5 GHz"])
        ax.grid(axis="y",alpha=.2)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("SC-029: first-band choice and independent continuation branches\nRed × / *: hard stop, last accepted endpoint",fontsize=12)
    fig.savefig(HERE/"rms_comparison.png",dpi=170);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(11,7),constrained_layout=True)
    arms=(("baseline","none","#777777","Original ladder"),("baseline","extend","#3269ad","Ladder + frequencies"),
          ("protect","extend","#d27716","M=2 + frequencies"))
    for case,ax in zip(st.CASES,axes.flat):
        truth=st.curve_from(st.sc.read(st.source_folder(case)/"truth.json")).values(4096)*st.sc.LENGTH*1000
        ax.plot(truth.real,truth.imag,"k",lw=2,label="Truth")
        stops=[]
        for prefix,suffix,color,label in arms:
            z=st.curve_from(rows[case,prefix,suffix]["final_curve"]).values(4096)*st.sc.LENGTH*1000
            ax.plot(z.real,z.imag,color=color,lw=1.1,label=label)
            if rows[case,prefix,suffix]["status"]!="COMPLETED_SCHEDULE":
                stops.append(label+" stopped")
        if stops:
            ax.text(.03,.03,"\n".join(stops),transform=ax.transAxes,fontsize=7,color="#ad2525",
                    bbox=dict(facecolor="white",edgecolor="none",alpha=.85,pad=2))
        ax.set_aspect("equal");ax.set_title(LABELS[case]);ax.set_xlabel("x from scene centre (mm)")
        ax.set_ylabel("y (mm)");ax.grid(alpha=.15)
    axes.flat[0].legend(fontsize=7)
    fig.suptitle("SC-029 endpoint boundaries",fontsize=13)
    fig.savefig(HERE/"boundaries.png",dpi=170);plt.close(fig)


def main():
    paths=list((HERE/"runs").glob("*/*/*/result.json"))
    rows={(d["case"],d["prefix"],d["suffix"]):d for d in (st.sc.read(p) for p in paths)}
    expected={(c,p,s) for c in st.CASES for p in st.PREFIXES for s in ("none",*st.SUFFIXES)}
    if set(rows)!=expected:
        raise RuntimeError(f"Incomplete comparison: missing {sorted(expected-set(rows))}")
    validation=validate(rows)
    st.sc.write(HERE/"validation.json",validation)
    comparisons=dict(
        first_band=criterion(rows,("protect","none"),("baseline","none")),
        frequency_baseline=criterion(rows,("baseline","extend"),("baseline","repeat")),
        frequency_protect=criterion(rows,("protect","extend"),("protect","repeat")),
        combined_vs_original=criterion(rows,("protect","extend"),("baseline","none")))
    st.sc.write(HERE/"comparisons.json",comparisons)
    control=criterion(rows,("baseline","repeat"),("baseline","none"))
    control.pop("qualifies_for_fresh_case_test")
    control["interpretation"]="Descriptive control contrast, not a preregistered adoption gate; bands, work and stage restarts change together."
    control["original_work_units"]=sum(rows[c,"baseline","none"]["work"]["work_units"] for c in st.CASES)
    control["control_work_units"]=sum(rows[c,"baseline","repeat"]["work"]["work_units"] for c in st.CASES)
    st.sc.write(HERE/"control_extension.json",control)
    table=[]
    for (case,prefix,suffix),r in sorted(rows.items()):
        parent=rows[case,prefix,"none"]
        mm=r["mechanism"]
        radii=[x for x in (mm["min_radius_mm"],parent["mechanism"]["min_radius_mm"]) if x is not None]
        table.append(dict(case=case,prefix=prefix,suffix=suffix,status=r["status"],reason=r["reason"],
            rms_mm=r["score"]["symmetric_rms_mm"],hausdorff_mm=r["score"]["hausdorff_mm"],
            hausdorff_upper_mm=r["score"]["hausdorff_upper_mm"],work_units=r["work"]["work_units"],
            inverse_seconds=r["inverse_seconds"],min_radius_mm=min(radii),
            projection_refusals=mm["unresolved_projection_refusals"]+(parent["mechanism"]["unresolved_projection_refusals"] if suffix!="none" else 0),
            last_stage_fmax_ghz=(st.EXTRA_HZ[int(r["stages"][-1]["stage"].split("_")[-1])-5]/1e9 if suffix=="extend" else 1.25),
            residual_125=r["score"]["catalog_relative_residual"][8],
            residual_250=r["score"]["catalog_relative_residual"][-1]))
    with (HERE/"case_results.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    unique_work=sum(r["work"]["work_units"]-(rows[c,p,"none"]["work"]["work_units"] if s!="none" else 0)
                    for (c,p,s),r in rows.items())
    st.sc.write(HERE/"summary.json",dict(endpoints=len(rows),statuses={status:sum(r["status"]==status for r in rows.values())
        for status in sorted({r["status"] for r in rows.values()})},actual_unique_inverse_work_units=unique_work,
        endpoint_evaluation_solves=sum(r["score"]["evaluation_field_solves"] for r in rows.values()),
        comparisons=comparisons,validation=validation))
    figures(rows)
    lines=["| Case | Baseline | M=2 first | Baseline + old data | Baseline + high f | M=2 + old data | M=2 + high f |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    order=(("baseline","none"),("protect","none"),("baseline","repeat"),("baseline","extend"),("protect","repeat"),("protect","extend"))
    for case in st.CASES:
        lines.append("| "+LABELS[case]+" | "+" | ".join(f"{rows[case,p,s]['score']['symmetric_rms_mm']:.6g}"+
            ("*" if rows[case,p,s]["status"]!="COMPLETED_SCHEDULE" else "") for p,s in order)+" |")
    lines.append("\n\\* Hard stop: the retained accepted endpoint, not a completed continuation path.")
    (HERE/"rms_table.md").write_text("\n".join(lines)+"\n")
    for filename,metric in (("hausdorff_table.md","hausdorff_mm"),("work_table.md","work_units")):
        other=lines[:2]
        for case in st.CASES:
            cells=[]
            for p,s in order:
                r=rows[case,p,s]
                value=r["work"][metric] if metric=="work_units" else r["score"][metric]
                cells.append(f"{value:.6g}"+("*" if r["status"]!="COMPLETED_SCHEDULE" else ""))
            other.append("| "+LABELS[case]+" | "+" | ".join(cells)+" |")
        other.append(lines[-1])
        (HERE/filename).write_text("\n".join(other)+"\n")
    print(json.dumps(dict(comparisons=comparisons,unique_inverse_units=unique_work,validation=validation),indent=2))


if __name__ == "__main__":
    main()
