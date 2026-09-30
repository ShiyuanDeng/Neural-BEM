"""SC-051 predeclared six-scene resolution control: N doubles, M/K stay 255."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

from experiments.shape_continuation import frequency_only as f

PRIMARY = f.OUT
CONTROL = PRIMARY / 'resolution_1024'
original_schedule = f.schedule


def schedule(catalog, frequencies, config):
    return [replace(s, nodes=1024, refined_nodes=2048)
            for s in original_schedule(catalog, frequencies, config)]


def prepare():
    manifest = f.verify()
    if (CONTROL/'manifest.json').exists():
        raise FileExistsError('Preserve resolution control')
    rows = [r for r in manifest['cases'] if r['panel']=='core']
    f.write(CONTROL/'manifest.json', dict(manifest, experiment='SC-051-resolution-control', cases=rows,
        nodes=1024, M=255, K=255, parent_manifest=f.digest(PRIMARY/'manifest.json'),
        sources=dict(manifest['sources'], **{f.relative(Path(__file__)):f.digest(Path(__file__)),
            f.relative(CONTROL/'plan.md'):f.digest(CONTROL/'plan.md')})))
    print('FROZEN resolution control, six cases, same M/K and budgets',flush=True)


def worker(row):
    f.OUT = CONTROL
    f.schedule = schedule
    return f.run_case(row)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('prepare','run'))
    p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    if args.mode=='prepare':
        prepare()
        return
    f.OUT=CONTROL
    manifest=f.verify()
    with ProcessPoolExecutor(args.workers) as pool:
        futures=[pool.submit(worker,r) for r in manifest['cases']]
        for future in as_completed(futures):
            future.result()
    f.verify()


if __name__=='__main__':
    main()
