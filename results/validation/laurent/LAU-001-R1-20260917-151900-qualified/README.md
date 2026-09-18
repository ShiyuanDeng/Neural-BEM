# LAU-001-R1 — corrected qualification; practical compression remains unproved

**Execution: COMPLETE. Verdict: STRUCTURE_ONLY, with narrower conclusions.**
User authorized repair and testing on 2026-09-17 after the independent outsider
review. Owner: Codex; no second independent implementation reviewer assigned.
[Contract](../../../../docs/iterations/laurent/iteration_02/03_plan.md).
Original LAU-001 artifacts are unchanged.

## Decision

The ellipse preserves all numerical quantities with a 30% remainder budget.
Neither star fixture does so at a budget of 30% or 50% of its smaller qualified
matrix, including when that same absolute budget is moved to a larger trace
space. The refined 30% pass is real but uses more retained entries than the
entire smaller remainder. It supports approximation quality, not practical
compression or a sparse implementation decision.

The asymmetric control also narrows the original derivative-awareness claim:
forward-only selection no longer destroys derivatives by order-one errors once
this star's symmetry is broken. Both selectors still fail the full-system
residual at the smaller budgets. Do not generalize a large symmetry-induced
derivative gap to generic inverse iterates.

No solver default, sparse assembler, or optimizer changed. Imported solver
sources were read-only. This revision addresses validation of the tested rule;
it does not close the broader Laurent/Fourier research direction.

## Repairs and validation

- Nodal Kress at N=256/384 supplies independent fields and reciprocal data
  derivatives in the same real Laurent coordinate directions. Centered nodal
  reassembly checks the held-out c5 direction per fixture at three h values
  and both node counts at the smallest h. Native A, b, C and frozen objectives
  are checked in all six directions at ka=2 per fixture.
- The derivative reference is no longer the native derivative being tested.
  Compression-only and total-to-Kress errors occupy separate columns.
- `passes_all` includes independent reference qualification, receiver error,
  flux-scaled residual, training and held-out physical data derivatives, and
  objective derivatives with the declared cancellation allowance.
- Residuals use the fixed oracle's `(u, J*d_n u)` coordinates. This is a
  correction to the old metric; original physical-coordinate residuals are not
  silently compared as if they were the same norm.
- K and B are varied separately; a labelled `both` arm bridges to the old
  confounded comparison. Absolute entry budgets stay fixed when K changes.
- The asymmetric anchor, held-out transmitter coordinates, and the planned
  star offsets all run. Mask selection never sees held-out observations.
- Continuous Hadamard derivatives on compressed traces are a separate
  diagnostic, never substituted for the discrete tangent acceptance gate.
- Work is reserved before assemblies, factorizations and RHS batches. Output
  folders cannot be reused; source drift invalidates a run. Comparison IDs link
  each arm to six detailed directional measurements and a saved mask.

**66/66 package and imported-library tests pass.** At the smallest declared
finite-difference step, **128/128 campaign checks pass**. The read-back audit
checks **528 comparisons, 3,168 derivative records, 283 distinct masks and 73
source files**, with no source drift. Of the 528 comparisons, 178 satisfy all
numerical gates; the other rows retain intentionally poor controls and failed
candidates. This count is not an inverse success rate. See [audit.json](audit.json).

## Independent qualification

All rows below use B=96, 28 Bessel terms and the original physical frequencies.
Every direction must qualify before masks run. Relative errors are worst-case
over the six directions where applicable.

| Case | K | Native field error | Native flux residual | Native physical derivative error | Kress derivative N-refinement |
|---|---:|---:|---:|---:|---:|
| circle@ka2 | 16 | 4.80e-14 | 1.16e-11 | 7.16e-14 | 3.22e-15 |
| circle@ka5 | 24 | 7.51e-11 | 9.54e-12 | 6.63e-11 | 5.89e-14 |
| ellipse@ka2 | 16 | 9.31e-15 | 4.42e-13 | 6.72e-15 | 1.52e-15 |
| ellipse@ka5 | 24 | 6.19e-12 | 1.07e-12 | 1.39e-11 | 9.53e-14 |
| star@ka2 | 40 | 1.44e-14 | 2.61e-08 | 7.84e-15 | 6.85e-15 |
| star@ka5 | 48 | 4.30e-12 | 4.13e-08 | 6.93e-12 | 4.81e-14 |
| asymmetric_star@ka2 | 40 | 9.34e-15 | 2.78e-08 | 1.13e-14 | 7.73e-15 |
| asymmetric_star@ka5 | 48 | 5.27e-12 | 4.24e-08 | 9.19e-12 | 5.16e-14 |

