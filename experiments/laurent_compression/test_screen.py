"""Regression checks for the independent-reference and acceptance repairs."""
from types import SimpleNamespace

import numpy as np
import pytest

from .adapters import (NativeCase, lift, masked_hadamard_derivatives, moved_geometry, nodal_derivatives,
                       nodal_reference, parameterization, relative)
from .evaluation import assess, full_solution, qualify_native, reference_bundle
from .masks import derivative_aware, full
from .metrics import Ledger, acceptance, lifted_residual, paired
from .run_screen import (directions_for, equivalent_radius, fixture_set, inputs,
                         run, validation_acquisition)

FREQUENCY = 1.0669086261672807e9
LABEL = 'VERIFIED_SINGULAR_SPLIT'


def test_acceptance_requires_objective_and_reference_even_when_other_errors_are_zero():
    assert acceptance(0., 0., 0., 0., True)['passes_all']
    assert not acceptance(0., 0., 0., 0., False)['passes_all']
    assert not acceptance(0., 0., 0., 0., True, qualified=False)['passes_all']
    assert not acceptance(0., 0., np.nan, 0., True)['passes_all']


def test_budget_is_reserved_before_work_and_failed_reservation_does_not_change_counts():
    ledger = Ledger()
    ledger.charge(assemblies=ledger.CEILINGS['assemblies'])
    counts = ledger.counts.copy()
    with pytest.raises(RuntimeError, match='assemblies'):
        ledger.charge(assemblies=1, factorizations=1)
    assert ledger.counts == counts


def test_output_directory_cannot_be_overwritten(tmp_path):
    marker = tmp_path / 'previous_measurement'
    marker.write_text('retain')
    with pytest.raises(FileExistsError):
        run(tmp_path, 'pilot', True)
    assert marker.read_text() == 'retain'


def test_lifted_residual_uses_fixed_oracle_flux_scaling():
    # Deliberately unequal J and residual components distinguish physical and
    # flux norms, without relying on the production transform implementation.
    curve = SimpleNamespace(parameters=np.array([0., np.pi]), parameter_origin=0.,
                            period=2*np.pi, speeds=np.array([.1, .3]))
    state = np.array([[1.], [2.]])  # cutoff zero, one coefficient per trace
    a = np.eye(4)
    b = lift(state, [curve], 0) + np.array([[1.], [2.], [3.], [4.]])
    reference = dict(a=a, b=b, curves=[curve])
    scaling = np.diag([1., 1., .1, .3])
    expected = np.linalg.norm(scaling @ (a @ lift(state, [curve], 0) - b)) / np.linalg.norm(scaling @ b)
    assert lifted_residual(state, reference, 0) == pytest.approx(expected)
    assert abs(expected - relative(a @ lift(state, [curve], 0), b)) > .01


@pytest.mark.parametrize('fixture', ['ellipse', 'asymmetric_star'])
def test_independent_nodal_derivative_agrees_with_nodal_centered_differences(fixture):
    geometry = fixture_set()[fixture]
    acq, _ = inputs()
    dz = directions_for(geometry, equivalent_radius(geometry))[-1][1]
    base = nodal_reference([parameterization(geometry)], FREQUENCY, acq, 128)
    tangent = nodal_derivatives(base, geometry, [dz])[0]
    errors = []
    for h in (1e-3, 5e-4, 2.5e-4):
        ys = [nodal_reference([parameterization(moved_geometry(geometry, dz, sign*h))],
                              FREQUENCY, acq, 128)['y'] for sign in (1, -1)]
        errors.append(relative(tangent, (ys[0]-ys[1])/(2*h)))
    assert errors[-1] < 1e-5
    assert 3 < errors[0]/errors[1] < 5


def test_control_and_compressed_acceptance_detect_independent_derivative_error():
    geometry = fixture_set()['ellipse']
    acq, _ = inputs()
    directions = [d for _, d in directions_for(geometry, equivalent_radius(geometry))]
    reference = reference_bundle(geometry, acq, FREQUENCY, directions)
    case = NativeCase(geometry, acq, FREQUENCY, 16, 96, 28)
    derivatives = [case.derivative(d) for d in directions]
    control, native_dy = qualify_native(case, reference, derivatives)
    assert control['qualified']
    continuous = masked_hadamard_derivatives(full_solution(case), case, directions)
    assert max(relative(a, b) for a, b in zip(continuous, reference['dy'])) < 1e-7
    # A plausible but biased native derivative must not validate itself.
    biased = dict(reference, dy=[1.01 * dy for dy in reference['dy']])
    bad_control, _ = qualify_native(case, biased, derivatives)
    assert not bad_control['qualified']
    result, _ = assess(case, full_solution(case), full(case, LABEL), LABEL, derivatives,
                       biased, 1.05 * paired(reference['fine']['y']), native_dy, qualified=True)
    assert result['compression_derivative_error'] == 0.
    assert result['worst_data_derivative_error'] > .009
    assert not result['passes_all']


def test_absolute_mask_budget_is_preserved_when_trace_dimension_doubles():
    geometry = fixture_set()['ellipse']
    acq, _ = inputs()
    directions = [d for _, d in directions_for(geometry, equivalent_radius(geometry))[:4]]
    counts = []
    for cutoff in (16, 32):
        case = NativeCase(geometry, acq, FREQUENCY, cutoff, 96, 28)
        mask = derivative_aware(case, LABEL, .3, derivatives=[case.derivative(d) for d in directions],
                                floor=1e-12, count_per_block=327)
        counts.append(int(mask.sum()))
    assert counts == [1308, 1308]


def test_validation_illuminations_are_new_and_do_not_mutate_training_acquisition():
    acq, _ = inputs()
    original = np.array(acq['source_points'])
    validation = validation_acquisition(acq)
    np.testing.assert_array_equal(acq['source_points'], original)
    assert not np.allclose(validation['source_points'], original)
    np.testing.assert_array_equal(validation['receiver_points'], acq['receiver_points'])
