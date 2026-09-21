"""Literature test boundaries and the analyticity half-width b* that FJS bounds use.

Fang-Jiang-Su 2024 (arXiv:2408.02199), Corollary 3.1:

    |K_{k,l}| <= (M/2pi) exp(-b ||l-k||_1)   for every b < b*,

where b* is the half-width of the strip |Im t| < b* into which the kernel of the
boundary integral operator extends analytically.  For a closed curve
z(t) = sum_j z_j e^{ijt} the obstruction is a *complexified self-intersection*:
writing u = e^{it}, v = e^{is} and zbar(u) = sum_j conj(z_j) u^{-j},

    W(u,v) = -u v (z(u)-z(v)) (zbar(u)-zbar(v)) / (u-v)^2

equals R^2 / (4 sin^2((t-s)/2)) on the real torus and is strictly positive
there.  b* is the largest beta with W != 0 on |u|, |v| in [e^-beta, e^beta].
That quantity is a pure function of the geometry spectrum {z_j}, is invariant
under translation and scaling, and is what the 2026-09-18 report calls for when
it asks whether coupling bandwidth can be tied to the geometry spectrum.

Closed form for an ellipse z = A u + B/u:  b* = (1/2) log|A/B|.
"""
import numpy as np

# Kress kite, Colton & Kress "Inverse Acoustic and Electromagnetic Scattering
# Theory": x(t) = (cos t + 0.65 cos 2t - 0.65, 1.5 sin t).
KITE = {0: -.65, 1: 1.25, -1: -.25, 2: .325, -2: .325}


def evaluate(coefficients, t):
    t = np.asarray(t, dtype=float)
    return sum(v * np.exp(1j * j * t) for j, v in coefficients.items())


def tangent(coefficients, t):
    t = np.asarray(t, dtype=float)
    return sum(1j * j * v * np.exp(1j * j * t) for j, v in coefficients.items())


def diameter(coefficients, grid=2048):
    z = evaluate(coefficients, 2 * np.pi * np.arange(grid) / grid)
    return float(np.abs(z[:, None] - z[None, :]).max())


def normalise(coefficients, target=1.):
    """Centre at the curve centroid and scale to unit diameter."""
    scale = target / diameter(coefficients)
    shifted = {j: v * scale for j, v in coefficients.items() if j != 0}
    t = 2 * np.pi * np.arange(4096) / 4096
    z = evaluate(shifted, t)
    # Area centroid of the enclosed region, by the complex Green's formula.
    dz = tangent(shifted, t) * (2 * np.pi / 4096)
    area = .5 * np.sum((z.conj() * dz).imag)
    centroid = np.sum((np.abs(z)**2 * dz).imag) / (4 * area)
    shifted[0] = -complex(centroid)
    return shifted


def quotient(coefficients, u, v):
    """W(u,v) = -uv (z(u)-z(v))(zbar(u)-zbar(v)) / (u-v)^2."""
    z = lambda w: sum(c * w**j for j, c in coefficients.items())
    zbar = lambda w: sum(np.conj(c) * w**(-j) for j, c in coefficients.items())
    return -u * v * (z(u) - z(v)) * (zbar(u) - zbar(v)) / (u - v)**2


def divided_difference(coefficients):
    """Laurent coefficients w_pq of (z(u)-z(v))/(u-v) = sum w_pq u^p v^q."""
    terms = {}
    for j, value in coefficients.items():
        if j > 0:
            for r in range(j):
                terms[(j - 1 - r, r)] = terms.get((j - 1 - r, r), 0) + value
        elif j < 0:
            for r in range(-j):
                terms[(-1 - r, j + r)] = terms.get((-1 - r, j + r), 0) - value
    return terms


