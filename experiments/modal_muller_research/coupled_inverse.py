"""Coupled shape inversion and factored reciprocal derivatives.

Native states are component-major (u, canonical flux per component); the nodal
oracle stores all Dirichlet traces first. Multiple scattering is retained in
both primal and reciprocal illuminations. No cross-operator derivatives are
needed by the reciprocal identity.
"""
from dataclasses import dataclass,replace
from time import perf_counter
import numpy as np
from scipy.linalg import lu_factor,lu_solve
from scipy.optimize import least_squares
from scipy.signal import fftconvolve
from scipy.sparse.linalg import LinearOperator
from .inverse import ShapeChart,real_stack,wave_numbers
from .coefficient_operator import CoefficientGeometry,add,conjugate,multiply,times
from .coefficient_derivative import FixedAcquisition,ShapeFields,ShapeOperator,geometry_powers
from .coefficient_fields import cross_matrix


@dataclass
class SceneChart:
    charts: tuple
    center_bound: float = 1.5

    @property
    def slices(self):
        stops=np.r_[0,np.cumsum([c.size for c in self.charts])]
        return tuple(slice(a,b) for a,b in zip(stops[:-1],stops[1:]))

    @property
    def size(self):
        return sum(c.size for c in self.charts)

    def bounds(self):
        limits=[c.bounds() for c in self.charts]
        for lower,upper in limits:
            lower[:2]=-self.center_bound;upper[:2]=self.center_bound
        return tuple(np.concatenate([v[i] for v in limits]) for i in (0,1))

    def expanded(self,x,additions):
        charts=[];values=[]
        for index,(chart,sl) in enumerate(zip(self.charts,self.slices)):
            modes=tuple(m for component,m in additions if component==index and m not in chart.modes)
            charts.append(replace(chart,modes=chart.modes+modes))
            values.extend(np.r_[x[sl],np.zeros(2*len(modes))])
        return SceneChart(tuple(charts),self.center_bound),np.array(values)


def selected(values,paired):
    if paired:
        if values.shape[0]!=values.shape[1]:
            raise ValueError('Paired measurements require equal source and receiver counts.')
        return np.diag(values)
    return values.reshape(-1)


def trace_products(ur,us,paired,modal):
    if paired:
        a,b=ur,us
    else:
        a,b=ur[:,:,None],us[:,None,:]
    product=fftconvolve(a,b,axes=0) if modal else a*b
    return product.reshape(product.shape[0],-1)


class FactoredJacobian:
    """J_fc = L_fc W_c; exposes complex Jv and real-parameter adjoint actions.

    L contains physical trace products, W contains geometry directions. Neither
    action constructs the measurement-by-parameter Jacobian.
    """
    def __init__(self,blocks,slices,size):
        self.blocks,self.slices,self.size=blocks,slices,size
        self.output_shape=(len(blocks),blocks[0][0][0].shape[0])
        self.actions=dict(jvp=0,vjp=0,dense=0)

    @property
    def stored_bytes(self):
        arrays={id(a):a for row in self.blocks for pair in row for a in pair}
        return sum(a.nbytes for a in arrays.values())

    def matvec(self,v):
        self.actions['jvp']+=1
        v=np.asarray(v).reshape(-1)
        return np.stack([sum(left@(right@v[sl]) for (left,right),sl in zip(row,self.slices))
                         for row in self.blocks])

    def rmatvec(self,w):
        self.actions['vjp']+=1
        w=np.asarray(w).reshape(self.output_shape)
        out=np.zeros(self.size)
        for values,row in zip(w,self.blocks):
            for (left,right),sl in zip(row,self.slices):
                out[sl]+=np.real(right.conj().T@(left.conj().T@values))
        return out

    def dense(self):
        self.actions['dense']+=1
        return np.stack([np.concatenate([left@right for left,right in row],axis=1)
                         for row in self.blocks])

    def real_operator(self,scales,penalty):
        scales=np.asarray(scales)[:,None]
        count=np.prod(self.output_shape)
        def mv(v):
            v=np.asarray(v).reshape(-1)
            return np.r_[real_stack(self.matvec(v)/scales),penalty*v]
        def rmv(w):
            w=np.asarray(w).reshape(-1)
            complex_values=(w[:count]+1j*w[count:2*count]).reshape(self.output_shape)
            return self.rmatvec(complex_values/scales)+penalty*w[2*count:]
        return LinearOperator((2*count+self.size,self.size),matvec=mv,rmatvec=rmv,dtype=float)


