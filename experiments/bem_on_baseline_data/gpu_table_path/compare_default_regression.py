"""Compare the saved CPU reference numerics and decisions, excluding clocks."""
import json
import argparse
from pathlib import Path
import numpy as np

BASE=Path(__file__).resolve().parents[3]/'results/bem/baseline_data/gpu_table_path/2026-11-18'
KEYS=('outcome','detail','contrast_start','contrast','final_curve','final_stage','stages','decisions',
      'fit_work','frequencies_hz','noise_sigma_declared','work','residual','maximum_residual','residual_resolution')


def stable(value):
    if isinstance(value,dict):
        return {k:stable(v) for k,v in value.items()
                if 'seconds' not in k and k not in ('elapsed','started','timestamp')
                and not (k in ('table_mode','ragged_data') and v is False)}
    if isinstance(value,list):return [stable(v) for v in value]
    return value


def cpu_comparison():
    arrays={}
    with np.load(BASE/'cpu_before/fit.npz') as before,np.load(BASE/'cpu_after/fit.npz') as after:
        assert set(before.files)==set(after.files)
        for key in before.files:
            arrays[key]=dict(bit_identical=bool(before[key].dtype==after[key].dtype and
                before[key].shape==after[key].shape and before[key].tobytes()==after[key].tobytes()),
                shape=list(before[key].shape))
    before=json.loads((BASE/'cpu_before/fit.json').read_text());after=json.loads((BASE/'cpu_after/fit.json').read_text())
    keys=('outcome','detail','contrast_start','contrast','final_curve','final_stage','stages','decisions',
          'fit_work','frequencies_hz','noise_sigma_declared','work','residual','maximum_residual','residual_resolution')
    checks={k:stable(before[k])==stable(after[k]) for k in keys}
    record=dict(arrays=arrays,stable_records_identical=checks,
                passes=all(a['bit_identical'] for a in arrays.values()) and all(checks.values()),
                excluded='clock fields; added default-false options; execution timing receipts')
    (BASE/'cpu_comparison.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
    assert record['passes'],'Default CPU reference changed; report to the coordinator.'


def numeric_and_structure(value):
    """Compare all stable record numerics, retaining strings, shapes and decisions."""
    numeric = []
    def walk(item):
        if isinstance(item, dict):
            return {k: walk(v) for k, v in sorted(item.items())}
        if isinstance(item, list):
            return [walk(v) for v in item]
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            numeric.append(item)
            return '<number>'
        return item
    structure = walk(stable(value))
    return np.array(numeric, dtype=float), structure


def difference(a, b):
    assert a.shape == b.shape and a.dtype == b.dtype
    delta = np.abs(a-b)
    return dict(max_absolute=float(delta.max(initial=0.)),
                relative_l2=float(np.linalg.norm(delta)/max(np.linalg.norm(a), np.finfo(float).tiny)),
                bit_identical=a.tobytes()==b.tobytes())


def gpu_difference(second):
    metrics = {}
    with np.load(BASE/'gpu_before_1/fit.npz') as before, np.load(BASE/second/'fit.npz') as after:
        assert set(before.files) == set(after.files)
        for key in before.files:
            metrics['array:'+key] = difference(before[key], after[key])
    before = json.loads((BASE/'gpu_before_1/fit.json').read_text())
    after = json.loads((BASE/second/'fit.json').read_text())
    stable_equal = {}
    for key in KEYS:
        a, sa = numeric_and_structure(before[key])
        b, sb = numeric_and_structure(after[key])
        assert sa == sb, f'Stable record structure/decision changed: {key}'
        metrics['record:'+key] = difference(a, b)
        stable_equal[key] = stable(before[key]) == stable(after[key])
    return dict(metrics=metrics, stable_records_identical=stable_equal)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['gpu-repeatability', 'after'])
    args = parser.parse_args()
    if args.phase == 'gpu-repeatability':
        out = BASE/'gpu_repeatability.json'
        assert not out.exists(), 'Freeze the pre-edit envelope; never overwrite it.'
        record = gpu_difference('gpu_before_2')
        record['rule'] = 'Post-edit max-absolute and relative-L2 differences must each be <= pre-edit repeat differences; byte-identical when the baseline is byte-identical.'
        out.write_text(json.dumps(record, indent=2)+'\n')
    else:
        cpu_comparison()
        baseline = json.loads((BASE/'gpu_repeatability.json').read_text())
        record = gpu_difference('gpu_after')
        record['within_pre_edit_envelope'] = {
            key: all(value[m] <= baseline['metrics'][key][m] for m in ('max_absolute', 'relative_l2'))
                 and (not baseline['metrics'][key]['bit_identical'] or value['bit_identical'])
            for key, value in record['metrics'].items()}
        record['passes'] = all(record['within_pre_edit_envelope'].values())
        (BASE/'gpu_comparison.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2))
    if args.phase == 'after':
        assert record['passes'], 'GPU default outside pre-edit repeatability; report to coordinator.'


if __name__=='__main__':main()
