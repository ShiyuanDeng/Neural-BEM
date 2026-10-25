"""Level penalty: speed-unevenness rows stacked under the B5 data residual (GU-001).

E = sum_{m != 0} |rho_m|^2 / rho_0^2, with rho the Fourier coefficients of
J^2 = |z'|^2 (band 2K). This coefficient form is exact; by Parseval it is the
mean of (J^2/<J^2> - 1)^2 over the parameter. The penalty adds lambda_J E to
the loss 0.5 ||r||^2 through the rows 2 sqrt(lambda_J) rho_m/rho_0, m = 1..2K
(real parts, then imaginary parts). Their derivative in the update coordinates
follows from d(J^2) = 2 Re(conj(z') dz'). lambda_J is a fixed fraction of the
data loss at stage entry, set once per stage by ``fit_stage``.
"""
from dataclasses import replace

import numpy as np

from .a1_geometry import real_product

FRACTION = .01  # lambda_J = FRACTION x data loss at stage entry; GU-001 tries no other value


def speed_squared(coefficients):
    """Exact coefficients of J^2 = |z'|^2, modes -2K..2K."""
    derivative = 1j*np.arange(-(len(coefficients)//2), len(coefficients)//2+1)*coefficients
    return real_product(derivative, derivative, 1)


def unevenness(coefficients):
    """E, the relative spread of squared speed."""
    rho = speed_squared(coefficients)
    centre = len(rho)//2
    return float(2*np.sum(np.abs(rho[centre+1:])**2)/rho[centre].real**2)


class LevelPenalty:
    def settings(self):
        return dict(name='level_penalty', fraction=FRACTION,
                    loss='data loss + lambda_J E, E = sum_{m!=0} |rho_m|^2/rho_0^2, rho = coefficients of |z\'|^2',
                    weight='lambda_J = fraction x data loss at stage entry, once per stage')

    def weight(self, data_loss):
        """lambda_J for a stage whose entry data loss is ``data_loss``."""
        return FRACTION*float(data_loss)

    def rows(self, coefficients, weight):
        rho = speed_squared(coefficients)
        centre = len(rho)//2
        q = 2*np.sqrt(weight)*rho[centre+1:]/rho[centre].real
        return np.concatenate((q.real, q.imag))

    def jacobian(self, coefficients, derivatives, weight):
        """Derivative of ``rows`` along each column of coefficient ``derivatives`` (2K+1, dim)."""
        modes = np.arange(-(len(coefficients)//2), len(coefficients)//2+1)
        derivative = 1j*modes*coefficients
        rho = speed_squared(coefficients)
        drho = 2*real_product((1j*modes[:, None]*derivatives).T, derivative[None, :], 1)  # (dim, 4K+1)
        centre = len(rho)//2
        rho0, drho0 = rho[centre].real, drho[:, centre].real
        dq = 2*np.sqrt(weight)*(drho[:, centre+1:]/rho0-np.outer(drho0, rho[centre+1:])/rho0**2)
        return np.concatenate((dq.real, dq.imag), axis=1).T

    def stacked(self, evaluation, weight):
        """The evaluation with the penalty rows under its data residual and lambda_J E in its loss."""
        q = self.rows(evaluation.curve.coefficients, weight)
        return replace(evaluation, residual=np.concatenate((evaluation.residual, q)),
                       loss=evaluation.loss+.5*float(q@q))

    def record(self, evaluation, weight):
        """Data loss and penalty reported separately, for the saved history."""
        E = unevenness(evaluation.curve.coefficients)
        return dict(data_loss=evaluation.loss-weight*E, penalty_loss=weight*E, penalty_weight=weight, level_E=E)
