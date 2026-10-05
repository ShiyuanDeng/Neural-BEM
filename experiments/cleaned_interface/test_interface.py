"""Bounded numerical and contract regressions; never run the 36-scene campaign."""
from dataclasses import asdict, replace
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

from experiments.shape_continuation import forward as F
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, Objective, fit_stage, stage_record
from . import benchmark as b
from .geometry import ProjectedUpdate, resize, cleanup
from .io import read, portable
from .physics import Execution, make_backend, Prediction
from .policy import CumulativePolicy, LocalizationRule
from .problem import Observation


def problem(case='modal__c4__development_c'):
    return b.fitting_problem(next(r for r in b.descriptors() if r['id']==case), b.DEFAULT_OUTPUT)


def test_inventory_preserves_all_36_sources_and_noise_draws():
    rows=b.descriptors()
    assert len(rows)==36
    assert sum('damped' not in r for r in rows)==16
    assert {panel:sum(r['panel']==panel for r in rows) for panel in ('core','fresh','far','modal')} == dict(core=6,fresh=6,far=7,modal=17)
    original={r['id']:r for r in read(b.SOURCE_MANIFEST)['cases']}
    for row in rows:
        assert row['data']==original[row['id']]['data']
        assert row.get('initial')==original[row['id']].get('initial')
        assert row['predecessor_path'][-1]['source']==row['reference']
        assert all((b.ROOT/item['source']).exists() for item in row['predecessor_path'])


def test_noiseless_policy_matches_every_archived_stage_and_optimizer():
    p=problem()
    policy=CumulativePolicy()
    backend=make_backend(execution_settings=Execution(device='cpu'))
    ops=policy.operations(p,backend)
    archived=read(b.ROOT/'results/validation/modal_atlas/MA-004/runs/D/c4/development_c/configuration.json')
    fits=[o for o in ops if o.kind=='fit']
    assert [portable(stage_record(o.stage)) for o in fits]==archived['stages']
    # New opt-in controller defaults preserve this archived optimizer recipe.
    archived_backend = dict(archived['backend'], reach_fraction=0.)
    assert all(portable(asdict(o.optimizer))==archived_backend for o in fits)
    assert [op.record() for op in ops]==policy.plan(p,backend)['operations']
    assert len([o for o in ops if o.kind=='cleanup'])==1
    assert [o.stage.update_modes for o in policy.tail(p,backend,95) if o.kind=='fit']==[43,49,55,61,67,73,79,85,91]
    assert not policy.tail(p,backend,37)


def test_noise_rules_are_shared_declared_input_rules():
    p=problem('modal__c4__noisy_asymmetric')
    policy=CumulativePolicy()
    backend=make_backend(execution_settings=Execution(device='cpu'))
    ops=policy.operations(p,backend)
    fits=[o for o in ops if o.kind=='fit']
    assert all(o.details['noise_threshold']>0 for o in fits)
    assert len([o for o in ops if o.kind=='cleanup'])==6
    full=next(o for o in fits if o.label=='release_M11')
    raw=np.asarray([(np.linalg.norm(o.scattered)/o.sigma_real_imag)**2 for o in p.real])
    np.testing.assert_array_equal(full.stage.weights,raw/raw.sum())
    assert full.optimizer.loss_tolerance==1.1**2*sum(o.scattered.size for o in p.real)/raw.sum()
    assert policy.at_noise_discrepancy(full,full.optimizer.loss_tolerance,p)
    assert not policy.at_noise_discrepancy(fits[0],0,p)
    assert not policy.at_noise_discrepancy(full,2*full.optimizer.loss_tolerance,p)


def test_missing_or_mismatched_damped_inputs_are_not_synthesized(tmp_path):
    row=next(r for r in b.descriptors() if r['id']=='core__wrong_circle')
    with pytest.raises(ValueError,match='missing damped'):
        b.fitting_problem(row,tmp_path)
    p=problem()
    with pytest.raises(ValueError,match='matched real AND damped'):
        replace(p,damped=())
    with pytest.raises(ValueError,match='Damped catalog'):
        replace(p,damped=tuple(replace(o,wavenumber=o.wavenumber*1.01) for o in p.damped))


def test_solver_and_device_capabilities_fail_before_fitting(monkeypatch):
    with pytest.raises(NotImplementedError,match='No nodal fallback'):
        make_backend('modal_muller')
    monkeypatch.setattr(F.cuda_assembly,'available',lambda:False)
    with pytest.raises(RuntimeError,match='Explicit CUDA'):
        make_backend(execution_settings=Execution(device='cuda')).validate(problem())
    with pytest.raises(ValueError,match='material'):
        make_backend().validate(replace(problem(),material='variable_density'))


