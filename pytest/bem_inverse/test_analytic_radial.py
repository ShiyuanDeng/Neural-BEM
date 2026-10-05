"""Independent checks of direct Bessel--Chebyshev radial coefficients."""
import numpy as np
import pytest
from numpy.polynomial.chebyshev import chebval
from scipy.fft import dct

from bem_inverse import modal_operator as operator


def dct_reference(ko, ki, upper, count=2048):
    x = np.cos(np.pi*(np.arange(count)+.5)/count)
    coefficients = dct(operator.radial_functions(upper*(x+1)/2, ko, ki),
                       type=2, axis=1)/count
    coefficients[:, 0] /= 2
    return coefficients


def high_precision_values(ko, ki, points):
    mp = pytest.importorskip('mpmath')
    with mp.workdps(60):
        ko, ki = mp.mpc(ko), mp.mpc(ki)

        def split(k, r):
            if r == 0:
                constant = mp.j/4-(mp.euler+mp.log(k/2))/(2*mp.pi)
                return (-1/(4*mp.pi), constant, k*k/(16*mp.pi),
                        -k*k/4*(constant+1/(2*mp.pi)))
            z = k*mp.sqrt(r)
            p = -mp.besselj(0, z)/(4*mp.pi)
            q = mp.j/4*mp.hankel1(0, z)-p*mp.log(r)
            dp = k*mp.besselj(1, z)/(8*mp.pi*mp.sqrt(r))
            dq = -mp.j*k*mp.hankel1(1, z)/(8*mp.sqrt(r))-dp*mp.log(r)-p/r
            return p, q, dp, dq

        values = []
        for point in points:
            r = mp.mpf(float(point))
            po, qo, dpo, dqo = split(ko, r)
            pi, qi, dpi, dqi = split(ki, r)
            quotient = (po-pi)/r if r else dpo-dpi
            values.append([complex(v) for v in (po-pi, qo-qi, dpo-dpi,
                           dqo-dqi+quotient, ko*ko*po-ki*ki*pi, ko*ko*qo-ki*ki*qi)])
        return np.array(values).T


@pytest.mark.parametrize('contrast', [.5, 4., 13.3])
@pytest.mark.parametrize('damping', [0., .25])
@pytest.mark.parametrize('k,upper', [(.05, .01), (1.2, 4.), (6.417188604442469, 12.)])
def test_all_six_series_against_dct_and_high_precision(contrast, damping, k, upper):
    ko = k*(1+1j*damping)
    ki = ko*np.sqrt(contrast)
    coefficients, info = operator.radial_coefficients(ko, ki, upper)
    reference = dct_reference(ko, ki, upper)
    scale = np.sum(np.abs(reference), axis=1)
    padded = np.pad(coefficients, ((0, 0), (0, reference.shape[1]-coefficients.shape[1])))
    assert np.all(np.sum(np.abs(padded-reference), axis=1) < 1e-11*scale)
    points = upper*np.array([0., 1e-12, .001, .17, .63, 1.])
    exact = high_precision_values(ko, ki, points)
    values = chebval(2*points/upper-1, coefficients.T)
    assert np.all(np.max(np.abs(values-exact), axis=1) < 1e-11*scale)
    assert info['radial_points'] == 0
    assert info['radial_coefficient_method'] == 'analytic_bessel'


def test_analytic_path_does_not_sample_radial_functions_or_use_dct(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Sampled radial coefficient construction')
    import scipy.fft
    monkeypatch.setattr(operator, 'radial_functions', forbidden)
    monkeypatch.setattr(scipy.fft, 'dct', forbidden)
    monkeypatch.setattr(operator, 'dct', forbidden, raising=False)
    coefficients, info = operator.radial_coefficients(3+0.75j, 11+2.75j, 8.)
    assert np.all(np.isfinite(coefficients))
    assert info['radial_points'] == 0


def test_zero_material_contrast_is_exactly_zero():
    coefficients, info = operator.radial_coefficients(3+.75j, 3+.75j, 8.)
    np.testing.assert_array_equal(coefficients, np.zeros_like(coefficients))
    assert info['amplification'] == 0


@pytest.mark.parametrize('args', [(0., 1., 4., 1e-15), (1., np.nan, 4., 1e-15),
                                  (1., 2., 0., 1e-15), (1., 2., np.inf, 1e-15),
                                  (1., 2., 4., 0.), (1., 2., 4., np.nan)])
def test_invalid_radial_inputs_are_refused(args):
    with pytest.raises(ValueError):
        operator.radial_coefficients(*args)


def test_nonfinite_analytic_coefficients_are_refused(monkeypatch):
    monkeypatch.setattr(operator, '_radial_split_coefficients',
                        lambda k, upper, count: np.full((4, count), np.nan))
    with pytest.raises(ValueError, match='Non-finite'):
        operator.radial_coefficients(1., 2., 4.)


def test_unresolved_neumann_tail_is_refused_without_dct_fallback(monkeypatch):
    counts = []

    def unresolved(k, upper, count):
        counts.append(count)
        return np.inf, np.inf

    monkeypatch.setattr(operator, '_neumann_tail_bounds', unresolved)
    with pytest.raises(ValueError, match='unresolved'):
        operator.radial_coefficients(1., 2., 4.)
    assert len(counts) == 8  # two materials, four successive resolutions
    assert counts[::2] == [counts[0]*2**i for i in range(4)]


def test_neumann_tail_bound_covers_retained_coefficient_error():
    k, upper, count = 4+1j, 4., 12
    truncated = operator._radial_split_coefficients(k, upper, count)
    extended = operator._radial_split_coefficients(k, upper, 4*count)
    for index, bound in zip((1, 3), operator._neumann_tail_bounds(k, upper, count)):
        assert np.sum(np.abs(truncated[index]-extended[index, :count])) <= bound


@pytest.mark.parametrize('a', [.003, 3+1j, 3-1j, -3+1j, 40+10j, 100+25j])
def test_scaled_bessel_recurrence_against_high_precision(a):
    mp = pytest.importorskip('mpmath')
    values = operator._radial_bessel_orders(a, 200)
    with mp.workdps(70):
        for n in (0, 1, 10, 40, 150):
            exact = mp.besselj(n, mp.mpc(a))
            # Preserve extended precision and orders below float64 underflow.
            got = mp.mpc(str(values[n].real), str(values[n].imag))
            assert abs(got-exact) <= 5e-17*abs(exact)
