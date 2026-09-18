"""Independent analytic and quadrature checks, before literature campaigns."""
import numpy as np
import pytest
from scipy.special import hankel1, jv

from .scalar import (ellipse_coefficients, ellipse_log_density, kernel_matrix,
                     literature_mask, convolution_diagonal, direct_log_matrix)


def test_published_double_fourier_index_is_input_sign_reversed():
    n, mu = 17, 1.2
    modes = np.arange(1-n, n)
    k, l = np.meshgrid(modes, modes, indexing='ij')
    published = (1+(k+l)**2)**mu * np.minimum(1+k*k, 1+l*l) <= n*n
    actual = literature_mask(n-1, mu)
    assert np.array_equal(actual, published[:, ::-1])
    assert np.all(actual.diagonal())
    assert actual[-1, -1] and not actual[-1, 0]


def test_restricted_larger_mask_is_exact_central_submatrix():
    big=literature_mask(80,1.1)
    small=literature_mask(20,1.1,mask_n=81)
    assert np.array_equal(small,big[60:101,60:101])


def test_principal_log_sign_against_circle_large_mode_asymptotic():
    from types import SimpleNamespace
    from experiments.modal_muller_research.coefficient_operator import LaurentGeometry,CoefficientGeometry
    from .transmission import principal_log
    g=LaurentGeometry.circle()
    a,_=CoefficientGeometry(g,64).assemble(60.,43.,40,28)
    case=SimpleNamespace(geometry=g,cutoff=40,ko=60.,ki=43.,a=a)
    principal=principal_log(case)
    # The diagonal T difference has this principal 1/|m| symbol; lower-order
    # terms vanish as |m| grows. Independent physical circle assembly above.
    index=80
    assert abs(principal[81+index,index]/a[81+index,index]-1)<.01


@pytest.mark.parametrize('radius,wave', [(1., .8), (.7, 3.)])
def test_circle_against_exact_single_layer_eigenvalues(radius, wave):
    p, s = ellipse_coefficients(radius, radius, wave, 128)
    matrix = kernel_matrix(p, s, 20)
    modes = np.arange(-20, 21)
    exact = .5j*np.pi*jv(modes, wave*radius)*hankel1(modes, wave*radius)
    assert np.max(np.abs(matrix-np.diag(exact))) < 2e-13


def test_contraction_beyond_coefficient_window_against_literal_formula():
    rng = np.random.default_rng(982)
    p = rng.normal(size=(9, 9))+1j*rng.normal(size=(9, 9))
    s = rng.normal(size=(9, 9))+1j*rng.normal(size=(9, 9))
    actual = kernel_matrix(p, s, 11)
    expected = direct_log_matrix(p, s, 11)
    assert np.max(np.abs(actual-expected)) < 5e-13


def test_analytic_density_coefficients_against_independent_samples():
    modes = np.arange(-70, 71)
    coeff = ellipse_log_density(modes)
    theta = 2*np.pi*(np.arange(2048)+.37)/2048
    actual = np.exp(1j*theta[:, None]*modes) @ coeff / np.sqrt(2*np.pi)
    exact = np.log(np.abs(2*np.cos(theta)+1j*np.sin(theta)-1.9))
    assert np.max(np.abs(actual-exact)) < 6e-5
    # A larger mode window must resolve the near-boundary logarithm.
    modes = np.arange(-320, 321)
    actual = np.exp(1j*theta[:, None]*modes) @ ellipse_log_density(modes)/np.sqrt(2*np.pi)
    assert np.max(np.abs(actual-exact)) < 3e-14


def test_diagonal_convolution_normalization():
    # Integral kernel -(log|2 sin(t/2)| - 1)/(2*pi).
    assert np.array_equal(convolution_diagonal(2), [.25, .5, 1., .5, .25])


def test_smooth_ellipse_quadrature_refinement():
    p, s = ellipse_coefficients(2., 1., 3., 128)
    p2, s2 = ellipse_coefficients(2., 1., 3., 256)
    a = kernel_matrix(p, s, 40)
    a2 = kernel_matrix(p2, s2, 40)
    assert np.linalg.norm(a-a2)/np.linalg.norm(a2) < 1e-12


def test_ellipse_against_independent_physical_kress_single_layer():
    from periodic_kress import kress_log_weight_matrix
    count, cutoff, wave = 256, 24, 3.
    theta = 2*np.pi*np.arange(count)/count
    z = 2*np.cos(theta)+1j*np.sin(theta)
    r = np.abs(z[:,None]-z[None,:])
    delta = theta[:,None]-theta[None,:]
    diag = np.eye(count,dtype=bool)
    logpart = -jv(0,wave*r)/(4*np.pi)
    smooth = .25j*hankel1(0,wave*np.where(diag,1.,r))
    smooth -= logpart*np.log(np.where(diag,1.,4*np.sin(delta/2)**2))
    speed = np.sqrt(4*np.sin(theta)**2+np.cos(theta)**2)
    smooth[diag] = .25j-(np.euler_gamma+np.log(wave*speed/2))/(2*np.pi)
    nodal = logpart*kress_log_weight_matrix(count)+(2*np.pi/count)*smooth
    basis = np.exp(1j*theta[:,None]*np.arange(-cutoff,cutoff+1))/np.sqrt(count)
    reference = basis.conj().T @ nodal @ basis
    p,s = ellipse_coefficients(2.,1.,wave,128)
    actual = kernel_matrix(p,s,cutoff)
    assert np.linalg.norm(actual-reference)/np.linalg.norm(reference) < 2e-13


def test_principal_symbol_uses_physical_flux_diagonal_and_shape_tangent():
    from types import SimpleNamespace
    from experiments.modal_muller_research.coefficient_operator import LaurentGeometry
    from experiments.laurent_compression.adapters import moved_geometry
    from .transmission import principal_log, speed_squared_coefficients
    g=LaurentGeometry.star()
    k=16
    case=SimpleNamespace(geometry=g,cutoff=k,ko=60.,ki=43.,a=np.zeros((4*k+2,4*k+2),complex))
    dz={2:.6+.3j,-2:-.2+.1j}
    h=1e-5
    sides=[SimpleNamespace(**dict(case.__dict__,geometry=moved_geometry(g,dz,sign*h))) for sign in [1,-1]]
    fd=(principal_log(sides[0])-principal_log(sides[1]))/(2*h)
    actual=principal_log(case,dz)
    assert np.linalg.norm(fd-actual)/np.linalg.norm(actual)<1e-9
    theta=2*np.pi*(np.arange(57)+.2)/57
    speed2=sum(v*np.exp(1j*j*theta) for j,v in speed_squared_coefficients(g.coefficients).items())
    tangent=sum(1j*j*v*np.exp(1j*j*theta) for j,v in g.coefficients.items())
    assert np.max(np.abs(speed2-np.abs(tangent)**2))<1e-13
