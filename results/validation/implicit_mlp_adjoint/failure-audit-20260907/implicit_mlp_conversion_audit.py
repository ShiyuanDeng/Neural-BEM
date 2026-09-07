"""Frozen raw-versus-Method-B polygonal set distances at two sampling levels."""
import json
from pathlib import Path
from dataclasses import replace
import sys
import torch
import numpy as np
ROOT=Path('/home/drdeng/Neural_SDF_BEM_AD')
sys.path[:0]=[str(ROOT),str(ROOT/'solvers')]
from sdf_inverse.models import SirenImplicitField2D
from sdf_inverse.geometry import OrderedSDFGeometryConfig, build_ordered_sdf_geometry
from sdf_inverse.neural_optimization import maximum_curve_set_distance
from sdf_to_ordered_boundary import TorchImplicitField2D, FrontendConfig, prepare_single_component
import run_sdf_inverse_comparison as driver
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'results/validation/implicit_mlp_adjoint/failure-audit-20260907'
results=[]
for path in sorted((ROOT/'results/inverse/implicit_mlp').glob('*/metrics.json')):
    saved=torch.load(path.parent/'kress_model.pt',weights_only=True,map_location='cpu')
    constructor=dict(saved['constructor']);constructor['dtype']=torch.float64
    model=SirenImplicitField2D(**constructor);model.load_state_dict(saved['state_dict'])
    cfg=OrderedSDFGeometryConfig(**saved['geometry_config'])
    target=driver._build_target(json.loads(path.read_text())['target_shape'])
    field=TorchImplicitField2D(model,dtype=torch.float64,device='cpu')
    case={'run':path.parent.name,'records':[]}
    for count in [1024,2048]:
        # Fixed extraction grid and unchanged production conversion; vary curve audit density only.
        raw=prepare_single_component(field,FrontendConfig(bounds=cfg.bounds,grid_shape=(513,513),projected_samples=count)).projected_points
        curve=build_ordered_sdf_geometry(model,replace(cfg,num_nodes=count))
        case['records'].append({'samples':count,'raw_maximum_node_to_target_m':float(target.boundary_distances(raw).max()),
            'converted_maximum_node_to_target_m':float(target.boundary_distances(curve.curve.points).max()),
            'raw_to_converted_symmetric_vertex_to_polygon_m':maximum_curve_set_distance(raw,curve.curve.points)})
    results.append(case)
    (OUT/'conversion.json').write_text(json.dumps({'scope':'Frozen checkpoints; two sampling densities at fixed 513 grid. Polygonal set distance, not a certified continuous Hausdorff distance or full one-factor conversion study.','cases':results},indent=2)+'\n')
    print(case,flush=True)
