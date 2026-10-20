"""B6. Normal optimizer coordinates → complete-trial coefficient velocities.

For each of the 2*M+1 coordinates (metres), apply positive/negative geometry
perturbations and differentiate the projected arclength-reset map at zero.
The derivative array has axes (2*K_geometry+1 Cartesian coefficients, 2*M+1
coordinates). These are finite differences of geometry, not forward physics.

The batched torch float64 construction retains its device, chunk size, grids,
base projections and out-of-memory fallback. C10 consumes the same prepared
space for finite trials; B7 contracts these velocities with field traces.
"""
from . import checks
import time
import numpy as np
import torch
from .continuation.geometry import grid_size, normal_basis
from .continuation.updates import BorgesUpdate
from .c10_geometry_trial import CertifiedSpace, CertifiedSpectralUpdate


CHUNK_BYTES = 2**29   # complex128 e^{-ik alpha} block per chunk (512 MiB)


def batched_projection(curve, steps, band, count, length_unit_m, device):
    """``spectral_project(curve, a, band, count, unit)[0]`` for every row a of ``steps``."""
    nodes = curve.nodes(count)
    z = torch.as_tensor(curve.values(count), device=device)
    basis = torch.as_tensor(normal_basis(nodes, steps.shape[1]//2), device=device)
    normal = torch.as_tensor(nodes.normals@np.array([1, 1j]), device=device)
    moved = z[None]+(torch.as_tensor(steps, device=device)@basis.T/length_unit_m)*normal[None]
    spectrum = torch.fft.fft(moved, dim=1)/count
    spectrum[:, count//2] = 0                                    # from_samples keeps |j| <= count/2-1
    modes = torch.fft.fftfreq(count, d=1/count, device=device).to(torch.float64)
    values = torch.fft.ifft(spectrum, dim=1)*count
    speeds = (torch.fft.ifft(spectrum*(1j*modes), dim=1)*count).abs()
    speed = torch.fft.fft(speeds, dim=1)/count
    primitive = torch.zeros_like(speed)
    primitive[:, 1:] = speed[:, 1:]/(1j*modes[1:])
    oscillation = (torch.fft.ifft(primitive, dim=1)*count).real
    theta = 2*np.pi*torch.arange(count, device=device, dtype=torch.float64)/count
    distance = speed[:, :1].real*theta+oscillation-oscillation[:, :1]
    length = 2*np.pi*speed[:, 0].real
    gaps = torch.diff(torch.cat((distance, length[:, None]), 1), dim=1)
    checks.require_arclength_monotone(gaps)
    angles = 2*np.pi*distance/length[:, None]
    weights = values*speeds/(length[:, None]/(2*np.pi))
    k = torch.arange(band+1, device=device, dtype=torch.float64)
    rows = max(1, CHUNK_BYTES//(16*(band+1)*count))
    out = []
    for i in range(0, len(steps), rows):
        powers = torch.exp(-1j*k[None, :, None]*angles[i:i+rows, None, :])
        positive = torch.einsum('pkn,pn->pk', powers, weights[i:i+rows])/count
        negative = torch.einsum('pkn,pn->pk', powers[:, 1:].conj(), weights[i:i+rows])/count
        out.append(torch.cat((negative.flip(1), positive), 1))
    return torch.cat(out).cpu().numpy()


class BatchedCertifiedUpdate(CertifiedSpectralUpdate):
    """NU-005 update; ``prepare`` evaluates all its projections in one batched device call."""

    def __init__(self, length_unit_m, *, device=None, **kwargs):
        super().__init__(length_unit_m, **kwargs)
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.counts.update(batched_preparations=0, prepare_fallbacks=0)
        self.fallback_reasons = {}

    def settings(self):
        return dict(super().settings(), prepare='batched torch float64 (NU-006)', prepare_device=self.device,
                    chunk_bytes=CHUNK_BYTES)

    def prepare(self, curve, update_modes, curve_modes):
        started = time.perf_counter()
        plain = BorgesUpdate.prepare(self, curve, update_modes, curve_modes)
        count = grid_size(max(curve_modes, update_modes))
        dim = len(plain.orders)
        eye = np.eye(dim)*self.derivative_step_m
        steps = np.vstack((np.zeros(dim), eye, -eye))
        try:
            coarse = batched_projection(curve, steps, curve_modes, count, self.length_unit_m, self.device)
            fine = batched_projection(curve, steps[:1], curve_modes, 2*count, self.length_unit_m, self.device)[0]
        except torch.OutOfMemoryError as exc:
            torch.cuda.empty_cache()
            self.counts['prepare_fallbacks'] += 1
            self.fallback_reasons[type(exc).__name__] = self.fallback_reasons.get(type(exc).__name__, 0)+1
            return super().prepare(curve, update_modes, curve_modes)
        self.counts['geometry_projections'] += len(steps)+1
        derivatives = (coarse[1:dim+1]-coarse[dim+1:])/(2*self.derivative_step_m)
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['batched_preparations'] += 1
        self.counts['preparation_seconds'] += elapsed
        return CertifiedSpace(**plain.__dict__, derivatives=derivatives.T.copy(), base_projection=coarse[0],
                              fine_base_projection=fine, count=count, preparation_seconds=elapsed)
