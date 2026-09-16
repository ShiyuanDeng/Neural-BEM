"""Laurent shape derivatives of compiled scattering matrices and coupled data.

Each shape family uses a FIXED cylindrical normalization. This makes shape
changes act only on T: no artificial shape derivatives of U, a, or C occur.
The reciprocal derivative is continuous shape calculus evaluated with the
compiled traces; refinement and recompilation tests quantify truncation error.
"""
from dataclasses import replace
from time import perf_counter
import numpy as np
from scipy.linalg import lu_factor,lu_solve
from scipy.signal import fftconvolve
from .coefficient_operator import LaurentGeometry,CoefficientGeometry,add,conjugate,multiply,times
from .coefficient_derivative import ShapeOperator,prepare_direction
from .coefficient_fields import RegularWaves,convolve_sparse
from .scattering_library import compile_template,ScatteringScene,parameterization
from .inverse import wave_numbers


def compile_shape_jet(geometry,directions,ko,ki,normalization_radius,*,backend='native',**options):
    """Compile T and all dT using the same local regular-wave trace solutions."""
    tick=perf_counter()
    template=compile_template(geometry,ko,ki,backend=backend,normalization_radius=normalization_radius,
                              retain_trace=True,**options)
    u=template.local_trace
    # Outgoing mode m tests against incident regular wave -m, with factor
    # (i/4)(-1)^m. Both sides already use the same fixed s_m normalization.
    if backend=='native':
        cutoff=template.diagnostics['trace_cutoff']
        products=fftconvolve(u[:,::-1,None],u[:,None,:],axes=0)
        normal={(j,):j*v for j,v in geometry.coefficients.items()}
        columns=[]
        for dz in directions:
            delta={(j,):v for j,v in dz.items()}
            weight=times(add(multiply(delta,conjugate(normal)),multiply(conjugate(delta),normal)),
                         .5*geometry.scale**2)
            integral=sum(value*products[2*cutoff-j] for (j,),value in weight.items() if abs(j)<=2*cutoff)
            columns.append(2*np.pi*integral)
    else:
        curve=parameterization(geometry).discretize(options.get('nodes',128),require_even=True)
        theta=np.arange(len(u))*2*np.pi/len(u)
        columns=[]
        for dz in directions:
            delta=geometry.scale*sum(v*np.exp(1j*j*theta) for j,v in dz.items())
            weight=(delta.real*curve.normals[:,0]+delta.imag*curve.normals[:,1])*curve.arc_length_weights
            columns.append(u[:,::-1].T@(weight[:,None]*u))
    jets=.25j*(-1.)**template.modes[None,:,None]*(ki**2-ko**2)*np.stack(columns)
    template.local_trace=None
    return template,jets,perf_counter()-tick


def operator_shape_jet(geometry,directions,ko,ki,normalization_radius,*,order=12,cutoff=24,bandwidth=48,terms=28):
    """Independent d(P A^-1 B) check; deliberately not the fast inverse path."""
    template=compile_template(geometry,ko,ki,normalization_radius=normalization_radius,
                              order=order,cutoff=cutoff,bandwidth=bandwidth,terms=terms)
    prepared=CoefficientGeometry(geometry,bandwidth)
    op=ShapeOperator(prepared,ko,ki,cutoff,terms)
    regular=RegularWaves(geometry,ko,bandwidth,order+2,terms)
    modes=np.arange(-cutoff,cutoff+1)
    def maps(values,flux):
        b=np.concatenate((values[bandwidth+modes],flux[bandwidth+modes]))/template.normalization[None,:]
        p=2*np.pi*np.concatenate((flux[bandwidth-modes].T,-values[bandwidth-modes].T),axis=1)
        p=.25j*(-1.)**template.modes[:,None]*p[::-1]/template.normalization[:,None]
        return b,p
    b,p=maps(regular.values[:,2:-2],regular.flux[:,2:-2])
    factors=lu_factor(op.a);u=lu_solve(factors,b)
    transfer=lu_solve(factors,p.T,trans=1).T
    z=geometry.coefficients;zbar={-j:complex(v).conjugate() for j,v in z.items()}
    h=geometry.scale*ko;f=regular.values;columns=[]
    for dz in directions:
        dzbar={-j:complex(v).conjugate() for j,v in dz.items()}
        df=h/2*(convolve_sparse(f[:,:-2],dz)-convolve_sparse(f[:,2:],dzbar))
        dq=h/2*(convolve_sparse(f[:,1:-3],{j:j*v for j,v in dz.items()})
                 +convolve_sparse(f[:,3:-1],{j:j*v for j,v in dzbar.items()})
                 +convolve_sparse(df[:,:-2],{j:j*v for j,v in z.items()})
                 +convolve_sparse(df[:,2:],{j:j*v for j,v in zbar.items()}))
        db,dp=maps(df[:,1:-1],dq)
        da=op.derivative(prepare_direction(prepared,dz))
        columns.append(dp@u+transfer@(db-da@u))
    return np.stack(columns)


