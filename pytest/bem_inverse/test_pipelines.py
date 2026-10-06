"""Named pipelines fill fit()'s slots and add no numerics."""
import pytest

from bem_inverse import pipelines as P
from bem_inverse.geometry_selection import make_update
from bem_inverse.physics import Execution, NodalKress


def test_presets_and_their_slots():
    assert set(P.PIPELINES) == {'nodal_baseline', 'nodal_fixed', 'modal_fixed', 'modal_response'}
    base, fixed, modal = (P.get(n) for n in ('nodal_baseline', 'nodal_fixed', 'modal_fixed'))
    response = P.get('modal_response')
    assert (response.solver, response.geometry_update, response.resolution_response) == (
        'modal_muller', 'certified_spectral', (1024, 1280))
    assert {k for k, v in response.settings().items() if modal.settings()[k] != v} == {
        'name', 'resolution_response', 'description'}
    assert (base.solver, base.geometry_update, base.resolution_response) == ('nodal_kress', 'spline', None)
    assert (fixed.solver, fixed.geometry_update, fixed.resolution_response) == ('nodal_kress', 'certified_spectral', (1024, 2048))
    assert (modal.solver, modal.geometry_update, modal.resolution_response) == ('modal_muller', 'certified_spectral', None)
    # The two fixed pipelines differ only in physics and the nodal-only response.
    assert {k for k, v in fixed.settings().items() if modal.settings()[k] != v} == {
        'name', 'solver', 'resolution_response', 'description'}


def test_baseline_geometry_is_fit_default():
    execution = Execution(device='cpu', frequency_threads=1)
    from bem_inverse.geometry import ProjectedUpdate
    assert type(make_update('spline', .05, execution)) is type(make_update(None, .05, execution, default=ProjectedUpdate))


def test_components_are_built_from_the_recipe(monkeypatch):
    from bem_inverse import physics
    # Registering modal here must not leak into suites that expect it unregistered.
    monkeypatch.setattr(physics, '_BACKENDS', dict(physics._BACKENDS))
    execution = Execution(device='cpu', frequency_threads=2)
    assert P.resolution_response('nodal_baseline', execution) is None
    assert P.resolution_response('modal_fixed', execution) is None
    response = P.resolution_response('nodal_fixed', execution)
    assert (response.production_nodes, response.refined_nodes) == (1024, 2048)
    assert isinstance(response.physics, NodalKress) and response.physics.execution.resolution == 1024
    assert response.physics.execution.device == 'cpu' and response.physics.execution.frequency_threads == 2
    assert type(P.physics('nodal_fixed', execution)) is NodalKress
    assert P.physics('modal_fixed', execution).name == 'modal_muller'


def test_modal_resolution_response_uses_trace_tokens():
    # Tokens are 8*K_trace; the modal response promotes inside the same service.
    P.Pipeline('x', 'modal_muller', 'certified_spectral', (1024, 1280))
    with pytest.raises(ValueError, match='multiples of 8'):
        P.Pipeline('x', 'modal_muller', 'certified_spectral', (1024, 1284))
    response = P.resolution_response('modal_response', Execution(device='cpu', frequency_threads=1))
    assert (response.production_nodes, response.refined_nodes, response.physics) == (1024, 1280, None)
    with pytest.raises(ValueError):
        P.Pipeline('x', 'nodal_kress', 'certified_spectral', (1024, 1024))
    with pytest.raises(ValueError, match='Unknown pipeline'):
        P.get('nodal')


def test_pipeline_owns_its_slots():
    with pytest.raises(ValueError, match='pipeline sets'):
        P.fit(None, 'modal_fixed', solver='nodal_kress')


def test_promotion_is_read_from_stage_resolutions():
    result = dict(stages=[dict(nodes=512), dict(nodes=1024)])
    assert P.promoted(result, 'nodal_fixed') and not P.promoted(dict(stages=[dict(nodes=512)]), 'nodal_fixed')
    assert not P.promoted(result, 'nodal_baseline')
    # Recorded events decide: a compact modal stage may start at the ceiling profile by itself.
    native = dict(stages=[dict(nodes=512, resolution_events=[]), dict(nodes=1024, resolution_events=[])])
    assert not P.promoted(native, 'modal_response')
    native['stages'][0]['resolution_events'] = [dict(action='promoted', nodes=1024)]
    assert P.promoted(native, 'modal_response')
