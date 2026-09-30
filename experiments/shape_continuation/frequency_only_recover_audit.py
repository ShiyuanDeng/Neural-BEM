"""Resume the saved SC-051 kite endpoint audit after an abrupt worker loss.

No fitting is rerun and no endpoint coefficient is changed. Unknown work in
the interrupted audit remains explicitly bounded rather than counted as zero.
"""
from dataclasses import asdict
import json
from pathlib import Path
import time

import numpy as np

from experiments.shape_continuation import frequency_only as f
from experiments.shape_continuation import frequency_only_resolution as control
from experiments.shape_continuation.lm_backend import stage_record


def main():
    f.OUT=control.CONTROL
    manifest=f.verify()
    row=next(r for r in manifest['cases'] if r['id']=='core__kite')
    folder=f.OUT/'runs'/row['id']
    if (folder/'result.json').exists():
        raise FileExistsError('Preserve completed endpoint')
    result=f.sc.read(folder/'unscored.json')
    saved=f.sc.read(folder/'configuration.json')
    frozen_endpoint=f.digest(folder/'unscored.json')
    f.set_contrast(row['contrast'])
    catalog,_,frequencies=f.data_only(row)
    _,config=f.ast.schedules(catalog,'baseline')
    stage=control.schedule(catalog,frequencies,config)[-1]
    assert json.loads(json.dumps(stage_record(stage)))==saved['schedule'][-1]['stage']
    assert json.loads(json.dumps(asdict(config)))==saved['schedule'][-1]['backend']
    curve=f.restore(result['final_curve'])
    s=f.sc050()
    update=s.c.reference.ProjectedUpdate(f.sc.LENGTH)
    receipt=dict(reason='Resolution-control ProcessPoolExecutor raised BrokenProcessPool during the kite endpoint audit.',
        cause='Abrupt worker termination; root cause not established.',
        fit_unchanged=True, endpoint_sha256=frozen_endpoint,
        unknown_interrupted_audit_work_units_upper_bound=6*len(catalog)+12,
        interrupted_audit_work_units=None, interrupted_audit_seconds=None,
        resumed_with_one_worker=True, source_sha256=f.digest(Path(__file__)))
    f.write(folder/'audit_recovery.json',receipt)
    started=time.perf_counter()
    with s.old.deadline(300):
        final=f.audit(curve,stage,config,update,row['contrast'],folder)
    result.update(final_audit_passed=final['passed'],audit_units=final['work']['work_units'])
    result['metrics']=f.score(row,curve)
    limits,noisy=f.residual_limits(row,catalog)
    result.update(noisy=noisy,residual_limits=limits,relative_residual=final.get('relative_residual'),
        maximum_residual=max(final['relative_residual']) if 'relative_residual' in final else None)
    result['recovered']=bool(final['passed'] and result['metrics']['rms_mm']<=1 and
        result['metrics']['hausdorff_upper_mm']<=2 and result['relative_residual'] is not None and
        np.all(np.array(result['relative_residual'])<=limits))
    result['total_seconds']=None
    result['audit_recovery']=dict(receipt,resumed_audit_and_score_seconds=time.perf_counter()-started)
    assert f.digest(folder/'unscored.json')==frozen_endpoint
    f.write(folder/'result.json',result)
    print('RECOVERED AUDIT',row['id'],final['passed'],'RMS',result['metrics']['rms_mm'],flush=True)


if __name__=='__main__':
    main()
