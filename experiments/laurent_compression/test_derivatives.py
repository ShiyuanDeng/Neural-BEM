"""Derivative checks required by the LAU-001 plan, section 10.

The entrywise D_v A check is new: the repository already validates the forward
operator blockwise and the derivative at the DATA level, but nothing checked
D_v A entry by entry, which is the granularity this experiment masks at.
"""
import numpy as np
import pytest

from experiments.bie002_modal_diagnostic.fixtures import inputs

from . import masks as mask_rules
from .adapters import (NativeCase, masked_data_derivative, moved_geometry, relative,
                       solve_masked)
from .metrics import objective, objective_derivative, paired
from .run_screen import directions_for, equivalent_radius, fixture_set

FREQUENCY = 1.0669086261672807e9
LABEL = 'VERIFIED_SINGULAR_SPLIT'


def make(name, cutoff=16, bandwidth=96, terms=28):
    acq, _ = inputs()
    geometry = fixture_set()[name]
    return NativeCase(geometry, acq, FREQUENCY, cutoff, bandwidth, terms), geometry, acq


@pytest.mark.parametrize('name', ['circle', 'ellipse', 'star'])
def test_entrywise_operator_derivative_is_second_order_accurate(name):
    case, geometry, acq = make(name)
    # RMS boundary displacement a_ref per unit step, as the screen normalises:
    # a smaller direction puts centered differences straight on the roundoff
    # floor and the convergence order becomes unmeasurable.
    dz = dict(directions_for(geometry, equivalent_radius(geometry))[0][1])
    analytic = case.derivative(dz)['total']
    errors = []
    for step in (1e-3, 5e-4, 2.5e-4):
        sides = [NativeCase(moved_geometry(geometry, dz, sign * step), acq, FREQUENCY,
                            case.cutoff, case.bandwidth, case.terms) for sign in (+1, -1)]
        errors.append(relative(analytic, (sides[0].a - sides[1].a) / (2 * step)))
    assert errors[-1] < 1e-6
    for coarse, fine in zip(errors, errors[1:]):
        assert 3.0 < coarse / fine < 5.0, f'not second order: {errors}'


@pytest.mark.parametrize('name', ['circle', 'ellipse', 'star'])
def test_data_derivative_matches_the_qualified_jacobian(name):
    """masked_data_derivative at full mask == NativeShapeForward.jacobian."""
    case, _, _ = make(name)
    dz = {2: 5e-3, 3: 2e-3}
    mask = np.ones_like(case.a, dtype=bool)
    solved = solve_masked(*case.parts(LABEL), mask, case.b, case.c)
    mine = masked_data_derivative(solved, case, case.derivative(dz), mask, LABEL)
    assert relative(mine, case.forward.jacobian([dz])[0][..., 0]) < 1e-12


@pytest.mark.parametrize('fraction', [0.3, 0.5])
def test_frozen_mask_tangent_matches_finite_differences_of_the_same_model(fraction):
    """Differentiate the model that is solved: same mask for A~ and D_v A~."""
    case, geometry, acq = make('ellipse')
    named = dict(directions_for(geometry, equivalent_radius(geometry)))
    dz = named['train_c2_re']
    training = [case.derivative(named['train_c2_re']), case.derivative(named['train_cm1_re'])]
    mask = mask_rules.derivative_aware(case, LABEL, fraction, derivatives=training, floor=1e-12)
    solved = solve_masked(*case.parts(LABEL), mask, case.b, case.c)
    observed = paired(case.y) * (1 + 0.05)          # a deliberately off-anchor target
    _, residual = objective(paired(solved['y']), observed)
    tangent = objective_derivative(
        residual, paired(masked_data_derivative(solved, case, case.derivative(dz), mask, LABEL)))
    step = 5e-4
    values = []
    for sign in (+1, -1):
        side = NativeCase(moved_geometry(geometry, dz, sign * step), acq, FREQUENCY,
                          case.cutoff, case.bandwidth, case.terms)
        moved = solve_masked(*side.parts(LABEL), mask, side.b, side.c)
        values.append(objective(paired(moved['y']), observed)[0])
    finite = (values[0] - values[1]) / (2 * step)
    assert abs(tangent - finite) <= 1e-3 * abs(finite)


def test_real_adjoint_identity_matches_the_forward_tangent():
    case, geometry, _ = make('ellipse')
    dz = dict(directions_for(geometry, equivalent_radius(geometry))[3][1])
    mask = np.ones_like(case.a, dtype=bool)
    solved = solve_masked(*case.parts(LABEL), mask, case.b, case.c)
    observed = paired(case.y) * (1 + 0.05)
    _, residual = objective(paired(solved['y']), observed)
    derivative = case.derivative(dz)
    forward = objective_derivative(
        residual, paired(masked_data_derivative(solved, case, derivative, mask, LABEL)))
    # Adjoint form on the paired subset: lift the paired residual back to a full
    # receiver-by-source weight, then contract.
    from scipy.linalg import lu_solve
    weights = np.diag(residual)
    lam = lu_solve(solved['factors'], case.c.conj().T @ weights, trans=2)
    d_protected, d_remainder = case.derivative_parts(derivative, LABEL)
    da = d_protected + mask * d_remainder
    adjoint = float(np.real(np.sum(np.conj(lam) * (derivative['db'] - da @ solved['state'])))
                    + np.real(np.sum(np.conj(weights) * (derivative['dc'] @ solved['state']))))
    assert abs(adjoint - forward) <= 1e-8 * max(abs(forward), 1e-300)


@pytest.mark.parametrize('name', ['ellipse', 'star'])
def test_tangential_reparameterisation_leaves_receiver_data_stationary(name):
    """Control on DATA only: a tangential shift moves A but not the physics."""
    case, geometry, _ = make(name)
    tangential = {j: 1j * j * v for j, v in geometry.coefficients.items()}
    scale = 1e-3 / max(abs(v) for v in tangential.values())
    dz = {j: v * scale for j, v in tangential.items()}
    mask = np.ones_like(case.a, dtype=bool)
    solved = solve_masked(*case.parts(LABEL), mask, case.b, case.c)
    dy = masked_data_derivative(solved, case, case.derivative(dz), mask, LABEL)
    assert np.linalg.norm(dy) / np.linalg.norm(case.y) < 1e-6
