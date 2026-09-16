"""Pilot orchestration contracts; all objective calls below are analytic mocks."""
from dataclasses import replace
from pathlib import Path
import sys
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import run_top016_pilot as m
from sdf_inverse.runtime import inverse_runtime


def test_acceptance_requires_both_decreases_and_numerical_margin():
    assert m.acceptance(1.,.5,1.,.5)['accepted']
    assert not m.acceptance(1.,.5,1.,1.1)['accepted']
    assert not m.acceptance(1.,.5,1.,.9)['accepted']
    assert not m.acceptance(1e-10,1e-10-1e-15,1e-10,1e-10-1e-15)['accepted']
    assert m.acceptance(1e-10,1e-10-1e-12,1e-10,1e-10-1e-12)['accepted']


def test_stage_budget_cannot_borrow_and_endpoint_is_reserved():
    ledger=m.TrialLedger(8000,1800);ledger.begin_stage(1,1000)
    ledger.attempted['objective']=960
    ledger.reserve(28)
    with pytest.raises(m.p.Budget,match='endpoint reserve'):
        ledger.reserve(29)
    with ledger.endpoint_scope():ledger.reserve(40)
    assert ledger.total==960
    with pytest.raises(m.p.Budget):ledger.reserve(68)


def test_training_fit_interface_has_no_truth_or_evaluation_inputs():
    import inspect
    params=set(inspect.signature(m.fit_stage).parameters)
    assert params=={'initial','data','nodes','solve','optimizer','floor','ledger','output'}


def test_fit_stage_smoke_and_latest_state_retention(tmp_path,monkeypatch):
    state=m.p.driver.deserialize_state(m.p.benchmark.read(m.p.PLATEAU)['final_state'])
    data=m.p.training_data((.5e9,),np.ones((24,1),complex))
    initial_center=state.components[0].center[0]
    def objective(candidate,data,geometry,*,solve_config=None):
        value=candidate.components[0].center[0]-(initial_center-.001)
        prediction=np.ones((24,1),complex)+value
        residual,_=m.p.normalized_complex_residual(prediction,data.observed_scattered_response,data.frequency_weights)
        return m.rt.MultiRadialObjectiveEvaluation(candidate,.5*float(residual@residual),float(np.linalg.norm(residual)),residual,prediction,0.,0.)
    monkeypatch.setattr(m.rt,'evaluate_multiradial_objective',objective)
    controller=m.p.TopologyControllerConfig(**m.p.benchmark.read(m.p.DATA/'scene_spec.json')['controller'])
    optimizer=replace(m.p._optimizer_config(state,controller),max_iterations=1,loss_tolerance=1e-14)
    ledger=m.TrialLedger(8000,1800);ledger.begin_stage(1,1000)
    with inverse_runtime('reference'):  # This fixture supplies a synthetic FD residual.
        final,terminal=m.fit_stage(state,data,(128,256),m.p.driver.baseline.iteration01_solve_config(),optimizer,.008,ledger,tmp_path/'stage')
    assert terminal['failure_type'] is None
    assert terminal['accepted_steps']==1
    assert final.components[0].center[0]<initial_center
    assert ledger.total==0
    assert ledger.calls['cache_hit']>0
    assert (tmp_path/'stage/accepted_state.json').exists()
