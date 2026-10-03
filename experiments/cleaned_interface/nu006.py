"""NU-006: the NU-005 update with its spectral ``prepare`` batched on the GPU.

``ProjectedUpdate.prepare`` builds 2(2M+1) + 2 independent projections of the accepted
curve: the base and fine-grid base projections and central differences (eps = 1e-7 m)
for every coordinate. NU-003/NU-005 run them one at a time on the CPU through
``spectral_project``. At K = 192, M = 37 that is 152 calls and about 2 s, mostly the
eq. 9 quadrature and the arclength basis of the same base curve recomputed each call.

``batched_projection`` evaluates the same mathematics for all steps at once in torch
float64: normal move on the uniform grid, FFT fit without the Nyquist mode, moved-curve
speed and normalised arclength, and the eq. 9 quadrature with e^{-ik alpha} evaluated
directly rather than by recurrence. Trials, validity tiers, LM, schedule and physics are
unchanged from NU-005. The arithmetic differs only by rounding, so the run is not
bit-identical; decision identity is measured.

    python -m experiments.cleaned_interface.nu006 precheck --output DIR
    python -m experiments.cleaned_interface.nu006 prepare --output CAMPAIGN
    python -m experiments.cleaned_interface.nu006 run --output CAMPAIGN --cases ...
    python -m experiments.cleaned_interface.nu006 drift --output DIR
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch

from experiments.shape_continuation.geometry import grid_size, normal_basis
from experiments.shape_continuation.updates import BorgesUpdate
from . import benchmark as b
from . import runner
from .geometry import ProjectedSpace
from .io import read, write, curve_from, portable
from .modal_muller import register
from .n_update_audit import ArmPolicy, CORE, case_drift, relative_columns
from .nu003 import BASE, CONSTRUCTION, decide, identity
from .nu005 import ROOT, SOLVER, CertifiedSpace, CertifiedSpectralUpdate, tier_counts
from .policy import CumulativePolicy
from .physics import Execution
from bem_inverse.batched import (
    CHUNK_BYTES, batched_projection, BatchedCertifiedUpdate,
)


# --------------------------------------------------------------------------- pre-check

def precheck(output, source=BASE/'NU-005/runs', unit=.05):
    rows = []
    for case in CORE:
        last = {}
        for state in read(Path(source)/case/'accepted.json')['states']:
            last[state['stage']] = state
        for stage, state in last.items():
            curve = curve_from(state['curve'])
            cpu, gpu = CertifiedSpectralUpdate(unit), BatchedCertifiedUpdate(unit)
            t0 = time.perf_counter(); a = cpu.prepare(curve, state['M'], curve.band); tc = time.perf_counter()-t0
            gpu.prepare(curve, state['M'], curve.band)
            if gpu.device == 'cuda':
                torch.cuda.synchronize()
            t0 = time.perf_counter(); g = gpu.prepare(curve, state['M'], curve.band); tg = time.perf_counter()-t0
            radius = curve.nodes(a.count).perimeter/(2*np.pi)
            columns = relative_columns(g.derivatives, a.derivatives)
            row = dict(case=case, stage=stage, K=curve.band, M=state['M'], count=a.count,
                       column_relative_max=float(np.max(columns)),
                       base_relative=float(np.max(np.abs(g.base_projection-a.base_projection)))/radius,
                       fine_relative=float(np.max(np.abs(g.fine_base_projection-a.fine_base_projection)))/radius,
                       seconds=dict(cpu=tc, batched=tg), fallbacks=gpu.counts['prepare_fallbacks'])
            rows.append(row)
            print(case, stage, 'K', row['K'], 'M', row['M'], 'col %.1e' % row['column_relative_max'],
                  'base %.1e' % row['base_relative'], 'cpu %.3f gpu %.4f' % (tc, tg), flush=True)
    gates = dict(columns_within_decision_neutral=max(r['column_relative_max'] for r in rows) <= 1e-7,
                 base_projections_at_roundoff=max(max(r['base_relative'], r['fine_relative']) for r in rows) <= 1e-12,
                 no_fallback=all(r['fallbacks'] == 0 for r in rows))
    result = dict(experiment='NU-006 pre-check', source=str(Path(source).relative_to(ROOT)), states=len(rows),
                  worst=dict(column_relative=max(r['column_relative_max'] for r in rows),
                             base_relative=max(max(r['base_relative'], r['fine_relative']) for r in rows)),
                  seconds=dict(cpu=float(sum(r['seconds']['cpu'] for r in rows)),
                               batched=float(sum(r['seconds']['batched'] for r in rows))),
                  device=BatchedCertifiedUpdate(unit).device, gates=gates, passed=all(gates.values()), rows=rows)
    write(Path(output)/'precheck.json', result)
    return {k: v for k, v in result.items() if k != 'rows'}


# --------------------------------------------------------------------------- campaign

@contextmanager
def substitution():
    saved = runner.ProjectedUpdate, runner.CumulativePolicy
    runner.ProjectedUpdate = BatchedCertifiedUpdate
    runner.CumulativePolicy = lambda: ArmPolicy(geometry_update=CONSTRUCTION)
    try:
        yield
    finally:
        runner.ProjectedUpdate, runner.CumulativePolicy = saved


def prepare(output):
    output = Path(output)
    value = b.prepare(output)
    b.augment(output, None, allow_new_damped_data=True, reuse_from=BASE/'CI-001')
    write(output/'arm.json', dict(experiment='NU-006', arm='MG', solver=SOLVER, update='BatchedCertifiedUpdate',
        construction=CONSTRUCTION, update_settings=BatchedCertifiedUpdate(.05).settings(), cases=list(CORE),
        policy_changes=dict(fit_seconds=[CumulativePolicy.fit_seconds, ArmPolicy.fit_seconds],
                            audit_seconds=[CumulativePolicy.audit_seconds, ArmPolicy.audit_seconds],
                            reason='identical to the NU-001 to NU-005 arms; unit caps unchanged')))
    return value


def run(output, execution, cases):
    register()
    with substitution():
        return b.run(output, execution, solver=SOLVER, workers=1, cases=cases)


def report(output):
    register()
    return b.report(output)


def drift(output, nodal=BASE/'CI-001', reference=BASE/'NU-005', arm=BASE/'NU-006', certificate=True):
    out = dict(experiment='NU-006 drift, decision and identity audit', arms={})
    for name, campaign in (('nodal', Path(nodal)), ('MC', Path(reference)), ('MG', Path(arm))):
        comparison = read(campaign/'comparison.json') if (campaign/'comparison.json').exists() else dict(rows=[])
        status = {r['id']: r['status'] for r in comparison['rows'] if r['id'] in CORE}
        cases = {}
        for case in CORE:
            folder = campaign/'runs'/case
            if (folder/'result.json').exists():
                cases[case] = case_drift(folder, certificate)
                if name == 'MG':
                    cases[case]['identity_vs_MC'] = identity(Path(reference)/'runs'/case, folder)
                    cases[case]['identity_vs_nodal'] = identity(Path(nodal)/'runs'/case, folder)
                    cases[case]['validity'] = tier_counts(folder)
                print(name, case, 'max r', round(cases[case]['max_speed_ratio'], 4), cases[case]['outcome'], flush=True)
        out['arms'][name] = dict(campaign=str(campaign.resolve().relative_to(ROOT)), status=status, cases=cases)
    if all(len(out['arms'][a]['cases']) == len(CORE) for a in ('nodal', 'MC', 'MG')):
        rule = decide(out['arms']['nodal'], out['arms']['MG'])
        rule.pop('outcome')
        table = out['arms']['MG']['cases']
        units = {c: [read(Path(a)/'runs'/c/'result.json')['total_units'] for a in (reference, arm)] for c in CORE}
        identical = all(table[c]['identity_vs_MC']['same_accepted_steps'] and units[c][0] == units[c][1] for c in CORE)
        seconds = {name: {key: float(sum(read(Path(a)/'runs'/c/'result.json')[field] if field == 'total_seconds'
                                         else read(Path(a)/'runs'/c/'result.json')['geometry_work'][field] for c in CORE))
                          for key, field in (('wall', 'total_seconds'), ('preparation', 'preparation_seconds'))}
                   for name, a in (('MC', reference), ('MG', arm))}
        out['decision'] = dict(rule, decision_identical_to_MC=identical, units=units, seconds=seconds,
                               retained=rule['qualifies'],
                               default=rule['qualifies'] and identical,
                               outcome=('not retained' if not rule['qualifies'] else
                                        'retained and decision-identical: adopt as the default prepare'
                                        if identical else 'retained, not decision-identical'))
    write(Path(output)/'drift.json', out)
    return out.get('decision', 'incomplete')


def main(argv=None):
    parser = argparse.ArgumentParser(description='NU-006 GPU-batched spectral prepare')
    parser.add_argument('command', choices=('precheck', 'prepare', 'run', 'report', 'drift'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', default=list(CORE))
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--frequency-threads', type=int, default=4)
    args = parser.parse_args(argv)
    if args.command == 'precheck':
        value = precheck(args.output)
    elif args.command == 'prepare':
        value = prepare(args.output)
    elif args.command == 'run':
        value = run(args.output, Execution(args.device, args.frequency_threads), args.cases)
    elif args.command == 'report':
        value = report(args.output)
    else:
        value = drift(args.output)
    print(json.dumps(portable(value), indent=2))


if __name__ == '__main__':
    main(sys.argv[1:])
