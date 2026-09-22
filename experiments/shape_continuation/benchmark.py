"""Replay saved observations to time the inverse without reference generation."""
import argparse
import cProfile
from dataclasses import asdict
import io
import json
from pathlib import Path
import pstats
from time import perf_counter

import numpy as np

from .forward import Acquisition, Work
from .geometry import FourierCurve
from .inverse import FitConfig, Observation, run_continuation
from .run import provenance
from .schedule import Stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    args.output.mkdir(parents=True, exist_ok=False)
    saved = json.loads((args.pilot / "summary.json").read_text())
    stages = [Stage(**s) for s in saved["planned_stages"]]
    config = FitConfig(**saved["config"])
    with np.load(args.pilot / "inputs.npz") as arrays:
        initial = FourierCurve(arrays["initial"])
        observations = [Observation(s.wavenumber,
            Acquisition(arrays[f"directions_{i}"], arrays[f"receivers_{i}"]), arrays[f"data_{i}"])
            for i, s in enumerate(stages)]
    rows = []
    for repeat in range(args.repeats + 1):
        work = Work(max_forwards=550)
        profile = cProfile.Profile() if repeat == args.repeats else None
        if profile is not None:
            profile.enable()
        started = perf_counter()
        results = run_continuation(initial, observations, stages, saved["contrast"], config=config, work=work)
        seconds = perf_counter() - started
        if profile is not None:
            profile.disable()
            buffer = io.StringIO()
            pstats.Stats(profile, stream=buffer).strip_dirs().sort_stats("cumtime").print_stats(45)
            (args.output / "profile.txt").write_text(buffer.getvalue())
        row = dict(repeat=repeat, profiled=profile is not None, seconds=seconds,
            work=work.summary(), stop_reasons=[r.stop_reason for r in results],
            residuals=[r.relative_residual for r in results],
            accepted_updates=sum(len(r.states) - 1 for r in results))
        rows.append(row)
        np.savez_compressed(args.output / f"states_{repeat}.npz",
            **{f"stage_{i}_iterate_{j}": s.coefficients for i, r in enumerate(results) for j, s in enumerate(r.states)})
        print(json.dumps(row), flush=True)
    report = dict(provenance=provenance(), pilot=str(args.pilot), config=asdict(config), rows=rows,
                  median_seconds=float(np.median([r["seconds"] for r in rows if not r["profiled"]])))
    (args.output / "timing.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
