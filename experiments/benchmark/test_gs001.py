"""Independent dense controls for the GS-001 Gaussian mass preconditioner."""
import numpy as np
import pytest
import torch

from . import campaign as B
from . import gs001_adapter as G
from . import on002_adapter as A


def test_native_tv_has_nonzero_change_at_small_step():
    A.external()
    from gaugal.paper2d.tv import denoise_tv
    image = torch.zeros((16,16), dtype=torch.float64)
    image[4:12,4:12] = 1
    alpha = 1e-8
    actual, _, _, _ = denoise_tv(image,alpha,lower_bound=0,upper_bound=1)
    # A true bounded isotropic TV proximal step changes bounded y by at most
    # 4 alpha. Preserve the released finite-iteration failure as evidence.
    assert float(abs(actual-image).max()) > .01
    assert float(abs(actual-image).max()) > 4*alpha


@pytest.mark.parametrize('alpha', [0., 1e-8, .01, .1])
def test_bounded_tv_prox_identity_bounds_and_proximal_energy(alpha):
    from .gs001 import tv
    image = torch.rand((16,16),dtype=torch.float64,
                       generator=torch.Generator().manual_seed(1))
    result = G.bounded_tv_prox(image,alpha)
    assert result.min() >= 0 and result.max() <= 1
    assert float(abs(result-image).max()) <= 4*alpha+1e-15
    before = alpha*image.numel()*tv(image)
    after = .5*torch.sum((result-image)**2)+alpha*image.numel()*tv(result)
    assert after <= before+1e-12
    if alpha == 0:
        torch.testing.assert_close(result,image,rtol=0,atol=0)


@pytest.mark.parametrize('contrast', [.5, 4., 13.3])
def test_mass_preconditioned_solve_and_complete_gradient(contrast):
    torch.set_num_threads(1)
    p = B.problem(f'circle__c{contrast:g}')
    f = G.build(p, p.real[2], pixels=12, centers=6, device='cpu')
    C, _ = A.external()
    n = f.projected.num_basis
    identity = torch.eye(n, dtype=torch.complex128)
    chi = (contrast-1)*f.coefficients
    matrix = C.collocation_a_forward(f.projected, chi, identity).T
    mass = C._mass_forward(f.projected, identity).T
    torch.testing.assert_close(f.mass_inverse(identity) @ mass.T, identity,
                               rtol=1e-7, atol=1e-7)
    direct = torch.linalg.solve(matrix, f.projected.uinc.T).T
    predicted, iterative, residual = f.predict()
    assert residual <= 1e-6
    torch.testing.assert_close(iterative, direct, rtol=2e-5, atol=2e-11)
    target = torch.as_tensor(p.real[2].scattered.copy(), dtype=torch.complex128)
    loss, grad, receipt = f.objective_gradient(target)
    direction = torch.cos(torch.arange(n, dtype=torch.float64))
    epsilon = 1e-4
    values = []
    for sign in (-1, 1):
        material = (contrast-1)*(f.coefficients+sign*epsilon*direction)
        m = C.collocation_a_forward(f.projected, material, identity).T
        field = torch.linalg.solve(m, f.projected.uinc.T).T
        prediction = C.collocation_sensor_forward(f.model, f.projected, material, field).diagonal()
        values.append(.5*torch.sum(abs(prediction-target)**2)/torch.sum(abs(target)**2))
    fd = (values[1]-values[0])/(2*epsilon)
    torch.testing.assert_close(torch.sum(grad*direction), fd, rtol=1e-3, atol=1e-7)
    assert receipt['adjoint_true_residual'] <= 1e-6
