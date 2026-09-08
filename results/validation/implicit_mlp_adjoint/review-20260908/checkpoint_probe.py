"""Read-only frozen checkpoint probes for review of 6496cd3."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
import torch
ROOT=Path('/home/drdeng/Neural_SDF_BEM_AD')
sys.path[:0]=[str(ROOT),str(ROOT/'solvers')]
import run_sdf_inverse_comparison as driver
from sdf_inverse.models import SirenImplicitField2D,build_siren_parameter_controller
from sdf_inverse.geometry import OrderedSDFGeometryConfig
from sdf_inverse.optimization import ComplexScatteredData,normalized_complex_residual
from sdf_inverse.forward import predict_paired_response
from sdf_inverse.implicit_adjoint import implicit_mlp_data_gradient,_eikonal,_flatten_gradient
from sdf_inverse.neural_optimization import maximum_curve_set_distance
folder=ROOT/'results/validation/implicit_mlp_adjoint/rerun-20260907/star-bw96'
metrics=json.loads((folder/'metrics.json').read_text())
saved=torch.load(folder/'kress_model.pt',weights_only=True,map_location='cpu')
constructor=dict(saved['constructor']);constructor['dtype']=torch.float64
model=SirenImplicitField2D(**constructor);model.load_state_dict(saved['state_dict'])
controller=build_siren_parameter_controller(model); theta=controller.parameter_vector()
gc=OrderedSDFGeometryConfig(**saved['geometry_config']); cfg=saved['optimizer_config']
archive=np.load(folder/'kress_responses.npz');freqs=metrics['train_frequencies_ghz'];exp=metrics['experiment']
columns=[int(np.where(np.isclose(archive['frequencies_ghz'],f))[0][0]) for f in freqs]
problem=driver._build_problem(freqs,np.array(exp['source_points_m']),np.array(exp['receiver_points_m']))
data=ComplexScatteredData(problem,archive['exact_scattered_response'][:,columns])
rng=np.random.default_rng(cfg['random_seed']);box=np.array(gc.bounds)
points=torch.tensor(rng.uniform(box[0],box[1],(cfg['regularization_samples'],2)),dtype=torch.float64)
def evaluate():
 fwd=predict_paired_response(model,problem,gc,solver='kress',retain_kress_state=True)
 residual,rel=normalized_complex_residual(fwd.scattered_response,data.observed_scattered_response)
 loss=float(.5*(residual@residual)); eik=float(_eikonal(model,points,create_graph=False).detach())
 return fwd,loss,eik,loss+cfg['eikonal_weight']*eik
out={'scope':'Frozen star-bw96 final checkpoint: unchanged production fallback direction, selected backtracks; does not replay Adam moments.', 'checkpoint_sha256':hashlib.sha256((folder/'kress_model.pt').read_bytes()).hexdigest(),'probes':[]}
def flush():
 (Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/implicit_verdict_audit.json')).write_text(json.dumps(out,indent=2)+'\n')
fwd,loss,eik,obj=evaluate();dg,diag=implicit_mlp_data_gradient(model,data,gc,forward_result=fwd)
params=tuple(model.parameters());rg=_flatten_gradient(torch.autograd.grad(cfg['eikonal_weight']*_eikonal(model,points,create_graph=True),params,allow_unused=True),params);g=dg+rg
out.update(loss=loss,saved_loss=saved['training_loss'],eikonal=eik,objective=obj,data_gradient_norm=float(np.linalg.norm(dg)),weighted_eikonal_gradient_norm=float(np.linalg.norm(rg)),total_gradient_max=float(np.max(np.abs(g))),data_regularizer_cosine=float(dg@rg/(np.linalg.norm(dg)*np.linalg.norm(rg))),data_dot_negative_total_gradient=float(-dg@g),total_gradient_norm=float(np.linalg.norm(g)),gradient_diagnostics=diag)
print({k:v for k,v in out.items() if k!='probes'},flush=True);flush()
proposal=controller.project(theta-g*(cfg['learning_rate']/max(float(np.max(np.abs(g))),1.0)))-theta
for b in [8,9,10,12]:
 step=controller.project(theta+cfg['backtrack_factor']**b*proposal)-theta;controller.assign(theta+step)
 p={'backtracks':b,'max_weight_step':float(np.max(np.abs(step)))}
 try:
  trial,l,e,o=evaluate();drift=maximum_curve_set_distance(fwd.geometry_build.curve.points,trial.geometry_build.curve.points)
  p.update(loss=l,eikonal=e,objective=o,conversion_m=trial.geometry_build.maximum_conversion_error_m,boundary_drift_m=drift,data_armijo=bool(l<loss and l<=loss+cfg['armijo_fraction']*float(dg@step)),total_armijo=bool(o<=obj+cfg['armijo_fraction']*float(g@step)),drift_pass=bool(drift<=cfg['maximum_boundary_step_m']))
  p['production_accepts']=p['data_armijo'] and p['total_armijo'] and p['drift_pass'] and bool(dg@proposal<0 and g@proposal<0)
 except Exception as exc:
  p['error']=f'{type(exc).__name__}: {exc}'
 finally:controller.assign(theta)
 out['probes'].append(p);flush();print(p,flush=True)
