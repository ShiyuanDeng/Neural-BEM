"""RD-4: how many arclength storage modes do the saved states actually need? Zero field solves.

For a curve, err(K) is the max distance (mm) between its uniform-arclength samples and their band-K
Fourier projection (`geometry.reparameterize` with no tolerance gate). K_eff(eps) is the smallest K with
err(K) <= eps. Bernstein's inequality for a degree-K trigonometric polynomial gives, for an
arclength-parameterized band-K curve, curvature <= 2 pi K / L, i.e. radius >= L / (2 pi K).
States: the six truths (reference only), hybrid R0 stage 1 (SC-029 baseline), hybrid with first band
M=2 (SC-029 protect), and SPD-L stage 1 (SC-034 arm L). Run: PYTHONPATH=solvers:. python <this file>
"""
import json
from pathlib import Path

import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import reparameterize

HERE = Path(__file__).resolve().parent
R0 = sc.ROOT / 'results/validation/shape_continuation/SC-029-atlas-strategies/runs'
SPDL = sc.ROOT / 'results/validation/shape_continuation/SC-034-spd-legacy-controls/runs/L'
KS = (3, 4, 6, 8, 12, 16, 24, 32, 48, 64)
EPS = (0.01, 0.05, 0.2)
L = sc.LENGTH


def profile(curve):
    errs = {}
    for k in KS:
        try:
            errs[k] = float(1e3 * L * reparameterize(curve, k, tolerance=np.inf)[1])
        except ValueError:
            errs[k] = float('nan')
    nodes = curve.nodes(8192)
    perimeter_mm = float(1e3 * L * nodes.perimeter)
    radius_mm = float(1e3 * L / np.max(np.abs(nodes.curvatures)))
    keff = {str(e): next((k for k in KS if errs[k] <= e), None) for e in EPS}
    return dict(err_mm=errs, K_eff=keff, radius_mm=radius_mm, perimeter_mm=perimeter_mm,
                bernstein_K_for_radius=perimeter_mm / (2 * np.pi * radius_mm))


def main():
    p = sc.spd_modules()[0].p
    out, lines = {}, []
    for case in ast.CASES:
        truth = ast.curve_from(json.loads((ast.source_folder(case) / 'truth.json').read_text()))
        t = profile(truth)
        paths = {}
        for prefix in ('baseline', 'protect'):
            items = json.loads((R0 / prefix / case / 'none' / 'stage_1_history.json').read_text())['history']
            paths[f'hybrid_{prefix}'] = [profile(ast.curve_from(i['coefficients'])) for i in items]
        rows = [json.loads(l) for l in (SPDL / case / 'stage_1' / 'trajectory.jsonl').read_text().splitlines()]
        paths['spd_l'] = [profile(sc.from_cartesian(p.driver.deserialize_state(r['state']).components[0])) for r in rows]
        out[case] = dict(truth=t, **paths)
        lines.append(f"{case}: truth radius {t['radius_mm']:.1f} mm, perimeter {t['perimeter_mm']:.0f} mm; "
                     f"err(K) mm " + ' '.join(f"K{k}:{t['err_mm'][k]:.3g}" for k in KS[:8])
                     + f"; K_eff(0.01/0.05/0.2 mm) = {t['K_eff']['0.01']}/{t['K_eff']['0.05']}/{t['K_eff']['0.2']}")
        for name, path in paths.items():
            lines.append(f"  {name:15s} radius: " + ' '.join(f"{s['radius_mm']:.1f}" for s in path))
            lines.append(f"  {'':15s} K_eff(0.05 mm): " + ' '.join(str(s['K_eff']['0.05']) for s in path))
            lines.append(f"  {'':15s} err(K=8) mm: " + ' '.join(f"{s['err_mm'][8]:.2g}" for s in path))
    (HERE / 'audit.json').write_text(json.dumps(out, indent=2) + '\n')
    (HERE / 'audit.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
