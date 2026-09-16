"""Exploratory fixed-topology shape inversion with interchangeable BIE backends.

The native path never samples the boundary. The nodal path uses the existing
analytic coupled Kress derivative with retained LU factors. Only diagnostics
and the nodal comparator evaluate a geometric point grid.
"""
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from scipy.optimize import least_squares

from .coefficient_operator import LaurentGeometry
from .coefficient_derivative import FixedAcquisition, NativeShapeForward


@dataclass
class ShapeChart:
    """Radial Fourier shape chart for initial recovery experiments.

    The BIE accepts general Laurent geometry; this inverse chart intentionally
    removes tangential gauge freedom. Parameters: center offsets / 1 cm,
    radius / 4 cm, and cos/sin radial coefficients / 5 mm.
    """
    modes: tuple = (2,3,5)
    anchor: complex = .5+.5j
    scale: float = .04

    @property
    def size(self):
        return 3+2*len(self.modes)

    def geometry(self,x):
        x=np.asarray(x)
        z={0:.01/self.scale*(x[0]+1j*x[1]),1:x[2]}
        for i,mode in enumerate(self.modes):
            a,b=x[3+2*i:5+2*i]*.005/self.scale
            z[1+mode]=z.get(1+mode,0)+(a-1j*b)/2
            z[1-mode]=z.get(1-mode,0)+(a+1j*b)/2
        return LaurentGeometry(z,self.anchor,self.scale)

    def directions(self):
        # Geometry is affine; these are exact and reusable at every iterate.
        zero=self.geometry(np.zeros(self.size)).coefficients
        result=[]
        for row in np.eye(self.size):
            z=self.geometry(row).coefficients
            result.append({j:z.get(j,0)-zero.get(j,0) for j in z if z.get(j,0)!=zero.get(j,0)})
        return result

    def bounds(self):
        limits={2:.004,3:.003,5:.009,7:.003}
        upper=[6.,6.,1.3]
        lower=[-6.,-6.,.675]
        for mode in self.modes:
            limit=limits.get(mode,.003)/.005
            upper.extend([limit,limit]);lower.extend([-limit,-limit])
        return np.array(lower),np.array(upper)

    def physical_coefficients(self,x):
        g=self.geometry(x)
        coeff={j:v*g.scale for j,v in g.coefficients.items()}
        coeff[0]=coeff.get(0,0)+g.center
        return coeff

    def parameterization(self,x):
        from ordered_boundary import fourier_curve
        coeff=self.physical_coefficients(x)
        degree=max(abs(j) for j in coeff)
        cosine=np.zeros((degree+1,2));sine=np.zeros_like(cosine)
        cosine[0]=[coeff[0].real,coeff[0].imag]
        for j in range(1,degree+1):
            c=coeff.get(j,0)+coeff.get(-j,0)
            s=1j*(coeff.get(j,0)-coeff.get(-j,0))
            cosine[j]=[c.real,c.imag];sine[j]=[s.real,s.imag]
        return fourier_curve(cosine,sine,component_id='inverse-shape')

    def direction_jets(self,theta,direction):
        coefficients={j:v*self.scale for j,v in direction.items()}
        result=[]
        for order in range(4):
            value=sum(v*(1j*j)**order*np.exp(1j*j*theta) for j,v in coefficients.items())
            result.append(np.column_stack((value.real,value.imag)))
        return result


class NodalShapeForward:
    def __init__(self,chart,x,acq,frequencies,nodes=64):
        from ordered_boundary import OrderedBoundary2D
        from gpr_bem_kress import Material
        from gpr_bem_kress.coupled_shape_derivative import build_coupled_base
        from gpr_bem_kress.execution import execution
        self.chart=chart
        curve=chart.parameterization(x).discretize(nodes,require_even=True)
        self.curve=curve
        boundary=OrderedBoundary2D((curve,))
        self.states=[]
        with execution(kernels='real_bessel'):
            for frequency in frequencies:
                self.states.append(build_coupled_base(boundary,np.array(acq['source_points']),
                    np.array(acq['receiver_points']),2*np.pi*frequency,acq['source_strength'],
                    exterior=Material(**acq['exterior']),interior=Material(**acq['interior']),
                    eps0=acq['eps0'],mu0=acq['mu0']))
        self.outputs=[s.Y for s in self.states]

    def jacobian(self,directions):
        from gpr_bem_kress.shape_derivative import KressDirection
        from gpr_bem_kress.coupled_shape_derivative import directional_operators,tangent_response
        from gpr_bem_kress.execution import execution
        jets=[KressDirection(*self.chart.direction_jets(self.curve.parameters,d)) for d in directions]
        result=[]
        with execution(kernels='real_bessel'):
            for base in self.states:
                result.append(np.stack([tangent_response(base,directional_operators(base,(direction,)))
                                        for direction in jets],axis=-1))
        return result

    def hadamard_jacobian(self,directions):
        """Nodal control for the same continuous reciprocity shape identity."""
        from gpr_bem_kress.multicomponent import multicomponent_incident_trace_on_boundary
        from gpr_bem_kress.execution import execution
        velocities=[self.chart.direction_jets(self.curve.parameters,d)[0] for d in directions]
        weights=[np.sum(v*self.curve.normals,axis=1)*self.curve.arc_length_weights for v in velocities]
        result=[]
        with execution(kernels='real_bessel'):
            for base in self.states:
                d,n=multicomponent_incident_trace_on_boundary(base.system.geometry,base.receivers,
                                                              base.system.k_exterior,1.)
                ur=base.factors.solve(np.concatenate((d,n),axis=1).T)[:self.curve.num_nodes]
                us=base.U[:self.curve.num_nodes]
                contrast=base.system.k_interior**2-base.system.k_exterior**2
                result.append(np.stack([contrast*(ur.T@(weight[:,None]*us)) for weight in weights],axis=-1))
        return result


