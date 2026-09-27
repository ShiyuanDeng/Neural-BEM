"""Update equations as a slide image (matplotlib mathtext; no LaTeX needed)."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
INK, MUTED, SURFACE, AMBER = '#0b0b0b', '#52514e', '#fcfcfb', '#c98500'
plt.rcParams.update({'mathtext.fontset': 'cm', 'font.family': 'DejaVu Sans'})

rows = [
    (r'$\Gamma(t)\;=\;\sum_{k=-K}^{K} c_k\, e^{\,i k t}$', 'boundary state, stored band $K$', r'$t\in[0,2\pi)$'),
    (r'$h(s)\;=\;a_0+\sum_{m=1}^{M}\left(a_m\cos ms+b_m\sin ms\right)$', 'scalar normal update, band $M$', r'$s$: arclength angle'),
    (r'$\delta\Gamma^{\,j}\;=\;h\,\boldsymbol{\nu}^{\,j}$', 'move each point along the normal', r'$\boldsymbol{\nu}^{\,j}$: outward unit normal of $\Gamma^{\,j}$'),
    (r'$\Gamma^{\,j+1}\;=\;\Gamma^{\,j}+\delta\Gamma^{\,j}$', 'next accepted state', r'then stored in band $K$'),
]
fig = plt.figure(figsize=(13.333, 7.5), facecolor=SURFACE)
fig.text(.06, .9, 'One update step', fontsize=24, fontweight='bold', color=INK, va='top')
for i, (eq, label, note) in enumerate(rows):
    y = .73 - i*.175
    fig.text(.06, y, eq, fontsize=29, color=INK, va='center')
    fig.text(.71, y+.022, label, fontsize=16, color=INK, va='center')
    fig.text(.71, y-.028, note, fontsize=14, color=MUTED, va='center')
fig.text(.06, .1, r'In the solver the stored state is the band-$K$ projection of the moved curve after arclength reparametrisation:',
         fontsize=13, color=MUTED, va='top')
fig.text(.06, .058, r'$\Gamma^{\,j+1}=\Gamma^{\,j}+P_K\!\left[A(\Gamma^{\,j}+h\boldsymbol{\nu}^{\,j})-A(\Gamma^{\,j})\right]$   (SC-035 centred state-band update)',
         fontsize=13, color=MUTED, va='top')
for ext in ('png', 'pdf', 'svg'):
    fig.savefig(HERE/f'00_update_equations.{ext}', dpi=150, facecolor=SURFACE)
print('ok')
