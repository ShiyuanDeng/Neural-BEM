"""FM-001: forced CUDA OOM must reuse the original LU on the host, also for A^H."""
from pathlib import Path
from unittest.mock import patch
import warnings
import numpy as np
import torch
from gpr_bem_kress.cuda_assembly import DeviceFactors
from experiments.cleaned_interface.io import write,digest
rng=np.random.default_rng(50191)
a=rng.normal(size=(64,64))+1j*rng.normal(size=(64,64))+20*np.eye(64)
b=rng.normal(size=(64,5))+1j*rng.normal(size=(64,5))
records=[]
for adjoint in (False,True):
    factors=DeviceFactors(torch.as_tensor(a,device='cuda'),fallback=True)
    with warnings.catch_warnings(record=True) as caught, patch.object(factors,'_solve_device',side_effect=torch.OutOfMemoryError('injected qualification failure')):
        x,residual=factors.solve(b,adjoint=adjoint)
    ref=np.linalg.solve(a.conj().T if adjoint else a,b)
    relative=float(np.linalg.norm(x-ref)/np.linalg.norm(ref))
    assert factors.fallback_count==1 and factors._resident is None
    assert residual<1e-12 and relative<1e-12
    records.append(dict(adjoint=adjoint,residual=residual,relative_error=relative,fallback_count=factors.fallback_count))
write(Path(__file__).with_suffix('.json'),dict(passed=True,records=records,script_sha256=digest(__file__)))
print(records)
