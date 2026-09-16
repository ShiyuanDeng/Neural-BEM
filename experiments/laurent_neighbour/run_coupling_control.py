"""Second candidate selected BEFORE nonlinear recovery by interaction-specific gain.

The primary screen chooses maximum overall unknown-neighbour information. That
can reward calibration-reference effects. This counterfactual criterion instead
maximizes the worst-prior precision gain from switching interactions on, among
candidates whose coupled information also exceeds the isolated-target baseline.
Both candidates use the same existing sweep; no recovery outcome enters selection.
"""
import argparse
import json
from pathlib import Path

from experiments.laurent_calibration.run import save
from .run import OUTPUT, qualify, recover, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--max-nfev", type=int, default=180)
    parser.add_argument("--select-only", action="store_true")
    args = parser.parse_args()
    record = json.loads((args.output/"screen.json").read_text())
    eligible = [r for r in record["candidates"] if r["robust_score"] > 1.]
    def score(row):
        return min(p["arms"]["unknown_additive"]["radial_rms_crlb_mm"] /
                   p["arms"]["unknown_coupled"]["radial_rms_crlb_mm"] for p in row["priors"])
    selected = max(eligible, key=score)
    record["original_overall_selection"] = record["selected"]
    record["selected"] = {k: selected[k] for k in ("distance_m", "angle_degrees", "epsr", "robust_score")}
    record["selected"]["interaction_precision_gain"] = score(selected)
    record["criterion"] = "Maximize worst-prior unknown-neighbour precision gain from coupling versus additive echoes; require coupled information to exceed absent baseline"
    record["selection_note"] = "Mechanism control selected from prior-only sweep before either candidate's nonlinear recoveries; not chosen using truth or inversion outcomes"
    output = args.output/"coupling_control"
    save(output/"screen.json", record)
    print("coupling control", json.dumps(record["selected"]), flush=True)
    qualify(output, record)
    if not args.select_only:
        recover(output, record, args.seeds, args.max_nfev)
    manifest(output)


if __name__ == "__main__":
    main()
