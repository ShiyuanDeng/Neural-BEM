"""Read-only linearized evidence from the qualified SC-049 initial atlas."""
from pathlib import Path
import json
import numpy as np
from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc

HERE=Path(__file__).resolve().parent
source=HERE.parent/'SC-049-far-circle-to-c'
with np.load(source/'initial_atlas.npz') as data:
    prediction=data['prediction_1024']
    jacobian=data['jacobian_1024']
catalog=ast.catalog_only('circle_to_c')
rows=[]
for index in (0,2):
    observed=catalog[index].scattered
    residual=(prediction[index]-observed)/np.linalg.norm(observed)
    for name,columns in [('radius_translation',[0,1,49]),('M3',[0,1,2,3,49,50,51])]:
        J=jacobian[index][:,columns]
        matrix=np.vstack((J.real,J.imag))
        vector=np.r_[residual.real,residual.imag]
        step=np.linalg.lstsq(matrix,-vector,rcond=1e-12)[0]
        s=np.linalg.svd(matrix,compute_uv=False)
        projection=1-np.linalg.norm(vector+matrix@step)**2/np.linalg.norm(vector)**2
        rows.append(dict(frequency_hz=.25e9+index*.125e9,space=name,
            columns=columns,unconstrained_linear_step_mm=(1000*step).tolist(),
            singular_values=s.tolist(),condition=float(s[0]/s[-1]),
            fraction_squared_residual_projected=float(projection)))
result=dict(rows=rows,scope='Local least-squares projection at original displaced circle; unconstrained infinitesimal normal update, not a proposed finite step or a global identifiability claim.',
    sources={str(p.relative_to(sc.ROOT)):sc.digest(p) for p in (source/'initial_atlas.npz',source/'initial_atlas.json',ast.source_folder('circle_to_c')/'observations.json')},
    note='On a circle, normal harmonics 0/cos1/sin1 are first-order radius/x-translation/y-translation. Atlas Jacobian columns are relative-data derivatives per metre.')
sc.write(HERE/'atlas_diagnosis.json',result)
for row in rows:
    print(row['frequency_hz'],row['space'],'step mm',np.round(row['unconstrained_linear_step_mm'],2),'projected',round(row['fraction_squared_residual_projected'],4))
