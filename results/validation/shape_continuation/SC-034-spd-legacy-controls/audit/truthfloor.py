import numpy as np
from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from sdf_inverse.radial_topology import component_radius_floor
for case in ast.CASES:
    truth = ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    z = truth.values(8192)*sc.LENGTH + sc.CENTER
    comp = sc.to_cartesian(truth, 'truth')
    centre = np.asarray(comp.center)
    d = 1e3*np.min(np.abs(z - (centre[0]+1j*centre[1])))
    try:
        from sdf_inverse.curve_updates import polar_angle_gauge_fixed_point
        g,_ = polar_angle_gauge_fixed_point(comp)
        cert = 1e3*component_radius_floor(g); star = g.is_star_shaped_about_center
    except Exception as e:
        cert, star = None, repr(e)[:60]
    print(case, 'band', truth.band, 'truth min centre distance mm %.2f' % d, 'certificate mm', cert if cert is None else round(cert,3), 'star about centre', star)
