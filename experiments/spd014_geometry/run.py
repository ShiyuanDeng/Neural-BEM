"""SPD-014 qualification and matched replays; never overwrites an evidence folder."""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import threading
import time

import numpy as np

from .runtime import ARMS, cache_diagnostic, geometry_acceleration

ROOT = Path(__file__).resolve().parents[2]
SPD = ROOT / 'results/validation/speedup'
SC = ROOT / 'results/validation/shape_continuation'
ARCHIVE = SC / 'SC-043-prospective-band'
CASES = ('wrong_circle', 'circle_to_star', 'circle_to_c', 'kite', 'peanut', 'hook')
REPLAY = SPD / 'SPD-010-20260927-frequency-threads/replay.py'
RENDER = SC / 'videos/latest_vs_hybrid/render.py'
FILES = ('decisions.json', 'accepted.json', 'block_1.json', 'block_2.json', 'block_3.json',
         'checkpoint.json', 'audit.json', 'result.json', 'progress.json')


def plain(value):
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, complex):
        return [value.real, value.imag]
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(plain(value), indent=1, allow_nan=False)+'\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def environment():
    try:
        gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu',
                                       '--format=csv,noheader'], text=True, timeout=10).strip()
    except (OSError, subprocess.SubprocessError):
        gpu = 'unavailable'
    return dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                dirty_tracked_files=subprocess.check_output(
                    ['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).splitlines(),
                host=platform.node(), python=sys.version, cpus=os.cpu_count(), load=os.getloadavg(),
                gpu=gpu, numpy=np.__version__,
                env={k: os.environ.get(k) for k in ('SC_FORWARD_BACKEND', 'SC_FREQUENCY_THREADS', 'SC_GEOMETRY_RUNTIME',
                     'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')},
                processes=subprocess.check_output(['ps', '-eo', 'pid,ppid,pcpu,comm'], text=True))


def freeze(folder, *, plan=None, scope='SPD-014', extra_sources=()):
    folder.mkdir(parents=True, exist_ok=False)
    paths = set()
    for root in ('solvers/ordered_boundary', 'solvers/gpr_bem_kress',
                 'experiments/shape_continuation', 'experiments/spd014_geometry'):
        paths.update((ROOT/root).rglob('*.py'))
    archived = read(ARCHIVE/'manifest.json')
    paths.update(ROOT/p for p in archived['sources'] if (ROOT/p).is_file())
    paths.update((REPLAY, RENDER, ROOT/'pytest/ordered_boundary/test_spd014.py'))
    paths.update(extra_sources)
    plan = plan or ROOT/'docs/iterations/speedup/iteration_10/03_spd014_plan.md'
    (folder/'approved_plan.md').write_bytes(plan.read_bytes())
    inputs = dict(archived['inputs'])
    for case in CASES:
        for name in ('decisions.json', 'accepted.json', 'result.json'):
            p = ARCHIVE/'runs'/case/'fixed'/name
            inputs[str(p.relative_to(ROOT))] = digest(p)
        prepared = read(SC/'videos/latest_vs_hybrid/prepared'/f'{case}.json')
        for key in ('sources', 'raw_shots'):
            for p in prepared[key]:
                inputs[p] = digest(ROOT/p)
    with tarfile.open(folder/'sources.tar.gz', 'w:gz') as archive:
        for p in sorted(paths):
            archive.add(p, arcname=str(p.relative_to(ROOT)), recursive=False)
    write(folder/'manifest.json', dict(sources={str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)},
         inputs=inputs, environment=environment(), approved_scope=scope,
         plan_sha256=digest(folder/'approved_plan.md'), source_archive_sha256=digest(folder/'sources.tar.gz'),
         created=time.time()))


