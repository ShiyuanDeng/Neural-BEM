"""Conditional field-table numerical gate, with original geometry/field factories."""
import json
from pathlib import Path
import time
import numpy as np
from experiments.modal_atlas import damped, damped_screen as ds
from experiments.modal_atlas.contrast_screen import set_contrast
from experiments.shape_continuation import forward as F
from experiments.shape_continuation.atlas import orthonormal_normal_basis
from field_runtime import install_fields, field_module
import runtime

BUNDLE=Path(__file__).resolve().parents[1]
reference_solve=damped.solve
candidate=runtime.install()
original,hook,counters=install_fields()
rows=[]


def rel(a,b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-300))


def fields(curve,o):
    _,receiver,incident=F._operators(curve)
    started=time.perf_counter()
    rec=receiver(curve,o.acquisition.receivers,o.wavenumber)
    d,n=incident(curve,o.acquisition.sources,o.wavenumber,o.acquisition.strength)
    return (rec.state_rows,d,n),time.perf_counter()-started


ds.verify()
for contrast,scene in [(0.5,'shifted_star'),(13.3,'new_asymmetric')]:
    set_contrast(contrast)
    _,obs,initial=ds.fitting_data(contrast,scene)
    endpoint=ds.ast.curve_from(json.loads((ds.OUT/'runs/D'/ds.tag(contrast)/scene/'result.json').read_text())['final_curve'])
    for shape_name,shape in [('initial',initial),('endpoint',endpoint)]:
        for j in (0,5,18):
            for nodes in (512,1024):
                o=obs[j]
                field_module.hankel1=original
                a=reference_solve(shape,o.wavenumber,contrast,o.acquisition,nodes)
                h=orthonormal_normal_basis(a.curve,9)
                ja=F.shape_jacobian(a,h)
                fa,ta=fields(a.curve,o)
                field_module.hankel1=hook
                b=candidate(shape,o.wavenumber,contrast,o.acquisition,nodes)
                jb=F.shape_jacobian(b,h)
                fb,tb=fields(b.curve,o)
                errors=dict(prediction=rel(b.prediction,a.prediction),jacobian=rel(jb,ja),
                            receiver=rel(fb[0],fa[0]),incident_dirichlet=rel(fb[1],fa[1]),incident_neumann=rel(fb[2],fa[2]))
                row=dict(contrast=contrast,scene=scene,shape=shape_name,frequency_index=j,nodes=nodes,
                         errors=errors,reference_fields_seconds=ta,table_fields_seconds=tb,
                         passed=max(errors.values())<=1e-10)
                rows.append(row)
                (BUNDLE/'field_qualification.json').write_text(json.dumps(rows,indent=2)+'\n')
                print(json.dumps(row),flush=True)
                assert row['passed'], row
# Unsupported calls must retain the reference behavior exactly.
for order,z in [(0,np.array([1.,2.])),(1,np.array([1+0.1j])),(2,np.array([1+.25j])),
                (0,np.array([.001+.00025j])),(1,np.array([101+25.25j]))]:
    assert np.array_equal(hook(order,z),original(order,z))
assert counters['table_calls']>0 and counters['reference_calls']>=5
print('FIELD_QUALIFICATION_PASS',json.dumps(counters),flush=True)
