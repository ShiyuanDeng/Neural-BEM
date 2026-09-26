"""Frozen SC-041 outsider probe: loss of truth, endpoint and filtered endpoints. See plan.md."""
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
spec = importlib.util.spec_from_file_location('sc041_run', RESULTS/'SC-041-atlas-decisions/run.py')
sc041 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc041)

from dataclasses import replace
from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import Ledger, Objective
from ordered_boundary.validation_cache import geometry_validation

BAND = 192


def padded(curve, band=BAND):
    c = np.zeros(2*band+1, complex)
    c[curve.modes + band] = curve.coefficients
    return FourierCurve(c)


def low_pass(curve, K):
    c = np.array(curve.coefficients)
    c[np.abs(curve.modes) > K] = 0
    return FourierCurve(c)


def main():
    truth = padded(ast.curve_from(sc.read(ast.source_folder('kite')/'truth.json')))
    result = json.loads((RESULTS/'SC-041-atlas-decisions/runs/kite/M22/result.json').read_text())
    endpoint = ast.curve_from(result['curve'])
    curves = {'truth': truth, 'endpoint_M22': endpoint}
    curves.update({f'endpoint_lowpass_K{K}': low_pass(endpoint, K) for K in (8, 16, 32, 64)})
    curves['midpoint_endpoint_truth'] = FourierCurve(0.5*(endpoint.coefficients + truth.coefficients))
    refined = ('truth', 'endpoint_M22')

    stage, config, _ = sc041.setup('kite', 22)
    ledger = Ledger(cap=10**6, seconds=10**6, endpoint_reserve=0)
    coarse = Objective(stage, ac.contrast(), config, ledger)
    fine = Objective(replace(stage, nodes=stage.refined_nodes, refined_nodes=2*stage.refined_nodes),
                     ac.contrast(), config, ledger)
    rows = {}
    for name, curve in curves.items():
        row = dict(score=sc041.geometry_score('kite', curve))
        try:
            curve.validate()
            row['valid'] = True
        except ValueError as error:
            row['valid'], row['invalid_reason'] = False, str(error)
        start = time.time()
        with geometry_validation('cache'):
            value = coarse.production(curve, 'outsider_probe') if row['valid'] else None
            row['loss'] = None if value is None else float(value.loss)
            if name in refined and value is not None:
                row['loss_refined'] = float(fine.production(curve, 'outsider_probe_fine').loss)
        row['seconds'] = time.time() - start
        rows[name] = row
        print(name, json.dumps(row), flush=True)
    control = abs(rows['endpoint_M22']['loss'] - result['final_loss'])/result['final_loss']
    base = rows['endpoint_M22']['loss']
    lever = [n for n, r in rows.items() if n.startswith('endpoint_lowpass') and r['loss'] is not None
             and r['loss'] <= base and r['score']['tightest_radius_fine_mm'] >= 1.0]
    decision = dict(
        control_relative_error=control, control_passed=control <= 1e-10,
        truth_over_endpoint_loss=rows['truth']['loss']/base,
        data_do_not_require_feature=rows['truth']['loss'] <= 0.1*base,
        spectral_cap_candidates=lever,
    )
    report = dict(plan='plan.md', nodes=stage.nodes, refined_nodes=stage.refined_nodes,
                  rows=rows, decision=decision, work=ledger.snapshot())
    (HERE/'probe.json').write_text(json.dumps(report, indent=1, default=float) + '\n')
    print(json.dumps(decision, indent=1))


if __name__ == '__main__':
    main()
