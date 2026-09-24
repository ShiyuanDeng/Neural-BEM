import json, sys, time, numpy as np
sys.path[:0]=['solvers','.']
from experiments.shape_continuation import spd_cases as sc
from experiments.shape_continuation.lm_backend import *
from experiments.shape_continuation.updates import BorgesUpdate
import config.two_circle_config as cfg
import run_radial_fourier_topology_inverse as base
inputs=sc.load(); top025=inputs['top025']
obs=sc.package_observations(list(top025.p.TRAIN), inputs['observed'], cfg, base)
policy=sc.spd_matching_policy(obs, inputs['optimizer'], top025)
config=sc.backend_config(inputs['optimizer'], top025.p.driver.baseline._geometry_config(256).bounds)
print(config)
u=BorgesUpdate(sc.LENGTH); ledger=Ledger()
c=sc.from_cartesian(inputs['state'].components[0]); g,_=u.regauge(c,sc.CURVE_MODES)
stage=policy.stages[0]
ledger.begin_stage(stage.label, stage.quota)
t=time.time()
r=fit_stage(g, stage, cfg.PLASTIC_EPSR/cfg.SAND_EPSR, u, config, ledger)
print('time',time.time()-t, r.outcome, r.stop_reason, r.accepted_steps, r.initial_loss, r.final_loss)
for h in r.history: print(h['iteration'], f"{h['loss']:.3e} g={h['gradient_inf']:.2e} step={h['step_norm_m']:.2e} lam={h['damping']:.1e}", h.get('maximum_normal_m'))
from collections import Counter
print(Counter(t.get('status','?')+':'+t.get('reason','') for t in r.trials))
print(r.work)
s=sc.score_state(sc.hybrid_state(r.curve), inputs); print('haus',s['geometry']['maximum_matched_hausdorff_m'],'train',s['training_errors'],'eval',s['evaluation_errors'])
