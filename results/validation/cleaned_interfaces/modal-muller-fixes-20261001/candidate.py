"""Capture and resolve the rejected trial behind the contrast-13.3 C stops in CI-001-modal-r2.

Replays ``fixed_M31`` of ``modal__c13.3__development_c`` from its archived start
with the frozen policy operation and the fixed modal service (CUDA). Records every
curve evaluated at the refined token, then compares modal K_trace 128-256 with
2048-node CPU Kress on the first rejected candidate at the four highest frequencies.

Usage: python candidate.py  (writes candidate.json)
"""
import json
from pathlib import Path
import subprocess

import numpy as np

from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.geometry import ProjectedUpdate
from experiments.cleaned_interface.io import curve_from, curve_record
from experiments.cleaned_interface.modal_muller import ModalMuller, token, trace_cutoff
from experiments.cleaned_interface.physics import Execution, NodalKress
from experiments.cleaned_interface.policy import CumulativePolicy
from experiments.shape_continuation.lm_backend import Ledger, fit_stage

HERE = Path(__file__).resolve().parent
CASE, STAGE, M = 'modal__c13.3__development_c', 'fixed_M31', 31
RUN = HERE.parent/'CI-001-modal-r2'/'runs'/CASE


class Recording(ModalMuller):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.refined = []

    def evaluate(self, curve, observation, contrast, resolution):
        if trace_cutoff(int(resolution)) == 160 and observation.frequency_hz == 2.5e9:
            self.refined.append(curve)
        return super().evaluate(curve, observation, contrast, resolution)


def relative(a, reference):
    return float((np.linalg.norm(a-reference, axis=0)/np.linalg.norm(reference, axis=0)).max())


def main():
    p = b.fitting_problem(next(r for r in b.descriptors() if r['id'] == CASE), b.DEFAULT_OUTPUT)
    start = curve_from(json.loads((RUN/'fixed_M25.json').read_text())['curve'])
    policy = CumulativePolicy()
    service = Recording(Execution(device='cuda', frequency_threads=4))
    op = next(o for o in (*policy.operations(p, service), *policy.tail(p, service, 10**6)) if o.label == STAGE)
    ledger = Ledger(cap=policy.fit_units, seconds=policy.fit_seconds)
    ledger.begin_stage(op.label, op.stage.quota)
    result = fit_stage(start, op.stage, p.contrast, ProjectedUpdate(p.length_unit_m), op.optimizer, ledger, physics=service)
    archived = json.loads((RUN/f'{STAGE}.json').read_text())
    replay = dict(outcome=result.outcome, accepted=result.accepted_steps,
                  discrepancy=[max(c['prediction_discrepancy']) for c in result.acceptance_checks],
                  archived_outcome=archived['outcome'],
                  archived_discrepancy=[max(c['prediction_discrepancy']) for c in archived['acceptance_checks']])
    print(replay, flush=True)
    candidate = next(c for c in service.refined if not np.array_equal(c.coefficients, start.coefficients))
    nodal = NodalKress(Execution(device='cpu', frequency_threads=4))
    clean = ModalMuller(Execution(device='cuda', frequency_threads=4))
    modes = np.arange(-candidate.band, candidate.band+1)
    rows = []
    for o in p.real[-4:]:
        reference = nodal.evaluate(candidate, o, p.contrast, 2048).prediction
        row = dict(frequency_hz=o.frequency_hz,
                   kress_512=relative(nodal.evaluate(candidate, o, p.contrast, 512).prediction, reference),
                   kress_1024=relative(nodal.evaluate(candidate, o, p.contrast, 1024).prediction, reference))
        values = {}
        for cutoff in (128, 160, 192, 224, 256):
            values[cutoff] = clean.evaluate(candidate, o, p.contrast, token(cutoff)).prediction
            row[f'modal_{cutoff}'] = relative(values[cutoff], reference)
        row['modal_128_vs_160'] = relative(values[128], values[160])
        row['modal_160_vs_192'] = relative(values[160], values[192])
        rows.append(row)
        print({k: f'{v:.2e}' for k, v in row.items()}, flush=True)
    step = candidate.coefficients-start.coefficients
    out = dict(case=CASE, stage=STAGE, replay=replay, rows=rows,
               step_coefficient_max=float(np.abs(step).max()),
               step_by_band={str(q): float(np.abs(step[np.abs(modes) >= q]).max()) for q in (8, 16, 24, 31, 32)},
               candidate=curve_record(candidate),
               git_head=subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip())
    (HERE/'candidate.json').write_text(json.dumps(out, indent=1, default=lambda o: np.asarray(o).tolist()))


if __name__ == '__main__':
    main()
