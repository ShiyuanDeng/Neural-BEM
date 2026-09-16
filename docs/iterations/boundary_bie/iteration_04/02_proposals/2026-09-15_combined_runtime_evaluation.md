# Combining analytic Jacobians with CPU/CUDA acceleration

2026-09-15. Requested evaluation; no numerical implementation or new run is
part of this document. This is an integration proposal, not an approved
experiment contract. It does not change the track handoff or supersede BIE-007.

**Follow-up:** the proposed successor was found under the new speed-up track as
[SPD-001](../../../speedup/iteration_01/03_plan.md). The user authorized the
combined measurements; that plan owns their execution. This earlier evaluation
is retained as the reasoning record.

## Recommendation

Combine the analytic residual Jacobian with faster **primal and derivative**
kernel evaluation. Expose CPU/CUDA factorization and factor reuse through one
small numerical interface. Compare derivative choice and execution choice
independently before choosing a default.

The coupled derivative already exists in BIE-004. The work is to qualify and
integrate that implementation, extend the acceleration to its derivative
functions, and measure the resulting inverse. A fresh multi-component
derivation is not the starting point.

At inspection, this checkout contained BIE-004 and BIE-006 closeouts but no
BIE-007 plan or implementation. The latest handoff says analytic integration
remains unexecuted. The user has been asked for BIE-007's location. Reconcile
this evaluation with that plan before assigning implementation scope or an
experiment ID; do not create a second competing analytic-Jacobian project.

## Evidence and its limits

The [BIE-004 result](../../../../../results/validation/boundary_bie/BIE-004-20260915-coupled-02/README.md)
compared complete 34-column Jacobians on the saved terminal two-star state,
at 1.25 GHz, 256 nodes per component and 24 source RHSs:

| Method | Median full-Jacobian time | Factorizations | RHS batches |
|---|---:|---:|---:|
| FD | 49.083 s | 69 | 69 |
| Analytic | 26.249 s | 1 | 35 |

The full analytic Jacobian agreed with gauge-retracted central FD to about
1.4e-7 relative error on two states. This is fixed-state derivative evidence;
no inverse was run by BIE-004.

A read-only aggregation of BIE-004's saved paired-timing controls gives these
mean contributions per analytic Jacobian:

| Work | Time |
|---|---:|
| Derivative-operator assembly, including its primal consistency checks | 25.252 s |
| Within that assembly: self interactions | 14.863 s |
| Within that assembly: cross interactions | 9.107 s |
| Tangent RHS formation and CPU solves together | 0.245 s |
| Base factorization | 0.042 s |

The self/cross rows are subsets of assembly, not additional costs. Assembly
accounts for about 96% of this analytic workload. Even removing the base
factorization, base solve and all measured tangent-solve work would save only
about 1.1% here. GPU **solves alone** therefore have much less headroom after
analytic derivatives are introduced. Larger refined systems and candidate
forward evaluations must be measured separately.

The earlier local acceleration assessment measured four-frequency forward
evaluations of the same terminal geometry with current inverse settings:

| Configuration | N=256 per component | N=512 per component |
|---|---:|---:|
| Current CPU | 1.735 s | 7.431 s |
| Faster real-argument Bessel routines on CPU | 0.947 s | 4.344 s |
| Those routines plus CUDA solve | 0.824 s | 3.154 s |

Those three-repeat temporary prototypes agreed with current predictions within
9e-14 relative error; the original campaign was concurrently running. They
measured forward evaluations, not analytic Jacobians or complete inverses.
Scripts, repeat timings and hashes are in
`/tmp/neural_sdf_cuda_evaluation/`; that temporary directory is not a repository
result bundle.

**Do not multiply the reported 1.87x and 2.1–2.4x improvements.** They cover
different workloads and overlapping costs. BIE-004 also uses
`validation_resolution=1024` and FD step `1e-5`, whereas the current topology
driver uses validation resolution 256 and its production FD step is `1e-4`.
The new comparison must rerun the current reference settings in every arm.

## Shared implementation

