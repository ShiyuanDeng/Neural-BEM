"""SPD-012: compare two replays' recorded runs value by value (timing keys excluded).

    python determinism.py NEW_RUNS REFERENCE_RUNS OUT.json
Each argument is a runs/ folder; every JSON file under NEW_RUNS is compared
with the file at the same relative path under REFERENCE_RUNS.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'SPD-013-20260927-cuda-multicomponent'))
from replay_multi import compare_values  # noqa: E402  (excludes seconds, preparation_seconds, trial_seconds)


def main(new, reference, out):
    new, reference = Path(new), Path(reference)
    rows = {}
    for path in sorted(new.rglob('*.json')):
        report = dict(leaves=0, numeric_differences=0, max_relative=0.0, differences=[])
        compare_values(json.loads((reference / path.relative_to(new)).read_text()),
                       json.loads(path.read_text()), str(path.relative_to(new)), report)
        rows[str(path.relative_to(new))] = dict(identical=not report['differences'], leaves=report['leaves'],
                                                numeric_differences=report['numeric_differences'],
                                                max_relative=report['max_relative'],
                                                first_differences=report['differences'][:3])
    summary = dict(all_identical=all(r['identical'] for r in rows.values()),
                   leaves=sum(r['leaves'] for r in rows.values()), files=rows)
    Path(out).write_text(json.dumps(summary, indent=1))
    print('IDENTICAL' if summary['all_identical'] else 'DIFFERENT', summary['leaves'], 'values in', len(rows), 'files')


if __name__ == '__main__':
    main(*sys.argv[1:4])
