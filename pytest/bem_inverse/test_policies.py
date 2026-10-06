"""The policy registry: one declared change per entry, buildable recipes, compact storage."""
from dataclasses import asdict, fields

import pytest

from bem_inverse import policies as R
from bem_inverse.continuation_policy import ShapeFrequencyPolicy
from bem_inverse.modal_muller import ModalMuller
from bem_inverse.physics import Execution
from bem_inverse.policy import CumulativePolicy
from test_continuation_policy import fixture


def test_every_lineage_starts_at_baseline_and_statuses_are_known():
    assert R.lineage('baseline') == ('baseline',)
    for name, entry in R.POLICIES.items():
        assert R.lineage(name)[0] == 'baseline'
        assert entry.status in R.STATUSES
        assert entry.change and entry.evidence


def test_each_entry_changes_exactly_what_it_declares():
    for name, entry in R.POLICIES.items():
        if entry.parent is None:
            continue
        declared = {f'options.{k}' for k, _ in entry.options} | {f'execution.{k}' for k, _ in entry.execution}
        declared |= {'schedule'} if entry.schedule else set()
        declared |= {'pipeline'} if entry.pipeline else set()
        assert set(R.difference(entry.parent, name)) == declared, name


def test_exact_entries_change_only_how_work_is_done():
    for entry in R.POLICIES.values():
        if entry.exact:
            assert not entry.options and entry.schedule is None and entry.pipeline is None, entry.name
            assert {k for k, _ in entry.execution} <= {'validity_order', 'stage_entry_reuse'}


def test_archived_recipes_resolve_to_their_recorded_settings():
    recipe = R.recipe('four_phase')
    assert (recipe.schedule, recipe.pipeline) == ('four_phase', 'modal_fixed')
    assert recipe.options == dict(required_accuracy=.003, damping_rule='agreement', avoid_terminal_linearization=True)
    assert recipe.execution == dict(audit_frequency_batch=2)
    assert R.recipe('decision_gate').options == dict(required_accuracy=.003, resolution_gate='decision')
    assert R.recipe('adaptive_resolution').pipeline == 'modal_response'
    assert R.recipe('adaptive_resolution').execution == dict(
        audit_frequency_batch=2, validity_order='sampled_first', stage_entry_reuse=True)


def test_build_applies_the_contract_uniformly():
    for name in R.POLICIES:
        built = R.build(name, **R.BENCHMARK_CONTRACT)
        assert isinstance(built, ShapeFrequencyPolicy if name == 'four_phase' else CumulativePolicy)
        assert {k: getattr(built, k) for k in R.CONTRACT} == R.BENCHMARK_CONTRACT
    with pytest.raises(ValueError, match='Contract fields'):
        R.build('baseline', required_accuracy=.001)
    with pytest.raises(ValueError, match='not a policy option'):
        R.Policy('x', 'baseline', 'x', 'candidate', options=(('fit_seconds', 1.),))
    with pytest.raises(ValueError, match='not a policy execution option'):
        R.Policy('x', 'baseline', 'x', 'candidate', execution=(('device', 'cpu'),))


def test_execution_keeps_devices_and_adds_policy_options():
    base = Execution(device='cpu', frequency_threads=2)
    built = R.execution_for('exact_fast', base)
    assert (built.device, built.frequency_threads) == ('cpu', 2)
    assert (built.validity_order, built.stage_entry_reuse, built.audit_frequency_batch) == ('sampled_first', True, 2)
    assert R.execution_for('baseline', base) == base


def test_fit_owns_policy_and_pipeline_slots():
    with pytest.raises(ValueError, match='policy sets'):
        R.fit(None, 'baseline', policy=CumulativePolicy())
    with pytest.raises(ValueError, match='policy sets'):
        R.fit(None, 'baseline', solver='nodal_kress')


def test_every_policy_plans_on_a_problem():
    problem, physics = fixture(), ModalMuller(Execution(device='cpu'))
    for name in R.POLICIES:
        plan = R.build(name, **R.BENCHMARK_CONTRACT).plan(problem, physics)
        assert plan['operations'][0]['operation'] == 'audit' and plan['operations'][-1]['operation'] == 'audit'


def test_compact_storage_changes_only_full_catalog_storage():
    problem, physics = fixture(), ModalMuller(Execution(device='cpu'))
    fixed = CumulativePolicy().operations(problem, physics)
    compact = CumulativePolicy(release_storage='compact').operations(problem, physics)
    assert [o.label for o in fixed] == [o.label for o in compact]
    for a, b in zip(fixed, compact):
        if a.kind != 'fit':
            continue
        if a.label.startswith(('release_', 'fixed_')):
            assert a.stage.observations is b.stage.observations and len(a.stage.observations) == len(problem.real)
            assert a.stage.curve_modes == 192
            assert b.stage.curve_modes == 2*b.stage.update_modes+2
            assert b.stage.nodes <= a.stage.nodes
        else:
            assert a.record() == b.record()
    tail = CumulativePolicy(release_storage='compact').tail(problem, physics, 50)
    assert [(o.stage.update_modes, o.stage.curve_modes) for o in tail if o.kind == 'fit'] == [(43, 88), (49, 100), (55, 112)]
    assert all(o.stage.curve_modes == 192 for o in CumulativePolicy().tail(problem, physics, 50) if o.kind == 'fit')
    with pytest.raises(ValueError, match='release_storage'):
        CumulativePolicy(release_storage='tight')
    with pytest.raises(ValueError, match='do not apply|does not apply'):
        ShapeFrequencyPolicy(release_storage='compact').operations(problem, physics)


def test_default_policy_fields_are_unchanged():
    # New fields are neutral; the archived defaults remain the established recipe.
    defaults = asdict(CumulativePolicy())
    assert defaults['release_storage'] == 'fixed' and defaults['storage_band'] == 192
    assert {f.name for f in fields(Execution)} >= {'validity_order', 'stage_entry_reuse'}
    assert (Execution().validity_order, Execution().stage_entry_reuse) == ('certificate_first', False)
