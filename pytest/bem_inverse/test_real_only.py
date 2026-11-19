"""A real-only problem holds no damped data, and RealOnlyPolicy reads none."""
from dataclasses import replace

import numpy as np
import pytest

from bem_inverse.continuation.forward import PointSourceAcquisition
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.forward_solvers.modal_muller import ModalMuller
from bem_inverse.localization import localize
from bem_inverse.physics import Execution
from bem_inverse.policy import CumulativePolicy
from bem_inverse.problem import Problem, Observation
from bem_inverse.real_only_policy import RealOnlyPolicy

FREQUENCIES = (.25e9, .5e9, .75e9, 1e9, 1.25e9, 2.5e9)


def catalog(frequencies=FREQUENCIES, sigma=0.):
    angles = np.arange(8)*2*np.pi/8
    ring = 6*np.column_stack((np.cos(angles), np.sin(angles)))
    acquisition = PointSourceAcquisition(ring, 1.05*ring, 1e-6)
    return tuple(Observation(f/1.25e9*3.2, acquisition, np.ones(8, complex), f, sigma) for f in frequencies)


def real_only(**options):
    return Problem(FourierCurve.circle(1.3), catalog(**options), None, 4.)


def stages(policy, problem):
    return [(o.label, len(o.stage.observations), o.stage.update_modes, o.stage.curve_modes, o.stage.quota)
            for o in policy.operations(problem, ModalMuller(Execution(device='cpu'))) if o.kind == 'fit']


def test_absent_damped_catalog_is_explicit_and_refused_where_it_is_needed():
    problem = real_only()
    assert problem.real_only and problem.observations == problem.real
    with pytest.raises(ValueError):
        Problem(problem.initial, problem.real, (), 4.)      # an empty tuple is not "absent"
    physics = ModalMuller(Execution(device='cpu'))
    physics.validate(problem)
    with pytest.raises(ValueError, match='RealOnlyPolicy'):
        CumulativePolicy().operations(problem, physics)
    with pytest.raises(ValueError, match='real-only'):
        localize(problem, physics, CumulativePolicy().localization, None)
    damped = tuple(replace(o, wavenumber=o.wavenumber*(1+.25j)) for o in problem.real)
    with pytest.raises(ValueError, match='real-only'):
        RealOnlyPolicy().operations(replace(problem, damped=damped), physics)


def test_default_schedule_is_the_old_one_on_real_data_with_a_real_warmup():
    problem = real_only()
    physics = ModalMuller(Execution(device='cpu'))
    operations = RealOnlyPolicy().operations(problem, physics)
    assert not any(o.kind == 'localize' for o in operations)
    damped = tuple(replace(o, wavenumber=o.wavenumber*(1+.25j)) for o in problem.real)
    old = [o for o in CumulativePolicy().operations(replace(problem, damped=damped), physics) if o.kind == 'fit']
    new = [o for o in operations if o.kind == 'fit']
    # Old order: warm-up, four damped ladder stages, the real return, six full-catalog stages.
    assert [(o.stage.update_modes, o.stage.curve_modes, o.stage.quota, o.stage.iterations) for o in new] == \
           [(o.stage.update_modes, o.stage.curve_modes, o.stage.quota, o.stage.iterations) for o in old[:5]+old[6:]]
    assert [o.label for o in new[:5]] == ['warmup_real']+[f'ladder_{i}_real' for i in (1, 2, 3, 4)]
    assert [obs.frequency_hz for obs in new[0].stage.observations] == [.25e9]     # the lowest of the catalog
    assert (new[0].stage.update_modes, new[0].stage.curve_modes, new[0].stage.quota, new[0].stage.iterations) == \
           (1, 4, 600, 44)
    # warmup=False is the 17 November schedule: the same stages without the first.
    plain = [o for o in RealOnlyPolicy(warmup=False).operations(problem, physics) if o.kind == 'fit']
    assert [o.record() for o in plain] == [o.record() for o in new[1:]]
    assert all(complex(obs.wavenumber).imag == 0 for o in new for obs in o.stage.observations)
    assert operations[-1].kind == 'frontier'
    assert [o.label for o in operations if o.kind == 'cleanup'] == ['full_4_M25_cleanup']
    tail = RealOnlyPolicy().tail(problem, physics, 50)
    assert [o.stage.update_modes for o in tail] == [43, 49, 55]


def test_variants_change_one_thing():
    problem = real_only()
    default = stages(RealOnlyPolicy(), problem)
    assert stages(RealOnlyPolicy(frequency_schedule='simultaneous'), problem) == default[5:]     # no warm-up, no ladder
    assert stages(RealOnlyPolicy(frequency_schedule='simultaneous', warmup=False), problem) == default[5:]
    fixed = stages(RealOnlyPolicy(fixed_band=37), problem)
    assert [s[2] for s in fixed] == [37]*11 and [s[3] for s in fixed] == [76]*5+[192]*6
    assert [(s[1], s[4]) for s in fixed] == [(s[1], s[4]) for s in default]
    physics = ModalMuller(Execution(device='cpu'))
    assert RealOnlyPolicy(fixed_band=37).operations(problem, physics)[-1].kind == 'fit'


def test_single_frequency_grows_its_band_up_to_the_measured_frontier():
    problem = real_only(frequencies=(1e9,))
    physics = ModalMuller(Execution(device='cpu'))
    policy = RealOnlyPolicy(frequency_schedule='single')
    operations = policy.operations(problem, physics)
    assert [o.kind for o in operations] == ['fit', 'frontier']
    assert operations[0].stage.update_modes == 7 and operations[0].stage.curve_modes == 16
    assert [o.stage.update_modes for o in policy.tail(problem, physics, 16) if o.kind == 'fit'] == [11, 15, 19]
    assert policy.tail(problem, physics, 7) == ()
    with pytest.raises(ValueError):
        policy.operations(real_only(), physics)


def test_declared_noise_gives_recurrent_cleanup_and_a_discrepancy_threshold():
    problem = real_only(sigma=.01)
    operations = RealOnlyPolicy().operations(problem, ModalMuller(Execution(device='cpu')))
    assert sum(o.kind == 'cleanup' for o in operations) == 6
    assert all(o.details['noise_threshold'] for o in operations if o.kind == 'fit')
