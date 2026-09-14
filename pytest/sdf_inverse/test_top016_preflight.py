"""TOP-016 preflight contracts with no physical forward solves."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('top016_preflight',ROOT/'run_top016_preflight.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_padding_preserves_ids_coefficients_and_geometry():
    c=m.driver.deserialize_state(m.benchmark.read(m.DATA/'runs/H/central-ellipse-star/metrics.json')['final_state'])
    result=m.padded(c)
    assert [x.component_id for x in result.components]==[x.component_id for x in c.components]
    assert [x.maximum_mode for x in result.components]==[9,9]
    for a,b in zip(m.boundary_points(c),m.boundary_points(result)):
        np.testing.assert_allclose(a,b,rtol=0,atol=1e-14)


def test_padding_refuses_truncation():
    c=m.driver.deserialize_state(m.benchmark.read(m.PLATEAU)['final_state'])
    larger=m.MultiRadialFourierState(tuple(m.zero_padded_component(x,10) for x in c.components))
    with pytest.raises(m.Obstruction,match='truncation'):
        m.padded(larger)


def test_training_normalization_order_and_scale():
    observed=np.arange(1,97).reshape(24,4)*(1+2j)
    predicted=observed+np.arange(96).reshape(24,4)*(.01-.02j)
    data=m.training_data(m.TRAIN,observed)
    residual,_=m.normalized_complex_residual(predicted,observed,data.frequency_weights)
    reference=np.concatenate([np.r_[(predicted[:,i]-observed[:,i]).real,
        (predicted[:,i]-observed[:,i]).imag]/np.linalg.norm(observed[:,i])/2 for i in range(4)])
    assert residual@residual==pytest.approx(reference@reference,rel=1e-14)
    matrix=(predicted-observed)/np.linalg.norm(observed,axis=0)/2
    np.testing.assert_array_equal(residual,np.r_[matrix.real.ravel(),matrix.imag.ravel()])


def test_training_excludes_evaluation_and_unusable_observations():
    with pytest.raises(ValueError,match='evaluation-only'):
        m.training_data((1.5e9,),np.ones((24,1)))
    with pytest.raises(m.Obstruction,match='norm'):
        m.training_data((.5e9,),np.zeros((24,1)))


def test_inputs_preserve_frozen_observation_bytes_and_retained_state(tmp_path):
    _,_,states,_,_,manifest=m.load_inputs(tmp_path)
    for name in m.SCENES:
        assert (tmp_path/'inputs'/name/'observations.json').read_bytes()==(m.DATA/'scenes'/name/'observations.json').read_bytes()
        assert manifest[name]['observations_sha256']==manifest[name]['portable_observations_sha256']
    retained=m.driver.deserialize_state(m.benchmark.read(m.PLATEAU)['final_state'])
    np.testing.assert_array_equal(states['far-two-stars'].parameter_vector(),retained.parameter_vector())


def test_budget_reserves_batch_before_attempt_and_checks_time():
    now=[0.];ledger=m.Ledger(cap=5,seconds=10,clock=lambda:now[0])
    ledger.attempted['x']=3
    ledger.reserve(2)
    with pytest.raises(m.Budget,match='cannot fit'):
        ledger.reserve(3)
    assert ledger.total==3
    now[0]=10
    with pytest.raises(m.Budget,match='wall-clock'):
        ledger.reserve(1)


def test_frequency_attempts_partial_failure_and_restoration(monkeypatch):
    calls=[]
    def forward(*_,**__):
        calls.append(1)
        if len(calls)==2:
            raise RuntimeError('physical failure')
        return 'ok'
    monkeypatch.setattr(m.physical,'solve_multicomponent_kress_tmz_total_field_batch',forward)
    ledger=m.Ledger(cap=3)
    with ledger.instrument(),ledger.category_scope('validation'):
        assert m.physical.solve_multicomponent_kress_tmz_total_field_batch()=='ok'
        with pytest.raises(RuntimeError):
            m.physical.solve_multicomponent_kress_tmz_total_field_batch()
    assert m.physical.solve_multicomponent_kress_tmz_total_field_batch is forward
    assert ledger.snapshot()['attempted']=={'validation':2}
    assert ledger.snapshot()['completed']=={'validation':1}
    assert ledger.snapshot()['failed']=={'validation':1}


def test_prediction_batch_cannot_begin_if_over_budget(monkeypatch):
    monkeypatch.setattr(m.physical,'predict_multicomponent_kress_paired_boundary_response',
                        lambda *a,**k:pytest.fail('over-budget batch began'))
    ledger=m.Ledger(cap=3)
    with pytest.raises(m.Budget):
        m.prediction(None,m.TRAIN,64,None,ledger,'validation')
    assert ledger.total==0
