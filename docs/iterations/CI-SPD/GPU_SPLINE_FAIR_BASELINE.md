# GPU spline baseline: findings, design and predictions

2026-10-05. Requested by the user to make the spline/spectral comparison fair.
This is a design and evidence note. No GPU spline implementation, new benchmark
or inverse experiment was performed for this note. Predictions below are
engineering hypotheses, not measurements or approved experiment results.

## Recommendation

First implement **GPU-batched spline preparation with the existing CPU spline
trial**. This matches the actual deployment split of today's GPU-prepared
spectral update, whose finite trial projection still runs on CPU. Preserve the
same cubic interpolants, grid sizes, finite-difference step and validity tests.
Then measure fully GPU spline trials as a separate intervention, alongside a
GPU spectral-trial control if comparing equal device coverage.

Do not replace spline by linear interpolation, PCHIP, an approximate inverse or
a different boundary condition to obtain the GPU baseline. Those would change
the geometric algorithm. Output-grid oversampling can improve accuracy, but is
a separate intervention from moving the existing calculation to GPU.

## Findings already measured

Sources: [GC-001 report](../../../results/validation/cleaned_interfaces/GC-001/README.md),
[raw summary](../../../results/validation/cleaned_interfaces/GC-001/report.json), and
[iteration-30 interpretation](../cleaned_interfaces/iteration_30/01_results.md).
31 saved TG-002 states, 279 common moves; headline timings use 11 states with
three repeats. Medians below are medians of each state's repeated median.

| Existing geometry implementation | Preparation | First 1 mm trial | Later 6 mm trial |
|---|---:|---:|---:|
| CPU spline | 1,133 ms | 33.8 ms | 34.6 ms |
| CPU spectral, sampled checks | 2,197 ms | 59.5 ms | 64.6 ms |
| GPU-prepared spectral, sampled checks | 41.4 ms | 65.3 ms | 65.7 ms |
| GPU-prepared spectral, certificate checks | 41.5 ms | 97.6 ms | 487.1 ms |

The two trial columns have different displacement sizes/directions; their
difference does not isolate warm-up or cache reuse. The 6 mm certificate
numbers are stress-move timings, not the average cost of actual LM proposals.
The median paired preparation gain of GPU spectral versus CPU spline is 27.1x.
That comparison includes shared-work elimination and different device execution,
so it does not establish an intrinsic spectral-over-spline algorithm speedup.

On the fixed five-state profile panel, CPU spline preparation spent **46%** in
repeated construction of the accepted curve's normal basis. Other costs include
repeated jets/FFTs and the two spline constructions. This provides an immediate
shared-work opportunity even before moving arithmetic to GPU. Profile fractions
are diagnostic, not interchangeable with the uninstrumented timing medians.

Removing CPU spectral's discarded crop-error reconstruction saves approximately
19–24% of preparation time in three high-band probes, with bit-identical
coefficients. Batched Torch CPU spectral preparation is slower than sequential
NumPy spectral at those bands. Thus GPU preparation gains cannot all be credited
to batching alone, or to removal of unused diagnostics.

Precision: all four arms accepted 277 moves and refused the same two
self-intersections. Refined references qualified on 278/279 moves; the unresolved
kite move is excluded from accuracy rankings. Worst qualified spline/reference
error was 400.8 nm versus 0.1855 nm for spectral. The main large-error source was
**uniform-arclength output sampling/FFT aliasing**: on the worst aphex probe,
refining only the final output grid reduced 400.8 nm to 0.906 nm. Replacing cubic
inverse/position interpolation alone barely changed that error. A GPU port with
unchanged grids should retain this sampling error; device execution is not an
accuracy correction.

## CI-SPD context is different from TG-002

The existing [CI-SPD summary](../../../results/validation/cleaned_interfaces/CI-SPD/comparison_summary.json) documents GGB-001 pilot
evidence from recorded source commit `3ec2627d3ff7329453ec7b76469a0761d6f6e3de`.
It is an aggregation of previous evidence, not the TG-002 geometry replay. The
summary defines other wall as fit plus audit minus successful/failed evaluation
and derivative times; LU is already a subset of physics, not another cost to add.

| Recorded sample | BEM fit + audit | Other wall | Other share | Trial proposals | Self-intersection refusals |
|---|---:|---:|---:|---:|---:|
| 8 | 349.03 s | 320.14 s | 91.7% | 845 | 669 |
| 13 | 2.008 s | 0.524 s | 26.1% | 24 | 0 |
| 14 | 36.24 s | 32.18 s | 88.8% | 133 | 66 |

**Other wall is not a measured spline or geometry bucket.** It can contain
preparation, trial construction, validity checks, controller work, transfers,
bookkeeping and timer remainder. The high proposal/refusal counts suggest a
different bottleneck pattern from TG-002, but do not isolate its cause. Profile
these categories before predicting a CI-SPD whole-inverse gain. Porting spline
does not eliminate geometrically invalid proposals or repair model/data mismatch.
Do not apply TG-002's approximately 19% geometry share to this different pilot.