class TraceJacobian(FactoredJacobian):
    """Reciprocal actions without materializing all source/receiver products.

    Modal Jv uses a Hankel coefficient matrix H_ij = weight_(i+j).
    The adjoint contracts the data weights with receiver/source traces, then
    sums coefficient anti-diagonals. Storage excludes any data-by-shape matrix
    and any mode-by-receiver-by-source product tensor.
    """
    def __init__(self,blocks,slices,size,paired,modal):
        self.blocks,self.slices,self.size=blocks,slices,size
        self.paired,self.modal=paired,modal
        ur,us,_,_=blocks[0][0]
        self.output_shape=(len(blocks),us.shape[1] if paired else ur.shape[1]*us.shape[1])
        self.actions=dict(jvp=0,vjp=0,dense=0)
        n=ur.shape[0]
        self.sums=np.add.outer(np.arange(n),np.arange(n)) if modal else None

    @property
    def stored_bytes(self):
        arrays={id(a):a for row in self.blocks for entry in row for a in entry if isinstance(a,np.ndarray)}
        return sum(a.nbytes for a in arrays.values())+(0 if self.sums is None else self.sums.nbytes)

    def matvec(self,v):
        self.actions['jvp']+=1
        v=np.asarray(v).reshape(-1)
        values=[]
        for row in self.blocks:
            out=np.zeros(self.output_shape[1],complex)
            for (ur,us,weights,contrast),sl in zip(row,self.slices):
                weight=weights@v[sl]
                moved=weight[self.sums]@us if self.modal else weight[:,None]*us
                out+=contrast*(np.sum(ur*moved,axis=0) if self.paired else (ur.T@moved).reshape(-1))
            values.append(out)
        return np.stack(values)

    def rmatvec(self,w):
        self.actions['vjp']+=1
        w=np.asarray(w).reshape(self.output_shape)
        out=np.zeros(self.size)
        for values,row in zip(w,self.blocks):
            for (ur,us,weights,contrast),sl in zip(row,self.slices):
                mixed=ur.conj()*values[None,:] if self.paired else ur.conj()@values.reshape(ur.shape[1],us.shape[1])
                if self.modal:
                    pair=mixed@us.conj().T
                    moments=(np.bincount(self.sums.ravel(),weights=pair.real.ravel())
                             +1j*np.bincount(self.sums.ravel(),weights=pair.imag.ravel()))
                else:
                    moments=np.sum(mixed*us.conj(),axis=1)
                out[sl]+=np.real(np.conj(contrast)*(weights.conj().T@moments))
        return out

    def dense(self):
        self.actions['dense']+=1
        blocks=[[(contrast*trace_products(ur,us,self.paired,self.modal).T,weights)
                 for ur,us,weights,contrast in row] for row in self.blocks]
        return FactoredJacobian(blocks,self.slices,self.size).dense()


