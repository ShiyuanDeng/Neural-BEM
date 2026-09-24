import json, numpy as np
from pathlib import Path
from experiments.shape_continuation import spd_cases as sc
top025,_ = sc.spd_modules(); p = top025.p
root = Path('results/validation/shape_continuation/SC-030-spd008-comparison/runs/repeat_0')
def pts(state, n=4096):
    return p.boundary_points(state, n)[0]
for case in ('wrong_circle','circle_to_star','kite','peanut'):
    rows=[json.loads(l) for l in (root/case/'spd008/stage_1/trajectory.jsonl').read_text().splitlines()]
    states=[p.driver.deserialize_state(r['state']) for r in rows]
    moves=[]
    for a,b in zip(states,states[1:]):
        A,B=pts(a),pts(b)
        d=np.sqrt(((B[:,None,:]-A[None,::4,:])**2).sum(-1)).min(1)
        moves.append(1e3*d.max())
    # high-mode radial content above mode 5 about the component centre
    def tail(s):
        c=s.components[0]; P=pts(s,4096)-np.asarray(c.center); th=np.arctan2(P[:,1],P[:,0]); r=np.hypot(*P.T)
        o=np.argsort(th); th,r=th[o],r[o]; g=np.linspace(-np.pi,np.pi,4096,endpoint=False); rr=np.interp(g,th,r,period=2*np.pi)
        F=np.fft.rfft(rr)/len(g); F[:6]=0; return 1e3*np.sqrt(2*np.sum(abs(F)**2))
    print(case, 'accepted', len(moves), 'first moves mm', [round(x,2) for x in moves[:4]], 'max', round(max(moves),2),
          'radial rms above mode 5 after step1/end mm', round(tail(states[1]),3), round(tail(states[-1]),3))
