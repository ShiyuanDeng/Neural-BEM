"""Run one TG-002 case with the default method and save every LM proposal's base state.

Saves, per proposal event: base curve, the optimiser space, J, g, H_GN, D, lambda, the raw and
bounded steps, and the config. Also saves the real per-trial rows (`geometry_trial`) so the
notebook replay can be compared with what the loop actually did. Nothing in the solver changes.
"""
import pickle
import sys
from pathlib import Path

import numpy as np

from bem_inverse import modal_muller
from experiments.benchmark import campaign as c, scenes as S

case, out = sys.argv[1], Path(sys.argv[2])
events = []


def observer(kind, row):
    if kind == 'proposal':
        events.append(('proposal', dict(
            coefficients=row['evaluation'].curve.coefficients.copy(), loss=float(row['evaluation'].loss),
            space=row['space'], J=row['J'].copy(), g=row['gradient'].copy(), H=row['normal'].copy(),
            D=row['metric'].copy(), damping=float(row['damping']), raw=row['raw_proposed'],
            bounded=row['bounded_proposed'].copy(), floor=float(row['controller_floor']),
            stage=row['stage'].label, config=row['config'])))
    elif kind == 'geometry_trial':
        events.append(('trial', dict(row['trial'])))


original = modal_muller.ModalMuller.__init__


def init(self, *a, **k):
    original(self, *a, **k)
    self.observer = observer


modal_muller.ModalMuller.__init__ = init
settings = c.settings_for(localization='none', execution=c.Execution(device='cpu', frequency_threads=4),
                          solver='modal_muller', geometry_update='certified_spectral')
run_dir = out.parent/(out.stem+'_run')
row = next(r for r in c.descriptors() if r['id'] == case)
result = c.run_case((run_dir, row, settings))
print(result['outcome'], result.get('metrics'))
out.write_bytes(pickle.dumps(events))
print(len(events), 'events ->', out)
