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
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from time import perf_counter

import numpy as np
import torch
from scipy.special import hankel1

from gaugal.paper2d import collocation as operators
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


def prepare_direct(collocation):
    """Project the Green matrix once using the original pixel FFT in column blocks."""
    n = collocation.num_basis
    green = torch.empty((n, n), dtype=collocation.dtype, device=collocation.device)
    for start in range(0, n, 64):
        end = min(start + 64, n)
        columns = torch.zeros((end - start, n), dtype=collocation.dtype, device=collocation.device)
        columns[:, start:end].fill_diagonal_(1)
        green[:, start:end] = operators._k_forward(collocation, columns).T
    by, bx = collocation.basis_y_weights, collocation.basis_x_weights
    mass = torch.kron((by.T @ by).contiguous(), (bx.T @ bx).contiguous())
    collocation.mass_matrix = collocation.domain_cell_area * mass
    collocation.k_matrix = green


class SolveResidualError(ArithmeticError):
    """A checked forward, adjoint or endpoint equation failed its tolerance."""


class StageDivergence(ArithmeticError):
    """A continuation attempt violated its mismatch or finiteness limit."""


@dataclass
class StageAttempt:
    iteration: int = 0
    first_mismatch: float | None = None
    mismatch: float | None = None

    def check(self, value):
        self.mismatch = value
        if not np.isfinite(value):
            raise StageDivergence('nonfinite weighted mismatch')
        if self.first_mismatch is None:
            self.first_mismatch = value
        elif value > 2 * self.first_mismatch:
            raise StageDivergence('weighted mismatch exceeded twice its stage start')


def check_direct_solve(collocation, applied, rhs, kind, tolerance):
    """Check the true equation with the original pixel operator, for every source."""
    norms = torch.linalg.vector_norm(rhs, dim=1)
    errors = torch.linalg.vector_norm(applied - rhs, dim=1)
    relative = float(torch.max(errors / norms.clamp_min(torch.finfo(norms.dtype).tiny)))
    collocation.linear_solve_stats.append(dict(kind=kind, final_rel=relative, converged=relative <= tolerance))
    if not np.isfinite(relative) or relative > tolerance:
        raise SolveResidualError(f'{kind} solve residual {relative:g} exceeds {tolerance:g}')


def checked_gradient(model, collocation, coeff, u_warm, v_warm, opts):
    gradient, u, v, prediction = collocation_gradient(model, collocation, coeff, u_warm, v_warm, opts)
    applied = operators.collocation_a_forward(collocation, coeff, u)
    check_direct_solve(collocation, applied, collocation.uinc, 'forward', opts.pcg_tol)
    sensor_rhs = operators.collocation_sensor_adjoint(model, collocation, prediction - model.data)
    rhs = operators._contrast_source_u_adjoint(collocation, coeff, sensor_rhs)
    applied = operators.collocation_a_adjoint(collocation, coeff, v)
    check_direct_solve(collocation, applied, rhs, 'adjoint', opts.pcg_tol)
    return gradient, u, v, prediction


