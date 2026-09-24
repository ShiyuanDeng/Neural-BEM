"""One-variable ellipse-to-star ablation. Run from the repository root."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from experiments.shape_continuation.continuation import run_adaptive
from experiments.shape_continuation.forward import BudgetExceeded, Work
from experiments.shape_continuation.inverse import FitConfig, prepare_state, optimise_step
from experiments.shape_continuation.legacy_cases import (
    LegacyCatalogPolicy, load_shape, observations, physical, score, shape_record,
    source_hashes, write,
)
from experiments.shape_continuation.run import provenance
from experiments.shape_continuation.schedule import Stage

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "SC-018-legacy-single-object"
CASE = "ellipse-to-star"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output):
    original = json.loads((PREVIOUS / "manifest.json").read_text())
    current = source_hashes()
    assert all(current.get(k) == v for k, v in original["source_sha256"].items())
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise FileExistsError("Use a fresh output directory.")
    source = PREVIOUS / "inputs" / CASE / "input.json"
    (output / "input.json").write_bytes(source.read_bytes())
    write(output / "manifest.json", dict(
        case=CASE, provenance=provenance(), source_sha256=current,
        script_sha256=digest(Path(__file__)), input_sha256=digest(source),
        old_manifest_sha256=digest(PREVIOUS / "manifest.json"),
        base_config=original["new_config"], arms={"control": 0, "halving": 6},
        max_forwards=original["max_forward_frequency_solves"],
        max_seconds=original["max_seconds"], max_decisions=original["new_max_decisions"],
        gates=original["gates"], policy="LegacyCatalogPolicy(mode='fixed')",
        only_changed_setting="FitConfig.backtracks: 0 -> 6; steps 1, 1/2, ..., 1/64",
    ))


def checked_inputs(output):
    manifest = json.loads((output / "manifest.json").read_text())
    assert source_hashes() == manifest["source_sha256"]
    assert digest(Path(__file__)) == manifest["script_sha256"]
    assert digest(output / "input.json") == manifest["input_sha256"]
    return manifest, json.loads((output / "input.json").read_text())


def run_arm(output, arm):
    manifest, data = checked_inputs(output)
    directory = output / arm
    directory.mkdir()
    config = replace(FitConfig(**manifest["base_config"]), backtracks=manifest["arms"][arm])
    changes = {k: v for k, v in asdict(config).items()
               if v != asdict(FitConfig(**manifest["base_config"]))[k]}
    assert changes == ({} if arm == "control" else {"backtracks": 6})
    work = Work(max_forwards=manifest["max_forwards"], max_seconds=manifest["max_seconds"])
    obs = observations(data)[:3]
    policy = LegacyCatalogPolicy(obs, data["contrast"], work, mode="fixed", config=config)
    shape, trajectory = load_shape(data["initial"]), []

    def checkpoint(record):
        nonlocal shape
        if record.committed:
            shape = record.result.shape
        row = dict(index=record.index, stage=asdict(record.decision.stage),
                   config=asdict(record.decision.config), stop=record.result.stop_reason,
                   committed=record.committed, shape=shape_record(shape),
                   residual=record.result.relative_residual, forwards=work.attempted,
                   seconds=perf_counter()-work.started,
                   accepted_steps=len(record.result.states)-1,
                   history=record.result.history, trials=record.result.trials,
                   states=[shape_record(s) for s in record.result.states])
        trajectory.append(row)
        write(directory / f"decision-{record.index:02d}.json", row)
        write(directory / "checkpoint.json", dict(shape=shape_record(shape),
              stage=row["stage"], forwards=work.attempted, residual=row["residual"]))
        print(json.dumps({k: row[k] for k in
                          ("index", "stop", "residual", "forwards", "accepted_steps")}), flush=True)

    try:
        result = run_adaptive(shape, obs, data["contrast"], policy, work=work,
                              max_decisions=manifest["max_decisions"], on_decision=checkpoint)
        shape, stop, failure = result.shape, result.stop_reason, None
    except BudgetExceeded:
        stop, failure = "budget_exhausted", None
    except Exception as exc:
        stop, failure = "failed", f"{type(exc).__name__}: {exc}"
    record = dict(arm=arm, config=asdict(config), changed_settings=changes,
                  input_sha256=manifest["input_sha256"], shape=shape_record(shape),
                  stop=stop, failure=failure, forwards=work.attempted,
                  elapsed_seconds=perf_counter()-work.started, work=work.summary(),
                  accepted_steps=sum(r["accepted_steps"] for r in trajectory),
                  trial_status_counts=dict(Counter(t.get("status", "unknown")
                      for r in trajectory for t in r["trials"])),
                  accepted_halved_steps=sum(h.get("step", 1.) < 1.
                      for r in trajectory for h in r["history"] if "direction" in h))
    if arm == "control":
        previous = json.loads((PREVIOUS / "runs" / CASE / "fixed" / "result.json").read_text())
        record["exact_sc018_replay"] = (record["shape"] == previous["shape"]
                                        and work.attempted == previous["forwards"])
        assert record["exact_sc018_replay"]
    write(directory / "result.json", record)
    try:
        scores = score(data, shape)
        gate = manifest["gates"]
        record.update(scores=scores, passed=(failure is None
            and scores["boundary_upper_m"] <= gate["boundary_upper_m"]
            and scores["train_relative"] <= gate["train_relative"]
            and scores["worst_holdout_relative"] <= gate["holdout_relative"]
            and scores["endpoint_field_refinement"] <= gate["endpoint_field_refinement"]))
    except Exception as exc:
        record.update(passed=False, evaluation_failure=f"{type(exc).__name__}: {exc}")
    write(directory / "result.json", record)
    print(json.dumps({k: record.get(k) for k in
                      ("arm", "stop", "forwards", "passed", "scores")}), flush=True)


def probe_stalled_state(output):
    """Compare both searches at exactly the control's first stalled geometry."""
    manifest, data = checked_inputs(output)
    stalled = json.loads((output / "control" / "decision-00.json").read_text())
    assert stalled["stop"] == "no_acceptable_step"
    stage = Stage(**stalled["stage"])
    shape = load_shape(stalled["shape"])
    rows = []
    for backtracks in (0, 6):
        work = Work(max_forwards=500, max_seconds=120)
        state = prepare_state(shape, observations(data)[0], stage, data["contrast"], work=work)
        result = optimise_step(state, config=replace(FitConfig(**manifest["base_config"]),
                                                    backtracks=backtracks), work=work)
        rows.append(dict(backtracks=backtracks, accepted=result.accepted,
                         before=state.relative_residual, after=result.state.relative_residual,
                         stop=result.stop_reason, diagnostics=result.diagnostics,
                         trials=result.trials, accepted_record=result.accepted_record,
                         work=work.summary()))
    write(output / "same-state-probe.json", dict(shape=stalled["shape"], stage=asdict(stage),
          note="Separate post-run diagnostic; its work is excluded from both inverse arms.", rows=rows))
    print(json.dumps([{k: r[k] for k in ("backtracks", "accepted", "before", "after", "stop")}
                      for r in rows]), flush=True)


