"""ON-002 known-material TG adaptation of the pinned, read-only GauGal source.

Dependency direction is benchmark -> external GauGal. No BEM runtime imports
GauGal. Physical Helmholtz operators are built here, never read from SingleTX.
"""
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
import importlib.metadata
import subprocess
import sys

import numpy as np
from scipy.integrate import quad
from scipy.special import hankel1, roots_legendre
import torch

EXTERNAL = Path("/home/drdeng/Gau-Gal")
PIN = "3ec2627d3ff7329453ec7b76469a0761d6f6e3de"


def external():
    head = subprocess.check_output(["git", "-C", str(EXTERNAL), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise RuntimeError(f"Pinned GauGal changed: {head}")
    path = str(EXTERNAL / "src")
    if path not in sys.path:
        sys.path.insert(0, path)
    from gaugal.paper2d import collocation as C
    from gaugal.paper2d import synthetic as S
    return C, S


def sync(device):
    if torch.device(device).type == "cuda":
        torch.cuda.synchronize(device)


def circle_fraction(x, y, spacing, center, radius):
    """Exact disk/cell area, deterministic adaptive integration on boundary cells."""
    xx, yy = np.meshgrid(x-center.real, y-center.imag)
    h = spacing / 2
    near = np.hypot(np.maximum(abs(xx)-h, 0), np.maximum(abs(yy)-h, 0))
    far = np.hypot(abs(xx)+h, abs(yy)+h)
    out = (far <= radius).astype(float)
    for iy, ix in zip(*np.where((near < radius) & (far > radius))):
        a, b = max(xx[iy, ix]-h, -radius), min(xx[iy, ix]+h, radius)
        ymin, ymax = yy[iy, ix]-h, yy[iy, ix]+h
        def width(t):
            v = np.sqrt(max(radius*radius-t*t, 0))
            return max(0, min(ymax, v)-max(ymin, -v))
        breaks = [a, b]
        for v in (ymin, ymax):
            if abs(v) < radius:
                u = np.sqrt(radius*radius-v*v)
                breaks.extend(t for t in (-u, u) if a < t < b)
        breaks = sorted(set(breaks))
        area = sum(quad(width, u, v, epsabs=spacing**2*1e-10)[0]
                   for u, v in zip(breaks[:-1], breaks[1:]))
        out[iy, ix] = area / spacing**2
    return np.clip(out, 0, 1)


def physical_kernel(k, n, dx, dy):
    """Cell-integrated outgoing k² G; singular square integral is analytic/radial.

    Four-point tensor Gauss integrates nonself source cells. Self uses 32-point
    angular quadrature of the exact radial primitive. No periodic propagation.
    """
    offsets = np.arange(-(n-1), n)
    xx, yy = np.meshgrid(offsets*dx, offsets*dy)
    values = np.zeros(xx.shape, complex)
    q, w = roots_legendre(4)
    for a, wa in zip(q, w):
        for b, wb in zip(q, w):
            r = np.hypot(xx+a*dx/2, yy+b*dy/2)
            values += wa*wb*(.25j*k*k)*hankel1(0, k*r)*dx*dy/4
    if not np.isclose(dx, dy):
        raise ValueError("ON-002 registered square physical domain required")
    t, wt = roots_legendre(32)
    theta = (t+1)*np.pi/8
    R = dx/2/np.cos(theta)
    primitive = (R*hankel1(1, k*R)/k + 2j/(np.pi*k*k))
    values[n-1, n-1] = .25j*k*k*8*np.sum(wt*np.pi/8*primitive)
    pad = np.zeros((2*n, 2*n), complex)
    pad[np.ix_(offsets % (2*n), offsets % (2*n))] = values
    return pad


@dataclass
class AdaptedFrequency:
    model: object
    projected: object
    options: object
    contrast: float
    grid: int
    coefficients: torch.Tensor
    build_seconds: float

    def predict(self, occupancy=None):
        C, _ = external()
        b = self.coefficients if occupancy is None else occupancy
        chi = (self.contrast-1)*b
        u = C.collocation_forward_prop(self.projected, chi,
                torch.zeros_like(self.projected.uinc), self.options)
        residual = true_relative(C.collocation_a_forward(self.projected, chi, u),
                                 self.projected.uinc)
        pred = C.collocation_sensor_forward(self.model, self.projected, chi, u).diagonal()
        return pred, u, residual

    def objective_gradient(self, target, occupancy=None):
        C, _ = external()
        b = self.coefficients if occupancy is None else occupancy
        chi = (self.contrast-1)*b
        pred, u, forward_residual = self.predict(b)
        if not np.isfinite(forward_residual) or forward_residual > self.options.pcg_tol:
            raise RuntimeError(f"Forward true residual refuses update: {forward_residual:g}")
        z = torch.zeros_like(self.model.data)
        z.diagonal().copy_(pred-target)
        norm2 = torch.sum(abs(target)**2)
        z = z/norm2
        p = C.collocation_sensor_adjoint(self.model, self.projected, z)
        rhs = C._contrast_source_u_adjoint(self.projected, chi, p)
        v = C.collocation_backward_prop(self.projected, chi, rhs,
                torch.zeros_like(rhs), self.options)
        adjoint_residual = true_relative(C.collocation_a_adjoint(self.projected, chi, v), rhs)
        if not np.isfinite(adjoint_residual) or adjoint_residual > self.options.pcg_tol:
            raise RuntimeError(f"Adjoint true residual refuses update: {adjoint_residual:g}")
        grad = (self.contrast-1)*C._contrast_source_coeff_adjoint(
            self.projected, u, p+C._k_adjoint(self.projected, v))
        loss = .5*torch.sum(abs(pred-target)**2)/norm2
        return loss, grad, dict(forward_true_residual=forward_residual,
                                adjoint_true_residual=adjoint_residual)

    def render(self):
        C, _ = external()
        return C.render_collocation_contrast(self.model, self.projected, self.coefficients)


def true_relative(lhs, rhs):
    value = torch.linalg.vector_norm(lhs-rhs, dim=1)/torch.clamp(
        torch.linalg.vector_norm(rhs, dim=1), min=1e-30)
    return float(value.max().detach().cpu())


def build(problem, observation, *, pixels=128, centers=112, device="cuda", double=False):
    C, S = external()
    sync(device)
    started = perf_counter()
    rd, cd = (torch.float64, torch.complex128) if double else (torch.float32, torch.complex64)
    bounds = np.asarray(problem.bounds_m)
    dx, dy = (bounds[1]-bounds[0])/pixels
    x = bounds[0, 0]+(np.arange(pixels)+.5)*dx
    y = bounds[0, 1]+(np.arange(pixels)+.5)*dy
    xx, yy = np.meshgrid(x, y)
    points = np.stack([xx.ravel(), yy.ravel()], -1)
    origin = np.array([problem.origin_m.real, problem.origin_m.imag])
    sources = observation.acquisition.sources*problem.length_unit_m+origin
    receivers = observation.acquisition.receivers*problem.length_unit_m+origin
    k = complex(observation.wavenumber)/problem.length_unit_m
    def real(v):
        return torch.as_tensor(v, device=device, dtype=rd)
    def comp(v):
        return torch.as_tensor(v, device=device, dtype=cd)
    inc = .25j*observation.acquisition.strength*hankel1(0, k*np.linalg.norm(
        sources[:, None]-points[None, :], axis=-1))
    sensor = .25j*k*k*dx*dy*hankel1(0, k*np.linalg.norm(
        receivers[:, None]-points[None, :], axis=-1))
    empty = comp(np.empty((0, 0)))
    # Only measured diagonal pairs populate data and mask, even though the
    # reusable released sensor operator internally applies a shared row map.
    data = np.zeros((len(sources), len(receivers)), complex)
    np.fill_diagonal(data, observation.scattered)
    model = S.SyntheticScatteringModel(
        file_name="TG-002 adapted GauGal", frequency_ghz=observation.frequency_hz/1e9,
        wavelength=2*np.pi/k.real, kb=k, length=float(bounds[1,0]-bounds[0,0]),
        nx=pixels, ny=pixels, dx=dx, dy=dy, x=real(x), y=real(y), xx=real(xx), yy=real(yy),
        data=comp(data), receiver_mask=real(np.eye(len(sources))), uinc=comp(inc),
        nominal_truth=real(np.empty(0)), dense_g=empty, dense_h=comp(sensor),
        pixel_points=real(points), x_transmit=real(sources[:,0]), y_transmit=real(sources[:,1]),
        x_receive=real(receivers[:,0]), y_receive=real(receivers[:,1]),
        amp=observation.acquisition.strength,
        domain_kernel_fft=torch.fft.fft2(comp(physical_kernel(k, pixels, dx, dy))))
    options = C.CollocationOptions(collocation_grid_size=centers, collocation_sigma_scale=.8,
        collocation_preconditioner="jacobi", pcg_tol=1e-6, pcg_max_iter=200,
        collocation_chunk_size=64, collocation_contrast_mode="lumped-galerkin")
    projected = S.build_synthetic_galerkin_model(model, options)
    # Initial circle in coefficients: exact cell fraction at the centre lattice.
    # GauGal's normalized separable rendering provides the fixed smoothing.
    center = problem.origin_m+problem.length_unit_m*complex(problem.initial.coefficients[problem.initial.band])
    # TG prescribed initial geometry has radius 65 mm, verified by the driver.
    cx = np.linspace(x[0], x[-1], centers); cy = np.linspace(y[0], y[-1], centers)
    b = real(circle_fraction(cx, cy, cx[1]-cx[0], center, .065)).reshape(-1)
    sync(device)
    return AdaptedFrequency(model, projected, options, problem.contrast, pixels, b,
                            perf_counter()-started)


def versions():
    result = {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "torch")}
    result["gaugal"] = "0.1.0 (source checkout at " + PIN + ")"
    return result
