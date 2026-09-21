"""Read-back verification of selected entries, saved solves and release decision."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from .core import System, blocks, block_mask, relative, solve, data_derivatives


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    config = json.loads((args.bundle/'config.json').read_text())
    summary = json.loads((args.bundle/'summary.json').read_text())
    checks, cases = [], []
    drift = [p for p, h in config['sources_sha256'].items()
             if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    assert not drift, drift
    for path in sorted(args.bundle.glob('*/case.json')):
        case = json.loads(path.read_text())
        cases.append(case)
        with np.load(path.parent/'arrays.npz') as arr:
            a = arr['a']; r = a-np.eye(len(a))
            system = System(a, arr['b'], arr['c'], arr['receiver_rhs'], case['cutoff'])
            physical = case['physical_directions']
            deriv = {n: (arr['da'][i], arr['db'][i], arr['dc'][i]) for i,n in enumerate(physical)}
            scale = max(np.linalg.norm(y) for y in arr['oracle_dy'])
            for row in case['scans']:
                mask = arr['mask_'+row['key']]
                expected = block_mask(r, row['tolerance'])
                if row['arm']=='common':
                    expected |= np.logical_or.reduce([block_mask(v[0],row['tolerance']) for v in deriv.values()])
                assert np.array_equal(mask, expected)
                assert mask.sum()+len(a)==row['represented_slots']
                sol = solve(system, mask)
                dy = data_derivatives(system, deriv, sol, mask)
                field = relative(sol['y'], arr['oracle_y'])
                worst = max(relative(dy[n], arr['oracle_dy'][i], max(1e-8*scale,1e-300))
                            for i,n in enumerate(physical))
                assert np.isclose(field,row['field_error'],rtol=1e-8,atol=1e-13)
                assert np.isclose(worst,row['worst_derivative_error'],rtol=1e-8,atol=1e-13)
                passed = bool(case['qualified'] and field<=1e-6 and worst<=1e-3
                              and row['represented_fraction']<=.5)
                assert passed==row['passed']
                checks.append(dict(case=path.parent.name,key=row['key'],passed=passed))
    qualifying = [n for n in ('ellipse','asymmetric_star','crescent')
                  if all(any(c['name']==n and c['kd']==kd and c['winner'] for c in cases) for kd in (2,10))]
    assert qualifying==summary['qualifying_noncircles']
    assert summary['stage_b_released']==bool(summary['status']=='COMPLETE' and len(qualifying)>=2)
    result = dict(status='PASS',source_drift=drift,recomputed_solve_rows=len(checks),
                  qualifying_noncircles=qualifying,stage_b_released=summary['stage_b_released'])
    (args.bundle/'readback.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
