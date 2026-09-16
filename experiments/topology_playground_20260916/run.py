"""Small, time-bounded topology experiments for the September 16 meeting."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import time
import traceback

import numpy as np

from experiments.top025 import run as pipeline
from sdf_inverse.runtime import inverse_execution, runtime_metadata
from sdf_inverse import runtime
from sdf_inverse import topology_controller as tc

p, m, suite, follow = pipeline.p, pipeline.m, pipeline.suite, pipeline.follow
SOURCE = pipeline.ROOT / 'results/validation/topology/TOP-025-20260915-210356-all-scenes-current'
write, read = pipeline.write, pipeline.read


@inverse_execution
def run(args):
    if args.true_jacobian:
        runtime.PROFILES['fast'] = replace(runtime.PROFILES['fast'], analytic_constraint_policy='true')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    initial, observed, evaluation, scene, spec = suite.load_scene(SOURCE, args.scene)
    if initial is not None and args.initial_modes:
        initial=tc.state_in_chart(initial,'cartesian')
        initial=p.MultiRadialFourierState(tuple(tc.zero_padded_component(c,args.initial_modes)
            if c.maximum_mode<args.initial_modes else c for c in initial.components))
    indices = [int(i) for i in args.frequencies.split(',')]
    frequencies = np.asarray(p.TRAIN)[indices]
    control = p.benchmark.controller_config(spec, 'H')
    overrides = json.loads(args.control)
    control = replace(control, **overrides)
    solve = p.driver.baseline.iteration01_solve_config()
    if args.training_ghz:
        frequencies = np.asarray(args.training_ghz)*1e9
        if any(np.isclose(f, p.EVALUATION, atol=1., rtol=0).any() for f in frequencies):
            raise ValueError('1.5 and 2.5 GHz remain evaluation-only')
        oracle_ledger = m.Ledger(cap=30, seconds=300)
        with oracle_ledger.instrument():
            oracle = {n:suite.screen.oracle(scene,frequencies,n,solve,oracle_ledger) for n in (256,512)}
        discrepancy = p.relative(oracle[256],oracle[512])
        if max(discrepancy)>1e-5:raise ValueError('new training oracle is not converged')
        write(output/'oracle.json',dict(frequencies_hz=frequencies,discrepancy=discrepancy,
            observed_real=oracle[512].real,observed_imag=oracle[512].imag,work=oracle_ledger.snapshot()))
        topology_data=p.ComplexScatteredData(p.driver.baseline._problem(frequencies),oracle[512],
            np.ones(len(frequencies))/len(frequencies))
    else:
        topology_data=p.training_data(frequencies, observed[:, indices])
    record = dict(scene=args.scene, frequencies_hz=frequencies, original_start=True,
                  controller=asdict(control), runtime=runtime_metadata(),
                  nodes=[args.nodes, args.refined], supplied_target_count=False,
                  seconds=args.seconds, source_bundle=str(SOURCE), command=vars(args).copy())
    record['command']['output'] = str(output)
    write(output/'config.json', record)
    # A circular seed has identical geometry after zero padding, but can then
    # deform before the controller decides whether another object is needed.
    if args.seed_modes:
        original_circle = tc.circle_component
        def flexible_circle(*positional, **kwargs):
            component = original_circle(*positional, **kwargs)
            return tc.zero_padded_component(component, args.seed_modes)
        tc.circle_component = flexible_circle
    ledger = follow.TopologyLedger(cap=args.cap, seconds=args.seconds)
    started = time.monotonic()
    state = initial
    try:
        def controller(initial, data, production, refined, **kwargs):
            return p.benchmark.run_topology_aware_fourier_inverse(initial, data,
                p.driver.baseline._geometry_config(args.nodes),
                p.driver.baseline._geometry_config(args.refined),
                feasibility_geometry_configs=tuple(p.driver.baseline._geometry_config(n)
                    for n in args.guard_nodes), **kwargs)
        with ledger.instrument():
            state = follow.topology_prefix(initial, topology_data,
                control, solve, ledger, output/'topology', controller=controller)
        record['status'] = 'TOPOLOGY_COMPLETE'
    except Exception as exc:
        record.update(status='STOPPED', reason=getattr(exc, 'code', type(exc).__name__),
                      detail=str(exc), traceback=traceback.format_exc())
        checkpoint = output/'topology/checkpoint.json'
        if checkpoint.exists():
            state = p.driver.deserialize_state(read(checkpoint)['state'])
    record['topology_seconds'] = time.monotonic()-started
    record['topology_work'] = ledger.snapshot()
    record['geometry'] = p.benchmark.geometry_metrics(state, scene, spec)
    record['continuation_feasible'] = state is not None and p.feasible(state, (256,512), solve, control.minimum_component_radius_m)
    write(output/'retained_state.json', p.driver.serialize_state(state))
    write(output/'result.json', record)
    if args.continue_fit and record['status']=='TOPOLOGY_COMPLETE' and record['continuation_feasible']:
        state, optimizer, capacity = suite.capacity_start(state, control, solve)
        record['capacity'] = capacity
        record['continuation'] = pipeline.run_continuation(output/'continuation', state, optimizer,
            observed, evaluation, scene, spec, control, solve)
    record['total_seconds'] = time.monotonic()-started
    write(output/'result.json', record)
    print(json.dumps({k:record[k] for k in ('scene','status','geometry','topology_seconds','continuation_feasible')},
        default=lambda x: x.tolist() if hasattr(x,'tolist') else str(x)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frequencies', default='0')
    parser.add_argument('--training-ghz',type=float,nargs='+')
    parser.add_argument('--nodes', type=int, default=64)
    parser.add_argument('--refined', type=int, default=128)
    parser.add_argument('--seconds', type=float, default=600)
    parser.add_argument('--cap', type=int, default=20000)
    parser.add_argument('--guard-nodes', type=int, nargs='*', default=[])
    parser.add_argument('--seed-modes', type=int, default=0)
    parser.add_argument('--initial-modes', type=int, default=0)
    parser.add_argument('--true-jacobian', action='store_true')
    parser.add_argument('--control', default='{}')
    parser.add_argument('--continue-fit', action='store_true')
    run(parser.parse_args())
