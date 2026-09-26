# SC-042 — cleanup versus persistent state restriction

2026-09-26. Owner: Codex. Independent reviewer: unassigned.

**APPROVED:** the user's “go then. dont stop until you hit every wall” accepts
the preceding four-arm comparison and successive evidence-led iterations.
It supersedes the old named-ID approval wording for this work. No new branch
or worktree; existing `feature/shape-frequency-continuation` checkout.

Question: does removing accumulated high-band state content suffice, or does
maintaining a restriction improve subsequent reconstruction at matched work?

Baseline source: b946d57. All six development cases. Star starts from SC-041
M25, kite from SC-041 M22; circle/C/peanut/hook start at their SC-040 indexed
endpoints. Starts are reconstructed from committed JSON, never local shots.

Four arms: `none` (K192); `once` (initial K64 truncation then K192);
`boundary` (K64 truncation at every stage start then K192); `cap` (initial
K64 truncation and K64 throughout). Truncation acts on the stored centred
arclength Fourier state, without another reparametrization. Save its full
before/after curves and objective change. It is an intentional intervention,
not an accepted descent step. Geometry and numerical validity remain required.

All arms of a case use identical M ladders: star 25/31/37, kite 22/28/34,
others 19/25/31. Each stage gets 608 work units, 22 iterations and a 3600 s
emergency wall ceiling; each path gets at most 1824 inverse work units.
Quotas, not accepted-step counts, define the matched allowance. No transfer
of unused stage allowance. All 19 existing frequencies and their weights,
objective, ProjectedUpdate, LM settings and acceptance tolerances stay fixed.
`log_model=True` only adds diagnostics. Star/others use 512/1024 nodes; kite
uses 768/1536. No numerical retry within an arm; failed endpoints remain.

The comparison is a suffix-mechanism study, not new-shape generalization or
an end-to-end reconstruction benchmark. Each final state gets an independent
N/2N field, complete-construction Jacobian and directional FD audit (130 units,
900 s). Field tolerances inherited; relative J and FD gates 1e-3, fixed FD
direction seed 42001, step 1e-7 m. Starting baseline losses reproduce within
1e-8 relative or 1e-14 absolute. No failed audit can support promotion.

Maximum 43,776 inverse plus 3,120 audit units; at most six single-thread
numerical workers. Report units and uncontrolled elapsed time separately.
First inspect star/kite, then complete the four shape-preservation controls.
All inputs, code and settings hashed before fitting; accepted states saved
including the last state before a quota interrupts derivative construction.
Truth enters scoring only after a path returns and never selects an iterate.

Compare final and common-observed-work RMS/Hausdorff, loss, curvature radius,
tail energy, accepted steps and numerical failures. For an intervention to be
a candidate across the six cases: geometric-mean RMS ratio <=1, no RMS or
Hausdorff ratio >1.25 (floors 0.01 mm), and no additional numerical failure.
Prefer once over boundary/cap when all RMS/Hausdorff differences are <=5%
under the same floors and failure counts match. Report exact ratios even
when failing these development gates. These are selection criteria, not
statistical confidence intervals or evidence of generalization.

Follow-on decisions under the same user authorization: freeze a narrow
prospective atlas-versus-simple-rule comparison and then a noise experiment
after examining SC-042. New experiments receive their own immutable plans,
fresh bundles and explicit numerical ceilings. Negative results narrow the
method; they do not justify silently changing SC-042 or tuning on truth.