def wave_numbers(acq,frequencies):
    for region in ('exterior','interior'):
        material=acq[region]
        if material.get('mur',1)!=1 or material.get('sigma',0)!=0:
            raise ValueError('This inverse prototype requires lossless materials with mur=1.')
    factor=2*np.pi*np.asarray(frequencies)*np.sqrt(acq['eps0']*acq['mu0'])
    return factor*np.sqrt(acq['exterior']['epsr']),factor*np.sqrt(acq['interior']['epsr'])


class ShapeEvaluator:
    def __init__(self,chart,acq,frequencies,*,backend='native',cutoff=32,bandwidth=64,
                 terms=24,angular_order=24,nodes=64,paired=True,jacobian_kind='operator'):
        self.chart,self.acq,self.frequencies=chart,acq,tuple(frequencies)
        self.backend,self.nodes,self.paired=backend,nodes,paired
        if jacobian_kind not in ('operator','hadamard'):
            raise ValueError(jacobian_kind)
        if jacobian_kind=='hadamard' and (acq['exterior'].get('mur',1)!=acq['interior'].get('mur',1)):
            raise ValueError('This Hadamard identity requires equal permeability.')
        self.jacobian_kind=jacobian_kind
        self.options=dict(cutoff=cutoff,bandwidth=bandwidth,terms=terms)
        ko,self.ki=wave_numbers(acq,frequencies)
        tick=perf_counter()
        self.acquisitions=([FixedAcquisition(chart.anchor,chart.scale,k,acq['source_points'],
            acq['receiver_points'],acq['source_strength'],angular_order) for k in ko]
            if backend=='native' else [])
        self.work=dict(acquisition_setup_seconds=perf_counter()-tick,forward_seconds=0.,
                       jacobian_seconds=0.,forward_evaluations=0,jacobian_evaluations=0)
        self.x=self.base=self.j=None
        self.directions=chart.directions()

    def select(self,values):
        if self.paired:
            return np.diagonal(values,axis1=0,axis2=1).T if values.ndim==3 else np.diag(values)
        return values.reshape((-1,)+values.shape[2:])

    def forward(self,x):
        x=np.asarray(x)
        if self.x is None or not np.array_equal(x,self.x):
            tick=perf_counter()
            if self.backend=='native':
                base=NativeShapeForward(self.chart.geometry(x),self.acquisitions,self.ki,**self.options)
            elif self.backend=='nodal':
                base=NodalShapeForward(self.chart,x,self.acq,self.frequencies,self.nodes)
            else:
                raise ValueError(self.backend)
            self.base,self.x,self.j=base,x.copy(),None
            self.work['forward_seconds']+=perf_counter()-tick
            self.work['forward_evaluations']+=1
        return np.stack([self.select(y) for y in self.base.outputs],axis=0)

    def jacobian(self,x):
        self.forward(x)
        if self.j is None:
            tick=perf_counter()
            method=self.base.jacobian if self.jacobian_kind=='operator' else self.base.hadamard_jacobian
            self.j=np.stack([self.select(y) for y in method(self.directions)],axis=0)
            self.work['jacobian_seconds']+=perf_counter()-tick
            self.work['jacobian_evaluations']+=1
        return self.j


def real_stack(value):
    return np.concatenate((value.real.reshape(-1,*value.shape[2:]),
                           value.imag.reshape(-1,*value.shape[2:])),axis=0)


