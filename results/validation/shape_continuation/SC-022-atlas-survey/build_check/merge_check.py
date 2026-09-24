"""SC-022 build check on the SC-020 stage-1 stall state (merge handoff, M=16).

Question: does the 0.5 GHz step layer at P=48 request the correction above
harmonic 16 that SC-021 (M=32) later made, and does it agree with the
evaluation-only true error there? No dense catalog; four solves.
"""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(ROOT / 'solvers')]
from experiments.shape_continuation import spd_cases as sc
from experiments.shape_continuation.atlas_survey import cell, lm_step, gn_step, pair_magnitude, true_error
from experiments.shape_continuation.geometry import FourierCurve
import config.two_circle_config as cfg, run_radial_fourier_topology_inverse as base

OUT = Path(__file__).parent
SC020 = ROOT / 'results/validation/shape_continuation/SC-020-spd-matched-hybrid'
inputs = sc.load()
obs = sc.package_observations(list(inputs['top025'].p.TRAIN), inputs['observed'], cfg, base)
contrast = cfg.PLASTIC_EPSR / cfg.SAND_EPSR
history = json.load(open(SC020 / 'runs/hybrid/stage_1_history.json'))['history']
row = next(r for r in history if r['iteration'] == 8)            # mid-plateau state
curve = FourierCurve(np.array(row['coefficients']['real']) + 1j * np.array(row['coefficients']['imag']))
damping = row['damping'] * 0.3                                   # live damping for the next step
truth = json.load(open(SC020 / 'inputs/scene_spec.json'))
e = next(s for s in truth['scenes'] if s['id'] == 'merge')['truth'][0]
t = np.linspace(0, 2 * np.pi, 20000, endpoint=False)
points = ((e['center'][0] + e['semi_major'] * np.cos(t)) + 1j * (e['center'][1] + e['semi_minor'] * np.sin(t)) - sc.CENTER) / sc.LENGTH
P = 48
truth_coef, truth_summary = true_error(curve, points, P, sc.LENGTH)
report = dict(state=dict(stage=1, iteration=8, loss=row['loss'], damping_next=damping), P=P, truth=truth_summary, frequencies={})
for f, o in zip(inputs['top025'].p.TRAIN, obs):
    c = cell(curve, o, contrast, 256, P, sc.LENGTH)
    lm = lm_step(c.gauss_newton, c.gradient, damping)
    gn, predicted = gn_step(c.gauss_newton, c.gradient)
    rows = {}
    for name, v in (('lm', lm), ('gn', gn), ('truth', truth_coef)):
        mag = pair_magnitude(v, P) * 1e3
        rows[name] = dict(norm_le16_mm=float(np.linalg.norm(mag[:17])), norm_17_32_mm=float(np.linalg.norm(mag[17:33])),
                          norm_33_48_mm=float(np.linalg.norm(mag[33:])), by_harmonic_mm=mag.round(6).tolist())
    def corr(a, b, sel):
        a, b = a[sel], b[sel]
        return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    order = np.r_[0, np.arange(1, P + 1), np.arange(1, P + 1)]
    band = (order >= 17) & (order <= 24)
    report['frequencies'][f'{f/1e9:g} GHz'] = dict(loss=c.loss, gn_predicted_decrease=predicted, **rows,
        cosine_with_truth_harmonics_17_24=dict(lm=corr(lm, truth_coef, band), gn=corr(gn, truth_coef, band)),
        cosine_with_truth_harmonics_0_16=dict(lm=corr(lm, truth_coef, order <= 16), gn=corr(gn, truth_coef, order <= 16)),
        sensitivity_by_harmonic=pair_magnitude(c.sensitivity, P).round(9).tolist())
(OUT / 'merge_check.json').write_text(json.dumps(report, indent=1))
for k, v in report['frequencies'].items():
    print(k, 'loss %.2e' % v['loss'], '| |step| mm <=16 / 17-32 / 33-48:',
          'LM %.4f %.4f %.4f' % (v['lm']['norm_le16_mm'], v['lm']['norm_17_32_mm'], v['lm']['norm_33_48_mm']),
          '| GN %.4f %.4f %.4f' % (v['gn']['norm_le16_mm'], v['gn']['norm_17_32_mm'], v['gn']['norm_33_48_mm']),
          '| cos(step,truth) 17-24: LM %.3f GN %.3f ; 0-16: LM %.3f GN %.3f' % (
              v['cosine_with_truth_harmonics_17_24']['lm'], v['cosine_with_truth_harmonics_17_24']['gn'],
              v['cosine_with_truth_harmonics_0_16']['lm'], v['cosine_with_truth_harmonics_0_16']['gn']))
tr = report['frequencies']['0.5 GHz']['truth']
print('truth |err| mm <=16 / 17-32 / 33-48: %.4f %.4f %.4f; beyond 48 rms %.2e mm' % (tr['norm_le16_mm'], tr['norm_17_32_mm'], tr['norm_33_48_mm'], truth_summary['beyond_band_rms_m']*1e3))
