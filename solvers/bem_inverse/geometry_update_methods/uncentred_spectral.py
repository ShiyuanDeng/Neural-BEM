"""Uncentred refit: store the arclength refit of the moved boundary directly (GU-001).

A trial is R(w_a), the eq. 9 arclength refit of the pushed curve cropped to the
storage band, instead of spectral's c + R(w_a) - R(0). The two differ by the
fixed c - R(0), so the slope in a is spectral's: preparation is spectral's
batched central difference of R, built from spectral's functions. Every
accepted curve is in the arclength gauge up to the crop.
"""
import time

import numpy as np
import torch

from .. import checks
from ..continuation.geometry import FourierCurve, grid_size, integer, speed_ratio, values
from ..errors import UpdateRefused, refusal_from_value_error as _refusal
from .spectral import CHUNK_BYTES, Prepared, batched_projection, push_and_refit, sample_grid

CONSTRUCTION = 'P_K R(z+h*n), R = eq. 9 arclength quadrature (no splines); FD derivative of R'


class UncentredSpectralUpdate:
    name = 'uncentred_arclength_refit'

    def __init__(self, length_unit_m, *, derivative_step_m=1e-7, device=None):
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.derivative_step_m = float(derivative_step_m)
        checks.require_derivative_step(self.derivative_step_m)
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.counts = dict(preparations=0, geometry_projections=0, trial_constructions=0, refused_trials=0,
                           preparation_seconds=0., trial_seconds=0., sampled_seconds=0., projection_seconds=0.)

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m,
                    coordinates='real Fourier coefficients of normal distance h (m) in normalized arclength',
                    gauge='arclength refit stored on every trial; zero step gives R(0), not c',
                    derivative_step_m=self.derivative_step_m, construction=CONSTRUCTION,
                    resampler='eq. 9 quadrature on the uniform grid; no splines', boundary_samples=True,
                    validity='coefficient area, sampled minimum speed and segment intersections',
                    prepare='batched torch float64', prepare_device=self.device, chunk_bytes=CHUNK_BYTES)

    def prepare(self, curve, update_modes, curve_modes):
        started = time.perf_counter()
        update_modes = integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('The accepted curve must already use the stage storage band.')
        harmonics = np.arange(1, update_modes+1)
        count = grid_size(max(curve_modes, update_modes))
        dim = 2*update_modes+1
        eye = np.eye(dim)*self.derivative_step_m
        steps = np.vstack((np.zeros(dim), eye, -eye))
        refits = batched_projection(curve, steps, curve_modes, count, self.length_unit_m, self.device)
        self.counts['geometry_projections'] += len(steps)
        derivatives = ((refits[1:dim+1]-refits[dim+1:])/(2*self.derivative_step_m)).T.copy()
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        return Prepared(curve=curve, update_modes=update_modes, curve_modes=curve_modes,
                        length_unit_m=self.length_unit_m, orders=np.concatenate(([0], harmonics, harmonics)),
                        labels=('a0', *[f'a{m}' for m in harmonics], *[f'b{m}' for m in harmonics]),
                        derivatives=derivatives, base_projection=refits[0], count=count,
                        grid=sample_grid(curve, count, update_modes), preparation_seconds=elapsed)

    def velocities(self, space, nodes):
        vectors = values(space.derivatives, nodes.num_nodes)
        n = nodes.normals@np.array([1, 1j])
        return (vectors*np.conj(n[:, None])).real

    def measure(self, space, coefficients):
        a = self._checked(space, coefficients)
        n = space.curve.nodes(space.count)
        h = self.velocities(space, n)@a*self.length_unit_m
        w = n.arc_length_weights/n.perimeter
        return dict(maximum_normal_m=float(np.max(np.abs(h))), rms_normal_m=float(np.sqrt(w@h**2)))

    def metric(self, space, kind, smoothing_m=None):
        if kind != 'mass':
            raise ValueError('SC-035 only qualifies the complete physical mass metric.')
        n = space.curve.nodes(space.count)
        basis = self.velocities(space, n)*self.length_unit_m
        return basis.T@((n.arc_length_weights/n.perimeter)[:, None]*basis)

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f"Expected {len(space.orders)} finite update coefficients.")
        return a


def geometry_update(normal_update, *, prepared, settings):
    """Move and refit on the N-point grid, store the refit itself, then check it.

    Logs the zero-step jump ||c - R(0)|| (coefficient l2, so the RMS
    parameter shift between the two gauges) and the crop of the refit.
    """
    curve = prepared.curve
    started = time.perf_counter()
    settings.counts['trial_constructions'] += 1
    a = settings._checked(prepared, normal_update)
    unit_mm = settings.length_unit_m*1e3
    jump = float(np.linalg.norm(curve.coefficients-prepared.base_projection))*unit_mm
    try:
        settings.counts['geometry_projections'] += 1
        projected_at = time.perf_counter()
        try:
            refit, smoothing = push_and_refit(prepared.grid, a, prepared.curve_modes, settings.length_unit_m)
        finally:
            settings.counts['projection_seconds'] += time.perf_counter()-projected_at
        candidate = FourierCurve(refit)
        checked_at = time.perf_counter()
        try:
            checks.check_area(candidate.coefficients)
            final_nodes = candidate.nodes(grid_size(candidate.band))
            checks.check_speed(final_nodes.speeds)
            checks.check_intersection(final_nodes.points)
        finally:
            settings.counts['sampled_seconds'] += time.perf_counter()-checked_at
        return candidate, dict(**settings.measure(prepared, a), speed_ratio=speed_ratio(candidate), refits=1,
            intentional_projection_mm=smoothing*unit_mm, zero_step_jump_mm=jump, finite_path=settings.name)
    except UpdateRefused:
        settings.counts['refused_trials'] += 1
        raise
    except ValueError as exc:
        settings.counts['refused_trials'] += 1
        raise _refusal(exc) from exc
    finally:
        settings.counts['trial_seconds'] += time.perf_counter()-started
