"""Predeclared test 1: the seven refused original starts against 1024-node CPU Kress.

Every real frequency, modal production and refined tokens of the initial audit
(K_trace 64 and 96), on CPU and CUDA. Gate: modal within 1e-12 of Kress 1024.
Also records the Graf orders and the audit's production/refined discrepancy.

Usage: python starts.py  (writes starts.json)
"""
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.modal_muller import ModalMuller, token
from experiments.cleaned_interface.physics import CA, Execution, NodalKress

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CASES = ('far__development_c', 'far__opposite_c', 'modal__c2__development_c', 'modal__c4__development_c',
         'modal__c13.3__development_c', 'modal__c4__opposite_c', 'modal__c13.3__opposite_c')


def relative(a, reference):
    return np.linalg.norm(a-reference, axis=0)/np.linalg.norm(reference, axis=0)


def main():
    nodal = NodalKress(Execution(device='cpu', frequency_threads=4))
    devices = ('cpu', 'cuda') if CA.available() else ('cpu',)
    rows = []
    for case in CASES:
        p = b.fitting_problem(next(r for r in b.descriptors() if r['id'] == case), b.DEFAULT_OUTPUT)
        curve = p.initial
        services = {d: ModalMuller(Execution(device=d, frequency_threads=4)) for d in devices}
        for o in p.real:
            reference = nodal.evaluate(curve, o, p.contrast, 1024).prediction
            row = dict(case=case, contrast=p.contrast, frequency_hz=o.frequency_hz,
                       kress_512=float(relative(nodal.evaluate(curve, o, p.contrast, 512).prediction, reference).max()))
            for device, service in services.items():
                values = {}
                for cutoff in (64, 96):
                    prediction = service.evaluate(curve, o, p.contrast, token(cutoff))
                    values[cutoff] = prediction.prediction
                    row[f'{device}_{cutoff}'] = float(relative(prediction.prediction, reference).max())
                    row[f'{device}_{cutoff}_graf_order'] = prediction.diagnostics['graf_order']
                    row[f'{device}_{cutoff}_device'] = prediction.diagnostics['device']
                row[f'{device}_audit_discrepancy'] = float(relative(values[64], values[96]).max())
            rows.append(row)
        worst = {k: max(r[k] for r in rows if r['case'] == case) for k in rows[-1] if k.endswith(('_64', '_96'))}
        print(case, {k: f'{v:.2e}' for k, v in worst.items()}, flush=True)
    keys = [k for k in rows[0] if k.endswith(('_64', '_96'))]
    summary = dict(worst={k: max(r[k] for r in rows) for k in keys},
                   worst_audit_discrepancy={d: max(r[f'{d}_audit_discrepancy'] for r in rows) for d in devices},
                   graf_orders=sorted({r[f'{d}_{c}_graf_order'] for r in rows for d in devices for c in (64, 96)}))
    summary['gate_1e-12'] = all(v <= 1e-12 for v in summary['worst'].values())
    sources = {name: hashlib.sha256((ROOT/'experiments/cleaned_interface'/name).read_bytes()).hexdigest()
               for name in ('modal_operator.py', 'modal_muller.py', 'modal_geometry.py', 'modal_cuda.py')}
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    (HERE/'starts.json').write_text(json.dumps(dict(summary=summary, rows=rows, git_head=head, sources=sources), indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
