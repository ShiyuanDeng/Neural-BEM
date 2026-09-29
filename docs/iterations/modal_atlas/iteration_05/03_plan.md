# MA-005 plan: extend the final band to the observable frontier

2026-09-29. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
Authority: the user's 2026-09-29 instructions ("go next steps as you see fit,
you have my approval to stop only until genuine good news or hit every
wall"; "go finish your work"). Frozen before any MA-005 attempt ran. The
inverse evidence seen so far: MA-002, MA-003 and MA-004's development D
attempts, and the evaluation-only MA-004 diagnosis. The plumbing smoke test
measured one frontier and ran one tail stage with two LM iterations, and
looked at no geometry error or residual. No production default, branch or
worktree changes.

## Question

MA-004's damped start (D) repairs the contrast-4 C and the contrast-13.3
asymmetric scene, and keeps all 8 earlier recoveries. It misses its gate
(2 of the 4 failures; 3 needed). One near miss has a diagnosed cause:

- The 13.3 star converges exactly like the star at every lower contrast. It
  ends 0.022 mm from the truth (0.018–0.022 mm at the others). Every fixed
  stage stops at its band's stationary point, and the loss falls about
  4–7× per 6 added harmonics (5.0e-3, 2.3e-4, 5.5e-5, 7.6e-6 at
  M = 19/25/31/37).
- On the 13.3 data, curves 0.02 mm from the truth leave a 0.7–1.7% residual.
  That includes the lower-contrast D endpoints, which passed their own
  0.3% criterion. The data are that much more sensitive at 13.3.
- At the star truth and the top four catalog frequencies, the 1% observable
  frontier is 33–34 at contrast 0.5, 47–55 at 4 and 69–84 at 13.3
  ([`diagnosis_frontier_star.json`](../../../../results/validation/modal_atlas/MA-004/diagnosis_frontier_star.json)).
  SC-050's schedule stops at M = 37, a band chosen for contrast 0.5.

At the low prefix frequencies, MA-002/003 found the band should follow the
exterior wavenumber. At the top frequencies the observable band grows with
contrast, and the frozen schedule stops short of it.

> **Does extending the final band to the measured observable frontier
> recover the 13.3 star, without harming any recovery, and does D plus the
> tail beat the frozen policy on untouched scenes?**

## Arm

**DF = D, then a frontier tail.** After D's last stage (fixed M = 37), measure
the 1% frontier F at the current iterate: the highest arclength harmonic
`p ≤ 95` whose paired-Jacobian column norm is at least 1% of the strongest.
It is taken at the highest catalog frequency (2.5 GHz) on 1,024 nodes. This
is MA-001's definition and needs no truth. Charge 2 work units (one solve,
one Jacobian). While the band is below F, append fixed stages
M = 43, 49, …, SC-050's step of 6. Stop at the first M ≥ F, never above
M = 95 (the K = 192 storage limit). Every appended stage copies SC-050's
fixed M = 37 stage: all 19 frequencies, K = 192, 512/1024 nodes, 22 LM
iterations, a quota of 304 units. The same total cap (13,412
fit+localization units) and wall limit (1,800 s) apply. If F ≤ 37, DF is D
exactly.

DF continues from D's saved endpoint and ledger. That equals rerunning D
because D is deterministic, which `replay` checks before anything counts.
A D attempt that did not complete its schedule gets no tail, and DF
inherits its verdict. Recovery, audits and endpoint residuals are MA-004's.

Frozen by the manifest: this plan, the driver
(`experiments/modal_atlas/frontier_tail.py`), MA-004's sealed sources and
inputs, and the 12 D development results that DF starts from.

## Stage 1: development (MA-002 scenes)

DF on the 12 development attempts. Predictions, written before running:

- DF recovers the 13.3 star.
- DF does not recover the 13.3 C. D leaves it 6.4 mm off, in a wrong basin
  from the damped prefix onward; a tail cannot fix that.
- DF keeps all 10 of D's recoveries.
- At contrast 0.5 the frontier is at most 37 at every endpoint, so DF = D.

**Gate G1 (MA-004's, unchanged; releases stage 2):** DF recovers at least 3
of the 4 MA-002 failures and all 8 earlier recoveries.

## Stage 2: transfer (untouched scenes)

MA-004's transfer design, unchanged. The scenes are `opposite_c`,
`shifted_rotated_c`, `new_thin_c` and `noisy_asymmetric` at contrasts 4 and
13.3. Frozen and D run from scratch (MA-004's driver, written under MA-005),
then DF runs on each D, one attempt each. The inputs are MA-004's sealed
transfer inputs. The noisy scene's damped data use an independent 1% draw, as
disclosed in MA-004.

**Gate G2 (the claim):** DF recovers at least 4 of the 8 transfer attempts
and at least 2 more than frozen, with every recovered endpoint passing its
final audit (part of the recovery definition). D's transfer outcomes are
reported alongside, not claimed; MA-004's gate failed.

## Not claimed in advance

A pass would support D plus a frontier tail for this acquisition and these
permittivities. It would not show robustness to unknown permittivity or to
real-data effects. It would not show that the 1% threshold or the step of 6
is optimal. The 13.3 C is not addressed.
