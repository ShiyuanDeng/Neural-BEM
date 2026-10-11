"""NU-006: the NU-005 update with its spectral ``prepare`` batched on the GPU.

``ProjectedUpdate.prepare`` builds 2(2M+1) + 2 independent projections of the accepted
curve: the base and fine-grid base projections and central differences (eps = 1e-7 m)
for every coordinate. NU-003/NU-005 run them one at a time on the CPU through
``spectral_project``. At K = 192, M = 37 that is 152 calls and about 2 s, mostly the
eq. 9 quadrature and the arclength basis of the same base curve recomputed each call.

``batched_projection`` evaluates the same mathematics for all steps at once in torch
float64: normal move on the uniform grid, FFT fit without the Nyquist mode, moved-curve
speed and normalised arclength, and the eq. 9 quadrature with e^{-ik alpha} evaluated
directly rather than by recurrence. Trials, validity tiers, LM, schedule and physics are
unchanged from NU-005. The arithmetic differs only by rounding, so the run is not
bit-identical; decision identity is measured.

Campaigns and diagnostics remain under experiments.cleaned_interface.
"""
import time
import numpy as np
import torch
from .continuation.geometry import grid_size, normal_basis
from .continuation.updates import BorgesUpdate
from .certified import CertifiedSpace, CertifiedSpectralUpdate


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
    if bool((gaps <= 0).any()):
        raise ValueError('Non-monotone arclength map.')
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