class NativeScene:
    def __init__(self,chart,x,acquisitions,ki,cutoff,bandwidth,terms):
        self.chart,self.cutoff=chart,cutoff
        self.geometries=[c.geometry(x[sl]) for c,sl in zip(chart.charts,chart.slices)]
        prepared=[CoefficientGeometry(g,bandwidth) for g in self.geometries]
        powers=[geometry_powers(g,terms) for g in prepared]
        self.states=[];self.outputs=[]
        for acqs,wave in zip(acquisitions,ki):
            operators=[ShapeOperator(g,a.wave,wave,cutoff,terms,p)
                       for g,a,p in zip(prepared,acqs,powers)]
            fields=[ShapeFields(g,a,bandwidth,cutoff,terms) for g,a in zip(self.geometries,acqs)]
            matrix=np.block([[op.a if i==j else cross_matrix(fields[i].waves,fields[j].waves,cutoff)
                              for j in range(len(fields))] for i,op in enumerate(operators)])
            factors=lu_factor(matrix)
            u=lu_solve(factors,np.concatenate([f.b for f in fields]))
            self.outputs.append(np.concatenate([f.c for f in fields],axis=1)@u)
            self.states.append((fields,factors,u,wave))

    def sensitivity(self,paired,representation='products'):
        m=self.cutoff;n=2*m+1
        weights=[]
        for chart,geometry in zip(self.chart.charts,self.geometries):
            normal={(j,):j*v for j,v in geometry.coefficients.items()}
            columns=[]
            for dz in chart.directions():
                delta={(j,):v for j,v in dz.items()}
                poly=times(add(multiply(delta,conjugate(normal)),multiply(conjugate(delta),normal)),
                           .5*geometry.scale**2)
                column=np.zeros(4*m+1,complex)
                for (j,),value in poly.items():
                    if abs(j)<=2*m:
                        column[2*m-j]+=value
                columns.append(column)
            weights.append(np.stack(columns,axis=1))
        blocks=[]
        for fields,factors,u,ki in self.states:
            receiver_rhs=[]
            for f in fields:
                indices=f.bandwidth+np.arange(-m,m+1)
                values,flux=f.waves.values[:,2:-2],f.waves.flux[:,2:-2]
                receiver_rhs.append(np.concatenate((values[indices]@f.acquisition.receiver_weights,
                                                     flux[indices]@f.acquisition.receiver_weights)))
            ur=lu_solve(factors,np.concatenate(receiver_rhs))
            row=[]
            for index,(f,weight) in enumerate(zip(fields,weights)):
                sl=slice(index*2*n,index*2*n+n)
                contrast=2*np.pi*(ki**2-f.acquisition.wave**2)
                if representation=='traces':
                    row.append((ur[sl],u[sl],weight,contrast))
                else:
                    row.append((contrast*trace_products(ur[sl],u[sl],paired,True).T,weight))
            blocks.append(row)
        if representation=='traces':
            return TraceJacobian(blocks,self.chart.slices,self.chart.size,paired,True)
        return FactoredJacobian(blocks,self.chart.slices,self.chart.size)


