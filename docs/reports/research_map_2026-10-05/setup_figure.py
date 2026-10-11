"""TG-002 setup figure: acquisition ring, start circle, true shape and dimensions.

PYTHONPATH=solvers:. python docs/reports/research_map_2026-10-05/setup_figure.py [--scene c_shape|all]

Reads the frozen TG-002 truth files and the frozen CI-001 acquisition only (no solves).
Writes tg002_setup_<scene>.png (200 dpi) and .pdf (vector) next to this script.
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, ConnectionPatch, Rectangle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from bem_inverse.io import read, curve_from  # noqa: E402
from experiments.benchmark import scenes as S  # noqa: E402
from experiments.cleaned_interface import benchmark as ci  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUTS = ROOT/'results/validation/cleaned_interfaces/TG-002/inputs'

SURFACE, INK, MUTED, SPINE = '#fcfcfb', '#0b0b0b', '#52514e', '#c9c8c2'
TRUTH, TX, RX, ACCENT = '#2a78d6', '#eb6834', '#1baf7a', '#eda100'
HOST_EPS = 6.0          # benchmark wavenumber: k = 2 pi f sqrt(mu0 eps0 * 6)
C0 = 1/np.sqrt(4e-7*np.pi*8.854187817e-12)
NAMES = dict(c_shape='C-shape', aphex_twin='Aphex Twin glyph', asymmetric='asymmetric shape')
LABEL_AT = dict(c_shape=38+20j)  # clear space for the offset label in the zoom panel (mm)


def geometry(scene):
    mm = lambda z: (z-S.START_CENTER_M)*1000  # noqa: E731  (mm relative to the start centre)
    truth = mm(S.CENTER+S.LENGTH*curve_from(read(INPUTS/scene/'truth.json')).values(4096))
    start = mm(S.CENTER+S.LENGTH*S.start_fixture().values(1024))
    acq = ci.acquisition()
    tx = (acq.sources[:, 0]+1j*acq.sources[:, 1])*S.LENGTH*1000
    rx = (acq.receivers[:, 0]+1j*acq.receivers[:, 1])*S.LENGTH*1000
    return truth, start, tx, rx, mm(S.centre_m(scene))


def closed(z):
    return np.r_[z, z[:1]]


def dimension(ax, a, b, label, *, offset=0., colour=INK, size=9.5, rotate=True, pad=7):
    """Double-headed dimension arrow from a to b with a label beside its midpoint."""
    ax.annotate('', xy=(b.real, b.imag), xytext=(a.real, a.imag),
                arrowprops=dict(arrowstyle='<|-|>', color=colour, lw=1.1, shrinkA=0, shrinkB=0, mutation_scale=9))
    mid, direction = (a+b)/2, (b-a)/abs(b-a)
    normal = 1j*direction
    angle = np.degrees(np.angle(direction)) if rotate else 0.
    if angle > 90 or angle < -90:
        angle -= 180*np.sign(angle)
    p = mid+normal*(pad+offset)
    ax.text(p.real, p.imag, label, color=colour, fontsize=size, ha='center', va='center', rotation=angle,
            rotation_mode='anchor', bbox=dict(boxstyle='round,pad=0.15', fc=SURFACE, ec='none'))


def style(ax, lim, ticks):
    ax.set_facecolor(SURFACE)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect('equal')
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.tick_params(colors=MUTED, labelsize=8.5, length=3)
    for side in ax.spines.values():
        side.set_color(SPINE)
    ax.set_xlabel('x (mm from scene centre)', color=MUTED, fontsize=9)
    ax.set_ylabel('y (mm)', color=MUTED, fontsize=9, labelpad=2)


def draw(scene):
    truth, start, tx, rx, centroid = geometry(scene)
    place, shape = S.PLACEMENTS[scene], S.SHAPES[scene]
    name = NAMES.get(scene, scene.replace('_', ' '))
    lam = {f: C0/(f*np.sqrt(HOST_EPS))*1000 for f in (.25e9, 2.5e9)}
    plt.rcParams.update({'font.family': ['Ubuntu', 'DejaVu Sans'], 'font.size': 10, 'mathtext.fontset': 'dejavusans'})
    fig = plt.figure(figsize=(13.333, 7.5), facecolor=SURFACE)
    fig.text(.045, .95, 'TG-002 inverse-scattering setup', fontsize=19, fontweight='bold', color=INK)
    fig.text(.045, .917, f'Scene shown: {name} (same outline at contrasts 0.5 / 4 / 13.3). One start circle for all '
             '30 cases. Drawn from the frozen input files; no new solves.', fontsize=10.5, color=MUTED)

    # ---------------------------------------------------------------- full acquisition view
    ax = fig.add_axes([.055, .1, .41, .72])
    style(ax, 345, [-300, -150, 0, 150, 300])
    ax.add_patch(Circle((0, 0), 300, fill=False, ec=SPINE, lw=1.0, ls=(0, (4, 3))))
    ax.plot(tx.real, tx.imag, '^', color=TX, ms=7.5, mec='white', mew=.6, zorder=4)
    ax.plot(rx.real, rx.imag, 'o', color=RX, ms=6.2, mec='white', mew=.6, zorder=4)
    k = 3                        # illustrate one measured pair: Tx_k and its receiver 0.2 rad further on
    arc = 300*np.exp(1j*np.linspace(np.angle(tx[k]), np.angle(tx[k])+.2, 20))
    ax.plot(arc.real, arc.imag, color=INK, lw=2.4, solid_capstyle='round', zorder=3)
    ax.plot([tx[k].real, centroid.real, rx[k].real], [tx[k].imag, centroid.imag, rx[k].imag], color=MUTED,
            lw=1, ls=(0, (2, 2)), zorder=1)
    ax.annotate(f'one measured pair: Tx {k+1} → object → Rx {k+1}', xy=(tx[k].real, tx[k].imag),
                xytext=(245, 330), fontsize=9, color=MUTED, ha='center',
                arrowprops=dict(arrowstyle='-', color=SPINE, lw=.8))
    ax.fill(truth.real, truth.imag, color=TRUTH, alpha=.25, lw=0, zorder=3)
    ax.plot(*np.array([closed(truth).real, closed(truth).imag]), color=TRUTH, lw=1.3, zorder=3)
    ax.plot(closed(start).real, closed(start).imag, color=INK, lw=1.1, ls=(0, (3, 2)), zorder=3)
    ax.plot([0], [0], '+', color=INK, ms=7, mew=1.1, zorder=5)
    dimension(ax, 0j, 300*np.exp(1j*np.radians(127.5)), 'R = 300 mm', pad=9)
    mid = 262*np.exp(1j*(np.angle(tx[k])+.1))
    ax.text(mid.real, mid.imag, '60 mm\n(0.2 rad)', fontsize=8.5, color=INK, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.15', fc=SURFACE, ec='none'))
    sweep = 335*np.exp(1j*np.linspace(np.angle(tx[6]), np.angle(tx[7]), 20))
    ax.plot(sweep.real, sweep.imag, color=INK, lw=.9)
    ax.text(sweep[10].real-4, sweep[10].imag+6, '15°', fontsize=8.5, color=INK, ha='right', va='bottom')
    zoom = 95
    ax.add_patch(Rectangle((-zoom, -zoom), 2*zoom, 2*zoom, fill=False, ec=MUTED, lw=.8, ls=(0, (1, 2))))
    ax.text(-338, -335, f'host medium: homogeneous, ε$_r$ = {HOST_EPS:g}, unbounded', fontsize=8.5, color=MUTED,
            va='bottom')
    ax.set_title('Acquisition: 24 paired line sources and receivers', loc='left', fontsize=12.5,
                 fontweight='bold', color=INK, pad=20)
    ax.text(0, 1.012, 'each Tx is recorded only at its own Rx · 24 complex values per frequency',
            transform=ax.transAxes, fontsize=9, color=MUTED, va='bottom')

    # ---------------------------------------------------------------- zoom on the unknown
    bx = fig.add_axes([.5, .1, .28, .72])
    style(bx, zoom, [-80, -40, 0, 40, 80])
    bx.fill(truth.real, truth.imag, color=TRUTH, alpha=.25, lw=0)
    bx.plot(closed(truth).real, closed(truth).imag, color=TRUTH, lw=1.8)
    bx.plot(closed(start).real, closed(start).imag, color=INK, lw=1.4, ls=(0, (4, 2.5)))
    bx.plot([0], [0], '+', color=INK, ms=9, mew=1.3, zorder=5)
    bx.annotate('', xy=(centroid.real, centroid.imag), xytext=(0, 0),
                arrowprops=dict(arrowstyle='-|>', color=ACCENT, lw=2, mutation_scale=12, shrinkA=0, shrinkB=0))
    bx.plot([centroid.real], [centroid.imag], 'o', color=ACCENT, ms=5, mec='white', mew=.7, zorder=6)
    label = LABEL_AT.get(scene, centroid*1.6)
    bx.annotate(f'offset {place["offset_mm"]} mm\nat {place["direction_deg"]}°', xy=(centroid.real/2, centroid.imag/2),
                xytext=(label.real, label.imag), color=INK, fontsize=9.5, ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2', fc=SURFACE, ec='none'),
                arrowprops=dict(arrowstyle='-', color=ACCENT, lw=.9, shrinkA=2, shrinkB=2))
    sa = np.exp(1j*np.radians(62))
    dimension(bx, 0j, 65*sa, 'r = 65 mm', pad=6)
    y0 = -86
    for i, (length, label) in enumerate([(lam[2.5e9], f'λ host @ 2.5 GHz = {lam[2.5e9]:.0f} mm'),
                                         (lam[2.5e9]/np.sqrt(13.3),
                                          f'λ inside, contrast 13.3 = {lam[2.5e9]/np.sqrt(13.3):.0f} mm')]):
        y = y0+9*i
        bx.plot([88-length, 88], [y, y], color=INK, lw=2.2, solid_capstyle='butt')
        bx.text(86-length, y, label+'  ', fontsize=8.3, color=MUTED, ha='right', va='center')
    bx.set_title(f'Unknown vs start: {name}', loc='left', fontsize=12.5, fontweight='bold', color=INK, pad=20)
    bx.text(0, 1.012, f'rotation {place["rotation"]:g} rad · stored Fourier band K = {shape["band"]}',
            transform=bx.transAxes, fontsize=9, color=MUTED, va='bottom')
    for corner in ((-zoom, zoom), (-zoom, -zoom)):
        fig.add_artist(ConnectionPatch(xyA=(zoom, corner[1]), coordsA=ax.transData, xyB=corner,
                                       coordsB=bx.transData, color=SPINE, lw=.8, ls=(0, (1, 2))))

    # ---------------------------------------------------------------- parameters
    items = [
        ('Physics', ['2-D scalar Helmholtz transmission,', 'one homogeneous object,', 'known contrast k$_i^2$/k$_e^2$',
                     '0.5 / 4 / 13.3  (object ε$_r$ = 3 / 24 / 80)']),
        ('Frequencies', ['19 from 0.25 to 2.5 GHz, step 0.125', f'host λ = {lam[.25e9]:.0f} → {lam[2.5e9]:.0f} mm',
                         'plus a damped copy k(1+0.25i)', 'for the low-frequency ladder']),
        ('Data', ['24 pairs × 19 freqs = 456 complex', 'scattered-field values, noiseless;',
                  'nodal Kress N2048, checked', 'against N1024 to 1e-8']),
        ('Start and truth', ['start: circle r = 65 mm at centre', 'truths: 10 shapes, centroids',
                             '22–38 mm off centre']),
        ('Recovered if', ['RMS ≤ 1 mm, Hausdorff ≤ 2 mm,', 'residual ≤ 0.3% at every freq.,',
                          'endpoint audit passed']),
    ]
    y = .845
    for head, lines in items:
        fig.text(.805, y, head, fontsize=10.5, fontweight='bold', color=INK)
        y -= .028
        for line in lines:
            fig.text(.805, y, line, fontsize=9.3, color=MUTED)
            y -= .025
        y -= .016

    handles = [Line2D([], [], marker='^', ls='', color=TX, ms=8, label='Tx (line source)'),
               Line2D([], [], marker='o', ls='', color=RX, ms=7, label='Rx (paired receiver)'),
               Patch(facecolor=TRUTH, alpha=.35, edgecolor=TRUTH, label='true boundary'),
               Line2D([], [], color=INK, ls=(0, (3, 2)), lw=1.3, label='start circle'),
               Line2D([], [], color=ACCENT, lw=2, marker='o', ms=4, label='centroid offset'),
               Line2D([], [], color=INK, lw=0, marker='+', ms=8, mew=1.2, label='scene centre (0.5, 0.5) m')]
    fig.legend(handles=handles, loc='lower left', bbox_to_anchor=(.045, .0), ncol=6, frameon=False,
               fontsize=9.3, labelcolor=INK, handlelength=1.8, columnspacing=1.6)
    stem = HERE/f'tg002_setup_{scene}'
    fig.savefig(stem.with_suffix('.png'), dpi=200, facecolor=SURFACE)
    fig.savefig(stem.with_suffix('.pdf'), facecolor=SURFACE)
    plt.close(fig)
    return stem


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', default='c_shape', choices=(*S.SCENES, 'all'))
    args = parser.parse_args()
    for scene in (S.SCENES if args.scene == 'all' else (args.scene,)):
        print(draw(scene))


if __name__ == '__main__':
    main()