def reconstruct(case, case_settings, *, frequencies=None, pixels=PIXELS, device='cuda',
                controls=SolverControls(), verbose=False, max_seconds=None, checkpoint=None, convergence=None,
                initial_coefficients=None, operator_cache=None, stage_attempt=None):
    """GGB-002: one GauGal fit over several frequencies (FISTA + TV, shared coefficients)."""
    frequencies = list(range(len(case.frequencies_hz))) if frequencies is None else list(frequencies)
    opts = paper_options(case_settings, controls)
    start = perf_counter()
    if operator_cache is None:
        models = [build_model(case, i, pixels, device) for i in frequencies]
        collocations = [build_synthetic_galerkin_model(m, opts) for m in models]
    else:
        # Cache only fixed operators. Each stage starts with fresh fields,
        # momentum, TV dual variables and solve records.
        for i in frequencies:
            if i not in operator_cache:
                model = build_model(case, i, pixels, device)
                collocation = build_synthetic_galerkin_model(model, opts)
                prepare_direct(collocation)
                operator_cache[i] = (model, collocation)
        models, collocations = zip(*(operator_cache[i] for i in frequencies))
        for c in collocations:
            c.linear_solve_stats = []
    gradient = collocation_gradient
    tv_opts = opts
    if convergence:
        if operator_cache is None:
            for c in collocations:
                prepare_direct(c)
        opts = replace(opts, collocation_linear_solver='direct')
        tv_opts = replace(opts, num_iter=convergence['tv_schedule_iterations'])
        gradient = checked_gradient
    torch.cuda.synchronize()
    build_seconds = perf_counter()-start
    weights = [1./float(torch.linalg.vector_norm(m.data))**2 for m in models]
    first = collocations[0]
    coeff = torch.zeros(first.num_basis, device=device, dtype=first.real_dtype)
    if initial_coefficients is not None:
        coeff = torch.as_tensor(initial_coefficients, device=device, dtype=first.real_dtype)
        if coeff.shape != (first.num_basis,) or not bool(torch.isfinite(coeff).all()):
            raise ValueError('Invalid starting coefficient vector')
    momentum, q = coeff.clone(), 1.
    fields = [c.uinc.clone() for c in collocations]
    adjoints = [torch.zeros_like(c.uinc) for c in collocations]
    # GauGal scales TV by half the data energy; the weighted energy is the frequency count.
    base_lam = opts.base_lambda_scale*.5*len(frequencies)*opts.lambda_scale
    step = float(opts.collocation_step_size)
    tv_p, tv_q = None, None
    history = []
    start = perf_counter()
    stop_reason = 'iteration_limit'
    for it in range(1, opts.num_iter+1):
        if stage_attempt is not None:
            stage_attempt.iteration = it
            stage_attempt.mismatch = None
        with torch.no_grad():
            lam = _lambda_value_for_iteration(base_lam, tv_opts, it)
            projected = torch.clamp(momentum, min=LOWER, max=opts.contrast_max)
            grad = torch.zeros_like(coeff)
            misfit = 0.
            evaluated_predictions = []
            for j, (m, c, w) in enumerate(zip(models, collocations, weights)):
                g, fields[j], adjoints[j], prediction = gradient(m, c, projected, fields[j],
                                                                 adjoints[j], opts)
                grad += w*g
                misfit += w*float(torch.linalg.vector_norm(prediction-m.data))**2
                evaluated_predictions.append(case.strength*torch.diagonal(prediction).cpu().numpy())
            if stage_attempt is not None:
                stage_attempt.check(misfit)
            if not np.isfinite(misfit) or not bool(torch.isfinite(grad).all()):
                if stage_attempt is not None:
                    raise StageDivergence('nonfinite gradient')
                stop_reason = 'nonfinite_gradient'
                break
            if checkpoint is not None and (it == 1 or it % 10 == 0):
                checkpoint(dict(coefficients=projected.cpu().numpy(),
                    image=render_collocation_contrast(models[0], first, projected).cpu().numpy(),
                    predictions=np.array(evaluated_predictions), frequencies=frequencies,
                    history=history+[dict(iteration=it, weighted_misfit=misfit, lam=lam)],
                    build_seconds=build_seconds, optimize_seconds=perf_counter()-start,
                    settings=asdict(case_settings), iterations=it, stop_reason='running'))
            if convergence and it >= tv_opts.num_iter + convergence['window_steps']:
                recent = [h['weighted_misfit'] for h in history[-convergence['window_steps']:]] + [misfit]
                spread = max(recent)-min(recent)
                if spread < convergence['relative_range']*recent[0] or max(recent) == 0:
                    history.append(dict(iteration=it, weighted_misfit=misfit, lam=lam))
                    coeff = projected
                    stop_reason = 'mismatch_plateau'
                    break
            candidate = projected-step*grad
            grid, tv_p, tv_q, _ = denoise_tv(candidate.reshape(first.grid_size, first.grid_size), lam*step,
                                             p0=tv_p, q0=tv_q, max_iter=_tv_max_iter_for_iteration(opts, it),
                                             tol=opts.tv_tol, lower_bound=LOWER, upper_bound=opts.contrast_max)
            following = grid.reshape(-1)
            if not bool(torch.isfinite(following).all()):
                if stage_attempt is not None:
                    raise StageDivergence('nonfinite update')
                stop_reason = 'nonfinite_update'
                break
            q_next = .5*(1.+(1.+4.*q*q)**.5)
            momentum = following+opts.alpha*((q-1.)/q_next)*(following-coeff)
            q, coeff = q_next, following
        history.append(dict(iteration=it, weighted_misfit=misfit, lam=lam))
        if verbose and (it == 1 or it % 10 == 0):
            print(f'[{case.case_id}] iter {it}: relative misfit^2 mean {misfit/len(frequencies):.3e}', flush=True)
        if verbose and convergence and it == 20:
            print(f'First 20 iterations: {(perf_counter()-start)/20:.5f} s/iteration', flush=True)
        if max_seconds is not None and perf_counter()-start >= max_seconds:
            stop_reason = 'time_limit'
            break
    torch.cuda.synchronize()
    optimize_seconds = perf_counter()-start
    final = torch.clamp(coeff, min=LOWER, max=opts.contrast_max)
    predictions = []
    if stage_attempt is not None:
        stage_attempt.mismatch = None  # The endpoint mismatch is known only after every solve.
    with torch.no_grad():
        for m, c, u in zip(models, collocations, fields):
            u = collocation_forward_prop(c, final, u, opts)
            if convergence:
                check_direct_solve(c, operators.collocation_a_forward(c, final, u), c.uinc, 'endpoint', opts.pcg_tol)
            predictions.append(case.strength*torch.diagonal(collocation_sensor_forward(m, c, final, u)).cpu().numpy())
        image = render_collocation_contrast(models[0], first, final).cpu().numpy()
    return dict(coefficients=final.cpu().numpy(), image=image, predictions=np.array(predictions),
                **(dict(solve_residuals=[c.linear_solve_stats for c in collocations]) if convergence else {}),
                frequencies=frequencies, history=history, build_seconds=build_seconds,
                optimize_seconds=optimize_seconds, settings=asdict(case_settings),
                iterations=len(history), stop_reason=stop_reason,
                linear_solves=[dict(frequency_hz=float(case.frequencies_hz[i]),
                    calls=len(c.linear_solve_stats),
                    unconverged=sum(not bool(s.get('converged', 0)) for s in c.linear_solve_stats),
                    max_final_relative=max((s.get('final_rel', 0.) for s in c.linear_solve_stats), default=0.))
                    for i, c in zip(frequencies, collocations)])


