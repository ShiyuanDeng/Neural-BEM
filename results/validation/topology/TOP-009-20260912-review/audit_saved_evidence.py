"""Audit TOP-009's saved records without importing a solver or running an inverse.

Usage: python audit_saved_evidence.py --output /tmp/top009-review.json
The output must be new; historical experiment artifacts are only read.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BUNDLE = ROOT / 'results/validation/topology/TOP-009-20260912-bandwidth-capacity'
SPEC = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd/scene_spec.json'


def main(output):
    inputs = [BUNDLE / name for name in (
        'stage2_climb.json', 'stage3_correction.json', 'stage4_uncapped_ladder.json')]
    stage2, stage3, stage4 = [json.loads(path.read_text()) for path in inputs]
    spec = json.loads(SPEC.read_text())
    promotion = next(arm for arm in stage2['arms'] if arm['arm'] == 'promotion')
    rungs = [r for r in stage4['rungs'] if r['retained']]
    # This conversion holds for this single-frequency, unit-weight acquisition.
    # Cross-check it against an independently stored relative error before use.
    assert len(spec['training_frequencies_hz']) == 1
    assert math.isclose(math.sqrt(2 * promotion['refined_loss']),
                        promotion['refined_relative_error'], rel_tol=1e-12)
    tolerance = spec['controller']['relative_error_tolerance']
    first_below = next(r for r in rungs
                       if math.sqrt(2 * r['production_after']) <= tolerance)
    values = [stage2['start_geometry']['maximum_matched_hausdorff_m']]
    values += [r['matched_hausdorff_m'] for r in promotion['rungs'] if r['retained']]
    decreases = [dict(from_rung=i, to_rung=i + 1, before_m=a, after_m=b)
                 for i, (a, b) in enumerate(zip(values, values[1:])) if b < a]
    sources = inputs + [SPEC, Path(__file__),
        ROOT / 'solvers/sdf_inverse/radial_topology.py',
        ROOT / 'solvers/sdf_inverse/topology_controller.py',
        ROOT / 'solvers/sdf_inverse/optimization.py',
        BUNDLE / 'stage4_uncapped_ladder.py']
    report = dict(
        scope='Saved-artifact and source review; no forward solve or inverse run.',
        reviewed_experiment_commit='ab10e400d62ad173d3799dc4660eec4112f6dfd2',
        source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sources},
        retained_rungs=len(rungs),
        optimizer_stop_reasons=dict(Counter(r['optimizer_stop_reason'] for r in rungs)),
        terminal_optimizer_stop_reason=rungs[-1]['optimizer_stop_reason'],
        final_modes=stage4['final_modes'],
        final_relative_l2_from_loss=math.sqrt(2 * stage4['final_production_loss']),
        final_over_truth_loss_ratio=stage4['final_production_loss'] / stage3['truth_production_loss'],
        controller_relative_error_tolerance=tolerance,
        first_saved_rung_below_controller_tolerance=dict(
            modes=first_below['modes'],
            relative_l2_from_loss=math.sqrt(2 * first_below['production_after']),
            matched_hausdorff_m=first_below['matched_hausdorff_m']),
        final_matched_hausdorff_m=stage4['final_geometry']['maximum_matched_hausdorff_m'],
        final_worst_holdout_relative_error=stage4['final_worst_holdout_relative_error'],
        stage2_boundary_error_monotonically_worsens=not decreases,
        stage2_boundary_error_improvements=decreases,
        interpretation_limits=[
            'Small loss change does not certify a small gradient or a local minimum.',
            'An accurate truth forward response does not prove uniqueness or stable recovery.',
            'A saved rung below the controller threshold would satisfy its data stop; '
            'this is not a replay of the full controller trajectory.',
            'Truth-selected rotations are geometry diagnostics, not training-selected proposals.',
        ])
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'source_sha256'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
