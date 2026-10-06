"""TG-002 scenes, rows and the no-grid adapter; no forward solves."""
import numpy as np
import pytest

from experiments.cleaned_interface import benchmark as ci
from . import campaign as c, nl001, pc001, scenes as S


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


def test_pc001_arms_are_the_three_pipelines_with_shared_settings():
    from bem_inverse.pipelines import PIPELINES
    assert pc001.ARMS == dict(N0='nodal_baseline', N1='nodal_fixed', M1='modal_fixed')
    assert set(pc001.ARMS.values()) <= set(PIPELINES) and set(pc001.RUN_ORDER) == set(pc001.ARMS)
    assert pc001.LOCALIZATION == 'none' and pc001.WORKERS <= c.MAX_WORKERS


def test_run_refuses_mixed_method_selection(tmp_path):
    from bem_inverse.physics import Execution
    with pytest.raises(ValueError, match='Choose one of a policy, a pipeline, or solver/geometry_update'):
        c.run(tmp_path, [], pipeline='modal_fixed', solver='modal_muller', localization='none', execution=Execution())
    with pytest.raises(ValueError, match='both solver'):
        c.run(tmp_path, [], solver='modal_muller', localization='none', execution=Execution())


def test_run_case_routes_pipeline_settings(tmp_path, monkeypatch):
    seen = {}

    def fake(problem, name, **options):
        seen.update(name=name, adapter=options['localization_adapter'])
        raise RuntimeError('stop after routing')
    monkeypatch.setattr(c.P, 'fit', fake)
    monkeypatch.setattr(c.ci, 'fitting_problem', lambda row, run_dir: None)
    settings = dict(pipeline=dict(name='nodal_fixed'), localization='none',
                    execution=dict(device='cpu', frequency_threads=1))
    result = c.run_case((tmp_path, dict(id='circle__c0.5'), settings))
    assert seen == dict(name='nodal_fixed', adapter=c.keep_start)
    assert result['outcome'] == 'WORKER_EXCEPTION' and 'stop after routing' in result['traceback']


def test_pc001_report_on_synthetic_runs(tmp_path):
    if not c.descriptors():
        pytest.skip('TG-002 inputs not generated')
    from bem_inverse.io import curve_record, write
    outcomes = dict(N0=(True, 'COMPLETED_SCHEDULE', 512), N1=(True, 'COMPLETED_SCHEDULE', 1024),
                    M1=(False, 'NUMERICAL_FAILURE', None))
    for arm, (recovered, outcome, nodes) in outcomes.items():
        for case in ('circle__c0.5', 'c_shape__c13.3'):
            scene, _ = case.rsplit('__', 1)
            write(tmp_path/arm/'runs'/case/'result.json', dict(
                case=c.row(case), recovered=recovered and scene == 'circle', outcome=outcome,
                metrics=dict(rms_mm=.1, hausdorff_upper_mm=.2), maximum_residual=1e-4, final_audit_passed=True,
                total_units=10, total_seconds=dict(N0=300., N1=200., M1=100.)[arm],
                resolution_promoted=nodes == 1024, stages=[dict(stage='stage_4_undamped', nodes=nodes)],
                final_curve=curve_record(S.truth_fixture(scene))))
    summary = pc001.report(tmp_path)
    assert summary['arms']['N1']['promoted'] == 2 and summary['arms']['M1']['recovered'] == 0
    assert summary['pairs'][0] == dict(compared=2, both=0, neither=1, only_first=[], only_second=['circle__c0.5'])
    assert all(v == 'pending' for v in summary['readings'].values())  # 2 of 30 cases
    assert {p.name for p in tmp_path.iterdir()} >= {'report.json', 'report.md', 'comparison.csv', 'comparison.png'}
    assert '| M1 vs N1 | 2 | 0 | 1 | — | circle__c0.5 |' in (tmp_path/'report.md').read_text()
