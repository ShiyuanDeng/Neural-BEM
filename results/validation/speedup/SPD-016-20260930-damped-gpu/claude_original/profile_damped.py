"""Scratch profile (read-only on the repo): where a damped attempt spends CPU time.

1. One damped forward solve at N=512 and 1024: assembly vs LU vs RHS/readout.
2. The dense Mie localization grid on damped data: Hankel products vs coefficients vs contraction.
"""
import sys, time, json
import numpy as np

from experiments.modal_atlas import damped_screen as ds, damped, mie_localize as ml
from experiments.modal_atlas.contrast_screen import set_contrast
from experiments.modal_atlas.diagnose import dense_grid
from experiments.shape_continuation import forward as F
from gpr_bem_kress.execution import execution
from scipy.linalg import lu_factor

contrast = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
scene = sys.argv[2] if len(sys.argv) > 2 else 'shifted_star'
set_contrast(contrast)
real, damped_obs, initial = ds.fitting_data(contrast, scene)
print('frequencies', len(real), 'damped k range', abs(damped_obs[0].wavenumber), abs(damped_obs[-1].wavenumber))

# --- 1. one damped solve, broken down
for nodes in (512, 1024):
    o = damped_obs[5]
    curve = initial.nodes(nodes)
    assemble, receivers, incident = F._operators(curve)
    k = o.wavenumber
    ki = k*np.sqrt(contrast)
    with execution(kernels='reference', device='cpu'):
        t = time.perf_counter(); A = np.asarray(assemble(curve, k, ki).system_matrix); ta = time.perf_counter()-t
        t = time.perf_counter(); f = lu_factor(A); tl = time.perf_counter()-t
        t = time.perf_counter(); rec = receivers(curve, o.acquisition.receivers, k)
        fld, nrm = incident(curve, o.acquisition.sources, k, o.acquisition.strength); tr = time.perf_counter()-t
    t = time.perf_counter(); st = damped.solve(initial, k, contrast, o.acquisition, nodes); tt = time.perf_counter()-t
    # the same solve at the real wavenumber through the CUDA default
    t = time.perf_counter(); F.solve(initial, real[5].wavenumber, contrast, real[5].acquisition, nodes); treal = time.perf_counter()-t
    t = time.perf_counter(); F.solve(initial, real[5].wavenumber, contrast, real[5].acquisition, nodes); treal2 = time.perf_counter()-t
    print(json.dumps(dict(nodes=nodes, damped_assembly=ta, damped_lu=tl, damped_rhs_readout=tr, damped_total=tt,
                          real_cuda_first=treal, real_cuda=treal2)), flush=True)

# --- 2. Mie grid, as localize_damped_mie does it, components timed on one chunk
obs = damped_obs[:3]
centers_m, radii_m, centers, radii, inside = dense_grid()
cut = int(np.ceil(max(abs(o.wavenumber) for o in obs) * np.sqrt(max(contrast, 1)) * radii.max() + 30))
chunk = centers[:800]
orders = np.arange(-cut, cut+1)
t = time.perf_counter()
for o in obs:
    P = ml.geometric_products(o.wavenumber, chunk, o.acquisition.sources, o.acquisition.receivers, orders)
tp = time.perf_counter()-t
t = time.perf_counter()
for o in obs:
    C = ml.radial_coefficients(o.wavenumber, contrast, radii, orders)
tc = time.perf_counter()-t
t = time.perf_counter()
for o in obs:
    np.einsum('cpn,rn->crp', P, C)
te = time.perf_counter()-t
t = time.perf_counter()
ml.landscape(obs, contrast, chunk, radii, cutoff=cut)
tl = time.perf_counter()-t
chunks = int(np.ceil(len(centers)/800))
print(json.dumps(dict(centers=len(centers), radii=len(radii), cut=cut, orders=len(orders), chunks=chunks,
                      per_chunk_products=tp, per_chunk_coefficients=tc, per_chunk_einsum=te, per_chunk_landscape=tl,
                      estimated_grid=tl*chunks,
                      same_acquisition_all_freqs=all(np.array_equal(o.acquisition.sources, obs[0].acquisition.sources) for o in obs))), flush=True)