def test_projected_update_preserves_archived_complete_trial():
    path=b.ROOT/'results/validation/shape_continuation/SC-035-state-band/state_update.py'
    spec=importlib.util.spec_from_file_location('ci001_archived_geometry',path)
    old=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=old
    spec.loader.exec_module(old)
    curve=resize(FourierCurve.circle(1.02,.03+.02j),8)
    current,previous=ProjectedUpdate(.05),old.ProjectedUpdate(.05)
    new_space,old_space=current.prepare(curve,3,8),previous.prepare(curve,3,8)
    np.testing.assert_array_equal(new_space.derivatives,old_space.derivatives)
    step=np.random.default_rng(81).normal(size=7)*1e-6
    np.testing.assert_array_equal(current.trial(new_space,step)[0].coefficients,
                                  previous.trial(old_space,step)[0].coefficients)
    padded=resize(curve,192)
    np.testing.assert_array_equal(cleanup(padded).coefficients,padded.coefficients)


@pytest.mark.parametrize('damping',[0.,.25])
def test_cpu_predictions_and_complete_trial_derivative(damping,monkeypatch):
    # Explicit execution must override inherited ambient solver settings.
    monkeypatch.setenv('SC_FORWARD_BACKEND','cuda')
    backend=make_backend(execution_settings=Execution(device='cpu',frequency_threads=1))
    scan=b.acquisition()
    k=1.2*(1+1j*damping)
    observation=Observation(k,scan,np.ones(24,complex),.5e9)
    curve=resize(FourierCurve.circle(1.02,.03+.02j),8)
    state=backend.evaluate(curve,observation,.5,128)
    if damping:
        from experiments.modal_atlas.damped import solve
        ref=solve(curve,k,.5,scan,128).prediction
    else:
        ref=F.solve(curve,k.real,.5,scan,128,execution_backend='cpu').prediction
    np.testing.assert_array_equal(state.prediction,ref)
    update=ProjectedUpdate(.05)
    space=update.prepare(curve,3,8)
    jacobian=backend.derivative(state,update,space)
    direction=np.random.default_rng(42).normal(size=7)
    direction/=np.linalg.norm(direction)
    plus,minus=[backend.evaluate(update.trial(space,s*1e-7*direction)[0],observation,.5,128).prediction for s in (1,-1)]
    fd=(plus-minus)/2e-7
    assert np.linalg.norm(fd-jacobian@direction)/np.linalg.norm(fd)<1e-3
    assert not hasattr(state,'curve') and not hasattr(state,'traces')


def test_lm_injected_backend_matches_reference_path(monkeypatch):
    monkeypatch.setenv('SC_FORWARD_BACKEND','cpu')
    monkeypatch.setenv('SC_FREQUENCY_THREADS','1')
    backend=make_backend(execution_settings=Execution(device='cpu',frequency_threads=1))
    scan=b.acquisition()
    target=FourierCurve.circle(1.0)
    values=F.solve(target,1.2,.5,scan,128,execution_backend='cpu').prediction
    obs=(Observation(1.2,scan,values,.5e9),)
    stage=FitStage('equivalence',obs,(1.,),(1e-5,),3,8,64,128,2,300)
    curve=resize(FourierCurve.circle(1.03,.01j),8)
    rows=[]
    for physics in (None,backend):
        ledger=Ledger(cap=400,seconds=120)
        ledger.begin_stage(stage.label,stage.quota)
        rows.append(fit_stage(curve,stage,.5,ProjectedUpdate(.05),BackendConfig(),ledger,physics=physics))
    a,c=rows
    assert a.accepted_steps==c.accepted_steps and a.outcome==c.outcome
    assert a.work['work_units']==c.work['work_units']
    np.testing.assert_array_equal(a.curve.coefficients,c.curve.coefficients)
    assert a.final_loss==c.final_loss


def test_objective_treats_non_nodal_state_as_opaque(monkeypatch):
    def forbidden(*a,**kw):
        raise AssertionError('Hidden nodal physics call')
    from experiments.shape_continuation import lm_backend
    monkeypatch.setattr(lm_backend,'solve',forbidden)
    monkeypatch.setattr(lm_backend,'shape_jacobian',forbidden)
    class Service:
        calls=0
        @contextmanager
        def ordered_calls(self,fn,items):
            yield [lambda item=item:fn(item) for item in items]
        def evaluate(self,curve,observation,contrast,resolution):
            self.calls+=1
            return Prediction(np.ones(24,complex),{},42)
        def derivative(self,prediction,update,space):
            assert prediction._handle==42
            return np.ones((24,7),complex)
    service=Service()
    stage=FitStage('opaque',(problem().real[0],),(1.,),(1e-5,),3,8,64,128,1)
    objective=Objective(stage,.5,BackendConfig(),Ledger(),physics=service)
    evaluated=objective.production(resize(FourierCurve.circle(),8),'base')
    assert objective.jacobian(evaluated,None,None).shape==(48,7)
    assert service.calls==1


