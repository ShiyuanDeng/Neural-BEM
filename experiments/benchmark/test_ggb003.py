"""Block-controller accounting and its subspace stopping semantics."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.lm_backend import BackendConfig, FitStage, Ledger, StageResult
from .ggb003 import fit_record, stage_one


def test_blocks_carry_separate_damping_and_share_quota(monkeypatch):
    import bem_inverse.continuation.lm_backend as lm
    calls = []
    curve = FourierCurve.circle(.2)
    stage = FitStage('T_M3',(object(),),(1.,),(1e-4,),3,1,64,96,2,200)
    ledger = Ledger(cap=500,seconds=30,endpoint_reserve=0)
    ledger.begin_stage(stage.label,stage.quota)
    shape = SimpleNamespace(length_unit_m=1.,name='shape')
    config = BackendConfig()

    def fake_fit(current, substage, contrast, update, cfg, shared, **kwargs):
        assert shared is ledger and shared.stage == 'T_M3'
        assert substage.iterations == 1
        kind = 'shape' if update is shape else 'translation'
        calls.append((kind,cfg.initial_damping))
        shared.reserve(1)
        shared.charge('solve','test')
        # First translation is stationary; shape must still run.
        count = 0 if len(calls)==1 else 1
        initial = 10.-len(calls)
        history = [dict(iteration=0,next_damping=cfg.initial_damping,
                        coefficients=dict(real=current.coefficients.real.tolist(),
                                          imag=current.coefficients.imag.tolist()))]
        final = current
        if count:
            c = current.coefficients.copy();c[current.band] += .001
            final = FourierCurve(c)
            history.append(dict(iteration=1,next_damping=.3*cfg.initial_damping,
                coefficients=dict(real=final.coefficients.real.tolist(),imag=final.coefficients.imag.tolist())))
        return StageResult(substage.label,final,'NORMAL_OPTIMIZER_RETURN',
            'gradient_tolerance' if not count else None,not count,count,initial,initial-.1*count,
            history,[],[],work=shared.snapshot())

    monkeypatch.setattr(lm,'fit_stage',fake_fit)
    final, row = stage_one(curve,stage,1.4,shape,config,ledger,object())
    assert calls == [('translation',.001),('shape',.001),('translation',.001),('shape',.0003)]
    assert ledger.snapshot()['stage_units'] == 4
    assert row['accepted_steps'] == 3
    assert not row['converged']
    assert [h['iteration'] for h in row['history']] == [0,1,2,3]
    np.testing.assert_allclose(final.coefficients[1],.003)


def test_translation_numerical_failure_stops_before_shape(monkeypatch):
    import bem_inverse.continuation.lm_backend as lm
    curve = FourierCurve.circle(.2)
    stage = FitStage('T_M3',(object(),),(1.,),(1e-4,),3,1,64,96,100,200)
    ledger = Ledger(cap=500,seconds=30)
    ledger.begin_stage(stage.label,stage.quota)
    calls = []
    def fail(current, substage, *args, **kwargs):
        calls.append(substage.label)
        return StageResult(substage.label,current,'NUMERICAL_FAILURE',None,False,0,1.,1.,
                           [],[],[],detail='fixture failure')
    monkeypatch.setattr(lm,'fit_stage',fail)
    _,row = stage_one(curve,stage,1.4,SimpleNamespace(length_unit_m=1.),BackendConfig(),ledger,object())
    assert len(calls)==1 and calls[0].endswith('_translation')
    assert row['outcome']=='NUMERICAL_FAILURE'
    assert row['detail']=='fixture failure'


def test_explicit_translation_refuses_later_stages():
    stage = FitStage('T_M7',(object(),),(1.,),(1e-4,),7,1,64,96,100,200)
    with pytest.raises(ValueError, match='only in M3'):
        stage_one(FourierCurve.circle(), stage, 1.4, None, None, None, None)


def test_acceptance_survives_quota_in_terminal_linearization(monkeypatch):
    import bem_inverse.continuation.lm_backend as lm
    curve = FourierCurve.circle(.2)
    final = FourierCurve.circle(.2, .01-.02j)
    stage = FitStage('T_M3',(object(),),(1.,),(1e-4,),3,1,64,96,100,200)
    ledger = Ledger(cap=500,seconds=30)
    ledger.begin_stage(stage.label,stage.quota)
    seen = []
    def exhausted(current, substage, *args, **kwargs):
        callback = kwargs['on_accept']
        callback(0, SimpleNamespace(curve=current,loss=1.,relative_l2=1.))
        callback(1, SimpleNamespace(curve=final,loss=.8,relative_l2=.9))
        return StageResult(substage.label,final,'STAGE_QUOTA',None,False,1,1.,.8,
            [dict(iteration=0,next_damping=.001)],
            [dict(iteration=1,status='accepted',damping=.1,step_m=[.01,-.02])],[],
            detail='terminal Jacobian quota')
    monkeypatch.setattr(lm,'fit_stage',exhausted)
    endpoint,row = stage_one(curve,stage,1.4,SimpleNamespace(length_unit_m=1.),
        BackendConfig(),ledger,object(), on_accept=lambda c,e: seen.append((c,e)))
    assert row['accepted_steps'] == 1 and len(row['history']) == 2
    assert row['history'][-1]['terminal_linearization_incomplete']
    assert row['damping_next']['translation'] == .03
    assert seen[-1][0] is final and endpoint is final
    assert seen[-1][1]['iteration'] == 1


@pytest.mark.parametrize('mode',[3,7,11])
def test_accepted_checkpoint_precedes_unexpected_failure(monkeypatch,mode):
    import bem_inverse.continuation.lm_backend as lm
    final = FourierCurve.circle(.2,.03j)
    stage = FitStage(f'B_M{mode}',(object(),),(1.,),(1e-4,),mode,1,64,96,100,200)
    ledger = Ledger(cap=500,seconds=30)
    latest = []
    def fail(*args,**kwargs):
        kwargs['on_accept'](1,SimpleNamespace(curve=final,loss=.8,relative_l2=.9))
        raise RuntimeError('unexpected failure after acceptance')
    monkeypatch.setattr(lm,'fit_stage',fail)
    with pytest.raises(RuntimeError,match='after acceptance'):
        fit_record(FourierCurve.circle(.2),stage,1.4,None,BackendConfig(),ledger,None,
                   on_accept=lambda c,e: latest.append((c,e)))
    assert latest[-1][0] is final
    assert latest[-1][1]['stage_label'] == stage.label
