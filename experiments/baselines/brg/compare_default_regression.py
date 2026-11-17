"""Compare the saved CPU reference numerics and decisions, excluding clocks."""
import json
from pathlib import Path
import numpy as np

BASE=Path(__file__).resolve().parents[3]/'results/brg/bem_adaptation/2026-11-17/regression'


def stable(value):
    if isinstance(value,dict):
        return {k:stable(v) for k,v in value.items()
                if 'seconds' not in k and k not in ('elapsed','started','timestamp')
                and not (k in ('table_mode','ragged_data') and v is False)}
    if isinstance(value,list):return [stable(v) for v in value]
    return value


def main():
    arrays={}
    with np.load(BASE/'before/fit.npz') as before,np.load(BASE/'after/fit.npz') as after:
        assert set(before.files)==set(after.files)
        for key in before.files:
            arrays[key]=dict(bit_identical=bool(before[key].dtype==after[key].dtype and
                before[key].shape==after[key].shape and before[key].tobytes()==after[key].tobytes()),
                shape=list(before[key].shape))
    before=json.loads((BASE/'before/fit.json').read_text());after=json.loads((BASE/'after/fit.json').read_text())
    keys=('outcome','detail','contrast_start','contrast','final_curve','final_stage','stages','decisions',
          'fit_work','frequencies_hz','noise_sigma_declared','work','residual','maximum_residual','residual_resolution')
    checks={k:stable(before[k])==stable(after[k]) for k in keys}
    record=dict(arrays=arrays,stable_records_identical=checks,
                passes=all(a['bit_identical'] for a in arrays.values()) and all(checks.values()),
                excluded='clock fields; added default-false options; execution timing receipts')
    (BASE/'comparison.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
    assert record['passes'],'Default CPU reference changed; do not proceed to BRG inversion.'


if __name__=='__main__':main()
