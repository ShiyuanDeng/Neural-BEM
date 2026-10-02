"""NU-004: modal Müller physics with the NU-003 spline-free increment map (six core cases).

Arms (both with ``solver='modal_muller'``, NU-001's ArmPolicy, unchanged schedule):
  MS  SpectralProjectedUpdate (NU-003)            decisive arm
  MN  ProjectedUpdate (CI-001 spline resampler)   attribution control
The nodal reference is the archived CI-001 campaign (nodal_kress + ProjectedUpdate).

    python -m experiments.cleaned_interface.nu004 prepare --arm MS --output CAMPAIGN
    python -m experiments.cleaned_interface.nu004 run --output CAMPAIGN --cases ...
    python -m experiments.cleaned_interface.nu004 drift --output DIR
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys

from . import benchmark as b
from . import runner
from .geometry import ProjectedUpdate
from .io import read, write, portable
from .modal_muller import register
from .n_update_audit import ARMS as NU001_ARMS, ArmPolicy, CORE, case_drift
from .nu003 import BASE, CONSTRUCTION, SpectralProjectedUpdate, decide, identity
from .physics import Execution
from .policy import CumulativePolicy

ROOT = b.ROOT
ARMS = dict(
    MS=dict(update=SpectralProjectedUpdate, construction=CONSTRUCTION),
    MN=dict(update=ProjectedUpdate, construction=NU001_ARMS['nodal']['construction']))
SOLVER = 'modal_muller'


@contextmanager
def substitution(arm):
    saved = runner.ProjectedUpdate, runner.CumulativePolicy
    runner.ProjectedUpdate = ARMS[arm]['update']
    runner.CumulativePolicy = lambda: ArmPolicy(geometry_update=ARMS[arm]['construction'])
    try:
        yield
    finally:
        runner.ProjectedUpdate, runner.CumulativePolicy = saved


def prepare(output, arm):
    output = Path(output)
    value = b.prepare(output)
    b.augment(output, None, allow_new_damped_data=True, reuse_from=BASE/'CI-001')
    write(output/'arm.json', dict(experiment='NU-004', arm=arm, solver=SOLVER,
        update=ARMS[arm]['update'].__name__, construction=ARMS[arm]['construction'],
        update_settings=ARMS[arm]['update'](.05).settings(), cases=list(CORE),
        policy_changes=dict(fit_seconds=[CumulativePolicy.fit_seconds, ArmPolicy.fit_seconds],
                            audit_seconds=[CumulativePolicy.audit_seconds, ArmPolicy.audit_seconds],
                            reason='identical to NU-001 and NU-003 arms; unit caps unchanged')))
    return dict(value, arm=arm)


def run(output, execution, cases):
    register()
    arm = read(Path(output)/'arm.json')['arm']
    with substitution(arm):
        return b.run(output, execution, solver=SOLVER, workers=1, cases=cases)


def report(output):
    register()
    return b.report(output)


def drift(output, nodal=BASE/'CI-001', ms=BASE/'NU-004-MS', mn=BASE/'NU-004-MN', certificate=True):
    out = dict(experiment='NU-004 drift audit', arms={})
    for name, campaign in (('nodal', Path(nodal)), ('MS', Path(ms)), ('MN', Path(mn))):
        comparison = read(campaign/'comparison.json') if (campaign/'comparison.json').exists() else dict(rows=[])
        status = {r['id']: r['status'] for r in comparison['rows'] if r['id'] in CORE}
        cases = {}
        for case in CORE:
            folder = campaign/'runs'/case
            if (folder/'accepted.json').exists():
                cases[case] = case_drift(folder, certificate)
                if name != 'nodal':
                    cases[case]['identity_vs_nodal'] = identity(Path(nodal)/'runs'/case, folder)
                if name == 'MS' and (Path(mn)/'runs'/case/'accepted.json').exists():
                    cases[case]['identity_vs_MN'] = identity(Path(mn)/'runs'/case, folder)
                print(name, case, 'max r', round(cases[case]['max_speed_ratio'], 4), cases[case]['outcome'], flush=True)
        out['arms'][name] = dict(campaign=str(campaign.resolve().relative_to(ROOT)), status=status, cases=cases)
    complete = {a: len(out['arms'][a]['cases']) == len(CORE) for a in out['arms']}
    if complete['nodal'] and complete['MS']:
        out['decision'] = decide(out['arms']['nodal'], out['arms']['MS'])
        out['decision']['outcome'] = ('node-free physics with the spline-free map retains nodal on the six core cases'
                                      if out['decision']['qualifies'] else 'not retained')
    if complete['nodal'] and complete['MN']:
        out['control'] = decide(out['arms']['nodal'], out['arms']['MN'])
        out['control'].pop('outcome')
    write(Path(output)/'drift.json', out)
    return dict(decision=out.get('decision', 'incomplete'), control=out.get('control', 'incomplete'))


def main(argv=None):
    parser = argparse.ArgumentParser(description='NU-004 modal Müller + spline-free increment map')
    parser.add_argument('command', choices=('prepare', 'run', 'report', 'drift'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arm', choices=tuple(ARMS))
    parser.add_argument('--cases', nargs='+', default=list(CORE))
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--frequency-threads', type=int, default=4)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        if args.arm is None:
            parser.error('prepare requires --arm')
        value = prepare(args.output, args.arm)
    elif args.command == 'run':
        value = run(args.output, Execution(args.device, args.frequency_threads), args.cases)
    elif args.command == 'report':
        value = report(args.output)
    else:
        value = drift(args.output)
    print(json.dumps(portable(value), indent=2))


if __name__ == '__main__':
    main(sys.argv[1:])
