"""python -m experiments.benchmark {prepare,generate,verify,inventory,figure,plan,run} (repository root, PYTHONPATH=solvers:.)"""
import argparse
import json
from pathlib import Path

from bem_inverse.io import portable
from bem_inverse.physics import Execution
from . import campaign as c, scenes as S


def main():
    parser = argparse.ArgumentParser(description='TG-002 benchmark: inputs, plans and fits')
    parser.add_argument('command', choices=('prepare', 'generate', 'verify', 'inventory', 'figure', 'plan', 'run'))
    parser.add_argument('--cases', nargs='+', help=f'case IDs, e.g. {S.CASES[0]}; "all" for every case')
    parser.add_argument('--run-dir', type=Path, help='fresh directory for fits (run only)')
    parser.add_argument('--solver', default='modal_muller', choices=('modal_muller', 'nodal_kress'))
    parser.add_argument('--geometry-update', default='certified_spectral',
                        choices=('spline', 'spectral', 'certified_spectral', 'analytic_spectral'))
    parser.add_argument('--localization', default='none', choices=c.LOCALIZATION,
                        help='none (default): keep the centred start; grid: legacy SC-050 disk search')
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--frequency-threads', type=int, default=4)
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    execution = Execution(args.device, args.frequency_threads)
    cases = list(S.CASES) if args.cases in (None, ['all']) else args.cases
    if args.command == 'prepare':
        value = c.prepare()
    elif args.command == 'generate':
        value = c.generate()  # always the CPU reference path
    elif args.command == 'verify':
        m = c.verify(require_inputs=True)
        value = dict(verified=True, sealed=m['inputs_sealed'], cases=len(c.descriptors()))
    elif args.command == 'inventory':
        value = [dict(id=r['id'], scene=r['case'], contrast=r['contrast']) for r in c.descriptors()]
    elif args.command == 'figure':
        value = c.figure()
    elif args.command == 'plan':
        from bem_inverse.policy import CumulativePolicy, readable_plan
        from bem_inverse.geometry_selection import make_update, describe_plan
        problem = c.problem(cases[0])
        plan = CumulativePolicy().plan(problem, c._physics(args.solver, execution))
        plan = describe_plan(plan, make_update(args.geometry_update, problem.length_unit_m, execution).settings(),
                             override_operations=True)
        print(readable_plan(plan))
        if args.localization == 'none':
            print('\nNOTE: --localization none replaces operation "damped_localization" with keep_start '
                  '(no grid search); the 0.25 GHz warm-up then moves the start circle.')
        return
    else:
        if not args.run_dir:
            parser.error('run needs --run-dir (a fresh directory per setting)')
        value = c.run(args.run_dir, cases, solver=args.solver, geometry_update=args.geometry_update,
                      localization=args.localization, execution=execution, workers=args.workers)
    print(json.dumps(portable(value), indent=2))


if __name__ == '__main__':
    main()