class NodalScene:
    def __init__(self,chart,x,acq,frequencies,nodes):
        from ordered_boundary import OrderedBoundary2D
        from gpr_bem_kress import Material
        from gpr_bem_kress.coupled_shape_derivative import build_coupled_base
        from gpr_bem_kress.execution import execution
        self.chart=chart
        curves=tuple(replace(c.parameterization(x[sl]),component_id=f'component-{index}').discretize(nodes,require_even=True)
                     for index,(c,sl) in enumerate(zip(chart.charts,chart.slices)))
        self.boundary=OrderedBoundary2D(curves)
        with execution(kernels='real_bessel'):
            self.states=[build_coupled_base(self.boundary,np.array(acq['source_points']),
                np.array(acq['receiver_points']),2*np.pi*f,acq['source_strength'],
                exterior=Material(**acq['exterior']),interior=Material(**acq['interior']),
                eps0=acq['eps0'],mu0=acq['mu0']) for f in frequencies]
        self.outputs=[s.Y for s in self.states]

    def sensitivity(self,paired,representation='products'):
        from gpr_bem_kress.multicomponent import multicomponent_incident_trace_on_boundary
        from gpr_bem_kress.execution import execution
        weights=[]
        for chart,curve in zip(self.chart.charts,self.boundary.components):
            columns=[np.sum(chart.direction_jets(curve.parameters,d)[0]*curve.normals,axis=1)
                     *curve.arc_length_weights for d in chart.directions()]
            weights.append(np.stack(columns,axis=1))
        blocks=[]
        with execution(kernels='real_bessel'):
            for base in self.states:
                d,n=multicomponent_incident_trace_on_boundary(self.boundary,base.receivers,base.system.k_exterior,1.)
                ur=base.factors.solve(np.concatenate((d,n),axis=1).T)
                contrast=base.system.k_interior**2-base.system.k_exterior**2
                if representation=='traces':
                    blocks.append([(ur[sl],base.U[sl],weight,contrast)
                                   for sl,weight in zip(self.boundary.component_slices,weights)])
                else:
                    blocks.append([(contrast*trace_products(ur[sl],base.U[sl],paired,False).T,weight)
                                   for sl,weight in zip(self.boundary.component_slices,weights)])
        if representation=='traces':
            return TraceJacobian(blocks,self.chart.slices,self.chart.size,paired,False)
        return FactoredJacobian(blocks,self.chart.slices,self.chart.size)

    def operator_jacobian(self,paired):
        from gpr_bem_kress.shape_derivative import KressDirection
        from gpr_bem_kress.coupled_shape_derivative import directional_operators,tangent_response
        from gpr_bem_kress.execution import execution
        directions=[]
        for index,(chart,curve) in enumerate(zip(self.chart.charts,self.boundary.components)):
            for d in chart.directions():
                row=[KressDirection() for _ in self.chart.charts]
                row[index]=KressDirection(*chart.direction_jets(curve.parameters,d))
                directions.append(tuple(row))
        with execution(kernels='real_bessel'):
            return np.stack([np.stack([selected(tangent_response(base,directional_operators(base,row)),paired)
                                      for row in directions],axis=-1) for base in self.states])


class SceneEvaluator:
    def __init__(self,chart,acq,frequencies,*,backend='native',cutoff=24,bandwidth=40,
                 terms=24,angular_order=24,nodes=64,paired=True):
        self.chart,self.acq,self.frequencies=chart,acq,tuple(frequencies)
        self.backend,self.nodes,self.paired=backend,nodes,paired
        self.options=dict(cutoff=cutoff,bandwidth=bandwidth,terms=terms)
        tick=perf_counter()
        ko,self.ki=wave_numbers(acq,frequencies)
        self.acquisitions=[[FixedAcquisition(c.anchor,c.scale,k,acq['source_points'],acq['receiver_points'],
            acq['source_strength'],angular_order) for c in chart.charts] for k in ko] if backend=='native' else []
        self.work=dict(setup_seconds=perf_counter()-tick,forward_seconds=0.,sensitivity_seconds=0.,
                       forward_evaluations=0,sensitivity_evaluations=0)
        self.x=self.base=None
        self.factors={}

    def forward(self,x):
        x=np.asarray(x)
        if self.x is None or not np.array_equal(x,self.x):
            tick=perf_counter()
            if self.backend=='native':
                self.base=NativeScene(self.chart,x,self.acquisitions,self.ki,**self.options)
            elif self.backend=='nodal':
                self.base=NodalScene(self.chart,x,self.acq,self.frequencies,self.nodes)
            else:
                raise ValueError(self.backend)
            self.x,self.factors=x.copy(),{}
            self.work['forward_seconds']+=perf_counter()-tick
            self.work['forward_evaluations']+=1
        return np.stack([selected(y,self.paired) for y in self.base.outputs])

    def sensitivity(self,x,representation='products'):
        self.forward(x)
        if representation not in ('products','traces'):
            raise ValueError(representation)
        if representation not in self.factors:
            tick=perf_counter()
            self.factors[representation]=self.base.sensitivity(self.paired,representation)
            self.work['sensitivity_seconds']+=perf_counter()-tick
            self.work['sensitivity_evaluations']+=1
        return self.factors[representation]


