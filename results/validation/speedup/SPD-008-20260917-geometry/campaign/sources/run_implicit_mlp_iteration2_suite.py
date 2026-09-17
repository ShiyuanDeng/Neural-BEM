#!/usr/bin/env python3
"""Run all ungated iteration-2 diagnostics, then stop for evidence review."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parent


def build_jobs(output):
    jobs = []
    def add(name, script, arguments):
        jobs.append({"name": name, "command": [sys.executable, "-u", str(ROOT / script),
                     *arguments, "--output-dir", str(output / name)], "status": "pending"})
    add("geometry-replay", "audit_implicit_mlp_geometry_runtime.py", ["--all-selected-states", "--max-seconds", "120"])
    def frozen(case, states, stage):
        name = f"{case}-{states.replace(',', '-')}-{stage}"
        add(name, "run_implicit_mlp_frozen_diagnostics.py", [
            "--run-dir", str(ROOT / "results/inverse/implicit_mlp/2026-09-08" / case),
            "--states", states, "--stages", stage,
            "--max-evaluations", "160", "--max-wall-seconds", "600"])
    frozen("circle", "55,60", "characterize")
    frozen("star", "0,16,32,40,47", "characterize")
    frozen("star-truth", "all", "characterize")
    for case, states in (("star", (32, 47)), ("circle", (60,))):
        for state in states:
            frozen(case, str(state), "curve_metric")
    for case, states in (("star", (32, 47)), ("circle", (55, 60))):
        for state in states:
            frozen(case, str(state), "neural_motion")
    for state in (32, 47):
        frozen("star", str(state), "field_repair")
    for state in (40, 47):
        frozen("star", str(state), "conversion_audit")
    add("ellipse-startup", "run_implicit_mlp_ellipse_startup.py", ["--max-wall-seconds", "600"])
    return jobs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    output = (args.output_root or ROOT / "results/validation/implicit_mlp_adjoint" /
              ("iteration-02-suite-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))).resolve()
    jobs = build_jobs(output)
    if args.dry_run:
        for job in jobs:
            print(shlex.join(job["command"]))
        return 0
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    env["MPLCONFIGDIR"] = "/tmp/implicit-iteration2-mpl"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "solvers"), env.get("PYTHONPATH")]))
    manifest = {"jobs": jobs, "status": "running", "output_root": str(output),
                "next_gate": "Review measured diagnostics before conditional sampling/acquisition inverses; no long inverse is launched."}
    def save():
        (output / "suite.json").write_text(json.dumps(manifest, indent=2) + "\n")
    save()
    print(f"Results and logs: {output}", flush=True)
    try:
        for index, job in enumerate(jobs, 1):
            print(f"\n[{index}/{len(jobs)}] {job['name']}", flush=True)
            log = output / (job["name"] + ".log")
            job.update(status="running", log=str(log))
            save()
            start = monotonic()
            with log.open("w", buffering=1) as stream:
                with subprocess.Popen(job["command"], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, bufsize=1) as process:
                    try:
                        for line in process.stdout:
                            stream.write(line)
                            print(line, end="", flush=True)
                        code = process.wait()
                    except BaseException:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        raise
            job.update(exit_code=code, seconds=monotonic() - start,
                       status="completed" if code == 0 else "incomplete_or_failed")
            save()
            if index == 1 and code:
                manifest["status"] = "geometry_replay_gate_failed"
                save()
                return code
        manifest["status"] = "ready_for_review" if all(j["status"] == "completed" for j in jobs) else "review_partial_results"
    except BaseException:
        manifest["status"] = "interrupted"
        save()
        raise
    save()
    print(f"\n{manifest['status']}: {output / 'suite.json'}", flush=True)
    print(manifest["next_gate"], flush=True)
    return 0 if manifest["status"] == "ready_for_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
