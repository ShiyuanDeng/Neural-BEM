from pathlib import Path
import json
import numpy as np
from ordered_boundary import circle
from gpr_bem_kress.system import build_muller_system
from gpr_bem_kress.forward import kress_incident_trace_on_boundary,build_exterior_receiver_operator
from .screen import CircleData,material,EPS0,MU0


def run():
    out=Path('results/experiments/passive_shape_20260916');saved=json.loads((out/'screen.json').read_text())
    rows=[]
    for record in saved['records']:
        if record['radius_mm'] not in (5.,30.):continue
        for kind,radius,parameters in [('truth',record['radius_mm']/1000,record['true_material']),
                                       ('alternative',record['alternative_radius_mm']/1000,record['fitted_material'])]:
            for frequency in (.3e9,.9e9,1.5e9):
                model=CircleData([frequency]);eps=material(frequency,parameters)
                # The production material wrapper deliberately rejects loss.
                # Use its documented low-level complex-wave numerical API,
                # explicitly choosing outgoing H1 and passive Im(k)>0.
                curve=circle(tuple(model.center),radius).discretize(192)
                ke=2*np.pi*frequency*np.sqrt(EPS0*MU0*6.)
                ki=2*np.pi*frequency*np.sqrt(EPS0*MU0*eps)
                system=build_muller_system(curve,ke,ki,angular_frequency=2*np.pi*frequency)
                d,n=kress_incident_trace_on_boundary(curve,model.sources,ke,1.)
                state=np.linalg.solve(system.system_matrix,np.concatenate((d,n),axis=1).T)
                ref=build_exterior_receiver_operator(curve,model.receivers,ke).state_rows@state
                pred=model.predict(radius,parameters)[0]
                error=float(np.linalg.norm(ref-pred)/np.linalg.norm(ref))
                rows.append(dict(radius_mm=radius*1000,kind=kind,frequency=frequency,relative_error=error))
                print(rows[-1],flush=True)
    (out/'qualification.json').write_text(json.dumps(rows,indent=2))
    assert max(r['relative_error'] for r in rows)<1e-9


if __name__=='__main__':run()
