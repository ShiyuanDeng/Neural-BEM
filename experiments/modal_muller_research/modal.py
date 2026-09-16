"""FFT similarity transforms and flux-density modal solves.

The physical state is (u, d_n u). The flux state is (u, J d_n u),
where J=|dx/dtheta|, including the native-to-canonical period conversion.
This is a similarity transform before truncation, not a changed BIE.
"""
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy.fft import fft, ifft, fftfreq
from scipy.linalg import lu_factor, lu_solve


def trace_slices(curves):
    sizes = [c.num_nodes for c in curves] * 2
    offsets = np.r_[0, np.cumsum(sizes)]
    return [slice(a, b) for a, b in zip(offsets[:-1], offsets[1:])]


def fft_left(array, curves, inverse=False):
    result = np.empty_like(array, dtype=complex)
    transform = ifft if inverse else fft
    for block in trace_slices(curves):
        result[block] = transform(array[block], axis=0, norm='ortho')
    return result


def fft_right(array, curves):
    result = np.empty_like(array, dtype=complex)
    for block in trace_slices(curves):
        result[:, block] = ifft(array[:, block], axis=1, norm='ortho')
    return result


def state_scale(curves, kind='flux'):
    speed = np.concatenate([c.speeds * c.period / (2*np.pi) for c in curves])
    if kind == 'constant':
        speed = np.full_like(speed, np.mean(speed))
    elif kind != 'flux':
        raise ValueError(kind)
    return np.r_[np.ones(len(speed)), speed]


def mode_indices(curves, cutoff):
    return np.concatenate([
        np.flatnonzero(np.abs(fftfreq(s.stop-s.start)*(s.stop-s.start)) <= cutoff) + s.start
        for s in trace_slices(curves)])


@dataclass
class ModalSystem:
    a: np.ndarray
    b: np.ndarray
    c: np.ndarray
    curves: tuple
    scale: np.ndarray
    transform_seconds: float

    @classmethod
    def from_nodal(cls, a, b, c, curves, kind='flux'):
        started = perf_counter()
        scale = state_scale(curves, kind)
        aa = fft_right(fft_left(a*scale[:, None]/scale[None, :], curves), curves)
        bb = fft_left(b*scale[:, None], curves)
        cc = fft_right(c/scale[None, :], curves)
        return cls(aa, bb, cc, tuple(curves), scale, perf_counter()-started)

    def solve(self, cutoff):
        started = perf_counter()
        indices = mode_indices(self.curves, cutoff)
        factors = lu_factor(self.a[np.ix_(indices, indices)])
        z = lu_solve(factors, self.b[indices])
        modal = np.zeros_like(self.b)
        modal[indices] = z
        y = self.c[:, indices] @ z
        seconds = perf_counter()-started
        physical = fft_left(modal, self.curves, inverse=True)/self.scale[:, None]
        return dict(y=y, physical=physical, z=z, indices=indices, factors=factors,
                    seconds=seconds,
                    residual=float(np.linalg.norm(self.a@modal-self.b)/np.linalg.norm(self.b)))
