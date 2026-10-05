"""ON-003 bounded outgoing/circle diagnostics. No fitting or truth access.

Run only through compute.lock then shared source.lock. References import
from the recorded ordinary archive, never from unfinished ON-001 sources.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tarfile
from time import perf_counter

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/validation/cleaned_interfaces/ON-003'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned_reference():
    manifest=json.loads((OUT/'manifest.json').read_text())
    archive=OUT/'reference_HEAD_sources.tar.gz'
    if digest(archive)!=manifest['reference_archive_sha256']:
        raise RuntimeError('Reference archive changed')
    pin=Path('/tmp/neural-sdf-bem-ad-coordination/on003_reference_6f2c1408')
    pin.mkdir(exist_ok=True)
    # Frozen archive produced locally by git archive, with only solvers paths.
    with tarfile.open(archive) as t:
        for member in t.getmembers():
            if (member.name != 'solvers' and not member.name.startswith('solvers/')) or '..' in Path(member.name).parts:
                raise RuntimeError('Unexpected archive member')
        t.extractall(pin)
    sys.path.insert(0,str(pin/'solvers'))
    import bem_inverse
    bem_inverse.__path__.append(str(ROOT/'solvers/bem_inverse'))
    return manifest,pin


def write(path,data):
    Path(path).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def run(xi):
    started=perf_counter()
    manifest,pin=pinned_reference()
    import numpy as np
    from scipy.integrate import quad
    from scipy.special import jv,jvp
    from bem_inverse import on003_ewald as E
    from bem_inverse.problem import Problem,Observation
    from bem_inverse.continuation.geometry import FourierCurve
    from bem_inverse.continuation.forward import PointSourceAcquisition
    folder=OUT/f'stage_A_xi{xi}'
    if folder.exists():
        raise FileExistsError('Preserve existing batch; use a new declared phase')
    folder.mkdir()
    # Observation metadata uses the frozen benchmark formula and actual
    # Problem/Observation contract, never saved truth or regenerated data.
    obsdata=json.loads((ROOT/'results/validation/cleaned_interfaces/TG-002/inputs/circle/c4/observations.json').read_text())
    dampdata=json.loads((ROOT/'results/validation/cleaned_interfaces/TG-002/inputs/circle/c4/damped.json').read_text())
    scanfile=ROOT/'results/validation/shape_continuation/SC-051-frequency-only/manifest.json'
    scan=json.loads(scanfile.read_text())
    # Actual acquisition constructor is the benchmark read-only contract.
    from experiments.cleaned_interface.benchmark import acquisition
    acq=acquisition()
    values=np.asarray(obsdata['observed_real'])+1j*np.asarray(obsdata['observed_imag'])
    dampvalues=np.asarray(dampdata['observed_real'])+1j*np.asarray(dampdata['observed_imag'])
    frequencies=obsdata['frequencies_hz']
    wave=lambda f:2*np.pi*f*np.sqrt((4*np.pi*1e-7)*8.854187817e-12*6.)*.05
    real=tuple(Observation(wave(f),acq,values[:,i],f) for i,f in enumerate(frequencies))
    damp=tuple(Observation(wave(f)*(1+.25j),acq,dampvalues[:,i],f) for i,f in enumerate(frequencies))
    c=manifest['states'][0]['coefficients']
    problem=Problem(FourierCurve(np.asarray(c['real'])+1j*np.asarray(c['imag'])),real,damp,4.)
    unit=problem.length_unit_m
    assert unit==manifest['states'][0]['length_unit_m']
    tau=1/(4*(xi*manifest['settings']['k_star_per_m'])**2)
    configs=[]
    waves={}
    for contrast in (.5,4.,13.3):
        for catalog,label in ((problem.real,'real'),(problem.damped,'damped')):
            for index in (0,len(catalog)-1):
                observation=catalog[index]
                ko=complex(observation.wavenumber)/unit
                ki=ko*np.sqrt(contrast)
                key=lambda z:f'{z.real:.16g},{z.imag:.16g}'
                waves[key(ko)]=ko; waves[key(ki)]=ki
                configs.append(dict(contrast=contrast,frequency_hz=observation.frequency_hz,kind=label,exterior=key(ko),interior=key(ki)))
    modes=np.arange(-128,129)
    a=float(abs(problem.initial.coefficients[-1])*unit)
    near={}; exact={}; flat_rows=[]; medium_rows=[]; products={}
    for label,k in waves.items():
        near1=E.circle_near(a,k,tau,modes,2048)
        near2=E.circle_near(a,k,tau,modes,4096)
        near[label]=near2
        exact[label]=E.circle_exact(a,k,modes)
        flat=E.flat_near(modes/a,k,tau)/a
        curve=flat+E.flat_curvature(modes/a,k,tau,1/a)/a
        norm=max(float(np.max(np.abs(near2[0]))),1e-30)
        medium_rows.append(dict(wavenumber_per_m=[k.real,k.imag],near_refinement_absolute=float(np.max(np.abs(near1-near2))),near_single_layer_scale=norm,flat_relative_scale_error=float(np.max(np.abs(flat-near2[0]))/norm),curvature_relative_scale_error=float(np.max(np.abs(curve-near2[0]))/norm)))
        for omega in (0.,k.real,2*k.real):
            f=lambda u:np.sqrt(tau/np.pi)*np.exp(-(omega**2-k*k)*tau*u*u)
            control=quad(lambda u:f(u).real,0,1,epsabs=1e-14)[0]+1j*quad(lambda u:f(u).imag,0,1,epsabs=1e-14)[0]
            symbol=complex(E.flat_near(omega,k,tau))
            flat_rows.append(dict(k=[k.real,k.imag],omega=omega,near=[symbol.real,symbol.imag],independent_absolute_error=abs(symbol-control),grazing=omega==k.real and k.imag==0))
    write(folder/'near_and_flat_controls.json',dict(flat=flat_rows,near_controls=medium_rows,wave_order=list(waves)))
    rows=[]; grid_receipts=[]
    for size in (128,256):
        grid=E.FarGrid.build(size,tau,manifest['settings']['R0_m'])
        begin=perf_counter()
        qa=a*grid.unique_q[:,None]
        J=jv(modes[None,:],qa)
        JV=J*J
        JK=J*qa*jvp(modes[None,:],qa)
        JH=a*a/2*(jv(modes[None,:]-1,qa)**2+jv(modes[None,:]+1,qa)**2)
        del J
        mapseconds=perf_counter()-begin
        mapbytes=JV.nbytes+JK.nbytes+JH.nbytes
        far={}; order_errors=[]
        saved={}
        for label,k in waves.items():
            d1,r1=grid.multiplier(k,256)
            d2,r2=grid.multiplier(k,512)
            order_errors.append(dict(k=[k.real,k.imag],multiplier_max_difference=float(np.max(np.abs(d1-d2))),**r2))
            w=np.bincount(grid.inverse,weights=d2.real)+1j*np.bincount(grid.inverse,weights=d2.imag)
            V=2*np.pi*(w@JV)
            K=2*np.pi*(w@JK)
            H=2*np.pi*k*k*(w@JH)
            far[label]=np.array([V,K,-modes*modes*V+H])
            saved[label]=np.array([d1,d2])
        grid_receipts.append(dict(grid=size,map_setup_seconds=mapseconds,persistent_diagonal_control_maps_bytes=mapbytes,far_quadrature=order_errors,L_m=grid.period,R0_m=grid.R0,R1_m=grid.R1,tau_m2=tau))
        # Save full failed multipliers and all retained individual spectra.
        np.savez_compressed(folder/f'grid{size}_arrays.npz',modes=modes,q=grid.q,**{f'far_{i}':far[label] for i,label in enumerate(waves)},**{f'near_{i}':near[label] for i,label in enumerate(waves)},**{f'exact_{i}':exact[label] for i,label in enumerate(waves)},**{f'multiplier_{i}':saved[label] for i,label in enumerate(waves)})
        for config in configs:
            o,i=config['exterior'],config['interior']
            candidate=near[o]+far[o]-near[i]-far[i]
            reference=exact[o]-exact[i]
            for cutoff in (64,128):
                use=abs(modes)<=cutoff
                for block,bindex in [('V',0),('K',1),('Kprime',1),('T',2)]:
                    ref=reference[bindex,use]; error=np.abs(candidate[bindex,use]-ref)
                    # Scale is max action of corresponding exact circle
                    # difference block on orthonormal parameter-Fourier basis.
                    scale=max(float(np.max(np.abs(ref))),1e-14)
                    worst=int(np.argmax(error))
                    rows.append(dict(**config,xi_over_kstar=xi,grid=size,trace_cutoff=cutoff,block=block,absolute_max_error=float(np.max(error)),reference_scale=scale,normalized_max_diagonal_error=float(np.max(error)/scale),worst_mode=int(modes[use][worst]),qualification='NECESSARY_DIAGONAL_SCREEN_ONLY',source='analytic circle reference and complete near quadrature'))
        print('xi',xi,'grid',size,'max diagonal block error',max(r['normalized_max_diagonal_error'] for r in rows if r['grid']==size),flush=True)
        del JV,JK,JH
    imports={name:str(sys.modules[name].__file__) for name in ('bem_inverse','bem_inverse.problem','bem_inverse.continuation.geometry','bem_inverse.on003_ewald')}
    source_hashes={p:digest(ROOT/p) for p in ('solvers/bem_inverse/on003_ewald.py','experiments/benchmark/on003.py','pytest/bem_inverse/test_on003.py')}
    result=dict(experiment='ON-003',stage='A',xi_over_kstar=xi,seconds=perf_counter()-started,precision='complex128/float64',device='cpu',threads={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},imports=imports,source_hashes=source_hashes,manifest_sha256=digest(OUT/'manifest.json'),flat=flat_rows,near_controls=medium_rows,grids=grid_receipts,rows=rows,coverage='circle diagonal controls only; curved states/full fields/derivatives not yet run')
    write(folder/'receipt.json',result)
    import csv
    with (folder/'block_diagonal_errors.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return result


def main():
    p=argparse.ArgumentParser(); p.add_argument('--xi',type=int,choices=(1,2,4,8),required=True)
    args=p.parse_args(); run(args.xi)


if __name__=='__main__': main()
