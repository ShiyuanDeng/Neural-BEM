"""TG-002: the ten benchmark scenes. This is the only scene set for new experiments.

Every scene is one homogeneous object, fitted from the SAME start: a 65 mm
circle at the scene centre (0.5, 0.5) m. Targets sit 22-38 mm off that
centre in different directions, so the offset is visible but inside the range
where recorded runs recovered without any grid search (SC-043/SC-044: 12/12
contrast-0.5 configurations from 13-39 mm offsets, no localization).
Placements were frozen on 2026-10-04 before any fit. Do not tune them, and do
not drop a scene because it fails.

Shapes keep their historical definitions (cited per scene); only the
placement is new. Each outline is centred at its sample area centroid,
rotated, then placed at ``offset_mm`` in direction ``direction_deg``.
"""
from pathlib import Path
import re

import numpy as np

from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.io import digest

LENGTH, CENTER = .05, .5+.5j          # package length unit and scene centre (m)
START_CENTER_M, START_RADIUS_M = .5+.5j, .065
CONTRASTS = (.5, 4., 13.3)            # k_i^2/k_e^2: plastic in sand, and two dense (resonant) media

LOGO = Path(__file__).resolve().parent/'assets/aphex_twin_logo.svg'
LOGO_SHA256 = '05f73997e0bd08e6ba18073783c5e9824ba9d2664f699580995a443b9faa66ec'
LOGO_PROVENANCE = dict(
    source='https://en.wikipedia.org/wiki/File:Aphex_Twin_logo.svg', licence='Public domain',
    author='Original logo by Paul Nicholson; vectorized by Iwantmorelife',
    used='first path only (the central glyph); the surrounding ring is a separate annulus and is omitted')


def _t(count=8192):
    return 2*np.pi*np.arange(count)/count


def _arclength(p, count=8192):
    p = np.asarray(p, complex)
    s = np.r_[0, np.cumsum(np.abs(np.diff(np.r_[p, p[0]])))]
    u = np.linspace(0, s[-1], count, endpoint=False)
    return np.interp(u, s, np.r_[p.real, p[0].real])+1j*np.interp(u, s, np.r_[p.imag, p[0].imag])


def thick_arc(centreline_m, half_thickness_m, half_angle_deg):
    """Thick arc with semicircular caps (SC-022 C, SC-025 hook)."""
    R, w, alpha = centreline_m, half_thickness_m, np.radians(half_angle_deg)
    cap = np.linspace(0, np.pi, 600)
    return _arclength(np.concatenate([
        (R+w)*np.exp(1j*np.linspace(-alpha, alpha, 2000)), R*np.exp(1j*alpha)+w*np.exp(1j*(alpha+cap)),
        (R-w)*np.exp(1j*np.linspace(alpha, -alpha, 2000)), R*np.exp(-1j*alpha)+w*np.exp(1j*(-alpha+np.pi+cap))]))


def logo_outline():
    """Aphex Twin glyph polygon (first SVG path), y up, ring centre at 0, SVG units."""
    if digest(LOGO) != LOGO_SHA256:
        raise ValueError('Vendored logo asset changed')
    d = re.search(r'<path d="([^"]+)"', LOGO.read_text()).group(1)
    tokens = re.findall(r'[MmLlHhVvZz]|-?\d*\.?\d+(?:e-?\d+)?', d)
    points, command, i, current = [], None, 0, 0j
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        if command in 'Zz':
            break
        if command in 'MLml':
            step = complex(float(tokens[i]), float(tokens[i+1]))
            current = step if command in 'ML' else current+step
            command = {'M': 'L', 'm': 'l'}.get(command, command)  # implicit lineto after moveto
            i += 2
        elif command in 'HhVv':
            value = float(tokens[i])
            current = {'H': complex(value, current.imag), 'V': complex(current.real, value),
                       'h': current+value, 'v': current+1j*value}[command]
            i += 1
        else:
            raise ValueError('Unsupported SVG path command: '+command)
        points.append(current)
    # The path's own transform flips SVG y; raw coordinates are already y up.
    return np.asarray(points)-(3196.54+3196.54j)


def _cross():
    a = .36
    z = [complex(*p) for p in [(a, -a), (1, -a), (1, a), (a, a), (a, 1), (-a, 1), (-a, a), (-1, a),
                                (-1, -a), (-a, -a), (-a, -1), (a, -1)]]
    return np.concatenate([np.linspace(p, q, 500, endpoint=False) for p, q in zip(z, z[1:]+z[:1])])


def _scaled(points, max_radius_m):
    """Centre at area centroid and scale an outline (arbitrary units) to a maximum radius."""
    z = np.asarray(points, complex)
    z = z-_area_centroid(z)
    return z*max_radius_m/np.abs(z).max()


def _area_centroid(p):
    q = np.roll(p, -1)
    cross = p.real*q.imag-q.real*p.imag
    return ((p+q)*cross).sum()/(3*cross.sum())


