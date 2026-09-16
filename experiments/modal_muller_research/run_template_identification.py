"""Identify object types and poses using one shared Laurent scattering library."""
from itertools import product
import json
from pathlib import Path
from time import perf_counter
import numpy as np
from .coefficient_operator import LaurentGeometry
from .scattering_library import PoseChart,compile_template
from .pose_inverse import PoseEvaluator,invert_pose
from .run_scattering_library import fixture,FREQUENCIES,metrics
from .run_inverse import save


def symmetry_audit(output):
    entries=[('circle',LaurentGeometry.circle(radius=.03),None),
             ('ellipse',LaurentGeometry.ellipse(major=.033,minor=.025,rotation=0),2),
             ('three_lobed',LaurentGeometry.star(radius=.028,amplitude=.12,lobes=3,rotation=0),3)]
    rows=[]
    for name,geometry,symmetry in entries:
        template=compile_template(geometry,64.,45.25,order=10)
        difference=template.modes[None,:]-template.modes[:,None]
        forbidden=difference!=0 if symmetry is None else difference%symmetry!=0
        angle=.317 if symmetry is None else 2*np.pi/symmetry
        rotated,_=template.rotated(angle)
        rows.append(dict(name=name,rotational_order=symmetry,modes=template.modes.tolist(),
            forbidden_coupling_fraction=float(np.linalg.norm(template.matrix[forbidden])/np.linalg.norm(template.matrix)),
            symmetry_rotation_error=float(np.linalg.norm(rotated-template.matrix)/np.linalg.norm(template.matrix)),
            absolute_matrix=np.abs(template.matrix).tolist()))
    save(output/'symmetry.json',rows)


def main():
    root=Path('results/experiments/modal_muller_20260916/scattering_library')
    output=root/'identification';output.mkdir(parents=True,exist_ok=True)
    symmetry_audit(output)
    raw=json.loads((root/'four_noise1pct_inputs.json').read_text())
    observed=np.array(raw['observed_real'])+1j*np.array(raw['observed_imag'])
    clean=np.array(raw['clean_real'])+1j*np.array(raw['clean_imag'])
    acq,reference_chart,truth,initial=fixture(4)
    catalog=reference_chart.geometries[:2]
    cache={};rows=[];tick=perf_counter()
    # All 16 type assignments get the same zero-pose initial guess and limits.
    # The observations carry the information about which template belongs where.
    for assignment in product(range(len(catalog)),repeat=4):
        chart=PoseChart([catalog[i] for i in assignment],reference_chart.anchors)
        started=perf_counter()
        evaluator=PoseEvaluator(chart,acq,FREQUENCIES,template_cache=cache)
        result=invert_pose(chart,acq,FREQUENCIES,observed,initial,evaluator=evaluator)
        seconds=perf_counter()-started
        name=''.join(map(str,assignment))
        record=dict(assignment=assignment,seconds_including_new_compilation=seconds,result=result)
        save(output/(name+'.json'),record)
        rows.append(dict(assignment=assignment,score=result['residual_norm'],seconds=seconds,
                         success=result['success'],nfev=result['nfev'],compiled_templates=evaluator.work['compiled_templates'],
                         parameters=result['parameters']))
        print('template hypothesis',json.dumps(rows[-1]),flush=True)
    seconds=perf_counter()-tick
    rows.sort(key=lambda r:r['score'])
    chosen=rows[0]
    # Ground-truth labels and geometry enter only the final assessment.
    expected=[0,1,0,1]
    correct=list(chosen['assignment'])==expected
    validation=metrics(reference_chart,np.array(chosen['parameters']),truth,acq,observed,clean) if correct else None
    summary=dict(ranking=rows,chosen_assignment=chosen['assignment'],expected_assignment=expected,
        correct=correct,total_seconds=seconds,compiled_templates=len(cache),hypotheses=len(rows),
        runner_up_score_ratio=rows[1]['score']/chosen['score'],metrics=validation,
        scope='Four known components and anchors; each object is either an ellipse or three-lobed template. '
              'Types, positions, and orientations are unknown; local shapes and materials are fixed. '
              'One local optimizer start per assignment; no global pose guarantee.',selection_uses_truth=False)
    save(output/'summary.json',summary)
    print('identification result',json.dumps({k:v for k,v in summary.items() if k!='ranking'}),flush=True)


if __name__=='__main__':
    main()
