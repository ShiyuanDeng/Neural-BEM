import json, sys, numpy as np
from pathlib import Path
from experiments.shape_continuation import spd_cases as sc
p = sc.spd_modules()[0].p
root = Path(__file__).resolve().parents[1] / 'runs'
for arm_case in sys.argv[1:]:
    arm, case = arm_case.split(':')
    f = root/arm/case
    r = json.loads((f/'result.json').read_text())
    last = sorted(f.glob('stage_*'))[-1]
    t = json.loads((last/'terminal.json').read_text())
    st = p.driver.deserialize_state(json.loads((f/'final_state.json').read_text()))
    c = st.components[0]
    pts = p.boundary_points(st, 4096)[0]
    actual = 1e3*np.min(np.linalg.norm(pts-np.asarray(c.center), axis=1))
    rows = [json.loads(l) for l in (last/'jacobians.jsonl').read_text().splitlines()]
    print(arm, case, r['status'], r['reason'], 'stage', last.name, 'K', c.maximum_mode,
          '| certificate mm %.3f actual min centre distance mm %.2f star-shaped %s' % (1e3*c.minimum_radius_lower_bound_m, actual, c.is_star_shaped_about_center),
          '| last jac unresolved/one-sided', rows[-1]['unresolved_columns'], rows[-1]['one_sided_columns'], '| reason:', t['reason'][:80])
