"""How well can GauGal's lattice reproduce the data of the true object?

For each case, lattice and frequency: set the lattice coefficients to the truth
(susceptibility times the cell area fraction), solve the field equation exactly
(projected dense LU, as in the ``converged`` variant) and compare the 24 paired
predictions with the sealed observations. This is a diagnostic that reads the
truth. It chooses no fit setting.

Run from the repository root:
    $PY docs/iterations/evaluate_our_method/06_make_gaugal_fits_converge/forward_floor.py
"""
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
for extra in (Path(os.environ.get('GAUGAL_SRC', Path.home()/'Gau-Gal/src')), ROOT/'solvers', ROOT):
    sys.path.insert(0, str(extra))

import numpy as np
import torch
from gaugal.paper2d.collocation import collocation_forward_prop, collocation_sensor_forward
from gaugal.paper2d.reconstruct import paper_options
from gaugal.paper2d.settings import SolverControls
from gaugal.paper2d.synthetic import build_synthetic_galerkin_model

from experiments.gaugal_comparison import gaugal_arm as G
from experiments.gaugal_comparison import tg002_data as D

OUT = ROOT/'results/_probes/gaugal_convergence/2026-11-19/forward_floor'
CASES = sys.argv[1].split(',') if len(sys.argv) > 1 else ['kite__c0.5', 'kite__c4']
LATTICES = [(51, .7), (101, .7)]
FREQUENCIES = [0, 3, 6, 9, 12, 15, 18]


def paired_error(case, index, grid, sigma):
    opts = paper_options(G.settings(grid, sigma_scale=sigma), SolverControls())
    model = G.build_model(case, index, G.PIXELS, 'cuda')
    collocation = build_synthetic_galerkin_model(model, opts)
    G.prepare_direct(collocation)
    opts = replace(opts, collocation_linear_solver='direct')
    coeff = torch.as_tensor(G.lattice_truth(case, grid), device='cuda', dtype=collocation.real_dtype)
    with torch.no_grad():
        u = collocation_forward_prop(collocation, coeff, collocation.uinc, opts)
        predicted = collocation_sensor_forward(model, collocation, coeff, u)
    paired = case.strength*torch.diagonal(predicted).cpu().numpy()
    del collocation, model, u, predicted
    torch.cuda.empty_cache()
    return float(D.relative_error(paired, case.observed[index]))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for case_id in CASES:
        case = D.load(case_id)
        for grid, sigma in LATTICES:
            for index in FREQUENCIES:
                error = paired_error(case, index, grid, sigma)
                rows.append(dict(case=case_id, lattice=grid, width=sigma,
                                 frequency_ghz=float(case.frequencies_hz[index]/1e9), relative_error=error))
                print(f'{case_id} lattice {grid} width {sigma} {rows[-1]["frequency_ghz"]:.3f} GHz: {error:.3f}', flush=True)
    name = 'forward_floor_' + '_'.join(CASES) + '.json'
    (OUT/name).write_text(json.dumps(dict(
        note='True object on the lattice, exact field solve, error against sealed data over 24 pairs.',
        rows=rows), indent=1))


if __name__ == '__main__':
    main()