def report(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    manifest, data = checked_inputs(output)
    rows = [json.loads((output / a / "result.json").read_text()) for a in manifest["arms"]]
    legacy = json.loads((PREVIOUS / "runs" / CASE / "legacy_cartesian" / "result.json").read_text())
    write(output / "comparison.json", rows)
    fig, ax = plt.subplots(figsize=(6, 6))
    series = [(data["initial"], "initial", "0.65", ":"),
              (data["truth"], "truth", "black", "--"),
              (legacy["shape"], "previous Cartesian", "black", "-"),
              (rows[0]["shape"], "new: no halving", "C0", "-"),
              (rows[1]["shape"], "new: six halvings", "C1", "-")]
    for record, label, color, style in series:
        z = physical(load_shape(record)).values(4096)
        ax.plot(z.real, z.imag, label=label, color=color, linestyle=style)
    ax.set(xlabel="x (m)", ylabel="y (m)", title="Ellipse-to-star: step-halving ablation")
    ax.set_aspect("equal")
    ax.grid(alpha=.2)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), ncol=2)
    fig.tight_layout()
    fig.savefig(output / "boundaries.png", dpi=160)
    plt.close(fig)
    for r in [legacy, *rows]:
        print(r.get("arm"), r["forwards"], r.get("scores"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--arm", choices=("control", "halving"))
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.prepare: prepare(args.output)
    if args.arm: run_arm(args.output, args.arm)
    if args.probe: probe_stalled_state(args.output)
    if args.report: report(args.output)


if __name__ == "__main__":
    main()