def verify(folder):
    manifest = read(folder/'manifest.json')
    if digest(folder/'approved_plan.md') != manifest['plan_sha256']:
        raise RuntimeError('Frozen approval contract changed')
    if digest(folder/'sources.tar.gz') != manifest['source_archive_sha256']:
        raise RuntimeError('Frozen source archive changed')
    for kind in ('sources', 'inputs'):
        changed = [p for p, h in manifest[kind].items() if digest(ROOT/p) != h]
        if changed:
            raise RuntimeError('Frozen '+kind+' changed: '+repr(changed))


def strip_timing(value):
    if isinstance(value, dict):
        return {k: strip_timing(v) for k, v in value.items() if k != 'seconds'}
    if isinstance(value, list):
        return [strip_timing(v) for v in value]
    return value


def array_digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, allow_nan=False).encode()).hexdigest()


@contextmanager
def checks():
    """Count executed predicates, outside memoization; timers may be nested/threaded."""
    from ordered_boundary import validation
    names = ('_dense_self_intersection_count', 'spatial_self_intersection_count')
    originals = {name: getattr(validation, name) for name in names}
    lock, stats = threading.Lock(), {}
    for name, original in originals.items():
        stats[name] = dict(calls=0, seconds=0.)
        def wrapped(*args, _name=name, _original=original, **kwargs):
            started = time.perf_counter()
            try:
                return _original(*args, **kwargs)
            finally:
                with lock:
                    stats[_name]['calls'] += 1
                    stats[_name]['seconds'] += time.perf_counter()-started
        setattr(validation, name, wrapped)
    try:
        yield stats
    finally:
        for name, original in originals.items():
            setattr(validation, name, original)


def curves(case):
    from experiments.shape_continuation.atlas_strategy_tests import curve_from
    decisions = read(ARCHIVE/'runs'/case/'fixed/decisions.json')
    result = read(ARCHIVE/'runs'/case/'fixed/result.json')
    return dict(start=curve_from(decisions['rows'][0]['curve_before_fit']), endpoint=curve_from(result['curve']))


def geometry(folder):
    from ordered_boundary import sampled_self_intersection_count
    from ordered_boundary.spatial_validation import _candidate_pairs
    out = folder/'geometry'
    out.mkdir(exist_ok=False)
    started, rows = time.perf_counter(), []
    for case in CASES:
        for label, curve in curves(case).items():
            for n in (256, 512, 1024, 2048):
                if n <= 2*curve.band:
                    continue
                if time.perf_counter()-started > 890:
                    raise TimeoutError('Geometry screen budget exhausted')
                points = curve.nodes(n).points
                scale = np.linalg.norm(np.ptp(points, axis=0))
                pairs = _candidate_pairs(points, 1e-12*scale)
                timing = {arm: [] for arm in ('reference', 'spatial')}
                counts = {}
                for repeat in range(2):
                    for arm in (('reference', 'spatial') if repeat == 0 else ('spatial', 'reference')):
                        with geometry_acceleration(arm):
                            tick = time.perf_counter()
                            counts[arm] = sampled_self_intersection_count(points)
                            timing[arm].append(time.perf_counter()-tick)
                row = dict(case=case, state=label, nodes=n, counts=counts, seconds=timing,
                           candidate_pairs=None if pairs is None else len(pairs),
                           possible_nonadjacent_pairs=n*(n-3)//2,
                           speedup=np.median(timing['reference'])/np.median(timing['spatial']),
                           passed=counts['reference'] == counts['spatial'])
                rows.append(row)
                write(out/'progress.json', dict(rows=rows))
                if not row['passed']:
                    raise AssertionError(row)
    med = float(np.median([r['speedup'] for r in rows if r['nodes'] >= 512]))
    write(out/'result.json', dict(passed=all(r['passed'] for r in rows) and med >= 2,
          median_speedup=med, rows=rows, seconds=time.perf_counter()-started, environment=environment()))
    verify(folder)