def invert_scene(chart,acq,frequencies,observed,initial,*,backend='native',regularization=.001,
                 continuation=True,jacobian_storage='dense',max_nfev=60,**options):
    tick=perf_counter();x=np.array(initial,dtype=float);history=[];records=[]
    penalty=np.concatenate([np.r_[np.zeros(3),np.repeat([(m/5)**2 for m in c.modes],2)*regularization]
                            for c in chart.charts])
    stages=[(0,),tuple(range(len(frequencies)))] if continuation and len(frequencies)>1 else [tuple(range(len(frequencies)))]
    for stage,indices in enumerate(stages):
        evaluator=SceneEvaluator(chart,acq,[frequencies[i] for i in indices],backend=backend,**options)
        target=observed[list(indices)]
        scales=np.linalg.norm(target,axis=1)*np.sqrt(len(indices))
        def residual(v):
            return np.r_[real_stack((evaluator.forward(v)-target)/scales[:,None]),penalty*v]
        def jacobian(v):
            factors=evaluator.sensitivity(v,'traces' if jacobian_storage=='linear_operator' else 'products')
            history.append(dict(stage=stage,elapsed_seconds=perf_counter()-tick,
                                residual_norm=float(np.linalg.norm(residual(v))),parameters=v.tolist()))
            if jacobian_storage=='linear_operator':
                return factors.real_operator(scales,penalty)
            if jacobian_storage!='dense':
                raise ValueError(jacobian_storage)
            return np.vstack((real_stack(factors.dense()/scales[:,None,None]),np.diag(penalty)))
        solver=dict(tr_solver='lsmr',tr_options=dict(atol=1e-12,btol=1e-12,maxiter=4*chart.size)) if jacobian_storage=='linear_operator' else {}
        result=least_squares(residual,x,jac=jacobian,bounds=chart.bounds(),x_scale=1.,
            ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=max_nfev,**solver)
        x=result.x
        records.append(dict(stage=stage,success=bool(result.success),message=result.message,nfev=result.nfev,
                            njev=result.njev,work=evaluator.work,residual_norm=float(np.linalg.norm(result.fun))))
    return dict(parameters=x.tolist(),seconds=perf_counter()-tick,stages=records,history=history,
                backend=backend,jacobian_storage=jacobian_storage)


def rank_scene_modes(chart,x,acq,frequencies,observed,*,candidates=(4,5,6,7),noise_fraction=.01,**options):
    tick=perf_counter()
    additions=[(i,m) for i,c in enumerate(chart.charts) for m in candidates if m not in c.modes]
    expanded,v=chart.expanded(x,additions)
    evaluator=SceneEvaluator(expanded,acq,frequencies,**options)
    prediction=evaluator.forward(v)
    scales=np.linalg.norm(observed,axis=1)*np.sqrt(len(frequencies))
    residual=real_stack((prediction-observed)/scales[:,None])
    jac=real_stack(evaluator.sensitivity(v).dense()/scales[:,None,None])
    current=np.concatenate([np.arange(sl.start,sl.start+c.size) for c,sl in zip(chart.charts,expanded.slices)])
    u,s,_=np.linalg.svd(jac[:,current],full_matrices=False)
    active=u[:,s>1e-10*s[0]]
    residual-=active@(active.T@residual)
    rows=[]
    for component,mode in additions:
        c,sl=expanded.charts[component],expanded.slices[component]
        start=sl.start+3+2*c.modes.index(mode)
        k=jac[:,start:start+2].copy();k-=active@(active.T@k)
        step=np.linalg.lstsq(k,-residual,rcond=1e-10)[0]
        decrease=.5*(np.dot(residual,residual)-np.linalg.norm(residual+k@step)**2)
        rows.append(dict(component=component,mode=mode,predicted_loss_decrease=float(decrease),step=step.tolist()))
    rows.sort(key=lambda r:r['predicted_loss_decrease'],reverse=True)
    threshold=8*noise_fraction**2/len(residual)
    chosen=(rows[0]['component'],rows[0]['mode']) if rows and rows[0]['predicted_loss_decrease']>threshold else None
    return dict(selected=chosen,ranking=rows,noise_threshold=threshold,seconds=perf_counter()-tick,
                work=evaluator.work,selection_uses_truth=False)
