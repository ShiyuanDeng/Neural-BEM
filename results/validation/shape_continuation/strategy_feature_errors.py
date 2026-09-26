"""Post-fit localization of fresh-shape boundary error; no inverse decisions.

The cavity region is declared from the analytic deep-C construction, not
selected from a reconstruction's error map. These are descriptive metrics,
added after launching the study; the frozen selection gates are unchanged.
"""
import importlib.util
from pathlib import Path
import numpy as np
from experiments.shape_continuation.metrics import points_to_polygon_distance

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('feature_common',ROOT/'SC-044-noisy-fresh-cases/run.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def measure(target,recovered,case,count):
    nodes=target.nodes(count)
    vertices=recovered.nodes(count).points
    distances=50*points_to_polygon_distance(nodes.points,vertices)
    regions={'whole_truth':np.ones(count,dtype=bool)}
    if case=='deep_c':
        unrotated=target.values(count)*np.exp(.4j)
        regions['cavity_wall']=(abs(unrotated)<.7) & (abs(np.angle(unrotated))<np.radians(110))
        regions['remaining_truth']=~regions['cavity_wall']
    result={}
    for label,mask in regions.items():
        weight=nodes.arc_length_weights[mask]
        error=distances[mask]
        result[label]=dict(rms_mm=float(np.sqrt(np.sum(weight*error**2)/weight.sum())),
            maximum_mm=float(error.max()),truth_perimeter_fraction=float(weight.sum()/nodes.arc_length_weights.sum()))
    return result


def main():
    r.verify()
    rows=[]
    for p in sorted((r.HERE/'runs').glob('*/*/*/result.json')):
        d=r.c.sc.read(p)
        if 'curve' not in d:continue
        target=r.c.ast.curve_from(r.c.sc.read(r.HERE/'inputs'/d['case']/'truth.json'))
        recovered=r.c.ast.curve_from(d['curve'])
        coarse=measure(target,recovered,d['case'],8192)
        fine=measure(target,recovered,d['case'],16384)
        change=max(abs(fine[key][metric]-coarse[key][metric]) for key in fine for metric in ('rms_mm','maximum_mm'))
        rows.append(dict(case=d['case'],profile=d['profile'],arm=d['arm'],regions=fine,
            maximum_sampling_change_mm=change))
    r.c.write(ROOT/'strategy_feature_errors.json',dict(rows=rows,samples=16384,coarse_samples=8192,
        post_hoc=True,used_for_selection=False,
        definition='One-sided truth-to-reconstruction polygon distance, weighted by truth arclength. '
        'Deep-C cavity wall: undo rotation -0.4 rad, radius <0.7, polar angle within +/-110 degrees. '
        'The analytic inner arc has radius 0.58; these bounds exclude its rounded mouth transitions. '
        'The regional maximum is sampled; refinement agreement is empirical, not a certificate.'))
    print({'rows':len(rows),'maximum_sampling_change_mm':max((s['maximum_sampling_change_mm'] for s in rows),default=None)})


if __name__=='__main__':main()
