"""A2. Geometry arrays → modal Müller matrix (one frequency, on a prepared ModalGeometry).

Traces are Fourier coefficients |m|<=K_trace of the flux state (u, J d_n u),
J=|z'(t)|. The Müller system is [[I-K, V], [-T, I+K']] with the Maue form of
T. Every kernel is split as G=P(R) log R+Q(R); log R=log(4 sin^2((theta-phi)/2))
+log|W|^2, and the first term has exact coefficients -1/|l|.
Sources and receivers use Graf's addition theorem about z_0.
"""
from . import checks
import numpy as np
from functools import lru_cache
from scipy.signal import fftconvolve
from scipy.special import gammaln, hankel1, i0e, jv

from .a1_geometry import EPS, half, reflect


_RADIAL_PI = np.longdouble('3.141592653589793238462643383279502884')
_RADIAL_EULER = np.longdouble('0.577215664901532860606512090082402431')


def _radial_bessel_orders(a, count):
    """Integer J orders by scaled Miller recurrence in extended precision.

    Normalize with J0+2 sum_(n>=1) t^n J_n = exp(sign*i*a), t=sign*i,
    choosing sign opposite Im(a). The right side then grows rather than
    decays, avoiding an ill-conditioned normalization for damped arguments.
    No special-function values at radial sample points are involved.
    """
    a = np.clongdouble(a)
    last = count+32
    values = np.zeros(last+2, dtype=np.clongdouble)
    values[last] = 1
    for n in range(last, 0, -1):
        values[n-1] = (2*n/a)*values[n]-values[n+1]
        if checks.bessel_requires_rescaling(values[n-1]):
            values[n-1:] *= np.longdouble('1e-200')
    sign = -1 if a.imag >= 0 else 1
    phase = np.array([1, sign*1j, -1, -sign*1j], dtype=np.clongdouble)
    normalization = values[0]+2*np.sum(phase[np.arange(1, last+1) % 4]*values[1:last+1])
    values *= np.exp(sign*1j*a)/normalization
    return values[:count]


def radial_functions(r2, ko, ki):
    """P0-P1, Q0-Q1, their R-derivatives (with P/R added to Q'), and k^2-weighted P,Q.

    Closed forms cancel the log(R)J0/(4 pi R) terms analytically (summary
    eq. 10). Taylor series in R are used only where max|k| r < 2.
    """
    r2 = np.asarray(r2, float)
    r = np.sqrt(r2)
    log = np.log(r2)
    jo, ji = jv(0, ko*r), jv(0, ki*r)
    po, pi = -jo/(4*np.pi), -ji/(4*np.pi)
    qo = .25j*hankel1(0, ko*r)-po*log
    qi = .25j*hankel1(0, ki*r)-pi*log
    dj = ko*jv(1, ko*r)-ki*jv(1, ki*r)
    dh = ko*hankel1(1, ko*r)-ki*hankel1(1, ki*r)
    out = np.array([po-pi, qo-qi, dj/(8*np.pi*r), -1j*dh/(8*r)-log*dj/(8*np.pi*r),
                    ko*ko*po-ki*ki*pi, ko*ko*qo-ki*ki*qi])
    near = max(abs(ko), abs(ki))*r < 2
    if np.any(near):
        x = r2[near]
        local = np.zeros((6, len(x)), complex)
        ao = ai = 1.
        harmonic = 0.
        for p in range(24):
            if p:
                ao *= -ko*ko/(4*p*p)
                ai *= -ki*ki/(4*p*p)
                harmonic += 1/p
            po_p, pi_p = -ao/(4*np.pi), -ai/(4*np.pi)
            qo_p = ao*(.25j+(harmonic-np.euler_gamma-np.log(ko/2))/(2*np.pi))
            qi_p = ai*(.25j+(harmonic-np.euler_gamma-np.log(ki/2))/(2*np.pi))
            power = x**p
            local[0] += (po_p-pi_p)*power
            local[1] += (qo_p-qi_p)*power
            local[4] += (ko*ko*po_p-ki*ki*pi_p)*power
            local[5] += (ko*ko*qo_p-ki*ki*qi_p)*power
            if p:
                local[2] += p*(po_p-pi_p)*x**(p-1)
                local[3] += (po_p-pi_p+p*(qo_p-qi_p))*x**(p-1)
        out[:, near] = local
    return out


