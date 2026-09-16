# Compiled BIE-005 scattering: integrate the Kress backend in stages

2026-09-16. User-requested review: “theres also a compiled version in bie 005,
have a look, should we integrate it?” Review complete; integration recommended
as an opt-in backend. No production implementation or new inverse dispatched.
Owner/reviewer: Codex `/root`, self-review.

**Yes: pursue the compiled Kress scattering matrices and their shape
derivatives for fixed-topology fitting.** The latest extension supports actual
deformation, so the proposal is broader than a catalog of rigid objects.
Keep the existing Cartesian shape space, controller and endpoint qualification.
The priority remains geometry-validation cost plus this solver reduction before
GPU work; compilation alone does not remove the measured feasibility overhead.

## What the evidence establishes

The [fixed-template library](../../../boundary_bie/iteration_05/03_scattering_library.md)
eliminates each object's boundary traces into an incoming-to-outgoing matrix
`T = P A^-1 B`. The [deformable extension](../../../boundary_bie/iteration_05/04_deformable_scattering.md)
also compiles `dT` for shape directions using reciprocal trace products. The
online coupled system is `(I - T U) beta = T a`; interactions remain coupled.
Pose changes reuse `T`, while a changed shape recompiles that object's matrices
at each frequency. This is mathematical reduction and reuse; the implementation
uses NumPy/SciPy rather than a CUDA or native-code compilation backend.

Median complete local deformation fits, including compilation and rebuilds:

| Method | Two objects, clean | Four objects, clean | Four objects, 1% noise |
|---|---:|---:|---:|
| Full Kress, 64 nodes, reciprocal | 0.234 s | 0.994 s | 1.364 s |
| Full Kress, qualified 32 nodes, reciprocal | 0.104 s | 0.351 s | 0.602 s |
| Compiled Kress, 32 nodes, fresh changed shapes | 0.089 s | 0.215 s | 0.242 s |
| Native Laurent compiler, fresh changed shapes | 0.527 s | 1.194 s | 1.363 s |
| Compiled Kress, checked local linear models | 0.118 s | 0.376 s | 0.364 s |

The relevant noisy-case gain is **2.48x against accuracy-qualified Kress**, or
5.63x against the 64-node control. The native Laurent compiler is slower here.
Checked linear models also lose to fresh Kress compilation on these fixtures;
use the exact-recompilation path first. “Exact” here refers to rebuilding the
finite scattering representation, whose truncation still requires qualification.

All 54 archived inverses report convergence. The largest recovered-coordinate
difference from 64-node Kress is below `2.5e-8` in the experimental chart. These
fits have known counts, nearby starts, and only three shape coordinates plus
three pose coordinates per object. They use two frequencies and exclude
independent data generation, resolution qualification and final validation.
They therefore do not establish subsecond automatic topology reconstruction.

The [saved-evidence audit](compiled_scattering_review/audit.json) recalculates
all timing medians and verifies **43/43 benchmark source hashes still match**.
The BIE report records 30 passing experimental tests; this review did not rerun
tests or numerical experiments.

## Compatibility with the actual topology states

Cartesian Fourier curves can be converted exactly into finite Laurent
coefficients: for complex Cartesian cosine/sine coefficients `C_k, S_k`,
`z_k = (C_k - i S_k)/2` and `z_-k = (C_k + i S_k)/2`. This needs no shape fit
and does not require restricting the production representation to the six
coordinates used by the BIE benchmark.

The prototype requires disjoint bounding circles and acquisition points outside
those circles. Applying its coefficient-sum radius bound to archived TOP-025
states gives:

- **8/8 available continuation handoffs pass** both geometric conditions.
- **503/503 nonempty saved topology trajectory states pass**; four additional
  records are empty states and need the existing free-space path.
- The smallest saved pair's circle gap is about **7.19 mm**.

This is arithmetic on saved coefficients, with source/input hashes and a
[reproduction script](compiled_scattering_review/audit_saved_evidence.py).
It is encouraging coverage, not accuracy qualification: these records exclude
unsaved trials, rejected proposals and continuation trajectories. Positive
circle separation does not establish that order 12 suffices. It also does not
prove the native compiler's separate log-series certificate; the nodal compiler
does not invoke that certificate.

## Integration boundary and sequence

1. **Port the nodal compiler and reduced forward/Jacobian together.** Adapt
   the existing Cartesian coefficients and every production gauge direction;
   keep the optimizer, normalization, retraction and feasibility policy. Do not
   substitute the experimental six-coordinate chart or its least-squares driver.
   Preserve the current `2e-11` internal objective/Jacobian base-consistency
   check. Add separately declared comparison against refined full Kress: the
   exploratory `1e-9` field gate alone is not a drop-in guarantee for that check.
2. **Qualify both local node count and outgoing angular order on real states.**
   Include pre/post events, all four training frequencies, and the full K9/K17
   reachable basis. Do not inherit the 32-node/order-12 settings from the small
   fixtures. Keep a fixed cylindrical normalization across a shape family and
   include normalization, shape, frequency, material and resolution in cache
   validity. Invalidate changed components after topology events. Unsupported
   or insufficiently converged states use full Kress, with reason and cost logged.
3. **Use it first inside continuation shape fits.** Retain full Kress for
   topology-derivative maps, topology acceptance and final 256/512 checks. The
   current topology map explicitly needs interior fields for removal and
   exterior fields near boundaries for insertion. `ScatteringScene` supplies
   exterior receiver data outside bounding circles. The shape compiler discards
   local traces after compiling shape jets; replacing the TD path needs a separately
   qualified local field/trace reconstruction interface.
4. **Measure full workers against SPD-005 reciprocal plus readiness.** Include
   merge as a single-object control and central-ellipse-star/far-two-stars as
   hard multi-object cases, plus an easy readiness case. Retain failed recovery
   outcomes. Count compilation, all trial solves, fallback, screening and final
   validation. Extend to topology candidate fits and all twelve scenes only
   after the fixed-topology comparison establishes a benefit at unchanged final
   accuracy and data access.

The existing reciprocal derivative and readiness work remain useful. The
compiled backend reduces the forward system; reciprocal identities make its
shape derivatives cheap; readiness can avoid a fit altogether. Their gains
overlap and must be measured together. A one-object scene may gain little from
inter-object elimination, and death/split already skip continuation with
readiness, so they are poor primary targets for this backend.

In SPD-005, 94.6% of one profiled continuation stage was stencil feasibility
checking. A reduced field solver leaves those checks in place. Continue exact
geometry-validation reuse and separately qualified constraint-policy work;
do not predict a whole-inverse gain by multiplying the local BIE timings.

The reuse strategy is consistent with established scattering-matrix methods
for separated particles, including [Lai, Kobayashi and Greengard (2014)](https://arxiv.org/abs/1407.3868).
That prior work supports the architectural mechanism, not the local benchmark
numbers or production integration qualification recorded here.
