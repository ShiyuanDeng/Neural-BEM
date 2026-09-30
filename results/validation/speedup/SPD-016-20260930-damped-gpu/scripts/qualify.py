"""Fresh SPD-016 matrix, prediction, Jacobian and full localization-grid gates."""
import json
from pathlib import Path
import time
import numpy as np
import torch
from experiments.modal_atlas import damped, damped_screen as ds
from experiments.modal_atlas import mie_localize as ml
from experiments.modal_atlas.contrast_screen import set_contrast
from experiments.modal_atlas.diagnose import dense_grid
from experiments.shape_continuation import forward as F
from experiments.shape_continuation.atlas import orthonormal_normal_basis
from scipy.special import jv, hankel1
from damped_gpu import RayTable
import mie_grid
import runtime

BUNDLE = Path(__file__).resolve().parents[1]
reference_solve, reference_landscape = damped.solve, ml.landscape
accelerated_solve = runtime.install()
rows = []


def emit(row):
    rows.append(row)
    print(json.dumps(row), flush=True)
    (BUNDLE / 'qualification.json').write_text(json.dumps(rows, indent=2) + '\n')
    assert row['passed'], row


def relative(a, b):
    return float(np.linalg.norm(a-b) / max(np.linalg.norm(b), 1e-300))


ds.verify()
table = RayTable(ds.GAMMA)
rng = np.random.default_rng(0)
x = np.sort(np.r_[table.edges, np.exp(rng.uniform(np.log(.01), 0, 20000)), rng.uniform(1, 100, 80000)])
z = x * table.w
ref = np.stack([jv(n, z) for n in range(3)] + [hankel1(n, z) for n in range(3)], -1)
got = table(torch.as_tensor(x, device='cuda')).cpu().numpy()
err = float(np.max(np.abs(got-ref) / np.abs(ref)))
emit(dict(kind='table', max_relative=err, passed=err <= 1e-11))

for contrast, scene in [(0.5, 'shifted_star'), (13.3, 'new_asymmetric')]:
    set_contrast(contrast)
    _, observations, initial = ds.fitting_data(contrast, scene)
    saved = json.loads((ds.OUT / 'runs/D' / ds.tag(contrast) / scene / 'result.json').read_text())
    endpoint = ds.ast.curve_from(saved['final_curve'])
    for shape_name, shape in [('initial', initial), ('endpoint', endpoint)]:
        for index in (0, 5, 18):
            o = observations[index]
            for nodes in (512, 1024):
                t = time.perf_counter()
                ref = reference_solve(shape, o.wavenumber, contrast, o.acquisition, nodes)
                ref_s = time.perf_counter() - t
                t = time.perf_counter()
                got = accelerated_solve(shape, o.wavenumber, contrast, o.acquisition, nodes)
                got_s = time.perf_counter() - t
                basis = orthonormal_normal_basis(ref.curve, 9)
                jr, jg = F.shape_jacobian(ref, basis), F.shape_jacobian(got, basis)
                me = float(np.max(np.abs(got.matrix-ref.matrix))/np.max(np.abs(ref.matrix)))
                pe, je = relative(got.prediction, ref.prediction), relative(jg, jr)
                emit(dict(kind='forward_jacobian', contrast=contrast, scene=scene,
                          shape=shape_name, frequency_index=index, nodes=nodes,
                          matrix_max_relative=me, prediction_relative=pe,
                          jacobian_relative=je, reference_seconds=ref_s,
                          accelerated_seconds=got_s, residual=got.system_residual,
                          passed=me<=1e-11 and pe<=1e-10 and je<=1e-10))
    obs = observations[:3]
    cm, rm, centers, radii, inside = dense_grid()
    cut = int(np.ceil(max(abs(o.wavenumber) for o in obs)*np.sqrt(max(contrast, 1))*radii.max()+30))
    a, ta = mie_grid.grid(lambda o,c,x,r,k: reference_landscape(o,c,x,r,cutoff=k), obs, contrast, centers,radii,inside,cut)
    b, tb = mie_grid.grid(lambda o,c,x,r,k: mie_grid.landscape_variant(o,c,x,r,k,device='cuda'), obs,contrast,centers,radii,inside,cut)
    finite = np.isfinite(a)
    error = float(np.max(np.abs(b[finite]-a[finite])/np.abs(a[finite])))
    same_mask = bool(np.array_equal(finite,np.isfinite(b)))
    same_starts = bool(np.array_equal(mie_grid.starts(a,cm,rm),mie_grid.starts(b,cm,rm)))
    emit(dict(kind='mie_grid', contrast=contrast,scene=scene,reference_seconds=ta,
              accelerated_seconds=tb,max_relative_loss=error,same_mask=same_mask,
              same_starts=same_starts,passed=same_mask and same_starts and error<=1e-11))
print('QUALIFICATION_PASS', flush=True)
