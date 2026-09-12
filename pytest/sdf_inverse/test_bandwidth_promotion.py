"""A mode-1 component can only translate and scale; a rung must buy a direction.

Geometry and gauge algebra only — no BIE solve anywhere in this file.
"""
import numpy as np
import pytest

from sdf_inverse import MultiRadialFourierState
from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, chart_contour_modes, component_parameterization,
    gauge_dimension, next_bandwidth_rung, zero_padded_component,
)

CAP = 9


def circle(radius_m=.03, center=(.5, .5), component_id='only'):
    return circle_cartesian_fourier_state(center, radius_m, component_id)


def boundary_points(component, samples=2048):
    return component_parameterization(component).discretize(samples).points


# --- the ladder ----------------------------------------------------------

def test_mode_one_and_mode_two_carry_the_same_directions():
    """The reason the ladder is stated in gauge dimension and not mode count."""
    one = circle()
    two = zero_padded_component(one, 2)
    assert two.maximum_mode == 2
    assert two.parameter_count > one.parameter_count
    # Four more parameters, not one more search direction.
    assert gauge_dimension(two) == gauge_dimension(one) == 3


def test_the_ladder_skips_the_rung_that_buys_nothing():
    assert next_bandwidth_rung(circle(), CAP) == 3


def test_every_rung_strictly_increases_the_gauge_dimension():
    component, rungs = circle(), []
    while True:
        rung = next_bandwidth_rung(component, CAP)
        if rung is None:
            break
        promoted = zero_padded_component(component, rung)
        assert gauge_dimension(promoted) > gauge_dimension(component)
        rungs.append(rung)
        component = promoted
    assert rungs == [3, 4, 5, 6, 7, 8, 9]
    assert component.maximum_mode == CAP


def test_the_ladder_stops_at_the_cap():
    assert next_bandwidth_rung(zero_padded_component(circle(), CAP), CAP) is None


def test_the_cap_comes_from_the_existing_contour_setting():
    """No constant in the ladder is chosen by the implementer or from a truth."""
    assert chart_contour_modes(TopologyControllerConfig(chart='cartesian')) == CAP


# --- geometry preservation ----------------------------------------------

@pytest.mark.parametrize('rung', (3, 4, 5, 9))
def test_padding_moves_no_point_of_the_boundary(rung):
    """Promotion has to be exact, or a drift would look like an improvement."""
    component = circle()
    np.testing.assert_allclose(boundary_points(zero_padded_component(component, rung)),
                               boundary_points(component), rtol=0., atol=1.e-15)


def test_padding_preserves_the_gauge_fixed_state():
    """The padded state is regauged like any other, and must survive it."""
    component = circle()
    padded = MultiRadialFourierState((zero_padded_component(component, 5),))
    regauged = padded.polar_angle_gauge_fixed()[0]
    np.testing.assert_allclose(boundary_points(regauged.components[0]),
                               boundary_points(component), rtol=0., atol=1.e-12)


def test_padding_refuses_to_shrink_or_stand_still():
    component = zero_padded_component(circle(), 5)
    for target in (5, 4, 1):
        with pytest.raises(ValueError, match='strictly increase'):
            zero_padded_component(component, target)


def test_promotion_requires_the_cartesian_chart():
    from sdf_inverse import circle_radial_fourier_state
    radial = circle_radial_fourier_state((.5, .5), .03, 'only')
    assert next_bandwidth_rung(radial, CAP) is None
    with pytest.raises(ValueError, match='Cartesian chart'):
        zero_padded_component(radial, 3)


# --- plumbing ------------------------------------------------------------

def test_the_controller_flag_is_off_by_default_and_validated():
    assert TopologyControllerConfig().bandwidth_promotion is False
    with pytest.raises(ValueError, match='bandwidth_promotion must be boolean'):
        TopologyControllerConfig(bandwidth_promotion=1)


def test_the_benchmark_arm_differs_from_its_baseline_by_one_policy():
    import run_topology_scene_benchmark as benchmark
    h, j = benchmark.ARM_POLICIES['H'], benchmark.ARM_POLICIES['J']
    assert {k: v for k, v in j.items() if k != 'bandwidth_promotion'} == h
    assert j['bandwidth_promotion'] is True