class ShapePoseChart:
    """Per-object x/y/rotation and real coordinates in a local Laurent family."""
    def __init__(self,geometries,directions,anchors,shape_bound=1.5):
        self.geometries=tuple(geometries);self.directions=tuple(directions)
        self.anchors=np.asarray(anchors,complex);self.shape_bound=shape_bound
        stops=np.r_[0,np.cumsum([3+len(row) for row in directions])]
        self.slices=tuple(slice(a,b) for a,b in zip(stops[:-1],stops[1:]));self.size=int(stops[-1])
        self.radii=[g.scale*(sum(abs(v) for v in g.coefficients.values())
                       +shape_bound*sum(sum(abs(v) for v in d.values()) for d in row))
                    for g,row in zip(geometries,directions)]

    def poses(self,x):
        values=np.array([np.asarray(x)[sl][:3] for sl in self.slices])
        return self.anchors+.01*(values[:,0]+1j*values[:,1]),values[:,2]

    def local(self,x):
        result=[]
        for g,row,sl in zip(self.geometries,self.directions,self.slices):
            z=dict(g.coefficients)
            for value,d in zip(x[sl][3:],row):
                for j,v in d.items(): z[j]=z.get(j,0)+value*v
            result.append(LaurentGeometry(z,0j,g.scale))
        return result

    def moved(self,x):
        centers,angles=self.poses(x)
        return [LaurentGeometry({j:v*np.exp(1j*a) for j,v in g.coefficients.items()},c,g.scale)
                for g,c,a in zip(self.local(x),centers,angles)]

    def bounds(self):
        lo=[];hi=[]
        for row in self.directions:
            lo.extend([-1.5,-1.5,-.8]+[-self.shape_bound]*len(row))
            hi.extend([1.5,1.5,.8]+[self.shape_bound]*len(row))
        return np.array(lo),np.array(hi)


class DeformableEvaluator:
    def __init__(self,chart,acq,frequencies,*,backend='native',order=12,cutoff=24,bandwidth=48,
                 terms=28,nodes=64,paired=True):
        self.chart,self.acq,self.frequencies=chart,acq,tuple(frequencies)
        self.backend,self.paired=backend,paired
        self.options=dict(order=order,cutoff=cutoff,bandwidth=bandwidth,terms=terms,nodes=nodes)
        self.ko,self.ki=wave_numbers(acq,frequencies)
        self.cache={};self.x=None;self.states=[];self.jets=[]
        self.work=dict(local_compilations=0,compile_seconds=0.,forward_seconds=0.,jacobian_seconds=0.,
                       forward_evaluations=0,jacobian_evaluations=0)

    def compile_at(self,x):
        templates=[];jets=[]
        local=self.chart.local(x)
        for ko,ki in zip(self.ko,self.ki):
            row=[];jr=[]
            for i,(g,d,radius) in enumerate(zip(local,self.chart.directions,self.chart.radii)):
                # Keep just the last local shape per object/frequency. Pose-only
                # changes need no compilation; memory does not grow with trials.
                key=(i,ko,ki)
                coefficients=tuple(sorted(g.coefficients.items()))
                if key not in self.cache or self.cache[key][0]!=coefficients:
                    t,j,seconds=compile_shape_jet(g,d,ko,ki,radius,backend=self.backend,**self.options)
                    self.cache[key]=(coefficients,t,j)
                    self.work['local_compilations']+=1;self.work['compile_seconds']+=seconds
                _,t,j=self.cache[key];row.append(t);jr.append(j)
            templates.append(row);jets.append(jr)
        return templates,jets

    def forward(self,x):
        x=np.asarray(x)
        if self.x is None or not np.array_equal(self.x,x):
            tick=perf_counter();templates,self.jets=self.compile_at(x)
            centers,angles=self.chart.poses(x);a=self.acq
            self.states=[ScatteringScene(row,centers,angles,a['source_points'],a['receiver_points'],a['source_strength'],self.paired)
                         for row in templates]
            self.values=np.stack([s.output for s in self.states]);self.x=x.copy();self.jac=None
            self.work['forward_seconds']+=perf_counter()-tick;self.work['forward_evaluations']+=1
        return self.values

    def jacobian(self,x):
        self.forward(x)
        if self.jac is not None: return self.jac
        tick=perf_counter();_,angles=self.chart.poses(x);rows=[]
        for scene,jets in zip(self.states,self.jets):
            pose=scene.jacobian();columns=[]
            transfer=lu_solve(scene.factors,scene.receiver.T,trans=1).T
            for i,(t,sl,j,angle) in enumerate(zip(scene.templates,scene.slices,jets,angles)):
                columns.extend([pose[:,3*i+k] for k in range(3)])
                phase=np.exp(1j*(t.modes[None,:]-t.modes[:,None])*angle)
                for derivative in j:
                    columns.append(scene.select(transfer[:,sl]@(derivative*phase)@scene.local_incident[sl]))
            rows.append(np.stack(columns,axis=-1))
        self.jac=np.stack(rows)
        self.work['jacobian_seconds']+=perf_counter()-tick;self.work['jacobian_evaluations']+=1
        return self.jac


class LinearizedEvaluator(DeformableEvaluator):
    """Shape-linear T, with exact nonlinear pose and multiple scattering.

    This is a local surrogate, never an exact shape-forward claim. The caller
    must validate it with fresh compiled templates before accepting a recovery.
    """
    def __init__(self,exact,anchor):
        self.__dict__.update(exact.__dict__)
        self.anchor=np.array(anchor,copy=True)
        self.base,self.base_jets=exact.compile_at(anchor)
        self.x=None;self.jac=None
        self.work=dict(local_compilations=0,compile_seconds=0.,forward_seconds=0.,jacobian_seconds=0.,
                       forward_evaluations=0,jacobian_evaluations=0)

    def compile_at(self,x):
        rows=[]
        for row,jets in zip(self.base,self.base_jets):
            rows.append([replace(t,matrix=t.matrix+np.einsum('j,jmn->mn',(x-self.anchor)[sl][3:],j),
                                 radius_bound=radius)
                         for t,j,sl,radius in zip(row,jets,self.chart.slices,self.chart.radii)])
        return rows,self.base_jets
