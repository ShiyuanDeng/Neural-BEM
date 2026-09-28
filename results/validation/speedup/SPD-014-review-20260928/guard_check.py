"""Check the proposed SPD-014 guard on the fuzz set, without editing the solver.

Proposed rule: take the dense reference whenever cross_tolerance is below a
bound on cross-product roundoff, 8 * eps * Lmax * diameter. Above it, a
computed 'proper' crossing implies a true crossing, so pruning is exact.

    python guard_check.py fuzz.json OUT.json
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'solvers'), str(Path(__file__).resolve().parent)]
from fuzz import main as _unused, resolved  # noqa: E402,F401
import fuzz  # noqa: E402
from ordered_boundary.spatial_validation import spatial_self_intersection_count  # noqa: E402
from ordered_boundary.validation import _dense_self_intersection_count  # noqa: E402


def guarded(points, cross, length):
    deltas = np.roll(points, -1, axis=0) - points
    diameter = float(np.linalg.norm(np.ptp(points, axis=0)))
    bound = 8 * np.finfo(float).eps * float(np.max(np.linalg.norm(deltas, axis=1))) * diameter
    if not cross >= bound:
        return _dense_self_intersection_count(points, cross, length), 'dense-guard'
    return spatial_self_intersection_count(points, cross, length, fallback=_dense_self_intersection_count), 'spatial'


def main(out):
    rng = np.random.default_rng(280928)
    # Rebuild exactly the fuzz cases by re-running the generator's recipe via its module.
    captured = []
    original = fuzz.counts
    fuzz.counts = lambda points, cross, length: captured.append((points.copy(), cross, length)) or \
        {'reference': 0, 'spatial': 0}
    fuzz.main('/dev/null')
    fuzz.counts = original
    rows = []
    for points, cross, length in captured:
        points = np.ascontiguousarray(points, float)
        reference = _dense_self_intersection_count(points, cross, length)
        value, path = guarded(points, cross, length)
        rows.append(dict(equal=value == reference, path=path, reference=reference, guarded=value,
                         relative_zero=cross == 0.0))
    summary = dict(comparisons=len(rows), all_equal=all(r['equal'] for r in rows),
                   guard_fallbacks=sum(r['path'] == 'dense-guard' for r in rows),
                   guard_fallbacks_at_nonzero_tolerance=sum(r['path'] == 'dense-guard' and not r['relative_zero']
                                                             for r in rows))
    Path(out).write_text(json.dumps(dict(summary, rows=rows), indent=1))
    print(summary)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'guard_check.json')
