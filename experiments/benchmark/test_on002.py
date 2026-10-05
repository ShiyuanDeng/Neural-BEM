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
