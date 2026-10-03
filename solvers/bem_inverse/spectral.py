"""NU-003 spectral increment map: the CI-001 trial map with its spline resampler replaced by eq. 9.

CI-001 (``geometry.ProjectedUpdate``):  T_z(a) = z + P_K[A(z + h n) - A(z)], where A
samples the moved curve, inverts its arclength with a cubic spline and interpolates
it with a second spline at uniform arclength. NU-003 keeps every other step
(normal move h(alpha) n on the uniform theta grid, FFT fit, finite-difference
columns, coarse/fine refinement check, validation) and replaces A by the
change-of-variables quadrature of the proposal's eq. 9,

    R(w)_k = <w(theta) alpha'(theta) e^{-i k alpha(theta)}>_0,   |k| <= K,

evaluated on the same uniform grid. No spline, interpolation or inversion theta(alpha)
remains; grids serve as FFT and quadrature engines. This is spline-free, not
sample-free or exact nonlinear convolution. The increment form keeps the first-order cancellation of
the arclength crop that NU-002 found necessary at the damped bands.

Campaigns and diagnostics remain under experiments.cleaned_interface.
"""
import numpy as np
from .continuation.geometry import FourierCurve, arclength_angles, normal_basis
from .continuation.updates import UpdateRefused
from .continuation.validation import self_intersections
from .geometry import ProjectedUpdate


CONSTRUCTION = 'z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial'


def arclength_quadrature(moved, nodes, band):
    """Coefficients |k| <= band of the arclength curve of ``moved`` by eq. 9 on its uniform nodes.

    Returns (coefficients, crop error): the error is max |P_band R(moved)(alpha_i) - moved(theta_i)|,
    the same intentional-smoothing quantity ``project`` reports, sampled at alpha(theta_i).
    """
    angles, length = arclength_angles(nodes)
    count = nodes.num_nodes
    w = moved.values(count)
    weights = w*nodes.speeds/(length/(2*np.pi))
    step = np.exp(-1j*angles)
    powers = np.empty((band+1, count), complex)
    powers[0] = 1.
    for k in range(1, band+1):
        powers[k] = powers[k-1]*step                       # e^{-i k alpha}
    positive = powers@weights/count                        # k = 0..band
    negative = np.conj(powers[1:])@weights/count           # k = -1..-band
    coefficients = np.concatenate((negative[::-1], positive))
    evaluated = coefficients[band]+np.conj(powers[1:]).T@positive[1:]+powers[1:].T@negative
    return coefficients, float(np.max(np.abs(evaluated-w)))


def spectral_project(curve, coefficients, band, count, length_unit_m, *, validate=False):
    """``geometry.project`` with A replaced by ``arclength_quadrature``; same signature and checks."""
    nodes = curve.nodes(count)
    z = curve.values(count)
    h = normal_basis(nodes, len(coefficients)//2)@coefficients/length_unit_m
    normal = nodes.normals@np.array([1, 1j])
    moved = FourierCurve.from_samples(z+h*normal, count//2-1)
    n = moved.nodes(count)
    if validate:
        if n.signed_area <= 0 or np.min(n.speeds) < 1e-6*np.mean(n.speeds):
            raise UpdateRefused('irregular_parameterization', 'Invalid displaced curve.')
        if self_intersections(n.points):
            raise UpdateRefused('self_intersection', 'Displaced curve self-intersects.')
    return arclength_quadrature(moved, n, band)


class SpectralProjectedUpdate(ProjectedUpdate):
    name = 'centred_state_band_spectral_projection'

    def settings(self):
        return dict(super().settings(), construction=CONSTRUCTION,
                    resampler='eq. 9 quadrature on the uniform grid (count and 2*count); no splines',
                    boundary_samples=True, projection_error_control='coarse/fine diagnostic; not a rigorous bound')

    def _project(self, *args, **kwargs):
        self.counts['geometry_projections'] += 1
        return spectral_project(*args, **kwargs)
