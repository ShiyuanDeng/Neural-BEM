import json, sys, time, numpy as np
sys.path[:0]=['solvers','.']
exec(open('results/validation/shape_continuation/SC-020-spd-matched-hybrid/development/dry.py').read().split("t=time.time()")[0])
cfgc=cfg.PLASTIC_EPSR/cfg.SAND_EPSR
obj=Objective(stage, cfgc, config, ledger)
e=obj.production(g,'x')
space=u.prepare(g, stage.update_modes, stage.curve_modes)
J=obj.jacobian(e,u,space)
rng=np.random.default_rng(0)
dirs={'random':rng.standard_normal(J.shape[1]), 'mode0':np.eye(J.shape[1])[0], 'mode5':np.eye(J.shape[1])[5], 'mode16':np.eye(J.shape[1])[16]}
for name,a in dirs.items():
    a=a/np.linalg.norm(a)
    for eps in (1e-4,1e-5,1e-6,1e-7):
        cc,_=u.trial(space, eps*a)
        ep=obj.production(cc,'x'); em=obj.production(u.trial(space,-eps*a)[0],'x')
        fd=(ep.residual-em.residual)/(2*eps)
        lin=J@a
        print(name, eps, 'rel err central', np.linalg.norm(fd-lin)/np.linalg.norm(lin))
