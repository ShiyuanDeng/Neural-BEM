"""TOP-011 follow-up: how far does the linear model actually describe? No solves.

The walk's probes are predicted/actual pairs at known fractions of the feasible
step, so the radius over which the linear model still describes the objective
can be read straight out of ``tolerance_sensitivity.json``. This matters for the
reading: the finite-difference Jacobian is verified stable to 3e-06 across three
FD scales, so the derivative is not wrong. What the probes show is that in the
weak directions the neighbourhood it describes is far smaller than the step the
tolerance permits -- which is a statement about validity radius, not accuracy.

Reads the recorded run and writes a table. It runs no solver at all.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_fourier_topology_controller as driver  # noqa: E402

AGREEMENT = 0.10


def main():
    recorded = json.loads((HERE / 'tolerance_sensitivity.json').read_text())
    states = []
    for state in recorded['states']:
        probes = state['linear_model_breakdown']
        walks = {(w['rank'], w['sign']): w for w in state['walks']}
        rows = []
        for rank in range(state['gauge_directions']):
            here = [p for p in probes if p['rank'] == rank]
            if not here:
                continue
            agreeing = [p for p in here if p['linear_model_relative_error'] <= AGREEMENT]
            smallest = min(p['fraction_of_feasible_step'] for p in here)
            rows.append(dict(
                rank=rank, singular_value=walks[(rank, 1)]['singular_value'],
                boundary_displacement_mm=walks[(rank, 1)].get('boundary_displacement_mm'),
                largest_agreeing_fraction=(max(p['fraction_of_feasible_step']
                                               for p in agreeing) if agreeing else None),
                smallest_probed_fraction=smallest,
                error_at_smallest_probed=min(p['linear_model_relative_error'] for p in here
                                             if p['fraction_of_feasible_step'] == smallest)))
        described = [r for r in rows if r['largest_agreeing_fraction'] == 1.0]
        undescribed = [r for r in rows if r['largest_agreeing_fraction'] is None]
        states.append(dict(
            state=state['state'], agreement_threshold=AGREEMENT, per_rank=rows,
            ranks_described_to_the_full_permitted_step=[r['rank'] for r in described],
            ranks_with_no_probed_step_in_agreement=[r['rank'] for r in undescribed],
            worst_smallest_probed_fraction_among_those=(
                max(r['smallest_probed_fraction'] for r in undescribed)
                if undescribed else None),
            error_range_at_the_smallest_probed_step=(
                [min(r['error_at_smallest_probed'] for r in undescribed),
                 max(r['error_at_smallest_probed'] for r in undescribed)]
                if undescribed else None)))
        print(f"\n=== {state['state']} ===")
        print(f"  linear model within {AGREEMENT:.0%} out to the full permitted step: "
              f"ranks {described[0]['rank']}-{described[-1]['rank']}"
              if described else '  no rank described to the full step')
        print(f"  no probed step in agreement at all: ranks "
              f"{undescribed[0]['rank']}-{undescribed[-1]['rank']}, probed down to "
              f"{max(r['smallest_probed_fraction'] for r in undescribed):.2f} of the "
              f"feasible step, errors "
              f"{min(r['error_at_smallest_probed'] for r in undescribed):.2f}-"
              f"{max(r['error_at_smallest_probed'] for r in undescribed):.1f}")
    driver.write_json(HERE / 'model_validity_radius.json',
                      dict(forward_solves=0, agreement_threshold=AGREEMENT, states=states))


if __name__ == '__main__':
    main()
