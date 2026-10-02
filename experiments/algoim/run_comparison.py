#!/usr/bin/env python3
"""Algoim vs Method B on an ellipse and a real saved SIREN zero contour."""
from __future__ import annotations
import os
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "solvers"))
import numpy as np
from scipy.special import ellipe
import torch
torch.set_num_threads(1)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
if __package__:
    from .build import build
else:
    from build import build
from sdf_inverse.models import SirenImplicitField2D
from sdf_inverse.geometry import OrderedSDFGeometryConfig, build_ordered_sdf_geometry
from sdf_inverse.method_b_pullback import build_method_b_pullback
from sdf_to_ordered_boundary import fit_method_b_from_samples, MethodBConfig


def export_siren(model, path):
    layers = model.network.network
    with path.open("w") as stream:
        print(*model.origin.tolist(), model.length_scale, len(layers), file=stream)
        for layer in layers:
            linear = getattr(layer, "linear", layer)
            print(linear.in_features, linear.out_features, getattr(layer, "omega_0", 0), file=stream)
            print(*linear.weight.detach().flatten().tolist(), file=stream)
            print(*linear.bias.detach().flatten().tolist(), file=stream)


def quadrature(executable, field, cells, order, *, delta=0.0, parameter=-1, extent=0.2):
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="algoim_nodes_") as temporary:
        path = Path(temporary) / "nodes.txt"
        subprocess.run([str(executable), str(field), str(cells), str(order), str(delta),
                        str(parameter), str(path), str(extent)], capture_output=True, text=True, check=True)
        elapsed = time.perf_counter() - start
        nodes = np.loadtxt(path, ndmin=2)
    if nodes.shape[1] != 3 or np.any(nodes[:, 2] <= 0) or not np.isfinite(nodes).all():
        raise ValueError("Algoim returned invalid positive surface quadrature.")
    return nodes, {"cells_per_axis": cells, "gauss_order": order, "nodes": len(nodes),
                   "perimeter_m": float(nodes[:, 2].sum()), "seconds": elapsed}


def neural_quantities(model, nodes):
    coordinates = torch.tensor(nodes[:, :2], dtype=torch.float64, requires_grad=True)
    phi = model(coordinates).flatten()
    gradient, = torch.autograd.grad(phi.sum(), coordinates, create_graph=True)
    hxx = torch.autograd.grad(gradient[:, 0].sum(), coordinates, retain_graph=True)[0]
    hyy = torch.autograd.grad(gradient[:, 1].sum(), coordinates, retain_graph=True)[0]
    norm = torch.linalg.vector_norm(gradient, dim=1)
    gx, gy = gradient.unbind(dim=1)
    curvature = (hxx[:, 0] * gy**2 - 2*hxx[:, 1]*gx*gy + hyy[:, 1]*gx**2)/norm**3
    w = torch.tensor(nodes[:, 2])
    # Hadamard derivative: Vn=-phi_p/|grad phi|, L'=integral kappa Vn ds.
    coefficient = (-w*curvature/norm).detach()
    last = model.network.network[-1]
    weight, bias = torch.autograd.grad((phi*coefficient).sum(), (last.weight,last.bias))
    return {
        "max_neural_zero_residual_m": float(phi.detach().abs().max()),
        "minimum_gradient_norm": float(norm.detach().min()),
        "area_by_divergence_m2": float((0.5*w*(coordinates*gradient/norm[:, None]).sum(1)).detach().sum()),
        "normal_closure_m": torch.sum(w[:,None]*gradient/norm[:,None],0).detach().tolist(),
        "perimeter_bias_derivative": float(bias[0]),
        "perimeter_final_weight_derivatives": weight.flatten().tolist(),
    }