def invert(chart,acq,frequencies,observed,initial,*,backend='native',regularization=0.,
           continuation=True,max_nfev=60,verbose=False,**options):
    """Full least-squares recovery, including trial forwards and analytic Jacobians."""
    started=perf_counter()
    stages=[(0,),tuple(range(len(frequencies)))] if continuation and len(frequencies)>1 else [tuple(range(len(frequencies)))]
    x=np.array(initial,copy=True,dtype=float)
    records=[]
    history=[]
    penalty=np.zeros(chart.size)
    for index,mode in enumerate(chart.modes):
        penalty[3+2*index:5+2*index]=regularization*(mode/5)**2
    for stage_index,indices in enumerate(stages):
        evaluator=ShapeEvaluator(chart,acq,[frequencies[i] for i in indices],backend=backend,**options)
        target=observed[list(indices)]
        scales=np.linalg.norm(target,axis=1)*np.sqrt(len(indices))
        def residual(v):
            prediction=evaluator.forward(v)
            r=real_stack((prediction-target)/scales[:,None])
            return np.r_[r,penalty*v]
        def jacobian(v):
            values=evaluator.jacobian(v)/scales[:,None,None]
            r=residual(v)
            record=dict(stage=stage_index,evaluation=evaluator.work['forward_evaluations'],
                        residual_norm=float(np.linalg.norm(r)),parameters=v.tolist(),
                        elapsed_seconds=perf_counter()-started)
            history.append(record)
            if verbose:
                print(f'{backend} stage={stage_index} eval={record["evaluation"]} '
                      f'residual={record["residual_norm"]:.4e} elapsed={record["elapsed_seconds"]:.2f}s',flush=True)
            return np.vstack((real_stack(values),np.diag(penalty)))
        stage_started=perf_counter()
        result=least_squares(residual,x,jac=jacobian,bounds=chart.bounds(),method='trf',
                             ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=max_nfev,x_scale='jac')
        x=result.x
        records.append(dict(stage=stage_index,frequencies_hz=[frequencies[i] for i in indices],
                            seconds=perf_counter()-stage_started,work=evaluator.work,
                            nfev=result.nfev,njev=result.njev,status=result.status,
                            message=result.message,success=bool(result.success),
                            residual_norm=float(np.linalg.norm(result.fun))))
    return dict(parameters=x.tolist(),seconds=perf_counter()-started,stages=records,history=history,
                backend=backend,settings=dict(regularization=regularization,continuation=continuation,**options))


def rank_new_shape_modes(chart,x,acq,frequencies,observed,candidates=(4,6,7,8),
                         *,noise_fraction=.01,backend='native',**options):
    """Score missing shape modes using only training residuals and derivative columns.

    Project away the current model's tangent space before ranking each cosine/
    sine pair. The noise threshold is an exploratory heuristic, not a formal
    model-selection confidence interval. No truth geometry enters this routine.
    """
    tick=perf_counter()
    candidates=tuple(m for m in candidates if m not in chart.modes)
    expanded=ShapeChart(chart.modes+candidates,chart.anchor,chart.scale)
    parameters=np.r_[x,np.zeros(2*len(candidates))]
    evaluator=ShapeEvaluator(expanded,acq,frequencies,backend=backend,jacobian_kind='hadamard',**options)
    prediction=evaluator.forward(parameters)
    scales=np.linalg.norm(observed,axis=1)*np.sqrt(len(frequencies))
    residual=real_stack((prediction-observed)/scales[:,None])
    jacobian=real_stack(evaluator.jacobian(parameters)/scales[:,None,None])
    u,s,_=np.linalg.svd(jacobian[:,:chart.size],full_matrices=False)
    active=u[:,s>1e-10*s[0]]
    residual=residual-active@(active.T@residual)
    rows=[]
    for index,mode in enumerate(candidates):
        k=jacobian[:,chart.size+2*index:chart.size+2*index+2]
        k-=active@(active.T@k)
        step=np.linalg.lstsq(k,-residual,rcond=1e-10)[0]
        decrease=.5*(np.dot(residual,residual)-np.linalg.norm(residual+k@step)**2)
        rows.append(dict(mode=mode,predicted_loss_decrease=float(decrease),
                         proposed_cos_sin_step=step.tolist(),singular_values=np.linalg.svd(k,compute_uv=False).tolist()))
    rows.sort(key=lambda r:r['predicted_loss_decrease'],reverse=True)
    threshold=8*noise_fraction**2/len(residual)
    selected=rows[0]['mode'] if rows and rows[0]['predicted_loss_decrease']>threshold else None
    return dict(ranking=rows,selected_mode=selected,noise_threshold=threshold,
                seconds=perf_counter()-tick,work=evaluator.work,
                selection_uses_truth=False)
