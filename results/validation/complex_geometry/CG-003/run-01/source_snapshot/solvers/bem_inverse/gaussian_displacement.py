"""ON-001 Gaussian ambient displacement, Lipschitz-scaled once, then projected.

The raw ambient map has a global lower Lipschitz bound. The projected stored
curve still requires independent regularity/simplicity/refinement validation.
"""
from dataclasses import dataclass, field
from time import perf_counter
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.linalg import lu_factor, lu_solve
import torch
from .continuation.geometry import FourierCurve, grid_size, arclength_angles
from .continuation.updates import BorgesUpdate, UpdateRefused, _refusal, speed_ratio
from .continuation.validation import self_intersections
from .geometry import ProjectedSpace, ProjectedUpdate, values
from .spectral import arclength_quadrature


@dataclass(frozen=True)
class GaussianSpace(ProjectedSpace):
    centres: np.ndarray
    width: float
    weights: np.ndarray
    translation: np.ndarray
    prescribed: np.ndarray
    condition: float
    cache: dict = field(default_factory=dict, compare=False)


def kernel(points, centres, width):
    return np.exp(-abs(points[:, None]-centres[None, :])**2/(2*width**2))


def project_batch(samples, band, device):
    """Same spectral arclength quadrature as NU-006, for supplied moved samples."""
    moved = torch.as_tensor(samples, device=device)
    count = samples.shape[1]
    spectrum = torch.fft.fft(moved, dim=1)/count
    spectrum[:, count//2] = 0
    modes = torch.fft.fftfreq(count, d=1/count, device=device).to(torch.float64)
    z = torch.fft.ifft(spectrum, dim=1)*count
    speeds = (torch.fft.ifft(spectrum*(1j*modes), dim=1)*count).abs()
    speed = torch.fft.fft(speeds, dim=1)/count
    primitive = torch.zeros_like(speed)
    primitive[:, 1:] = speed[:, 1:]/(1j*modes[1:])
    oscillation = (torch.fft.ifft(primitive, dim=1)*count).real
    theta = 2*np.pi*torch.arange(count, device=device, dtype=torch.float64)/count
    distance = speed[:, :1].real*theta+oscillation-oscillation[:, :1]
    length = 2*np.pi*speed[:, 0].real
    if bool((torch.diff(torch.cat((distance, length[:, None]), 1), dim=1) <= 0).any()):
        raise UpdateRefused("irregular_parameterization", "Non-monotone Gaussian arclength map")
    angles = 2*np.pi*distance/length[:, None]
    weights = z*speeds/(length[:, None]/(2*np.pi))
    k = torch.arange(band+1, device=device, dtype=torch.float64)
    rows = max(1, 2**27//(16*(band+1)*count))
    out = []
    for i in range(0, len(samples), rows):
        powers = torch.exp(-1j*k[None, :, None]*angles[i:i+rows, None, :])
        positive = torch.einsum("pkn,pn->pk", powers, weights[i:i+rows])/count
        negative = torch.einsum("pkn,pn->pk", powers[:, 1:].conj(), weights[i:i+rows])/count
        out.append(torch.cat((negative.flip(1), positive), 1))
    return torch.cat(out).cpu().numpy()


def projection_tangent(curve, directions, band, count):
    """Differentiate the full discrete projection of supplied Gaussian field directions.

    The field directions include the saddle solve. Scaling is identity in a
    neighbourhood of zero; fixed centres/width do not depend on coordinates.
    """
    modes = np.fft.fftfreq(count)*count
    spectrum = np.fft.fft(directions, axis=0)/count
    # Exactly the band kept by from_samples, including both omitted modes on
    # odd diagnostic grids (production grid_size always returns an even size).
    spectrum[np.abs(np.rint(modes)) > count//2-1] = 0
    dz = np.fft.ifft(spectrum, axis=0)*count
    dz_prime = np.fft.ifft(spectrum*(1j*modes[:, None]), axis=0)*count

    # Reproduce the zero-step FFT fit before differentiating its speed/map.
    moved = FourierCurve.from_samples(curve.values(count), count//2-1)
    base = moved.nodes(count)
    z, z_prime = moved.values(count), moved.values(count, 1)
    sigma = base.speeds
    if not np.all(np.isfinite(sigma)) or np.min(sigma) <= 0:
        raise ValueError('Projection derivative requires a regular curve.')
    alpha, length = arclength_angles(base)
    mean = length/(2*np.pi)
    dsigma = (np.conj(z_prime)[:, None]*dz_prime).real/sigma[:, None]
    dspectrum = np.fft.fft(dsigma, axis=0)/count
    dmean = dspectrum[0].real
    primitive = np.zeros_like(dspectrum)
    primitive[1:] = dspectrum[1:]/(1j*modes[1:, None])
    oscillation = (np.fft.ifft(primitive, axis=0)*count).real
    ddistance = base.parameters[:, None]*dmean+oscillation-oscillation[0]
    dalpha = (ddistance-alpha[:, None]*dmean)/mean
    weights = z*sigma/mean
    dweights = (dz*sigma[:, None]+z[:, None]*dsigma)/mean-weights[:, None]*dmean/mean

    orders = np.arange(-band, band+1)
    out = np.empty((len(orders), directions.shape[1]), complex)
    for start in range(0, len(orders), 32):
        k = orders[start:start+32, None]
        phase = np.exp(-1j*k*alpha)
        out[start:start+32] = (phase@dweights-1j*k*(phase@(weights[:, None]*dalpha)))/count
    if not np.isfinite(out).all():
        raise ValueError('Non-finite projection derivative.')
    return out


class GaussianDisplacement(ProjectedUpdate):
    name = "gaussian_lipschitz_displacement"

    def __init__(self, length_unit_m, *, width_factor=2., device=None, **kwargs):
        super().__init__(length_unit_m, **kwargs)
        self.width_factor = float(width_factor)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.counts.update(interpolation_seconds=0., projection_seconds=0., raw_clipped=0,
                           interpolation_refusals=0, certificate_seconds=0., sampled_seconds=0.)
        self.last_trial = {}

    def settings(self):
        return dict(super().settings(), construction="z + P_K[R(z+alpha*v_a(z))-R(z)]",
            displacement="v=b+sum w exp(-distance^2/(2 width^2)); alpha=min(1,.8/C), applied once",
            width_factor=self.width_factor, ridge=1e-10, condition_limit=1e12,
            interpolation_relative_tolerance=1e-4, control_count="max(32,2*(2M+1))",
            raw_lower_lipschitz=.2, projected_validity="sampled original gates and grid doubling",
            tangent="analytic derivative of complete discrete projection of interpolated Gaussian field at zero", device=self.device)

    def _velocities(self, space, count):
        if count not in space.cache:
            space.cache[count] = kernel(space.curve.values(count), space.centres, space.width)@space.weights+space.translation
        return space.cache[count]

    def prepare(self, curve, update_modes, curve_modes):
        started = perf_counter()
        plain = BorgesUpdate.prepare(self, curve, update_modes, curve_modes)
        count = grid_size(max(curve_modes, update_modes))
        n = curve.nodes(count)
        angles, _ = arclength_angles(n)
        controls = max(32, 2*(2*update_modes+1))
        s = 2*np.pi*np.arange(controls)/controls
        theta = CubicSpline(np.r_[angles, 2*np.pi], np.r_[n.parameters, 2*np.pi])(s)
        powers = np.exp(1j*theta[:, None]*curve.modes)
        centres = powers@curve.coefficients
        dz = powers@(curve.coefficients*1j*curve.modes)
        normals = -1j*dz/abs(dz)
        phase = s[:, None]*np.arange(1, update_modes+1)
        basis = np.column_stack((np.ones(controls), np.cos(phase), np.sin(phase)))
        prescribed = normals[:, None]*basis/self.length_unit_m
        width = self.width_factor*float(np.median(abs(np.roll(centres, -1)-centres)))
        if not width > 0:
            raise UpdateRefused("gaussian_interpolation", "Nonpositive Gaussian width")
        K = kernel(centres, centres, width)
        saddle = np.zeros((controls+1, controls+1))
        saddle[:-1, :-1] = K+1e-10*np.eye(controls)
        saddle[-1, :-1] = saddle[:-1, -1] = 1.
        condition = float(np.linalg.cond(saddle))
        if not condition <= 1e12:
            self.counts["interpolation_refusals"] += 1
            raise UpdateRefused("gaussian_interpolation", f"condition {condition:g} > 1e12")
        coefficients = lu_solve(lu_factor(saddle), np.vstack((prescribed, np.zeros((1, prescribed.shape[1])))))
        relative = np.linalg.norm(K@coefficients[:-1]+coefficients[-1]-prescribed, axis=0)/np.linalg.norm(prescribed, axis=0)
        if max(relative) > 1e-4:
            self.counts["interpolation_refusals"] += 1
            raise UpdateRefused("gaussian_interpolation", f"coordinate interpolation error {max(relative):g}")
        self.counts["interpolation_seconds"] += perf_counter()-started
        dim = len(plain.orders)
        zero = np.zeros((2*curve_modes+1, dim), complex)
        space = GaussianSpace(**plain.__dict__, derivatives=zero, base_projection=zero[:, 0],
            fine_base_projection=zero[:, 0], count=count, preparation_seconds=0., centres=centres, width=width,
            weights=coefficients[:-1], translation=coefficients[-1], prescribed=prescribed, condition=condition)
        projection_started = perf_counter()
        coarse = project_batch(curve.values(count)[None], curve_modes, self.device)[0]
        fine = project_batch(curve.values(2*count)[None], curve_modes, self.device)[0]
        derivatives = projection_tangent(curve, self._velocities(space, count), curve_modes, count)
        self.counts["projection_seconds"] += perf_counter()-projection_started
        elapsed = perf_counter()-started
        self.counts["preparations"] += 1
        self.counts["geometry_projections"] += 2
        self.counts["preparation_seconds"] += elapsed
        return GaussianSpace(**plain.__dict__, derivatives=derivatives, base_projection=coarse,
            fine_base_projection=fine, count=count, preparation_seconds=elapsed, centres=centres, width=width,
            weights=space.weights, translation=space.translation, prescribed=prescribed,
            condition=condition, cache=space.cache)

    def tangent_at(self, space, coefficients, direction):
        """Complete directional derivative away from the norm/clipping kinks.

        Centres and interpolation solve are fixed in this prepared finite map.
        A coefficient-zero Gaussian group or C=.8 requires one-sided checks.
        """
        a = self._checked(space, coefficients)
        d = self._checked(space, direction)
        w, dw = space.weights@a, space.weights@d
        C = float(np.exp(-.5)*sum(abs(w))/space.width)
        alpha = min(1., .8/C) if C > 0 else 1.
        if C > .8:
            nonzero = abs(w) > 0
            if np.any(~nonzero & (abs(dw) > 0)):
                raise ValueError("Gaussian norm kink requires a one-sided derivative")
            gradient = np.exp(-.5)*float(np.real(np.sum(np.conj(w[nonzero])*dw[nonzero]/abs(w[nonzero]))))/space.width
            dalpha = -alpha*gradient/C
        elif abs(C-.8) <= 1e-12:
            raise ValueError("Gaussian clipping kink requires one-sided checks")
        else:
            dalpha = 0.
        used_direction = alpha*d+dalpha*a
        velocity = self._velocities(space, space.count)
        raw = space.curve.values(space.count)+alpha*(velocity@a)
        moved = FourierCurve.from_samples(raw, space.count//2-1)
        return projection_tangent(moved, (velocity@used_direction)[:, None], space.curve_modes, space.count)[:, 0]

    def trial(self, space, coefficients):
        started = perf_counter()
        self.counts["trial_constructions"] += 1
        a = self._checked(space, coefficients)
        self.last_trial = {}
        try:
            if not np.any(a):
                return space.curve, dict(a_used=a.tolist(), gaussian_alpha=1., gaussian_C=0.,
                    raw_lower_lipschitz=1., projection_relative=0., maximum_normal_m=0., rms_normal_m=0.)
            w, b = space.weights@a, space.translation@a
            target = space.prescribed@a
            error = float(np.linalg.norm(kernel(space.centres, space.centres, space.width)@w+b-target)
                          /max(np.linalg.norm(target), np.finfo(float).tiny))
            if error > 1e-4:
                self.counts["interpolation_refusals"] += 1
                raise UpdateRefused("gaussian_interpolation", f"direction interpolation error {error:g}")
            C = float(np.exp(-.5)*sum(abs(w))/space.width)
            alpha = min(1., .8/C) if C > 0 else 1.
            used = alpha*a
            if alpha < 1:
                self.counts["raw_clipped"] += 1
            self.last_trial = dict(a_used=used.tolist(), gaussian_alpha=alpha, gaussian_C=C,
                gaussian_momenta_norm_sum=float(sum(abs(w))), gaussian_translation=complex(b),
                gaussian_width_solver=space.width, gaussian_condition=space.condition,
                gaussian_interpolation_relative=error, raw_lower_lipschitz=1-alpha*C,
                scaling="original fitted field scaled exactly once")
            projected, raw_values, smoothing = [], [], []
            projection_started = perf_counter()
            sampled_before = self.counts["sampled_seconds"]
            for count in (space.count, 2*space.count):
                raw = space.curve.values(count)+alpha*(self._velocities(space, count)@a)
                moved = FourierCurve.from_samples(raw, count//2-1)
                sampled_started = perf_counter()
                raw_nodes = moved.nodes(count)
                if raw_nodes.signed_area <= 0 or min(raw_nodes.speeds) < 1e-6*np.mean(raw_nodes.speeds):
                    raise UpdateRefused("irregular_parameterization", "Invalid Gaussian displaced curve")
                if self_intersections(raw_nodes.points):
                    raise UpdateRefused("self_intersection", "Gaussian displaced curve self-intersects")
                self.counts["sampled_seconds"] += perf_counter()-sampled_started
                p, sm = arclength_quadrature(moved, moved.nodes(count), space.curve_modes)
                projected.append(p)
                raw_values.append(raw)
                smoothing.append(sm)
                self.counts["geometry_projections"] += 1
            self.counts["projection_seconds"] += perf_counter()-projection_started-(self.counts["sampled_seconds"]-sampled_before)
            c = space.curve.coefficients+projected[0]-space.base_projection
            f = space.curve.coefficients+projected[1]-space.fine_base_projection
            refinement = float(max(abs(values(c-f, 2*space.count))))
            radius = space.curve.nodes(space.count).perimeter/(2*np.pi)
            self.last_trial.update(projection_relative=refinement/radius, projection_error=refinement,
                raw_maximum_displacement_m=float(max(abs(raw_values[0]-space.curve.values(space.count))))*self.length_unit_m,
                intentional_projection_mm=smoothing[0]*self.length_unit_m*1e3)
            if refinement/radius > self.projection_tolerance:
                raise UpdateRefused("unresolved_projection", f"Gaussian projection grid refinement {refinement/radius:g}")
            candidate = FourierCurve(c)
            raw_curve = FourierCurve.from_samples(raw_values[0], space.count//2-1)
            alpha_angles, _ = arclength_angles(raw_curve.nodes(space.count))
            represented = np.exp(1j*alpha_angles[:, None]*candidate.modes)@candidate.coefficients
            self.last_trial['raw_projected_displacement_mm'] = float(max(abs(represented-raw_values[0])))*self.length_unit_m*1e3
            sampled_started = perf_counter()
            candidate.validate()
            self.counts["sampled_seconds"] += perf_counter()-sampled_started
            self.last_trial.update(**self.measure(space, used), speed_ratio=speed_ratio(candidate),
                                   finite_path=self.name, final_validity="passed")
            return candidate, dict(self.last_trial)
        except UpdateRefused:
            self.counts["refused_trials"] += 1
            raise
        except ValueError as exc:
            self.counts["refused_trials"] += 1
            raise _refusal(exc) from exc
        finally:
            self.counts["trial_seconds"] += perf_counter()-started
