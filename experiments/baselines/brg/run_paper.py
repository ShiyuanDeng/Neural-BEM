"""One resumable paper case; four hours shared by all attempts/candidates."""
import argparse
import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "results/brg/paper_examples/2026-11-17"
UPSTREAM = Path.home() / "neural_bem_external/inverse-obstacle-scattering2d"
CASES = {"glider_033": ("glider", .33, False), "glider_10": ("glider", 10., False),
         "star_full": ("star", .9, False), "star_limited": ("star", .9, True),
         "cavity_09": ("cavity", .9, False), "cavity_2": ("cavity", 2., False)}


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def matlab_processes():
    result = subprocess.run(["ps", "-C", "MATLAB", "-o", "pid=,etime=,args="], capture_output=True, text=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=CASES)
    parser.add_argument("--curvature", required=True, choices=["shipped", "default"])
    parser.add_argument("--detach", action="store_true", help="Keep the supervisor independent of terminal-session lifetime.")
    parser.add_argument('--max-k',type=float,default=30.,help='Last frequency; saved higher-frequency states are retained.')
    args = parser.parse_args()
    assert 1<=args.max_k<=30 and (args.max_k-1)*4==round((args.max_k-1)*4)
    if args.case != "glider_033":
        choice = json.loads((BASE / "curvature_choice.json").read_text())
        assert args.curvature == choice["selected"], "Use the frozen curvature setting."
    case = BASE / args.case
    output = case / args.curvature
    if (output/'coordinator_stop.json').exists():
        raise SystemExit('Coordinator stopped this run after its question was answered; do not resume it.')
    local = output / "local"
    local.mkdir(parents=True, exist_ok=True)
    (case / "local").mkdir(exist_ok=True)
    BASE.mkdir(parents=True, exist_ok=True)
    if args.detach:
        number=len(list(output.glob('launcher_*.json')))+1
        command=['setsid','nohup',sys.executable,str(Path(__file__).resolve()),
                 '--case',args.case,'--curvature',args.curvature,'--max-k',str(args.max_k)]
        log=local/f'supervisor_{number:02d}.log'
        with log.open('w') as stream:
            child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,
                                   stdout=stream,stderr=subprocess.STDOUT,close_fds=True)
        receipt=dict(command=command,pid=child.pid,started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     log=str(log.relative_to(ROOT)))
        write_json(output/f'launcher_{number:02d}.json',receipt)
        print(json.dumps(receipt,indent=2),flush=True)
        return
    with (case / "local" / "runner.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = [p for p in BASE.glob('*/*/attempt_*.json')
                  if json.loads(p.read_text()).get('status') == 'running']
        if any(json.loads(p.read_text()).get('case') == args.case for p in active):
            raise SystemExit('This case already has a running attempt.')
        available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                           if line.startswith('MemAvailable:')))*1024
        if available<14*1024**3:
            raise SystemExit('Memory reserve: less than 14 GiB available; wait before launching.')
        attempts = sorted(case.glob("*/attempt_*.json"))
        now = datetime.datetime.now(datetime.timezone.utc)
        used = sum(json.loads(p.read_text()).get("wall_seconds", (now - datetime.datetime.fromisoformat(json.loads(p.read_text())["started"])).total_seconds()) for p in attempts)
        remaining = math.floor(14400 - used)
        if remaining <= 0:
            raise SystemExit("CASE LIMIT: four-hour budget exhausted; stop and report.")
        number = len(list(output.glob("attempt_*.json"))) + 1
        path = output / f"attempt_{number:02d}.json"
        log = local / f"matlab_{number:02d}.log"
        command = ["matlab", "-batch", f"addpath('{ROOT}/experiments/baselines/brg'); run_paper_case"]
        shape, eta, limited = CASES[args.case]
        record = {"case": args.case, "curvature": args.curvature, "shape": shape,
                  "eta": eta, "limited": limited, "max_k":args.max_k,"command": command, "cwd": str(UPSTREAM),
                  "started": now.isoformat(), "prior_case_wall_seconds": used,
                  "remaining_seconds": remaining, "status": "running",
                  "other_matlab_at_start": matlab_processes(), "log": str(log.relative_to(ROOT))}
        write_json(path, record)
        settings=output/'settings.json'
        if settings.exists():
            (output/f'settings_before_attempt_{number:02d}.json').write_bytes(settings.read_bytes())
        env = os.environ.copy()
        env.update(BRG_PAPER_CASE=args.case, BRG_CURVATURE=args.curvature,
                   BRG_REMAINING_SECONDS=str(remaining - 5), BRG_SHAPE=shape,
                   BRG_ETA=str(eta), BRG_LIMITED=str(int(limited)),BRG_MAX_K=str(args.max_k))
        start = time.monotonic()
        with log.open("w") as stream:
            result = subprocess.run(["timeout", "--signal=KILL", str(remaining), *command],
                                    cwd=UPSTREAM, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record.update(wall_seconds=time.monotonic()-start, returncode=result.returncode,
                      ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      other_matlab_at_end=matlab_processes(), status="finished" if result.returncode == 0 else "failed_or_timed_out")
        write_json(path, record)
        print(json.dumps(record, indent=2), flush=True)
        manifest = []
        for folder in [case / "local", local]:
            for item in sorted(folder.rglob("*")):
                if item.is_file():
                    with item.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    manifest.append({"path": str(item.relative_to(ROOT)), "bytes": item.stat().st_size, "sha256": digest})
        write_json(output / "bulk_manifest.json", {"command": f"python experiments/baselines/brg/run_paper.py --case {args.case} --curvature {args.curvature} --max-k {args.max_k}", "files": manifest})
        lines = [line for line in log.read_text(errors="replace").splitlines() if line.startswith("BRG ")]
        (output / f"progress_{number:02d}.log").write_text("\n".join(lines)+"\n")
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