## Preserve the existing mathematical map

The maintained implementation is
[`bem_inverse/geometry.py`](../../../solvers/bem_inverse/geometry.py).
Its accepted-state update is

`T_z(a) = z + P_K[A(z + h(a) n) - A(z)]`.

`A` samples the moved curve, integrates speed spectrally, inverts normalized
arclength using a cubic spline, evaluates a periodic cubic position spline,
then takes an FFT and retains the Cartesian band K. Both moved and base
projections are needed: replacing their centred difference by a direct refit
changes the update and is outside this baseline port.

There are **two different spline systems** to reproduce:

1. **Inverse arclength:** real, nonuniform strictly increasing knots
   `alpha(theta_i)`, values `theta_i`, with the current default **not-a-knot**
   boundary conditions and the explicit final 2pi knot/value.
2. **Position:** complex values on uniform theta knots, with **periodic**
   boundary conditions and the duplicated endpoint value.

The installed SciPy 1.13.1 source constructs the inverse's banded system and
calls a CPU banded solve. Its boundary conditions must be carried into the GPU
implementation. The [official CubicSpline documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.CubicSpline.html)
distinguishes default not-a-knot from periodic and natural conditions; swapping
them would change the interpolant. This is not solved by moving input arrays to
CUDA while continuing to call the installed SciPy CPU implementation.

## Proposed device implementation

### 1. Share the accepted curve across perturbations

Prepare base positions, normal vectors and the arclength normal basis once per
exact curve/grid/M. Initially it is reasonable to compute these once on CPU and
upload them, matching today's spectral preparation. Include that CPU work and
upload in the measured wall time. A later fully device-resident base setup is
another optimization to qualify separately.

Let `d = 2*M + 1`. Batch the coarse steps
`[zero, +eps*I_d, -eps*I_d]`, with eps = 1e-7 m; build the fine zero-step base
on 2N. There are `2*d + 2` projections in total, 152 at M37. Reuse the normal
basis, and form every moved curve in a batch without reconstructing that basis
for every column. Produce the same central-difference geometry derivatives.

Give a CPU implementation the same hoisting as a diagnostic control. This
distinguishes shared-work savings from GPU arithmetic savings. The GPU baseline
should not depend on repeatedly doing avoidable work in its CPU comparator.

### 2. Batch normal moves, FFTs and speed integration

Reuse the FFT/normal-move structure of
[`bem_inverse/batched.py`](../../../solvers/bem_inverse/batched.py), but stop
before spectral coefficient quadrature. Use float64/complex128, the same
length-unit conversion, Fourier mode ordering, Nyquist omission, speed FFT,
primitive anchoring and normalized arclength. Check monotonic gaps with the
existing semantics. A spline backend must continue to do spline resampling.

### 3. Solve the nonuniform inverse spline on GPU

Construct each perturbation's knot intervals and the same not-a-knot system.
These knots change with the moved curve, so a factorization cannot be reused
across all perturbations. Batch the independent banded systems across the
perturbation dimension. A dedicated tridiagonal/PCR CUDA kernel is an appropriate
candidate after handling the boundary rows algebraically; endpoint elimination
must preserve not-a-knot equations exactly.

Use residual/finite-value checks and qualify behavior on strongly nonuniform
knots. Do not assume an unpivoted solver reproduces the CPU solver's stability
on every curve. Retain and count any explicit CPU fallback, including its time.
Avoid a dense N-by-N solve: it would turn a banded interpolation problem into
the wrong complexity and memory footprint. Avoid a Python loop issuing one
GPU operation per knot; it would replace CPU work with thousands of launches.

Evaluate the inverse with row-wise interval search and gathered cubic/Horner
evaluation. Each row has its own knots; a single shared interval-index table
would be incorrect. Targets are the existing common uniform arclength grid.

### 4. Exploit uniform periodic position knots

The position spline has identical uniform knot spacing for every perturbation,
so its cyclic system structure is reusable for each N. Either use a reusable
cyclic banded solve or compute its second derivatives with a circulant FFT
solve. This FFT solves the **periodic cubic spline coefficient system**; it is
not a replacement by Fourier position interpolation.

For spacing `h = 2pi/N`, the usual periodic second-derivative equations are

`m_(i-1) + 4*m_i + m_(i+1) = (6/h^2)*(y_(i-1) - 2*y_i + y_(i+1))`.

The circulant eigenvalue is `4 + 2*cos(2pi*j/N)`, so the coefficients can be
obtained with batched FFTs and elementwise division. Reconstruct the ordinary
cubic polynomial on each interval and evaluate it at the inverse's theta
queries. Uniform theta permits floor/index arithmetic rather than another
nonuniform search. Preserve periodic endpoint behavior and complex values.
This is a proposed algebraically equivalent construction; it still requires
coefficient/value/derivative comparisons against the installed CPU reference.

### 5. Crop, centre and return the existing interface

FFT the uniformly resampled positions, keep exactly modes -K..K and form the
same centred increment. Return the existing `ProjectedSpace` coefficient
derivatives/base projections. Keep arrays on device through the batched work
and transfer the small retained coefficients together, rather than copying
every projection to CPU. Include synchronization and all copies in wall time.

