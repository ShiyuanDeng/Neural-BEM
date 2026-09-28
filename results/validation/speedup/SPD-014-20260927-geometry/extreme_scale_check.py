"""Post-timing check of pruning under floating-point norm underflow."""
import json
from pathlib import Path
import numpy as np
from ordered_boundary import sampled_self_intersection_count
from ordered_boundary.validation import _self_intersection_count
from ordered_boundary.validation_cache import intersection_validation

OUT = Path('results/validation/speedup/SPD-014-20260927-geometry')
rng = np.random.default_rng(14015)
theta = np.linspace(0, 2*np.pi, 512, endpoint=False)
polygons = {
    'circle': np.column_stack((np.cos(theta), np.sin(theta))),
    'bowtie': np.array([[0., 0.], [1., 1.], [0., 1.], [1., 0.]]),
    'folded': rng.normal(size=(127, 2)),
}
rows = []
for name, polygon in polygons.items():
    for scale in (1e-300, 1e-200, 1e-170, 1e-162, 1e-155, 1e-100):
        points = polygon*scale
        for kind in ('public_zero', 'public_default', 'resolved_zero'):
            results = {}
            for backend in ('reference', 'spatial'):
                with intersection_validation(backend), np.errstate(all='ignore'):
                    try:
                        if kind == 'resolved_zero':
                            value = _self_intersection_count(points, 0., 0.)
                        else:
                            value = sampled_self_intersection_count(
                                points, relative_tolerance=0. if kind == 'public_zero' else 1e-12)
                        results[backend] = {'count': value}
                    except ValueError as error:
                        results[backend] = {'error': str(error)}
            equal = results['reference'] == results['spatial']
            rows.append(dict(polygon=name, scale=scale, kind=kind, results=results, passed=equal))
            assert equal, rows[-1]
report = dict(passed=True, comparisons=len(rows), rows=rows)
(OUT/'extreme_scale_check.json').write_text(json.dumps(report, indent=1)+'\n')
print(f'{len(rows)} exact extreme-scale count/error comparisons passed')
