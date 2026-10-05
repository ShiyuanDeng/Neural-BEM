"""GGB-004: one initial circle stage, exact translation and uniform scaling."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter
import traceback
from types import SimpleNamespace

import numpy as np

from . import ggb003 as common

ROOT = common.ROOT
OUTPUT = ROOT/'results/validation/cleaned_interfaces/GGB-004'
ID = 'GGB-004'


def sources():
    hashes = common.sources()
    for path in (Path(__file__), ROOT/'pytest/bem_inverse/test_similarity.py'):
        hashes[str(path.relative_to(ROOT))] = common.previous.sha256(path)
    return hashes


def coordinates(curve):
    c = curve.coefficients
    radius = np.sqrt(np.sum(np.arange(-curve.band,curve.band+1)*abs(c)**2))
    return dict(centre_m=[float(c[curve.band].real),float(c[curve.band].imag)],
                radius_m=float(radius))


def qualify(output):
    from bem_inverse.continuation.geometry import FourierCurve
    from bem_inverse.physics import Execution
    from bem_inverse.problem import Observation
    from bem_inverse.similarity import SimilarityUpdate
    from .ggb002_adapter import FullAcquisition, FullMatrixModal
    output.mkdir(parents=True,exist_ok=True)
    path = output/'qualification.json'
    if path.exists():
        raise ValueError('Preserve prior qualification before rerunning.')
    data, seal = common.inputs()
    before = sources()
    row = dict(experiment_id=ID,status='RUNNING',source_hashes=before,input=seal,rows=[])
    common.write(path,row)
    try:
        fixtures = [('circle',FourierCurve.circle(.2,.03+.04j).coefficients,1.),
                    ('curved_nonunit',np.array([.004j,.007,.03+.04j,.2,.014j]),.25)]
        for device in ('cpu','cuda'):
            service = FullMatrixModal(Execution(device=device,frequency_threads=1))
            for name,physical,unit in fixtures:
                curve = FourierCurve(np.pad(physical/unit,32-len(physical)//2))
                update = SimilarityUpdate(unit)
                space = update.prepare(curve,0,curve.band)
                for index in (1,2,3,4):
                    f = float(data['frequencies_hz'][index])
                    acq = FullAcquisition(data['sources']/unit,data['receivers']/unit,
                                         complex(data['source_scale'])*f/.4e9)
                    obs = Observation(float(data['reference_wavenumber'])*f/.4e9*unit,
                                      acq,np.ones((16,32),complex),f)
                    base = service.evaluate(curve,obs,float(data['known_epsilon']),8*64)
                    jac = service.derivative(base,update,space)
                    errors = []
                    for column in range(3):
                        delta = np.eye(3)[column]*1e-6
                        high = service.evaluate(update.trial(space,delta)[0],obs,
                                                float(data['known_epsilon']),8*64).prediction
                        low = service.evaluate(update.trial(space,-delta)[0],obs,
                                               float(data['known_epsilon']),8*64).prediction
                        fd = ((high-low)/2e-6).reshape(-1)
                        errors.append(float(np.linalg.norm(fd-jac[:,column])/np.linalg.norm(fd)))
                    row['rows'].append(dict(device=device,fixture=name,frequency_hz=f,errors=errors))
                    common.write(path,row)
        errors = np.array([e for r in row['rows'] for e in r['errors']])
        if not np.isfinite(errors).all() or errors.max()>1e-5:
            raise ValueError('Similarity derivative qualification failed.')
        if sources()!=before:
            raise ValueError('Sources changed during qualification.')
        row.update(status='PASSED',maximum_relative_column_error=float(errors.max()))
    except Exception:
        row.update(status='FAILED',traceback=traceback.format_exc())
        common.write(path,row)
        raise
    common.write(path,row)
    print('Qualification:',row['maximum_relative_column_error'],flush=True)


def stationarity(curve,observations,weights,contrast,update,service,config):
    from bem_inverse.continuation.lm_backend import normalize
    observed = np.stack([o.scattered.reshape(-1) for o in observations],axis=1)
    space = update.prepare(curve,0,curve.band)
    rows = []
    for cutoff in (64,96):
        states = [service.evaluate(curve,o,contrast,8*cutoff) for o in observations]
        prediction = np.stack([s.prediction.reshape(-1) for s in states],axis=1)
        residual = normalize(prediction-observed,observed,weights,config.residual_floor)
        jac = np.stack([service.derivative(s,update,space) for s in states],axis=1)
        matrix = normalize(jac,observed,weights,config.residual_floor)
        gradient = matrix.T@residual
        step = np.linalg.lstsq(matrix,-residual,rcond=None)[0]
        gain = float(-gradient@step-.5*np.linalg.norm(matrix@step)**2)
        loss = float(.5*residual@residual)
        margin = config.acceptance_absolute_margin+config.acceptance_relative_margin*loss
        rows.append(dict(cutoff=cutoff,loss=loss,gradient=gradient,gradient_inf=float(abs(gradient).max()),
            gn_step_m=step,gn_step_norm_m=float(np.linalg.norm(step)),predicted_gain=gain,
            acceptance_margin=margin,gradient_tolerance_met=bool(abs(gradient).max()<=config.gradient_tolerance),
            model_gain_below_acceptance_margin=bool(gain<=margin)))
    return dict(rows=rows,model_gain_below_margin_both=all(r['model_gain_below_acceptance_margin'] for r in rows),
                gradient_tolerance_met_both=all(r['gradient_tolerance_met'] for r in rows),
                predicted_gain_resolution_difference=abs(rows[0]['predicted_gain']-rows[1]['predicted_gain']))


def run(output):
    import torch
    from bem_inverse.continuation.geometry import FourierCurve
    from bem_inverse.continuation.lm_backend import FitStage,Ledger
    from bem_inverse.physics import Execution
    from bem_inverse.policy import CumulativePolicy
    from bem_inverse.similarity import SimilarityUpdate
    from .ggb002_adapter import FullMatrixModal
    authorization = json.loads((output/'authorization.json').read_text())
    if authorization['experiment_id']!=ID or not authorization['authorized']:
        raise ValueError('User authorization must be recorded.')
    qualification = json.loads((output/'qualification.json').read_text())
    before = sources()
    data,seal = common.inputs()
    if qualification['status']!='PASSED' or qualification['source_hashes']!=before or qualification['input']!=seal:
        raise ValueError('Current sources and inputs must pass qualification.')
    folder = output/'W'
    folder.mkdir(exist_ok=False)
    observations = common.previous.observations(data,(1,2,3,4))
    config,weights,expected = CumulativePolicy()._config(SimpleNamespace(domain_box=common.previous.DOMAIN),observations)
    execution = Execution(device='cuda',frequency_threads=1)
    service = FullMatrixModal(execution)
    update = SimilarityUpdate(1.)
    curve = FourierCurve(np.r_[np.zeros(33,complex),.35,np.zeros(31,complex)])
    stage = FitStage('W_translation_radius',observations,weights,(1e-4,)*4,0,32,8*64,8*96,100,2600)
    ledger = Ledger(cap=8000,seconds=2400,strict_dispatch=True)
    ledger.begin_stage(stage.label,stage.quota)
    row = dict(experiment_id=ID,arm='W',status='RUNNING',input=seal,source_hashes=before,
        backend_config=asdict(config),execution=asdict(execution),weights=weights,
        expected_noise_loss=expected,settings=dict(stage='translation and radius only',iterations=100,
        quota=2600,cap=8000,seconds_cap=2400,translation_cap_m=.018,radius_cap_m=.012),
        environment=dict(torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0)),stages=[])
    common.write(folder/'result.json',row)
    started = perf_counter()
    def accepted(current,event):
        nonlocal curve
        curve = current
        event.update(coordinates(curve),elapsed_fit_seconds=perf_counter()-started)
        np.savez_compressed(folder/'curve.npz',coefficients=curve.coefficients)
        with (folder/'accepted.jsonl').open('a') as stream:
            stream.write(json.dumps(common.portable(event),allow_nan=False)+'\n')
        x,y = event['centre_m']
        print(f"{event['iteration']:3d} centre=({x:.6f},{y:.6f}) radius={event['radius_m']:.6f} "
              f"loss={event['loss']:.8g} elapsed={event['elapsed_fit_seconds']:.2f}s",flush=True)
    try:
        torch.cuda.synchronize()
        curve,stage_row = common.fit_record(curve,stage,float(data['known_epsilon']),update,
                                            config,ledger,service,on_accept=accepted)
        torch.cuda.synchronize()
        row.update(stages=[stage_row],fit_seconds=perf_counter()-started,ledger=ledger.snapshot(),
                   geometry_work=dict(update.counts),physics_receipt_fit=service.receipt())
        np.savez_compressed(folder/'curve.npz',coefficients=curve.coefficients)
        common.write(folder/'result.json',row)
        began = perf_counter()
        audited,prediction,refined = common.audit(curve,data,service,weights,config)
        row.update(audited)
        np.savez_compressed(folder/'endpoint.npz',coefficients=curve.coefficients,
                            prediction=np.stack(prediction),refined_prediction=np.stack(refined))
        row['endpoint_stationarity'] = stationarity(curve,observations,weights,
            float(data['known_epsilon']),update,service,config)
        torch.cuda.synchronize()
        row.update(audit_seconds=perf_counter()-began,physics_receipt_with_audits=service.receipt())
        row.update(common.shape_metrics(curve,data))
        if sources()!=before:
            raise ValueError('Numerical sources changed during the run.')
        row.update(status='COMPLETE')
    except Exception:
        row.update(status='FAILED',traceback=traceback.format_exc(),ledger=ledger.snapshot(),
                   physics_receipt_at_failure=service.receipt(),geometry_work=dict(update.counts))
        np.savez_compressed(folder/'curve.npz',coefficients=curve.coefficients)
        common.write(folder/'result.json',row)
        raise
    common.write(folder/'result.json',row)
    print(json.dumps({k:row[k] for k in ('status','fit_seconds','centre_error_m','equivalent_radius_m',
                                       'refined_joint_loss','noise_discrepancy_met')},indent=2))
    print(stage_row['outcome'],stage_row['stop_reason'],flush=True)


def verify(output):
    from bem_inverse.continuation.geometry import FourierCurve
    row = json.loads((output/'W/result.json').read_text())
    data,seal = common.inputs()
    assert row['input']==seal
    assert row['source_hashes']==json.loads((output/'qualification.json').read_text())['source_hashes']
    if row['status']=='FAILED':
        assert row.get('traceback')
        common.write(output/'validation.json',dict(experiment_id=ID,status='FAILED_PRESERVED'))
        return
    with np.load(output/'W/endpoint.npz') as end:
        curve = FourierCurve(end['coefficients'])
        keep = np.ones(len(curve.coefficients),bool)
        keep[[curve.band,curve.band+1]] = False
        np.testing.assert_array_equal(curve.coefficients[keep],0)
        assert curve.coefficients[curve.band+1].imag==0 and curve.coefficients[curve.band+1].real>0
        with np.load(output/'W/curve.npz') as checkpoint:
            np.testing.assert_array_equal(checkpoint['coefficients'],end['coefficients'])
        events = [json.loads(s) for s in (output/'W/accepted.jsonl').read_text().splitlines()]
        last = events[-1]['coefficients']
        np.testing.assert_array_equal(np.array(last['real'])+1j*np.array(last['imag']),end['coefficients'])
        for i,a in enumerate(row['audit']):
            target = data['archived_observed'] if i==0 else data['observed'][i]
            residual = np.linalg.norm(end['refined_prediction'][i]-target)/np.linalg.norm(target)
            np.testing.assert_allclose(residual,a['relative_residual'],rtol=1e-13)
            error = np.linalg.norm(end['prediction'][i]-end['refined_prediction'][i])/np.linalg.norm(end['refined_prediction'][i])
            np.testing.assert_allclose(error,a['field_refinement_relative_error'],rtol=1e-13)
            assert a['field_gate_passed']==bool(error<=1e-4)
            assert a['noise_target_met']==bool(residual<=a['noise_target_relative'])
        for key,value in common.shape_metrics(curve,data).items():
            if isinstance(value,dict):
                for k,v in value.items():np.testing.assert_allclose(v,row[key][k],rtol=1e-12)
            else:np.testing.assert_allclose(value,row[key],rtol=1e-12)
    for event in events:
        c = np.array(event['coefficients']['real'])+1j*np.array(event['coefficients']['imag'])
        np.testing.assert_array_equal(c[keep],0)
        assert c[curve.band+1].real>0 and c[curve.band+1].imag==0
    stage = row['stages'][0]
    assert len(events)-1==stage['accepted_steps']
    audit = row['endpoint_stationarity']['rows'][0]
    np.testing.assert_allclose(audit['loss'],stage['final_loss'],rtol=1e-12)
    if stage['history'][-1].get('gradient_inf') is not None:
        np.testing.assert_allclose(audit['gradient_inf'],stage['history'][-1]['gradient_inf'],rtol=1e-7,atol=1e-12)
    joint = .5*sum(w*a['relative_residual']**2 for w,a in zip(row['weights'],row['audit'][1:]))
    np.testing.assert_allclose(joint,row['refined_joint_loss'],rtol=1e-13)
    common.write(output/'validation.json',dict(experiment_id=ID,status='PASSED',
        accepted_steps=len(events)-1,circle_preserved=True))
    print('Saved restricted endpoint verified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('qualify','run','verify'))
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args = parser.parse_args()
    {'qualify':qualify,'run':run,'verify':verify}[args.command](args.output)


if __name__=='__main__':
    main()
