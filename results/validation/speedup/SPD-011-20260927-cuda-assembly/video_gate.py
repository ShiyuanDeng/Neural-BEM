"""SPD-011 gate 4: compare GPU-prepared latest_vs_hybrid records with the committed CPU ones.

The unchanged renderer is run separately with SC_FORWARD_BACKEND=cuda and a
fresh --output folder, so no committed display cache is reused. This script
compares every displayed diagnostic field state by state.

    python video_gate.py GPU_OUTPUT OUT.json
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
CPU = ROOT / 'results/validation/shape_continuation/videos/latest_vs_hybrid/prepared'
CASES = ('wrong_circle', 'circle_to_star', 'circle_to_c', 'kite', 'peanut', 'hook')
FLOATS = ('heat', 'column', 'misfit', 'rms_mm', 'x', 'y')
INTEGERS = ('front', 'front_joint', 'frontier_changes')


def relative(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.max(np.abs(a - b)) / max(np.max(np.abs(b)), 1e-300))


def main(gpu_output, out):
    rows = {}
    for case in CASES:
        cpu = json.loads((CPU / f'{case}.json').read_text())
        gpu = json.loads((Path(gpu_output) / 'prepared' / f'{case}.json').read_text())
        assert [len(t) for t in cpu['tracks']] == [len(t) for t in gpu['tracks']]
        floats = {k: 0.0 for k in FLOATS}
        integer_changes = {k: 0 for k in INTEGERS}
        log_heat = 0.0
        for cpu_track, gpu_track in zip(cpu['tracks'], gpu['tracks']):
            for a, b in zip(cpu_track, gpu_track):
                assert a['label'] == b['label'] and a['shot'] == b['shot']
                for key in FLOATS:
                    floats[key] = max(floats[key], relative(b[key], a[key]))
                for key in INTEGERS:
                    integer_changes[key] += int(np.sum(np.asarray(a[key]) != np.asarray(b[key])))
                clip = lambda v: np.log10(np.maximum(np.asarray(v, float), 1e-6))
                log_heat = max(log_heat, float(np.max(np.abs(clip(a['heat']) - clip(b['heat'])))))
        rows[case] = dict(states=[len(t) for t in cpu['tracks']], max_relative=floats,
            integer_changes=integer_changes, max_displayed_log10_heat_difference=log_heat,
            cpu_checks=cpu['checks'], gpu_checks=gpu['checks'],
            cpu_seconds=cpu['seconds'], gpu_seconds=gpu['seconds'],
            cpu_work=cpu['diagnostic_work'], gpu_work=gpu['diagnostic_work'])
        print(case, json.dumps(dict(max_relative=floats, integer_changes=integer_changes,
              log_heat=log_heat, seconds=(round(cpu['seconds'], 1), round(gpu['seconds'], 1)))), flush=True)
    # The renderer itself asserts saved-loss agreement and endpoint RMS; misfit is
    # reported, not thresholded, because converged misfits (~1e-7) amplify roundoff.
    passed = all(sum(r['integer_changes'].values()) == 0 and r['max_displayed_log10_heat_difference'] <= 1e-6
                 and r['max_relative']['rms_mm'] == 0.0 for r in rows.values())
    Path(out).write_text(json.dumps(dict(passed=passed, cases=rows,
        criteria='renderer assertions pass; no frontier/integer changes; displayed log10 heat within 1e-6; '
                 'curve RMS identical'), indent=1))
    print('PASSED' if passed else 'FAILED')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