def reconstruct_continuation(case, case_settings, counts, convergence, checkpoint, stage_finished):
    """Transfer accepted coefficients and retain step reductions across stages."""
    cache = {}
    stages, history, linear_solves, residual_arrays = [], [], [], {}
    build_seconds = optimize_seconds = 0.
    rejected_iterations = halvings = 0
    max_halvings = 4
    initial = None
    fit = None
    for count in counts:
        rejected = []
        stage = dict(frequency_count=count, frequencies_hz=case.frequencies_hz[:count].tolist(),
                     restarts=0, rejected_attempts=rejected)
        while True:
            attempt = StageAttempt()
            step = case_settings.step_size
            stage['step_size'] = step
            stage.pop('next_step_size', None)
            started = perf_counter()
            try:
                candidate = reconstruct(case, case_settings, frequencies=range(count), convergence=convergence,
                                        checkpoint=checkpoint, verbose=True, initial_coefficients=initial,
                                        operator_cache=cache, stage_attempt=attempt)
                residual = D.relative_error(candidate['predictions'], case.observed[:count])
                final_mismatch = float(np.sum(residual**2))
                attempt.check(final_mismatch)
                break
            except (StageDivergence, SolveResidualError, torch.linalg.LinAlgError) as exc:
                if attempt.iteration == 0:
                    raise  # Setup errors cannot be corrected by a smaller optimization step.
                elapsed = perf_counter() - started
                optimize_seconds += elapsed
                rejected_iterations += attempt.iteration
                rejected.append(dict(step_size=step, iteration=attempt.iteration, reason=str(exc),
                                     initial_weighted_mismatch=attempt.first_mismatch,
                                     weighted_mismatch=attempt.mismatch, seconds=elapsed))
                # A failed solve can leave some frequencies with one fewer evaluation.
                for j in range(count):
                    stats = cache[j][1].linear_solve_stats
                    linear_solves.append(dict(frequency_hz=float(case.frequencies_hz[j]), frequency_count=count,
                                              rejected_attempt=len(rejected), calls=len(stats),
                                              unconverged=sum(not s['converged'] for s in stats),
                                              max_final_relative=max((s['final_rel'] for s in stats), default=0.)))
                    for kind in ('forward', 'adjoint', 'endpoint'):
                        key = f'stage_{count}_rejected_{len(rejected)}_freq_{j}_{kind}_relative_residual'
                        residual_arrays[key] = np.asarray([s['final_rel'] for s in stats if s['kind'] == kind])
                exhausted = halvings == max_halvings
                stage.update(iterations=attempt.iteration, hit_cap=False,
                             initial_weighted_mismatch=attempt.first_mismatch, final_weighted_mismatch=attempt.mismatch,
                             stop_reason='restart_limit' if exhausted else 'restarting')
                if not exhausted:
                    halvings += 1
                    stage['restarts'] += 1
                    case_settings = replace(case_settings, step_size=step / 2)
                    stage['next_step_size'] = case_settings.step_size
                stage_finished(stages + [stage])
                if exhausted:
                    break

        if stage.get('stop_reason') == 'restart_limit':
            stages.append(stage)
            if fit is None:
                # No accepted stage exists. Preserve failed work without reporting a rejected image.
                fit = dict(frequencies=[], history=[], settings=asdict(case_settings))
            fit['stop_reason'] = 'restart_limit'
            break

        fit = candidate
        initial = fit['coefficients']
        stage.update(iterations=fit['iterations'], stop_reason=fit['stop_reason'],
                     hit_cap=fit['stop_reason'] == 'iteration_limit',
                     initial_weighted_mismatch=fit['history'][0]['weighted_misfit'] if fit['history'] else None,
                     final_weighted_mismatch=final_mismatch, residual=residual.tolist(),
                     setup_seconds=fit['build_seconds'], fit_seconds=fit['optimize_seconds'])
        stages.append(stage)
        stage_finished(stages)
        build_seconds += fit['build_seconds']
        optimize_seconds += fit['optimize_seconds']
        history.extend(dict(row, frequency_count=count) for row in fit['history'])
        linear_solves.extend(dict(row, frequency_count=count) for row in fit['linear_solves'])
        for kind in ('forward', 'adjoint', 'endpoint'):
            residual_arrays[f'stage_{count}_{kind}_relative_residual'] = np.asarray([
                [s['final_rel'] for s in solves if s['kind'] == kind] for solves in fit['solve_residuals']])
        if fit['stop_reason'] not in ('iteration_limit', 'mismatch_plateau'):
            break
    fit.pop('solve_residuals', None)
    fit.update(stages=stages, history=history, linear_solves=linear_solves, solve_arrays=residual_arrays,
               iterations=len(history)+rejected_iterations, build_seconds=build_seconds, optimize_seconds=optimize_seconds)
    return fit
