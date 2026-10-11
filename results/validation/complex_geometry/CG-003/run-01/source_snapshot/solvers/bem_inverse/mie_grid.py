"""SPD-016 order recurrence and optional device contraction for exact disks."""
import numpy as np
from scipy.special import hankel1
from . import mie_localize as ml

def hankel_orders(z, cut):
    """H_n(z) for n = -cut..cut along a new last axis, by upward recurrence."""
    h = np.empty(z.shape + (cut + 1,), complex)
    h[..., 0] = hankel1(0, z)
    if cut:
        h[..., 1] = hankel1(1, z)
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
            import torch
            Pt, Ct = torch.as_tensor(P, device=device), torch.as_tensor(C, device=device)
            pred = torch.einsum('cpn,rn->crp', Pt, Ct) * complex(acq.strength)
            diff = pred - torch.tensor(obs, device=device)[None, None, :]
            total += ((torch.linalg.vector_norm(diff, dim=2) / float(np.linalg.norm(obs))) ** 2).cpu().numpy()
    loss = 0.5 * total / len(observations)
    points = np.concatenate([o.acquisition.sources for o in observations] +
                            [o.acquisition.receivers for o in observations])
    zp = points[:, 0] + 1j * points[:, 1]
    clearance = np.min(np.abs(zp[None, :] - centers[:, None]), axis=1)[:, None] - radii[None, :]
    return np.where(clearance > 1e-9, loss, np.inf)
