# Put reciprocal Kress derivatives before further runtime optimization

2026-09-16. Review requested after SPD-004: “check out the latest results on
kress with reciprocal derivatives … that should come before speed up we
proposed here?” This revises the next-work recommendation. It does not promote
a production default or launch a new full-inverse timing campaign.

**Recommendation: first qualify and integrate the reciprocal derivative with
the existing nodal Kress forward. Then measure SPD-004 readiness on that new
baseline.** Defer optimization of per-direction operator assembly and a GPU
port until the remaining cost has been measured. Keep earlier fine-grid
feasibility and adaptive topology/shape/data decisions on the architectural
agenda; reciprocal derivatives make their inner fits cheaper but do not
resolve inadmissible geometry or choose the correct topology by themselves.

## Why the evidence changes the order

The [single-object experiments](../../boundary_bie/iteration_05/01_exploration.md)
and [coupled follow-up](../../boundary_bie/iteration_05/02_coupled_modes_and_measurements.md)
separate the derivative improvement from the modal representation. The nodal
Kress path benefits strongly without replacing its forward solver.

For the supported equal-permeability problem, source and receiver boundary
traces give shape sensitivities through a boundary product weighted by normal
motion. The receiver illuminations reuse the forward factorization; additional
shape columns are contractions. The existing
[production bridge](../../../../solvers/sdf_inverse/analytic_jacobian.py)
instead assembles differentiated operators and solves a tangent problem for
every direction at every frequency. The prototype's
[nodal implementation](../../../../experiments/modal_muller_research/coupled_inverse.py)
removes that work while retaining multiple scattering in both trace sets.
A related continuous adjoint boundary-product formula is given in
[Guo and de Hoop (2013), equation 15](https://cpb-us-e1.wpmucdn.com/blogs.rice.edu/dist/8/4754/files/2020/12/SEG-2013-1057.pdf);
the repository's acquisition-specific implementation is checked independently
against its differentiated Kress operator.

The numerical evidence is unusually useful for prioritization:

| Single-object case | Nodal operator derivative | Nodal reciprocal derivative | Fit speedup | Forward/Jacobian evaluations in either arm |
|---|---:|---:|---:|---:|
| Clean | 1.9585 s | 0.1042 s | 18.79x | 14 / 14 |
| 1% noise | 3.6461 s | 0.1927 s | 18.92x | 22 / 22 |
| Missing mode 7 + noise, before enrichment | 5.2920 s | 0.2780 s | 19.03x | 37 / 37 |

These are medians of three runs from the
[raw single-object summary](../../../../results/experiments/modal_muller_20260916/hadamard_inverse/summary.json).
The matched evaluation counts and near-identical recovered parameters support
a derivative-cost explanation rather than an easier optimization trajectory.
The missing-mode row retains its model error; optimizer success there does not
mean the missing shape has been recovered.

At the coupled qualification fixture, the 64-node reciprocal Jacobian differs
from the 256-node operator derivative by `3.7484e-14` in relative norm, with
worst column `4.6087e-14`. Neglecting interaction would change the data by
25.8%, so this checks meaningful multiple scattering. See the
[qualification record](../../../../results/experiments/modal_muller_20260916/coupled_inverse/qualification.json).
The [coupled inverse summary](../../../../results/experiments/modal_muller_20260916/coupled_inverse/summary.json)
also has successful nodal reciprocal fits at 0.192/0.343/0.550 s; its comparison
is against modal reciprocal fits, not a timed coupled operator-derivative arm.

The current 16 experimental tests were rerun for this review: **16 passed in
6.40 s**. They cover coupled derivatives, paired/full acquisitions, complex
strengths, transpose identities and directional finite differences, among
other checks. No new timing ratio is claimed from this test run.

## Relation to SPD-004 and the other proposals

SPD-004 skips an unnecessary continuation phase after an adequate topology
handoff. Reciprocal Kress differentiation can reduce the cost of the actual
shape fits inside topology search, candidate refinement and continuation,
including cases that never become ready to stop early. That is a broader
opportunity within the existing pipeline.

The two savings overlap. SPD-004 removed 340 expensive directional assemblies
on each easy case; those assemblies would disappear from the reciprocal path
anyway. Readiness can still avoid forward solves, optimizer setup and repeated
assessment, but its incremental 5.12x/6.72x gains must be remeasured. Multiplying
those factors by 19 would double-count much of the saved work.

SPD-003's exact-reuse idea remains valid in principle, but its contract was
written around expensive operator derivatives. Reconsider caching of forward
states, factors and traces after reciprocal integration. GPU work on the old
directional assembly would optimize a computation this approach removes.

The newer residual-guided mode and frequency selection experiments also give
concrete evidence for the architectural direction we proposed. Their coupled
missing-mode example reaches 0.030 mm combined RMS after selecting an extra
frequency and component-specific modes. This is one positive example and a
noise-only control, not a qualified automatic topology policy. The idea can
be investigated with the nodal backend as well; modal traces are not a
prerequisite for cheap shape sensitivities.

## Recommended sequence and remaining checks

1. **Qualify reciprocal nodal derivatives on production states.** Include
   Cartesian gauge directions, every production training frequency, refined
   grids, and saved difficult states before/after topology events. Compare
   directional differences and the existing discrete analytic derivative.
   The reciprocal identity differentiates the continuous problem; its numerical
   approximation need not equal a coarse discrete residual derivative.
2. **Use the same full controller and schedule for the first comparison.**
   Preserve normalization, feasibility checks, constrained-direction policy,
   recovery requirements and initialization. Time topology, candidate fits,
   continuation and endpoint verification separately. Retain the current
   derivative for unsupported material cases. Account for primal and reciprocal
   RHS work explicitly rather than calling cheap contractions full solves.
3. **Measure the combination with readiness.** Compare the current fast
   baseline, reciprocal Kress alone, and reciprocal Kress plus SPD-004 under
   the same final quality requirements; use the existing SPD-004 arm as
   additional context or repeat it under matched timing conditions. This
   separates cheaper fitting from avoiding unnecessary fitting.
4. **Revisit the outer decisions with the new cost profile.** Earlier fine-grid
   feasibility remains directly relevant to failed handoffs. Then investigate
   component-specific shape detail, frequency information and candidate effort.
   Prefer explicit Jacobians for the current small paired acquisition unless
   measurement proves otherwise; matrix-free actions become compelling at
   larger acquisition sizes. Select CPU/GPU work from the remaining profile.

## Limits of the current result

The roughly 19x numbers include fitting but exclude independent data generation
and final validation. Adding each run's separately recorded validation cost
reduces the single-object ratios to about 7.12x, 9.80x and 11.49x respectively;
these are arithmetic summaries of saved timings, still not automatic topology
pipeline measurements. They cannot be compared directly with SPD-004's full
worker times.

The prototype uses known topology and common lossless nonmagnetic materials.
Production topology events, close boundaries, all production frequencies,
unsupported material cases and broader noise/initialization coverage still
need qualification. The native modal path's bounding-circle and logarithm
certificates are separate restrictions; they do not have to be imported with
the nodal derivative. Conversely, retaining Kress does not fix the existing
fine-grid clearance failures.

These are exploratory records. Several early run-manifest source hashes differ
from the subsequently extended checkout; all 18 source hashes in the latest
coupled `findings_summary.json` match the checkout reviewed here. A production
comparison should freeze its actual sources and inputs afresh. This does not
invalidate the saved numerical observations, but a current test pass is not
an exact replay of every earlier timed source version.
