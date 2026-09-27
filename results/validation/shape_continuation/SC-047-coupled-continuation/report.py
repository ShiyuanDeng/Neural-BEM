"""Rebuild SC-047 decisions and scientific figures from saved records only."""
import json
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from qualify import HERE, LENGTH, load_scene, scene, write
from strategies import score


def read(path):
    return json.loads(path.read_text())


def curves(ax, current, **kwargs):
    for i, curve in enumerate(current.components):
        z = curve.values(2048) * LENGTH * 1000
        ax.plot(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]],
                **({k: v for k, v in kwargs.items() if k != "label"} if i else kwargs))


def main():
    started = time.perf_counter()
    qualification = read(HERE / "qualification.json")
    summary = dict(qualification=qualification["status"],
        max_reference_error=max(r.get("fine_vs_oracle", 0) for r in qualification["reference"]),
        max_refinement_error=max(r.get("fine_refinement", 0) for r in qualification["reference"]),
        max_derivative_error=max(max(r["errors"]) for r in qualification["derivatives"] if r["nodes"] == 256),
        strategies=[], all_strategy_gates_pass=False)
    records = [read(p) for p in sorted((HERE / "runs").glob("*/*/result.json"))]
    cases = sorted(set(r["case"] for r in records))
    colors = dict(joint="#0072B2", round_robin="#D55E00", conditional="#009E73")
    if records:
        fig, axes = plt.subplots(len(cases), 3, figsize=(13, 3 * len(cases)), squeeze=False,
                                  layout="constrained")
        for i, case in enumerate(cases):
            arms = {r["arm"]: r for r in records if r["case"] == case}
            if len(arms) != 3:
                continue
            sep = float(case[3:7])
            truth = scene(sep)
            common = min(r["work"]["work_units"] for r in arms.values())
            candidate = arms["conditional"]
            gate = all(candidate["score"]["worst_rms_mm"] <= .9 * arms[a]["score"]["worst_rms_mm"]
                       and candidate["work"]["work_units"] <= arms[a]["work"]["work_units"]
                       for a in ("joint", "round_robin"))
            gate = gate and all(candidate["score"]["objects"][j]["rms_mm"] <= 1.05 * min(
                arms[a]["score"]["objects"][j]["rms_mm"] for a in ("joint", "round_robin")) for j in (0, 1))
            gate = gate and all(r["audit"]["passed"] for r in arms.values())
            comparison = dict(case=case, superiority_gate=gate, common_work_ceiling=common, arms={})
            for j, name in enumerate(("joint", "round_robin", "conditional")):
                r = arms[name]
                eligible = [s for s in r["accepted"] if s["units"] <= common]
                common_state = load_scene(eligible[-1]["state"]) if eligible else scene(sep, initial=True)
                common_score = score(common_state, truth)
                comparison["arms"][name] = dict(score=r["score"], initial_score=r["initial_score"],
                    audit=r["audit"], outcome=r["outcome"], units=r["work"]["work_units"],
                    seconds=r["work"]["seconds"], common_work_score=common_score,
                    common_work_used=eligible[-1]["units"] if eligible else 0)
                ax = axes[i, j]
                curves(ax, scene(sep, initial=True), color="0.75", linewidth=1, label="start")
                curves(ax, truth, color="black", linestyle="--", linewidth=1.3, label="truth")
                curves(ax, load_scene(r["final_state"]), color=colors[name], linewidth=1.1, label=name)
                ax.set_aspect("equal")
                ax.set_title(f"{case} · {name}\nworst RMS {r['score']['worst_rms_mm']:.3f} mm · {r['work']['work_units']} units", fontsize=10)
                ax.set_xlabel("x from scene centre (mm)")
                if j == 0:
                    ax.set_ylabel("y (mm)")
                if i == 0 and j == 0:
                    ax.legend(fontsize=8)
                ax.grid(alpha=.15)
            summary["strategies"].append(comparison)
        summary["all_strategy_gates_pass"] = len(summary["strategies"]) == 4 and all(
            r["superiority_gate"] for r in summary["strategies"])
        fig.savefig(HERE / "reconstructions.png", dpi=160)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
        positions = np.arange(len(summary["strategies"]))
        for j, name in enumerate(("joint", "round_robin", "conditional")):
            values = [row["arms"][name] for row in summary["strategies"]]
            axes[0].bar(positions + (j - 1) * .23, [v["score"]["worst_rms_mm"] for v in values],
                        width=.23, color=colors[name], label=name)
            axes[1].bar(positions + (j - 1) * .23, [v["units"] for v in values],
                        width=.23, color=colors[name], label=name)
        for ax in axes:
            ax.set_xticks(positions, [row["case"].replace("_", "\n") for row in summary["strategies"]])
            ax.grid(axis="y", alpha=.2)
        axes[0].set(ylabel="Worst-object RMS error (mm)", title="Endpoint geometry (initial error 3.81 mm)")
        axes[1].set(ylabel="Charged work units", title="Forward + reciprocal + validation work")
        axes[0].legend(fontsize=8)
        fig.savefig(HERE / "accuracy_and_work.png", dpi=160)
        plt.close(fig)
    if (HERE / "atlas.json").exists():
        atlas = read(HERE / "atlas.json")
        fig, axes = plt.subplots(2, 2, figsize=(10, 7), layout="constrained")
        for ax, row in zip(axes.flat, atlas["rows"]):
            for label, key, color in (("Target alone", "target_alone_singular_values", "0.4"),
                ("Known neighbour", "known_neighbour_singular_values", "#0072B2"),
                ("Unknown neighbour", "unknown_neighbour_singular_values", "#D55E00")):
                s = row[key]
                ax.semilogy(np.arange(1, len(s) + 1), s, "o-", label=label, color=color, markersize=3)
            ax.set_title(f"Separation {row['separation_m'] * 100:.0f} cm · M={row['modes']}\nconditional information retained {row['conditional_fractions'][1]:.1%}")
            ax.set(xlabel="Singular-value index", ylabel="Sensitivity per metre RMS")
            ax.grid(alpha=.2)
        axes[0, 0].legend(fontsize=8)
        fig.savefig(HERE / "conditional_information.png", dpi=160)
        plt.close(fig)
        summary["atlas"] = atlas
    if (HERE / "topology.json").exists():
        top = read(HERE / "topology.json")
        summary["topology"] = dict(status=top["status"], work=top["work"], seconds=top["seconds"],
            insertion_qualification=top["insertion_qualification"],
            decision=top.get("decision"), error=top.get("error"), cases={})
        if top["cases"]:
            fig, axes = plt.subplots(len(top["cases"]), 2, figsize=(11, 3.4 * len(top["cases"])),
                                      squeeze=False, layout="constrained")
            for i, (name, row) in enumerate(top["cases"].items()):
                limit = max(np.max(np.abs(row[phase]["derivative_per_package_area"])) for phase in ("before", "after"))
                summary["topology"]["cases"][name] = {}
                for j, phase in enumerate(("before", "after")):
                    r, ax = row[phase], axes[i, j]
                    points = np.array(r["points"]) * LENGTH * 1000
                    artist = ax.scatter(points[:, 0], points[:, 1], c=r["derivative_per_package_area"],
                        cmap="coolwarm", vmin=-limit, vmax=limit, s=18, marker="s")
                    curves(ax, scene(.14), color="0.4", linewidth=1, linestyle="--", label="truth")
                    curves(ax, load_scene(r["state"]), color="black", linewidth=1, label="current")
                    selected = np.array(r["selected_point"]) * LENGTH * 1000
                    ax.scatter(*selected, marker="x", color="black", s=55)
                    ax.set_aspect("equal")
                    ax.set_title(f"{name} · {phase}\nfinite 3 mm birth Δloss={-r['finite_birth_refined_decrease']:.2e}", fontsize=10)
                    ax.set(xlabel="x (mm)", ylabel="y (mm)")
                    if i == 0 and j == 0:
                        ax.legend(fontsize=8)
                    fig.colorbar(artist, ax=ax, shrink=.8, label="d(loss)/d(package area)")
                    summary["topology"]["cases"][name][phase] = {k: r[k] for k in (
                        "loss", "minimum", "finite_birth_refined_decrease", "finite_birth_refinement", "deletions")}
            fig.savefig(HERE / "topology_diagnostics.png", dpi=160)
            plt.close(fig)
    summary["report_seconds"] = time.perf_counter() - started
    write(HERE / "summary.json", summary)
    print(json.dumps(dict(qualification=summary["qualification"], strategy_cases=len(summary["strategies"]),
                          strategy_gate=summary["all_strategy_gates_pass"],
                          topology_status=summary.get("topology", {}).get("status"))))


if __name__ == "__main__":
    main()