def _reach(terms, logs, angles):
    """min over v, over roots u of the divided difference, of the strip width.

    A complexified self-intersection at (u, v) first enters the strip
    |Im t| <= beta at beta = max(|log|u||, |log|v||), so the minimum of that
    quantity over the whole zero set is b*.
    """
    if not terms:
        return np.inf
    ps = sorted({p for p, _ in terms})
    qs = sorted({q for _, q in terms})
    table = np.zeros((len(ps), len(qs)), complex)
    for (p, q), value in terms.items():
        table[ps.index(p), qs.index(q)] = value
    powers = np.array(qs, dtype=float)

    def probe(log_radius, angle):
        v = np.exp(log_radius + 1j * angle)
        column = table @ (v ** powers)
        # highest power of u first, for numpy.roots
        roots = np.roots(column[::-1]) if np.any(column) else np.array([])
        roots = roots[np.abs(roots) > 1e-12]
        if roots.size == 0:
            return np.inf
        return float(np.maximum(np.abs(np.log(np.abs(roots))),
                                abs(log_radius)).min())

    best, argument = np.inf, None
    for log_radius in logs:
        for angle in angles:
            value = probe(log_radius, angle)
            if value < best:
                best, argument = value, (log_radius, angle)
    if argument is None:
        return np.inf
    from scipy.optimize import minimize
    refined = minimize(lambda x: probe(x[0], x[1]), np.array(argument),
                       method='Nelder-Mead',
                       options=dict(xatol=1e-7, fatol=1e-10, maxiter=400))
    return float(min(best, refined.fun))


def analyticity_halfwidth(coefficients, upper=3.5, radii=49, angles=192):
    """b*: the analyticity strip half-width of the kernel, from {z_j} alone."""
    reflected = {-j: np.conj(v) for j, v in coefficients.items()}
    logs = np.linspace(-upper, upper, radii)
    turns = 2 * np.pi * np.arange(angles) / angles
    return float(min(upper,
                     _reach(divided_difference(coefficients), logs, turns),
                     _reach(divided_difference(reflected), logs, turns)))


def star_shaped_defect(coefficients, grid=4096):
    """min Im[z' conj(z-c)] / max|z-c|^2 about the centroid c.

    The ray from c meets the boundary once for every direction exactly when
    arg(z(t)-c) is monotone, i.e. when this quantity is positive.
    """
    t = 2 * np.pi * np.arange(grid) / grid
    offset = evaluate(coefficients, t) - coefficients.get(0, 0j)
    return float((tangent(coefficients, t) * offset.conj()).imag.min()
                 / np.abs(offset).max()**2)


def is_simple(coefficients, angles=1024, threshold=1e-6):
    """Cheap screen: min |W| stays away from zero on the real torus.

    `W` vanishes both where the curve self-intersects and where `z'` vanishes,
    so this rejects cusps as well, which is what a boundary integral wants. It
    is a *screen*: a fixed relative threshold on a finite grid can pass a curve
    with a near-cusp between samples. `analyticity_halfwidth(...) > 0` is the
    rigorous test — it roots the divided difference instead of sampling it, and
    returns exactly 0 in either degenerate case.
    """
    angle = 2 * np.pi * np.arange(angles) / angles
    u = np.exp(1j * angle)[:, None]
    v = np.exp(1j * (angle + np.pi / angles))[None, :]
    values = np.abs(quotient(coefficients, u, v))
    return bool(values.min() > threshold * values.max())


def crescent(major=.6, minor=.15, bend=1.6):
    """Ellipse bent by z -> z + i*bend*(Re z)^2; stays a finite Laurent series.

    At bend = 1.6 the curve is simple and smooth but *not* star-shaped about its
    centroid, which is the case an explicit Cartesian Laurent chart is supposed
    to buy over a radial chart.
    """
    amount = bend * (major + minor)**2
    return {1: major, -1: minor, 0: .5j * amount,
            2: .25j * amount, -2: .25j * amount}


def library():
    """The families the report names, all normalised to unit diameter.

    `crescent` and `corrugated` are the discriminating pair: the crescent has
    only |j| <= 2 while the corrugated boundary reaches |j| = 9, yet their
    analyticity half-widths are close.  A rule keyed to "geometry bandwidth"
    separates them; a rule keyed to b* does not.
    """
    lobed = {1: 1., 9: .055, -7: .055, 5: .035, -3: .035}
    return {
        'circle':     normalise({1: 1.}),
        'ellipse':    normalise({1: .65, -1: .35}),
        'kite':       normalise(KITE),
        'crescent':   normalise(crescent()),
        'corrugated': normalise(lobed),
    }
