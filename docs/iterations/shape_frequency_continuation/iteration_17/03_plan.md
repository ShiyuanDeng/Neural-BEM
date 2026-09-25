# SC-035 — centred state-band restriction

2026-09-25. Owner: Codex; independent reviewer unassigned. Authorized by the
user's 2026-09-25 autonomous instruction. This is Priority C of the new brief,
separate from the running SC-036 finite-ray comparison. It uses the existing
checkout and no new branches/worktrees.

Question: does an intentional low-band state family improve complete inverse
recovery once the Jacobian differentiates the actual finite construction?
Keep one intervention: K=8/12/16/20 versus K=192 at every stage. The former is
RD-4's `2M+2`, fixed without truth; the detectability-based alternative is not
bundled in. Both use `T_z(a)=z+P_K[A(z+h(a)n)-A(z)]`, existing normal h basis,
same backend and M=3/5/7/9. No curvature or clearance prior is added.

API map: isolated `state_update.py` and driver in the SC-035 result bundle;
`LocalSpace` carries geometry derivative coefficients; `velocities` evaluates
the full trial derivative at physics nodes. Existing `Objective` and
`fit_stage` do all fitting/acceptance. No solver/backend/default changes.
Central geometry differences (1e-7 m) assemble the derivative without field
probes; halve this step in qualification. `T_z(0)=z` exactly. Enlarging K pads
coefficients and does not change the shape. Initial state is the same circle.
Trial validity checks apply both before and after intentional smoothing;
resolution is checked by doubling the geometry grid to relative 1e-5. The
size of intentional smoothing is recorded, not rejected as a numerical error.

Qualification: zero-step identity, K padding invariance, full-construction
field directional derivatives at K=8/12 on noncircle/non-star controls
(relative 1e-3), derivative stability (1e-3), and K=192 agreement with Borges
on a smooth curve. Reject the pilot on failure; do not relax numerical gates.
At least one low-K test must measure a material difference between the old
normal Jacobian and the complete-construction Jacobian. This guards against
an inactive intervention. Qualification cap 200 field/reciprocal units.

Pilot: stage 1, peanut/C/star/kite, low K=8 versus high K=192. 22 iterations,
512/1024 physics nodes, existing weights, limits and acceptance, 600 units and
900 seconds each. Truth is evaluation only. Release full continuation if low
K improves stage-1 RMS by at least 20% on peanut or C without increasing star
or kite RMS by over 25%; retain every failure. This is a development gate,
not a generalization claim.

If released: continue BOTH arms through stages 2–4 then one matched final
release/repeat stage at K=192 on the existing four frequencies, M=9, 22
iterations, quota 1,000. Charge work from the pilot. Per-path total ceiling
3,000 units and 2,700 seconds; eight paths reserve 24,000 units, plus 152
endpoint-evaluation solves. Stop with a budget-limited result on exhaustion.
Save all histories, source/input hashes and commands. Compare pre-release
and post-release errors to expose temporary/final bias and the cost of extra
work. Same-data repeat is present in the high-K control too.

Interpretation: keep a restriction only for recovery/reliability at comparable
cost. Lower curvature alone is insufficient. Even positive results do not
promote an atlas controller or establish generalization on these development
cases. If projection fails, close this specific mechanism before considering
another prior. Conformal inversion remains conditional and out of this pilot.