def _radial_split_coefficients(k, upper, count):
    """Analytic P,Q,P',Q'+(P-P(0))/R coefficients (no radial samples).

    Graf's theorem gives [J_(2m)(k sqrt(R))]_n = e_n J_(m+n)(a) J_(m-n)(a),
    where a=k sqrt(upper)/2 and e_n=2-delta_n0. DLMF 10.23.16 then gives
    Q=C J0 + sum_(m>=1) (-1)^m J_(2m)/(pi m),
    C=i/4-(EulerGamma+log(k/2))/(2 pi). This avoids subtracting a singular
    Hankel series and P log(R). Negative integer orders use J_-n=(-1)^n J_n.
    """
    k = np.clongdouble(k)
    a = k*np.sqrt(np.longdouble(upper))/2
    n = np.arange(count)
    m = np.arange(1, count+1)[:, None]
    bessel = _radial_bessel_orders(a, 2*count)
    difference = m-n
    products = bessel[m+n]*bessel[np.abs(difference)]
    products *= np.where(difference < 0, (-1.)**difference, 1.)
    j0 = (-1.)**n*bessel[:count]**2
    pi = _RADIAL_PI
    constant = .25j-(_RADIAL_EULER+np.log(k/2))/(2*pi)
    q = constant*j0+np.sum(((-1.)**m/m.astype(np.longdouble))*products, axis=0)/pi
    p = -j0/(4*pi)
    dp = k*k/(16*pi)*(j0+products[0])
    # Differentiate the Neumann expansion analytically and use the Bessel
    # recurrences before evaluating coefficients. For S=Q'+(P-P(0))/R,
    # the J_(2m) weights are k^2*(-C/4-1/(16pi)) at m=0,
    # k^2*(-C/4+1/(32pi)) at m=1, and
    # k^2*(1+2*(-1)^m/m)/(8pi*(m^2-1)) for m>=2.
    # This avoids spectral differentiation of rounded coefficients.
    high = m[1:].astype(np.longdouble)
    weights = (1+2*(-1.)**high/high)/(8*pi*(high*high-1))
    s = k*k*((-constant/4-1/(16*pi))*j0
             +(-constant/4+1/(32*pi))*products[0]
             +np.sum(weights*products[1:], axis=0))
    arrays = np.array([p, q, dp, s])
    arrays[:, 1:] *= 2
    return arrays


def _neumann_tail_bounds(k, upper, count):
    """Absolute l1 bounds for omitted Neumann terms in Q and regular S.

    |J_l(a)| <= exp(|Im a|) (|a|/2)^l/l!. In the omitted products m>count,
    l=m+n>count, n<=l, and summing the other Bessel factor is bounded by
    2 exp(|Im a|+|a|/2). Sum the resulting geometric majorant. The absolute
    S/Q weight ratio is at most |k|^2*(m+2)/(8*(m^2-1)), decreasing for m>=2.
    These bound truncation, not roundoff.
    """
    a = k*np.sqrt(upper)/2
    h, start = abs(a)/2, count+1
    ratio = h/(start+1)
    if checks.neumann_tail_unbounded(ratio):
        return np.inf, np.inf
    log_first = (np.log(4/(np.pi*start))+2*abs(a.imag)+h
                 +start*np.log(h)-gammaln(start+1))
    first = np.exp(log_first)
    tail = first/(1-ratio)
    return tail, tail*abs(k)**2*(start+2)/(8*(start**2-1))


