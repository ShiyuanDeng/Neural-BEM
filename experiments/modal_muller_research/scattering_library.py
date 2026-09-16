"""Compile Laurent objects into scattering matrices; pose updates need no BIE.

The local Muller solve is eliminated into a regular-to-outgoing cylindrical
wave map. Rigid rotations are diagonal phase conjugations. Multiple scattering
and analytic pose derivatives then involve only small translation matrices.
The nodal compiler is a control for the same elimination mechanism.
"""
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from scipy.linalg import lu_factor,lu_solve,block_diag
from scipy.special import hankel1,jv,gammaln
from .coefficient_operator import LaurentGeometry,CoefficientGeometry
from .coefficient_fields import RegularWaves


def parameterization(geometry,component_id='template'):
    from ordered_boundary import fourier_curve
    coeff={j:v*geometry.scale for j,v in geometry.coefficients.items()}
    coeff[0]=coeff.get(0,0)+geometry.center
    degree=max(abs(j) for j in coeff)
    cosine=np.zeros((degree+1,2));sine=np.zeros_like(cosine)
    cosine[0]=[coeff[0].real,coeff[0].imag]
    for j in range(1,degree+1):
        c=coeff.get(j,0)+coeff.get(-j,0)
        s=1j*(coeff.get(j,0)-coeff.get(-j,0))
        cosine[j]=[c.real,c.imag];sine[j]=[s.real,s.imag]
    return fourier_curve(cosine,sine,component_id=component_id)


def circular_functions(orders,delta,wave,kind='hankel',sign=1):
    """Values and Cartesian derivatives of H_n(kr) exp(sign*i*n*theta)."""
    orders=np.asarray(orders)
    delta=np.asarray(delta)
    function=hankel1 if kind=='hankel' else jv
    # Translation matrices repeat the same order difference along diagonals.
    # Evaluate every required order once per distinct displacement entry, then
    # gather the matrix and both ladder derivatives from the same table.
    first=int(np.min(orders))-1;last=int(np.max(orders))+1
    ladder=np.arange(first,last+1)[:,None]
    flat=delta.reshape(-1)
    table=function(ladder,wave*np.abs(flat)[None,:])*np.exp(sign*1j*ladder*np.angle(flat)[None,:])
    indices=np.arange(delta.size).reshape(delta.shape)
    f=table[orders-first,indices]
    lower=table[orders-first-1,indices];upper=table[orders-first+1,indices]
    return f,wave/2*(lower-upper),sign*1j*wave/2*(lower+upper)


@dataclass
class ScatteringTemplate:
    geometry: LaurentGeometry
    wave: float
    interior_wave: float
    modes: np.ndarray
    normalization: np.ndarray
    matrix: np.ndarray
    radius_bound: float
    diagnostics: dict
    local_trace: object = None

    def rotated(self,angle):
        phase=np.exp(1j*(self.modes[None,:]-self.modes[:,None])*angle)
        matrix=self.matrix*phase
        derivative=1j*(self.modes[None,:]-self.modes[:,None])*matrix
        return matrix,derivative


