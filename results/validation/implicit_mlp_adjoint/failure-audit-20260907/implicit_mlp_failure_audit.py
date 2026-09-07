"""Read-only checkpoint audit; production code and historical bundles unchanged."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import sys
from datetime import datetime, timezone

import numpy as np
import torch

ROOT = Path('/home/drdeng/Neural_SDF_BEM_AD')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))
import run_sdf_inverse_comparison as driver
from sdf_inverse.models import SirenImplicitField2D, build_siren_parameter_controller
from sdf_inverse.geometry import OrderedSDFGeometryConfig
from sdf_inverse.optimization import ComplexScatteredData, normalized_complex_residual
from sdf_inverse.forward import predict_paired_response
from sdf_inverse.implicit_adjoint import implicit_mlp_data_gradient, _eikonal, _flatten_gradient
from sdf_inverse.neural_optimization import maximum_curve_set_distance
from sdf_to_ordered_boundary import TorchImplicitField2D, FrontendConfig, prepare_single_component

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'results/validation/implicit_mlp_adjoint/failure-audit-20260907'
OUT.mkdir(parents=True, exist_ok=False)
result = {'created_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'frozen final checkpoints; local direction and extraction probes, not inverse recovery', 'cases': []}

def flush():
    (OUT/'metrics.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')

for folder in sorted((ROOT/'results/inverse/implicit_mlp').glob('*/metrics.json')):
    metrics = json.loads(folder.read_text())
    saved = torch.load(folder.parent/'kress_model.pt', weights_only=True, map_location='cpu')
    constructor = dict(saved['constructor']); constructor['dtype'] = torch.float64
    model = SirenImplicitField2D(**constructor)
    model.load_state_dict(saved['state_dict'])
    controller = build_siren_parameter_controller(model)
    accepted = controller.parameter_vector()
    geometry = OrderedSDFGeometryConfig(**saved['geometry_config'])
    responses = np.load(folder.parent/'kress_responses.npz')
    exp = metrics['experiment']
    frequencies = metrics['train_frequencies_ghz']
    columns = [int(np.where(np.isclose(responses['frequencies_ghz'], f))[0][0]) for f in frequencies]
    problem = driver._build_problem(frequencies, np.array(exp['source_points_m']), np.array(exp['receiver_points_m']))
    data = ComplexScatteredData(problem, responses['exact_scattered_response'][:, columns])
    cfg = saved['optimizer_config']
    rng = np.random.default_rng(cfg['random_seed'])
    box = np.array(geometry.bounds)
    points = torch.tensor(rng.uniform(box[0], box[1], (cfg['regularization_samples'],2)),dtype=torch.float64)
    def evaluate():
        fwd = predict_paired_response(model, problem, geometry, solver='kress',retain_kress_state=True)
        residual, rel = normalized_complex_residual(fwd.scattered_response,data.observed_scattered_response)
        loss = float(.5*(residual@residual))
        eik = float(_eikonal(model,points,create_graph=False).detach())
        return fwd,loss,eik,loss+cfg['eikonal_weight']*eik
    fwd, loss, eik, obj = evaluate()
    dg, diag = implicit_mlp_data_gradient(model,data,geometry,forward_result=fwd)
    params = tuple(model.parameters())
    penalty = cfg['eikonal_weight']*_eikonal(model,points,create_graph=True)
    rg = _flatten_gradient(torch.autograd.grad(penalty,params,allow_unused=True),params)
    gradient = dg+rg
    case = {'run':folder.parent.name,'checkpoint_sha256':hashlib.sha256((folder.parent/'kress_model.pt').read_bytes()).hexdigest(), 'geometry_config':saved['geometry_config'],
        'recomputed_training_loss':loss,'saved_training_loss':saved['training_loss'], 'eikonal_loss':eik,'regularized_objective':obj,
        'data_gradient_norm':float(np.linalg.norm(dg)), 'weighted_eikonal_gradient_norm':float(np.linalg.norm(rg)),
        'data_regularizer_cosine':float(dg@rg/(np.linalg.norm(dg)*np.linalg.norm(rg))),
        'data_dot_negative_total_gradient':float(-dg@gradient), 'total_gradient_norm':float(np.linalg.norm(gradient)),
        'gradient_diagnostics':diag, 'direction_probes':[], 'raw_zero_set':[], 'bem_refinement':[]}
    result['cases'].append(case);flush()
    print(case['run'], {k:v for k,v in case.items() if isinstance(v,(str,float))},flush=True)
    # Audit the actual steepest-descent fallback, plus a data-only diagnostic.
    if metrics['target_shape']=='circle' and saved['initial_model']=='siren_circle':
        for name,g in [('production_total_gradient',gradient),('data_gradient_only',dg)]:
            proposal=-g*(cfg['learning_rate']/np.max(np.abs(g)))
            for b in range(19):
                step=cfg['backtrack_factor']**b*proposal
                controller.assign(accepted+step)
                probe={'direction':name,'backtracks':b,'max_weight_step':float(np.max(np.abs(step)))}
                try:
                    trial, l, e, o = evaluate()
                    drift=maximum_curve_set_distance(fwd.geometry_build.curve.points,trial.geometry_build.curve.points)
                    probe.update(loss=l,eikonal=e,objective=o,boundary_drift_m=drift,
                        data_armijo=bool(l<loss and l<=loss+cfg['armijo_fraction']*float(dg@step)),
                        total_armijo=bool(o<=obj+cfg['armijo_fraction']*float(gradient@step)),
                        drift_pass=bool(drift<=cfg['maximum_boundary_step_m']))
                    probe['production_accepts']=probe['data_armijo'] and probe['total_armijo'] and probe['drift_pass']
                except Exception as ex:
                    probe['error']=f'{type(ex).__name__}: {ex}'
                finally:
                    controller.assign(accepted)
                case['direction_probes'].append(probe);flush()
            print(name,[p for p in case['direction_probes'] if p['direction']==name and p.get('production_accepts')],flush=True)
    target = driver._build_target(metrics['target_shape'])
    field = TorchImplicitField2D(model,device='cpu',dtype=torch.float64)
    # Both grid and sample refinement, independently varied; raw samples never pass through Fourier fitting.
    for grid,samples in [(257,512),(513,512),(513,1024)]:
        front=prepare_single_component(field,FrontendConfig(bounds=geometry.bounds,grid_shape=(grid,grid),projected_samples=samples))
        raw=front.projected_points
        distances=target.boundary_distances(raw)
        case['raw_zero_set'].append({'grid':grid,'samples':samples,'maximum_raw_node_to_target_m':float(np.max(distances)),
            'mean_raw_node_to_target_m':float(np.mean(distances)), 'maximum_abs_field':float(np.max(np.abs(field.value(raw.copy()))))})
        np.savez_compressed(OUT/f'{folder.parent.name}-raw-{grid}-{samples}.npz',points=raw)
        flush()
    previous=fwd.scattered_response
    for nodes in [geometry.num_nodes*2,geometry.num_nodes*4]:
        refined=predict_paired_response(model,problem,replace(geometry,num_nodes=nodes),solver='kress')
        r, rel=normalized_complex_residual(refined.scattered_response,data.observed_scattered_response)
        case['bem_refinement'].append({'nodes':nodes,'training_loss':float(.5*(r@r)),
            'response_relative_change':float(np.linalg.norm(refined.scattered_response-previous)/np.linalg.norm(refined.scattered_response))})
        previous=refined.scattered_response;flush()
    print('raw',case['raw_zero_set'],'bem',case['bem_refinement'],flush=True)
result['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'solvers/sdf_inverse/implicit_adjoint.py',ROOT/'solvers/sdf_inverse/models.py',ROOT/'solvers/sdf_inverse/geometry.py',ROOT/'run_sdf_inverse_comparison.py']}
result['finished_utc']=datetime.now(timezone.utc).isoformat();flush()
print('SAVED',OUT,flush=True)
