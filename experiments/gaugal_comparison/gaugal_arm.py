"""GauGal on TG-002 (FW-001 operator check, GGB-002 reconstructions).

GauGal's own SingleTX models project the MoM pixel operators that generated
the data onto its Gaussian lattice. This adapter builds the same pixel
operators for TG-002 (pulse-basis Green kernel with the equal-area disk self
term, as in mom_esi, but with exact constants) and hands them to GauGal's
unchanged lattice builder, forward solver, gradient and TV denoiser.

Two things differ from GauGal's released driver, both agreed in the plan:
- one loss summed over frequencies, each weighted by 1/||d_f||^2, sharing one
  coefficient vector; each frequency keeps its own field warm starts;
- the susceptibility lower limit is LOWER = -0.9 instead of 0, so contrast 0.5
  (chi = -0.5) is representable. The limit is passed to GauGal's own TV
  denoiser; GauGal's files are not edited.

Data are divided by the source strength, so the incident field is i H0 / 4.
"""
from dataclasses import asdict
from time import perf_counter

import numpy as np
import torch
from scipy.special import hankel1

from gaugal.paper2d.collocation import (collocation_forward_prop, collocation_gradient,
                                        collocation_sensor_forward, render_collocation_contrast)
from gaugal.paper2d.reconstruct import paper_options
from gaugal.paper2d.settings import PaperCaseSettings, SolverControls
from gaugal.paper2d.solver import _lambda_value_for_iteration, _tv_max_iter_for_iteration
from gaugal.paper2d.synthetic import SyntheticScatteringModel, build_synthetic_galerkin_model
from gaugal.paper2d.tv import denoise_tv

from . import tg002_data as D

LOWER = -.9
PIXELS = 201                      # 1 mm quadrature grid for the Green integrals


def _green(k, r):
    return .25j*hankel1(0, k*r)


def build_model(case, frequency_index, pixels=PIXELS, device='cuda', dtype=torch.complex64):
    """GauGal's SyntheticScatteringModel for one TG-002 frequency."""
    real_dtype = torch.float32 if dtype == torch.complex64 else torch.float64
    x, y = D.pixel_grid(pixels)
    step = float(x[0, 1]-x[0, 0])
    area = step*step
    k = float(case.wavenumbers[frequency_index])
    n = pixels
    offsets = np.arange(1-n, n)
    dy, dx = np.meshgrid(offsets, offsets, indexing='ij')
    r = step*np.hypot(dx, dy)
    with np.errstate(all='ignore'):
        kernel = k*k*area*_green(k, np.where(r == 0, 1., r))
    a = np.sqrt(area/np.pi)
    kernel[n-1, n-1] = k*k*area*.25j*(2*hankel1(1, k*a)/(k*a)+4j/(k*k*area))
    pad = np.zeros((2*n, 2*n), complex)
    pad[dy % (2*n), dx % (2*n)] = kernel
    points = np.column_stack((x.reshape(-1), y.reshape(-1)))
    to = lambda a, t=dtype: torch.as_tensor(a, device=device, dtype=t)

    def distance(sensors):
        return np.hypot(sensors[:, 0, None]-points[None, :, 0], sensors[:, 1, None]-points[None, :, 1])

    uinc = _green(k, distance(case.sources))
    dense_h = k*k*area*_green(k, distance(case.receivers))
    pairs = len(case.sources)
    data = np.zeros((pairs, pairs), complex)
    data[np.arange(pairs), np.arange(pairs)] = case.observed[frequency_index]/case.strength
    x_unique, y_unique = np.unique(x), np.unique(y)
    return SyntheticScatteringModel(
        file_name=case.case_id, frequency_ghz=case.frequencies_hz[frequency_index]/1e9,
        wavelength=2*np.pi/k, kb=k, length=2*D.BOX_HALF_WIDTH_M, nx=n, ny=n, dx=step, dy=step,
        x=to(x_unique, real_dtype), y=to(y_unique, real_dtype), xx=to(x, real_dtype), yy=to(y, real_dtype),
        data=to(data), receiver_mask=torch.eye(pairs, device=device, dtype=torch.bool),
        uinc=to(uinc), nominal_truth=to(case.susceptibility*D.fill_fraction(case.boundary, x, y), real_dtype),
        dense_g=torch.empty((0, 0), device=device, dtype=dtype), dense_h=to(dense_h),
        pixel_points=to(points, real_dtype),
        x_transmit=to(case.sources[:, 0], real_dtype), y_transmit=to(case.sources[:, 1], real_dtype),
        x_receive=to(case.receivers[:, 0], real_dtype), y_receive=to(case.receivers[:, 1], real_dtype),
        domain_kernel_fft=torch.fft.fft2(to(pad)))


def settings(grid_size, *, sigma_scale=.35, lambda_scale=.5, step_size=1., contrast_max=15.,
             num_iter=300, tv_max_iter=100, lambda_schedule='linear-decay',
             lambda_final_fraction=.5, lambda_decay_start_fraction=.5):
    """GauGal case settings; defaults follow the released cylinder config except
    the step (data are normalised here) and the common susceptibility limit."""
    return PaperCaseSettings(lambda_scale=lambda_scale, sigma_scale=sigma_scale, step_size=step_size,
                             contrast_max=contrast_max, grid_size=grid_size, num_iter=num_iter,
                             tv_max_iter=tv_max_iter, lambda_schedule=lambda_schedule,
                             lambda_final_fraction=lambda_final_fraction,
                             lambda_decay_start_fraction=lambda_decay_start_fraction)


