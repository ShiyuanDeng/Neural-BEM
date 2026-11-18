"""Compare the iteration limit and shape-update band of the four early TG-002 stages."""
import argparse
from collections import defaultdict
from dataclasses import dataclass, replace
import hashlib
import os
from pathlib import Path
import subprocess

for variable in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[variable] = "1"

import numpy as np

from bem_inverse.continuation.geometry import resize
from bem_inverse.io import curve_from, read, write
from bem_inverse.material import MaterialUnknown
from bem_inverse.problem import Problem
from bem_inverse.real_only_policy import RealOnlyPolicy
from bem_inverse.runner import fit
from experiments.benchmark import campaign, scenes
from experiments.comparison import bem
from experiments.comparison.runs import parse, RESULTS
from experiments.comparison.scoring import PROTOCOL, region, region_scores

BASE = parse("bem/default_clean_uc_fc")
OUTPUT = RESULTS / "bem/stage_stops/2026-11-18"
ARMS = ("reference", "longer", "wider", "both")
CASES = ("kite__c4", "c_shape__c4", "aphex_twin__c4", "cog__c4")


@dataclass(frozen=True)
class EarlyStagePolicy(RealOnlyPolicy):
    arm: str = "reference"

    def operations(self, problem, physics):
        operations = []
        for op in super().operations(problem, physics):
            if op.label.startswith("ladder_"):
                stage = op.stage
                stage = replace(stage,
                                iterations=220 if self.arm in ("longer", "both") else stage.iterations,
                                update_modes=stage.update_modes + (2 if self.arm in ("wider", "both") else 0))
                operations.append(replace(op, stage=stage))
            elif self.arm != "reference":
                operations.append(op)
        return operations


def curve_region(curve):
    return region([scenes.LENGTH * curve.values(PROTOCOL["curve_samples"])])[0]


def run(arm, case):
    commit = revision()
    driver_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BASE.folder() / case
    saved = read(directory / "fit.json")
    row = campaign.row(case)
    real, _ = bem.observations(BASE, row, RESULTS)
    initial = curve_from(read(campaign.ROOT / row["initial"]))
    start, _ = bem.weak_start(initial, real[0], bem.solver(BASE), bem.EXECUTION)
    physics, forward = campaign._physics(bem.solver(BASE), bem.EXECUTION)
    loss_history = defaultdict(list)
    boundary_samples = defaultdict(dict)

    def observe(kind, payload):
        if kind == "accepted_history":
            record = payload["row"]
            label = record["work"]["stage"]
            iteration = record["iteration"]
            loss_history[label].append([iteration, record["loss"], record["contrast"]])
            if iteration in (17, 22, 23):
                boundary_samples[label][iteration] = record["coefficients"]

    def select_history(event):
        if event["reason"] == "resolved stage entered":
            physics.observer = observe if event["operation"]["label"].startswith("ladder_") else None

    result = fit(Problem(initial, real, None, start), solver=bem.solver(BASE), execution=bem.EXECUTION,
                 policy=EarlyStagePolicy(arm=arm, fit_seconds=bem.FIT_SECONDS), physics=physics,
                 forward_solve=forward, geometry_update=bem.GEOMETRY_UPDATE, material=MaterialUnknown(),
                 on_event=select_history)
    # Load truth only after the inverse returns.
    truth_curve = curve_from(read(campaign.ROOT / row["truth"]))
    truth = curve_region(truth_curve)

    def score(curve):
        return region_scores(curve_region(curve), truth)["area_error"]

    saved_stages = {s["stage"]: s for s in saved["stages"]}
    stages = []
    for stage in result["stages"]:
        label = stage["stage"]
        curve = curve_from(stage["curve"])
        record = {k: stage[k] for k in ("stage", "M", "K_geometry", "nodes", "outcome", "stop", "detail",
                                        "accepted_steps", "seconds", "initial_loss", "final_loss", "contrast", "curve")}
        record["stage_units"] = stage["work"]["stage_units"]
        record["area_error"] = score(curve)
        if label.startswith("ladder_"):
            record["accepted_iteration_loss_contrast"] = loss_history[label]
            record["sampled_area_error"] = {i: score(curve_from(data)) for i, data in boundary_samples[label].items()}
            if label in saved_stages:
                saved_curve = curve_from(saved_stages[label]["curve"])
                record["relative_curve_difference_from_saved"] = float(
                    np.linalg.norm(curve.coefficients - saved_curve.coefficients) / np.linalg.norm(saved_curve.coefficients))
        stages.append(record)
    summary = dict(case=case, arm=arm, default_run=BASE.key, source_commit=commit, driver_sha256=driver_sha256,
                   initial_contrast=start, original_initial_contrast=saved["contrast_start"]["start_contrast"],
                   fit_seconds=result["fit_and_localization_seconds"], work_units=result["fit_and_localization_units"],
                   outcome=result["outcome"], detail=result["detail"], final_contrast=result["final_contrast"],
                   final_area_error=score(curve_from(result["final_curve"])), stages=stages)
    if arm == "reference":
        summary["true_curve_storage_area_error"] = {k: score(resize(truth_curve, k)) for k in (8, 12, 16, 20)}
    return summary


def revision():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=campaign.ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arm", choices=ARMS)
    arm = parser.parse_args().arm
    for case in CASES:
        file = OUTPUT / arm / f"{case}.json"
        if file.exists():
            continue
        result = run(arm, case)
        write(file, result)
        print(case, arm, result["outcome"], f"area error {result['final_area_error']:.3%}", flush=True)


if __name__ == "__main__":
    main()