def main():
    output = ROOT / "results/algoim"
    output.mkdir(parents=True, exist_ok=True)
    executable = build()
    report = {"upstream": json.loads((HERE/"upstream.json").read_text()), "ellipse": [], "ellipse_nonvertex_aligned": [],
              "neural_algoim": [], "neural_method_b": [], "derivative_checks": []}
    exact = 4*.05*ellipe(1-(.035/.05)**2)
    report["ellipse_exact_perimeter_m"] = float(exact)
    for cells in (8,16,32):
        for order in (2,4,6,8):
            _, row = quadrature(executable, "ellipse", cells, order, extent=.08)
            row["relative_error"] = abs(row["perimeter_m"]-exact)/exact
            report["ellipse"].append(row)
    # Separate the finite-precision sensitivity of exact cell-vertex tangencies.
    for cells in (8,16,32):
        _, row = quadrature(executable, "ellipse", cells, 8, extent=.083)
        row["relative_error"] = abs(row["perimeter_m"]-exact)/exact
        row["bounding_box_half_width_m"] = .083
        report["ellipse_nonvertex_aligned"].append(row)
    angles = 2*np.pi*np.arange(256)/256
    points = .5+np.column_stack((.05*np.cos(angles),.035*np.sin(angles)))
    ellipse_b = fit_method_b_from_samples(angles, points, config=MethodBConfig(bandwidth=20))
    parameterization = ellipse_b.parameterization
    curve = parameterization.discretize(256)
    report["ellipse_method_b"] = {"perimeter_m": float(curve.arc_length_weights.sum()),
        "relative_error": float(abs(curve.arc_length_weights.sum()-exact)/exact)}
    # Safe, self-contained snapshot of the saved weights. The historical PT is
    # locally ignored and must not be required for fresh-checkout reproduction.
    checkpoint_path = ROOT / "results/algoim/input/siren_circle.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    constructor = dict(checkpoint["constructor"])
    constructor["dtype"] = torch.float64
    model = SirenImplicitField2D(**constructor)
    model.load_state_dict({key: torch.tensor(value, dtype=torch.float64)
                           for key, value in checkpoint["state_dict"].items()})
    weights_file = executable.parent / "siren.txt"
    export_siren(model, weights_file)
    report["checkpoint"] = {"path": str(checkpoint_path.relative_to(ROOT)),
        "sha256": sha256(checkpoint_path.read_bytes()).hexdigest(),
        "source_checkpoint": checkpoint["source_checkpoint"],
        "parameters": model.num_network_parameters,
        "description": "Saved accepted SIREN circle inversion, iteration 60; its learned contour is not an exact circle."}
    for cells, order in [(16,4),(16,6),(32,6),(32,8)]:
        nodes, row = quadrature(executable, weights_file, cells, order)
        row.update(neural_quantities(model, nodes))
        report["neural_algoim"].append(row)
        print("neural_algoim",cells,order,row["perimeter_m"],row["seconds"],flush=True)
        (output/"metrics.json").write_text(json.dumps(report,indent=2)+"\n")
    ref = report["neural_algoim"][-1]["perimeter_m"]
    for row in report["neural_algoim"]:
        row["relative_difference_from_refined"] = abs(row["perimeter_m"]-ref)/ref
    configuration = OrderedSDFGeometryConfig(**checkpoint["geometry_config"])
    final = model.network.network[-1]
    selected = np.argsort(np.abs(report["neural_algoim"][-1]["perimeter_final_weight_derivatives"]))[-2:].tolist()
    for bandwidth in (20,40,64):
        cfg = replace(configuration, bandwidth=bandwidth, num_nodes=256,
                      projected_samples=256, arclength_dense_resolution=2048,
                      validation_resolution=1024)
        begin = time.perf_counter()
        result = build_ordered_sdf_geometry(model,cfg)
        elapsed = time.perf_counter()-begin
        pullback = build_method_b_pullback(model,cfg,reference_curve=result.curve)
        perimeter = torch.linalg.vector_norm(pullback.first_derivatives,dim=1).sum()*(2*np.pi/256)
        weight_gradient, bias_gradient = torch.autograd.grad(perimeter,(final.weight,final.bias))
        row = {"bandwidth":bandwidth,"nodes":256,"seconds":elapsed,
               "perimeter_m":float(perimeter.detach()),
               "relative_difference_from_algoim_refined":abs(float(perimeter.detach())-ref)/ref,
               "max_replay_error_m":pullback.maximum_replay_error,
               "perimeter_bias_derivative":float(bias_gradient[0]),
               "perimeter_selected_weight_derivatives":{str(i):float(weight_gradient[0,i]) for i in selected}}
        report["neural_method_b"].append(row)
        print("method_b",row,flush=True)
    reference_quantities = report["neural_algoim"][-1]
    for parameter in [-1]+selected:
        analytic = reference_quantities["perimeter_bias_derivative"] if parameter<0 else reference_quantities["perimeter_final_weight_derivatives"][parameter]
        for step in (1e-5,3e-6):
            plus,_ = quadrature(executable,weights_file,32,8,delta=step,parameter=parameter)
            minus,_ = quadrature(executable,weights_file,32,8,delta=-step,parameter=parameter)
            fd = (plus[:,2].sum()-minus[:,2].sum())/(2*step)
            report["derivative_checks"].append({"final_layer_parameter":parameter,"step":step,
                "continuum_shape_derivative":analytic,"recomputed_quadrature_fd":float(fd),
                "relative_error":float(abs(fd-analytic)/abs(analytic))})
    np.savez_compressed(output/"refined_quadrature.npz",nodes_m=nodes[:,:2],weights_m=nodes[:,2],
                        method_b_nodes_m=result.curve.points)
    (output/"metrics.json").write_text(json.dumps(report,indent=2)+"\n")
    fig,ax=plt.subplots(1,3,figsize=(12,3.7),constrained_layout=True)
    for cells in (8,16,32):
        rows=[r for r in report['ellipse'] if r['cells_per_axis']==cells]
        ax[0].semilogy([r['gauss_order'] for r in rows],[max(r['relative_error'],1e-16) for r in rows],'o-',label=f'{cells}² cells')
    ax[0].set(xlabel='Gauss order',ylabel='Relative perimeter error',title='Analytic ellipse')
    ax[0].legend(fontsize=8)
    ax[1].scatter(nodes[:,0],nodes[:,1],s=2,label='Algoim q=8')
    ax[1].plot(*result.curve.points.T,'k--',lw=.7,label='Method B, band 64')
    ax[1].set(xlabel='x (m)',ylabel='y (m)',aspect='equal',title='Saved neural contour')
    ax[1].legend(fontsize=8)
    ax[2].semilogy([r['bandwidth'] for r in report['neural_method_b']],
                   [r['relative_difference_from_algoim_refined'] for r in report['neural_method_b']],'o-')
    ax[2].set(xlabel='Method B bandwidth',ylabel='Relative difference from Algoim',title='Neural perimeter convergence')
    fig.savefig(output/'comparison.png',dpi=170)
    plt.close(fig)
    assert max(r['relative_error'] for r in report['ellipse'] if r['gauss_order']==8)<1e-8
    assert reference_quantities['max_neural_zero_residual_m']<1e-10
    assert max(r['relative_error'] for r in report['derivative_checks'])<1e-3


if __name__=="__main__":
    main()
