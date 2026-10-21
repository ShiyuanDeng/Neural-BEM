"""Spline arclength geometry update, its preparation and step measurements."""
from .. import checks
from dataclasses import dataclass, field
import time
import numpy as np
from ..continuation.geometry import (
    FourierCurve, arclength_angles, grid_size, normal_basis, integer,
    reparameterize, values, speed_ratio,
)
from ..errors import UpdateRefused, refusal_from_value_error as _refusal
from scipy.interpolate import CubicSpline


@dataclass(frozen=True)
class Prepared:
    """Directions and projection data for this method at one accepted curve."""
    curve: FourierCurve
    update_modes: int
    curve_modes: int
    length_unit_m: float
    orders: np.ndarray
    labels: tuple
    derivatives: np.ndarray
    base_projection: np.ndarray
    fine_base_projection: np.ndarray
    count: int
    preparation_seconds: float
    cache: dict = field(default_factory=dict, compare=False)


ProjectedSpace = Prepared


def project(curve, coefficients, band, count, length_unit_m, *, validate=False):
    nodes=curve.nodes(count)
    z=curve.values(count)
    h=normal_basis(nodes,len(coefficients)//2)@coefficients/length_unit_m
    normal=nodes.normals@np.array([1,1j])
    moved=FourierCurve.from_samples(z+h*normal,count//2-1)
    n=moved.nodes(count)
    if validate:
        checks.check_area(moved.coefficients)
        checks.check_speed(n.speeds)
        checks.check_intersection(n.points)
    angles,_=arclength_angles(n)
    inverse=CubicSpline(np.r_[angles,2*np.pi],np.r_[n.parameters,2*np.pi])
    zz=moved.values(count)
    interpolate=CubicSpline(np.r_[n.parameters,2*np.pi],np.r_[zz,zz[0]],bc_type='periodic')
    samples=interpolate(inverse(n.parameters))
    projected=FourierCurve.from_samples(samples,band)
    error=float(np.max(np.abs(projected.values(count)-samples)))
    return projected.coefficients,error


class ProjectedUpdate:
    name = "centred_state_band_projection"

    def __init__(self, length_unit_m, *, projection_tolerance=1e-5, derivative_step_m=1e-7):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        if not np.isfinite(projection_tolerance) or projection_tolerance <= 0:
            raise ValueError('projection_tolerance must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.projection_tolerance = float(projection_tolerance)
        self.derivative_step_m = float(derivative_step_m)
        checks.require_derivative_step(self.derivative_step_m)
        self.counts = dict(preparations=0, geometry_projections=0, trial_constructions=0,
                          refused_trials=0, preparation_seconds=0., trial_seconds=0.)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m,
                    projection_tolerance=self.projection_tolerance,
                    coordinates='real Fourier coefficients of normal distance h (m) in normalized arclength',
                    gauge='arclength refit on every trial', derivative_step_m=self.derivative_step_m,
                    construction='z + P_K[A(z+h n)-A(z)]',
                    projection_tolerance_meaning='grid refinement, not intentional smoothing')

    def regauge(self, curve, curve_modes):
        """Express an input curve in this strategy's gauge at storage band K."""
        integer(curve_modes, "curve_modes")
        try:
            shape, error = reparameterize(curve, curve_modes, tolerance=self.projection_tolerance)
        except ValueError as exc:
            raise _refusal(exc) from exc
        return shape, float(error)

    def _project(self,*args,**kwargs):
        self.counts['geometry_projections']+=1
        return project(*args,**kwargs)

    def prepare(self,curve,update_modes,curve_modes):
        started=time.perf_counter()
        update_modes = integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('The accepted curve must already use the stage storage band.')
        harmonics = np.arange(1, update_modes+1)
        plain = dict(curve=curve, update_modes=update_modes, curve_modes=curve_modes,
                     length_unit_m=self.length_unit_m,
                     orders=np.concatenate(([0], harmonics, harmonics)),
                     labels=('a0', *[f'a{m}' for m in harmonics], *[f'b{m}' for m in harmonics]))
        count=grid_size(max(curve_modes,update_modes))
        dim=len(plain['orders'])
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
        return ProjectedSpace(**plain,derivatives=np.stack(derivatives,axis=1),
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

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f"Expected {len(space.orders)} finite update coefficients.")
        return a

    def geometry_update(self, curve, normal_update, *, prepared):
        return geometry_update(curve, normal_update, prepared=prepared, settings=self)

    def trial(self, space, coefficients):
        """Compatibility entry point; use the same implementation as the fitter."""
        return geometry_update(space.curve, coefficients, prepared=space, settings=self)


def geometry_update(curve, normal_update, *, prepared, settings):
    if curve is not prepared.curve and not np.array_equal(curve.coefficients, prepared.curve.coefficients):
        raise ValueError('Prepared geometry belongs to a different curve.')
    started=time.perf_counter()
    settings.counts['trial_constructions']+=1
    a=settings._checked(prepared,normal_update)
    try:
        if not np.any(a):
            return prepared.curve,dict(projection_error=0.,projection_relative=0.,
                maximum_normal_m=0.,rms_normal_m=0.,refits=2,speed_ratio=speed_ratio(prepared.curve),
                intentional_projection_mm=0.,finite_path=settings.name)
        coarse,smoothing=settings._project(prepared.curve,a,prepared.curve_modes,prepared.count,
                                       settings.length_unit_m,validate=True)
        fine,_=settings._project(prepared.curve,a,prepared.curve_modes,2*prepared.count,
                             settings.length_unit_m,validate=True)
        c=prepared.curve.coefficients+coarse-prepared.base_projection
        f=prepared.curve.coefficients+fine-prepared.fine_base_projection
        error=float(np.max(np.abs(values(c-f,2*prepared.count))))
        radius=prepared.curve.nodes(prepared.count).perimeter/(2*np.pi)
        checks.require_projection_agreement(error, radius, settings.projection_tolerance)
        candidate=FourierCurve(c)
        checks.check_area(candidate.coefficients)
        final_nodes = candidate.nodes(grid_size(candidate.band))
        checks.check_speed(final_nodes.speeds)
        checks.check_intersection(final_nodes.points)
        return candidate,dict(projection_error=error,projection_relative=error/radius,
            **settings.measure(prepared,a),speed_ratio=speed_ratio(candidate),refits=2,
            intentional_projection_mm=smoothing*settings.length_unit_m*1e3,finite_path=settings.name)
    except UpdateRefused:
        settings.counts['refused_trials']+=1
        raise
    except ValueError as exc:
        settings.counts['refused_trials']+=1
        raise _refusal(exc) from exc
    finally:
        settings.counts['trial_seconds']+=time.perf_counter()-started