def lattice_truth(case, grid_size):
    """Lattice coefficients of the true object: chi times the cell area fraction."""
    x, y = D.pixel_grid(grid_size)
    return case.susceptibility*D.fill_fraction(case.boundary, x, y).reshape(-1)


def forward(case, frequency_index, grid_size, *, sigma_scale=.35, pixels=PIXELS, device='cuda',
            controls=SolverControls()):
    """FW-001: GauGal's forward prediction for the true object at one frequency."""
    opts = paper_options(settings(grid_size, sigma_scale=sigma_scale), controls)
    model = build_model(case, frequency_index, pixels, device)
    collocation = build_synthetic_galerkin_model(model, opts)
    coeff = torch.as_tensor(lattice_truth(case, grid_size), device=device, dtype=collocation.real_dtype)
    torch.cuda.synchronize()
    start = perf_counter()
    u = collocation_forward_prop(collocation, coeff, collocation.uinc, opts)
    predicted = collocation_sensor_forward(model, collocation, coeff, u)
    torch.cuda.synchronize()
    seconds = perf_counter()-start
    stats = collocation.linear_solve_stats[-1] if collocation.linear_solve_stats else {}
    paired = case.strength*torch.diagonal(predicted).detach().cpu().numpy()
    return paired, seconds, stats


def reconstruct(case, case_settings, *, frequencies=None, pixels=PIXELS, device='cuda',
                controls=SolverControls(), verbose=False):
    """GGB-002: one GauGal fit over several frequencies (FISTA + TV, shared coefficients)."""
    frequencies = list(range(len(case.frequencies_hz))) if frequencies is None else list(frequencies)
    opts = paper_options(case_settings, controls)
    start = perf_counter()
    models = [build_model(case, i, pixels, device) for i in frequencies]
    collocations = [build_synthetic_galerkin_model(m, opts) for m in models]
    torch.cuda.synchronize()
    build_seconds = perf_counter()-start
    weights = [1./float(torch.linalg.vector_norm(m.data))**2 for m in models]
    first = collocations[0]
    coeff = torch.zeros(first.num_basis, device=device, dtype=first.real_dtype)
    momentum, q = coeff.clone(), 1.
    fields = [c.uinc.clone() for c in collocations]
    adjoints = [torch.zeros_like(c.uinc) for c in collocations]
    # GauGal scales TV by half the data energy; the weighted energy is the frequency count.
    base_lam = opts.base_lambda_scale*.5*len(frequencies)*opts.lambda_scale
    step = float(opts.collocation_step_size)
    tv_p, tv_q = None, None
    history = []
    start = perf_counter()
    for it in range(1, opts.num_iter+1):
        with torch.no_grad():
            lam = _lambda_value_for_iteration(base_lam, opts, it)
            projected = torch.clamp(momentum, min=LOWER, max=opts.contrast_max)
            grad = torch.zeros_like(coeff)
            misfit = 0.
            for j, (m, c, w) in enumerate(zip(models, collocations, weights)):
                g, fields[j], adjoints[j], prediction = collocation_gradient(m, c, projected, fields[j],
                                                                             adjoints[j], opts)
                grad += w*g
                misfit += w*float(torch.linalg.vector_norm(prediction-m.data))**2
            candidate = projected-step*grad
            grid, tv_p, tv_q, _ = denoise_tv(candidate.reshape(first.grid_size, first.grid_size), lam*step,
                                             p0=tv_p, q0=tv_q, max_iter=_tv_max_iter_for_iteration(opts, it),
                                             tol=opts.tv_tol, lower_bound=LOWER, upper_bound=opts.contrast_max)
            following = grid.reshape(-1)
            q_next = .5*(1.+(1.+4.*q*q)**.5)
            momentum = following+opts.alpha*((q-1.)/q_next)*(following-coeff)
            q, coeff = q_next, following
        history.append(dict(iteration=it, weighted_misfit=misfit, lam=lam))
        if verbose and (it == 1 or it % 50 == 0):
            print(f'[{case.case_id}] iter {it}: relative misfit^2 mean {misfit/len(frequencies):.3e}', flush=True)
    torch.cuda.synchronize()
    optimize_seconds = perf_counter()-start
    final = torch.clamp(coeff, min=LOWER, max=opts.contrast_max)
    predictions = []
    with torch.no_grad():
        for m, c, u in zip(models, collocations, fields):
            u = collocation_forward_prop(c, final, u, opts)
            predictions.append(case.strength*torch.diagonal(collocation_sensor_forward(m, c, final, u)).cpu().numpy())
        image = render_collocation_contrast(models[0], first, final).cpu().numpy()
    return dict(coefficients=final.cpu().numpy(), image=image, predictions=np.array(predictions),
                frequencies=frequencies, history=history, build_seconds=build_seconds,
                optimize_seconds=optimize_seconds, settings=asdict(case_settings))