def test_mie_recurrence_matches_reference_objective_and_mask():
    p=problem()
    from experiments.modal_atlas.mie_localize import landscape
    from .mie_grid import landscape_variant
    obs=p.damped[:3]
    centers=np.array([0j,.02+.01j,5.5+0j])
    radii=np.array([.6,.9,1.2])
    ref=landscape(obs,p.contrast,centers,radii,cutoff=35)
    current=landscape_variant(obs,p.contrast,centers,radii,35)
    assert np.array_equal(np.isfinite(ref),np.isfinite(current))
    finite=np.isfinite(ref)
    np.testing.assert_allclose(current[finite],ref[finite],rtol=1e-11,atol=1e-13)
    assert np.argmin(current)==np.argmin(ref)


def test_ray_table_on_cpu_and_explicit_kernel_does_not_mutate_globals():
    torch=pytest.importorskip('torch')
    from scipy.special import jv,hankel1
    from .damped_cuda import RayTable,make_direct
    table=RayTable(.25,device='cpu')
    points=np.geomspace(.01,100,1000)
    z=points*(1+.25j)
    exact=np.stack([jv(n,z) for n in range(3)]+[hankel1(n,z) for n in range(3)],axis=-1)
    value=table(torch.as_tensor(points)).numpy()
    assert np.max(np.abs(value-exact)/np.maximum(np.abs(exact),1e-30))<1e-9
    original=F.cuda_assembly._direct
    kernel=make_direct(table)
    kernel(torch.as_tensor(np.array([.1,.3])),1+.25j,2+.5j)
    assert F.cuda_assembly._direct is original
    with pytest.raises(ValueError,match='ray'):
        kernel(torch.as_tensor(np.array([.1])),1+.3j,2+.6j)
    with pytest.raises(ValueError,match='segment'):
        table(torch.as_tensor(np.array([100.01])))


def test_preparation_freezes_contract_and_refuses_unsealed_augmentation(tmp_path):
    result=b.prepare(tmp_path)
    assert result['cases']==36 and result['missing_damped']==16
    m=b.verify(tmp_path)
    assert m['comparison']==portable(b.COMPARISON)
    maintained={str(p.relative_to(b.ROOT)) for p in (b.ROOT/'solvers/bem_inverse').rglob('*.py')}
    assert maintained and maintained <= m['sources'].keys()
    import tarfile
    with tarfile.open(tmp_path/'sources.tar.gz') as archive:
        assert maintained <= set(archive.getnames())
    with pytest.raises(ValueError,match='sealed'):
        b.verify(tmp_path,require_damped=True)
    with pytest.raises(ValueError,match='explicitly'):
        b.augment(tmp_path,Execution(device='cpu'))
    summary=b.report(tmp_path)
    assert summary['pending']==36 and not summary['requirement_1_satisfied']
    from .qualification import compare_execution
    with pytest.raises(ValueError,match='three'):
        compare_execution([tmp_path],[tmp_path])


@pytest.mark.parametrize('failure',['oom','outside'])
def test_damped_automatic_reference_fallback_and_explicit_cuda_failure(monkeypatch,failure):
    torch=pytest.importorskip('torch')
    from . import damped_cuda
    monkeypatch.setattr(F.cuda_assembly,'available',lambda:True)
    p=problem()
    o=p.damped[0]
    curve=resize(FourierCurve.circle(),8)
    expected=make_backend(execution_settings=Execution(device='cpu')).evaluate(curve,o,p.contrast,64)
    def refused(*args,**kwargs):
        if failure=='oom':
            raise torch.OutOfMemoryError('simulated damped assembly OOM')
        raise ValueError('argument outside the tabulated ray segment')
    monkeypatch.setattr(damped_cuda,'gpu_matrix',refused)
    auto=make_backend(execution_settings=Execution(device='auto'))
    monkeypatch.setattr(auto,'_ray_table',lambda:None)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        got=auto.evaluate(curve,o,p.contrast,64)
    np.testing.assert_array_equal(got.prediction,expected.prediction)
    assert auto.receipt()['fallback_reasons']
    strict=make_backend(execution_settings=Execution(device='cuda'))
    monkeypatch.setattr(strict,'_ray_table',lambda:None)
    with pytest.raises((torch.OutOfMemoryError,ValueError)):
        strict.evaluate(curve,o,p.contrast,64)


