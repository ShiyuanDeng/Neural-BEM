"""Half-space buried disk qualification, including independent volume scattering."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.integrate import quad_vec
from ordered_boundary import circle
from experiments.support_certificates.core import volume_operator
from experiments.support_certificates.layered import Layered
from .sommerfeld import Sommerfeld, buried_scattering, outgoing_beta, fresnel

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'results/halfspace'


def write(name,value):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/name).write_text(json.dumps(value,indent=2,default=lambda x:x.tolist())+'\n')


def adaptive_kernel(ka,kg,target,source,cutoff=400.):
    """Independent scipy adaptive integration on the raw positive spectral axis."""
    dx=target[0]-source[0]
    def function(xi):
        ba,bg=outgoing_beta(ka,xi),outgoing_beta(kg,xi)
        return 1j/np.pi*np.cos(xi*dx)*np.exp(1j*ba*source[1]-1j*bg*target[1])/(ba+bg)
    breaks=sorted(set([0.,complex(ka).real,complex(kg).real,cutoff]))
    values,errors=[],[]
    for a,b in zip(breaks[:-1],breaks[1:]):
        value,error=quad_vec(function,a,b,epsabs=1e-12,epsrel=1e-11)
        values.append(value);errors.append(error)
    return sum(values),sum(errors)


def volume_disk(layer,ki,center,radius,sources,receivers,n,subpixels=8):
    """Independent full-volume Lippmann-Schwinger solve, no Born approximation.

    Fractional boundary cells use subpixel occupancy; local singular integration
    uses the existing equal-area disk diagonal. This is an independently
    convergent discretization, not an exact continuum reference.
    """
    started=perf_counter()
    h=2*radius/n
    axis=-radius+(np.arange(n)+.5)*h
    x,y=np.meshgrid(axis,axis)
    points=np.column_stack((x.ravel(),y.ravel()))+center
    offsets=((np.arange(subpixels)+.5)/subpixels-.5)*h
    fraction=np.zeros(len(points))
    for ox in offsets:
        for oy in offsets:
            fraction+=np.linalg.norm(points+[ox,oy]-center,axis=1)<radius
    fraction/=subpixels**2
    keep=fraction>0
    points,fraction=points[keep],fraction[keep]
    operator=volume_operator(layer.kg,points,h*h)+layer.kg**2*h*h*layer.reflected(points,points)
    incident=layer.transmitted(points,sources)
    chi=(ki**2/layer.kg**2-1)*fraction
    polarization=np.linalg.solve(np.eye(len(points))-chi[:,None]*operator,chi[:,None]*incident)
    result=layer.kg**2*h*h*layer.transmitted(points,receivers).T@polarization
    return result,dict(grid=n,unknowns=len(points),cell_width_m=h,
        represented_area_m2=float(np.sum(fraction)*h*h),true_area_m2=np.pi*radius**2,
        seconds=perf_counter()-started,factorizations=1,rhs_columns=len(sources),subpixels=subpixels)


def main():
    ka=15.707963267948966
    cases=[('lossless',ka*np.sqrt(6.),ka*np.sqrt(3.)),
           ('lossy',ka*np.sqrt(6.+.48j),ka*np.sqrt(3.+.24j))]
    center,radius=np.array([.015,-.15]),.025
    sources=np.array([[-.12,.06],[.13,.08]])
    receivers=np.column_stack((np.linspace(-.2,.2,21),np.full(21,.05)))
    report=dict(route='Sommerfeld layered Green function + existing Muller/Kress, not WGF',
        kair=ka,center_m=center,radius_m=radius,sources=sources,receivers=receivers,cases=[])
    for label,kg,ki in cases:
        ref=buried_scattering(circle(center=tuple(center),radius=radius).discretize(192),
            ka,kg,ki,sources,receivers,order=192,cutoff=600.)
        norm=np.linalg.norm(ref.scattered)
        rows=[]
        for nodes,order,cutoff in [(32,24,300.),(64,48,300.),(96,96,300.),(96,192,300.),
                                    (96,192,150.),(96,192,200.),(96,192,400.)]:
            solved=buried_scattering(circle(center=tuple(center),radius=radius).discretize(nodes),
                ka,kg,ki,sources,receivers,order=order,cutoff=cutoff)
            rows.append(dict(nodes=nodes,order=order,cutoff=cutoff,spectral_nodes=solved.spectral_nodes,
                relative_to_ref=float(np.linalg.norm(solved.scattered-ref.scattered)/norm),
                equation_residual=solved.residual,seconds=solved.seconds,factorizations=1,rhs_columns=len(sources)))
        layer=Sommerfeld(ka,kg,order=128,cutoff=400.)
        target=np.array([.035,-.125])
        integrated,error=adaptive_kernel(ka,kg,target,sources[0])
        fixed=layer.transmitted(target[None],sources[:1])[0,0]
        legacy=Layered(ka,kg,order=128,cutoff=400.).transmitted(target[None],sources[:1])[0,0]
        volumes=[]
        for n in (12,20,32,48):
            data,row=volume_disk(layer,ki,center,radius,sources,receivers,n)
            row['relative_to_bie']=float(np.linalg.norm(data-ref.scattered)/norm)
            volumes.append(row)
            print(label,'volume',row,flush=True)
        row=dict(label=label,ksoil=[complex(kg).real,complex(kg).imag],kobject=[complex(ki).real,complex(ki).imag],
            reference=dict(nodes=192,order=192,cutoff=600.,equation_residual=ref.residual,seconds=ref.seconds,
                           factorizations=1,rhs_columns=len(sources)),boundary_convergence=rows,
            kernel_relative_to_adaptive=float(abs(fixed-integrated)/abs(integrated)),
            adaptive_absolute_error_bound=float(error),legacy_kernel_relative_to_adaptive=float(abs(legacy-integrated)/abs(integrated)),
            volume_convergence=volumes)
        report['cases'].append(row)
        OUTPUT.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(OUTPUT/f'{label}_data.npz',scattered=ref.scattered,sources=sources,receivers=receivers)
        write('qualification.json',report)
    # Plane-wave background, no-object Fresnel coefficients, and flux accounting.
    angles=np.linspace(0.,80.,9)
    r,t=fresnel(ka,ka*np.sqrt(6.),ka*np.sin(np.deg2rad(angles)))
    ba=outgoing_beta(ka,ka*np.sin(np.deg2rad(angles)))
    bg=outgoing_beta(ka*np.sqrt(6.),ka*np.sin(np.deg2rad(angles)))
    report['no_object_fresnel']=dict(incidence_degrees=angles,reflection_real=r.real,transmission_real=t.real,
        maximum_flux_defect=float(np.max(abs(abs(r)**2+bg.real/ba.real*abs(t)**2-1))))
    write('qualification.json',report)
    files=list((ROOT/'experiments/halfspace').glob('*.py'))+[ROOT/'experiments/support_certificates/layered.py',
          ROOT/'experiments/support_certificates/core.py',ROOT/'solvers/gpr_bem_kress/system.py']
    write('manifest.json',dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        cpu_only=True,blas_threads=1,scope='forward qualification only; one buried interface; equal permeability'))
    plot(report)


def plot(report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for row in report['cases']:
        boundary=row['boundary_convergence'][:4]
        axes[0].semilogy([d['order'] for d in boundary],[max(d['relative_to_ref'],1e-16) for d in boundary],'.-',label=row['label'])
        volume=row['volume_convergence']
        axes[1].loglog([d['grid'] for d in volume],[d['relative_to_bie'] for d in volume],'.-',label=row['label'])
    axes[0].set(xlabel='Spectral quadrature order per segment',ylabel='Relative scattered-field error',title='BIE + Sommerfeld refinement (N also refined)')
    axes[1].set(xlabel='Volume grid side count',ylabel='Relative difference from BIE',title='Independent volume integral comparison')
    for ax in axes:ax.grid(True,alpha=.3);ax.legend()
    fig.savefig(OUTPUT/'convergence.png',dpi=150)


if __name__=='__main__':
    main()
