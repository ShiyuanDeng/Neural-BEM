"""Replay TOP-022 including its frozen negative comparison; no solver imports."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top020 import summarize as base


def verify_comparison(output):
    record = base.read(output/'staged_comparison.json')
    assert record == base.read(output/'manifest.json')['staged_comparison']
    folder = ROOT/record['path']
    for name in ('artifact_manifest', 'result', 'verification'):
        assert base.digest(folder/(name+'.json')) == record[name+'_sha256']
    assert base.read(output/'contract.json')['stage_plan'] == [[4, 8000]]
    result = base.read(output/'result.json')
    if 'fresh_prefix_reproducibility' in result:
        check = result['fresh_prefix_reproducibility']
        assert check['status'] == 'PASS' and not check['archived_state_used_for_fitting']
        assert check['computed_state_sha256'] == check['comparison_state_sha256'] == record['topology_state_sha256']
        assert check['computed_state_sha256'] == base.state_hash(base.read(output/'topology/terminal.json')['final_state'])
    if result['fresh_recovery_pass']:
        assert result['fresh_prefix_reproducibility']['status'] == 'PASS'
    return dict(status='PASS', new_physical_solves=0)


def summarize(output):
    verify_comparison(output)
    return base.summarize(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(summarize(parser.parse_args().output.resolve())))
