"""Sphere SDF narrow-band quadrature and weakly singular Müller transmission.

This is a sphere feasibility control, with exact spherical constant-density
row corrections. It is not an arbitrary-surface quadrature or a Maxwell solver.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from time import perf_counter
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ.setdefault(key,'1')
import numpy as np
from scipy.linalg import solve
from scipy.special import spherical_jn, spherical_yn, eval_legendre


def narrow_band(spacing, width_factor=1.5, radius=1., shift=(.137,.271,.389)):
    """Coarea weights δ_e(d)(R/|x|)^2 h^3 at closest points of |x|-R."""
    if not np.all(np.isfinite([spacing,width_factor,radius])) or spacing<=0 or width_factor<=0 or radius<=0:
        raise ValueError('Spacing, width factor and radius must be positive.')
    if np.asarray(shift).shape != (3,) or not np.all(np.isfinite(shift)):
        raise ValueError('Grid shift must have three finite coordinates.')
    width=width_factor*spacing
    if width>=radius:
        raise ValueError('Band must exclude the sphere centre.')
    axes=[np.arange(-radius-width,radius+width+spacing,spacing)+spacing*s for s in shift]
    x=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1).reshape(-1,3)
    r=np.linalg.norm(x,axis=1);mask=abs(r-radius)<width
    x,r=x[mask],r[mask]; d=r-radius
    weights=(1+np.cos(np.pi*d/width))/(2*width)*(radius/r)**2*spacing**3
    points=radius*x/r[:,None]
    # Coincident closest points are one unknown; summing their coarea weights
    # preserves the discrete integral. The translated grid largely avoids them.
    rounded=np.round(points/radius,12)
    _,first,inverse=np.unique(rounded,axis=0,return_index=True,return_inverse=True)
    return points[first],np.bincount(inverse,weights=weights),dict(
        grid_spacing=spacing,band_width=width,band_grid_nodes=len(x),surface_unknowns=len(first),
        surface_area=float(weights.sum()),area_relative_error=float(abs(weights.sum()-4*np.pi*radius**2)/(4*np.pi*radius**2)),
        grid_shift=list(shift),coarea_jacobian='(R/|x|)^2')


def hankel(l,z,derivative=False):
    return spherical_jn(l,z,derivative=derivative)+1j*spherical_yn(l,z,derivative=derivative)


def eigenvalues(k,radius,l=0):
    x=k*radius
    j,jp=spherical_jn(l,x),spherical_jn(l,x,True)
    h,hp=hankel(l,x),hankel(l,x,True)
    return 1j*k*radius**2*j*h,1j*k*k*radius**2*jp*h-.5,1j*k**3*radius**2*jp*hp


def delta_radial(r,ke,ki):
    """G_e-G_i and two radial derivatives; series avoids small-r subtraction."""
    safe=np.where(r>0,r,1.)
    def direct(k):
        e=np.exp(1j*k*safe)/(4*np.pi)
        return e/safe,e*(1j*k/safe-1/safe**2),e*(-k*k/safe-2j*k/safe**2+2/safe**3)
    a,b=direct(ke),direct(ki)
    result=[x-y for x,y in zip(a,b)]
    near=(max(abs(ke),abs(ki))*r<.1)
    rn=r[near]
    sums=[np.zeros_like(rn,dtype=complex) for _ in range(3)]
    import math
    for m in range(1,19):
        c=((1j*ke)**m-(1j*ki)**m)/(4*np.pi*math.factorial(m))
        sums[0]+=c*rn**(m-1)
        if m>=2: sums[1]+=c*(m-1)*rn**(m-2)
        if m>=3: sums[2]+=c*(m-1)*(m-2)*rn**(m-3)
    for a,s in zip(result,sums):a[near]=s
    return result


def assemble(points,weights,ke,ki,radius=1.):
    points,weights=np.asarray(points),np.asarray(weights)
    if (points.ndim!=2 or points.shape[1]!=3 or weights.shape!=(len(points),)
        or not np.all(np.isfinite(points)) or not np.all(np.isfinite(weights)) or np.any(weights<=0)):
        raise ValueError('Require finite Nx3 sphere points and N positive weights.')
    if not np.isfinite(radius) or radius<=0 or not np.allclose(np.linalg.norm(points,axis=1),radius,rtol=1e-11,atol=0):
        raise ValueError('This correction is valid only for points on the stated sphere.')
    dot=(points/radius)@(points/radius).T
    r=np.sqrt(np.maximum(0,2*radius**2*(1-np.clip(dot,-1,1))))
    np.fill_diagonal(r,0.)
    v,g1,g2=delta_radial(r,ke,ki)
    safe=np.where(r>0,r,1.)
    k=g1*r/(2*radius)
    t=r*r/(4*radius**2)*(g2-g1/safe)-g1/safe*dot
    # For each cancelled operator integrate f(y)-f(x), and restore its exact
    # action on 1. This removes the 1/r singularity of ΔT on the sphere.
    corrected=[]
    constants=np.subtract(eigenvalues(ke,radius),eigenvalues(ki,radius))
    for kernel,value in zip((v,k,t),constants):
        a=kernel*weights[None,:]
        np.fill_diagonal(a,0.)
        np.fill_diagonal(a,value-a.sum(axis=1))
        corrected.append(a)
    v,k,t=corrected
    eye=np.eye(len(points))
    return np.block([[eye-k,v],[-t,eye+k]])


def receiver_field(points,weights,u,q,ke,receivers,radius=1.):
    delta=receivers[:,None,:]-points[None,:,:]
    r=np.linalg.norm(delta,axis=-1)
    g=np.exp(1j*ke*r)/(4*np.pi*r)
    gp=g*(1j*ke-1/r)
    d=-gp*np.sum(delta*(points/radius)[None,:,:],axis=-1)/r
    return (d*weights)@u-(g*weights)@q


def mie(ke,ki,receivers,radius=1.,maximum_order=45):
    r=np.linalg.norm(receivers,axis=1);cos=receivers[:,2]/r
    answer=np.zeros(len(r),complex)
    for l in range(maximum_order+1):
        je,ji=spherical_jn(l,ke*radius),spherical_jn(l,ki*radius)
        jep,jip=spherical_jn(l,ke*radius,True),spherical_jn(l,ki*radius,True)
        he,hep=hankel(l,ke*radius),hankel(l,ke*radius,True)
        ratio=(ki*jip*je-ke*jep*ji)/(ke*hep*ji-ki*jip*he)
        answer+=(2*l+1)*1j**l*ratio*hankel(l,ke*r)*eval_legendre(l,cos)
    return answer


def run_case(spacing,ke,contrast=4.,width_factor=1.5):
    if not np.all(np.isfinite([ke,contrast])) or ke<=0 or contrast<=0:
        raise ValueError('The sphere experiment requires positive finite kR and contrast.')
    start=perf_counter()
    points,weights,metrics=narrow_band(spacing,width_factor)
    ki=ke*np.sqrt(contrast)
    matrix=assemble(points,weights,ke,ki)
    assemble_seconds=perf_counter()-start
    incident=np.exp(1j*ke*points[:,2]);derivative=1j*ke*points[:,2]*incident
    rhs=np.r_[incident,derivative]
    tick=perf_counter();solution=solve(matrix,rhs,assume_a='gen');solve_seconds=perf_counter()-tick
    theta=np.linspace(.1,np.pi-.1,31)
    receivers=3*np.column_stack((np.sin(theta),np.zeros_like(theta),np.cos(theta)))
    field=receiver_field(points,weights,solution[:len(points)],solution[len(points):],ke,receivers)
    exact=mie(ke,ki,receivers)
    return dict(**metrics,kR=ke,contrast=contrast,field_relative_error=float(np.linalg.norm(field-exact)/np.linalg.norm(exact)),
                linear_residual=float(np.linalg.norm(matrix@solution-rhs)/np.linalg.norm(rhs)),
                matrix_bytes=matrix.nbytes,assemble_seconds=assemble_seconds,solve_seconds=solve_seconds,
                total_seconds=perf_counter()-start),field,exact


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--spacing',nargs='+',type=float,default=[.35,.28,.22,.17])
    p.add_argument('--kR',nargs='+',type=float,default=[1.,3.])
    p.add_argument('--width-factor',type=float,default=1.5)
    args=p.parse_args(argv)
    if args.output.exists() and any(args.output.iterdir()):raise FileExistsError('Use a new output directory.')
    args.output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for k in args.kR:
        for h in args.spacing:
            row,field,exact=run_case(h,k,width_factor=args.width_factor)
            rows.append(row)
            print(json.dumps(row),flush=True)
            (args.output/'convergence.json').write_text(json.dumps(rows,indent=2)+'\n')
            np.savez_compressed(args.output/f'k{k:g}_h{h:g}.npz',field=field,reference=exact)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(6,4),constrained_layout=True)
    for k in args.kR:
        r=[r for r in rows if r['kR']==k]
        ax.loglog([r['grid_spacing'] for r in r],[r['field_relative_error'] for r in r],'o-',label=f'kR={k:g}')
    ax.set_xlabel('SDF grid spacing / radius');ax.set_ylabel('field error vs 3-D Mie');ax.legend();ax.grid(alpha=.2)
    fig.savefig(args.output/'convergence.png',dpi=180)

if __name__=='__main__':main()
