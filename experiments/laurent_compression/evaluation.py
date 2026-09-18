"""Independent physical references and shared acceptance for every screen arm."""
import numpy as np

from .adapters import (masked_data_derivative, masked_hadamard_derivatives,
                       nodal_derivatives, nodal_reference, parameterization, relative)
from .metrics import (CONTROL_GATES, acceptance, cancellation_allowance, lifted_residual,
                      objective, objective_derivative, objective_derivative_passes, paired)


def reference_bundle(geometry, acquisition, frequency, directions, ledger=None):
    curve = parameterization(geometry)
    coarse = nodal_reference([curve], frequency, acquisition, 256, ledger)
    fine = nodal_reference([curve], frequency, acquisition, 384, ledger)
    coarse_dy = nodal_derivatives(coarse, geometry, directions)
    fine_dy = nodal_derivatives(fine, geometry, directions)
    receiver_error = relative(paired(coarse['y']), paired(fine['y']))
    errors = [relative(paired(a), paired(b)) for a, b in zip(coarse_dy, fine_dy)]
    qualification = dict(oracle_receiver_error=receiver_error,
                         oracle_derivative_errors=errors,
                         oracle_derivative_worst=max(errors),
                         qualified=bool(receiver_error <= CONTROL_GATES['oracle_receiver']
                                        and max(errors) <= CONTROL_GATES['oracle_derivative']))
    return dict(fine=fine, coarse=coarse, dy=fine_dy, qualification=qualification)


def full_solution(case, ledger=None):
    """Reuse the native base LU instead of refactoring an unmasked control."""
    return dict(a=case.a, factors=case.factors, state=case.u, y=case.y, ledger=ledger)


def data_derivatives(solved, case, derivatives, mask, label):
    return [masked_data_derivative(solved, case, d, mask, label) for d in derivatives]


def qualify_native(case, reference, derivatives, ledger=None):
    solved = full_solution(case, ledger)
    mask = np.ones_like(case.a, dtype=bool)
    dy = data_derivatives(solved, case, derivatives, mask, 'VERIFIED_SINGULAR_SPLIT')
    errors = [relative(paired(a), paired(b)) for a, b in zip(dy, reference['dy'])]
    data_error = relative(paired(case.y), paired(reference['fine']['y']))
    residual = lifted_residual(case.u, reference['fine'], case.cutoff)
    qualified = (reference['qualification']['qualified']
                 and data_error <= CONTROL_GATES['receiver']
                 and residual <= CONTROL_GATES['lifted_residual']
                 and max(errors) <= CONTROL_GATES['data_derivative'])
    return dict(qualified=bool(qualified), data_error=data_error,
                lifted_residual=residual, data_derivative_errors=errors,
                worst_data_derivative_error=max(errors)), dy


def assess(case, solved, mask, label, derivatives, reference, observed,
           uncompressed_dy, *, qualified, training_count=4, directions=None):
    """Every arm uses the same physical field, derivative, and objective gates.

    Compression-only and total-to-Kress errors are different columns. A
    continuous Hadamard check is diagnostic, never substituted for the
    discrete derivative of the frozen mask.
    """
    ref_y = paired(reference['fine']['y'])
    y = paired(solved['y'])
    data_error = relative(y, ref_y)
    residual = lifted_residual(solved['state'], reference['fine'], case.cutoff)
    loss, r = objective(y, observed)
    _, ref_r = objective(ref_y, observed)
    dy = data_derivatives(solved, case, derivatives, mask, label)
    rows = []
    for index, (actual, truth, full) in enumerate(zip(dy, reference['dy'], uncompressed_dy)):
        a, b = paired(actual), paired(truth)
        check = objective_derivative_passes(
            objective_derivative(r, a), objective_derivative(ref_r, b),
            cancellation_allowance(ref_r, b))
        rows.append(dict(direction_index=index, heldout=index >= training_count,
                         data_derivative_error=relative(a, b),
                         compression_derivative_error=relative(a, paired(full)),
                         reference_derivative_norm=float(np.linalg.norm(b)),
                         **check))
    training = max(r['data_derivative_error'] for r in rows[:training_count])
    heldout = max(r['data_derivative_error'] for r in rows[training_count:])
    result = dict(data_error=data_error, lifted_residual=residual, loss=loss,
                  worst_training_derivative_error=training,
                  worst_heldout_derivative_error=heldout,
                  worst_data_derivative_error=max(training, heldout),
                  compression_derivative_error=max(r['compression_derivative_error'] for r in rows),
                  objective_derivative_worst_relative=max(r['relative_error'] for r in rows),
                  **acceptance(data_error, residual, training, heldout,
                               all(r['passes'] for r in rows), qualified=qualified))
    if directions is not None:
        continuous = masked_hadamard_derivatives(solved, case, directions)
        result['hadamard_physical_derivative_error'] = max(
            relative(paired(a), paired(b)) for a, b in zip(continuous, reference['dy']))
        result['hadamard_vs_discrete_derivative_error'] = max(
            relative(paired(a), paired(b)) for a, b in zip(continuous, dy))
    return result, rows
