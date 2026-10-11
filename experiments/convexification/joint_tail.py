"""CVX-002 joint unknown tail and frequency-secant reconstruction.

This experimental inverse accepts augmented boundary data, never truth or an
interior reference field. Sparse field coordinates are equivalent to (V,z).
"""
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy import sparse as sp
from scipy.sparse.linalg import spsolve, lsmr


@dataclass
class Grid:
    n: int
    half: float = 2.4

    def __post_init__(self):
        n = self.n
        self.axis = np.linspace(-self.half, self.half, n)
        self.h = self.axis[1]-self.axis[0]
        xx, yy = np.meshgrid(self.axis, self.axis)
        self.points = np.column_stack((xx.ravel(), yy.ravel()))
        ids = np.arange(n*n).reshape(n, n)
        self.interior = ids[1:-1, 1:-1].ravel()
        self.boundary = np.setdiff1d(ids.ravel(), self.interior)
        # Counterclockwise boundary cycle with each corner once.
        self.cycle = np.r_[ids[0, :], ids[1:, -1], ids[-1, -2::-1], ids[-2:0:-1, 0]]
        d1 = sp.lil_matrix((n, n))
        d2 = sp.lil_matrix((n, n))
        for j in range(1, n-1):
            d1[j, j-1:j+2] = np.array([-1, 0, 1])/(2*self.h)
            d2[j, j-1:j+2] = np.array([1, -2, 1])/self.h**2
        d1[0, :3], d1[-1, -3:] = np.array([-3,4,-1])/(2*self.h), np.array([1,-4,3])/(2*self.h)
        d2[0, :4], d2[-1, -4:] = np.array([2,-5,4,-1])/self.h**2, np.array([-1,4,-5,2])/self.h**2
        d1, d2 = d1.tocsr(), d2.tocsr()
        eye = sp.eye(n, format='csr')
        self.dx, self.dy = sp.kron(eye,d1,format='csr'), sp.kron(d1,eye,format='csr')
        self.dxx, self.dyy = sp.kron(eye,d2,format='csr'), sp.kron(d2,eye,format='csr')
        self.lap = self.dxx+self.dyy
        terms = [sp.eye(n*n,format='csr'),self.dx,self.dy,self.dxx,self.dx@self.dy,self.dyy]
        self.h2 = sp.vstack(terms,format='csr')*self.h
        self.h3 = sp.vstack(terms+[self.dx@self.dxx,self.dy@self.dxx,
                                  self.dx@self.dyy,self.dy@self.dyy],format='csr')*self.h
        # Exclude corners from normals; one outward normal on each open face.
        self.normal_ids = np.r_[ids[1:-1,0],ids[1:-1,-1],ids[0,1:-1],ids[-1,1:-1]]
        self.normals = np.repeat([[-1,0],[1,0],[0,-1],[0,1]],n-2,axis=0)
        self.normal = sp.vstack([-self.dx[ids[1:-1,0]],self.dx[ids[1:-1,-1]],
                                  -self.dy[ids[0,1:-1]],self.dy[ids[-1,1:-1]]],format='csr')


@dataclass
class BoundaryData:
    k: np.ndarray
    values: np.ndarray  # (frequencies, all grid positions); only boundary used
    normal: np.ndarray  # (frequencies, face points)
    incident_gradient: np.ndarray  # (frequencies, all grid positions, 2)