### 1. Preserve the optimizer; supply its residual Jacobian

Add an opt-in Jacobian provider to `run_multiradial_fd_inverse` in
`solvers/sdf_inverse/radial_topology.py`. It must return derivatives of the
same normalized real residual, in the same gauge-tangent basis and row order
as the existing LM step uses. Keep damping, clipping, line search, retraction,
acceptance, frequency schedule and candidate feasibility rules fixed.

Promote the coupled formulas from
`experiments/bie004_multi_derivative/operators.py` and the necessary
base/tangent solve logic from its `support.py` into project-owned solver APIs.
Keep the archived experiment intact. Production code should not import an
experiment runner or its frozen acquisition/configuration.

For each geometry and frequency, the implementation follows:

```
A U = B
A dU_j = dB_j - dA_j U
dY_j = dC_j U + C dU_j
```

Factor A once. Reuse its factors for the primal and every tangent RHS. Preserve
all 24 source columns. Stream derivative matrices or bounded chunks instead of
retaining q full dense matrices. Geometry-to-direction construction follows
the actual Cartesian gauge subspace; the frozen BIE-004 fixture is not proof
that every topology-produced state has a qualified gauge derivative.

The current objective result retains predictions/residuals but not the solved
base. Keep the accepted state's base/factors in a bounded solver workspace so
the analytic Jacobian can reuse them. Key reuse by the complete relevant
geometry, node grids, frequency, materials, acquisition and solver settings.
Invalidate it when those change, including topology events. Candidate and
refined evaluations must not accumulate a cache of dense matrices for every
trial state.

### 2. Share fast special functions across primal and derivative code

The real-positive argument fast path must cover `_kernels.py`, multi-component
incident/cross/receiver evaluation, and `shape_derivative.py` plus the promoted
coupled derivative. Retain the complex-argument reference path and the existing
near-interaction series and analytic diagonals.

The derivative helper evaluates orders `order-1` and `order+1`: derivatives of
orders 0–2 therefore require orders -1 through 3. The first forward-only
prototype's restricted 0–2 Hankel fast path is insufficient coverage. Check
negative-order identities, near/direct branch agreement, cancellation and
derivative parity. Keep float64/complex128.

BIE-004 currently recomputes primal special functions for each active
direction. Exact reuse of geometry/frequency-dependent radial values across
directions is a promising subsequent optimization. Measure it as a separately
identified change if included; rebuilding on geometry changes preserves the
exact physical model. It does not require the cross-state operator surrogate
that BIE-006 rejected.

### 3. Provide factor and solve operations on both devices

