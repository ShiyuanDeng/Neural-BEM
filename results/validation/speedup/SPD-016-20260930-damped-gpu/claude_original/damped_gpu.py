"""Scratch prototype: damped (complex-k) Kress assembly on the GPU (repo files untouched).

DF damps every wavenumber by the same factor w = 1 + i*gamma, and k_i = k_e sqrt(contrast)
with real sqrt(contrast). Every direct-branch Bessel argument is therefore x*w with
real x = Re(k)*r: J_n(xw) and H_n(xw), n = 0, 1, 2, are functions of one real variable.
They are tabulated once from SciPy (the same Amos routines the CPU reference calls) as
piecewise Chebyshev series and evaluated on the device with Clenshaw's recurrence.

The prototype swaps only `cuda_assembly._direct` in this process. `_series` (near pairs),
the geometry, the Kress weights, the diagonal limits and the composition are the existing
SPD-011 device code, which already carries complex scalars.
"""
import sys, time, json
import numpy as np
import torch
from scipy.special import jv, hankel1
from scipy.linalg import lu_factor

from gpr_bem_kress import cuda_assembly as CA
from gpr_bem_kress.geometry import adapt_periodic_curve
from gpr_bem_kress.operators import MullerAssemblyConfig
from gpr_bem_kress.execution import execution


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
        if bool((x < self.lo).any()) or bool((x > self.hi).any()):
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


TABLES = {}


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


def gpu_matrix(curve, ko, ki, table):
    CA._ready('cuda')
    original = CA._direct
    CA._direct = make_direct(table)
    try:
        adapter = adapt_periodic_curve(curve)
        blocks = CA._difference_blocks(adapter, complex(ko), complex(ki), MullerAssemblyConfig(), 'cuda')
        return CA._compose(blocks, adapter.num_nodes, 'cuda')
    finally:
        CA._direct = original


if __name__ == '__main__':
    from experiments.modal_atlas import damped_screen as ds
    from experiments.modal_atlas.contrast_screen import set_contrast
    from experiments.shape_continuation import forward as F

    gamma = ds.GAMMA
    t = time.perf_counter(); table = RayTable(gamma); torch.cuda.synchronize(); build = time.perf_counter() - t
    # 1. table accuracy against SciPy on random ray points
    rng = np.random.default_rng(0)
    x = np.sort(np.r_[np.exp(rng.uniform(np.log(.01), 0, 20000)), rng.uniform(1, 100, 80000)])
    z = x * table.w
    ref = np.stack([jv(0, z), jv(1, z), jv(2, z), hankel1(0, z), hankel1(1, z), hankel1(2, z)], -1)
    got = table(torch.as_tensor(x, device='cuda')).cpu().numpy()
    rel = np.abs(got - ref) / np.abs(ref)
    print(json.dumps(dict(table_build_s=build, panels=len(table.edges) - 1,
                          max_rel_by_function=rel.max(0).tolist(), p99999_rel=float(np.quantile(rel, 0.99999)))), flush=True)

    # 2. matrices, predictions and timings on recorded DF inputs
    for spec in sys.argv[1].split(','):
        contrast, scene = spec.split(':')
        contrast = float(contrast)
        if contrast != 0.5:
            set_contrast(contrast)
        real, damped_obs, initial = ds.fitting_data(contrast, scene)
        for j in (0, 5, 10, 18):
            o = damped_obs[j]
            ko, ki = o.wavenumber, o.wavenumber * np.sqrt(contrast)
            for nodes in (512, 1024):
                curve = initial.nodes(nodes)
                assemble, receivers, incident = F._operators(curve)
                with execution(kernels='reference', device='cpu'):
                    t = time.perf_counter(); A = np.asarray(assemble(curve, ko, ki).system_matrix); tcpu = time.perf_counter() - t
                gpu_matrix(curve, ko, ki, table); torch.cuda.synchronize()          # warm
                t = time.perf_counter(); Ag = gpu_matrix(curve, ko, ki, table); torch.cuda.synchronize(); tgpu = time.perf_counter() - t
                Ah = Ag.cpu().numpy()
                with execution(kernels='reference', device='cpu'):
                    rec = receivers(curve, o.acquisition.receivers, ko)
                    fld, nrm = incident(curve, o.acquisition.sources, ko, o.acquisition.strength)
                rhs = np.vstack((fld.T, nrm.T))
                y = [np.diag(rec.apply_state(F._solve(M, lu_factor(M), rhs)[0])) for M in (A, Ah)]
                t = time.perf_counter(); fac = CA.DeviceFactors(Ag); tr, res = F._solve(Ah, fac, rhs); torch.cuda.synchronize(); tlu = time.perf_counter() - t
                ydev = np.diag(rec.apply_state(tr))
                print(json.dumps(dict(contrast=contrast, scene=scene, freq_index=j, nodes=nodes, k=str(np.round(ko, 4)),
                                      matrix_max_rel=float(np.abs(Ah - A).max() / np.abs(A).max()),
                                      prediction_rel=float(np.linalg.norm(y[1] - y[0]) / np.linalg.norm(y[0])),
                                      prediction_rel_device_lu=float(np.linalg.norm(ydev - y[0]) / np.linalg.norm(y[0])),
                                      cpu_assembly_s=tcpu, gpu_assembly_s=tgpu, gpu_lu_solve_s=tlu)), flush=True)
