"""Compact comparison from saved arrays only; run from the repository root."""
from pathlib import Path
import json
import numpy as np
from experiments.modal_entry_screen.plots import plt, heat, save

root = Path(__file__).resolve().parent
fig, axes = plt.subplots(2, 4, figsize=(12, 6), constrained_layout=True)
for col, name in enumerate(('circle', 'ellipse', 'asymmetric_star', 'crescent')):
    case = json.loads((root/f'{name}_kd10/case.json').read_text())
    with np.load(root/f'{name}_kd10/arrays.npz') as arr:
        forward = arr['a']-np.eye(case['dimension'])
        derivative = arr['da'][4]
    for row, matrix in enumerate((forward, derivative)):
        im = heat(axes[row, col], matrix, case['cutoff'])
        if row == 0:
            axes[row, col].set_title(name.replace('_', ' ') + f" · K={case['cutoff']}", fontsize=10)
    axes[0, col].set_xlabel('Forward A − I')
    axes[1, col].set_xlabel('Shape derivative ∂A (p=6 cosine)')
fig.colorbar(im, ax=axes, shrink=.78, label='log₁₀ block-relative entry magnitude')
fig.suptitle('The forward matrix and its derivative can need different entries\n'
             'kD=10 · six-direction experiment · each block normalized separately', fontsize=13)
save(fig, root/'figures', '05_forward_vs_derivative_kd10')
gallery = root/'gallery.html'
text = gallery.read_text()
if '05_forward_vs_derivative_kd10.png' not in text:
    text += '<section><h2>Forward versus derivative at kD=10</h2>' \
        '<a href="figures/05_forward_vs_derivative_kd10.svg">SVG</a> · ' \
        '<a href="figures/05_forward_vs_derivative_kd10.png">PNG</a>' \
        '<img src="figures/05_forward_vs_derivative_kd10.png" alt="Forward and derivative matrices"></section>'
    gallery.write_text(text)
print(root/'figures/05_forward_vs_derivative_kd10.png')