def batches(folder):
    from experiments.shape_continuation import atlas_strategy_tests as ast
    from experiments.shape_continuation.forward import Work
    out = folder/'batches'
    out.mkdir(exist_ok=False)
    renderer = load(RENDER, 'spd014_batch_renderer')
    diagnostic = cache_diagnostic(renderer.diagnostic)
    started, rows, units = time.perf_counter(), [], 0
    for case in CASES:
        curve, catalog = curves(case)['endpoint'], ast.catalog_only(case)
        tracks, _, _ = renderer.collect(case, 'fixed')
        base_nodes = tracks[1][-1]['nodes']
        for n in (base_nodes, 2*base_nodes):
            # Warm one frequency at this resolution outside the timed arms;
            # charge its forward and reciprocal units separately.
            warmup = Work(max_forwards=1, max_seconds=60)
            if time.perf_counter()-started >= 1140 or units+2 > 30000:
                raise TimeoutError('Four-arm screen budget exhausted before warmup')
            with geometry_acceleration('reference'):
                diagnostic(curve, catalog[:1], n, None, warmup)
            units += warmup.attempted+warmup.jacobians
            expected = None
            for repeat in range(2):
                for arm in (ARMS if repeat == 0 else ARMS[::-1]):
                    if time.perf_counter()-started >= 1140 or units+2*len(catalog) > 30000:
                        raise TimeoutError('Four-arm screen budget exhausted before next batch')
                    work = Work(max_forwards=len(catalog), max_seconds=60)
                    with checks() as counts, geometry_acceleration(arm):
                        tick = time.perf_counter()
                        data = diagnostic(curve, catalog, n, None, work)
                        seconds = time.perf_counter()-tick
                    units += work.attempted+work.jacobians
                    fingerprint = array_digest(data)
                    if expected is None:
                        expected = fingerprint
                    row = dict(case=case, nodes=n, repeat=repeat, arm=arm, seconds=seconds,
                               checks=counts, work=work.summary(), digest=fingerprint,
                               identical=fingerprint == expected)
                    rows.append(row)
                    write(out/'progress.json', dict(rows=rows, units=units))
                    print('BATCH', case, n, repeat, arm, round(seconds, 3), row['identical'], flush=True)
                    if not row['identical']:
                        raise AssertionError('Diagnostic numerical regression: '+repr(row))
    sums = {arm: sum(r['seconds'] for r in rows if r['arm'] == arm) for arm in ARMS}
    reduction = 1-sums['both']/sums['reference']
    write(out/'result.json', dict(passed=all(r['identical'] for r in rows) and reduction >= .2,
          sums_seconds=sums, reduction=reduction, rows=rows, units=units,
          warmup_units=2*2*len(CASES),
          seconds=time.perf_counter()-started, environment=environment(),
          timer_note='Geometry timers may be nested; do not sum dense and spatial fallback time.'))
    verify(folder)


def inverse_worker(folder, out, case, arm):
    replay = load(REPLAY, 'spd014_archived_replay')
    module, manifest = replay.load_sc043(out)
    module.c.write(out/'manifest.json', manifest)
    module.c.audit = cache_diagnostic(module.c.audit)
    module.forecast = cache_diagnostic(module.forecast)
    with geometry_acceleration(arm), checks() as counts:
        result = module.worker((case, 'fixed'))
    write(out/'geometry_checks.json', counts)
    if result.get('outcome') == 'EXCEPTION' or not result.get('audit_passed'):
        raise RuntimeError('Inverse worker did not qualify: '+repr(result))
    verify(folder)


def video_worker(folder, out, case, arm):
    renderer = load(RENDER, 'spd014_video_renderer')
    renderer.diagnostic = cache_diagnostic(renderer.diagnostic)
    (out/'prepared').mkdir(parents=True, exist_ok=False)
    with geometry_acceleration(arm), checks() as counts:
        renderer.prepare_case((case, 'fixed', str(out)))
    write(out/'geometry_checks.json', counts)
    verify(folder)


def compare_inverse(first, second, case):
    rows = {}
    for name in FILES:
        a, b = [read(p/'runs'/case/'fixed'/name) for p in (first, second)]
        rows[name] = strip_timing(a) == strip_timing(b)
    return dict(passed=all(rows.values()), files=rows)


