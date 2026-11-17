"""Run one BRG stage with a wall limit and durable logs (one MATLAB process)."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
UPSTREAM = Path.home() / "neural_bem_external/inverse-obstacle-scattering2d"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    args = parser.parse_args()
    output = ROOT / "results/brg/examples" / args.stage
    output.mkdir(parents=True, exist_ok=True)
    if (output / "run.json").exists():
        raise SystemExit("Retain previous run: choose a new stage suffix for a retry.")
    command = (["make", "matlab", "MEX=/usr/local/MATLAB/R2026a/bin/mex"]
               if args.stage.startswith("build") else
               ["matlab", "-batch", f"addpath('{ROOT}/experiments/baselines/brg'); run_example('{args.stage}')"])
    limit = 14400 if args.stage == "full" else 1800
    start = time.monotonic()
    record = {"command": command, "cwd": str(UPSTREAM), "limit_seconds": limit,
              "started": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (output / "matlab.log").open("w") as log:
        try:
            result = subprocess.run(["timeout", "--signal=TERM", "--kill-after=30", str(limit), *command],
                                    cwd=UPSTREAM, stdout=log, stderr=subprocess.STDOUT)
            record["returncode"] = result.returncode
        except Exception as exc:
            record["error"] = repr(exc)
            record["returncode"] = 1
    record["wall_seconds"] = time.monotonic() - start
    (output / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    manifest = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
            manifest.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                             "sha256": digest, "commit": path.stat().st_size < 50_000_000})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(record, indent=2), flush=True)
    raise SystemExit(record["returncode"])


if __name__ == "__main__":
    main()
