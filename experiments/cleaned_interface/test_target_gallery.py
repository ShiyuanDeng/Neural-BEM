"""TG-001 target fixtures and case rows; no forward solves."""
import numpy as np
import pytest

from . import benchmark as b
from . import target_gallery as tg


def test_logo_glyph_is_the_vendored_closed_polygon():
    p = tg.logo_outline()
    assert len(p) == 190
    # The path closes with `z`; its last explicit vertex is one short edge from the first.
    assert abs(p[-1]-p[0]) < 30 and np.abs(np.diff(p)).max() > 30
    assert np.abs(p).max() < 2801.3  # glyph sits inside the logo's inner ring radius


@pytest.mark.parametrize('scene', tg.SCENES)
def test_truths_are_valid_ccw_curves_inside_the_domain(scene):
    truth = tg.truth_fixture(scene)
    nodes = truth.validate()
    assert nodes.signed_area > 0 and truth.band == tg.SCENES[scene]['band']
    z = tg.CENTER+tg.LENGTH*truth.values(4096)
    assert z.real.min() > .3 and z.real.max() < .7 and z.imag.min() > .3 and z.imag.max() < .7
    # Taper leaves the stored band negligible at its edge.
    c = np.abs(truth.coefficients)
    assert max(c[0], c[-1]) < 1e-3*c.max()


@pytest.mark.parametrize('scene', tg.SCENES)
def test_starts_are_off_centre_circles_disjoint_from_their_truths(scene):
    start = tg.start_fixture(scene)
    truth = tg.CENTER+tg.LENGTH*tg.truth_fixture(scene).values(4096)
    centre = complex(*tg.SCENES[scene]['start'])
    assert np.abs(truth-centre).min() > tg.START_RADIUS_M
    assert start.band == 1


def test_case_ids_and_rows_match_the_ci001_descriptor_shape():
    assert tg.case_id(13.3, 'aphex_twin') == 'target__c13.3__aphex_twin'
    rows = tg.descriptors()
    if not rows:
        pytest.skip('TG-001 inputs not generated')
    for row in rows:
        assert {'id', 'case', 'contrast', 'data', 'damped', 'initial', 'truth'} <= set(row)


def test_fitting_problem_never_opens_truth(monkeypatch):
    rows = tg.descriptors()
    if not rows:
        pytest.skip('TG-001 inputs not generated')
    row = rows[0]
    original = b.read

    def guarded(path):
        assert 'truth' not in str(path), 'fitting must not read truth'
        return original(path)
    monkeypatch.setattr(b, 'read', guarded)
    problem = b.fitting_problem(row, tg.DEFAULT_OUTPUT)
    assert problem.contrast == row['contrast'] and len(problem.real) == len(problem.damped) == 19
    assert complex(problem.damped[0].wavenumber).imag > 0
