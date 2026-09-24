import json, sys, time, numpy as np
sys.path[:0]=['solvers','.']
src=open('results/validation/shape_continuation/SC-020-spd-matched-hybrid/development/dry.py').read().split("for h in r.history")[0]
exec(src)
cfgc=cfg.PLASTIC_EPSR/cfg.SAND_EPSR
np.save('results/validation/shape_continuation/SC-020-spd-matched-hybrid/development/stage1_curve.npy', r.curve.coefficients)
obj=Objective(stage, cfgc, config, Ledger())
e=obj.production(r.curve,'x')
space=u.prepare(r.curve, stage.update_modes, stage.curve_modes)
J=obj.jacobian(e,u,space)
s=np.linalg.svd(J,compute_uv=False); print('sv', s[:3], s[-5:], 'cond', s[0]/s[-1])
d,*_=np.linalg.lstsq(J,-e.residual,rcond=None)
print('loss',e.loss,'GN predicted',0.5*np.linalg.norm(e.residual+J@d)**2, '|d| m',np.linalg.norm(d))
for f in (1,0.5,0.25,0.1,0.01):
    c,_=u.trial(space,f*d); ee=obj.production(c,'x')
    print(f, 'actual',ee.loss,'pred',0.5*np.linalg.norm(e.residual+f*J@d)**2)
# noise floor: loss of regauged same curve
c2,err=u.regauge(r.curve, stage.curve_modes); e2=obj.production(c2,'x'); print('regauge same curve loss',e2.loss, 'err',err)
c3,_=u.trial(space,np.zeros(J.shape[1])); e3=obj.production(c3,'x'); print('zero-step trial loss',e3.loss)