Use a small `factor(A)` / `solve(factors, RHS)` abstraction. CPU uses SciPy
LU factorization/solve. CUDA uses PyTorch LU factorization and
[`torch.linalg.lu_solve`](https://docs.pytorch.org/docs/stable/generated/torch.linalg.lu_solve.html),
which accepts existing LU factors and complex double inputs.

Retain factors, primal traces and receiver matrices on device during a CUDA
Jacobian; include transfer and synchronization costs in timings. Form
`dB-dA@U` and evaluate tangent receiver products on the device where measured
beneficial. Bound direction chunks and device memory. Keep the small LM normal
system on CPU initially. Avoid calling a fresh `torch.linalg.solve(A, rhs)`
for every analytic column, which would repeat factorization.

Full GPU special-function/derivative assembly is a later option if the combined
profile still justifies it. It is a larger scope than CUDA factor/solve support.

### 4. Update accounting with the numerical integration

Current callbacks reserve `2*q` objective evaluations before a Jacobian, and
experiment ledgers count calls to the public forward solver. An analytic path
can bypass both assumptions. Report forward assemblies, derivative assemblies,
LU factorizations, primal/tangent RHS counts, cache reuse, transfers, invalid
candidates and CPU/GPU time explicitly. A tangent solve must not become free
in the ledger just because no perturbed forward call occurred.

Preserve FD compatibility and diagnostics. Define analytic availability,
unsupported cases and constrained-boundary behavior explicitly; do not silently
fall back to FD and report a pure analytic run. Candidate feasibility remains
checked. An available unconstrained derivative is not a constrained-stationarity
certificate.

Likely shared edit areas: Kress kernel helpers, shape derivative/coupled
derivative API, multi-component forward/base workspace, factor/solve backend,
inverse Jacobian hook, work accounting and active driver configuration. This
is a contained integration across roughly 6–9 shared files plus tests and an
experiment driver, rather than two independently maintained solver paths.
Exact scope depends on BIE-007's unseen contract. A first integrated comparison
is plausibly about a working week; broad inverse qualification adds execution
and any numerical issues uncovered. This is an estimate, not a commitment.

## Runtime comparison

Use two independent options: Jacobian (`fd`, `analytic`) and execution
(`reference_cpu`, `fast_cpu`, `fast_cpu_cuda_linalg`). This produces six arms:

| | Reference CPU | Fast CPU kernels | Fast CPU kernels + CUDA algebra |
|---|---|---|---|
| FD | Current reference | Kernel improvement alone | Earlier acceleration combination |
| Analytic | Analytic integration alone | Analytic + kernel improvement | All proposed improvements |

The analytic + fast-CPU arm is essential: it shows whether CUDA adds enough
after analytic derivatives remove most factorization work.

### Stage A: numerical qualification

Follow BIE-007's gates when available. Cover the existing common/terminal
states, one-component coverage, and representative states around topology
events. Check all four training frequencies; use production/refined grids
256/512 for continuation and representative 64/128 topology states. Validate
forward/matrix parity, derivative columns in the production gauge, full
Jacobian/gradient where warranted, tangent residuals and mixed-direction Taylor
behavior. Compare analytic/accelerated paths directly with the analytic CPU
reference, and retain FD step ladders as derivative validation. Reuse declared
existing scientific tolerances; explicitly justify any added backend tolerance.

### Stage B: fixed-state timing

Start with the saved terminal two-star state, N=256 and all four training
frequencies: six arms, three alternating-order repetitions each. Time the
complete residual-plus-Jacobian operation, including geometry, primal setup,
derivative assembly, factorization, receiver evaluation and transfers. Report
both cold setup and reuse of an already accepted base, with all required setup
charged consistently. Capture phase timings, numerical work and peak host/GPU
memory. Use one numerical worker and one BLAS thread, exclude device startup
from steady-state timings but report it separately, and record other workload.

Proceed to N=512 and a second geometry only after numerical qualification and
the first comparison show a reason to expand. Cost ceilings and timeouts must
be bound in the agreed experiment contract before dispatch. Historical
one-frequency diagnostic times are insufficient to set reliable full-suite
wall limits for this comparison.

### Stage C: actual optimizer and inverse time

First replay fixed-topology refinement from the same saved state, then run
fresh automatic topology cases. Use current production geometry validation,
FD step, acquisition, initial states, gauge, materials, stage exposure,
acceptance/stopping criteria and seeds in every arm. Analytic derivatives may
change iterates, so compare both cost at a fixed number of model/update
opportunities and time to the same reconstruction-quality gate. Report
iterations, rejected steps and terminal reason to explain runtime differences.

Do not use the old number of full forward solves as a shared notion of equal
compute. First ensure budgets allow the same declared optimization exposure;
separately compare performance under equal wall-time budgets if useful. Keep
timeouts, failures and missed quality gates in the tables.

For a general claim about the current inverse, report all twelve frozen scenes
and the existing geometry, object-count, development-evaluation and resolution
gates. Early cheap cases are pilot evidence only. Separate numerical inversion
time from video rendering and report both if user-visible campaign completion
is the metric. Run timing arms sequentially; any four-worker campaign
throughput comparison is a separate measurement with matched concurrency.

## Decision

The combined approach is compatible and worth a matched evaluation. Prioritize
analytic integration and fast derivative kernels. Measure CUDA's incremental
value after those changes; adopt it where its full-cost timings justify it.
The combined end-to-end inverse speedup is currently unmeasured.
