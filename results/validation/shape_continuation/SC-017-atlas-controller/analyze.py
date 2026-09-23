"""Score every saved iterate of every arm, and draw cost against accuracy.

A single endpoint comparison depends on where the budget line happens to
fall. Scoring each committed iterate against its cumulative forward-solve
count gives the whole trade-off curve instead, which is what a continuation
policy should be judged on. Scoring uses only geometry, so it adds no solves.

    PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-017-atlas-controller/analyze.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))

from experiments.shape_continuation.geometry import FourierCurve  # noqa: E402
from experiments.shape_continuation.metrics import boundary_distance  # noqa: E402
from experiments.shape_continuation.run import fixture  # noqa: E402

ARMS = ("fixed", "band", "frequency", "full")


def trajectory(directory, truth, radius):
    """Boundary error of every committed iterate against forward solves spent."""
    summary = json.loads((directory / "summary.json").read_text())
    points = []
    for entry in summary["trace"]:
        shot = directory / f"decision_{entry['index']:03d}.npz"
        if not shot.exists():
            continue
        shape = FourierCurve(np.load(shot)["shape"])
        error, bound = boundary_distance(truth, shape)
        points.append(dict(index=entry["index"],
                           wavenumber=entry["stage"]["wavenumber"],
                           band=entry["stage"]["update_modes"],
                           forwards=entry["work_after"]["attempted"],
                           relative_residual=entry["relative_residual"],
                           relative_boundary_error=error / radius,
                           relative_boundary_error_upper_bound=(error + bound) / radius))
    return summary, points


def cost_to_reach(points, target):
    """Forward solves spent before the boundary error first reaches `target`."""
    for point in points:
        if point["relative_boundary_error"] <= target:
            return point["forwards"]
    return None


def main():
    truth = fixture("glider")
    radius = float(np.sqrt(truth.nodes(8192).signed_area / np.pi))
    targets = (0.1, 0.05, 0.02, 0.01)
    records = {}
    for case in sorted(p for p in HERE.iterdir() if p.is_dir()):
        for directory in sorted(p for p in case.iterdir() if p.is_dir()):
            if not (directory / "summary.json").exists():
                continue
            summary, points = trajectory(directory, truth, radius)
            arm, start = summary["arm"], summary["start"]
            records[f"{case.name}/{arm}-{start}"] = dict(
                case=case.name, arm=arm, start=start,
                contrast=json.loads((case / "manifest.json").read_text())["arguments"]["contrast"],
                stop_reason=summary["stop_reason"], failure=summary["failure"],
                decisions=summary["decisions"],
                highest_wavenumber=summary["highest_wavenumber"],
                forwards=summary["work"]["attempted"],
                final=summary["scores"]["relative_boundary_error"],
                final_bound=summary["scores"]["relative_boundary_error_upper_bound"],
                area=summary["scores"].get("area", {}).get("relative_symmetric_difference"),
                holdout=summary["scores"].get("holdout_relative_error"),
                best=min((p["relative_boundary_error"] for p in points), default=None),
                cost_to_reach={str(t): cost_to_reach(points, t) for t in targets},
                probe_forwards=sum(p["forwards"] for p in summary.get("probes", [])),
                probes=len(summary.get("probes", [])),
                bands=[d["band"] for d in summary.get("policy_decisions", [])],
                wavenumbers=[d["wavenumber"] for d in summary.get("policy_decisions", [])],
                trajectory=points)
    (HERE / "analysis.json").write_text(json.dumps(records, indent=2) + "\n")
    figures(records, targets)
    header = f"{'case/arm':28s} {'stop':18s} {'kmax':>5s} {'fwd':>6s} {'probe':>6s} {'final':>8s} {'best':>8s} " \
             + " ".join(f"{'c@'+str(t):>7s}" for t in targets)
    print(header)
    for name, record in sorted(records.items()):
        costs = " ".join(f"{record['cost_to_reach'][str(t)] or '-':>7}" for t in targets)
        print(f"{name:28s} {record['stop_reason']:18s} {str(record['highest_wavenumber']):>5s} "
              f"{record['forwards']:6d} {record['probe_forwards']:6d} "
              f"{record['final']:8.5f} {(record['best'] or float('nan')):8.5f} {costs}")


def figures(records, targets):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cases = sorted({record["case"] for record in records.values()})
    columns = min(4, len(cases))
    rows = int(np.ceil(len(cases) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(4.2 * columns, 3.6 * rows),
                                squeeze=False)
    colours = dict(zip(ARMS, ("k", "C0", "C1", "C3")))
    for axis, case in zip(axes.ravel(), cases):
        for name, record in sorted(records.items()):
            if record["case"] != case or not record["trajectory"]:
                continue
            forwards = [p["forwards"] for p in record["trajectory"]]
            errors = [p["relative_boundary_error"] for p in record["trajectory"]]
            axis.semilogy(forwards, errors, "-o", ms=2.5, color=colours.get(record["arm"], "C2"),
                          label=record["arm"])
        axis.set(title=case, xlabel="cumulative forward solves",
                 ylabel="relative boundary error")
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    for axis in axes.ravel()[len(cases):]:
        axis.set_axis_off()
    figure.suptitle("Cost against accuracy: atlas-driven arms versus the fixed ladder")
    figure.tight_layout()
    figure.savefig(HERE / "cost_accuracy.png", dpi=150)
    plt.close(figure)


if __name__ == "__main__":
    main()