class JointTail:
    def __init__(self, grid, data, span, h2=1e-5, h3=1e-6, c_reg=1e-7, normal_penalty=10.):
        self.grid, self.data, self.span = grid, data, span
        self.f = len(data.k)
        self.m, self.p = len(grid.interior), grid.n**2
        self.alpha2, self.alpha3, self.alpha_c = h2,h3,c_reg
        self.normal_penalty = normal_penalty
        self.dx,self.dy,self.lap = (a[grid.interior] for a in (grid.dx,grid.dy,grid.lap))
        self.inc = data.incident_gradient[:,grid.interior]
        psi = 1/np.sum((grid.points-np.array([3.4,0]))**2,axis=1)
        psi = (psi-psi.min())/(psi.max()-psi.min())
        w = np.exp(span*psi)
        w /= w[grid.interior].mean()
        self.weight = w
        self.pde_scale = grid.h*np.sqrt(w[grid.interior]/self.f)
        self.normal_scale = np.sqrt(normal_penalty*grid.h/self.f)
        t = (data.k-data.k[0])/(data.k[-1]-data.k[0])
        last = np.zeros((1,self.f)); last[0,-1]=1
        secants = np.zeros((self.f-1,self.f))
        for j in range(self.f-1):
            secants[j,j],secants[j,-1] = 1/(t[j]-1),-1/(t[j]-1)
        self.reg = sp.vstack([np.sqrt(h2)*sp.kron(last,grid.h2),
                              np.sqrt(h3/(self.f-1))*sp.kron(secants,grid.h3)],format='csr')
        self.normal_matrix = self.normal_scale*sp.block_diag([grid.normal]*self.f,format='csr')
        self.fixed = np.zeros((self.f,self.p),complex)
        self.fixed[:,grid.boundary] = data.values[:,grid.boundary]
        self.free_ids = np.concatenate([grid.interior+j*self.p for j in range(self.f)])
        self.fixed_flat = self.fixed.ravel()

    def residual(self, fields, coefficient):
        gx,gy = (fields@a.T for a in (self.dx,self.dy))
        return fields@self.lap.T+self.data.k[:,None]**2*(gx*gx+gy*gy)+2*(
            self.inc[:,:,0]*gx+self.inc[:,:,1]*gy)+coefficient[None,:]-1

    def objective(self, fields, coefficient):
        residual = self.residual(fields,coefficient)*self.pde_scale
        normal = self.normal_scale*(fields@self.grid.normal.T-self.data.normal)
        reg = self.reg@fields.ravel()
        cr = np.sqrt(self.alpha_c)*self.grid.h*(coefficient-1)
        parts = dict(pde=float(np.vdot(residual,residual).real),normal=float(np.vdot(normal,normal).real),
                     field_regularization=float(np.vdot(reg,reg).real),coefficient_regularization=float(cr@cr))
        return sum(parts.values()),parts

    def linear_system(self, fields):
        gx,gy = (fields@a.T for a in (self.dx,self.dy))
        blocks=[]
        for j,k in enumerate(self.data.k):
            op=self.lap+sp.diags(k*k*gx[j]+2*self.inc[j,:,0])@self.dx+sp.diags(k*k*gy[j]+2*self.inc[j,:,1])@self.dy
            blocks.append(sp.diags(self.pde_scale)@op)
        physics = sp.block_diag(blocks,format='csr')
        cc=sp.vstack([sp.diags(self.pde_scale)]*self.f,format='csr')
        ac=sp.vstack([physics,self.normal_matrix,self.reg],format='csr')
        cb=sp.vstack([cc,sp.csr_matrix((self.normal_matrix.shape[0]+self.reg.shape[0],self.m))],format='csr')
        rhs=np.r_[np.tile(self.pde_scale,self.f),self.normal_scale*self.data.normal.ravel(),
                  np.zeros(self.reg.shape[0])]-ac@self.fixed_flat
        ac=ac[:,self.free_ids]
        zeros=sp.csr_matrix((self.m,len(self.free_ids)))
        matrix=sp.vstack([sp.hstack([ac.real,-ac.imag,cb]),sp.hstack([ac.imag,ac.real,0*cb]),
                          sp.hstack([zeros,zeros,np.sqrt(self.alpha_c)*self.grid.h*sp.eye(self.m)])],format='csr')
        target=np.r_[rhs.real,rhs.imag,np.sqrt(self.alpha_c)*self.grid.h*np.ones(self.m)]
        return matrix,target

    def decode(self, x):
        n=len(self.free_ids)
        fields=self.fixed_flat.copy()
        fields[self.free_ids]=x[:n]+1j*x[n:2*n]
        return fields.reshape(self.f,self.p),x[2*n:]

    def solve_linear(self, fields):
        started=perf_counter()
        a,b=self.linear_system(fields)
        scale=1/np.maximum(np.sqrt(np.asarray(a.power(2).sum(axis=0)).ravel()),1e-15)
        scaled=a@sp.diags(scale)
        gram=(scaled.T@scaled).tocsc()
        rhs=scaled.T@b
        candidate=spsolve(gram,rhs)
        stationarity=float(np.linalg.norm(scaled.T@(scaled@candidate-b))/max(1,np.linalg.norm(rhs)))
        method='scaled_sparse_normal_equations'
        lsmr_receipt=None
        if not np.isfinite(candidate).all() or stationarity>1e-7:
            ls=lsmr(scaled,b,atol=1e-9,btol=1e-9,maxiter=2000)
            candidate=ls[0]; method='scaled_lsmr'
            stationarity=float(np.linalg.norm(scaled.T@(scaled@candidate-b))/max(1,np.linalg.norm(rhs)))
            lsmr_receipt=dict(istop=int(ls[1]),iterations=int(ls[2]),residual=float(ls[3]),normal_residual=float(ls[4]))
        receipt=dict(method=method,rows=a.shape[0],columns=a.shape[1],nnz=a.nnz,
                     normalized_stationarity=stationarity,seconds=perf_counter()-started,lsmr=lsmr_receipt)
        if stationarity>1e-7 or not np.isfinite(candidate).all():
            raise RuntimeError(f'Unqualified linear solve: {receipt}')
        return (*self.decode(candidate*scale),receipt)

    def fit(self, initial_fields, initial_coefficient, callback, iterations=12, wall_seconds=300):
        started=perf_counter()
        fields=np.array(initial_fields,copy=True)
        fields[:,self.grid.boundary]=self.data.values[:,self.grid.boundary]
        coefficient=np.array(initial_coefficient,copy=True)
        objective,parts=self.objective(fields,coefficient)
        history=[dict(iteration=0,objective=objective,parts=parts,elapsed_seconds=0)]
        callback(fields,coefficient,history,'RUNNING')
        stop='ITERATION_CAP'
        for iteration in range(1,iterations+1):
            if perf_counter()-started>=wall_seconds:
                stop='WALL_CAP';break
            vf,cf,receipt=self.solve_linear(fields)
            attempts=[]
            for fraction in (1.,.5,.25,.125,.0625,.03125):
                trial=fields+fraction*(vf-fields)
                ctrial=coefficient+fraction*(cf-coefficient)
                value,terms=self.objective(trial,ctrial)
                attempts.append(dict(fraction=fraction,objective=value))
                if np.isfinite(value) and value<objective-1e-12*max(1,objective):
                    relative=float(np.linalg.norm(np.r_[(trial-fields).ravel(),ctrial-coefficient])/
                                   max(1,np.linalg.norm(np.r_[fields.ravel(),coefficient])))
                    fields,coefficient,objective,parts=trial,ctrial,value,terms
                    history.append(dict(iteration=iteration,objective=value,parts=terms,fraction=fraction,
                                        relative_step=relative,linear=receipt,attempts=attempts,
                                        elapsed_seconds=perf_counter()-started))
                    callback(fields,coefficient,history,'RUNNING')
                    if relative<=1e-5:stop='SMALL_STEP'
                    break
            else:
                history.append(dict(iteration=iteration,accepted=False,linear=receipt,attempts=attempts,
                                    objective=objective,elapsed_seconds=perf_counter()-started))
                stop='NO_DECREASE';break
            if stop=='SMALL_STEP':break
        callback(fields,coefficient,history,stop)
        return fields,coefficient,history,stop

    def diagnostics(self, fields, coefficient):
        r=self.residual(fields,coefficient)
        normal=fields@self.grid.normal.T-self.data.normal
        ratio=np.exp(self.data.k[:,None]**2*fields)
        return dict(pde_rms=float(np.sqrt(np.mean(abs(r)**2))),
                    normal_relative=float(np.linalg.norm(normal)/max(1e-30,np.linalg.norm(self.data.normal))),
                    min_inferred_abs_u_over_u0=float(abs(ratio).min()),
                    max_inferred_abs_u_over_u0=float(abs(ratio).max()),
                    coefficient_min=float(coefficient.min()),coefficient_max=float(coefficient.max()),
                    weight_min=float(self.weight.min()),weight_max=float(self.weight.max()),
                    weight_ratio=float(self.weight.max()/self.weight.min()),
                    applied_weight_mean=float(self.weight[self.grid.interior].mean()),
                    applied_weight_min=float(self.weight[self.grid.interior].min()),
                    applied_weight_max=float(self.weight[self.grid.interior].max()))


