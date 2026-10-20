"""A3. Geometry and source/receiver positions → modal wave coefficients.

Arrays have axes (Cartesian coefficient, point); each point set retains its
own Graf cutoff. Frequency-independent regular-wave arrays are owned by A1.
"""
from . import checks
import numpy as np
from scipy.special import gammaln, hankel1, i0e
from .a1_geometry import EPS, reflect

def series_terms(x, tolerance):
    """Terms p<P of sum_p (-x^2/4)^p/(p!(n+p)!) so the first omitted n=0 term is small."""
    return checks.regular_wave_term_count(x, tolerance)



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
        increasing = checks.graf_hankel_increasing(scaled, a, order)
        q = np.maximum((order*ratio+a)/(order+1), ratio)
        if checks.graf_tail_is_bounded(increasing, q):
            # tail[l] bounds every order >= l, so L=l-1 is the last order kept.
            tail = np.cumsum(terms[::-1], axis=0)[::-1]+terms[-1]*q/(1-q)
            converged = checks.graf_tail_orders(tail, tolerance)
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
        checks.require_graf_separation(distance, waves.radius)
        sets.append((offset, distance, *graf_order(k, waves.radius, distance, tolerance)))
    order = max(row[2] for row in sets)
    x = abs(k)*waves.radius
    terms = series_terms(x, tolerance)
    loss = float(EPS*i0e(x)*np.exp(x))
    checks.require_wave_cancellation(loss, series_loss, x)
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
