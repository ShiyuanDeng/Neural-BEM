"""Numerical-control regression tests using a known analytic residual only."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest
import run_fourier_topology_controller as driver
from sdf_inverse import radial_topology as rt
from sdf_inverse.optimization import ParameterFDConfig

ROOT=Path(__file__).resolve().parents[2]
SOLVE=driver.baseline.iteration01_solve_config();GEOMETRY=driver.baseline._geometry_config(64)


def objective(state,data,geometry,*,solve_config=None):
    c=state.components[0]
    residual=np.array([c.mean_radius_m-.04,* (c.center-np.array([.5,.5]))])
    return rt.MultiRadialObjectiveEvaluation(state,.5*float(residual@residual),float(np.linalg.norm(residual)),residual,np.zeros((1,1),complex),0.,0.)


def initial():
    return rt.MultiRadialFourierState((rt.circle_radial_fourier_state((.6,.5),.03,'fixed'),))


def config(**kw):
    args=dict(max_iterations=3,max_parameters=32,finite_difference_steps=1e-4,max_steps=.01,
              initial_damping=1e5,gradient_tolerance=1e-12,relative_step_tolerance=1e-15,
              loss_tolerance=1e-4,infeasible_trial_policy='reject')
    args.update(kw);return ParameterFDConfig(**args)


def run(**kw):
    return rt.run_multiradial_fd_inverse(initial(),None,GEOMETRY,solve_config=SOLVE,config=config(),**kw)


def test_loss_change_disabling_is_separate_from_target(monkeypatch):
    monkeypatch.setattr(rt,'evaluate_multiradial_objective',objective)
    legacy=run();experimental=run(loss_change_stopping=False)
    assert legacy.stop_reason=='loss_change_tolerance'
    assert experimental.stop_reason=='maximum_iterations'
    assert len(legacy.iterations)==2 and len(experimental.iterations)==4
    high_target=rt.run_multiradial_fd_inverse(initial(),None,GEOMETRY,solve_config=SOLVE,
        config=config(loss_tolerance=.1),loss_change_stopping=False)
    assert high_target.stop_reason=='loss_tolerance'


def test_candidate_callback_can_reject_production_gain(monkeypatch):
    monkeypatch.setattr(rt,'evaluate_multiradial_objective',objective)
    probes=[]
    def refuse(base,candidate):
        assert candidate.loss<base.loss
        probes.append(candidate.loss)
        return False
    result=run(candidate_acceptance_callback=refuse)
    assert probes and result.stop_reason=='no_decreasing_step'
    np.testing.assert_array_equal(result.final_state.parameter_vector(),initial().parameter_vector())


def test_latest_accepted_state_saved_before_next_batch(monkeypatch):
    monkeypatch.setattr(rt,'evaluate_multiradial_objective',objective)
    states=[];batches=[]
    def checkpoint(iteration,evaluation):states.append((iteration,evaluation))
    def reserve(count):
        batches.append(count)
        if len(batches)==2:raise TimeoutError('next Jacobian cannot run')
    with pytest.raises(TimeoutError):
        run(loss_change_stopping=False,accepted_state_callback=checkpoint,jacobian_batch_callback=reserve)
    assert [i for i,_ in states]==[0,1]
    assert states[1][1].loss<states[0][1].loss
    assert batches==[2*initial().parameter_count]*2


def test_first_batch_reservation_prevents_any_fd_calls(monkeypatch):
    evaluations=[]
    def counted(*a,**k):evaluations.append(1);return objective(*a,**k)
    monkeypatch.setattr(rt,'evaluate_multiradial_objective',counted)
    def refuse(_):raise RuntimeError('batch limit')
    with pytest.raises(RuntimeError,match='batch limit'):
        run(jacobian_batch_callback=refuse)
    assert len(evaluations)==1 # base checkpoint only, no derivative probes


def test_default_trajectory_matches_archived_source(monkeypatch):
    name='sdf_inverse._top016_original'
    path=ROOT/'results/validation/topology/TOP-016-20260914-fixed-topology/phase1/radial_topology_source.py'
    spec=importlib.util.spec_from_file_location(name,path);old=importlib.util.module_from_spec(spec)
    sys.modules[name]=old;spec.loader.exec_module(old)
    monkeypatch.setattr(rt,'evaluate_multiradial_objective',objective)
    old.evaluate_multiradial_objective=objective;old.MultiRadialFourierState=rt.MultiRadialFourierState
    before=old.run_multiradial_fd_inverse(initial(),None,GEOMETRY,solve_config=SOLVE,config=config())
    after=run()
    assert before.stop_reason==after.stop_reason and before.evaluation_count==after.evaluation_count
    for a,b in zip(before.iterations,after.iterations):
        assert a.loss==b.loss and a.damping==b.damping
        np.testing.assert_array_equal(a.parameter_vector,b.parameter_vector)
        np.testing.assert_array_equal(a.gradient,b.gradient)
