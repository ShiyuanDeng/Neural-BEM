"""Per-frequency boundary-collocation-free Müller physics on a prepared ModalGeometry.

Traces are Fourier coefficients |m|<=K_trace of the flux state (u, J d_n u),
J=|z'(t)|. The Müller system is [[I-K, V], [-T, I+K']] with the Maue form of
T. Every kernel is split as G=P(R) log R+Q(R); log R=log(4 sin^2((theta-phi)/2))
+log|W|^2, and the first term has exact coefficients -1/|l|.
Sources and receivers use Graf's addition theorem about z_0.
"""
import numpy as np
from functools import lru_cache
from scipy.fft import dct
from scipy.signal import fftconvolve
from scipy.special import gammaln, hankel1, i0e, jv

from .modal_geometry import EPS, half, reflect


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


def radial_coefficients(ko, ki, upper, tolerance=1e-15):
    """Chebyshev coefficients on R in [0, upper], truncated where every later one is small.

    The sum of |c_n| is 1 for real alpha=|k|sqrt(upper)/2 and I0(2|Im alpha|)
    for damped k (summary Lemmas 2-3): the expected rounding scale.
    """
    alpha = max(abs(ko), abs(ki))*np.sqrt(upper)/2
    count = 16*int(np.ceil(max(64, 2*(alpha+6*alpha**(1/3)+24))/16))
    for _ in range(4):
        x = np.cos(np.pi*(np.arange(count)+.5)/count)
        values = radial_functions(upper*(x+1)/2, ko, ki)
        c = dct(values, type=2, axis=1)/count
        c[:, 0] /= 2
        size = np.sum(np.abs(c), axis=1)
        later = np.maximum.accumulate(np.abs(c)[:, ::-1], axis=1)[:, ::-1]
        small = later <= tolerance*size[:, None]
        if np.all(small[:, count//2]):
            degree = int(max(np.argmax(row) for row in small))+2
            peak = float(np.max(np.abs(values)))
            return c[:, :degree+1], dict(radial_degree=degree, radial_points=count, alpha=float(alpha),
                                         coefficient_sum=float(np.max(size)),
                                         amplification=float(np.max(size)/peak) if peak else 0.)
        count *= 2
    raise ValueError(f'Radial Chebyshev series unresolved at {count//2} points (alpha={alpha:.3g}).')


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
    if cutoff > band:
        raise ValueError('Trace cutoff must fit inside the coefficient window.')
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


def series_terms(x, tolerance):
    """Terms p<P of sum_p (-x^2/4)^p/(p!(n+p)!) so the first omitted n=0 term is small."""
    p = np.arange(2, 400)
    omitted = 2*p*np.log(max(x, 1e-300)/2)-2*gammaln(p+1)
    return int(p[np.argmax(omitted <= np.log(tolerance))])


def scaled_hankel(x, scale, order):
    """H_l(x) scale^l/l! for l=0..order (rows) at every x, by the forward recurrence.

    H_(l+1)=(2l/x)H_l-H_(l-1) becomes t_(l+1)=scale/(l+1)((2l/x)t_l-(scale/l)t_(l-1)).
    H_l grows like (l-1)!(2/x)^l while the factor shrinks, so neither the values
    nor the products overflow. H_l is the dominant solution for l>|x|, so the
    forward recurrence is stable.
    """
    x = np.asarray(x)
    t = np.empty((order+1,)+x.shape, complex)
    t[0] = hankel1(0, x)
    if order:
        t[1] = hankel1(1, x)*scale
    for l in range(1, order):
        t[l+1] = scale/(l+1)*(2*l/x*t[l]-scale/l*t[l-1])
    return t


def graf_order(k, radius, distance, tolerance, maximum=1024):
    """Smallest L bounding every omitted Graf order by tolerance*|H_0(k d)|.

    |J_l(k s)| <= a^l exp(|Im k| rho)/l! for |s|<=rho, a=|k|rho/2 (DLMF 10.14.4),
    so order l contributes at most b_l=2|H_l(k d)| a^l exp(|Im k| rho)/(l!|H_0(k d)|).
    Terms are computed to an order M>=|k d| with |H_(M-1)|<=|H_M|. The recurrence
    then keeps |H_l| increasing, so |H_(l+1)|<=(2l/|k d|+1)|H_l| for l>=M. That
    bounds b_(l+1)/b_l by q=max((M rho/d+a)/(M+1), rho/d), and the tail beyond M
    by b_M q/(1-q). The order is chosen by this bound, with no fixed cap below
    ``maximum``.
    """
    a = abs(k)*radius/2
    x = k*np.asarray(distance)
    ratio = radius/np.asarray(distance)
    order = max(64, int(np.ceil(np.max(np.abs(x))))+1)
    while order <= maximum:
        scaled = np.abs(scaled_hankel(x, a, order))
        terms = 2*scaled*np.exp(abs(np.imag(k))*radius)/scaled[0]
        increasing = np.all(scaled[-2]*a/order <= scaled[-1])
        q = np.maximum((order*ratio+a)/(order+1), ratio)
        if increasing and np.all(q < 1):
            # tail[l] bounds every order >= l, so L=l-1 is the last order kept.
            tail = np.cumsum(terms[::-1], axis=0)[::-1]+terms[-1]*q/(1-q)
            converged = np.flatnonzero(np.all(np.isfinite(tail) & (tail <= tolerance), axis=1))
            if len(converged):
                return max(int(converged[0])-1, 1), float(np.max(ratio))
        order *= 2
    raise ValueError(f'Graf expansion needs more than {maximum} orders (rho/d={np.max(ratio):.3g}).')


def point_kernels(geometry, k, point_sets, *, tolerance=1e-16, series_loss=1e-9, workers=1):
    """Coefficients (window x points) of the incident trace and flux of G_k(. - point).

    Regular waves depend only on k, so they are built once, at the largest
    Graf order any point set needs. Each set then keeps its own orders. Row l
    of the regular waves is divided by s_|l|=(k rho/2)^|l|/|l|!, and the Graf
    factor H_l(k d) is multiplied by it, so high orders neither underflow nor
    overflow.
    """
    waves = geometry.waves
    sets = []
    for points in point_sets:
        offset = points[:, 0]+1j*points[:, 1]-waves.center
        distance = np.abs(offset)
        if np.any(distance <= waves.radius):
            raise ValueError('Graf expansion requires every source and receiver outside the '
                             'coefficient bounding circle of the curve.')
        sets.append((offset, distance, *graf_order(k, waves.radius, distance, tolerance)))
    order = max(row[2] for row in sets)
    x = abs(k)*waves.radius
    terms = series_terms(x, tolerance)
    loss = float(EPS*i0e(x)*np.exp(x))
    if loss > series_loss:
        raise ValueError(f'Regular-wave series cancellation {loss:.2g} exceeds {series_loss:g} (|k| rho={x:.3g}).')
    arrays = waves.ensure(order+1, terms, workers)
    half_h = k*waves.radius/2
    n = np.arange(order+2)
    weights = np.empty((order+2, terms), complex)
    weights[:, 0] = 1
    for p in range(1, terms):
        weights[:, p] = weights[:, p-1]*(-half_h**2/(p*(n+p)))
    positive = np.einsum('np,npm->nm', weights, arrays)
    negative = (-1.)**n[:, None]*reflect(np.einsum('np,npm->nm', weights.conj(), arrays), 1)
    functions = np.concatenate((negative[:0:-1], positive))  # orders -(L+1)..L+1, row l over s_|l|
    l = np.arange(-order, order+1)
    lower = np.where(l >= 1, abs(l)/half_h, half_h/(abs(l)+1))[:, None]  # s_|l-1|/s_|l|
    upper = np.where(l >= 0, half_h/(abs(l)+1), abs(l)/half_h)[:, None]  # s_|l+1|/s_|l|
    flux = k/2*(geometry.normal_multiplier(functions[:-2]*lower, workers)
                -geometry.conjugate_normal_multiplier(functions[2:]*upper, workers))
    values = functions[1:-1]
    result = []
    for offset, distance, own, ratio in sets:
        rows = slice(order-own, order+own+1)
        orders = np.arange(-own, own+1)
        outgoing = scaled_hankel(k*distance, half_h, own)[np.abs(orders)]*np.where(orders < 0, (-1.)**orders, 1)[:, None]
        graf = .25j*outgoing*np.exp(-1j*orders[:, None]*np.angle(offset)[None, :])
        result.append((values[rows].T@graf, flux[rows].T@graf,
                       dict(graf_order=own, graf_ratio=ratio, series_terms=terms, series_loss=loss)))
    return result


def hadamard(traces, reciprocal, weights, cutoff, factor):
    """2 pi (ki^2-ko^2) sum_m w_m (u_s u~_r)_(-m) for paired columns; w=Re(V conj N)."""
    moments = fftconvolve(traces, reciprocal, axes=0)
    centre = (len(weights)-1)//2
    n = min(centre, 2*cutoff)
    return 2*np.pi*factor*moments[2*cutoff-n:2*cutoff+n+1][::-1].T@weights[centre-n:centre+n+1]
