"""Small algebraic models; no geometry or kernel approximation hidden here."""
import math
import time
import numpy as np
from scipy.linalg import lu_factor, lu_solve


def tangent(a,b,c,u,factors,direction):
    da,db,dc=direction
    du=lu_solve(factors,db-da@u)
    return dc@u+c@du


def operator_prediction(a,b,c,direction,h):
    tick=time.perf_counter()
    aa,bb,cc=[x+h*dx for x,dx in zip((a,b,c),direction)]
    update=time.perf_counter()-tick; tick=time.perf_counter()
    factors=lu_factor(aa);factor=time.perf_counter()-tick;tick=time.perf_counter()
    u=lu_solve(factors,bb);solve=time.perf_counter()-tick;tick=time.perf_counter()
    y=cc@u;evaluation=time.perf_counter()-tick;tick=time.perf_counter()
    residual=float(np.linalg.norm(aa@u-bb)/np.linalg.norm(bb))
    return dict(Y=y,U=u,approximate_residual=residual,
                times=dict(update=update,factorization=factor,solve=solve,
                           evaluation=evaluation,residual=time.perf_counter()-tick))


def break_even(setup,exact,online):
    return max(1,math.ceil(setup/(exact-online))) if exact>online else None
