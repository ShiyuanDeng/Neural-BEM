import numpy as np
from experiments.shape_continuation import atlas_strategy_tests as ast, atlas_cases as ac, spd_cases as sc
from experiments.shape_continuation.atlas_dataset import INPUTS, BASE
for case in ast.CASES:
    catalog, truth = ac.load_case(BASE/INPUTS[case], case)
    z = truth.values(8192)*sc.LENGTH + sc.CENTER
    best=None
    # search kernel: point where polar angle is monotone
    cx, cy = z.real.mean(), z.imag.mean()
    grid = [(cx+dx, cy+dy) for dx in np.linspace(-.03,.03,61) for dy in np.linspace(-.03,.03,61)]
    ok=[]
    for x,y in grid:
        a = np.unwrap(np.angle(z-(x+1j*y)))
        d = np.diff(np.r_[a, a[0]+2*np.pi*np.sign(a[-1]-a[0])])
        if np.all(d>0) or np.all(d<0): ok.append((x,y))
    a = np.unwrap(np.angle(z-(cx+1j*cy))); d=np.diff(a)
    print(case, 'star-shaped about centroid:', bool(np.all(d>0) or np.all(d<0)), 'kernel grid points:', len(ok))
