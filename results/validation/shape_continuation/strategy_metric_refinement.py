"""Post-hoc sampling check of returned geometry metrics; no inverse decisions.

The original frozen scores and gates stay unchanged. Double recovered RMS
samples (4096 -> 8192), truth samples (16384 -> 32768), and Hausdorff samples
(8192 -> 16384). Report measured changes and the conservative distance bound.
"""
import importlib.util
from pathlib import Path
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.metrics import boundary_distance

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('metric_common',ROOT/'SC-042-state-strategies/run.py')
c=importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def main():
    c.verify()
    rows=[]
    for name in ('SC-042-state-strategies','SC-043-prospective-band','SC-044-noisy-fresh-cases'):
        for p in sorted((ROOT/name/'runs').rglob('result.json')):
            d=c.sc.read(p)
            if d.get('arm')=='prefix' or 'score' not in d:continue
            case=d['case']
            target_path=(ROOT/name/'inputs'/case/'truth.json') if name.startswith('SC-044') else c.ast.source_folder(case)/'truth.json'
            target=c.ast.curve_from(c.sc.read(target_path))
            recovered=c.ast.curve_from(d['curve'])
            rms=1e3*symmetric_rms_distance(recovered,target.values(32768),c.sc.LENGTH,count=8192)
            hd,bound=boundary_distance(target,recovered,count=16384)
            hd,bound=50*hd,50*bound
            rows.append(dict(path=str(p.relative_to(ROOT)),rms_mm=rms,hausdorff_mm=hd,hausdorff_bound_mm=bound,
                rms_change_mm=rms-d['score']['rms_mm'],hausdorff_change_mm=hd-d['score']['hausdorff_mm'],
                original_rms_mm=d['score']['rms_mm'],original_hausdorff_mm=d['score']['hausdorff_mm']))
    result=dict(rows=rows,post_hoc=True,used_for_selection=False,
        maximum_absolute_rms_change_mm=max((abs(s['rms_change_mm']) for s in rows),default=None),
        maximum_absolute_hausdorff_change_mm=max((abs(s['hausdorff_change_mm']) for s in rows),default=None),
        note='Sampling agreement is an empirical check. The separate Hausdorff error bound remains conservative. These refined scores do not replace frozen selection criteria.')
    c.write(ROOT/'strategy_metric_refinement.json',result)
    print({k:v for k,v in result.items() if k!='rows'})


if __name__=='__main__':main()
