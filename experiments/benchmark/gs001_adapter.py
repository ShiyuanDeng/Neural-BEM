"""GS-001: exact mass-preconditioned, unchanged ON-002 GauGal equations."""
from dataclasses import dataclass

import numpy as np
import torch

from . import on002_adapter as A


def bounded_tv_prox(image, alpha, iterations=100):
    """Bounded periodic isotropic-TV prox with a continuous alpha->0 limit.

    Maximize the TV dual over pointwise unit disks. For fixed dual p the
    bounded primal minimizer is clip(image-alpha D* p,0,1). The dual ascent
    direction D x has Lipschitz constant <=8 alpha, so 0.124/alpha
    is below its inverse Lipschitz constant.
    """
    if alpha < 0 or not np.isfinite(alpha):
        raise ValueError('Finite nonnegative TV step required')
    if alpha == 0:
        return image.clamp(0,1)
    px, py = torch.zeros_like(image), torch.zeros_like(image)
    for _ in range(iterations):
        adjoint = torch.roll(px,1,1)-px+torch.roll(py,1,0)-py
        value = (image-alpha*adjoint).clamp(0,1)
        dx, dy = torch.roll(value,-1,1)-value, torch.roll(value,-1,0)-value
        px = px+(.124/alpha)*dx
        py = py+(.124/alpha)*dy
        norm = torch.sqrt(px*px+py*py).clamp(min=1)
        px, py = px/norm, py/norm
    adjoint = torch.roll(px,1,1)-px+torch.roll(py,1,0)-py
    return (image-alpha*adjoint).clamp(0,1)


@dataclass
class Frequency(A.AdaptedFrequency):
    mass_y_inverse: torch.Tensor
    mass_x_inverse: torch.Tensor

    def mass_inverse(self, rhs):
        n = self.projected.grid_size
        grid = rhs.reshape(-1, n, n)
        return (self.mass_y_inverse @ grid @ self.mass_x_inverse.T).reshape_as(rhs)

    def solve(self, chi, rhs, *, adjoint):
        C, _ = A.external()
        p = self.projected
        norms = torch.linalg.vector_norm(rhs, dim=1, keepdim=True)
        norms = torch.where(norms > 0, norms, torch.ones_like(norms))
        op = C.collocation_a_adjoint if adjoint else C.collocation_a_forward
        value, info = C._bicgstab(lambda u: op(p, chi, u), rhs/norms,
            torch.zeros_like(rhs), tol=1e-7, max_iter=400,
            preconditioner=self.mass_inverse, return_info=True)
        value = value*norms
        actual = A.true_relative(op(p, chi, value), rhs)
        info.update(kind='adjoint' if adjoint else 'forward', true_residual=actual)
        p.linear_solve_stats.append(info)
        if not np.isfinite(actual) or actual > 1e-6:
            raise RuntimeError(f'{info["kind"]} true residual refuses update: {actual:g}')
        return value, actual

    def predict(self, occupancy=None):
        C, _ = A.external()
        b = self.coefficients if occupancy is None else occupancy
        chi = (self.contrast-1)*b
        u, residual = self.solve(chi, self.projected.uinc, adjoint=False)
        pred = C.collocation_sensor_forward(self.model, self.projected, chi, u).diagonal()
        return pred, u, residual

    def objective_gradient(self, target, occupancy=None):
        C, _ = A.external()
        b = self.coefficients if occupancy is None else occupancy
        chi = (self.contrast-1)*b
        pred, u, forward_residual = self.predict(b)
        z = torch.zeros_like(self.model.data)
        norm2 = torch.sum(abs(target)**2)
        z.diagonal().copy_((pred-target)/norm2)
        p = C.collocation_sensor_adjoint(self.model, self.projected, z)
        rhs = C._contrast_source_u_adjoint(self.projected, chi, p)
        v, adjoint_residual = self.solve(chi, rhs, adjoint=True)
        gradient = (self.contrast-1)*C._contrast_source_coeff_adjoint(
            self.projected, u, p+C._k_adjoint(self.projected, v))
        return .5*torch.sum(abs(pred-target)**2)/norm2, gradient, dict(
            forward_true_residual=forward_residual, adjoint_true_residual=adjoint_residual)


def build(problem, observation, **kwargs):
    f = A.build(problem, observation, double=True, **kwargs)
    p = f.projected
    by, bx = p.basis_y_weights, p.basis_x_weights
    # The normalized testing mass is exactly Gy (x) Gx. Invert the small
    # one-dimensional Gram matrices, preserving the original equations.
    gy, gx = by.T @ by, bx.T @ bx
    result = Frequency(**f.__dict__, mass_y_inverse=torch.linalg.inv(gy),
                       mass_x_inverse=torch.linalg.inv(gx))
    result.mass_condition = [float(torch.linalg.cond(g).cpu()) for g in (gy, gx)]
    return result