@pytest.mark.parametrize('contrast',[.5,4.,13.3])
def test_cuda_damped_prediction_derivative_and_factor_lifetime(contrast):
    torch=pytest.importorskip('torch')
    if not torch.cuda.is_available():
        pytest.skip('CUDA unavailable')
    p=problem()
    curve=resize(FourierCurve.circle(1.03,.03+.02j),8)
    cpu=make_backend(execution_settings=Execution(device='cpu',frequency_threads=1))
    gpu=make_backend(execution_settings=Execution(device='cuda',frequency_threads=1))
    update=ProjectedUpdate(.05)
    space=update.prepare(curve,3,8)
    o=p.damped[8]
    a,c=[backend.evaluate(curve,o,contrast,128) for backend in (cpu,gpu)]
    assert np.linalg.norm(a.prediction-c.prediction)/np.linalg.norm(a.prediction)<1e-9
    ja,jc=[backend.derivative(value,update,space) for backend,value in ((cpu,a),(gpu,c))]
    assert np.linalg.norm(ja-jc)/np.linalg.norm(ja)<1e-7
    assert c._handle.factors._resident is None
    assert all(isinstance(v,np.ndarray) for v in c._handle.factors._offloaded)


def test_gpu_mie_grid_matches_reference_and_ordering():
    torch=pytest.importorskip('torch')
    if not torch.cuda.is_available():
        pytest.skip('CUDA unavailable')
    p=problem()
    reference=make_backend(execution_settings=Execution(device='cpu',acceleration='reference'))
    gpu=make_backend(execution_settings=Execution(device='cuda'))
    centers=np.array([0j,.04+.03j,-.1+.04j])
    radii=np.array([.8,1.,1.2])
    a,c=[backend.disk_landscape(p.damped[:3],p.contrast,centers,radii,35) for backend in (reference,gpu)]
    np.testing.assert_allclose(a,c,rtol=1e-11,atol=1e-13)
    np.testing.assert_array_equal(np.argsort(a,axis=None),np.argsort(c,axis=None))


@pytest.mark.parametrize('geometry_update', [None, 'certified_spectral', 'analytic_spectral'])
def test_runner_end_to_end_from_start_with_localization_cleanup_frontier_and_audit(tmp_path, geometry_update):
    """Small independent disk data; exercise the interpreter without a research-scene fit."""
    from .runner import fit
    from .problem import Problem
    from .physics import NodalKress
    from .policy import Operation
    class SmallBackend(NodalKress):
        def resolution_profile(self,storage_band):
            row=super().resolution_profile(storage_band)
            row.update(production=64,refined=128,nodal_resolution=64)
            return row
    class ShortPolicy(CumulativePolicy):
        def operations(self,p,physics):
            ops=super().operations(p,physics)
            fits=[o for o in ops if o.kind=='fit']
            warm=replace(fits[0],stage=replace(fits[0].stage,iterations=1))
            next_fit=replace(fits[1],stage=replace(fits[1].stage,iterations=1))
            clean=Operation('cleanup','test_cleanup','exercise exact cleanup','after warm-up','next fit',
                            details=dict(retained_band=4,storage_band=8))
            return (ops[0],ops[1],warm,clean,next_fit,ops[-2],ops[-1])
        def tail(self,p,physics,frontier):
            return ()
    backend=SmallBackend(Execution(device='cpu',frequency_threads=1))
    template=problem()
    truth=FourierCurve.circle()
    real=tuple(replace(o,scattered=backend.evaluate(truth,o,.5,128).prediction) for o in template.real)
    damped=tuple(replace(o,scattered=backend.evaluate(truth,o,.5,128).prediction) for o in template.damped)
    p=Problem(FourierCurve.circle(1.02),real,damped,.5)
    policy=ShortPolicy(storage_band=24,frontier_top=7,
        localization=LocalizationRule(center_min_m=.5,center_max_m=.5,center_step_m=.004,
            radius_min_m=.05,radius_max_m=.05,radius_step_m=.001,max_starts=1,refinement_iterations=1))
    result=fit(p,physics=backend,policy=policy,output=tmp_path,geometry_update=geometry_update)
    assert result['outcome']=='COMPLETED_SCHEDULE',result['detail']
    assert result['initial_audit_passed'] and result['final_audit_passed']
    assert result['localization']['units']==6
    assert len(result['stages'])==2
    operations={e['operation']['operation'] for e in result['decisions']}
    assert operations=={'audit','localize','fit','cleanup','frontier'}
    assert result['total_units']==result['audit_units']+result['fit_and_localization_units']
    from .geometry_selection import describe_plan
    expected = describe_plan(policy.plan(p,backend), result['geometry_settings'],
                             override_operations=geometry_update is not None)
    assert read(tmp_path/'plan.json')['operations']==portable(expected['operations'])
    if geometry_update is None:
        assert read(tmp_path/'plan.json')['operations']==portable([op.record() for op in policy.operations(p,backend)])
