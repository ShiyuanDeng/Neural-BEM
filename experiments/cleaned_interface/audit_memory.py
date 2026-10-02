"""Isolated single-curve peak-RSS evidence for equivalent audit implementations."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
import argparse
from pathlib import Path
import resource
from time import perf_counter
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage
from .geometry import ProjectedUpdate
from .io import write
from .physics import Execution, NodalKress
from .runner import audit
from .test_audit_streaming import fixture, reference_dense_audit


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--method', choices=['dense', 'streamed'], required=True)
    parser.add_argument('--nodes', type=int, default=512)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    p = fixture()
    physics = NodalKress(Execution(device='cpu', frequency_threads=1))
    stage = FitStage('memory_audit', p.real, (.2,)*5, (1e-5,)*3+(1e-7,)*2, 3, 8, args.nodes, 2*args.nodes, 1)
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = perf_counter()
    result = (reference_dense_audit if args.method=='dense' else audit)(
        p.initial, stage, BackendConfig(), p, physics, ProjectedUpdate(.05), 900.)
    elapsed = perf_counter()-started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write(args.output, dict(method=args.method, single_curve=True, frequencies=5,
        nodes=[args.nodes, 2*args.nodes], baseline_max_rss_kib=baseline, peak_rss_kib=peak,
        incremental_peak_kib=peak-baseline, seconds=elapsed, audit=result,
        memory_measurement='Linux getrusage(RUSAGE_SELF).ru_maxrss in a fresh process; includes interpreter/import baseline',
        physics=physics.receipt()))
    print(f'{args.method}: {peak/1024:.1f} MiB peak, {elapsed:.3f} seconds', flush=True)


if __name__ == '__main__': main()
