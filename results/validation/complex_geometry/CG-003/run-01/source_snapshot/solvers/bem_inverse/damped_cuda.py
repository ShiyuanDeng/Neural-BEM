"""Maintained SPD-016 fixed-ray assembly; field tables intentionally excluded."""
import numpy as np
import torch
from scipy.special import jv, hankel1

from gpr_bem_kress import cuda_assembly as CA
from gpr_bem_kress.geometry import adapt_periodic_curve
from gpr_bem_kress.operators import MullerAssemblyConfig


class RayTable:
    """J0, J1, J2, H0, H1, H2 at x*(1 + i gamma), x in [lo, hi], piecewise Chebyshev."""

    def __init__(self, gamma, lo=0.01, hi=100.0, degree=24, ratio=1.5, width=1.0, device='cuda'):
        self.w = complex(1.0, gamma)
        edges = [lo]
        while edges[-1] * ratio < 1.0:
            edges.append(edges[-1] * ratio)
        edges.append(1.0)
        while edges[-1] < hi:
            edges.append(edges[-1] + width)
        self.edges = np.array(edges)
        m = np.arange(degree + 1)
        nodes = np.cos(np.pi * (m + .5) / (degree + 1))           # first-kind points on [-1, 1]
        a, b = self.edges[:-1, None], self.edges[1:, None]
        x = (a + b) / 2 + (b - a) / 2 * nodes[None, :]            # (panels, degree+1)
        z = x * self.w
        values = np.stack([jv(0, z), jv(1, z), jv(2, z), hankel1(0, z), hankel1(1, z), hankel1(2, z)], -1)
        T = np.cos(np.outer(m, np.arccos(nodes)))                 # T_j(node_m)
        coeff = 2 / (degree + 1) * np.einsum('jm,pmf->pfj', T, values)
        coeff[..., 0] /= 2
        self.degree, self.lo, self.hi = degree, lo, edges[-1]
        self.coeff = torch.as_tensor(coeff, device=device)       # (panels, 6, degree+1)
        self.edges_t = torch.as_tensor(self.edges, device=device)
        self.seconds = None

    def __call__(self, x):
        if not bool(torch.isfinite(x).all()) or bool((x < self.lo).any()) or bool((x > self.hi).any()):
            raise ValueError('argument outside the tabulated ray segment')
        p = torch.clamp(torch.searchsorted(self.edges_t, x, right=True) - 1, 0, len(self.edges) - 2)
        a, b = self.edges_t[p], self.edges_t[p + 1]
        t = ((2 * x - a - b) / (b - a))[:, None]
        c = self.coeff[p]                                          # (M, 6, degree+1)
        b1 = torch.zeros(c.shape[:2], dtype=c.dtype, device=c.device)
        b2 = torch.zeros_like(b1)
        for j in range(self.degree, 0, -1):
            b1, b2 = c[:, :, j] + 2 * t * b1 - b2, b1
        return c[:, :, 0] + t * b1 - b2                            # (M, 6)



def make_direct(table, chunk=1 << 18):
    def _direct(radius, k_exterior, k_interior):
        ko, ki = complex(k_exterior), complex(k_interior)
        for k in (ko, ki):
            if abs(k / k.real - table.w) > 1e-14:
                raise ValueError('wavenumber is not on the tabulated damping ray')
        out = []
        for start in range(0, len(radius), chunk):
            r = radius[start:start + chunk]
            fo, fi = table(ko.real * r), table(ki.real * r)
            j0o, j1o, j2o, h0o, h1o, h2o = fo.unbind(1)
            j0i, j1i, j2i, h0i, h1i, h2i = fi.unbind(1)
            dh0 = h0o - h0i
            dh1 = ko * h1o - ki * h1i
            dh2 = ko ** 2 * h2o - ki ** 2 * h2i
            scale = -1.0 / (2.0 * np.pi)
            dj0 = j0o - j0i
            dj1 = ko * j1o - ki * j1i
            dj2 = ko ** 2 * j2o - ki ** 2 * j2i
            out.append([0.25j * dh0, -0.25j * dh1 / r, 0.25j * dh2,
                        scale * dj0, -scale * dj1 / r, scale * dj2])
        return [torch.cat(parts) for parts in zip(*out)]
    return _direct


def gpu_matrix(curve, ko, ki, table, *, adapter=None, prepared=None):
    """SPD-016 assembly with an explicit radial kernel, never a global patch."""
    CA._ready('cuda')
    adapter = adapt_periodic_curve(curve) if adapter is None else adapter
    blocks = CA._difference_blocks(adapter, complex(ko), complex(ki),
        MullerAssemblyConfig(), 'cuda', direct_kernel=make_direct(table), prepared=prepared)
    return CA._compose(blocks, adapter.num_nodes, 'cuda')
