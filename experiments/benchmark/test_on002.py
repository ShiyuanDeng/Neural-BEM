"""Independent controls for the ON-002 external adapter boundary."""
import numpy as np
import pytest
import torch
from scipy.integrate import dblquad
from scipy.special import hankel1
from . import on002_adapter as A


def test_disk_cell_area_conserves_prescribed_start():
    x=np.linspace(.2,.8,64,endpoint=False)+.6/128
    b=A.circle_fraction(x,x,.6/64,.5+.5j,.065)
    assert b.min()>=0 and b.max()<=1
    assert abs(b.sum()*(.6/64)**2-np.pi*.065**2)<1e-10


@pytest.mark.parametrize("k", [15.,15.+3.75j])
def test_kernel_cell_integral_has_outgoing_sign_and_area_once(k):
    h=.0125
    kernel=A.physical_kernel(k,4,h,h)
    # Independent Cartesian integration for one nonsingular neighbor cell.
    def value(y,x):
        return .25j*k*k*hankel1(0,k*np.hypot(2*h-x,h-y))
    exact=complex(dblquad(lambda y,x:value(y,x).real,-h/2,h/2,
                         lambda x:-h/2,lambda x:h/2,epsabs=1e-12)[0],
                  dblquad(lambda y,x:value(y,x).imag,-h/2,h/2,
                         lambda x:-h/2,lambda x:h/2,epsabs=1e-12)[0])
    assert abs(kernel[1,2]-exact)/abs(exact)<1e-6
    assert np.isfinite(kernel[0,0])
    # Positive imaginary self term of outgoing real-frequency Green function.
    if np.isreal(k):
        assert kernel[0,0].imag>0


def test_external_sensor_mask_discards_all_cross_pairs():
    C,_=A.external()
    from types import SimpleNamespace
    dtype=torch.complex128
    r=torch.tensor([[1+2j,3j],[4-1j,2]],dtype=dtype)
    model=SimpleNamespace(receiver_mask=torch.eye(2,dtype=torch.float64))
    projected=SimpleNamespace(r_matrix=r,r_harmonic_gamma=None,r_harmonic_basis=None,
                              profile=False)
    u=torch.tensor([[2+1j,3],[4,5-2j]],dtype=dtype)
    chi=torch.tensor([-.5,-.25],dtype=torch.float64)
    pred=C.collocation_sensor_forward(model,projected,chi,u)
    assert pred[0,1]==0 and pred[1,0]==0
    z=torch.tensor([[1+1j,1e9],[1e9,2-1j]],dtype=dtype)
    adj=C.collocation_sensor_adjoint(model,projected,z)
    lhs=torch.sum(torch.conj(z)*pred)
    rhs=torch.sum(torch.conj(adj)*chi[None,:]*u)
    torch.testing.assert_close(lhs,rhs)


@pytest.mark.parametrize("contrast", [.5, 4., 13.3])
def test_normalized_fft_system_matches_dense_physical_projection(contrast):
    """Independent dense Galerkin assembly, direct solve and complete derivative."""
    from . import campaign as B
    C, _ = A.external()
    torch.set_num_threads(1)
    problem = B.problem(f"circle__c{contrast:g}")
    f = A.build(problem, problem.damped[0], pixels=8, centers=4,
                device="cpu", double=True)
    p = f.projected
    basis = torch.kron(p.basis_y_weights.contiguous(), p.basis_x_weights.contiguous())
    n = f.grid
    iy, ix = torch.meshgrid(torch.arange(n), torch.arange(n), indexing="ij")
    kernel = torch.fft.ifft2(f.model.domain_kernel_fft)
    green = kernel[(iy.flatten()[:,None]-iy.flatten()[None,:]) % (2*n),
                   (ix.flatten()[:,None]-ix.flatten()[None,:]) % (2*n)]
    chi = (contrast-1)*f.coefficients
    # Explicit testing-area factors: divide both physical matrix and RHS.
    area = f.model.cell_area
    dense = area*(basis.T@basis - (basis.T@green@basis)*chi[None,:])
    rhs = area*f.model.uinc@basis
    random = torch.randn((2, p.num_basis), dtype=p.dtype,
                         generator=torch.Generator().manual_seed(2002))
    torch.testing.assert_close(C.collocation_a_forward(p,chi,random),
                               random@(dense/area).T, rtol=1e-12, atol=1e-12)
    torch.testing.assert_close(p.uinc, rhs/area, rtol=1e-12, atol=1e-12)
    direct = torch.linalg.solve(dense, rhs.T).T
    pred, iterative, residual = f.predict()
    assert residual <= 1e-6
    torch.testing.assert_close(iterative, direct, rtol=2e-5, atol=2e-6)
    expected = (chi[None,:]*direct)@(f.model.dense_h@basis).T
    torch.testing.assert_close(pred, expected.diagonal(), rtol=2e-5, atol=2e-7)
    target = torch.as_tensor(problem.damped[0].scattered.copy(), dtype=p.dtype)
    loss, grad, receipt = f.objective_gradient(target)
    direction = torch.sin(torch.arange(p.num_basis,dtype=p.real_dtype))
    epsilon = 1e-3
    values = []
    for sign in (-1, 1):
        trial = f.coefficients+sign*epsilon*direction
        trial_chi = (contrast-1)*trial
        matrix = basis.T@basis-(basis.T@green@basis)*trial_chi[None,:]
        field = torch.linalg.solve(matrix,p.uinc.T).T
        prediction = ((trial_chi[None,:]*field)@(f.model.dense_h@basis).T).diagonal()
        values.append(.5*torch.sum(abs(prediction-target)**2)/torch.sum(abs(target)**2))
    fd = (values[1]-values[0])/(2*epsilon)
    analytic = torch.sum(grad*direction)
    torch.testing.assert_close(analytic, fd, rtol=1e-3, atol=1e-8)
    assert receipt["adjoint_true_residual"] <= 1e-6
