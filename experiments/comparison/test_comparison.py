"""Run names, the noise rule and the scoring rules on shapes with known answers. No solves."""
import numpy as np
import pytest

from experiments.gaugal_comparison import tg002_data as D
from . import noise as N, runs as R, scoring as G


def circle(radius, centre=0j, count=4096):
    return centre+radius*np.exp(2j*np.pi*np.arange(count)/count)


def test_run_names_carry_four_tags_and_choose_their_cases():
    run = R.parse('bem/default_n1d2_uc_fc')
    assert (run.noise, run.damped, run.single_frequency_hz, run.fixed_band) == ((1., 2), False, None, None)
    assert len(R.cases_for(run)) == 30
    assert R.parse('bem/default_clean_uc_sf1.5').single_frequency_hz == 1.5e9
    assert R.parse('bem/fixedband37_clean_uc_fc').fixed_band == 37
    for key in ('bem/default_clean_kc_fc', 'bem/default_cleandamped_uc_fc', 'bem/nodal_clean_uc_fc',
                'bem/default_clean_uc_fs', 'gaugal/default_n1d0_uc_fs'):
        assert len(R.cases_for(R.parse(key))) == 20
    assert all(R.parse(key).key == key for _, _, keys in R.PLAN for key in keys)
    for bad in ('bem/default_clean_uc', 'bem/default_clean_uc_sf0.3', 'other/default_clean_uc_fc',
                'bem/tuned_clean_uc_fc', 'bem/default_noisy_uc_fc'):
        with pytest.raises(ValueError):
            R.parse(bad)


def test_noise_follows_its_rule_and_scales_between_levels():
    clean = np.exp(1j*np.arange(24*19).reshape(24, 19))*np.linspace(1, 3, 19)
    one, sigma = N.draw_noise(clean, 1., 0, 'kite__c4')
    again, _ = N.draw_noise(clean, 1., 0, 'kite__c4')
    five, _ = N.draw_noise(clean, 5., 0, 'kite__c4')
    assert np.array_equal(one, again) and np.allclose(five-clean, 5*(one-clean))
    assert np.allclose(sigma*np.sqrt(48), .01*np.linalg.norm(clean, axis=0))
    assert not np.allclose(N.draw_noise(clean, 1., 1, 'kite__c4')[0], one)
    assert not np.allclose(N.draw_noise(clean, 1., 0, 'kite__c0.5')[0], one)
    realized = np.linalg.norm(one-clean, axis=0)/np.linalg.norm(clean, axis=0)
    assert .005 < realized.min() and realized.max() < .015


def test_region_scores_are_unaligned_and_keep_every_component():
    truth, _ = G.region([circle(.03)])
    shifted, _ = G.region([circle(.03, .01)])
    scores = G.region_scores(shifted, truth)
    d, r = .01, .03
    lens = 2*r*r*np.arccos(d/(2*r))-.5*d*np.sqrt(4*r*r-d*d)
    assert np.isclose(scores['area_error'], 2*(np.pi*r*r-lens)/(np.pi*r*r), rtol=1e-5)
    assert np.isclose(scores['centroid_mm'], 10., rtol=1e-6) and scores['components'] == 1
    extra, _ = G.region([circle(.03), circle(.005, .06)])
    scores = G.region_scores(extra, truth)
    assert scores['components'] == 2 and np.isclose(scores['area_error'], (5/30)**2, rtol=1e-5)
    ring, _ = G.region([circle(.03), circle(.01)])
    scores = G.region_scores(ring, truth)
    assert (scores['components'], scores['holes']) == (1, 1) and np.isclose(scores['missing_area'], 1/9, rtol=1e-5)
    empty, _ = G.region([])
    assert G.region_scores(empty, truth)['area_error'] == 1. and G.region_scores(empty, truth)['centroid_mm'] is None
    assert G.boundary_scores(empty, truth)['boundary_rms_mm'] is None


def test_boundary_distances_of_concentric_circles():
    truth, _ = G.region([circle(.03, count=16384)])
    larger, _ = G.region([circle(.031, count=16384)])
    scores = G.boundary_scores(larger, truth)
    for key in ('boundary_rms_mm', 'chamfer_mm', 'hausdorff_mm'):
        assert np.isclose(scores[key], 1., atol=1e-4)
    assert scores['hausdorff_mm'] <= scores['hausdorff_upper_mm'] <= scores['hausdorff_mm']+.03
    # A far extra component dominates the Hausdorff distance and is not discarded.
    extra, _ = G.region([circle(.031, count=16384), circle(.002, .08)])
    assert np.isclose(G.boundary_scores(extra, truth)['hausdorff_mm'], 52., atol=1e-3)


def test_image_support_keeps_small_pieces_holes_and_the_sign_of_the_peak():
    x, y = D.pixel_grid(G.PROTOCOL['grid_cells'])
    r = np.hypot(x, y)
    chi = -.5*((r < .03) & (r > .01)).astype(float)-.4*(np.hypot(x-.07, y) < .004)
    rings, peak = G.support_rings(chi, .5)
    found, _ = G.region(rings)
    scores = G.region_scores(found, G.region([circle(.03)])[0])
    assert peak == -.5 and (scores['components'], scores['holes']) == (2, 1)
    assert np.isclose(found.area, np.pi*(.03**2-.01**2+.004**2), rtol=.02)
    assert G.support_rings(np.zeros_like(chi), .5) == ([], 0.)
    # A blob touching the grid edge still closes, because the grid is padded with background.
    edge, _ = G.region(G.support_rings((x > .09).astype(float), .5)[0])
    assert np.isclose(edge.area, .201*.010, rtol=.01)
