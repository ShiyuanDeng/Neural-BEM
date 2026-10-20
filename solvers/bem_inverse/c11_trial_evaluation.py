"""C11. Trial geometry → production/refined evaluation → accept or reject (records).

Evaluations own predictions; Objective owns its exact-coefficient refined cache.
These functions do not decide whether to retry, promote, or stop the optimizer:
those responses remain explicit in fit_stage.validate and its caller.
"""
from . import checks
import numpy as np
from .checks import resolution_check, relative_columns
from .recording import observe


def refined_pair(objective, base, candidate, ledger):
    """Reserve at the original point, then obtain/cache base and trial predictions."""
    ledger.reserve(2 * objective.count)
    refined_base = objective.refined(base.curve)
    refined_candidate = objective.refined(candidate.curve)
    return refined_base, refined_candidate


def checked_pair(base, candidate, rb, rc, active_stage, config, *,
                 acceptance_checks, physics, ledger, check_base=False):
    """Compare four evaluations; record evidence before any optional response.

    ``rb`` and ``rc`` are the refined base and candidate. The returned flags
    distinguish loss acceptance from base/candidate prediction agreement.
    """
    row, accurate = resolution_check(base, candidate, rb, rc, active_stage, config)
    discrepancy = np.asarray(row['prediction_discrepancy'])
    acceptance_checks.append(row)
    tolerances = np.asarray(active_stage.discrepancy_tolerances)
    base_accurate = True
    if check_base:
        bd = relative_columns(base.prediction, rb.prediction)
        base_accurate = checks.fields_agree(bd, tolerances)
        row.update(base_prediction_discrepancy=bd.tolist(), base_qualified=base_accurate,
                   candidate_qualified=accurate, nodes=active_stage.nodes,
                   refined_nodes=active_stage.refined_nodes,
                   threshold_distance=(tolerances-discrepancy).tolist())
    if (not accurate and config.resolution_gate == 'absolute') or not base_accurate:
        observe(physics, 'resolution_refusal', base=base, candidate=candidate,
                refined_base=rb, refined_candidate=rc, stage=active_stage, check=row, ledger=ledger)
        row.update(accepted=False, numerical_obstruction=True)
    return row, base_accurate, accurate
