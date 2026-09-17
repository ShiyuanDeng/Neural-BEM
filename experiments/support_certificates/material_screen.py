from pathlib import Path
import json
import numpy as np
from .core import Dual,SectorDual


def run():
    out=Path('results/experiments/support_certificates_20260916')
    data=np.load(out/'screen_data.npz');points=data['points'];g=data['g'];e=data['e'];a=data['a'];y=data['y']
    scale=np.linalg.norm(y);a=a/scale;y=y/scale
    masks=dict(full=np.ones(len(points),bool),left=points[:,0]<-.001,
               shallow=points[:,1]>-.151,deep=points[:,1]<-.169,
               without_core=np.linalg.norm(points-[.01,-.16],axis=1)>.031)
    records=[]
    for name,mask in masks.items():
        ids=np.flatnonzero(mask);gg=g[np.ix_(ids,ids)]
        for label,lo,hi in [('eps_3_to_6',-.5,0),('eps_1p5_to_6',-.75,0),('eps_1p5_to_15',-.75,1.5)]:
            dual=SectorDual(gg,e[ids],a[:,ids],y,lo,hi)
            result=dual.solve(max_steps=35)
            record=dict(name=name,material=label,**result);records.append(record)
            print({k:record.get(k) for k in ('name','material','bound','relative_residual_bound','seconds','success','reason')},flush=True)
            (out/'material_screen.json').write_text(json.dumps(records,indent=2))


if __name__=='__main__':run()