def compile_template(geometry,ko,ki,*,order=10,cutoff=24,bandwidth=48,terms=28,backend='native',nodes=128,
                     normalization_radius=None,retain_trace=False):
    tick=perf_counter()
    if geometry.center!=0 or abs(geometry.coefficients.get(0,0))>1e-14:
        raise ValueError('Compile shapes about the local origin; store translation in the pose.')
    radius=geometry.scale*sum(abs(v) for v in geometry.coefficients.values())
    modes=np.arange(-order,order+1)
    # Regular waves J_n/s_n and outgoing waves s_n H_n avoid factorial scales
    # in high-order translation blocks. No geometry samples are required.
    normalization_radius=radius if normalization_radius is None else normalization_radius
    norm=np.exp(np.abs(modes)*np.log(ko*normalization_radius/2)-gammaln(np.abs(modes)+1))
    if backend=='native':
        if order>cutoff:
            raise ValueError('Scattering order must fit the boundary trace cutoff.')
        prepared=CoefficientGeometry(geometry,bandwidth)
        matrix,_=prepared.assemble(ko,ki,cutoff,terms)
        regular=RegularWaves(geometry,ko,bandwidth,order,terms)
        trace_modes=np.arange(-cutoff,cutoff+1)
        rhs=np.concatenate((regular.values[bandwidth+trace_modes],regular.flux[bandwidth+trace_modes]))
        evaluate=2*np.pi*np.concatenate((regular.flux[bandwidth-trace_modes].T,
                                        -regular.values[bandwidth-trace_modes].T),axis=1)
        boundary_nodes=0
    elif backend=='nodal':
        from gpr_bem_kress.system import build_muller_system
        from gpr_bem_kress.execution import execution
        curve=parameterization(geometry).discretize(nodes,require_even=True)
        with execution(kernels='real_bessel'):
            matrix=build_muller_system(curve,ko,ki).system_matrix
        z=curve.points[:,0]+1j*curve.points[:,1]
        values,dx,dy=circular_functions(modes[None,:],z[:,None],ko,'bessel')
        normal=dx*curve.normals[:,0,None]+dy*curve.normals[:,1,None]
        rhs=np.concatenate((values,normal))
        evaluate=np.concatenate(((normal*curve.arc_length_weights[:,None]).T,
                                  -(values*curve.arc_length_weights[:,None]).T),axis=1)
        boundary_nodes=nodes
    else:
        raise ValueError(backend)
    outgoing=.25j*(-1.)**modes[:,None]*evaluate[::-1]
    local_state=lu_solve(lu_factor(matrix),rhs/norm[None,:])
    scattering=(outgoing/norm[:,None])@local_state
    return ScatteringTemplate(geometry,ko,ki,modes,norm,scattering,radius,
        dict(compile_seconds=perf_counter()-tick,backend=backend,boundary_nodes=boundary_nodes,
             boundary_unknowns=len(matrix),scattering_unknowns=len(modes),order=order,
             trace_cutoff=cutoff,bandwidth=bandwidth,terms=terms),
        local_state[:len(matrix)//2] if retain_trace else None)


class ScatteringScene:
    """The online solve contains outgoing coefficients only, with no trace solve."""
    def __init__(self,templates,centers,angles,sources,receivers,strengths=1e-6,paired=True):
        tick=perf_counter()
        self.templates=templates;self.centers=np.asarray(centers,complex)
        self.angles=np.asarray(angles);self.paired=paired
        self.slices=[];stop=0
        for template in templates:
            self.slices.append(slice(stop,stop+len(template.modes)));stop+=len(template.modes)
        self.rotations=[t.rotated(a) for t,a in zip(templates,angles)]
        self.t=block_diag(*[pair[0] for pair in self.rotations])
        self.translation=np.zeros((stop,stop),complex)
        self.translation_jets={}
        for i,(target,rs) in enumerate(zip(templates,self.slices)):
            for j,(source,cs) in enumerate(zip(templates,self.slices)):
                if i==j: continue
                delta=self.centers[i]-self.centers[j]
                if abs(delta)<=target.radius_bound+source.radius_bound:
                    raise ValueError('Scattering translations require disjoint bounding circles.')
                if target.wave!=source.wave:
                    raise ValueError('Every component must have the same exterior wave number.')
                orders=source.modes[None,:]-target.modes[:,None]
                values=circular_functions(orders,delta,target.wave)
                scale=target.normalization[:,None]*source.normalization[None,:]
                values=tuple(v*scale for v in values)
                self.translation[rs,cs]=values[0]
                self.translation_jets[i,j]=values[1:]
        sources=np.asarray(sources);receivers=np.asarray(receivers)
        sz=sources[:,0]+1j*sources[:,1];rz=receivers[:,0]+1j*receivers[:,1]
        if paired and len(sources)!=len(receivers):
            raise ValueError('Paired data require equal source and receiver counts.')
        self.incident_jets=[];self.receiver_jets=[];incident=[];receiver=[]
        for template,center in zip(templates,self.centers):
            if min(np.min(abs(sz-center)),np.min(abs(rz-center)))<=template.radius_bound:
                raise ValueError('Acquisition points must lie outside the template bounding circle.')
            source_values=circular_functions(template.modes[:,None],sz[None,:]-center,template.wave,sign=-1)
            source_values=tuple(.25j*template.normalization[:,None]*a*np.asarray(strengths) for a in source_values)
            receiver_values=circular_functions(template.modes[None,:],rz[:,None]-center,template.wave)
            receiver_values=tuple(a*template.normalization[None,:] for a in receiver_values)
            incident.append(source_values[0]);receiver.append(receiver_values[0])
            # Centers move oppositely to the source/receiver displacement vectors.
            self.incident_jets.append(tuple(-a for a in source_values[1:]))
            self.receiver_jets.append(tuple(-a for a in receiver_values[1:]))
        self.incident=np.concatenate(incident);self.receiver=np.concatenate(receiver,axis=1)
        self.matrix=np.eye(stop)-self.t@self.translation
        self.factors=lu_factor(self.matrix)
        self.outgoing=lu_solve(self.factors,self.t@self.incident)
        self.local_incident=self.incident+self.translation@self.outgoing
        self.full_output=self.receiver@self.outgoing
        self.output=self.select(self.full_output)
        self.seconds=perf_counter()-tick
        self.boundary_nodes=0;self.boundary_unknowns=0

    def select(self,values):
        return np.diag(values) if self.paired else values.reshape(-1)

    def jacobian(self,position_scale=.01):
        tick=perf_counter()
        transfer=lu_solve(self.factors,self.receiver.T,trans=1).T
        columns=[]
        for component,sl in enumerate(self.slices):
            for axis in (0,1):
                da=np.zeros_like(self.incident);dc=np.zeros_like(self.receiver)
                du=np.zeros_like(self.translation)
                da[sl]=self.incident_jets[component][axis]*position_scale
                dc[:,sl]=self.receiver_jets[component][axis]*position_scale
                for (i,j),jets in self.translation_jets.items():
                    if component==i or component==j:
                        du[self.slices[i],self.slices[j]]=(1 if component==i else -1)*position_scale*jets[axis]
                columns.append(self.select(dc@self.outgoing+transfer@(self.t@(da+du@self.outgoing))))
            forcing=np.zeros_like(self.incident)
            forcing[sl]=self.rotations[component][1]@self.local_incident[sl]
            columns.append(self.select(transfer@forcing))
        self.jacobian_seconds=perf_counter()-tick
        return np.stack(columns,axis=-1)


class PoseChart:
    def __init__(self,geometries,anchors):
        self.geometries=tuple(geometries);self.anchors=np.asarray(anchors,complex)
        self.size=3*len(geometries)

    def poses(self,x):
        values=np.asarray(x).reshape(-1,3)
        return self.anchors+.01*(values[:,0]+1j*values[:,1]),values[:,2]

    def moved(self,x):
        centers,angles=self.poses(x)
        return [LaurentGeometry({j:v*np.exp(1j*a) for j,v in g.coefficients.items()},c,g.scale)
                for g,c,a in zip(self.geometries,centers,angles)]

    def bounds(self):
        return np.tile([-1.5,-1.5,-.8],len(self.geometries)),np.tile([1.5,1.5,.8],len(self.geometries))
