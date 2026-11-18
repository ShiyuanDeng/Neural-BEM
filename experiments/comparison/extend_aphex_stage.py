"""Extend the original Aphex Twin fourth stage without changing its entry state."""
from dataclasses import replace

from experiments.comparison.check_stage_stops import BASE, OUTPUT, curve_region, revision
import numpy as np
from bem_inverse.io import curve_from, read, write
from bem_inverse.material import MaterialUnknown
from bem_inverse.problem import Problem
from bem_inverse.real_only_policy import RealOnlyPolicy
from bem_inverse.runner import fit
from experiments.benchmark import campaign
from experiments.comparison import bem
from experiments.comparison.runs import RESULTS
from experiments.comparison.scoring import region_scores


class FourthStage(RealOnlyPolicy):
    def operations(self, problem, physics):
        original = next(op for op in super().operations(problem, physics) if op.label == "ladder_4_real")
        return [replace(original, stage=replace(original.stage, iterations=220))]


def main():
    case = "aphex_twin__c4"
    saved = read(BASE.folder() / case / "fit.json")
    entry, original = saved["stages"][2:4]
    reference = read(OUTPUT / "reference" / f"{case}.json")["stages"][3]
    row = campaign.row(case)
    real, _ = bem.observations(BASE, row, RESULTS)
    problem = Problem(curve_from(entry["curve"]), real, None, entry["contrast"])
    physics, forward = campaign._physics(bem.solver(BASE), bem.EXECUTION)
    history = []

    def observe(kind, payload):
        if kind == "accepted_history":
            row = payload["row"]
            history.append(dict(iteration=row["iteration"], loss=row["loss"], contrast=row["contrast"],
                                seconds=row["work"]["seconds"], curve=row["coefficients"]))

    physics.observer = observe
    fit_result = fit(problem, solver=bem.solver(BASE), execution=bem.EXECUTION, physics=physics,
                     forward_solve=forward, policy=FourthStage(fit_seconds=240), material=MaterialUnknown(),
                     geometry_update=bem.GEOMETRY_UPDATE)
    stage = fit_result["stages"][0]
    truth = curve_region(curve_from(read(campaign.ROOT / row["truth"])))
    for point in history:
        point["area_error"] = region_scores(curve_region(curve_from(point["curve"])), truth)["area_error"]
    reference_history = reference["accepted_iteration_loss_contrast"]
    reference_matched = [[p["iteration"], p["loss"], p["contrast"]] for p in history[:len(reference_history)]]
    original_endpoint_matched = any(
        p["iteration"] == 22 and np.array_equal(curve_from(p["curve"]).coefficients,
                                               curve_from(original["curve"]).coefficients) for p in history)
    record = dict(case=case, source_commit=revision(), original_run=BASE.key, original_entry=entry["stage"],
                  original_seconds_left=bem.FIT_SECONDS-entry["work"]["seconds"], stage_seconds_limit=240,
                  original_iterations_match=reference_matched == reference_history,
                  original_boundary_at_22_matches=original_endpoint_matched, stage=stage, history=history)
    path = OUTPUT / "aphex_fourth" / f"{case}.json"
    write(path, record)
    print(stage["outcome"], stage["stop"], stage["accepted_steps"], path, flush=True)


if __name__ == "__main__":
    main()
