"""Named pipelines fill fit()'s slots and add no numerics."""
import pytest

from bem_inverse import pipelines as P
from bem_inverse.geometry_selection import make_update
from bem_inverse.physics import Execution
from bem_inverse.forward_solvers.nodal_kress import NodalKress


def test_presets_and_their_slots():
    assert set(P.PIPELINES) == {'nodal_baseline', 'nodal_fixed', 'modal_fixed'}
    base, fixed, modal = (P.get(n) for n in ('nodal_baseline', 'nodal_fixed', 'modal_fixed'))
    assert (base.solver, base.geometry_update) == ('nodal_kress', 'spline')
    assert (fixed.solver, fixed.geometry_update) == ('nodal_kress', 'spectral')
    assert (modal.solver, modal.geometry_update) == ('modal_muller', 'spectral')
    # The two fixed pipelines differ only in physics.
    assert {k for k, v in fixed.settings().items() if modal.settings()[k] != v} == {'name', 'solver', 'description'}
    with pytest.raises(ValueError, match='Unknown pipeline'):
        P.get('nodal')


def test_geometry_defaults_preserve_spline_and_batch_spectral():
    execution = Execution(device='cpu', frequency_threads=1)
    from bem_inverse.geometry_update_methods.spline import ProjectedUpdate
    assert type(make_update('spline', .05, execution)[0]) is type(make_update(None, .05, execution)[0]) is ProjectedUpdate
    spectral, _ = make_update(P.get('modal_fixed').geometry_update, .05, execution)
    assert spectral.batched and spectral.device == 'cpu'
    assert 'certificate' not in spectral.settings()['validity']


def test_components_are_built_from_the_recipe(monkeypatch):
    from bem_inverse import physics
    # Registering modal here must not leak into suites that expect it unregistered.
    monkeypatch.setattr(physics, '_BACKENDS', dict(physics._BACKENDS))
    execution = Execution(device='cpu', frequency_threads=2)
    assert type(P.physics('nodal_fixed', execution)[0]) is NodalKress
    assert P.physics('modal_fixed', execution)[0].name == 'modal_muller'


def test_pipeline_owns_its_slots():
    with pytest.raises(ValueError, match='pipeline sets'):
        P.fit(None, 'modal_fixed', solver='nodal_kress')
