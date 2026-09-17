"""Exact semidiscrete scalar-wave experiment, not a GPR field validation.

Tests the operator objective in a two-dimensional smooth inclusion family.
Positive/negative eigenspace truncation is followed by block Krylov
orthogonalization to recover a causal gauge, as in Borcea et al. (2024).
"""
from pathlib import Path
import json
import numpy as np
from scipy.linalg import eigh,qr


def positive_qr(a):
    q,r=qr(a,mode='economic')
    signs=np.where(np.diag(r)<0,-1.,1.)
    return q*signs,r*signs[:,None]


def matrices(data,second,n):
    s=data.shape[1]
    mass=np.empty((n*s,n*s));stiff=mass.copy();prop=mass.copy()
    for i in range(n):
        for j in range(n):
            sl=np.s_[i*s:(i+1)*s,j*s:(j+1)*s]
            mass[sl]=(data[i+j]+data[abs(i-j)])/2
            stiff[sl]=-(second[i+j]+second[abs(i-j)])/2
            prop[sl]=(data[i+j+1]+data[abs(i-j+1)]+data[abs(i+j-1)]+data[abs(i-j-1)])/4
    return mass,stiff,prop


def operator(mass,stiff,prop,s,rank=None,threshold=1e-7):
    values,vectors=eigh(mass)
    order=np.arange(len(values)-1,-1,-1);values=values[order];vectors=vectors[:,order]
    if rank is None:
        rank=max(s,(int(np.sum(values>threshold*values[0]))//s)*s)
    if values[rank-1]<=0:raise ValueError('Requested positive rank unavailable')
    v=vectors[:,:rank];w=v/np.sqrt(values[:rank])[None,:]
    pi=w.T@prop@w;aw=w.T@stiff@w
    b=np.sqrt(values[:rank])[:,None]*v[:s,:].T
    q,_=positive_qr(b);blocks=[q]
    for j in range(rank//s-1):
        candidate=pi@blocks[-1]
        full=np.concatenate(blocks,axis=1)
        for _ in range(2):candidate-=full@(full.T@candidate)
        block,r=positive_qr(candidate)
        if np.min(np.abs(np.diag(r)))<1e-13:raise ValueError('Krylov breakdown')
        blocks.append(block)
    basis=np.concatenate(blocks,axis=1)
    return basis.T@aw@basis,dict(rank=rank,smallest_retained=float(values[rank-1]),largest=float(values[0]),minimum=float(values[-1]),orthogonality=float(np.linalg.norm(basis.T@basis-np.eye(rank))))


class Wave:
    def __init__(self,nx=22,nz=28,snapshots=16,tau=.07,source_count=2):
        self.nx=nx;self.nz=nz;self.ns=source_count;self.snapshots=snapshots;self.tau=tau
        hx=1/(nx+1);hz=1.2/(nz+1)
        self.points=np.array([(x,z) for z in np.arange(1,nz+1)*hz for x in np.arange(1,nx+1)*hx])
        tx=(2*np.eye(nx)-np.eye(nx,k=1)-np.eye(nx,k=-1))/hx**2
        tz=(2*np.eye(nz)-np.eye(nz,k=1)-np.eye(nz,k=-1))/hz**2
        self.k=np.kron(np.eye(nz),tx)+np.kron(tz,np.eye(nx))
        self.source=np.zeros((nx*nz,source_count))
        source_x=[.35,.65] if source_count==2 else np.linspace(.22,.77,source_count)
        for j,position in enumerate([[sx,.12] for sx in source_x]):
            self.source[np.argmin(np.linalg.norm(self.points-position,axis=1)),j]=1.
        self.times=np.arange(2*snapshots)*tau

    def data(self,depth=.52,contrast=1.8,return_snapshots=False):
        r=np.linalg.norm(self.points-[.5,depth],axis=1)
        eps=1+(contrast-1)*.5*(1-np.tanh((r-.11)/.035))
        speed=1/np.sqrt(eps)
        a=speed[:,None]*self.k*speed[None,:]
        val,vec=eigh(a,check_finite=False,driver='evr')
        omega=np.sqrt(val)
        # Exactly zero low frequencies; a smooth band-limited pulse spectrum.
        pulse=np.exp(-.5*((omega-24)/7)**2)
        pulse[(omega<12)|(omega>40)]=0.
        b=(vec.T@(speed[:,None]*self.source))*pulse[:,None]
        cosine=np.cos(self.times[:,None]*omega[None,:])
        data=np.einsum('ki,tk,kj->tij',b,cosine,b,optimize=True)
        second=-np.einsum('ki,tk,kj->tij',b,cosine*val[None,:],b,optimize=True)
        if return_snapshots:
            u=np.concatenate([vec@(b*cosine[j,:,None]) for j in range(self.snapshots)],axis=1)
            return data,second,u,a
        return data,second


def extrema(v):
    return np.flatnonzero((v[1:-1]<v[:-2])&(v[1:-1]<v[2:]))+1


def run():
    out=Path('results/experiments/operator_rom_20260916');out.mkdir(parents=True,exist_ok=True)
    wave=Wave();data,second,u,a=wave.data(return_snapshots=True)
    m,s,p=matrices(data,second,wave.snapshots)
    checks=dict(mass_identity=float(np.linalg.norm(m-u.T@u)/np.linalg.norm(m)),
                stiffness_identity=float(np.linalg.norm(s-u.T@a@u)/np.linalg.norm(s)))
    target,info=operator(m,s,p,2);rank=info['rank']
    checks.update(info)
    depths=np.linspace(.25,.79,55)
    # Truth .52 lies exactly on this grid.
    raw=[];rom=[];rank_errors=[];datasets=[];seconds=[]
    for j,depth in enumerate(depths):
        d,dd=wave.data(depth=depth)
        datasets.append(d);seconds.append(dd)
        raw.append(float(np.linalg.norm(d-data)**2))
        mm,ss,pp=matrices(d,dd,wave.snapshots)
        try:
            op,meta=operator(mm,ss,pp,2,rank=rank)
            rom.append(float(np.linalg.norm(op-target)**2));rank_errors.append(None)
        except ValueError as error:
            rom.append(float('nan'));rank_errors.append(str(error))
        if j%10==0:print('depth',j,float(depth),'raw',raw[-1],'rom',rom[-1],flush=True)
    raw=np.array(raw);rom=np.array(rom)
    result=dict(checks=checks,depths=depths.tolist(),raw=raw.tolist(),rom=rom.tolist(),
                raw_minima=depths[extrema(raw)].tolist(),rom_minima=depths[extrema(rom)].tolist(),rank_errors=rank_errors)
    (out/'screen.json').write_text(json.dumps(result,indent=2))
    np.savez(out/'data.npz',depths=depths,observed=data,observed_second=second,data=np.array(datasets),second=np.array(seconds))
    print(json.dumps({k:result[k] for k in ('checks','raw_minima','rom_minima')},indent=2),flush=True)


if __name__=='__main__':run()
