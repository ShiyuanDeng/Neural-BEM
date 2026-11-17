"""Saved noisy real-frequency data, shared by every method.

Convention (fixed before any run):

- Noise is added to the clean real catalog only, one frequency at a time.
- At each frequency the real and imaginary parts of every sample get independent
  Gaussian noise of standard deviation ``sigma = level*||clean_f||/sqrt(2*24)``.
  The expected noise norm then equals ``level`` times the clean norm.
- ``expected_relative`` is that level; ``realized_relative`` is the norm of the
  noise actually drawn over the clean norm, per frequency. They differ by chance.
- Draw ``d`` of case number ``i`` uses ``SeedSequence(d, spawn_key=(i,))``. The unit
  normal draws depend only on the draw and the case, so 5% noise is the 1% noise
  of the same draw times five.

Files are written once and never overwritten; every method reads these arrays.
"""
from pathlib import Path

import numpy as np

from bem_inverse.io import digest, read
from experiments.benchmark import campaign as C, scenes as S
from experiments.cleaned_interface import benchmark as ci

from . import runs as R


def tag(percent, draw):
    return f'n{percent:g}d{draw}'


def path(percent, draw, case, root=R.RESULTS):
    return Path(root)/'_shared'/'noise'/tag(percent, draw)/f'{case}.npz'


def draw_noise(clean, percent, draw, case):
    """(observed, sigma per frequency) for a clean (24, 19) catalog."""
    rng = np.random.default_rng(np.random.SeedSequence(draw, spawn_key=(S.CASES.index(case),)))
    unit = rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape)
    sigma = percent/100*np.linalg.norm(clean, axis=0)/np.sqrt(2*len(clean))
    return clean+sigma[None, :]*unit, sigma


def make(percent, draws, cases=R.CASES_ALL, root=R.RESULTS):
    """Write the missing noise files; existing ones are checked, not replaced."""
    written = 0
    for draw in draws:
        for case in cases:
            source = ci.ROOT/C.row(case)['data']
            data = read(source)
            clean = np.asarray(data['clean_real'])+1j*np.asarray(data['clean_imag'])
            observed, sigma = draw_noise(clean, percent, draw, case)
            target = path(percent, draw, case, root)
            if target.exists():
                if not np.array_equal(np.load(target)['observed'], observed):
                    raise ValueError(f'Saved noise differs from its rule: {target}')
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.stem+'.tmp.npz')
            np.savez_compressed(temporary, observed=observed, sigma_real_imag=sigma,
                expected_relative=percent/100, draw=draw, case_index=S.CASES.index(case),
                realized_relative=np.linalg.norm(observed-clean, axis=0)/np.linalg.norm(clean, axis=0),
                frequencies_hz=np.asarray(ci.FREQUENCIES), clean_sha256=digest(source))
            temporary.replace(target)
            written += 1
    return written


def load(percent, draw, case, root=R.RESULTS):
    target = path(percent, draw, case, root)
    if not target.exists():
        raise FileNotFoundError(f'{target} is missing; run "python -m experiments.comparison noise" first')
    with np.load(target) as saved:
        row = {k: saved[k] for k in saved.files}
    if str(row['clean_sha256']) != digest(ci.ROOT/C.row(case)['data']):
        raise ValueError(f'{target} was drawn from different clean data')
    return row
