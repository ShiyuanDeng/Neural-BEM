# Outsider proposal: model-free lifting check and early-stage basin census

2026-10-03. Author: Claude (outsider review). Evidence below is from a sandbox run of the
committed check `experiments/cleaned_interface/fm003_lift.py` (CPU, 384 nodes, 106 s); FM-003
reruns it in the repository. Independent reviewer: unassigned.

## Why this question

FM-001 showed that full 24 × 24 data with the unchanged damped CI-001 policy recover the
contrast-13.3 C, and that paired and full runs separate at stage 2 (distance to truth after
stage 2: 19.3 mm paired, 3.49 mm full). That leaves two explanations for the paired failure:

1. **Information:** the paired data do not contain what stage 2 needs.
2. **Search:** the information is there, but local continuation from the fitted circle lands in
   the wrong basin.

The lifting check tests whether the missing full-matrix data can be recovered from paired data
using physics alone. The census tests explanation 2 directly.

## Lifting check: what goes in, what comes out

**In:** the 24 paired values at one frequency. **Out:** an estimate of all 24 × 24 values.
No shape model is used, only two laws that hold for every lossless object:

    X = c · P_R T P_Sᵀ,   S = I + 2T,   Q = S P D
    reciprocity        ⇔  Q symmetric
    lossless object    ⇔  Q unitary

X is the data matrix (receiver × source); c = strength · i/4; P_R, P_S hold Hankel functions
at the receivers and sources; T maps incoming wave order n to outgoing order m; P reverses the
order n → −n; D = diag((−1)ⁿ). A symmetric unitary Q equals exp(iH) with H real symmetric (its
real and imaginary parts commute, so one real orthogonal matrix diagonalises both). Keeping
orders |n| ≤ N leaves (2N+1)(2N+2)/2 real unknowns against 48 real paired values.

**Checks (all pass):** centred disk, |S_nn| − 1 ≤ 2.4e-15 and off-diagonal T ≤ 1.8e-15 of the
diagonal. For the true C, full-data fit residual 1e-10 / 4e-9 / 1e-7, unitarity error
1.5e-14 / 7.6e-14 / 4.6e-12 and symmetry error 5.7e-15 / 7.3e-14 / 4.2e-12 at
0.25 / 0.5 / 0.75 GHz. Doubling the nodes changes the data by ≤ 4.4e-15.

**Lifting results** (24 starts; "ambiguity" is the largest relative difference between lifted
matrices among the starts that reach the best paired residual, a truth-free measure):

| Frequency | N | Truncation floor (true T cut at N) | Best paired residual | Lift error | Ambiguity | Linear lift without the laws |
|---|---|---|---|---|---|---|
| 0.25 GHz | 2 | 0.34% | 0.14% | **0.61%** | 2.5e-8 | 95% |
| 0.25 GHz | 3 | 0.02% | 3e-6 | 102% | 3.2 | 98% |
| 0.5 GHz | 2 | 22% | 7.0% | 132% | 1.0e-7 | 98% |
| 0.5 GHz | 3 | 2.5% | 1.4% | 160% | 2.3 | 96% |
| 0.5 GHz | 4 | 0.09% | 7e-5 | 164% | 3.1 | 97% |
| 0.75 GHz | 2 | 37% | 30% | 72% | 1.8e-7 | 98% |
| 0.75 GHz | 3 | 7.1% | 5.2% | 89% | 1.3 | 96% |
| 0.75 GHz | 4 | 5.5% | 1.3% | 100% | 2.2 | 97% |

A truth-free rule separates the cases: a lift is usable when the best fit is unique
(ambiguity < 1e-3) **and** fits the paired data (residual < 1e-2). Only 0.25 GHz, N = 2 passes.
At 0.5 and 0.75 GHz every order either cannot represent the field or admits a family of
different scattering matrices that fit the paired data equally well.

**Reading.** The two laws add real information (0.25 GHz: 0.6% against 95% without them), but
not at the frequencies where the paired C goes wrong. There, paired data can be completed only
through a shape model. For noiseless data, the shape model still decides: the truth (Fourier
band 10) is representable at stage 2 (storage band 12) and has stage-2 loss ≈ 0, while the
CI-001 stage-2 endpoint has loss 0.0046. So the failure is plausibly a search failure.

## Proposed claim and test

*At high contrast with paired data, frequency continuation fails because the early stages are
solved locally, not because information is missing. The early stages are small (stage 2 has
11 shape parameters and 2 frequencies), so they can be searched globally at a measurable cost.*

The census in the [FM-003 plan](../03_plan.md) measures the fraction p of stage-2 starts that
reach the zero-loss basin. Because the data are noiseless, that basin is identified without
the truth (loss < 1e-6); the truth is used only afterwards to confirm it. If p > 0, the expected
cost of a global stage 2 is about 1/p stage fits, and continuing from the selected endpoint
tests recovery. Full-data and contrast-4 censuses give the controls.

What would weaken the claim: p = 0 in 512 starts (95% upper bound 0.58%), a zero-loss endpoint
far from the truth (non-uniqueness at stage 2), or no recovery after continuing from it.

Other ideas considered and not proposed now: Klibanov-type convexification adapted to shapes
(weeks of work), and following solution paths in complex frequency through turning points
(needs a complexified boundary solver).