def radial_coefficients(ko, ki, upper, tolerance=1e-15):
    """Construct all six radial Chebyshev series from analytic Bessel products.

    Derivatives and the removable quotient are combined analytically in the
    even-Bessel basis before coefficient evaluation. P_o(0)=P_i(0)=-1/(4 pi)
    cancels the singular constants. Resolution uses coefficient decay,
    not a floating-point error certificate. ``radial_points`` is always zero.
    ``amplification`` uses a coefficient-derived weighted RMS lower bound on
    the peak, rather than the former sampled peak (see amplification_scope).
    """
    checks.require_radial_domain(ko, ki, upper, tolerance)
    # Complex logarithms also give the principal branch for negative real k.
    ko, ki = np.clongdouble(ko), np.clongdouble(ki)
    alpha = max(abs(ko), abs(ki))*np.sqrt(upper)/2
    count = 16*int(np.ceil(max(64, 2*(alpha+6*alpha**(1/3)+24))/16))
    for _ in range(4):
        po, qo, dpo, so = _radial_split_coefficients(ko, upper, count)
        pi, qi, dpi, si = _radial_split_coefficients(ki, upper, count)
        p, q, dp, dq = po-pi, qo-qi, dpo-dpi, so-si
        # P_o(0)-P_i(0)=0 exactly. Obtain the constant coefficient from that
        # identity instead of subtracting two nearly equal O(1) constants
        # when |k| sqrt(upper) is small.
        p[0] = -np.sum((-1.)**np.arange(1, count)*p[1:])
        c = np.array([p, q, dp, dq,
                      ko*ko*po-ki*ki*pi, ko*ko*qo-ki*ki*qi])
        checks.require_finite_radial_coefficients(c)
        size = np.sum(np.abs(c), axis=1)
        qo_tail, dqo_tail = _neumann_tail_bounds(ko, upper, count)
        qi_tail, dqi_tail = _neumann_tail_bounds(ki, upper, count)
        tail = np.array([0., qo_tail+qi_tail, 0., dqo_tail+dqi_tail, 0.,
                         abs(ko)**2*qo_tail+abs(ki)**2*qi_tail])
        small = checks.radial_decay(c, tolerance, size)
        if checks.radial_series_converged(small, count, ko, ki, tail, tolerance, size):
            degree = int(max(np.argmax(row) for row in small))+2
            rms = np.sqrt(np.abs(c[:, 0])**2+np.sum(np.abs(c[:, 1:])**2, axis=1)/2)
            peak_lower_bound = float(np.max(rms))
            with np.errstate(over='ignore'):
                result = np.asarray(c[:, :degree+1], dtype=np.complex128)
            checks.require_finite_radial_coefficients(result)
            return result, dict(
                radial_degree=degree, radial_points=0, radial_terms=count,
                radial_coefficient_method='analytic_bessel', alpha=float(alpha),
                radial_work_precision_bits=int(np.finfo(np.longdouble).nmant+1),
                coefficient_sum=float(np.max(size)),
                neumann_tail_bound=float(np.max(tail)),
                amplification=float(np.max(size)/peak_lower_bound) if peak_lower_bound else 0.,
                amplification_scope='coefficient l1 / Chebyshev weighted RMS; no radial samples')
        count *= 2
    raise ValueError(f'Radial Chebyshev series unresolved at {count//2} terms (alpha={alpha:.3g}).')


@lru_cache(maxsize=8)
def assembly_indices(band, cutoff):
    modes = np.arange(-cutoff, cutoff+1)
    a = np.arange(-band, band+1)[None, :]
    b = np.arange(-2*cutoff, 2*cutoff+1)[:, None]-a
    ell = np.arange(-band-cutoff, band+cutoff+1)
    symbol = np.where(ell == 0, 0., -1/np.maximum(np.abs(ell), 1))
    m, n = np.meshgrid(modes, modes, indexing='ij')
    arrays = (modes, a+band, np.clip(b+band, 0, 2*band), np.abs(b)<=band,
              symbol, m+band, band-n, m-n+2*cutoff, m+2*band+cutoff, np.eye(len(modes)))
    for array in arrays:
        array.setflags(write=False)
    return arrays


def kernel_matrix(log_part, smooth, cutoff):
    """Galerkin block 2 pi (S[m,-n] + sum_l L_l P[m-l, l-n]), L_l=-1/|l|, L_0=0.

    For fixed d=m-n this is a 1-D convolution of the diagonal P[a, d-a]
    with the exact log symbol, evaluated for every m at once.
    """
    band = half(log_part)
    checks.require_trace_workspace(cutoff, band)
    modes, a, b, mask, symbol, sm, sn, pm, pn, identity = assembly_indices(band, cutoff)
    diagonals = np.where(mask, log_part[a, b], 0)
    product = fftconvolve(diagonals, symbol[None, :], axes=1)
    return 2*np.pi*(smooth[sm, sn]+product[pm, pn])


def muller_matrix(geometry, ko, ki, cutoff, *, tolerance=1e-15, workers=1, basis_workers=1):
    """Assemble the modal Müller matrix; no boundary point or kernel sample.

    ``basis_workers`` only threads a lazy extension of the shared radial
    arrays, which other frequency threads wait for.
    """
    coefficients, info = radial_coefficients(ko, ki, geometry.radial_upper, tolerance)
    p, q, dp, dq, hp, hq = geometry.radial.combine(coefficients, basis_workers)
    q, dq, hq = np.stack((q, dq, hq))+geometry.log_multiplier(np.stack((p, dp, hp)), workers)
    k_log, k_smooth = -2*geometry.source_dot(np.stack((dp, dq)), workers)
    t_log, t_smooth = geometry.normal_dot(np.stack((hp, hq)), workers)
    v = kernel_matrix(p, q, cutoff)
    k = kernel_matrix(k_log, k_smooth, cutoff)
    modes, *_, identity = assembly_indices(geometry.band, cutoff)
    t = -modes[:, None]*modes[None, :]*v+kernel_matrix(t_log, t_smooth, cutoff)
    # K' kernel is K with target and source exchanged: K'[m,n]=K[-n,-m].
    kp = k[::-1, ::-1].T
    return np.block([[identity-k, v], [-t, identity+kp]]), info










