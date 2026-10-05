"""Independent ON-003 circle/flux-basis reference qualification, no fit."""
import json
from pathlib import Path
from time import perf_counter
import sys

from .on003 import OUT,ROOT,pinned_reference,write,digest


def main():
    started=perf_counter(); manifest,pin=pinned_reference()
    import numpy as np
    import mpmath as mp
    from bem_inverse.continuation.geometry import FourierCurve
    from bem_inverse.modal_geometry import ModalGeometry
    from bem_inverse.modal_operator import muller_matrix
    from bem_inverse.on003_ewald import circle_exact
    from bem_inverse.on003_circle_reference import heat_circle
    mp.mp.dps=50
    c=manifest['states'][0]['coefficients']
    curve=FourierCurve(np.asarray(c['real'])+1j*np.asarray(c['imag']))
    unit=manifest['states'][0]['length_unit_m']; radius=abs(curve.coefficients[-1]); a=radius*unit
    base=2*np.pi*.25e9*np.sqrt((4*np.pi*1e-7)*8.854187817e-12*6.)*unit
    out=OUT/'stage_A_reference'; out.mkdir(exist_ok=False)
    geometries={}; rows=[]; mprows=[]; arrays={}
    for cutoff in (64,128):
        begin=perf_counter(); geometries[cutoff]=ModalGeometry(curve,cutoff+64,workers=1)
        setup=perf_counter()-begin
        n=np.arange(-cutoff,cutoff+1); count=len(n)
        rng=np.random.default_rng(3003); probes=rng.normal(size=(count,4))+1j*rng.normal(size=(count,4)); probes/=np.linalg.norm(probes,axis=0)
        for contrast in (.5,4.,13.3):
            for mult in (1.,10.):
                for damp in (0.,.25):
                    k=base*mult*(1+1j*damp); ki=k*np.sqrt(contrast)
                    begin=perf_counter(); matrix,info=muller_matrix(geometries[cutoff],k,ki,cutoff,workers=1,basis_workers=1); seconds=perf_counter()-begin
                    exact=circle_exact(a,k/unit,n)-circle_exact(a,ki/unit,n)
                    blocks=[matrix[:count,count:],np.eye(count)-matrix[:count,:count],matrix[count:,count:]-np.eye(count),-matrix[count:,:count]]
                    for block,got,index in zip(('V','K','Kprime','T'),blocks,(0,1,1,2)):
                        expected=np.diag(exact[index]); delta=got-expected; scale=max(float(np.max(abs(exact[index]))),1e-14)
                        columns=np.linalg.norm(delta,axis=0)/scale
                        rows.append(dict(trace_cutoff=cutoff,contrast=contrast,frequency_hz=.25e9*mult,damping=damp,block=block,max_basis_column_error_over_scale=float(np.max(columns)),complex_probe_error_over_scale=float(np.max(np.linalg.norm(delta@probes,axis=0))/scale),absolute_max_entry_error=float(np.max(abs(delta))),reference_scale=scale,source='pinned modal vs analytic outgoing circle',assembly_seconds=seconds,geometry_setup_seconds=setup,passed=bool(np.max(columns)<1e-7)))
                    arrays[f'matrix_{cutoff}_{contrast}_{mult}_{damp}']=matrix
                    if cutoff==128:
                        for mode in (0,60,128):
                            def one(kk):
                                x=mp.mpc(complex(kk))*mp.mpf(float(a)); m=mode
                                J=mp.besselj(m,x); H=mp.hankel1(m,x)
                                Jp=(mp.besselj(m-1,x)-mp.besselj(m+1,x))/2
                                Hp=(mp.hankel1(m-1,x)-mp.hankel1(m+1,x))/2
                                return [mp.j*mp.pi/2*J*H,mp.j*mp.pi/2*x*Jp*H-mp.mpf('.5'),mp.j*mp.pi/2*x*x*Jp*Hp]
                            o=one(k/unit); i=one(ki/unit)
                            exactmp=np.array([complex(x-y) for x,y in zip(o,i)])
                            exactfloat=circle_exact(a,k/unit,[mode])[:,0]-circle_exact(a,ki/unit,[mode])[:,0]
                            for b,j in (('V',0),('K',1),('T',2)):
                                scale=max(float(np.max(abs(exact[j]))),1e-14)
                                error=abs(exactfloat[j]-exactmp[j])/scale
                                mprows.append(dict(contrast=contrast,frequency_hz=.25e9*mult,damping=damp,mode=mode,block=b,absolute_error=float(abs(exactfloat[j]-exactmp[j])),error_over_operator_scale=float(error),passed=bool(error<1e-10)))
    near_rows=[]
    for xi in (1,2,4,8):
        phase=OUT/f'stage_A_xi{xi}'
        controls=json.loads((phase/'near_and_flat_controls.json').read_text())
        tau=1/(4*(xi*manifest['settings']['k_star_per_m'])**2)
        with np.load(phase/'grid256_arrays.npz') as saved:
            for index,label in enumerate(controls['wave_order']):
                ko=complex(*map(float,label.split(',')))
                q1=heat_circle(a,ko,tau,n,256);q2=heat_circle(a,ko,tau,n,512)
                delta=np.abs(saved[f'near_{index}']-q2)
                near_rows.append(dict(xi_over_kstar=xi,k=[ko.real,ko.imag],heat_256_512_max_difference=float(np.max(abs(q1-q2))),angular_4096_vs_heat_absolute_by_block=[float(np.max(row)) for row in delta]))
    np.savez_compressed(out/'matrices.npz',**arrays)
    imports={name:str(module.__file__) for name,module in sys.modules.items() if name.startswith('bem_inverse') and getattr(module,'__file__',None)}
    receipt=dict(stage='A independent circle reference',seconds=perf_counter()-started,reference_commit='6f2c1408',reference_archive_sha256=digest(OUT/'reference_HEAD_sources.tar.gz'),manifest_sha256=digest(OUT/'manifest.json'),mpmath_version=mp.__version__,mpmath_digits=50,rows=rows,high_precision_rows=mprows,near_heat_rows=near_rows,all_modal_basis_checks_passed=all(r['passed'] for r in rows),all_high_precision_checks_passed=all(r['passed'] for r in mprows),imports=imports,source_hashes={p:digest(ROOT/p) for p in ('experiments/benchmark/on003_reference.py','solvers/bem_inverse/on003_ewald.py','solvers/bem_inverse/on003_circle_reference.py')})
    write(out/'receipt.json',receipt)
    print('Reference max basis scale error',max(r['max_basis_column_error_over_scale'] for r in rows),'mp scale error',max(r['error_over_operator_scale'] for r in mprows),flush=True)


if __name__=='__main__': main()