# outline(): native outline in metres. band: stored Fourier band. taper: Gaussian
# width exp(-(n/taper)^2) applied before truncation (None = plain truncation, as historically).
# arclength: resample by arclength first (polygons, thick arcs). Formula shapes keep their
# uniform-parameter samples, as historically, so they are exactly band-limited.
SHAPES = {
    'circle': dict(source='SC-022 wrong_circle: radius 50 mm',
        outline=lambda: .05*np.exp(1j*_t()), band=1, taper=None, arclength=False),
    'kite': dict(source='SC-025 kite (Colton-Kress): 25 mm scale',
        outline=lambda: .025*(np.cos(_t())+.65*np.cos(2*_t())-.65+1.5j*np.sin(_t())), band=8, taper=None, arclength=False),
    'peanut': dict(source='SC-025 peanut: 50 mm (0.75 + 0.3 cos 2t)',
        outline=lambda: .05*(.75+.3*np.cos(2*_t()))*np.exp(1j*_t()), band=8, taper=None, arclength=False),
    'star': dict(source='SC-022 circle_to_star: 50 mm (1 + 0.25 cos 5t)',
        outline=lambda: .05*(1+.25*np.cos(5*_t()))*np.exp(1j*_t()), band=6, taper=None, arclength=False),
    'asymmetric': dict(source='SC-050 new_asymmetric: 50 mm (0.92 + 0.16 cos 3t + 0.12 sin 4t + 0.055 cos(7t+0.4))',
        outline=lambda: .05*(.92+.16*np.cos(3*_t())+.12*np.sin(4*_t())+.055*np.cos(7*_t()+.4))*np.exp(1j*_t()),
        band=8, taper=None, arclength=False),
    'c_shape': dict(source='SC-022 circle_to_c (development_c): R 40 mm, half-width 18 mm, half-angle 110 deg',
        outline=lambda: thick_arc(.040, .018, 110.), band=10, taper=None, arclength=True),
    'hook': dict(source='SC-025 hook: R 36 mm, half-width 13 mm, half-angle 130 deg',
        outline=lambda: thick_arc(.036, .013, 130.), band=10, taper=None, arclength=True),
    'cross': dict(source='TG-001 cross: rounded plus sign, arm half-width 0.36 of arm length',
        outline=lambda: _scaled(_arclength(_cross()), .0525), band=20, taper=10, arclength=True),
    'cog': dict(source='TG-001 cog: 8 teeth, r = 0.94 + 0.12 tanh(3 cos 8t)/tanh 3',
        outline=lambda: _scaled((.94+.12*np.tanh(3*np.cos(8*_t()))/np.tanh(3))*np.exp(1j*_t()), .0525),
        band=32, taper=20, arclength=False),
    'aphex_twin': dict(source='TG-001 Aphex Twin logo glyph (public-domain SVG, see LOGO_PROVENANCE)',
        outline=lambda: _scaled(_arclength(logo_outline()), .0575), band=32, taper=16, arclength=True),
}

# Frozen placements, easiest to hardest. offset_mm and direction_deg give the
# outline centroid relative to the start centre; rotation in radians.
PLACEMENTS = {
    'circle': dict(offset_mm=22, direction_deg=35, rotation=0.),
    'kite': dict(offset_mm=30, direction_deg=150, rotation=.5),
    'peanut': dict(offset_mm=34, direction_deg=255, rotation=1.1),
    'star': dict(offset_mm=26, direction_deg=320, rotation=.41),
    'asymmetric': dict(offset_mm=38, direction_deg=80, rotation=-.32),
    'c_shape': dict(offset_mm=30, direction_deg=205, rotation=.3),
    'hook': dict(offset_mm=26, direction_deg=290, rotation=2.4),
    'cross': dict(offset_mm=34, direction_deg=15, rotation=.35),
    'cog': dict(offset_mm=22, direction_deg=170, rotation=.17),
    'aphex_twin': dict(offset_mm=38, direction_deg=235, rotation=0.),
}
SCENES = tuple(PLACEMENTS)


def centre_m(scene):
    p = PLACEMENTS[scene]
    return START_CENTER_M+p['offset_mm']/1000*np.exp(1j*np.radians(p['direction_deg']))


def truth_fixture(scene):
    """Package-unit truth curve (origin at the scene centre, unit 5 cm)."""
    shape, place = SHAPES[scene], PLACEMENTS[scene]
    z = shape['outline']()
    z = _arclength(z) if shape['arclength'] else np.asarray(z, complex)
    if (z.real*np.roll(z.imag, -1)-np.roll(z.real, -1)*z.imag).sum() < 0:
        z = z[::-1]
    z = (z-_area_centroid(z))*np.exp(1j*place['rotation'])+centre_m(scene)
    z = (z-CENTER)/LENGTH
    spectrum = np.fft.fft(z)/len(z)
    if shape['taper'] is not None:
        spectrum *= np.exp(-(np.fft.fftfreq(len(z), 1/len(z))/shape['taper'])**2)
    curve = FourierCurve(spectrum[np.arange(-shape['band'], shape['band']+1) % len(z)])
    curve.validate()
    return curve


def start_fixture():
    """The single start for every scene and contrast."""
    return FourierCurve.circle(START_RADIUS_M/LENGTH, (START_CENTER_M-CENTER)/LENGTH)


def tag(contrast):
    return 'c'+f'{contrast:g}'


def case_id(contrast, scene):
    return f'{scene}__{tag(contrast)}'


CASES = tuple(case_id(c, s) for s in SCENES for c in CONTRASTS)