def compare_video(first, second, case):
    a, b = [read(p/'prepared'/f'{case}.json') for p in (first, second)]
    # Sources, raw-shot hashes, renderer signatures, work counts and every
    # displayed field are compared; only measured times may differ.
    equal = strip_timing(a) == strip_timing(b)
    return dict(passed=equal, all_non_timing_equal=equal)


def campaign(folder, kind, *, worker_module='experiments.spd014_geometry.run'):
    for prerequisite in ('geometry', 'batches'):
        if not read(folder/prerequisite/'result.json')['passed']:
            raise RuntimeError(prerequisite+' qualification failed')
    out = folder/kind
    out.mkdir(exist_ok=False)
    started, rows, units = time.perf_counter(), [], 0
    cap = 25000 if kind == 'inverse' else 12000
    # Case-bound reservations derived from frozen SPD-011 work. A child timeout
    # enforces the total wall ceiling even if its historical driver catches stops.
    video_units = {c: 2*r['gpu_work']['completed'] for c, r in
                   read(SPD/'SPD-011-20260927-cuda-assembly/video_gate.json')['cases'].items()}
    for index, case in enumerate(CASES):
        arms = ('reference', 'both') if index % 2 == 0 else ('both', 'reference')
        outputs = {}
        for arm in arms:
            verify(folder)
            expected = (read(ARCHIVE/'runs'/case/'fixed/result.json')['total_units']+114
                        if kind == 'inverse' else video_units[case])
            remaining = 3600-(time.perf_counter()-started)
            if remaining <= 0 or units+expected > cap:
                raise TimeoutError('Campaign budget exhausted before '+case+'/'+arm)
            dest = out/case/arm
            dest.mkdir(parents=True, exist_ok=False)
            command = [sys.executable, '-m', worker_module, kind+'-worker',
                       str(folder), '--output', str(dest), '--case', case, '--arm', arm]
            write(dest/'command.json', dict(command=command, environment=environment(), reserve_units=expected))
            with (dest/'run.log').open('w') as log:
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=remaining)
            if kind == 'inverse':
                result = read(dest/'runs'/case/'fixed/result.json')
                cost, seconds = result['total_units']+result['audit_units'], result['seconds']
            else:
                result = read(dest/'prepared'/f'{case}.json')
                work = result['diagnostic_work']
                cost, seconds = work['attempted']+work['jacobians'], result['seconds']
            units += cost
            outputs[arm] = dest
            rows.append(dict(case=case, arm=arm, seconds=seconds, units=cost,
                             checks=read(dest/'geometry_checks.json')))
            write(out/'progress.json', dict(rows=rows, units=units))
            print(kind.upper(), case, arm, round(seconds, 3), 'units', cost, flush=True)
        comparison = (compare_inverse if kind == 'inverse' else compare_video)(
            outputs['reference'], outputs['both'], case)
        write(out/case/'comparison.json', comparison)
        if not comparison['passed']:
            raise AssertionError(kind+' comparison failed: '+case)
    write(out/'result.json', dict(passed=True, rows=rows, units=units,
         seconds=time.perf_counter()-started, environment=environment()))
    verify(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('freeze', 'geometry', 'batches', 'inverse', 'video',
                                        'inverse-worker', 'video-worker'))
    parser.add_argument('folder', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--arm', choices=ARMS)
    args = parser.parse_args()
    folder = args.folder.resolve()
    if args.mode == 'freeze':
        freeze(folder)
        return
    verify(folder)
    if args.mode in ('inverse-worker', 'video-worker'):
        if args.output is None or args.case is None or args.arm is None:
            parser.error('workers require --output, --case and --arm')
        (inverse_worker if args.mode == 'inverse-worker' else video_worker)(
            folder, args.output.resolve(), args.case, args.arm)
    elif args.mode in ('inverse', 'video'):
        campaign(folder, args.mode)
    else:
        (geometry if args.mode == 'geometry' else batches)(folder)


if __name__ == '__main__':
    main()
