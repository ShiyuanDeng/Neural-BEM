# MC-001 modal entry screen

The [approved contract](../../docs/iterations/modal_compression/iteration_01/03_plan.md)
owns scope, qualification and conditional continuation. This isolated package
imports the older numerical sources without editing them.

`core.py` constructs analytic directional derivatives of the hybrid
analytic-log/FFT Galerkin operator, incident traces and receiver map. Centered
full reassembly differences check these derivatives. Independently refined
nodal Kress fields and reciprocal shape derivatives check the physical result.
Wavenumbers and acquisition coordinates stay fixed during differentiation.

`run.py` selects the first qualified cutoff on a frozen ladder, saves complete
matrices and six physical derivative directions, constructs arbitrary
entrywise masks by sorted magnitudes in each block, and re-solves. The union
contains the forward and six derivative supports; the derivative of the
compressed forward uses that same frozen mask. Reciprocal/Hadamard estimates
from its traces are reported separately.

The retained count measures a **shared sparsity pattern**, with the identity
counted separately. It is not total bytes for storing all seven matrices and
is not a sparse implementation or runtime speedup. All diagnostic construction
and factorization is dense. Relative norms of individual physical data
derivatives have a floor of `1e-8` times the largest tested directional norm;
matrix refinement comparisons use a `1e-12` largest-block floor.

Run from the repository root with the EMNerf environment and single-thread
BLAS:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q experiments/modal_entry_screen/test_core.py
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_entry_screen.run --output results/validation/modal_compression/MC-001-NEW-ID
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_entry_screen.audit results/validation/modal_compression/MC-001-NEW-ID
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_entry_screen.plots results/validation/modal_compression/MC-001-NEW-ID
```

Every run requires a fresh output directory. Configuration includes numerical
source hashes, exact coefficients, acquisition, cutoff/tolerance ladders and
resource counts. `audit.py` reconstructs masks and re-solves from saved arrays;
`plots.py` creates PNG/SVG scientific figures and a local HTML gallery.

Tests cover minimal tail selection including tiny values, pure-normal
directions, multi-step derivative convergence on three shapes, independent
circle physics, and differentiation of the actual frozen-mask forward.
