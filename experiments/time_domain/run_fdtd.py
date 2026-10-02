"""Run isolated 20-receiver gprMax Ricker experiments; preserve existing caches."""
from pathlib import Path
import argparse
import contextlib
import hashlib
import json
import subprocess
import sys
import tempfile
import time

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def render_scene(cell_size, target, time_window, threads):
    pml = round(.048 / cell_size)
    lines = [f"#title: time-domain circle, {'target' if target else 'background'}",
        f"#domain: 0.8 0.8 {cell_size}", f"#dx_dy_dz: {cell_size} {cell_size} {cell_size}",
        f"#time_window: {time_window}", f"#num_threads: {threads}",
        f"#pml_cells: {pml} {pml} 0 {pml} {pml} 0",
        "#material: 4 0 1 0 dielectric"]
    if target:
        lines.append(f"#cylinder: 0.4 0.4 0 0.4 0.4 {cell_size} 0.1 dielectric")
    lines += ["#waveform: ricker 1 1e9 pulse", "#hertzian_dipole: z 0.4 0.7 0 pulse"]
    lines += [f"#rx: {x:.8f} 0.64 0" for x in .2 + .02 * np.arange(20)]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/time_domain")
    parser.add_argument("--gprmax-checkout", type=Path, default=Path("/home/drdeng/gprMax"))
    parser.add_argument("--cell-sizes", type=float, nargs="+", default=[.004, .002, .001])
    parser.add_argument("--time-window", type=float, default=12e-9)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    if not np.isfinite(args.time_window) or args.time_window <= 0 or args.threads < 1:
        parser.error("Require a finite positive time window and at least one CPU thread.")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "inputs").mkdir(exist_ok=True)
    sys.path.insert(0, str(args.gprmax_checkout))
    from gprMax.gprMax import api
    from gprMax._version import __version__
    from gprMax.constants import e0, m0
    from gprMax.waveforms import Waveform
    if __version__ != "3.1.7":
        raise ValueError("This absolute source-timing experiment is qualified for gprMax3.1.7 only.")
    revision = subprocess.check_output(["git", "-C", str(args.gprmax_checkout), "rev-parse", "HEAD"], text=True).strip()
    physics_hashes = {name: hashlib.sha256((args.gprmax_checkout / "gprMax" / name).read_bytes()).hexdigest()
                      for name in ("sources.py", "waveforms.py", "model_build_run.py", "input_cmds_multiuse.py")}
    for dx in args.cell_sizes:
        coordinates = np.r_[.8, .4, .7, .64, .2 + .02 * np.arange(20)]
        if not np.isfinite(dx) or dx <= 0 or not np.allclose(coordinates / dx, np.round(coordinates / dx), atol=1e-8, rtol=0):
            raise ValueError("cell sizes must put domain, center, source, and receivers exactly on the Yee grid")
        label = f"dx{dx * 1000:g}mm"
        path = args.output / f"fdtd_{label}.npz"
        input_hashes = {variant: hashlib.sha256(render_scene(dx, variant == "target", args.time_window, args.threads).encode()).hexdigest()
                        for variant in ("background", "target")}
        if path.exists():
            old = json.loads(path.with_suffix(".json").read_text())
            if (old["time_window"] != args.time_window or old.get("gprmax_revision") != revision
                    or old.get("gprmax_version") != __version__ or old.get("input_sha256") != input_hashes
                    or old.get("gprmax_source_sha256") != physics_hashes):
                raise ValueError("Existing output has different or unverified inputs/physics; use a separate --output directory.")
            print(f"Keeping existing {path}", flush=True)
            continue
        started = time.perf_counter()
        results = {}
        with tempfile.TemporaryDirectory(prefix="neural_bem_time_domain_") as scratch:
            for variant in ("background", "target"):
                scene = render_scene(dx, variant == "target", args.time_window, args.threads)
                (args.output / "inputs" / f"{label}_{variant}.in").write_text(scene)
                inputfile = Path(scratch) / f"{variant}.in"
                inputfile.write_text(scene)
                with (args.output / f"{label}_{variant}.log").open("w") as log:
                    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                        api(str(inputfile), n=1)
                with h5py.File(inputfile.with_suffix(".out"), "r") as handle:
                    dt = float(handle.attrs["dt"])
                    results[variant] = np.stack([np.asarray(handle[f"rxs/rx{number}/Ez"], dtype=float)
                        for number in range(1, 21)], axis=1)
                print(f"Completed {label} {variant} in {time.perf_counter() - started:.2f}s", flush=True)
        assert results["background"].shape == results["target"].shape
        count = len(results["background"])
        waveform = Waveform()
        waveform.type, waveform.freq = "ricker", 1e9
        current = np.asarray([waveform.calculate_value(i * dt, dt) for i in range(count)], dtype=np.float32)
        np.savez_compressed(path, background=results["background"], total=results["target"],
            scattered=results["target"] - results["background"], source_current=current,
            dt=dt, cell_size=dx,
            source=np.array([[.4, .7]]), receivers=np.column_stack([.2 + .02 * np.arange(20), np.full(20, .64)]))
        metadata = dict(gprmax_version=__version__, gprmax_revision=revision, cell_size_m=dx, dt=dt,
            input_sha256=input_hashes, gprmax_source_sha256=physics_hashes,
            iterations=count, time_window=args.time_window, eps0=float(e0), mu0=float(m0),
            source_sampling="w(n*dt) used in update E(n*dt)->E((n+1)*dt); effective current time (n+1/2)*dt",
            source_units="amperes of z-directed line current; dl=dz cancels the one-cell extrusion",
            threads=args.threads, wall_seconds=time.perf_counter() - started)
        path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps(metadata), flush=True)


if __name__ == "__main__":
    main()
