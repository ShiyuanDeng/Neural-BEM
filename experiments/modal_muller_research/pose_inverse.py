"""Matched rigid-pose inverses with compiled and rebuilt forward systems."""
from time import perf_counter
import numpy as np
from scipy.linalg import lu_solve
from scipy.optimize import least_squares
from scipy.signal import fftconvolve
from .inverse import wave_numbers,real_stack
from .coefficient_operator import add,conjugate,multiply,times
from .coefficient_fields import solve
from .scattering_library import compile_template,ScatteringScene,parameterization


class PoseEvaluator:
    def __init__(self,chart,acq,frequencies,*,backend='library_native',order=12,
                 cutoff=24,bandwidth=48,terms=28,nodes=64,paired=True,template_cache=None):
        self.chart,self.acq,self.frequencies=chart,acq,tuple(frequencies)
        self.backend,self.paired,self.nodes=backend,paired,nodes
        self.cutoff,self.bandwidth,self.terms=cutoff,bandwidth,terms
        self.ko,self.ki=wave_numbers(acq,frequencies)
        tick=perf_counter();self.templates=[]
        cache={} if template_cache is None else template_cache
        cache_before=len(cache)
        if backend.startswith('library_'):
            for ko,ki in zip(self.ko,self.ki):
                row=[]
                for g in chart.geometries:
                    key=(backend,order,cutoff,bandwidth,terms,nodes,g.scale,tuple(sorted(g.coefficients.items())),ko,ki)
                    if key not in cache:
                        cache[key]=compile_template(g,ko,ki,order=order,cutoff=cutoff,bandwidth=bandwidth,
                            terms=terms,nodes=nodes,backend=backend.removeprefix('library_'))
                    row.append(cache[key])
                self.templates.append(row)
        self.work=dict(compilation_seconds=perf_counter()-tick,compiled_templates=len(cache)-cache_before,
                       forward_seconds=0.,jacobian_seconds=0.,forward_evaluations=0,jacobian_evaluations=0)
        self.x=self.jac=None;self.states=[]

    def select(self,y):
        return np.diag(y) if self.paired else y.reshape(-1)

    def forward(self,x):
        x=np.asarray(x)
        if self.x is None or not np.array_equal(x,self.x):
            tick=perf_counter();self.states=[]
            acq=self.acq
            centers,angles=self.chart.poses(x)
            geometries=self.chart.moved(x)
            if self.backend.startswith('library_'):
                for row in self.templates:
                    self.states.append(ScatteringScene(row,centers,angles,acq['source_points'],acq['receiver_points'],
                                                       acq['source_strength'],self.paired))
                self.values=np.stack([s.output for s in self.states])
            elif self.backend=='native_rebuild':
                self.states=[solve(geometries,ko,ki,acq['source_points'],acq['receiver_points'],
                    acq['source_strength'],cutoff=self.cutoff,bandwidth=self.bandwidth,
                    angular_order=24,terms=self.terms) for ko,ki in zip(self.ko,self.ki)]
                self.values=np.stack([self.select(s['y']) for s in self.states])
            elif self.backend=='nodal_rebuild':
                from ordered_boundary import OrderedBoundary2D
                from gpr_bem_kress import Material
                from gpr_bem_kress.coupled_shape_derivative import build_coupled_base
                from gpr_bem_kress.execution import execution
                self.boundary=OrderedBoundary2D(tuple(parameterization(g,f'pose-{i}').discretize(self.nodes,require_even=True)
                    for i,g in enumerate(geometries)))
                with execution(kernels='real_bessel'):
                    self.states=[build_coupled_base(self.boundary,np.array(acq['source_points']),np.array(acq['receiver_points']),
                        2*np.pi*f,acq['source_strength'],exterior=Material(**acq['exterior']),interior=Material(**acq['interior']),
                        eps0=acq['eps0'],mu0=acq['mu0']) for f in self.frequencies]
                self.values=np.stack([self.select(s.Y) for s in self.states])
            else:
                raise ValueError(self.backend)
            self.x=x.copy();self.jac=None
            self.work['forward_seconds']+=perf_counter()-tick;self.work['forward_evaluations']+=1
        return self.values

    def jacobian(self,x):
        self.forward(x)
        if self.jac is not None: return self.jac
        tick=perf_counter()
        if self.backend.startswith('library_'):
            jac=[s.jacobian() for s in self.states]
        elif self.backend=='native_rebuild':
            m=self.cutoff;n=2*m+1;weights=[]
            for g in self.chart.moved(x):
                normal={(j,):j*v for j,v in g.coefficients.items()}
                directions=[{0:.01/g.scale},{0:.01j/g.scale},{j:1j*v for j,v in g.coefficients.items()}]
                row=[]
                for d in directions:
                    delta={(j,):v for j,v in d.items()}
                    row.append(times(add(multiply(delta,conjugate(normal)),multiply(conjugate(delta),normal)),.5*g.scale**2))
                weights.append(row)
            jac=[]
            for state,ko,ki in zip(self.states,self.ko,self.ki):
                br=np.concatenate([w.rhs(self.acq['receiver_points'],1.,m) for w in state['waves']])
                ur=lu_solve(state['factors'],br);columns=[]
                for i,row in enumerate(weights):
                    sl=slice(2*n*i,2*n*i+n)
                    products=fftconvolve(ur[sl,:,None],state['state'][sl,None,:],axes=0)
                    for weight in row:
                        column=sum(value*products[2*m-mode] for (mode,),value in weight.items() if abs(mode)<=2*m)
                        columns.append(self.select(2*np.pi*(ki**2-ko**2)*column))
                jac.append(np.stack(columns,axis=-1))
        else:
            from gpr_bem_kress.multicomponent import multicomponent_incident_trace_on_boundary
            from gpr_bem_kress.execution import execution
            centers,_=self.chart.poses(x);weights=[]
            for curve,center in zip(self.boundary.components,centers):
                dx=curve.points[:,0]-center.real;dy=curve.points[:,1]-center.imag
                weights.append([.01*curve.normals[:,0]*curve.arc_length_weights,
                    .01*curve.normals[:,1]*curve.arc_length_weights,
                    (-dy*curve.normals[:,0]+dx*curve.normals[:,1])*curve.arc_length_weights])
            jac=[]
            with execution(kernels='real_bessel'):
                for state in self.states:
                    d,n=multicomponent_incident_trace_on_boundary(self.boundary,state.receivers,state.system.k_exterior,1.)
                    ur=state.factors.solve(np.concatenate((d,n),axis=1).T)
                    contrast=state.system.k_interior**2-state.system.k_exterior**2;columns=[]
                    for sl,row in zip(self.boundary.component_slices,weights):
                        for weight in row:
                            columns.append(self.select(contrast*(ur[sl].T@(weight[:,None]*state.U[sl]))))
                    jac.append(np.stack(columns,axis=-1))
        self.jac=np.stack(jac)
        self.work['jacobian_seconds']+=perf_counter()-tick;self.work['jacobian_evaluations']+=1
        return self.jac