CPU preparation currently computes crop diagnostics it does not use. Treat
omitting those as an explicit preparation-only optimization, mirrored or
reported in both arms. Preserve diagnostics that trial acceptance or its
published receipt actually uses.

Bound chunks by a memory budget and record allocated/reserved peaks. A nominal
chunk limit does not include all live FFT, banded-solver and gather buffers.
Cache fixed tables and exact accepted-curve data within a fit. Prepared-state
identity includes curve bytes, K, M, grid, length unit, device/dtype and FD step;
invalidate it after an accepted curve change. Geometry preparation is already
outside frequency loops; do not claim new cross-frequency sharing for that work.

## Fair comparisons and validation

The first comparison should be GPU spline **preparation** versus GPU spectral
preparation, followed by their current CPU trials with **the same sampled
validity checks**. Report CPU-original and CPU-shared-work controls. Compare
certificate-based validity separately, or attach the same coefficient-based
validity service to both trial maps before comparing their complete costs.

Keep grids, retained band, physical move coordinates, FD step, data/physics
settings, warm-up, cache scope and device-copy accounting fixed. A pure port
should reproduce CPU spline decisions on the 31 GC-001 states and all 279
moves, including the two refusals. Suggested qualification targets for a future
pre-registration are <=1e-10 sigma0 GPU/CPU curve disagreement and <=1e-6
relative geometry-column disagreement, with residual checks for the spline
systems and diagnostics around the wrap point. These are proposed targets,
not a claim that an unimplemented port has passed them.

Test nonuniform knots, periodic derivatives, wrap endpoints and centred base
subtraction independently. Keep the existing N/2N trial-refinement gate and
validate derivatives of the actual finite trial. Direct-grid accuracy tests
must also check N/2N/4N/8N references; device equivalence alone does not cure
output aliasing. A new GPU spline experiment requires a registered ID and
approval before measurement. Any new inverse fits must use TG-002 only.

For a fair physics speedup claim, a stronger control uses **one identical
geometry update in both nodal and modal arms**. GPU nodal+spline versus GPU
modal+spectral is a comparison of optimized complete pipelines. Equal geometry
device coverage does not itself equalize LU devices, resolution qualification,
worker count or audit cost; their component receipts still matter.

## Predictions and effort

| Proposed change | Prediction, unmeasured | Effort / main uncertainty |
|---|---|---|
| Share CPU spline base jets/basis | Material preparation reduction before any GPU port. Eliminating the profile panel's 46% basis category alone would cap its preparation gain at about 1.85x if all remaining work stayed fixed | Low–medium; preserve arithmetic and measure the shared-work control |
| GPU-batched spline preparation | Initial working hypothesis: roughly 5–20x faster than the original CPU preparation on the repeated GC-001 panel, corresponding to about 60–225 ms median; no guarantee it beats GPU spectral's 41 ms | Medium–high; inverse solver, search/gather efficiency, launches and copies |
| Mature GPU spline preparation versus GPU spectral | It may become competitive or faster because it avoids the band-by-grid phase quadrature; a poor inverse-solver implementation could erase that advantage | High uncertainty; asymptotic operation counts are not device timings |
| GPU spline trial | Likely a smaller gain than preparation: one move offers much less batch parallelism, and CPU sampled validity may remain the floor | Medium; transfers and unchanged checks can dominate |
| GPU execution at unchanged grids | Near CPU spline outputs, derivatives and decisions after qualification; no systematic precision improvement predicted | Numerical qualification required; FD amplification and ill-conditioned knots |
| Independent spline output oversampling | Large stress-move aliasing should shrink, following the six GC-001 probes; extra grid cost and possible changed acceptance need separate measurement | Medium; not part of the pure GPU port |
| CI-SPD complete runtime | No defensible numeric prediction from the existing other-wall bucket; identify preparation/trial/validation/controller fractions first | Profiling required; invalid-proposal counts will not vanish |

The 5–20x preparation range is deliberately a hypothesis, not extrapolation of
spectral's 27x result. A fast tridiagonal solve, shared setup and efficient
device evaluation are prerequisites. On tiny early-stage spaces, launch/copy
overheads may make the GPU benefit much smaller or absent.

For TG-002 NS, preparation is 612.53 s of 3,273.75 s total: **18.71%**. If that
entire preparation category became 5–20x faster at unchanged trial/physical/audit
work, the conditional whole-run saving would be about **15.0–17.8%**, or
**1.18–1.22x** speedup. This is an Amdahl scenario, not an inverse prediction;
endpoint timing-panel gains need not transfer to every earlier preparation.
Eliminating the full measured geometry-update category still caps the direct
TG-002 improvement at about 1.24x. CI-SPD needs its own measured fractions.

The intended outcome is an optimized, qualified spline baseline. Its measured
runtime can then support a fair comparison; the current spectral-GPU versus
spline-CPU preparation gap should not be presented as an algorithm-only gain.
