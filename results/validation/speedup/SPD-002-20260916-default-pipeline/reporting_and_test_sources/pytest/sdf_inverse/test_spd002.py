"""Default runtime propagation, real continuation, and bounded analytic work."""
from dataclasses import replace
import json
import os
import subprocess
import sys
import numpy as np
import pytest
import run_top017 as continuation
from sdf_inverse import radial_topology as rt
from sdf_inverse import analytic_jacobian as aj
from sdf_inverse.runtime import current_runtime, inverse_runtime, jacobian_selection, inverse_execution
from sdf_inverse.work_accounting import analytic_work, observe_analytic_work, collect_work
from gpr_bem_kress.execution import execution, current_execution
from test_spd001 import setup_case


def test_default_profile_and_spawned_worker_inheritance(monkeypatch):
    monkeypatch.delenv('SDF_INVERSE_RUNTIME',raising=False)
    assert current_runtime().profile=='fast'
    state,*_=setup_case(1)
    assert jacobian_selection(state)=='analytic'
    radial=rt.MultiRadialFourierState((rt.circle_radial_fourier_state((.5,.5),.03,'r'),))
    assert jacobian_selection(radial)=='fd'
    monkeypatch.setenv('SDF_INVERSE_RUNTIME','reference')
    output=subprocess.check_output([sys.executable,'-c',
        'from sdf_inverse.runtime import runtime_metadata; import json; print(json.dumps(runtime_metadata()))'],env=os.environ,text=True)
    assert json.loads(output)['jacobian']=='fd'
    with inverse_runtime('fast'):
        assert current_runtime().profile=='fast'
    assert current_runtime().profile=='reference'


def test_explicit_execution_context_is_preserved_and_restored():
    @inverse_execution
    def selected():return current_execution().kernels
    with inverse_runtime('fast'):
        assert selected()=='real_bessel'
        with execution(kernels='reference'):
            assert selected()=='reference'
    assert current_execution() is None


def test_real_continuation_inherits_analytic_default_and_accounts_all_work(tmp_path,monkeypatch):
    monkeypatch.delenv('SDF_INVERSE_RUNTIME',raising=False)
    state,data,geometry,solve=setup_case(1)
    config=rt.ParameterFDConfig(max_iterations=1,max_parameters=64,finite_difference_steps=1e-4,
        gradient_tolerance=1e50,loss_tolerance=1e-30,infeasible_trial_policy='reject')
    ledger=continuation.Ledger(cap=1000,seconds=30);ledger.begin_stage(1,1000)
    with ledger.instrument(),collect_work() as passive:
        _,terminal=continuation.fit_stage(state,data,(32,64),solve,config,.008,ledger,tmp_path/'stage')
    assert terminal['stage_outcome']=='NORMAL_OPTIMIZER_RETURN',terminal['reason']
    assert terminal['effective_training_exposure']
    counts=passive.snapshot()['totals']
    assert counts['analytic_base_frequency_solve_count']==2
    assert sum(ledger.completed.values())==counts['bie_frequency_solve_count']
    assert sum(ledger.derivative_completed.values())==counts['derivative_assembly_count']>0
    assert ledger.budget_total==ledger.total+counts['derivative_assembly_count']
    assert json.loads((tmp_path/'stage/optimizer.json').read_text())['inverse_runtime']['profile']=='fast'


def test_analytic_work_cannot_escape_caps_or_failure_accounting():
    ledger=continuation.Ledger(cap=2,seconds=30)
    with observe_analytic_work(ledger.analytic_event):
        with analytic_work('base',2*np.pi*.5e9):pass
        with pytest.raises(ValueError,match='synthetic'):
            with analytic_work('direction',2*np.pi*.5e9):raise ValueError('synthetic')
        with pytest.raises(continuation.TrialSolveCap):
            with analytic_work('direction',2*np.pi*.5e9):pytest.fail('work beyond cap')
    assert ledger.total==1 and ledger.budget_total==2
    assert sum(ledger.derivative_failed.values())==1
    assert sum(ledger.derivative_attempted.values())==1
    # A removed observer cannot charge a later unrelated call.
    with analytic_work('base',1.):pass
    assert ledger.total==1


def test_stage_cap_counts_directions_but_retains_physical_solve_totals():
    ledger=continuation.Ledger(cap=100,seconds=30);ledger.begin_stage(1,14)
    with observe_analytic_work(ledger.analytic_event):
        for _ in range(2):
            with analytic_work('direction',1.):pass
        with pytest.raises(continuation.StageQuota):
            with analytic_work('base',1.):pytest.fail('endpoint reserve was lost')
    assert ledger.total==0 and ledger.budget_total==2
