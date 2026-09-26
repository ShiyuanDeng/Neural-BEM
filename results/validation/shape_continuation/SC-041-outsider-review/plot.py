"""Figure for the outsider review: where kite's sharpest feature is, and when it appears."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc

HERE = Path(__file__).resolve().parent
L = 1e3*sc.LENGTH
survey = json.loads((HERE/'kite_feature_survey.json').read_text())
truth = ast.curve_from(sc.read(ast.source_folder('kite')/'truth.json')).values(4096)
M22 = ast.curve_from(json.loads((HERE.parent/'SC-041-atlas-decisions/runs/kite/M22/result.json').read_text())['curve'])
end = M22.values(16384)
feature = np.array(survey['trajectory'][-1]['feature_point'])
tips = np.array(survey['true_tips'])

fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
ax = axes[0]
ax.plot(L*truth.real, L*truth.imag, color='0.2', lw=2, label='truth (K=8)')
ax.plot(L*end.real, L*end.imag, color='tab:red', lw=1, label='SC-041 M=22 endpoint')
ax.scatter(*(L*tips.T), s=40, marker='^', color='0.2', zorder=3, label='true tips (r=2.14 mm)')
ax.scatter(*(L*feature), s=60, facecolor='none', edgecolor='tab:red', zorder=3, label='sharpest point (r=0.082 mm)')
ax.set_aspect('equal'); ax.set_title('Kite: whole boundary (mm)'); ax.legend(fontsize=7, loc='lower left')

ax = axes[1]
w = 3.0/L
for z, style in ((truth, dict(color='0.2', lw=2)), (end, dict(color='tab:red', lw=1))):
    keep = np.abs(z - (feature[0]+1j*feature[1])) < 1.5*w
    ax.plot(L*z.real[keep], L*z.imag[keep], '.', ms=1.5, **{k: v for k, v in style.items() if k != 'lw'})
ax.scatter(*(L*feature), s=60, facecolor='none', edgecolor='tab:red')
ax.set_xlim(L*(feature[0]-w), L*(feature[0]+w)); ax.set_ylim(L*(feature[1]-w), L*(feature[1]+w))
ax.set_aspect('equal'); ax.set_title('Zoom ±3 mm on the sharpest point')

ax = axes[2]
rows = survey['trajectory']
x = np.arange(len(rows))
ax.semilogy(x, [r['min_radius_mm'] for r in rows], color='tab:red', label='minimum radius')
ax.semilogy(x, [r['hausdorff_mm'] for r in rows], color='tab:blue', label='Hausdorff error')
ax.axhline(survey['true_tip_radius_mm'], color='0.2', ls='--', lw=1, label='true minimum radius')
labels = {}
for i, r in enumerate(rows):
    key = (r['curve_band'], r['update_modes'])
    labels.setdefault(key, i)
for n, ((K, M), i) in enumerate(sorted(labels.items(), key=lambda kv: kv[1])):
    ax.axvline(i, color='0.85', lw=0.8)
    ax.text(i+0.4, 60 if n % 2 == 0 else 25, f"K={K}\nM={M}", fontsize=6, va='top')
ax.set_xlabel('accepted state (SC-040 kite trajectory, then SC-041 M=19, M=22)', fontsize=8)
ax.set_ylabel('mm'); ax.set_title('The feature sharpens as M rises on K=192'); ax.legend(fontsize=7, loc='lower left')
fig.tight_layout()
fig.savefig(HERE/'kite_feature.svg')
fig.savefig(HERE/'kite_feature.png', dpi=110)
