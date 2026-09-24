import json, sys, numpy as np
sys.path[:0]=['solvers','.']
from dataclasses import replace
from experiments.shape_continuation import spd_cases as sc
from experiments.shape_continuation.lm_backend import Objective, BackendConfig, Ledger
from experiments.shape_continuation.updates import BorgesUpdate
from experiments.shape_continuation.geometry import FourierCurve
import config.two_circle_config as cfg, run_radial_fourier_topology_inverse as base
OUT='results/validation/shape_continuation/SC-020-spd-matched-hybrid'
inputs=sc.load(); top025=inputs['top025']
obs=sc.package_observations(list(top025.p.TRAIN), inputs['observed'], cfg, base)
policy=sc.spd_matching_policy(obs, inputs['optimizer'], top025)
h=json.load(open(f'{OUT}/runs/hybrid/result.json'))
curve=FourierCurve(np.array(h['final_curve']['real'])+1j*np.array(h['final_curve']['imag']))
u=BorgesUpdate(sc.LENGTH); M=28
for stage in (policy.stages[0], policy.stages[3]):
    st=replace(stage, update_modes=M)
    obj=Objective(st, cfg.PLASTIC_EPSR/cfg.SAND_EPSR, BackendConfig(), Ledger())
    e=obj.production(curve,'x'); space=u.prepare(curve,M,st.curve_modes); J=obj.jacobian(e,u,space)
    norms=np.linalg.norm(J,axis=0)
    per=[norms[0]]+[np.hypot(norms[m],norms[M+m])/np.sqrt(2) for m in range(1,M+1)]
    print(stage.label, 'residual norm', np.linalg.norm(e.residual))
    print(' data change per 0.05 mm of each harmonic (normalized residual units):')
    print('  ', ' '.join(f'{m}:{v*5e-5:.1e}' for m,v in enumerate(per)))
