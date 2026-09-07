"""Matched full-budget production star pretraining, changing only Eikonal weight."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import hashlib
import numpy as np
import torch
ROOT=Path('/home/drdeng/Neural_SDF_BEM_AD')
sys.path[:0]=[str(ROOT),str(ROOT/'solvers')]
import run_sdf_inverse_comparison as driver
from sdf_inverse.models import SirenImplicitField2D, pretrain_implicit_field, first_order_distance_supervisor
from sdf_inverse.geometry import build_ordered_sdf_geometry
from sdf_to_ordered_boundary import TorchImplicitField2D, FrontendConfig, prepare_single_component

OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'results/validation/implicit_mlp_adjoint/failure-audit-20260907'
target=driver._build_target('star')
box=np.array(driver.DEFAULT_GEOMETRY_BOUNDS)
supervisor=first_order_distance_supervisor(target.exact_model(),maximum_distance=float(np.linalg.norm(box[1]-box[0])))
result={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'same production star exact-target pretraining, network, seed, samples, optimizer, cosine schedule, 6000 updates; only Eikonal weight varies. Not an inverse run or shared-warm-up activation study.', 'arms':[]}

# Finite differences of the actual detached supervision function, away from the center.
rng=np.random.default_rng(0)
xy=rng.uniform(box[0],box[1],(10000,2))
xy=xy[np.linalg.norm(xy-np.array(target.center),axis=1)>.005]
values=supervisor(torch.tensor(xy,dtype=torch.float64)).numpy().ravel()
teacher=[]
for h in [1e-6,5e-7]:
    columns=[]
    for j in range(2):
        delta=np.zeros_like(xy);delta[:,j]=h
        plus=supervisor(torch.tensor(xy+delta,dtype=torch.float64)).numpy().ravel()
        minus=supervisor(torch.tensor(xy-delta,dtype=torch.float64)).numpy().ravel()
        columns.append((plus-minus)/(2*h))
    norm=np.linalg.norm(np.column_stack(columns),axis=1)
    teacher.append({'fd_step_m':h,'eikonal_rms_global':float(np.sqrt(np.mean((norm-1)**2))),
        'eikonal_rms_within_2mm_proxy_band':float(np.sqrt(np.mean((norm[np.abs(values)<.002]-1)**2))),
        'global_gradient_norm_quantiles':np.quantile(norm,[0,.1,.5,.9,1]).tolist()})
result['supervision_eikonal_audit']=teacher

for weight in [.1,0.0]:
    model=SirenImplicitField2D(bounds=driver.DEFAULT_GEOMETRY_BOUNDS,hidden_features=64,hidden_layers=2,omega_0=10,random_seed=0,dtype=torch.float64)
    report=pretrain_implicit_field(model,supervisor,bounds=driver.DEFAULT_GEOMETRY_BOUNDS,steps=6000,eikonal_weight=weight,random_seed=0)
    geometry=target.geometry_config(128)
    converted=build_ordered_sdf_geometry(model,geometry)
    distances=target.boundary_distances(converted.curve.points)
    arm={'eikonal_weight':weight,'pretraining':report.to_dict() if hasattr(report,'to_dict') else vars(report),
         'method_b_maximum_node_to_target_m':float(np.max(distances)),'method_b_normalized_field_residual_m':converted.maximum_normalized_curve_residual,'raw_zero_set':[]}
    field=TorchImplicitField2D(model,device='cpu',dtype=torch.float64)
    for grid,samples in [(257,512),(513,512),(513,1024)]:
        raw=prepare_single_component(field,FrontendConfig(bounds=geometry.bounds,grid_shape=(grid,grid),projected_samples=samples)).projected_points
        errors=target.boundary_distances(raw)
        arm['raw_zero_set'].append({'grid':grid,'samples':samples,'maximum_raw_node_to_target_m':float(errors.max()),'mean_raw_node_to_target_m':float(errors.mean())})
    with torch.no_grad():
        pred=model(torch.tensor(xy,dtype=torch.float64)).numpy().ravel()
    arm['heldout_proxy_fit_rms_m']=float(np.sqrt(np.mean((pred-values)**2)))
    p=OUT/f'star-pretraining-eikonal-{weight}.pt'
    torch.save({'state_dict':model.state_dict(),'eikonal_weight':weight,'metadata':model.initialization_metadata()},p)
    arm['checkpoint']=p.name;arm['checkpoint_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    result['arms'].append(arm)
    (OUT/'pretraining.json').write_text(json.dumps(result,indent=2)+'\n')
    print(arm,flush=True)
result['finished_utc']=datetime.now(timezone.utc).isoformat()
(OUT/'pretraining.json').write_text(json.dumps(result,indent=2)+'\n')
print('TEACHER',teacher,flush=True)