def algebra_qualification():
    """Independent nonlinear directional derivative and linear-stacking checks."""
    grid=Grid(9)
    rng=np.random.default_rng(1926)
    k=np.array([.6,.9,1.2])
    data=BoundaryData(k,.03*(rng.normal(size=(3,81))+1j*rng.normal(size=(3,81))),
                      .01*(rng.normal(size=(3,len(grid.normal_ids)))+1j*rng.normal(size=(3,len(grid.normal_ids)))),
                      .2*rng.normal(size=(3,81,2))+.1j*rng.normal(size=(3,81,2)))
    model=JointTail(grid,data,4)
    fields=.01*(rng.normal(size=(3,81))+1j*rng.normal(size=(3,81)))
    direction=.02*(rng.normal(size=(3,81))+1j*rng.normal(size=(3,81)))
    coefficient=1+.1*rng.normal(size=model.m)
    dc=rng.normal(size=model.m)
    gx,gy=fields@model.dx.T,fields@model.dy.T
    hx,hy=direction@model.dx.T,direction@model.dy.T
    exact=direction@model.lap.T+2*k[:,None]**2*(gx*hx+gy*hy)+2*(model.inc[:,:,0]*hx+model.inc[:,:,1]*hy)+dc
    h=1e-5
    fd=(model.residual(fields+h*direction,coefficient+h*dc)-model.residual(fields-h*direction,coefficient-h*dc))/(2*h)
    derivative=float(np.linalg.norm(fd-exact)/np.linalg.norm(exact))
    # Independently evaluate the frozen PDE term in complex arithmetic.
    trial=direction.copy();trial[:,grid.boundary]=data.values[:,grid.boundary]
    a,b=model.linear_system(fields)
    x=np.r_[trial[:,grid.interior].real.ravel(),trial[:,grid.interior].imag.ravel(),coefficient]
    explicit=trial@model.lap.T+k[:,None]**2*(gx*(trial@model.dx.T)+gy*(trial@model.dy.T))+2*(
        model.inc[:,:,0]*(trial@model.dx.T)+model.inc[:,:,1]*(trial@model.dy.T))+coefficient-1
    t=(k-k[0])/(k[-1]-k[0])
    regularization=np.concatenate([np.sqrt(model.alpha2)*(grid.h2@trial[-1])]+
        [np.sqrt(model.alpha3/(len(k)-1))*(grid.h3@((trial[j]-trial[-1])/(t[j]-1))) for j in range(len(k)-1)])
    expected_complex=np.r_[(explicit*model.pde_scale).ravel(),
                          (model.normal_scale*(trial@grid.normal.T-data.normal)).ravel(),regularization]
    expected=np.r_[expected_complex.real,expected_complex.imag,
                   np.sqrt(model.alpha_c)*grid.h*(coefficient-1)]
    residual=a@x-b
    stacking=float(np.linalg.norm(residual-expected)/np.linalg.norm(expected))
    xx,yy=grid.points.T;polynomial=xx*xx+3*xx*yy+2*yy*yy
    stencil_error=max(np.max(abs(grid.dx@polynomial-(2*xx+3*yy))),
                      np.max(abs(grid.dy@polynomial-(3*xx+4*yy))),np.max(abs(grid.lap@polynomial-6)))
    rank=int(np.linalg.matrix_rank(a.toarray()))
    return dict(nonlinear_derivative_relative=derivative,linear_stacking_relative=stacking,
                polynomial_stencil_error=float(stencil_error),linear_rank=rank,linear_columns=a.shape[1],
                passed=derivative<1e-5 and stacking<1e-12 and stencil_error<1e-10 and rank==a.shape[1])
