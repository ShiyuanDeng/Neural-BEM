"""Regressions for NF-001's numerical tangent and public geometry integration."""
import numpy as np
import pytest

from .analytic_projection import AnalyticSpectralUpdate, projection_derivatives
from .geometry import resize
from .geometry_selection import make_update
from .io import read, write, portable
from .modal_geometry import log_modulus
from .modal_muller import ModalMuller
from .nu003 import spectral_project
from .nu005 import CertifiedSpectralUpdate
from .physics import Execution, NodalKress
from .policy import CumulativePolicy
from .test_audit_streaming import fixture
from .test_nu005 import kite
from . import runner, benchmark


@pytest.mark.parametrize('count', [64, 65, 1024])
def test_derivative_of_actual_discrete_projection(count):
    curve, M, unit = kite(8), 5, .05
    tangent = projection_derivatives(curve, M, 8, count, unit)
    direction = np.random.default_rng(504).normal(size=2*M+1)
    direction /= np.linalg.norm(direction)
    errors = []
    for step in (1e-5, 5e-6, 1e-7):
        plus, minus = [spectral_project(curve, sign*step*direction, 8, count, unit)[0] for sign in (1, -1)]
        errors.append(np.linalg.norm((plus-minus)/(2*step)-tangent@direction)/np.linalg.norm(tangent@direction))
    assert errors[1] < .3*errors[0]  # centered-difference truncation converges quadratically
    assert errors[2] < 1e-7


def test_analytic_update_preserves_the_finite_trial_and_resets_zero_step_records():
    curve = resize(kite(8), 8)
    finite, analytic = CertifiedSpectralUpdate(.05), AnalyticSpectralUpdate(.05)
    a, b = finite.prepare(curve, 3, 8), analytic.prepare(curve, 3, 8)
    np.testing.assert_array_equal(a.base_projection, b.base_projection)
    step = np.random.default_rng(5).normal(size=7)*1e-5
    x, ix = finite.trial(a, step)
    y, iy = analytic.trial(b, step)
    np.testing.assert_array_equal(x.coefficients, y.coefficients)
    assert ix['validity_tiers'] == iy['validity_tiers']
    assert analytic.records
    analytic.trial(b, np.zeros(7))
    assert analytic.records == []


@pytest.mark.parametrize('selection', ['spline', 'spectral', 'certified_spectral', 'analytic_spectral'])
def test_runner_records_the_selected_geometry_without_global_substitution(selection, tmp_path):
    before = runner.ProjectedUpdate
    updates = []
    def audit(curve, stage, config, problem, physics, update, seconds):
        updates.append(update)
        return dict(passed=False, work=dict(work_units=0), seconds=0.)
    execution = Execution(device='cpu', frequency_threads=1)
    row = runner.fit(fixture(), physics=NodalKress(execution), geometry_update=selection,
                     policy=CumulativePolicy(prefix_frequencies_hz=(.375e9, .5e9, .75e9, 1e9)),
                     audit_adapter=audit, output=tmp_path)
    assert runner.ProjectedUpdate is before
    assert type(updates[0]) is type(make_update(selection, .05, execution))
    settings = row['geometry_settings']
    assert row['geometry_update'] == selection
    plan = read(tmp_path/'plan.json')
    assert plan['geometry'] == portable(settings)
    assert all(op['geometry_update'] == settings['construction'] for op in plan['operations'] if 'stage' in op)
    if selection == 'certified_spectral':
        assert settings['prepare_device'] == 'cpu'


def test_campaign_refuses_mixing_geometry_selections(monkeypatch, tmp_path):
    execution = Execution(device='cpu')
    monkeypatch.setattr(benchmark, 'verify', lambda *a, **kw: dict(cases=[]))
    write(tmp_path/'execution.json', dict(settings=dict(solver='nodal_kress',
          execution=benchmark.asdict(execution), workers=1, geometry_update='spectral')))
    with pytest.raises(ValueError, match='mix execution settings'):
        benchmark.run(tmp_path, execution, geometry_update='certified_spectral')


def test_receipts_distinguish_samples_from_collocation_and_exact_from_float_arithmetic():
    ww = np.zeros((3, 3), complex)
    ww[1, 1] = 1
    _, interval = log_modulus(ww, 4)
    assert interval['proposal_grid'] >= 64
    assert interval['certificate']['arithmetic_verified'] is False
    sampling = ModalMuller(Execution(device='cpu')).receipt()['sampling']
    assert not sampling['operator_boundary_collocation'] and sampling['interval_proposal_torus_grid']
    assert not sampling['end_to_end_sample_free']


@pytest.mark.parametrize('tolerance', [0, -1, np.inf, np.nan])
def test_invalid_interval_tolerance_is_refused(tolerance):
    with pytest.raises(ValueError, match='Positive finite'):
        log_modulus(np.ones((1, 1), complex), 2, tolerance=tolerance)
