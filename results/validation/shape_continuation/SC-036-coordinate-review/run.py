"""SC-036 zero-field coordinate and SC-035 speed-qualification review.

All truth geometries below are diagnostic controls, never inverse inputs.
Run under EMNerf with PYTHONPATH=solvers:. and single-thread BLAS.
"""
from pathlib import Path
import numpy as np
from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import normal_basis, reparameterize

HERE = Path(__file__).resolve().parent
BASE = sc.ROOT / 'results/validation/shape_continuation/SC-029-atlas-strategies/runs/baseline'


def weighted_basis(columns, weights):
    u,s,_ = np.linalg.svd(np.sqrt(weights[:,None])*columns, full_matrices=False)
    return u[:,s>1e-10*s[0]]


def captured(columns, values, weights):
    q = weighted_basis(columns, weights)
    y = np.sqrt(weights)*values
    return float(np.linalg.norm(q.T@y)**2 / np.linalg.norm(y)**2)


def measure(curve):
    nodes=curve.nodes(8192)
    w=nodes.arc_length_weights/nodes.perimeter
    z=curve.values(8192)-curve.coefficients[curve.band]
    n=nodes.normals @ np.array([1,1j])
    arc=normal_basis(nodes,3)
    theta=np.angle(z)
    cosine=(z/np.abs(z)*np.conj(n)).real
    translation={}
    for axis, h in [('x',n.real),('y',n.imag)]:
        translation[axis]={str(m):captured(normal_basis(nodes,m),h,w) for m in (3,9,24,48)}
    out=dict(translation_normal_energy_captured=translation,
             minimum_ray_cosine=float(np.min(cosine)),
             radius_mm=float(50/np.max(np.abs(nodes.curvatures))))
    if np.min(cosine)>.05:
        radial=np.column_stack((n.real,n.imag,cosine,
            cosine*np.cos(2*theta),cosine*np.cos(3*theta),
            cosine*np.sin(2*theta),cosine*np.sin(3*theta)))
        a,b=weighted_basis(arc,w),weighted_basis(radial,w)
        singular=np.linalg.svd(a.T@b,compute_uv=False)
        out.update(principal_cosines=singular, arclength_rank=a.shape[1],radial_rank=b.shape[1],
            radial_translation_capture=[captured(radial,n.real,w),captured(radial,n.imag,w)],
            arc_fraction_of_radial_directions=[captured(arc,radial[:,i],w) for i in range(7)],
            radial_fraction_of_arc_directions=[captured(radial,arc[:,i],w) for i in range(7)])
    return out


def band_review(curve):
    rows=[]
    for k in (8,12,16,24,48):
        try:
            projected,error=reparameterize(curve,k,tolerance=np.inf)
            n=projected.nodes(8192)
            v=n.speeds
            vb=n.perimeter/(2*np.pi)
            rows.append(dict(K=k,projection_error_mm=50*error,
                speed_ratio=float(np.max(v)/np.min(v)),
                nominal_radius_mm=50*vb/k,
                corrected_lower_radius_mm=float(50*np.min(v)**2/(k*np.max(v))),
                actual_radius_mm=float(50/np.max(np.abs(n.curvatures))),
                correction_factor=float((np.min(v)/vb)**2/(np.max(v)/vb))))
        except ValueError as exc:
            rows.append(dict(K=k,refusal=str(exc)))
    return rows


out={}
for case in ('wrong_circle','peanut','kite','circle_to_star','circle_to_c','hook'):
    curve=ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    out[case+'_truth']=dict(coordinates=measure(curve),state_band=band_review(curve))
for case in ('peanut','kite','circle_to_c'):
    hist=sc.read(BASE/case/'none/stage_1_history.json')['history']
    curve=ast.curve_from(hist[-1]['coefficients'])
    out[case+'_collapsed']=dict(coordinates=measure(curve),state_band=band_review(curve))
sc.write(HERE/'results.json',out)
for case, row in out.items():
    c=row['coordinates']
    print(case,'translation M3',*[round(c['translation_normal_energy_captured'][x]['3'],6) for x in ('x','y')],
          'ray min cosine',round(c['minimum_ray_cosine'],4),
          'principal',np.round(c.get('principal_cosines',[]),4))
