"""TOP-012 stage 4: per gate, on all twelve scenes, v2 arm H against v1 arm H.

The v1 side is read from the [TOP-008](../TOP-008-20260912-feasible-fd/README.md)
bundle and is never re-run, re-scored or touched. No result here transfers back
to v1: this is a separately named comparison against an immutable record.

A pass-count change is the headline. Boundary error, IoU, training and held-out
error are reported separately, and the enriched arm reports what it cost in
solves. Timeouts are reported apart from gate failures, because a scene that ran
out of wall clock has not said anything about information.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark  # noqa: E402
import run_fourier_topology_controller as driver  # noqa: E402

SUITE = HERE / 'suite'
V1 = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
ARM = 'H'
GATE_NAMES = ('correct_count', 'boundary', 'overlap', 'training', 'holdout',
              'monotone_accepted_states', 'all_event_margins_pass')


def side(bundle):
    metrics = benchmark.read(bundle / 'suite_metrics.json')
    rows = {r['scene']: r for r in metrics['metrics'] if r['arm'] == ARM}
    failures = {f['scene']: f for f in metrics['failures'] if f['arm'] == ARM}
    return metrics, rows, failures


def scene_row(scene, rows, failures):
    if scene in rows:
        row = rows[scene]
        return dict(status='completed', passed=bool(row['passed']), gates=row['gates'],
                    matched_hausdorff_mm=(row['geometry']['maximum_matched_hausdorff_m'] * 1.0e3
                                          if row['geometry']['maximum_matched_hausdorff_m']
                                          is not None else None),
                    union_iou=row['geometry']['union_iou'],
                    component_count=row['geometry']['component_count'],
                    refined_relative_error=row['refined_relative_error'],
                    maximum_holdout_relative_error=row['maximum_holdout_relative_error'],
                    bie_frequency_solve_count=row['work']['totals']['bie_frequency_solve_count'],
                    inversion_seconds=row['inversion_seconds'])
    return dict(status=failures.get(scene, {}).get('reason', 'missing'), passed=False)


def main():
    spec = benchmark.read(SUITE / 'scene_spec.json')
    v1_metrics, v1_rows, v1_failures = side(V1)
    v2_metrics, v2_rows, v2_failures = side(SUITE)

    scenes = []
    for scene in spec['scenes']:
        before = scene_row(scene['id'], v1_rows, v1_failures)
        after = scene_row(scene['id'], v2_rows, v2_failures)
        scenes.append(dict(scene=scene['id'], group=scene['group'], v1=before, v2=after,
                           pass_change=('gained' if after['passed'] and not before['passed']
                                        else 'lost' if before['passed'] and not after['passed']
                                        else 'unchanged'),
                           gate_changes=[name for name in GATE_NAMES
                                         if before.get('gates', {}).get(name)
                                         != after.get('gates', {}).get(name)]
                           if before['status'] == after['status'] == 'completed' else None))

    def counts(rows, failures):
        return dict(passed=sum(1 for r in rows.values() if r['passed']),
                    completed=len(rows), timeouts=sum(1 for f in failures.values()
                                                      if f['reason'] == 'timeout'),
                    other_failures=sum(1 for f in failures.values() if f['reason'] != 'timeout'),
                    bie_frequency_solve_count=sum(
                        r['work']['totals']['bie_frequency_solve_count'] for r in rows.values()))

    record = dict(
        arm=ARM, scenes_total=len(spec['scenes']),
        v1=dict(bundle=str(V1.relative_to(ROOT)), spec_version=v1_metrics['spec_version'],
                acquisition=None, **counts(v1_rows, v1_failures)),
        v2=dict(bundle=str(SUITE.relative_to(ROOT)), spec_version=v2_metrics['spec_version'],
                acquisition=spec.get('acquisition'), **counts(v2_rows, v2_failures)),
        per_scene=scenes,
        gained=[s['scene'] for s in scenes if s['pass_change'] == 'gained'],
        lost=[s['scene'] for s in scenes if s['pass_change'] == 'lost'],
        comparable=[s['scene'] for s in scenes
                    if s['v1']['status'] == s['v2']['status'] == 'completed'],
        v1_only_completed=[s['scene'] for s in scenes
                           if s['v1']['status'] == 'completed' != s['v2']['status']],
        v2_only_completed=[s['scene'] for s in scenes
                           if s['v2']['status'] == 'completed' != s['v1']['status']],
        v1_bundle_untouched=True)
    driver.write_json(HERE / 'stage4_comparison.json', record)

    print('=== stage 4: arm H, twelve frozen scenes, v1 versus v2 acquisition ===')
    print(f"  passed {record['v1']['passed']}/12 -> {record['v2']['passed']}/12")
    print(f"  completed {record['v1']['completed']} -> {record['v2']['completed']}  ·  "
          f"timeouts {record['v1']['timeouts']} -> {record['v2']['timeouts']}")
    print(f"  BIE frequency solves {record['v1']['bie_frequency_solve_count']} -> "
          f"{record['v2']['bie_frequency_solve_count']}")
    print(f"  gained {record['gained'] or 'none'}  ·  lost {record['lost'] or 'none'}")
    print(f"\n  {'scene':24s} {'v1':>22s}   {'v2':>22s}")
    for row in scenes:
        def cell(side_row):
            if side_row['status'] != 'completed':
                return f"{side_row['status']:>22s}"
            mark = 'PASS' if side_row['passed'] else 'fail'
            hausdorff = ('   n/a' if side_row['matched_hausdorff_mm'] is None
                         else f"{side_row['matched_hausdorff_mm']:6.2f}")
            return f"{mark} {hausdorff} mm IoU {side_row['union_iou']:.3f}"
        print(f"  {row['scene']:24s} {cell(row['v1'])}   {cell(row['v2'])}")


if __name__ == '__main__':
    main()
