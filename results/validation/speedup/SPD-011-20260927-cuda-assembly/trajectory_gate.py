"""SPD-011 gate 3: CUDA replays of SC-043 fixed runs against the CPU archive.

Run the replay first (SPD-010's replay.py with SC_FORWARD_BACKEND=cuda). The
gate requires the same outcome, per-block outcome/stop/M/units and total units,
and endpoint RMS within 1e-6 relative. Numeric drift is reported, not tuned.

    python trajectory_gate.py REPLAY_DIR OUT.json
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
ARCHIVE = ROOT / 'results/validation/shape_continuation/SC-043-prospective-band/runs'
RMS_LIMIT = 1e-6


def block_signature(result):
    return [{k: s[k] for k in ('block', 'M', 'outcome', 'stop', 'units', 'total_units')} for s in result['stages']]


def main(replay_dir, out):
    replay_dir = Path(replay_dir)
    comparison = json.loads((replay_dir / 'comparison.json').read_text())
    replay = json.loads((replay_dir / 'replay.json').read_text())
    rows = {}
    for case in replay['cases']:
        archived = json.loads((ARCHIVE / case / replay['policy'] / 'result.json').read_text())
        fresh = json.loads((replay_dir / 'runs' / case / replay['policy'] / 'result.json').read_text())
        accepted = [json.loads((root / case / replay['policy'] / 'accepted.json').read_text())['states']
                    for root in (ARCHIVE, replay_dir / 'runs')]
        rms = abs(fresh['score']['rms_mm'] - archived['score']['rms_mm']) / archived['score']['rms_mm']
        files = comparison['cases'][case]['files']
        rows[case] = dict(
            outcome=(archived['outcome'], fresh['outcome']),
            blocks_equal=block_signature(archived) == block_signature(fresh),
            total_units=(archived['total_units'], fresh['total_units']),
            accepted_states=(len(accepted[0]), len(accepted[1])),
            accepted_iterations_equal=[(s['block'], s['iteration']) for s in accepted[0]]
                                      == [(s['block'], s['iteration']) for s in accepted[1]],
            rms_mm=(archived['score']['rms_mm'], fresh['score']['rms_mm']), rms_relative=rms,
            audit_passed=fresh['audit_passed'],
            seconds=(archived['seconds'], fresh['seconds']), speedup=archived['seconds'] / fresh['seconds'],
            numeric_differences={name: f.get('numeric_differences') for name, f in files.items()},
            max_relative_numeric={name: f.get('max_relative') for name, f in files.items()},
            non_numeric_differences=sum(1 for f in files.values() for d in f.get('differences', [])
                                        if d['kind'] != 'number'),
            bit_identical=comparison['cases'][case]['identical'])
        rows[case]['passed'] = bool(rows[case]['outcome'][0] == rows[case]['outcome'][1] and rows[case]['blocks_equal']
                                    and rows[case]['total_units'][0] == rows[case]['total_units'][1]
                                    and rms <= RMS_LIMIT and fresh['audit_passed'])
        r = rows[case]
        print(case, 'PASS' if r['passed'] else 'FAIL', f"{r['seconds'][0]:.1f} -> {r['seconds'][1]:.1f} s "
              f"({r['speedup']:.1f}x)", 'rms rel %.1e' % rms, 'units', r['total_units'],
              'accepted', r['accepted_states'], 'bit-identical' if r['bit_identical'] else '', flush=True)
    passed = all(r['passed'] for r in rows.values())
    Path(out).write_text(json.dumps(dict(passed=passed, rms_limit=RMS_LIMIT, cases=rows,
        environment=replay['environment'], host_load=replay['host_load'], wall_seconds=replay['wall_seconds'],
        workers=replay['workers']), indent=1))
    print('PASSED' if passed else 'FAILED')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
