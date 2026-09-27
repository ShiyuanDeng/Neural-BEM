"""Audit frozen receipts and decisions without rerunning or selecting fits."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    checks = []

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    def read(path):
        return json.loads(path.read_text())

    for path in [*HERE.glob('*manifest.json'), HERE / 'dependency_audit.json']:
        receipt = read(path)
        for group in ('source_sha256', 'input_sha256'):
            for filename, expected in receipt.get(group, {}).items():
                check(hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == expected,
                      f'{path.name}: unchanged {filename}')
    records = [read(p) for p in sorted((HERE / 'runs').glob('*/*/result.json'))]
    check(len(records) == 12, 'twelve strategy endpoints')
    units = 0
    for row in records:
        name = f"{row['case']}/{row['arm']}"
        work = row['work']
        check(work['work_units'] == sum(work['solves'].values()) + sum(work['reciprocal_batches'].values()),
              name + ': full ledger sum')
        check(work['work_units'] <= 400 and work['seconds'] <= 1200, name + ': declared budget')
        check(row['audit']['passed'] and max(row['audit']['discrepancy']) <= 1e-6,
              name + ': qualified final endpoint')
        check(row['score']['valid'], name + ': valid geometry')
        check(row['final_state'] == row['accepted'][-1]['state'], name + ': actual returned state')
        for record in row['records']:
            suffix = name + f"/dispatch_{record['dispatch']}"
            check(record['final_loss'] <= record['initial_loss'] + 1e-14,
                  suffix + ': accepted trajectory never increases objective')
            for receipt in record['checks']:
                if receipt.get('accepted'):
                    check(receipt['refined_gain'] > receipt['margin'], suffix + ': refined descent')
            if row['arm'] == 'conditional':
                scores = record['nomination']['object_scores']
                check(record['active'] == [max(range(len(scores)), key=scores.__getitem__)],
                      suffix + ': nomination follows prospective rule')
        units += work['work_units']
    summary = read(HERE / 'summary.json')
    check(len(summary['strategies']) == 4 and not any(r['superiority_gate'] for r in summary['strategies']),
          'all four frozen strategy gates fail')
    topology = read(HERE / 'topology.json')
    check(topology['status'] == 'COMPLETE' and len(topology['cases']) == 4, 'topology screen complete')
    check(not topology['topology_actions_enabled'], 'topology remains diagnostic only')
    check(topology['false_birth_controls']['wrong_boundary'], 'false birth retained')
    check(topology['work']['attempted'] <= 600 and topology['seconds'] <= 1200, 'topology budget')
    for name, row in topology['cases'].items():
        check(row['refinement']['audit']['passed'], name + ': shape endpoint qualified')
        for phase in ('before', 'after'):
            check(row[phase]['finite_birth_refinement'] <= 1e-6, name + '/' + phase + ': finite birth qualified')
    result = dict(passed=True, checks=len(checks), strategy_units=units, labels=checks)
    (HERE / 'evidence_checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'labels'}))


if __name__ == '__main__':
    main()
