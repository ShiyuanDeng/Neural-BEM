"""Freeze the baseline-side request; never generate or read sealed TG-002 fields."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.io import savemat
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'solvers'),str(ROOT)]
from bem_inverse.io import read,curve_from,write,digest
from experiments.benchmark import scenes as S
from experiments.cleaned_interface import benchmark as ci
BASE=ROOT/'results/brg/tg002_shapes/2026-11-17'
SCENES=['circle','kite','peanut','star','asymmetric','c_shape','hook','cross','cog','aphex_twin']


def main():
    BASE.mkdir(parents=True,exist_ok=True); local=BASE/'local';local.mkdir(exist_ok=True)
    frequencies=np.linspace(ci.FREQUENCIES[0],ci.FREQUENCIES[-1],37)
    assert np.array_equal(frequencies[::2],ci.FREQUENCIES)
    ks=2*np.pi*frequencies*np.sqrt(4*np.pi*1e-7*6*8.854187817e-12)*.065
    layouts=[]
    for i,(f,k) in enumerate(zip(frequencies,ks),1):
        n=int(np.floor(10*k));theta=2*np.pi*np.arange(n)/n
        layouts.append(dict(index=i,frequency_hz=f,k=k,direction_angles_rad=theta,
                            directions_xy=np.column_stack((np.cos(theta),np.sin(theta))),
                            receivers_xy=10*np.column_stack((np.cos(theta),np.sin(theta)))))
    shapes=[];checks=[]
    for scene in SCENES:
        source=ROOT/f'development_results/TG-002/inputs/{scene}/truth.json'
        curve=curve_from(read(source));reference=S.truth_fixture(scene)
        assert np.max(abs(curve.values(16384)-reference.values(16384)))<1e-12
        coeff=curve.coefficients*(S.LENGTH/.065);modes=curve.modes
        z=curve.values(16384)*(S.LENGTH/.065);dz=curve.values(16384,1)*(S.LENGTH/.065)
        area=float(np.pi*np.sum(modes*abs(coeff)**2));poly=Polygon(np.column_stack((z.real,z.imag)))
        assert area>0 and poly.is_valid and np.min(abs(dz))>0
        assert np.max(abs(z))<10
        coefficient_bytes=np.column_stack((coeff.real,coeff.imag)).astype('<f8').tobytes()
        shapes.append(dict(shape=scene,modes=modes,coefficients_real=coeff.real,coefficients_imag=coeff.imag,
             coefficient_sha256=hashlib.sha256(coefficient_bytes).hexdigest(),
             coefficient_hash_encoding='little-endian float64 C-order rows [real,imag], ascending modes',
             source_path=str(source.relative_to(ROOT)),source_sha256=digest(source)))
        checks.append(dict(shape=scene,orientation='counterclockwise',signed_area=area,simple=True,
                           minimum_speed=float(min(abs(dz))),closure='periodic Fourier series',
                           maximum_radius=float(max(abs(z))),truth_fixture_agrees=True))
        savemat(local/f'{scene}.mat',dict(coefficients=coeff,modes=modes,ks=ks))
    contract=dict(schema='brg-tg002-plane-wave-request-v1',authority='BEM side generates and freezes; BRG side converts and fits',
       baseline_status='provisional BRG forward data until frozen data comparison',
       units=dict(length_unit_m=.065,origin_m=[.5,.5],coordinate_transform='x_dimensionless=(x_m-origin_m)/length_unit_m',
                  original_coefficient_unit_m=.05,coefficient_scale=.05/.065,start_center=[0,0],start_radius=1),
       background=dict(mu=4*np.pi*1e-7,epsilon=6*8.854187817e-12),
       eta_values=[.5,4],eta_definition='interior k squared / exterior k squared; equal density',
       incident_field='exp(+i*k*(direction_x*x+direction_y*y)); unit amplitude',
       requested_field='complex scattered scalar field at each finite-radius receiver; total minus incident',
       convention=dict(time='exp(-i*omega*t)',outgoing='Hankel first kind',density='equal; field and normal derivative continuous',
                       amplitude_scaling='none',phase_scaling='none'),
       geometry_definition='z(t)=sum_l c_l*exp(i*l*t), 0<=t<2*pi; x=real(z), y=imag(z); constant coefficient retains target offset',
       layout=dict(table_axes=['receiver','direction'],flat_order='C; direction index fastest',
                   flat_index_zero_based='receiver_index*n_directions+direction_index',
                   numpy_shape=['n_receivers','n_directions'],matlab_flatten="reshape(receiver_by_direction.',[],1); nonconjugating transpose",
                   requested_storage='per case/frequency complex table or separate real/imag arrays, with axes declared'),
       frequencies=layouts,shapes=shapes,
       comparison=dict(relative_complex_norm='norm(frozen-provisional)/norm(provisional)',
                       acceptance='<=max(1e-5,10*measured_BRG_refinement_error)',
                       default_tolerance=1e-5,brg_refinement_error_above_1e_4='return to coordinator',
                       rerun='only cases with a frequency exceeding the agreed tolerance'),
       reproduction_command='PYTHONPATH=solvers:. python experiments/baselines/brg/prepare_tg002.py')
    write(BASE/'data_request.json',contract)
    write(BASE/'geometry_checks.json',dict(shapes=checks,start=dict(center=[0,0],radius=1,physical_radius_m=.065),
                                         data_request_sha256=digest(BASE/'data_request.json')))
    print('Prepared',len(shapes),'shapes,',len(ks),'frequencies; request bytes',(BASE/'data_request.json').stat().st_size)

if __name__=='__main__':main()
