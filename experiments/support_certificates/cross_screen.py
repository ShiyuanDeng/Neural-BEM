from pathlib import Path
import json
import numpy as np
from .core import CrossDual


def run():
    out=Path('results/experiments/support_certificates_20260916');saved=np.load(out/'screen_data.npz')
    pts=saved['points'];g=saved['g'];e=saved['e'][:,[0,3]];a=saved['a'];y=saved['y'][:,[0,3]]
    scale=np.linalg.norm(y);a=a/scale;y=y/scale;records=[]
    for name,mask in [('full',np.ones(len(pts),bool)),('without_core',np.linalg.norm(pts-[.01,-.16],axis=1)>.031),('left',pts[:,0]<0)]:
        ids=np.flatnonzero(mask);d=np.eye(len(ids))/-.5-g[np.ix_(ids,ids)]
        labels=(pts[ids,0]>0).astype(int)+2*(pts[ids,1]>-.16).astype(int)
        groups=np.array([labels==j for j in np.unique(labels)],float)
        for diagonal in (True,False):
            model=CrossDual(d,e[ids],a[:,ids],y,groups,diagonal_only=diagonal)
            record=dict(name=name,diagonal_only=diagonal,**model.solve(max_steps=30,barriers=(1e-3,1e-4,1e-5,1e-6)))
            records.append(record)
            print({k:record.get(k) for k in ('name','diagonal_only','relative_residual_bound','seconds','success')},flush=True)
            (out/'cross_screen.json').write_text(json.dumps(records,indent=2))


if __name__=='__main__':run()
