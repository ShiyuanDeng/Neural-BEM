"""TOP-012 stage 3: the twelve frozen scenes, arm H, on the enriched acquisition.

Mirrors the benchmark driver's own post-prepare loop so the suite can be run
after stage 2 without re-preparing the bundle. Workers, per-scene timeout and
suite wall ceiling are the v1 numbers, unchanged: acquisition is the only
difference between this arm and the v1 arm it is compared against.

Arm H is the policy the most recent full v1 benchmark ran
([TOP-008](../TOP-008-20260912-feasible-fd/README.md): 5 of 12 passed, 2
timeouts), so it is the only arm here. Scenes, truths, materials, resolutions,
gates, budgets and controller policy are identical to v1.
"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark  # noqa: E402
import run_fourier_topology_controller as driver  # noqa: E402

SUITE = HERE / 'suite'
ARM = 'H'
# Declared before execution; the v1 values, unchanged.
WORKERS = 4
SUITE_WALL_CEILING_SECONDS = 2700


def main():
    spec = benchmark.read(SUITE / 'scene_spec.json')
    (SUITE / 'logs').mkdir(exist_ok=True)
    deadline = monotonic() + SUITE_WALL_CEILING_SECONDS
    # The v1 suite starts this scene first; keeping the order keeps the queue
    # comparable. No outcome affects what runs next.
    scenes = sorted(spec['scenes'], key=lambda s: s['id'] != 'far-ellipse-star')
    records = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs = [pool.submit(benchmark.run_job, SUITE, scene['id'], ARM, deadline)
                for scene in scenes]
        for job in as_completed(jobs):
            records.append(job.result())
            driver.write_json(SUITE / 'execution_status.json', records)
    summary = benchmark.summarize(SUITE, render=False)
    return 0 if summary['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
