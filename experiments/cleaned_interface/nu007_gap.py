"""NU-007 pre-check diagnostic: absolute bound differences and distance of each bound from 1.

The pre-registered gate 3 (relative bound difference <= 1e-9) failed while decisions and
tiers matched in all 864 trials. This replays the same trials (``nu007.precheck_state``'s
seeds, sizes and directions) and records, for every certified-tier bound, the host and
device values, their absolute difference and min(|bound-1|) - the margin a tier decision
actually depends on. Diagnostic only; it does not change the gate or the decision.

    python -m experiments.cleaned_interface.nu007_gap --output DIR
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

from experiments.shape_continuation.updates import UpdateRefused
from .io import read, write, curve_from, portable
from .n_update_audit import CORE
from .nu003 import BASE
from .nu006 import BatchedCertifiedUpdate
from .nu007 import DeviceCertifiedUpdate

KEYS = (('increment_bound', 'increment_lower'), ('full_bound', 'full_lower'))


def state_gaps(curve, M, unit=.05, sizes_m=(1e-7, 1e-3, 6e-3, 1.8e-2), directions=3, seed=5):
    host, device = BatchedCertifiedUpdate(unit), DeviceCertifiedUpdate(unit)
    s_host, s_dev = host.prepare(curve, M, curve.band), device.prepare(curve, M, curve.band)
    rng = np.random.default_rng(seed)
    rows = []
    for size in sizes_m:
        for _ in range(directions):
            a = rng.normal(size=len(s_host.orders))
            a *= size/max(host.measure(s_host, a)['maximum_normal_m'], 1e-300)
            for u, s in ((host, s_host), (device, s_dev)):
                try:
                    u.trial(s, a)
                except (UpdateRefused, ValueError):
                    pass
            for x, y in zip(host.records, device.records):
                for bound, lower in KEYS:
                    if bound in x and bound in y:
                        rows.append(dict(size_m=size, role=x['role'], bound=bound, host=x[bound], device=y[bound],
                                         absolute=abs(x[bound]-y[bound]), margin=min(abs(x[bound]-1), abs(y[bound]-1)),
                                         lower_absolute=abs(x[lower]-y[lower]),
                                         same_side=(x[bound] < 1) == (y[bound] < 1)))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args(argv).output
    rows = []
    for case in CORE:
        last = {}
        for state in read(BASE/'NU-006/runs'/case/'accepted.json')['states']:
            last[state['stage']] = state
        for stage, state in last.items():
            got = state_gaps(curve_from(state['curve']), state['M'])
            rows += [dict(r, case=case, stage=stage) for r in got]
            print(case, stage, 'max abs %.1e' % max((r['absolute'] for r in got), default=0),
                  'min margin %.1e' % min((r['margin'] for r in got), default=np.inf), flush=True)
    summary = dict(experiment='NU-007 pre-check gap diagnostic', bounds=len(rows),
                   max_absolute=max(r['absolute'] for r in rows), max_lower_absolute=max(r['lower_absolute'] for r in rows),
                   max_relative=max(r['absolute']/max(abs(r['host']), 1e-300) for r in rows),
                   min_margin=min(r['margin'] for r in rows), all_same_side=all(r['same_side'] for r in rows),
                   relative_above_1e9=sum(r['absolute'] > 1e-9*abs(r['host']) for r in rows),
                   largest_host_bound_with_relative_above_1e9=max(
                       (abs(r['host']) for r in rows if r['absolute'] > 1e-9*abs(r['host'])), default=None))
    write(Path(output)/'gap.json', dict(summary, rows=rows))
    print(json.dumps(portable(summary), indent=2))


if __name__ == '__main__':
    main(sys.argv[1:])
