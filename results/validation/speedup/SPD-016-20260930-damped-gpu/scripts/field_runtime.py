"""Optional bundle-local Hankel table hook; retain all existing field validation."""
import importlib
import numpy as np
import torch
from damped_gpu import RayTable
from experiments.modal_atlas import damped_screen as ds

field_module = importlib.import_module('gpr_bem_kress.forward')


def install_fields():
    original = field_module.hankel1
    table = RayTable(ds.GAMMA)
    counters = dict(table_calls=0, reference_calls=0)

    def hankel(order, argument):
        z = np.asarray(argument)
        # This hook only owns H0/H1 on the qualified positive damping ray.
        # Every other call retains the exact original dispatch.
        x = z.real
        if (order not in (0, 1) or not np.iscomplexobj(z) or not np.isfinite(z).all()
                or np.any(x < table.lo) or np.any(x > table.hi)
                or not np.allclose(z.imag, ds.GAMMA*x, rtol=1e-14, atol=0)):
            counters['reference_calls'] += 1
            return original(order, argument)
        values = table(torch.tensor(np.ascontiguousarray(x).ravel(), device='cuda'))
        counters['table_calls'] += 1
        return values[:, 3+order].cpu().numpy().reshape(z.shape)

    field_module.hankel1 = hankel
    return original, hankel, counters
