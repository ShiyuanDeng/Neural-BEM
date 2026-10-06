"""Each registry policy reproduces the settings its archived TG-002 experiment recorded."""
from dataclasses import asdict, fields
import json

import pytest

from bem_inverse import policies as R
from bem_inverse.physics import Execution
from . import campaign as c

ARCHIVE = c.ROOT/'results/validation/cleaned_interfaces'
# (policy, archived receipt, key holding asdict(policy)) for one case per archived arm.
ARMS = [
    ('baseline', 'ON-001/all_B', 'on001_settings'),
    ('accuracy_exit', 'ON-001/all_E', 'on001_settings'),
    ('reach_clip', 'ON-001/screen_G', 'on001_settings'),
    ('working_frequencies', 'ON-001/screen_EW', 'on001_settings'),
    ('accuracy_exit', 'RG-001/all/C', 'rg001_settings'),
    ('decision_gate', 'RG-001/all/RG', 'rg001_settings'),
    ('feedback', 'DP-001/F_screen', 'policy'),
    ('feedback', 'CS-001/control', 'policy_settings'),
    ('four_phase', 'CS-001/revised', 'policy_settings'),
]


def portable(value):
    return json.loads(json.dumps(value))


def matches(archived, current, defaults):
    """Archived keys equal; keys added since the archive hold their neutral defaults."""
    assert {k: archived[k] for k in archived} == {k: current[k] for k in archived}
    assert {k: current[k] for k in set(current)-set(archived)} == {k: defaults[k] for k in set(current)-set(archived)}


@pytest.mark.parametrize('policy, arm, key', ARMS)
def test_registry_reproduces_the_archived_policy_and_execution(policy, arm, key):
    receipt = json.loads((ARCHIVE/arm/'runs'/'circle__c4'/'result.json').read_text())
    built = R.build(policy, **R.BENCHMARK_CONTRACT)
    defaults = portable(asdict(type(built)()))
    matches(portable(receipt[key]), portable(asdict(built)), defaults)
    execution = R.execution_for(policy, Execution(device='cuda', frequency_threads=4))
    matches(portable(receipt['physics']['execution']), portable(asdict(execution)), portable(asdict(Execution())))
    assert receipt['geometry_update'] == c.P.get(R.recipe(policy).pipeline).geometry_update


def test_every_archived_tg002_recipe_is_registered():
    archived = {policy for policy, _, _ in ARMS}
    assert archived == {'baseline', 'accuracy_exit', 'reach_clip', 'working_frequencies', 'decision_gate',
                        'feedback', 'four_phase'}
    assert all(R.get(name).status in ('default', 'qualified', 'experimental', 'candidate', 'rejected') for name in archived)


def test_policy_runs_carry_one_setting_per_directory():
    settings = c.settings_for(localization='none', execution=Execution(device='cuda', frequency_threads=4),
                              policy='exact_fast')
    assert settings['policy']['recipe']['name'] == 'exact_fast'
    assert settings['policy']['contract'] == R.BENCHMARK_CONTRACT
    assert settings['execution']['validity_order'] == 'sampled_first' and settings['execution']['stage_entry_reuse']
    with pytest.raises(ValueError, match='Choose one'):
        c.settings_for(localization='none', execution=Execution(), policy='baseline', pipeline='modal_fixed')
    with pytest.raises(ValueError, match='named policies only'):
        c.settings_for(localization='none', execution=Execution(), pipeline='modal_fixed', contract={})
    assert {f.name for f in fields(Execution)} >= set(settings['execution'])
