"""Rebuild the SC-048 decision table and figures from completed receipts."""
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from run import HERE, ROOT, ARMS, gate, load_scene
from qualify import LENGTH


def read(path):
    return json.loads(path.read_text())


def draw(ax, state, **style):
    for i, curve in enumerate(state.components):
        z = curve.values(2048) * LENGTH * 1000
        ax.plot(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]],
                **({k: v for k, v in style.items() if k != 'label'} if i else style))


def main():
    summary = read(HERE / 'summary.json')
    if summary['status'] == 'RUNNING':
        raise RuntimeError('Wait for the frozen campaign to finish.')
    checks = []

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    frozen = read(HERE / 'manifest.json')
    for filename, expected in frozen['source_sha256'].items():
        check(hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == expected,
              'unchanged source: ' + filename)
    qualification = read(HERE / 'qualification.json')
    check(qualification['passed'], 'complete-trial qualification passes')
    check(qualification['work']['attempted'] <= 200 and qualification['seconds'] <= 600,
          'qualification budgets')
    rows = ['# SC-048 saved-result comparison', '',
            'Actual final endpoints; RMS in mm. Work includes endpoint qualification.', '',
            '| Case | Arm | Worst RMS | Ellipse RMS | C RMS | Work | Max dimensions | Outcome |',
            '|---|---|---:|---:|---:|---:|---:|---|']
    fig, axes = plt.subplots(len(summary['cases']), 3, figsize=(13, 3.4 * len(summary['cases'])),
                             squeeze=False, layout='constrained')
    cost = 0
    for i, case in enumerate(summary['cases']):
        name = case['case']
        inputs = read(HERE / 'inputs' / (name + '.json'))
        check(gate(case['arms']) == case['gate'], name + ': unchanged frozen gate')
        for j, arm in enumerate(ARMS):
            result = read(HERE / 'runs' / name / arm / 'result.json')
            work, score = result['work'], result['score']
            check(work['work_units'] == sum(work['solves'].values()) + sum(work['reciprocal_batches'].values()),
                  name + '/' + arm + ': complete work ledger')
            check(work['work_units'] <= 200 and work['seconds'] <= 900, name + '/' + arm + ': budgets')
            check(result['audit']['passed'] and max(result['audit']['discrepancy']) <= 1e-6,
                  name + '/' + arm + ': refined endpoint')
            check(result['final_state'] == result['states'][-1]['state'], name + '/' + arm + ': actual endpoint')
            for record in result['records']:
                check(record['final_loss'] <= record['initial_loss'] + 1e-14,
                      name + '/' + arm + ': accepted objective descent')
            cost += work['work_units']
            rms = [r['rms_mm'] for r in score['objects']]
            rows.append(f"| {name} | {arm} | {score['worst_rms_mm']:.6f} | {rms[0]:.6f} | {rms[1]:.6f} | "
                        f"{work['work_units']} | {result['maximum_dimension']} | {result['outcome']} |")
            ax = axes[i, j]
            draw(ax, load_scene(inputs['initial']), color='0.75', linewidth=1, label='start')
            draw(ax, load_scene(inputs['truth']), color='black', linestyle='--', linewidth=1.3, label='truth')
            draw(ax, load_scene(result['final_state']), color=('#0072B2', '#D55E00', '#009E73')[j],
                 linewidth=1.1, label=arm)
            ax.set_aspect('equal')
            ax.set_title(f"{name} · {arm}\n{score['worst_rms_mm']:.3f} mm · {work['work_units']} units", fontsize=10)
            ax.set(xlabel='x from scene centre (mm)', ylabel='y (mm)')
            ax.grid(alpha=.15)
            if i == 0 and j == 0:
                ax.legend(fontsize=8)
        rows.extend(['', f"Frozen superiority gate for **{name}: {case['gate']}**.", ''])
    if summary['status'] == 'PRIMARY_GATE_FAILED':
        check(len(summary['cases']) == 1, 'primary failure withholds transfers')
    fig.savefig(HERE / 'reconstructions.png', dpi=160)
    plt.close(fig)
    rows.extend([f'Total comparison work: **{cost} units**.', '',
                 'Qualification and data generation are charged separately in their own ledgers.', ''])
    (HERE / 'TABLES.md').write_text('\n'.join(rows))
    evidence = dict(passed=True, checks=len(checks), labels=checks, strategy_units=cost,
        input_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (HERE / 'inputs').glob('*.json')},
        note='Input hashes captured at closeout; source hashes checked against the pre-dispatch manifest.')
    (HERE / 'evidence_checks.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(dict(status=summary['status'], checks=len(checks), strategy_units=cost)))


if __name__ == '__main__':
    main()