def invert_pose(chart,acq,frequencies,observed,initial,*,backend='library_native',evaluator=None,max_nfev=50,**options):
    tick=perf_counter()
    if evaluator is None:
        evaluator=PoseEvaluator(chart,acq,frequencies,backend=backend,**options)
    work_before=dict(evaluator.work);history=[]
    scales=np.linalg.norm(observed,axis=1)*np.sqrt(len(frequencies))
    def residual(x):
        return real_stack((evaluator.forward(x)-observed)/scales[:,None])
    def jacobian(x):
        j=evaluator.jacobian(x)
        history.append(dict(parameters=x.tolist(),elapsed_seconds=perf_counter()-tick,
                            residual_norm=float(np.linalg.norm(residual(x)))))
        return real_stack(j/scales[:,None,None])
    result=least_squares(residual,initial,jac=jacobian,bounds=chart.bounds(),x_scale='jac',
                         ftol=1e-11,xtol=1e-11,gtol=1e-11,max_nfev=max_nfev)
    return dict(parameters=result.x.tolist(),seconds=perf_counter()-tick,success=bool(result.success),
        message=result.message,nfev=result.nfev,njev=result.njev,history=history,backend=evaluator.backend,
        work=dict(evaluator.work),work_before=work_before,residual_norm=float(np.linalg.norm(result.fun)))
