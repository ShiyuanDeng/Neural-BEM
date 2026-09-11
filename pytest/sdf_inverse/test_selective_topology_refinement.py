"""Selective refinement must respect physical optimization dimension and budget."""
from dataclasses import replace

import numpy as np
import pytest

from sdf_inverse import MultiRadialFourierState, circle_radial_fourier_state
from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
from sdf_inverse.topology_controller import TopologyCandidate, TopologyControllerConfig, _refinement_shortlist


def item(name, loss, mode=1, chart='radial'):
    if chart == 'cartesian':
        component = circle_cartesian_fourier_state((.5, .5), .03, name, maximum_mode=mode)
    else:
        component = circle_radial_fourier_state((.5, .5), .03, name)
        component = replace(component, radius_cosine_coefficients=np.r_[.03,np.zeros(mode)],
                             radius_sine_coefficients=np.zeros(mode+1))
    state = MultiRadialFourierState((component,))
    return loss, TopologyCandidate('split', state, ('parent',), (name,), -1., name), {'name':name}


def names(rows):
    return [r[2]['name'] for r in rows]


def test_selective_shortlist_reaches_third_ranked_simple_candidate():
    group = [item('complex1', .1, 4), item('complex2', .11, 4), item('simple', .2)]
    assert names(_refinement_shortlist(group, TopologyControllerConfig())) == ['complex1']
    assert names(_refinement_shortlist(group, TopologyControllerConfig(include_simplest_candidate=True))) == ['complex1','simple']


def test_simple_raw_winner_does_not_buy_extra_refinement():
    group = [item('simple', .1), item('complex', .2, 4), item('simple2', .3)]
    assert names(_refinement_shortlist(group, TopologyControllerConfig(include_simplest_candidate=True))) == ['simple']


def test_minimum_dimension_ties_choose_best_raw_and_never_duplicate_it():
    group = [item('complex', .1, 4), item('best_simple', .2), item('other_simple', .3)]
    for count in (1,2):
        config = TopologyControllerConfig(include_simplest_candidate=True,candidates_refined_per_group=count)
        assert names(_refinement_shortlist(group,config)) == ['complex','best_simple']


@pytest.mark.parametrize('mode,expected', [(2,['larger_storage']), (3,['larger_storage','circle'])])
def test_cartesian_cost_uses_gauge_dimension_not_coefficient_storage(mode,expected):
    group = [item('larger_storage', .1, mode, 'cartesian'), item('circle', .2, 1, 'cartesian')]
    config = TopologyControllerConfig(chart='cartesian',include_simplest_candidate=True)
    assert names(_refinement_shortlist(group,config)) == expected


def test_selective_flag_is_strictly_boolean():
    with pytest.raises(ValueError,match='must be boolean'):
        TopologyControllerConfig(include_simplest_candidate=1)
