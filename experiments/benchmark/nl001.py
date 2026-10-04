"""NL-001 (pre-registered, NOT yet approved to run): is the grid search needed?

All 30 TG-002 cases, node-free configuration (modal Müller physics,
certified spectral geometry update), default CumulativePolicy otherwise.
Arm A skips the grid localization (centred start kept); arm B is the matched
control with the legacy SC-050 grid search. Plan and predictions:
docs/iterations/cleaned_interfaces/iteration_26/03_plan.md.

    python -m experiments.benchmark.nl001 run --arm A
    python -m experiments.benchmark.nl001 run --arm B
    python -m experiments.benchmark.nl001 report
"""
import argparse
import json

from bem_inverse.io import read, write, portable
from bem_inverse.physics import Execution
from . import campaign as c, scenes as S

OUTPUT = c.ROOT/'results/validation/cleaned_interfaces/NL-001'
COMMON = dict(solver='modal_muller', geometry_update='certified_spectral')
ARMS = dict(A=dict(COMMON, localization='none'), B=dict(COMMON, localization='grid'))
EXECUTION = Execution(device='auto', frequency_threads=4)
WORKERS = 2


def run(arm):
    return c.run(OUTPUT/arm, S.CASES, execution=EXECUTION, workers=WORKERS, experiment='NL-001 arm '+arm, **ARMS[arm])


def report():
    arms = {arm: {r['id']: r for r in read(OUTPUT/arm/'summary.json')['rows']}
            for arm in ARMS if (OUTPUT/arm/'summary.json').exists()}
    rows = []
    for case in S.CASES:
        scene, tag = case.rsplit('__', 1)
        rows.append(dict(id=case, scene=scene, contrast=tag,
                         **{f'{arm}_recovered': arms[arm].get(case, {}).get('recovered') for arm in arms},
                         **{f'{arm}_rms_mm': arms[arm].get(case, {}).get('rms_mm') for arm in arms},
                         **{f'{arm}_seconds': arms[arm].get(case, {}).get('seconds') for arm in arms}))
    count = {arm: {S.tag(k): sum(bool(r.get(f'{arm}_recovered')) for r in rows if r['contrast'] == S.tag(k))
                   for k in S.CONTRASTS} for arm in arms}
    value = dict(arms=ARMS, recovered_by_contrast=count, rows=rows,
                 complete={arm: len(arms[arm]) == len(S.CASES) for arm in arms})
    write(OUTPUT/'report.json', value)
    return {k: v for k, v in value.items() if k != 'rows'}


def main():
    parser = argparse.ArgumentParser(description='NL-001: TG-002 with and without grid localization')
    parser.add_argument('command', choices=('run', 'report'))
    parser.add_argument('--arm', choices=tuple(ARMS))
    args = parser.parse_args()
    if args.command == 'run':
        if not args.arm:
            parser.error('run needs --arm')
        value = run(args.arm)
    else:
        value = report()
    print(json.dumps(portable(value), indent=2))


if __name__ == '__main__':
    main()
