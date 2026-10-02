"""NU-005 drift, decision and tier audit.

``nu005.drift`` reused the name ``mc`` for the campaign path and the case table, so
it fails after the case audits. ``nu005.py`` is hashed by the NU-005 campaign seal and
cannot be edited, so this module carries the same audit with the names separated.
The rule is unchanged (iteration 13 plan).

    python -m experiments.cleaned_interface.nu005_drift --output DIR
"""
import argparse
import json
from pathlib import Path
import sys

from .io import read, write, portable
from .n_update_audit import CORE, case_drift
from .nu003 import BASE, decide, identity
from .nu005 import ROOT, tier_counts


def drift(output, nodal=BASE/'CI-001', ms=BASE/'NU-004-MS', mc=BASE/'NU-005', certificate=True):
    out = dict(experiment='NU-005 drift, decision and tier audit', arms={})
    for name, campaign in (('nodal', Path(nodal)), ('MS', Path(ms)), ('MC', Path(mc))):
        comparison = read(campaign/'comparison.json') if (campaign/'comparison.json').exists() else dict(rows=[])
        status = {r['id']: r['status'] for r in comparison['rows'] if r['id'] in CORE}
        cases = {}
        for case in CORE:
            folder = campaign/'runs'/case
            if (folder/'result.json').exists():
                cases[case] = case_drift(folder, certificate)
                if name == 'MC':
                    cases[case]['identity_vs_MS'] = identity(Path(ms)/'runs'/case, folder)
                    cases[case]['identity_vs_nodal'] = identity(Path(nodal)/'runs'/case, folder)
                    cases[case]['validity'] = tier_counts(folder)
                print(name, case, 'max r', round(cases[case]['max_speed_ratio'], 4), cases[case]['outcome'], flush=True)
        out['arms'][name] = dict(campaign=str(campaign.resolve().relative_to(ROOT)), status=status, cases=cases)
    if len(out['arms']['MC']['cases']) == len(CORE) and len(out['arms']['nodal']['cases']) == len(CORE):
        rule = decide(out['arms']['nodal'], out['arms']['MC'])
        rule.pop('outcome')
        table = out['arms']['MC']['cases']
        units = {c: [read(Path(a)/'runs'/c/'result.json')['total_units'] for a in (ms, mc)] for c in CORE}
        identical = all(table[c]['identity_vs_MS']['same_accepted_steps'] and units[c][0] == units[c][1] for c in CORE)
        fallback = sum(table[c]['validity']['fallback'] for c in CORE)
        curves = sum(table[c]['validity']['curves'] for c in CORE)
        retained = rule['qualifies'] and identical
        out['decision'] = dict(rule, decision_identical_to_MS=identical, units=units,
                               fallback=fallback, curves=curves, fallback_fraction=fallback/max(curves, 1),
                               retained=retained,
                               outcome=('not retained: the tiers changed a decision' if not retained else
                                        'validity decided without samples on the six core cases' if fallback == 0 else
                                        f'retained; the sampled fallback decided {fallback} of {curves} curves'))
    write(Path(output)/'drift.json', out)
    return out.get('decision', 'incomplete')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NU-005 drift audit')
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(portable(drift(parser.parse_args(sys.argv[1:]).output)), indent=2))
