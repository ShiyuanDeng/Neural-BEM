# EW-001 — Ewald circle control at the unregistered split, and a cost gate

Prepared 2026-10-05 by Claude, following ON-003 and the
[outside review](../../cleaned_interfaces/iteration_31/02_claude_review.md)
(finding R5). User request: "draft plans for all three tracks".

**Status: APPROVED, IN PROGRESS.** User instruction: "go on EW-001"
(2026-10-05). Approval covers Q1 and Q2 below and the closeout.
Execution uses the existing `feature/shape-frequency-continuation` checkout,
where this plan was registered; no branch or worktree is created.
Start: 2026-10-05 09:31 UTC; two-hour deadline: 11:31 UTC.
It does not cover curved states, full fields, derivatives, inverse
integration, a new branch or worktree, or any other experiment.

## Why

ON-003 closed after failing its circle diagonal control. Every registered
split had ξ ≥ k*, on 128 and 256 grids.

- The measured errors follow the spectral-Ewald k-space term exp(−τ q_max²),
  with τ = 1/(4ξ²) and q_max = πN/(2.1 R1).
- On the 256 grid the term is 6.1e-3, 0.26, 0.71 and 0.92 at ξ/k* = 1, 2, 4
  and 8. The worst T errors are 0.043, 0.47, 0.83 and 1.91.
- The unregistered side was predicted to pass on the same grid.

Separately, operator assembly is about 18% of baseline inverse fit time.
Even a free operator therefore caps the inverse at about 1.22x. EW-001 settles
both questions cheaply and then closes the 2D line, unless the evidence
reverses the cost prediction.

## Q1 — circle control at smaller splits

Use ξ/k* ∈ {0.5, 0.4, 0.35}. Apart from ξ, the output folder and the experiment
label, every setting is ON-003's:

- the frozen manifest: k* = 482.46 /m and R0 = 0.16740 m;
- the start circle and the 12 contrast/frequency/catalog configurations;
- trace modes −128..128 with cutoffs 64 and 128;
- grids 128 and 256, period L = 2.1 R1, R1 = R0 + 8√τ;
- radial orders 256/512 and near quadrature 2048/4096;
- the independent flat-heat and near checks, and the analytic circle reference;
- the gate: normalized diagonal error ≤ 1e-7 for V, K, K′ and T.

Registered predictions for the 256 grid:

| ξ/k* | τ q_max² | exp(−τ q_max²) | Near/far cancellation exp(τk*²) | Predicted outcome |
|---:|---:|---:|---:|---|
| 0.5 | 18.6 | 8.2e-9 | 2.7 | Marginal. T ≈ 6e-8 if the ratio of about 7 measured at ξ = 1 holds. |
| 0.4 | 27.8 | 8.3e-13 | 4.8 | Pass, unless near-part quadrature now dominates |
| 0.35 | 35.2 | 5.1e-16 | 7.7 | Pass, unless near-part quadrature or cancellation dominates |

The 128 grid is predicted to fail at every split, because its tail stays large.
A pass at ξ/k* = 0.4 would correct ON-003's record: the circle failure came
from the registered range, not from the matched far-kernel construction.

**Reproduction check (required first).** The new driver must reproduce ON-003's
stored ξ = 1 rows. Require the maximum absolute difference in normalized
diagonal error to be ≤ 1e-12, otherwise stop as `QUALIFICATION_INCOMPLETE`.

## Q2 — cost gate (measured lower bound; no curved maps built)

1. **Current cost.** Time the maintained modal Müller assembly per frequency
   at K_trace 128/160. Use the saved PC-001 kite endpoint, 19 real frequencies,
   both media, and one cold plus three warm repeats. Cross-check against the
   ON-001 receipts' assembly seconds per assembly.
2. **Ewald contraction cost.**
   - From the ON-003 derivation, the far blocks need five dense contractions
     per medium per frequency: A^H D A, A^H D C, C^H D A and N_j^H D N_j for
     j = 1, 2.
   - Time one such contraction on the RTX 5090 for N_grid = 256² and
     N_trace = 257 (also 129), in complex128, with one cold and three warm
     repeats. complex64 is recorded only as context; it cannot meet 1e-7.
   - Projected far assembly for one complete 19-frequency, two-media service
     = 190 × contraction time. This is a **lower bound**: it excludes map
     construction, near corrections and transfers.
3. Prediction: the projected far assembly alone is ≥ 5x slower than the
   measured current assembly. A rough estimate is ≥ 1.5 s against about 0.25 s
   of thread time per 19-frequency service.

## Decision and closeout

| Q1 | Q2 | Terminal status | Next |
|---|---|---|---|
| Pass at some ξ < k* | Ewald lower bound < 0.5x current assembly | `CIRCLE_QUALIFIED_AND_COST_PLAUSIBLE` | Propose, not run, a curved-state forward study under a new ID |
| Pass | Lower bound ≥ 0.5x current | `CIRCLE_QUALIFIED_BUT_UNECONOMIC_2D` | Close the 2D Ewald line; correct the record |
| Fail | Any | `CIRCLE_FAILS_AT_UNREGISTERED_SPLIT` | Report the dominant error source (far tail, near quadrature or cancellation); close |

The ON-003 report stays unchanged. The CI-SPD README gets a one-line pointer
to EW-001's corrected record. No result here authorizes inverse integration or
a 3D rewrite.

## Budget

Two hours overall: about 20 s of CPU per split for Q1, a few minutes of GPU for
Q2, and the rest for implementation, the reproduction check and reporting. Use
the compute, source and Git locks.

## Implementation map

| Area | Location |
|---|---|
| Driver | New `experiments/benchmark/ew001.py`. It reuses `solvers/bem_inverse/on003_ewald.py` and `on003_circle_reference.py` unchanged. It may copy `on003.run`'s control logic, with only ξ, the output root and the label changed. `on003.py` and the ON-003 evidence are never edited. |
| Evidence | `results/validation/cleaned_interfaces/EW-001/`: a hash-verified copy of the ON-003 manifest and reference archive, per-split receipts and arrays, the cost measurements, `summary.json` |
| Report | `docs/iterations/CI-SPD/iteration_03/05_results.md` |

Reference: Lindbo and Tornberg, J. Comput. Phys. 230(24), 8744, 2011, for the
spectral-Ewald k-space truncation term.
