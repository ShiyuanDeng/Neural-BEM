#!/usr/bin/env python3
"""Rerun the September 7 wrong-start cases with repairs, then render videos.

Preserves the original cases, 12 paired views, frequencies, network size,
pretraining budget, and 60-update cap. This is a comparison of the repaired
configuration: contour resolution, star pretraining, and line search changed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
CASES = (
    ("circle", "circle", "siren_circle", "0.25,0.5", "1.0,1.5,2.5", 64, 20, 257, 128, "0.1"),
    ("ellipse-to-circle", "circle", "siren_ellipse", "0.25,0.5", "1.0,1.5,2.5", 64, 20, 257, 128, "0.1"),
    ("star", "star", "siren_star", "0.5,1.5", "0.25,1.0,2.5", 194, 96, 513, 256, "0"),
)


def build_commands(output_root: Path) -> list[dict]:
    """Make explicit wrong-start commands; no training happens here."""
    runs = []
    for name, target, initial, train, holdout, nodes, bandwidth, grid, samples, penalty in CASES:
        destination = output_root / name
        inverse = [
            sys.executable, str(ROOT / "run_implicit_mlp_inverse.py"),
            "--target", target, "--initial-model", initial,
            "--solvers", "kress", "--optimizer", "adjoint",
            "--max-iterations", "60", "--num-pairs", "12",
            "--train-ghz", train, "--holdout-ghz", holdout,
            "--num-nodes", str(nodes), "--bandwidth", str(bandwidth),
            "--grid-resolution", str(grid), "--projected-samples", str(samples),
            "--mlp-hidden-features", "64", "--mlp-hidden-layers", "2",
            "--mlp-pretrain-steps", "6000", "--mlp-pretrain-eikonal-weight", penalty,
            "--learning-rate", "0.001", "--eikonal-weight", "0.01",
            "--loss-tolerance", "1e-12", "--conversion-tolerance-mm", "0.2",
            "--max-backtracks", "14", "--output-dir", str(destination),
            # A scientific recovery FAIL still needs its results and video.
            # This does not disable the optimizer's acceptance checks.
            "--no-gate",
        ]
        video = [
            sys.executable, str(ROOT / "run_sdf_inverse_contour_video.py"),
            str(destination), "--solvers", "kress", "--morph-frames", "0",
            "--hold-frames", "40", "--final-hold-frames", "60",
        ]
        runs.append({
            "case": name,
            "baseline": str(ROOT / "results/inverse/implicit_mlp/2026-09-07" / name),
            "output_dir": str(destination),
            "inverse_command": inverse,
            "video_command": video,
            "status": "pending",
        })
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root", type=Path,
        default=ROOT / "results/inverse/implicit_mlp" / datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Parent directory containing circle/, ellipse-to-circle/, and star/ (default: today's UTC date).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without creating files or running jobs.")
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    runs = build_commands(output_root)
    for run in runs:
        print(f"\n[{run['case']}]", flush=True)
        print(shlex.join(run["inverse_command"]), flush=True)
        print(shlex.join(run["video_command"]), flush=True)
    if args.dry_run:
        return 0

    manifest_path = output_root / "wrong_start_suite.json"
    # Check every destination before starting any expensive job. Existing
    # unrelated siblings such as star-truth/ are fine.
    for path in [manifest_path] + [Path(run["output_dir"]) for run in runs]:
        if path.exists():
            parser.error(f"Refusing to overwrite existing output: {path}. Choose a fresh --output-root.")
    env = os.environ.copy()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "solvers"), env.get("PYTHONPATH", "")]))
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "comparison": "September 7 wrong-start cases and acquisition, with the repaired configuration",
        "changes": [
            "Line search repairs and 14 backtracks (previously 8); conversion tolerance 0.2 mm.",
            "Circle/ellipse: bandwidth 10 to 20, grid 129 to 257, samples 64 to 128; retain 64 nodes.",
            "Star: bandwidth 48 to 96, grid 257 to 513, samples 128 to 256, nodes 128 to 194.",
            "Star pretraining Eikonal weight 0.1 to 0; circle/ellipse retain 0.1.",
        ],
        "caveat": "Not a solver-only ablation. Circle resolution is also applied to ellipse as an unvalidated starting configuration.",
        "runs": runs,
    }
    output_root.mkdir(parents=True, exist_ok=True)

    def save_manifest() -> None:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    save_manifest()
    for run in runs:
        for stage in ("inverse", "video"):
            run["status"] = f"running_{stage}"
            save_manifest()
            print(f"\n[{run['case']}] Running {stage}", flush=True)
            stdout_path = output_root / f"{run['case']}_{stage}_stdout.log"
            stderr_path = output_root / f"{run['case']}_{stage}_stderr.log"
            run[f"{stage}_stdout"] = str(stdout_path)
            run[f"{stage}_stderr"] = str(stderr_path)
            save_manifest()
            with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
                result = subprocess.run(run[f"{stage}_command"], cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
            run[f"{stage}_exit_code"] = result.returncode
            if result.returncode:
                run["status"] = f"failed_{stage}"
                save_manifest()
                break
        else:
            run["status"] = "complete"
            save_manifest()
    print(f"\nSuite record: {manifest_path}", flush=True)
    for run in runs:
        print(f"{run['case']}: {run['status']}", flush=True)
    return 0 if all(run["status"] == "complete" for run in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
