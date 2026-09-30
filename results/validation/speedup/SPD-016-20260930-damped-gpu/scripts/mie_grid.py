"""Scratch prototype: faster dense Mie localization grid (repo files untouched).

Reference: experiments.modal_atlas.mie_localize.landscape over 800-centre chunks, as
damped_screen.localize_damped_mie calls it. Variants:
  R  order recurrence: H0, H1 from SciPy, H_{n+1} = (2n/z) H_n - H_{n-1}, H_{-n} = (-1)^n H_n
  G  the same recurrence plus the contraction and norms on the GPU (torch, complex128)
Both keep radial_coefficients, the loss definition and the clearance mask unchanged.
"""
import sys, time, json
import numpy as np
from scipy.special import hankel1
import torch

from experiments.modal_atlas import damped_screen as ds, mie_localize as ml
from experiments.modal_atlas.contrast_screen import set_contrast
from experiments.modal_atlas.diagnose import dense_grid


def hankel_orders(z, cut):
    """H_n(z) for n = -cut..cut along a new last axis, by upward recurrence."""
    h = np.empty(z.shape + (cut + 1,), complex)
    h[..., 0], h[..., 1] = hankel1(0, z), hankel1(1, z)
    for n in range(1, cut):
        h[..., n + 1] = (2 * n / z) * h[..., n] - h[..., n - 1]
    sign = (-1.0) ** np.arange(cut, 0, -1)
    return np.concatenate((h[..., :0:-1] * sign, h), axis=-1)


def products_recurrence(k, centers, sources, receivers, cut):
    zs = sources[:, 0] + 1j * sources[:, 1]
    zr = receivers[:, 0] + 1j * receivers[:, 1]
    c = np.asarray(centers)[:, None]
    ds_, dr = zs[None, :] - c, zr[None, :] - c
    n = np.arange(-cut, cut + 1)[None, None, :]
    phase = np.exp(1j * n * (np.angle(dr) - np.angle(ds_))[..., None])
    return hankel_orders(k * np.abs(ds_), cut) * hankel_orders(k * np.abs(dr), cut) * phase


def landscape_variant(observations, contrast, centers, radii, cut, device=None):
    centers = np.asarray(centers, complex)
    radii = np.asarray(radii, float)
    orders = np.arange(-cut, cut + 1)
    total = np.zeros((len(centers), len(radii)))
    for o in observations:
        acq = o.acquisition
        P = products_recurrence(o.wavenumber, centers, acq.sources, acq.receivers, cut)
        C = ml.radial_coefficients(o.wavenumber, contrast, radii, orders)
        obs = np.asarray(o.scattered)
        if device is None:
            pred = np.einsum('cpn,rn->crp', P, C) * acq.strength
            total += (np.linalg.norm(pred - obs[None, None, :], axis=2) / np.linalg.norm(obs)) ** 2
        else:
            Pt, Ct = torch.as_tensor(P, device=device), torch.as_tensor(C, device=device)
            pred = torch.einsum('cpn,rn->crp', Pt, Ct) * complex(acq.strength)
            diff = pred - torch.as_tensor(obs, device=device)[None, None, :]
            total += ((torch.linalg.vector_norm(diff, dim=2) / float(np.linalg.norm(obs))) ** 2).cpu().numpy()
    loss = 0.5 * total / len(observations)
    points = np.concatenate([o.acquisition.sources for o in observations] +
                            [o.acquisition.receivers for o in observations])
    zp = points[:, 0] + 1j * points[:, 1]
    clearance = np.min(np.abs(zp[None, :] - centers[:, None]), axis=1)[:, None] - radii[None, :]
    return np.where(clearance > 1e-9, loss, np.inf)


def grid(fn, obs, contrast, centers, radii, inside, cut):
    t = time.perf_counter()
    L = np.concatenate([fn(obs, contrast, centers[i:i + 800], radii, cut) for i in range(0, len(centers), 800)])
    return np.where(inside, L, np.inf), time.perf_counter() - t


def starts(L, centers_m, radii_m):
    """The five grid starts localize_damped_mie takes from the landscape."""
    out = []
    for index in np.argsort(L, axis=None)[:5000]:
        i, j = np.unravel_index(index, L.shape)
        if not np.isfinite(L[i, j]):
            break
        x = np.array([centers_m[i].real, centers_m[i].imag, radii_m[j]])
        if all(np.hypot(*(x[:2] - y[:2])) > .008 or abs(x[2] - y[2]) > .004 for y in out):
            out.append(x)
        if len(out) == 5:
            break
    return np.array(out)


if __name__ == '__main__':
    for spec in sys.argv[1].split(','):
        contrast, scene = spec.split(':')
        contrast = float(contrast)
        set_contrast(contrast) if contrast != 0.5 else None
        real, damped_obs, _ = ds.fitting_data(contrast, scene)
        obs = damped_obs[:3]
        centers_m, radii_m, centers, radii, inside = dense_grid()
        cut = int(np.ceil(max(abs(o.wavenumber) for o in obs) * np.sqrt(max(contrast, 1)) * radii.max() + 30))
        Lref, tref = grid(lambda o, c, x, r, k: ml.landscape(o, c, x, r, cutoff=k), obs, contrast, centers, radii, inside, cut)
        Lrec, trec = grid(landscape_variant, obs, contrast, centers, radii, inside, cut)
        torch.cuda.synchronize()
        Lgpu, tgpu = grid(lambda o, c, x, r, k: landscape_variant(o, c, x, r, k, device='cuda'), obs, contrast, centers, radii, inside, cut)
        finite = np.isfinite(Lref)
        rel = lambda L: float(np.max(np.abs(L[finite] - Lref[finite]) / np.abs(Lref[finite])))
        sref = starts(Lref, centers_m, radii_m)
        row = dict(contrast=contrast, scene=scene, cut=cut, seconds_reference=tref, seconds_recurrence=trec,
                   seconds_gpu=tgpu, max_rel_loss_recurrence=rel(Lrec), max_rel_loss_gpu=rel(Lgpu),
                   same_mask=bool(np.array_equal(np.isfinite(Lrec), finite) and np.array_equal(np.isfinite(Lgpu), finite)),
                   same_starts_recurrence=bool(np.array_equal(starts(Lrec, centers_m, radii_m), sref)),
                   same_starts_gpu=bool(np.array_equal(starts(Lgpu, centers_m, radii_m), sref)),
                   argmin_same=bool(np.argmin(Lref) == np.argmin(Lrec) == np.argmin(Lgpu)))
        print(json.dumps(row), flush=True)
