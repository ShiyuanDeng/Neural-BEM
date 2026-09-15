# TOP-023 — frozen terminal derivative and damping diagnosis

**Approval:** APPROVED under the 2026-09-15 user instruction “cp first. then i
approve you to finish the rest”. **Execution:** NOT STARTED. Owner/reviewer:
Codex `/root`; independent reviewer unassigned, no independent review claimed.

## Question and decision

TOP-022's failed final state has a measured reduced gradient 0.014276 and ends
at the 22-update limit. Does its finite-difference model reproduce, and does the
same LM formula give a more useful validated step with a declared larger
damping? This is a frozen training-model diagnosis, not an inverse restart or a
fresh-recovery experiment. A lower training objective alone is not recovery.

Reconstruct one complete training Jacobian at the saved final state. Qualify
two selected directions at two finite-difference scales and two resolutions.
If those checks pass, compare four damping values using the existing step
formula, coordinate bounds, feasibility and acceptance rules. No changed
optimizer implementation, chart, data, tolerance or shared default.

An alternative merits a separately bounded continuation comparison only if its
first qualified decreasing candidate has at least **2× the baseline production
gain with no more candidate frequency calls**, or it finds such a candidate
when the baseline finds none. All actual gains must pass the existing refined
acceptance and numerical gates. Otherwise reject the damping-change line.
This gate does not release a full suite, adopt a policy or extend TOP-022.

## Frozen inputs and boundaries

Use only TOP-022's prescribed final state, four-frequency training observations,
training prediction columns at 256/512, optimizer/solve configuration, exact
terminal gradient and last trajectory damping. Verify the completed negative
bundle and artifact hashes. Copy only training columns into diagnostic inputs;
truth, scene shapes and development observations do not enter the audit API.
Record this as an archived-terminal diagnostic, never a fresh initialization.

Retain the K9 polar-gauge Cartesian state, 34 orthonormal reduced directions,
0.5/0.75/1/1.25 GHz, equal normalized frequency weights, 256/512 nodes and 8-mm
radius floor. Reuse the eight saved training prediction frequency systems;
no new oracle or evaluation-frequency solve. All candidate states remain
diagnostic records; no candidate updates the frozen base or launches an inverse.

## Measurement and budgets

1. Reconstruct the full 256-node Jacobian at h=1e-4 using the existing normalized
   residual, retraction, feasibility checks and feasible-side quotient. Reserve
   its whole worst-case batch: 34 × 2 × 4 = **272 calls**. An unresolved column
   stops the diagnostic; never substitute zero. Require its gradient to match
   the saved model with rtol 1e-5, atol 1e-8.
2. Select the largest absolute **saved reduced training-gradient** coordinate
   (first index on ties) and the last basis row, using the first row if that
   duplicates the maximum. Probe h=1e-4 and 5e-5 at both resolutions, reusing
   the already computed 256/h=1e-4 probes: at most **48 extra calls**. Repeat
   the base at 256: **4 calls**. Use the existing TOP-018 0.25 relative scale
   stability and signal >=5× numerical-floor tests. State physical displacement
   per unit coefficient. These checks qualify the selected directions, not
   every Jacobian column or an entire nonlinear basin.
3. If model replay and selected-direction checks pass, form the unchanged LM
   proposal with `D=max(diag(J.T@J),1)` and the existing reduced-coordinate
   clipping at each of four damping values: **3.138105960899997e-15** (the next
   in-loop value from TOP-022), **1e-6**, **1e-4**, **1e-2**. Save raw/clipped
   directions, active bounds, singular values, predicted gains and physical
   step sizes. Full rank does not establish good conditioning.
4. Each damping arm gets at most eight backtracking attempts, scale 2^-j,
   j=0..7. Retain the existing relative-step floor. Reserve a full **8-call**
   two-resolution training batch before each feasible candidate. Apply the
   existing prediction tolerances and cross-resolution gain margin. Stop each
   arm at its first qualified decreasing candidate. Any numerical-resolution
   obstruction is a hard stop, as in TOP-022. No best-of-truth selection.

The worst-case count is 272+48+4+4×8×8 = **580 calls**. Hard ceiling **600
charged frequency calls / 1,200 active seconds**, one numerical worker and BLAS
1. Preserve all failed/refused calls and partial artifacts. No quota extension,
extra damping, restart or inverse continuation is part of this contract.

## File/API map and owner review

Add `experiments/top023/run.py` for source/input freezing and one training-only
audit, plus a saved-array reporter and focused mocked tests. Reuse TOP-022's
hash guards, TOP-018's quotient/derivative qualification, TOP-016's prediction,
normalization/physical-displacement helpers, and TOP-017's physical ledger.
Copy measured experiment dependencies and test files. Save all complex probes,
residuals, Jacobian/basis/scales, gradient identities, four arm records and work.
Replay model algebra, stencils, numerical gates, gains and counters without
physical calls. Results open iteration 16 after an owner closeout.

Accept the bounded diagnosis because the completed direct run has a non-small
measured gradient and slow backtracked progress. Do not infer that damping is
the bottleneck from that observation. Reject a new production optimizer or
box-constrained step solver at this stage: clipping may be inactive, and no
reconstruction benefit from either change has been established. Preserve both
failed fresh protocols and the successful different TOP-018 entry. TOP-021 stays
undispatched, and the full topology roadmap remains open.
