"""SC-035 opt-in centred arclength projection, with its complete derivative.

T_z(a) = z + P_K[A(z+h(a)n)-A(z)]. Units follow BorgesUpdate. The derivative
uses finite differences of GEOMETRY ONLY; the data derivative is reciprocal.
"""
from dataclasses import dataclass
import time
import numpy as np
from scipy.interpolate import CubicSpline

from experiments.shape_continuation.geometry import FourierCurve, arclength_angles, grid_size, normal_basis
from experiments.shape_continuation.updates import BorgesUpdate, LocalSpace, UpdateRefused, _refusal, speed_ratio
from experiments.shape_continuation.validation import self_intersections


@dataclass(frozen=True)
class ProjectedSpace(LocalSpace):
    derivatives: np.ndarray
    base_projection: np.ndarray
    fine_base_projection: np.ndarray
    count: int
    preparation_seconds: float


def values(coefficients, count):
    K=len(coefficients)//2
    spectrum=np.zeros((count,)+coefficients.shape[1:],complex)
    spectrum[np.arange(-K,K+1)%count]=coefficients
    return np.fft.ifft(spectrum,axis=0)*count


def project(curve, coefficients, band, count, length_unit_m, *, validate=False):
    nodes=curve.nodes(count)
    z=curve.values(count)
    h=normal_basis(nodes,len(coefficients)//2)@coefficients/length_unit_m
    normal=nodes.normals@np.array([1,1j])
    moved=FourierCurve.from_samples(z+h*normal,count//2-1)
    n=moved.nodes(count)
    if validate:
        if n.signed_area<=0 or np.min(n.speeds)<1e-6*np.mean(n.speeds):
            raise UpdateRefused('irregular_parameterization','Invalid displaced curve.')
        if self_intersections(n.points):
            raise UpdateRefused('self_intersection','Displaced curve self-intersects.')
    angles,_=arclength_angles(n)
    inverse=CubicSpline(np.r_[angles,2*np.pi],np.r_[n.parameters,2*np.pi])
    zz=moved.values(count)
    interpolate=CubicSpline(np.r_[n.parameters,2*np.pi],np.r_[zz,zz[0]],bc_type='periodic')
    samples=interpolate(inverse(n.parameters))
    projected=FourierCurve.from_samples(samples,band)
    error=float(np.max(np.abs(projected.values(count)-samples)))
    return projected.coefficients,error


class ProjectedUpdate(BorgesUpdate):
    name='centred_state_band_projection'

    def __init__(self,length_unit_m,*,projection_tolerance=1e-5,derivative_step_m=1e-7):
        super().__init__(length_unit_m,projection_tolerance=projection_tolerance)
        self.derivative_step_m=float(derivative_step_m)
        if not np.isfinite(self.derivative_step_m) or self.derivative_step_m<=0:
            raise ValueError('Positive finite derivative step required.')
        self.counts=dict(preparations=0,geometry_projections=0,trial_constructions=0,
                         refused_trials=0,preparation_seconds=0.,trial_seconds=0.)

    def settings(self):
        return dict(super().settings(),derivative_step_m=self.derivative_step_m,
                    construction='z + P_K[A(z+h n)-A(z)]',
                    projection_tolerance_meaning='grid refinement, not intentional smoothing')

    def _project(self,*args,**kwargs):
        self.counts['geometry_projections']+=1
        return project(*args,**kwargs)

    def prepare(self,curve,update_modes,curve_modes):
        started=time.perf_counter()
        plain=super().prepare(curve,update_modes,curve_modes)
        count=grid_size(max(curve_modes,update_modes))
        dim=len(plain.orders)
        zeros=np.zeros(dim)
        base=self._project(curve,zeros,curve_modes,count,self.length_unit_m)[0]
        fine=self._project(curve,zeros,curve_modes,2*count,self.length_unit_m)[0]
        derivatives=[]
        for j in range(dim):
            step=np.eye(dim)[j]*self.derivative_step_m
            plus=self._project(curve,step,curve_modes,count,self.length_unit_m)[0]
            minus=self._project(curve,-step,curve_modes,count,self.length_unit_m)[0]
            derivatives.append((plus-minus)/(2*self.derivative_step_m))
        elapsed=time.perf_counter()-started
        self.counts['preparations']+=1
        self.counts['preparation_seconds']+=elapsed
        return ProjectedSpace(**plain.__dict__,derivatives=np.stack(derivatives,axis=1),
            base_projection=base,fine_base_projection=fine,count=count,preparation_seconds=elapsed)

    def velocities(self,space,nodes):
        vectors=values(space.derivatives,nodes.num_nodes)
        n=nodes.normals@np.array([1,1j])
        return (vectors*np.conj(n[:,None])).real

    def measure(self,space,coefficients):
        a=self._checked(space,coefficients)
        n=space.curve.nodes(space.count)
        # Derivatives are in package units per metre. Convert the resulting
        # normal displacement back to metres for the backend's physical units.
        h=self.velocities(space,n)@a*self.length_unit_m
        w=n.arc_length_weights/n.perimeter
        return dict(maximum_normal_m=float(np.max(np.abs(h))),rms_normal_m=float(np.sqrt(w@h**2)))

    def metric(self,space,kind,smoothing_m=None):
        if kind!='mass':
            raise ValueError('SC-035 only qualifies the complete physical mass metric.')
        n=space.curve.nodes(space.count)
        basis=self.velocities(space,n)*self.length_unit_m
        return basis.T@((n.arc_length_weights/n.perimeter)[:,None]*basis)

    def trial(self,space,coefficients):
        started=time.perf_counter()
        self.counts['trial_constructions']+=1
        a=self._checked(space,coefficients)
        try:
            if not np.any(a):
                return space.curve,dict(projection_error=0.,projection_relative=0.,
                    maximum_normal_m=0.,rms_normal_m=0.,refits=2,speed_ratio=speed_ratio(space.curve),
                    intentional_projection_mm=0.,finite_path=self.name)
            coarse,smoothing=self._project(space.curve,a,space.curve_modes,space.count,
                                           self.length_unit_m,validate=True)
            fine,_=self._project(space.curve,a,space.curve_modes,2*space.count,
                                 self.length_unit_m,validate=True)
            c=space.curve.coefficients+coarse-space.base_projection
            f=space.curve.coefficients+fine-space.fine_base_projection
            error=float(np.max(np.abs(values(c-f,2*space.count))))
            radius=space.curve.nodes(space.count).perimeter/(2*np.pi)
            if error/radius>self.projection_tolerance:
                raise UpdateRefused('unresolved_projection',f'geometry grid refinement {error/radius:g}')
            candidate=FourierCurve(c)
            candidate.validate()
            return candidate,dict(projection_error=error,projection_relative=error/radius,
                **self.measure(space,a),speed_ratio=speed_ratio(candidate),refits=2,
                intentional_projection_mm=smoothing*self.length_unit_m*1e3,finite_path=self.name)
        except UpdateRefused:
            self.counts['refused_trials']+=1
            raise
        except ValueError as exc:
            self.counts['refused_trials']+=1
            raise _refusal(exc) from exc
        finally:
            self.counts['trial_seconds']+=time.perf_counter()-started


def resize(curve,band):
    """Enlarge the state without a shape change. Never truncate stage starts."""
    if band<curve.band:
        raise ValueError('Stage resize may only enlarge the band.')
    return FourierCurve(np.pad(curve.coefficients,(band-curve.band,band-curve.band)))
