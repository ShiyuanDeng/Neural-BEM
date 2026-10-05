"""Bounded ON-002 adapter screen. A failed physics gate never releases fitting."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time
import traceback

import numpy as np
import torch

from bem_inverse.io import write, digest
from bem_inverse.mie_localize import paired_data
from . import campaign as B
from . import on002_adapter as A

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/validation/cleaned_interfaces/ON-002"


def mie(problem, observation):
    c = problem.initial.coefficients
    # Qualification is the prescribed initial circle, never the target geometry.
    if problem.initial.band != 1 or abs(c[0]) > 1e-14 or abs(c[2]*problem.length_unit_m-.065) > 1e-14:
        raise ValueError("Expected prescribed 65 mm circle")
    k = observation.wavenumber
    cutoff = int(np.ceil(abs(k)*np.sqrt(max(problem.contrast, 1))*abs(c[2])+35))
    return paired_data(k, problem.contrast, [c[1]], [abs(c[2])],
        observation.acquisition.sources, observation.acquisition.receivers, cutoff)[0,0]*observation.acquisition.strength


def adjoint_check(frequency):
    C, _ = A.external()
    p = frequency.projected
    generator = torch.Generator(device=p.device).manual_seed(2002)
    def random():
        return torch.randn((1,p.num_basis),dtype=p.dtype,device=p.device,generator=generator)
    u, v = random(), random()
    chi = (frequency.contrast-1)*frequency.coefficients
    lhs = torch.sum(torch.conj(v)*C.collocation_a_forward(p,chi,u))
    rhs = torch.sum(torch.conj(C.collocation_a_adjoint(p,chi,v))*u)
    relative = float((abs(lhs-rhs)/torch.maximum(abs(lhs),abs(rhs))).cpu())
    # Sensor test uses only measured paired diagonal; all cross pairs are zero.
    u = random().expand(24,-1)
    z = torch.zeros_like(frequency.model.data)
    z.diagonal().copy_(torch.arange(1,25,device=p.device,dtype=p.real_dtype))
    sf = C.collocation_sensor_forward(frequency.model,p,chi,u)
    sa = C.collocation_sensor_adjoint(frequency.model,p,z)
    lhs = torch.sum(torch.conj(z)*sf)
    rhs = torch.sum(torch.conj(sa)*chi[None,:]*u)
    sensor_relative = float((abs(lhs-rhs)/torch.maximum(abs(lhs),abs(rhs))).cpu())
    return dict(system_relative=relative,sensor_relative=sensor_relative,
                off_pair_max=float(abs(sf-torch.diag(sf.diagonal())).max().cpu()))


def derivative_check(frequency, target):
    b = frequency.coefficients
    # Interface-supported bounded perturbation, fixed without target geometry.
    C, _ = A.external()
    pts = frequency.projected.centers
    direction = torch.cos(13*pts[:,0])*torch.sin(17*pts[:,1])*((b>.05)&(b<.95))
    if float(abs(direction).max().cpu()) <= 1e-12:
        raise ValueError("No nonzero interface-supported derivative direction")
    direction /= abs(direction).max()
    loss, grad, residuals = frequency.objective_gradient(target)
    exact = float(torch.sum(grad*direction).cpu())
    differences = []
    for epsilon in (1e-2, 3e-3, 1e-3):
        values=[]; true=[]
        for sign in (-1,1):
            pred, _, residual = frequency.predict(b+sign*epsilon*direction)
            values.append(float((.5*torch.sum(abs(pred-target)**2)/torch.sum(abs(target)**2)).cpu()))
            true.append(residual)
        fd = (values[1]-values[0])/(2*epsilon)
        differences.append(dict(epsilon=epsilon,finite_difference=fd,
            analytic=exact,relative=abs(fd-exact)/max(abs(fd),abs(exact),1e-12),
            true_residual=max(true)))
    return dict(loss=float(loss.cpu()),residuals=residuals,differences=differences,
                passed=any(r["relative"]<=1e-3 and r["true_residual"]<=1e-6 for r in differences))


def qualify(args):
    folder = OUT/args.batch
    folder.mkdir(exist_ok=False)
    started = time.perf_counter()
    B.verify(require_inputs=True)
    sources = [Path(A.__file__), Path(__file__), Path(B.__file__),
               ROOT/"experiments/benchmark/scenes.py", ROOT/"experiments/benchmark/test_on002.py"]
    # Record all actually-importable numerical sources; shared source lock is
    # held by launcher for the entire process, not just hash creation.
    sources += list((ROOT/"solvers").rglob("*.py"))
    sources += list((A.EXTERNAL/"src").rglob("*.py"))
    hashes = {str(p):digest(p) for p in sorted(sources)}
    write(folder/"manifest.json",dict(pixels=args.pixels,centers=args.centers,
        double=args.double,device=args.device,versions=A.versions(),source_hashes=hashes,
        contract="TG-002 adapted known-material GauGal; paired diagonal; circle initial state",
        field_target=1e-3,true_residual_target=1e-6,solver_iteration_cap=200,
        equation_normalization="A and RHS divided by physical testing cell area; kernel/readout unchanged",
        solver_rhs_normalization="unit 2-norm separately for every forward/adjoint channel; physical solution restored",
        source_lock="launcher holds shared lock throughout process",
        compute_lock="launcher holds exclusive lock throughout process"))
    records=[]
    for contrast in args.contrasts:
        problem=B.problem(f"circle__c{contrast:g}")
        for catalog_name in args.catalogs:
            catalog=getattr(problem,catalog_name)
            for index in args.indices:
                o=catalog[index]
                tag=f"c{contrast:g}_{catalog_name}_f{o.frequency_hz/1e9:g}"
                row=dict(contrast=contrast,catalog=catalog_name,frequency_hz=o.frequency_hz,
                         pixels=args.pixels,centers=args.centers,double=args.double)
                before=time.perf_counter()
                frequency=None
                try:
                    print("BUILD",tag,flush=True)
                    frequency=A.build(problem,o,pixels=args.pixels,centers=args.centers,
                                      device=args.device,double=args.double)
                    row["build_seconds"]=frequency.build_seconds
                    row["equation_scale"]=1/frequency.model.cell_area
                    A.sync(args.device); solve=time.perf_counter()
                    pred, u, residual=frequency.predict()
                    A.sync(args.device)
                    row["solve_seconds"]=time.perf_counter()-solve
                    reference=mie(problem,o)
                    predicted=pred.detach().cpu().numpy()
                    row.update(true_residual=residual,
                        physical_relative=float(np.linalg.norm(predicted-reference)/np.linalg.norm(reference)),
                        linear_stats=frequency.projected.linear_solve_stats)
                    row["field_passed"]=bool(residual<=1e-6 and row["physical_relative"]<=1e-3)
                    row["adjoint"]=adjoint_check(frequency)
                    if args.derivative:
                        try:
                            target=torch.as_tensor(o.scattered.copy(),device=args.device,dtype=pred.dtype)
                            row["derivative"]=derivative_check(frequency,target)
                        except Exception:
                            row["derivative"]=dict(passed=False,traceback=traceback.format_exc())
                    image=frequency.render().detach().cpu().numpy()
                    np.savez_compressed(folder/(tag+".npz"),prediction=predicted,reference=reference,
                        occupancy=image,coefficients=frequency.coefficients.detach().cpu().numpy(),
                        x=frequency.model.x.cpu().numpy(),y=frequency.model.y.cpu().numpy())
                    row["native_occupancy_range"]=[float(image.min()),float(image.max())]
                except Exception:
                    row.update(field_passed=False,traceback=traceback.format_exc())
                row["total_seconds"]=time.perf_counter()-before
                records.append(row)
                write(folder/(tag+".json"),row)
                write(folder/"summary.json",dict(records=records,complete=False,
                    elapsed_seconds=time.perf_counter()-started))
                print("RESULT",tag,row.get("physical_relative"),row.get("true_residual"),
                      row.get("field_passed"),f'{row["total_seconds"]:.2f}s',flush=True)
                del frequency
                if args.device.startswith("cuda"):
                    torch.cuda.empty_cache()
    changes=[p for p,h in hashes.items() if digest(p)!=h]
    if changes:
        raise RuntimeError("Numerical sources changed during batch: "+str(changes))
    write(folder/"summary.json",dict(records=records,complete=True,
        elapsed_seconds=time.perf_counter()-started,source_hashes_unchanged=True,
        fields_qualified=all(r.get("field_passed",False) for r in records),
        adjoints_qualified=all(r.get("adjoint",{}).get("system_relative",float("inf"))<=1e-5
            and r.get("adjoint",{}).get("sensor_relative",float("inf"))<=1e-5
            and r.get("adjoint",{}).get("off_pair_max",float("inf"))==0 for r in records),
        derivatives_qualified=bool(args.derivative and all(r.get("derivative",{}).get("passed",False) for r in records))))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("batch")
    p.add_argument("--pixels",type=int,choices=(128,256,512),required=True)
    p.add_argument("--centers",type=int,choices=(112,224,448),required=True)
    p.add_argument("--device",default="cuda")
    p.add_argument("--double",action="store_true")
    p.add_argument("--contrasts",type=float,nargs="+",default=[.5,4,13.3])
    p.add_argument("--catalogs",nargs="+",choices=("real","damped"),default=["real","damped"])
    p.add_argument("--indices",type=int,nargs="+",choices=(0,18),default=[0,18])
    p.add_argument("--derivative",action="store_true")
    args=p.parse_args()
    if {128:112,256:224,512:448}[args.pixels]!=args.centers:
        p.error("Registered pixel/centre pair required")
    torch.set_num_threads(1)
    qualify(args)


if __name__=="__main__":
    main()
