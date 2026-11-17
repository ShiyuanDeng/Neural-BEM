"""Resume the shipped BRG cavity example within a cumulative four-hour limit."""
import datetime
import fcntl
import hashlib
import json
import math
from pathlib import Path
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results/brg/examples/shipped_cavity_full"
UPSTREAM = Path.home() / "neural_bem_external/inverse-obstacle-scattering2d"
LABEL = "BRG shipped cavity example; not a table B result"


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def main():
    local = OUT / "local"
    local.mkdir(parents=True, exist_ok=True)
    with (local / "runner.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = sorted(OUT.glob("attempt_*.json"))
        used = 0.0
        now = datetime.datetime.now(datetime.timezone.utc)
        for path in previous:
            attempt = json.loads(path.read_text())
            used += attempt.get("wall_seconds", (now - datetime.datetime.fromisoformat(attempt["started"])).total_seconds())
        remaining = math.floor(14400 - used)
        if remaining <= 0:
            raise SystemExit("The cumulative four-hour budget is exhausted; retained checkpoints are unchanged.")
        number = len(previous) + 1
        record_path = OUT / f"attempt_{number:02d}.json"
        log_path = local / f"matlab_{number:02d}.log"
        command = ["matlab", "-batch", f"addpath('{ROOT}/experiments/baselines/brg'); run_shipped_cavity"]
        record = {"label": LABEL, "command": command, "cwd": str(UPSTREAM),
                  "started": now.isoformat(), "prior_wall_seconds": used,
                  "remaining_seconds": remaining, "status": "running", "log": str(log_path.relative_to(ROOT))}
        write_json(record_path, record)
        env = os.environ.copy()
        env["BRG_REMAINING_SECONDS"] = str(remaining - 5)
        begin = time.monotonic()
        with log_path.open("w") as log:
            result = subprocess.run(["timeout", "--signal=KILL", str(remaining), *command],
                                    cwd=UPSTREAM, env=env, stdout=log, stderr=subprocess.STDOUT)
        record.update(returncode=result.returncode, wall_seconds=time.monotonic() - begin,
                      status="finished" if result.returncode == 0 else "failed_or_timed_out")
        write_json(record_path, record)
        manifest = []
        for path in sorted(local.rglob("*")):
            if path.is_file() and path.name != "runner.lock":
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                manifest.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                                 "sha256": digest, "commit": False})
        write_json(OUT / "bulk_manifest.json", {"command": "python experiments/baselines/brg/run_full.py", "files": manifest})
        print(json.dumps(record, indent=2), flush=True)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
