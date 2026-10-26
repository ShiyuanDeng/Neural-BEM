"""HB-004: actual benchmark circle blocks, fields, and circular ItI flow."""
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np
from scipy.integrate import solve_ivp
from scipy.special import jv, jvp, hankel1, h1vp, jn_zeros

from bem_inverse.forward_solvers import modal_muller as MM
from bem_inverse.physics import Execution
from bem_inverse.mie_localize import paired_data
from experiments.benchmark.campaign import problem

OUT = Path('results/validation/cleaned_interfaces/HB-004-circle')


def spectra(k, radius, modes):
    t = k*radius
    j, h = jv(modes, t), hankel1(modes, t)
    dj, dh = jvp(modes, t), h1vp(modes, t)
    return (.5j*np.pi*j*h, .25j*np.pi*t*(dj*h+j*dh),
            .5j*np.pi*t*t*dj*dh)


def exact_matrix(k, contrast, radius, modes):
    outer, inner = spectra(k, radius, modes), spectra(k*np.sqrt(contrast), radius, modes)
    v, d, t = [x-y for x, y in zip(outer, inner)]
    eye = np.eye(len(modes))
    return np.block([[eye-np.diag(d), np.diag(v)],
                     [-np.diag(t), eye+np.diag(d)]])


def relative(a, b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b), 1e-300))


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    result = dict(length_unit_m=problem('circle__c13.3').length_unit_m,
                  revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  affinity=sorted(os.sched_getaffinity(0)), load=os.getloadavg(),
                  threads={k:os.environ.get(k) for k in
                           ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']},
                  circles=[], iti=[])
    save = lambda: (OUT/'summary.json').write_text(json.dumps(result, indent=2))
    n = np.arange(-64,65)
    for contrast in [.5,4.,13.3]:
        p = problem(f'circle__c{contrast:g}')
        curve = p.initial
        radius, center = float(curve.coefficients[-1].real), curve.coefficients[1]
        ctx = MM.ModalMuller(Execution(device='cpu', frequency_threads=1),
                            observer=lambda kind, payload: captured.update(payload) if kind=='field' else None)
        for copy, obs in [('real',p.real), ('damped',p.damped)]:
            for o in [obs[0],obs[-1]]:
                captured = {}
                start=perf_counter()
                pred=MM.forward_solve(curve,o,contrast,MM.token(64),context=ctx)
                seconds=perf_counter()-start
                start=perf_counter(); A=exact_matrix(o.wavenumber,contrast,radius,n)
                analytic_seconds=perf_counter()-start
                acq=o.acquisition
                start=perf_counter()
                mie=paired_data(o.wavenumber,contrast,[center],[radius],acq.sources,acq.receivers,64)[0,0]*acq.strength
                mie_seconds=perf_counter()-start
                errors={}
                for label, i,j in [('K',0,0),('V',0,1),('T',1,0),('Kprime',1,1)]:
                    sl=(slice(i*129,(i+1)*129),slice(j*129,(j+1)*129))
                    # Subtract identity before computing relative kernel errors.
                    x,y=captured['A'][sl].copy(), A[sl].copy()
                    if i==j: x-=np.eye(129); y-=np.eye(129)
                    errors[label]=relative(x,y)
                step=radius*1e-5
                # Formula (60) for uniform radial h=1.
                vplus=spectra(o.wavenumber,radius+step,n)[0]
                vminus=spectra(o.wavenumber,radius-step,n)[0]
                derivative=2*spectra(o.wavenumber,radius,n)[1]/radius
                result['circles'].append(dict(contrast=contrast,copy=copy,k_real=o.wavenumber.real,
                    k_imag=o.wavenumber.imag,radius=radius,block_relative_errors=errors,
                    matrix_relative=relative(captured['A'],A),field_relative=relative(pred.prediction,mie),
                    radius_derivative_relative=relative((vplus-vminus)/(2*step),derivative),
                    modal_forward_seconds=seconds,analytic_matrix_seconds=analytic_seconds,
                    mie_fields_seconds=mie_seconds,stages=ctx.receipt()['seconds']))
                save()
                print(contrast,copy,o.wavenumber,errors,flush=True)
    kreal=float(problem('circle__c13.3').real[-1].wavenumber.real)*np.sqrt(13.3)
    pole=float(jn_zeros(0,1)[0]/kreal)
    modes=np.arange(17); eta=1.
    for copy,k in [('real',complex(kreal)),('damped',kreal*(1+.25j))]:
        def exact(a):
            x=jv(modes,k*a); y=k*a*jvp(modes,k*a)
            return (y-1j*eta*x)/(y+1j*eta*x)
        def rhs(a,r):
            return (eta**2*(1+r)**2/a+(1-r)**2*(modes**2/a-k*k*a))/(2j*eta)
        radii=np.linspace(.9*pole,1.1*pole,101)
        for tol in [1e-7,1e-10]:
            start=perf_counter()
            sol=solve_ivp(rhs,(radii[0],radii[-1]),exact(radii[0]),t_eval=radii,
                          rtol=tol,atol=tol*.01,method='DOP853')
            reference=np.array([exact(a) for a in sol.t]).T
            result['iti'].append(dict(copy=copy,tolerance=tol,success=sol.success,nfev=sol.nfev,
                seconds=perf_counter()-start,radius_pole=pole,
                max_absolute_error=float(np.max(np.abs(sol.y-reference))),
                exact_unitarity_defect=float(np.max(np.abs(np.abs(reference)**2-1))),
                numerical_unitarity_defect=float(np.max(np.abs(np.abs(sol.y)**2-1))),
                pole_mode0_iti_error=float(abs(exact(pole)[0]-1))))
            save()
    result['checks']=dict(blocks=all(max(r['block_relative_errors'].values())<1e-8 for r in result['circles']),
                          fields=all(r['field_relative']<1e-8 for r in result['circles']),
                          iti=all(r['success'] and r['max_absolute_error']<100*r['tolerance'] for r in result['iti']))
    save()


if __name__=='__main__':
    run()