The four ka=10 inputs fail native control qualification at the declared
28/48-term and K ladders. They remain **UNQUALIFIED**, separately from
compression failures. This bounds the tested implementation, not Fourier or
Laurent representations in general. [reference_convergence.csv](reference_convergence.csv).

## Retained count is the relevant comparison

The following verified-split, derivative-aware rows compare the doubled-K case
at B=96. `True` means all numerical gates, including physical and objective
derivatives. The protected part is additional to the remainder counts.

| Case | Entire smaller remainder | Fixed original 30% count: pass | Refined 30% count: pass | Refined count / smaller dense |
|---|---:|---:|---:|---:|
| star@ka2 | 26,244 | 7,872: False | 31,104: True | 1.185 |
| star@ka5 | 37,636 | 11,292: False | 44,700: True | 1.188 |
| asymmetric_star@ka2 | 26,244 | 7,872: False | 31,104: True | 1.185 |
| asymmetric_star@ka5 | 37,636 | 11,292: False | 44,700: True | 1.188 |

The fixed 50% budgets also fail for both star fixtures at both frequencies.
Doubling B alone does not rescue them. The ellipse passes the fixed original
30% count at both frequencies, including trace refinement.
[compression.csv](compression.csv), [refinement.csv](refinement.csv).

## Symmetry control

At 30% retention and the original qualified K:

| Case | FORWARD physical derivative error | DERIVATIVE_AWARE physical derivative error | FORWARD flux residual | DERIVATIVE_AWARE flux residual |
|---|---:|---:|---:|---:|
| star@ka2 | 2.48e+00 | 1.04e-05 | 2.61e-08 | 4.29e-05 |
| asymmetric_star@ka2 | 6.43e-06 | 5.01e-06 | 1.30e-05 | 4.13e-05 |
| star@ka5 | 7.56e+00 | 2.65e-05 | 4.13e-08 | 1.21e-04 |
| asymmetric_star@ka5 | 4.88e-05 | 1.43e-05 | 3.92e-05 | 1.03e-04 |

On the asymmetric anchor both data derivative errors already satisfy 1e-3;
the residual is the blocker. The remaining derivative advantage is much smaller
than the original symmetric examples. This is one asymmetric fixture, not a
statistical generalization study.

## Held-out geometry, acquisition, and derivative interpretation

The star's refined verified-split derivative-aware masks at 30% and 50% pass
on new transmitter coordinates. At ka=5 they also pass both frozen-mask offsets
(0.005 and 0.01 times the anchor equivalent radius). The corresponding smaller
masks still fail. These results validate the larger masks locally but do not
remove their count disadvantage. [heldout.csv](heldout.csv).

The circle remains a failure of four-direction training for the two unseen
coordinates. At ka=2 and 30%, its discrete masked derivative has relative
physical error 1.46 while its continuous Hadamard evaluation on compressed
traces has error 7.65e-15. That difference is why the continuous expression
cannot be used to declare the derivative of the actual masked model correct.

## Coefficient window

B=64 with 28 terms passes every numerical gate at the original qualified K on
all eight ka=2/5 cases. At ka=2, 20 terms also pass on all four fixtures. At ka=5,
20 terms fail the joint gates. The old runner forced B>=2K, which prevented
several smaller-window comparisons; the matrix lookup requires B>=K, and the
new smaller windows are independently checked rather than assumed accurate.

This is a qualified approximation result for these cases. It is **not** a speed
claim or a universal coefficient-budget rule. The legacy `assembly_seconds`
column for windows measures complete NativeCase construction (acquisition,
assembly, primal solve and split); it is not isolated assembly cost. No matched
nodal timing campaign or repeated timing protocol was run.

## Scope and reproducibility

Materials, one-component topology, six directions, paired 24-source/receiver
measurements, and fixed-frequency scope remain as recorded in [config.json](config.json).
The ka=5 rows do not claim a fresh native finite-difference sweep: those checks
are explicitly scoped to ka=2, while independent Kress derivative refinement
and physical derivative comparison run at both frequencies.

The projected-Nystrom operator has not received its own compression sweep.
Thresholded support boxes are empirical finite-window diagnostics, not a proof
of a useful analytic sparsity law. No general mask-discovery or sparse-cost
mechanism is established. A later cost study should compare the qualified
coefficient-window option against the current nodal reciprocal/compiled path;
beating an unnecessarily expensive native setting would be insufficient.

Resources: 368 physical assemblies, 1136 factorizations, 2304 RHS batches / 55,296 columns; 128.9 seconds and 0.89 GiB peak RSS.
All declared ceilings held. Timings came from a shared developer host.
Commands are in [commands.md](commands.md); source hashes and actual thread
environment are in [manifest.json](manifest.json).
