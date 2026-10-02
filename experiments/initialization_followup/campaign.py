"""Run prepared initializer bundles with the frozen 600-second per-job cap."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from .run import frozen, write


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    jobs = []
    for method in ('lsm', 'topo_full'):
        folder = args.output/method
        manifest = frozen.read(folder/'manifest.json')
        manifest['suite_wall_ceiling_seconds'] = None
        manifest['campaign_note'] = 'No aggregate queue timeout; each independent job retains the frozen 600-second cap.'
        write(folder/'manifest.json', manifest)
        (folder/'logs').mkdir(exist_ok=True)
        spec = frozen.read(folder/'scene_spec.json')
        jobs.extend((method, scene['id'], folder) for scene in spec['scenes'])

    def execute(job):
        method, scene, folder = job
        path = folder/'runs'/'H'/scene
        if (path/'metrics.json').exists() or (path/'failure.json').exists():
            return dict(method=method, scene=scene, status='EXISTING')
        return dict(method=method, **frozen.run_job(folder, scene, 'H', float('inf')))

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(execute, jobs))
    write(args.output/'controller_campaign.json', dict(rows=rows,
        workers=args.workers, per_job_timeout_seconds=600, expected_jobs=len(jobs)))
    for method in ('lsm', 'topo_full'):
        frozen.summarize(args.output/method, render=False)


if __name__ == '__main__':
    main()
