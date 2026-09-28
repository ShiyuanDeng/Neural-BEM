"""SPD-015: compare the native default with the explicit reference execution."""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import time

from experiments.spd014_geometry import run as base
from experiments.shape_continuation.forward import Work
from experiments.shape_continuation.geometry_runtime import geometry_mode
from experiments.shape_continuation.latest_video import load_renderer

MODULE = 'experiments.spd015_default_geometry.run'


@contextmanager
def native_arm(arm):
    """The combined arm exercises the real unset-environment default."""
    previous = os.environ.pop('SC_GEOMETRY_RUNTIME', None)
    if arm != 'both':
        os.environ['SC_GEOMETRY_RUNTIME'] = arm
    try:
        assert geometry_mode() == arm
        yield
    finally:
        os.environ.pop('SC_GEOMETRY_RUNTIME', None)
        if previous is not None:
            os.environ['SC_GEOMETRY_RUNTIME'] = previous


def batches(folder):
    from experiments.shape_continuation import atlas_strategy_tests as ast
    out = folder/'batches'
    out.mkdir(exist_ok=False)
    renderer = load_renderer()
    started, rows, units = time.perf_counter(), [], 0
    for case in base.CASES:
        curve, catalog = base.curves(case)['endpoint'], ast.catalog_only(case)
        tracks, _, _ = renderer.collect(case, 'fixed')
        nodes = tracks[1][-1]['nodes']
        for n in (nodes, 2*nodes):
            warm = Work(max_forwards=1, max_seconds=60)
            with native_arm('reference'):
                renderer.diagnostic(curve, catalog[:1], n, None, warm)
            units += warm.attempted+warm.jacobians
            expected = None
            for repeat in range(2):
                for arm in (base.ARMS if repeat == 0 else base.ARMS[::-1]):
                    if time.perf_counter()-started >= 1140 or units+2*len(catalog) > 30000:
                        raise TimeoutError('Diagnostic validation budget exhausted')
                    work = Work(max_forwards=len(catalog), max_seconds=60)
                    with native_arm(arm), base.checks() as counts:
                        tick = time.perf_counter()
                        data = renderer.diagnostic(curve, catalog, n, None, work)
                        seconds = time.perf_counter()-tick
                    units += work.attempted+work.jacobians
                    fingerprint = base.array_digest(data)
                    if expected is None:
                        expected = fingerprint
                    row = dict(case=case, nodes=n, repeat=repeat, arm=arm, seconds=seconds,
                               checks=counts, work=work.summary(), digest=fingerprint,
                               identical=fingerprint == expected)
                    rows.append(row)
                    base.write(out/'progress.json', dict(rows=rows, units=units))
                    print('BATCH', case, n, repeat, arm, round(seconds, 3), row['identical'], flush=True)
                    if not row['identical']:
                        raise AssertionError(row)
    sums = {a: sum(r['seconds'] for r in rows if r['arm'] == a) for a in base.ARMS}
    reduction = 1-sums['both']/sums['reference']
    base.write(out/'result.json', dict(passed=all(r['identical'] for r in rows) and reduction >= .2,
        rows=rows, units=units, sums_seconds=sums, reduction=reduction,
        seconds=time.perf_counter()-started, environment=base.environment()))
    base.verify(folder)


def inverse_worker(folder, out, case, arm):
    replay = base.load(base.REPLAY, 'spd015_archived_replay')
    module, manifest = replay.load_sc043(out)
    module.c.write(out/'manifest.json', manifest)
    # No SPD-014 audit/forecast monkeypatches: native Objective and fit scopes
    # provide the acceleration used by ordinary inverse callers.
    with native_arm(arm), base.checks() as counts:
        result = module.worker((case, 'fixed'))
    base.write(out/'geometry_checks.json', counts)
    if result.get('outcome') == 'EXCEPTION' or not result.get('audit_passed'):
        raise RuntimeError('Inverse worker did not qualify: '+repr(result))
    base.verify(folder)


def video_worker(folder, out, case, arm):
    (out/'prepared').mkdir(parents=True, exist_ok=False)
    with native_arm(arm), base.checks() as counts:
        load_renderer().prepare_case((case, 'fixed', str(out)))
    base.write(out/'geometry_checks.json', counts)
    base.verify(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('freeze', 'verify', 'geometry', 'batches', 'inverse', 'video',
                                        'inverse-worker', 'video-worker'))
    parser.add_argument('folder', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case', choices=base.CASES)
    parser.add_argument('--arm', choices=base.ARMS)
    args = parser.parse_args()
    folder = args.folder.resolve()
    if args.mode == 'freeze':
        base.freeze(folder, plan=base.ROOT/'docs/iterations/speedup/iteration_12/03_plan.md',
                    scope='SPD-015', extra_sources=Path(__file__).parent.glob('*.py'))
        return
    base.verify(folder)
    if args.mode in ('inverse-worker', 'video-worker'):
        if args.output is None or args.case is None or args.arm is None:
            parser.error('Workers require --output, --case and --arm')
        (inverse_worker if args.mode == 'inverse-worker' else video_worker)(
            folder, args.output.resolve(), args.case, args.arm)
    elif args.mode in ('inverse', 'video'):
        base.campaign(folder, args.mode, worker_module=MODULE)
    elif args.mode == 'geometry':
        base.geometry(folder)
    elif args.mode == 'batches':
        batches(folder)
    else:
        print('Frozen sources and inputs verified.', flush=True)


if __name__ == '__main__':
    main()
