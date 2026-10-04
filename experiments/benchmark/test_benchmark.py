"""TG-002 scenes, rows and the no-grid adapter; no forward solves."""
import numpy as np
import pytest

from experiments.cleaned_interface import benchmark as ci
from . import campaign as c, nl001, scenes as S


def test_ten_scenes_three_contrasts_one_start():
    assert len(S.SCENES) == 10 and len(S.CASES) == 30
    assert set(S.SHAPES) == set(S.PLACEMENTS) == set(S.SCENES)
    start = S.start_fixture()
    assert start.band == 1 and np.isclose(abs(start.coefficients[2])*S.LENGTH, S.START_RADIUS_M)
    assert abs(S.CENTER+S.LENGTH*start.coefficients[1]-S.START_CENTER_M) < 1e-15


@pytest.mark.parametrize('scene', S.SCENES)
def test_truth_is_valid_inside_domain_and_placed_as_frozen(scene):
    truth = S.truth_fixture(scene)
    assert truth.validate().signed_area > 0 and truth.band == S.SHAPES[scene]['band']
    z = S.CENTER+S.LENGTH*truth.values(4096)
    assert z.real.min() > .35 and z.real.max() < .65 and z.imag.min() > .35 and z.imag.max() < .65
    q = np.roll(z, -1)
    cross = z.real*q.imag-q.real*z.imag
    centroid = ((z+q)*cross).sum()/(3*cross.sum())
    assert 21 <= 1000*abs(centroid-S.START_CENTER_M) <= 39  # visibly off-centre, inside recorded capture range


def test_placements_are_the_frozen_preregistered_values():
    assert {s: (p['offset_mm'], p['direction_deg'], p['rotation']) for s, p in S.PLACEMENTS.items()} == dict(
        circle=(22, 35, 0.), kite=(30, 150, .5), peanut=(34, 255, 1.1), star=(26, 320, .41),
        asymmetric=(38, 80, -.32), c_shape=(30, 205, .3), hook=(26, 290, 2.4), cross=(34, 15, .35),
        cog=(22, 170, .17), aphex_twin=(38, 235, 0.))


def test_logo_glyph_is_the_vendored_closed_polygon():
    p = S.logo_outline()
    assert len(p) == 190 and abs(p[-1]-p[0]) < 30 and np.abs(p).max() < 2801.3


def test_keep_start_skips_the_grid_and_returns_the_start():
    class Ledger:
        reserved = []

        def reserve(self, units):
            self.reserved.append(units)
    seen = []
    problem = type('P', (), dict(initial=S.start_fixture()))()
    curve, record = c.keep_start(problem, None, None, Ledger(), seen.append)
    assert curve is problem.initial and record['grid_search'] is False and Ledger.reserved == [0] and seen


def test_nl001_arms_differ_only_in_localization():
    a, b = nl001.ARMS['A'], nl001.ARMS['B']
    assert {k for k in a if a[k] != b[k]} == {'localization'}
    assert a['solver'] == 'modal_muller' and a['geometry_update'] == 'certified_spectral'
    assert nl001.WORKERS <= c.MAX_WORKERS


def test_rows_never_expose_truth_to_fitting(monkeypatch):
    rows = c.descriptors()
    if not rows:
        pytest.skip('TG-002 inputs not generated')
    assert [r['id'] for r in rows] == list(S.CASES)
    original = ci.read

    def guarded(path):
        assert 'truth' not in str(path), 'fitting must not read truth'
        return original(path)
    monkeypatch.setattr(ci, 'read', guarded)
    problem = ci.fitting_problem(rows[0], c.INPUTS)
    assert len(problem.real) == len(problem.damped) == 19 and complex(problem.damped[0].wavenumber).imag > 0
