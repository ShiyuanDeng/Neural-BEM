# FDE-001 (proposal, side quest): a presence variable for topology events

Drafted 2026-09-16. **Low-expectation side quest.** Not a declared contract on
the topology track, not on its critical path, does not consume `TOP-`
numbering, may be abandoned with only a negative result recorded. Everything
below is literature-backed; the citations are at the end and the borrowed
formulas are re-derived for this problem rather than copied.

---

## 1. Why the current controller is mechanical — the structural reason

`generate_topology_candidates` (`solvers/sdf_inverse/topology_controller.py:403`)
sweeps hardcoded geometric templates: birth from two threshold fractions
`(.65, .35)` of the field minimum, split from straight strips over rotations x
offsets `(-.25, 0, .25)` x widths `(.012, .020, .032)`, merge from straight
tubes at radius factors `(.45, .75, 1.05)`. The topological derivative enters
only as a scalar ranking score.

The templates are a *symptom*. The cause is that the state space has **no
continuous presence variable**. A component either exists — and costs a full
boundary block — or it does not. With no continuous path between "absent" and
"present", every topology change must be a discrete jump; a discrete jump
cannot be differentiated, so it can only be *enumerated*; enumeration in a
continuum forces a template grid. Every heuristic in the file follows from
that one missing degree of freedom.

This is exactly the situation 3D Gaussian Splatting was in, and exactly what
its literature spent 2024 fixing.

## 2. What 3DGS actually does

Kerbl et al.'s original Adaptive Density Control (clone if the view-space
positional gradient exceeds a threshold and the Gaussian is small, split if it
is large, prune if opacity falls below a threshold, reset opacity
periodically) is a template grid of the same kind as ours. Three follow-ups
dismantle it, and each one names a failure mode we can check for directly.

**(a) Gradient collision — AbsGS (Ye et al., ACM MM 2024).** The ADC
densification criterion is the *magnitude of the summed* per-pixel
view-space gradient. For a large primitive covering many pixels, sub-gradients
of opposing sign cancel, the sum never crosses the threshold, and the
primitive is never split — precisely in the over-reconstructed regions that
most need splitting. Their fix is the *homodirectional* gradient: sum absolute
values of the per-pixel sub-gradients.

**(b) Opacity bias on clone — Rota Bulo et al. (ECCV 2024).** ADC keeps the
parent's opacity on both children, so a cloned pair composites to
`1-(1-a)^2 != 1-a` and the densified primitive silently gains influence. Their
correction solves `(1-a) = (1-ã)^2`, giving `ã = 1 - sqrt(1-a)`: choose the
child parameter so the **observable is invariant** across the event. They also
replace the gradient criterion with a per-pixel error (SSIM-type) score and
add a global budget on primitive count.

**(c) Densification as sampling — Kheradmand et al. (NeurIPS 2024),
"3D Gaussian Splatting as MCMC".** The whole heuristic set is replaced by:

- an SGLD update, Eq. 7: `g <- g - lr * grad E[L] + lr * sigma(-k(o-t)) * Sigma eta`,
  `eta ~ N(0,I)`, `k=100`, `t=1-0.005` — noise **shaped by the primitive's own
  covariance** and gated on low opacity, so only near-dead primitives diffuse;
- no birth/death at all, but a **relocation** of dead primitives onto live
  ones chosen by multinomial sampling with `P(target = i) ∝ o_i`;
- a **state-preserving** relocation, Eq. 9: moving `N-1` dead Gaussians onto
  live Gaussian `N` sets `o^new = 1 - (1-o^old)^(1/N)` and rescales `Sigma`
  by an explicit factor so the *rendered output is unchanged* by the move;
- L1 sparsity on opacity and on the square roots of the covariance
  eigenvalues, Eq. 10, so unused primitives are pushed to death by the
  objective rather than by a threshold.

The unifying principle across all three: **a topology move should not change
the observable.** Then the move is free, and whether it was a good move is
decided afterwards by the gradient in the enlarged space — not by a jump in
the loss, which is what makes enumeration necessary.

## 3. The dictionary — and where it breaks

| 3DGS | This solver |
|---|---|
| N Gaussians `(mu, Sigma, o)` | N explicit Fourier components `(centre, radius, modes)` |
| rendered image vs photographs | BIE forward solve vs `ComplexScatteredData` |
| per-pixel photometric error | normalized complex residual |
| view-space positional gradient | topological derivative field `w.addition` / `w.removal` |
| clone / split / prune ADC | template birth / split / merge / death |
| **opacity `o`** | **nothing** |

The missing row is the whole problem. But this solver is a *transmission*
problem — `evaluate_current_domain_topological_derivative`
(`radial_topology.py:382`) is built on the squared-wavenumber contrast,
`D_minus = Re[(k_e^2 - k_i^2) sum(conj(residual) u_i u_i_recip)]` — so a
natural continuous presence variable already exists in the physics:

> **opacity := contrast factor.** Give component `c` a factor `tau_c ∈ (0,1]`
> multiplying its contrast `(k_e^2 - k_i^2)`. At `tau = 1` it is a full
> scatterer; as `tau -> 0` it becomes invisible while its geometry stays
> perfectly well-posed.

This is what shrinking the radius cannot do: radius `-> 0` collides with
`component_radius_floor` and with the small-scatterer limit that the BIE
discretisation resolves worst. `tau` degrades the *observable* without
degrading the *geometry*.

**Where the analogy honestly breaks.** A transparent Gaussian is nearly free
to render; a low-contrast inclusion still costs a full boundary block. So
`tau` buys *smoothness*, not *cheapness*, and 3DGS's budget arguments do not
transfer as stated. The ambitious repair is a two-tier representation —
a probationary component living in the **small-inclusion asymptotic regime**
as a point scatterer with a polarization tensor (Ammari–Kang; Ammari–Volkov),
which costs a rank-one far-field correction rather than a boundary block, and
which *graduates* to a meshed component when `tau |B|` crosses a threshold.
That tier is also exactly where the topological derivative is already exact:
the TD **is** the leading term of that same expansion (Sokolowski–Zochowski;
Novotny–Sokolowski). Flagged as the ambitious version; not required for the
first test.

## 4. Four borrowed mechanisms, one per intervention point

The topology track names four intervention points. Each gets one borrowed
mechanism with a classical counterpart, so nothing rests on the 3DGS analogy
alone.

**M1 — candidate scoring: stop summing a sign-oscillating field.**
Lines 527 and 556 score a candidate as `np.sum(w.removal[known])` and
`np.sum(w.addition[known])` and require `score < 0`. The TD here is
`Re[...]` of a product of oscillating total fields summed over frequencies:
its sign flips on the wavelength scale *by construction*. Summing it over a
corridor several wavelengths long cancels, and the larger the component, the
worse the cancellation. **This is AbsGS's gradient collision, in our code, at
two specific lines** — and it predicts precisely the observed symptom that
large components fail to split (TOP-024's two-star blocker). Sign carries
meaning here, so the AbsGS absolute-value fix is wrong; the correct analogue
is to score by the **negative part**, `integral of min(g,0)`, or by the
negative-part mass relative to the region measure, which is the quantity the
asymptotic expansion actually says predicts improvement.
*Cost: zero new solves. Re-scoring existing candidates is arithmetic.*

**M2 — event construction: state-preserving split and merge.**
Today a split seeds children with `seed_factor * sqrt(area/pi)` for
`seed_factor` from a tuned list — the unprincipled analogue of the clone
opacity bias. The principled version derives the child parameters from
invariance, as Rota Bulo et al. do. To leading order the scattered field
contribution of an inclusion is linear in `tau |B|` (contrast x volume), so a
split into children `i` that preserves the observable requires

> `sum_i tau_i |B_i| = tau |B|` (and, to next order, matching first moments).

Note this is **linear**, not 3DGS's N-th root — alpha compositing is
multiplicative, scattering is linear in the polarization to leading order. The
correct formula for our problem is therefore a different one, derived from our
own asymptotics. That is the point: borrow the *principle* (invariance), not
the formula. A state-preserving split does not jump the loss, so acceptance
stops being a gamble on a jump and becomes a test on the gradient afterwards.

**M3 — budget allocation: relocate dead components instead of killing them.**
3DGS-MCMC never births or kills; it *relocates* dead samples onto live ones
with `P ∝ o_i`. Our analogue: a component whose `tau` has collapsed is
relocated to the most negative basin of `w.addition`, sampled with probability
proportional to the basin's negative-part mass, and re-seeded state-preserving
per M2. This collapses two expensive template classes (death, birth) into one
cheap move and keeps the component count fixed, which is exactly the "easy
control over the number of Gaussians" that paper reports.

**M4 — triggering and acceptance: use the two classical criteria.**
*Trigger:* Amstutz & Andra (JCP 2006) give a sufficient condition for local
optimality under topological perturbation, measured by the angle `theta` in
L^2 between the level-set function and the topological gradient field. `theta`
is a single number in `[0, 90] degrees`, computable from fields we already
have, and it answers exactly the question "is a topology event worth proposing
at all". Fire when shape optimization has converged but `theta` is still
large. *Acceptance:* Green's reversible-jump MCMC (1995), with the
split/merge move pair of Richardson & Green (1997), gives the rigorous
acceptance ratio for a dimension-changing move, including the Jacobian of the
dimension-matching map. Its deterministic limit — accept iff the ratio exceeds
one — is a principled replacement for "accept if the loss went down", and the
Jacobian term is precisely the dimension penalty that should stop
over-splitting. This also reframes M2: a state-preserving split *is* a
dimension-matching bijection.

**Geometry, once decisions are principled.** With the above in place the
remaining template-ness is the *shape* of a proposal, where the earlier
plan still applies: split = weighted min-cut on the pixel graph with edge
costs from `removal` (or Fiedler bisection), merge = minimum-cost geodesic
through `addition` dilated to where it stays negative, birth = watershed
basins of the negative `addition` field. This is now the second half of the
work, not the headline.

## 5. Predictions, cheapest first

- **P0 (zero new solves).** On saved pre-event workspaces, the signed sum at
  lines 527/556 is materially cancelled: for at least one rejected corridor,
  `|sum(g)| / sum|g|` over the cut region is below 0.2 while the negative-part
  mass is large. Prediction: candidates that the negative-part score would
  have admitted were rejected by the signed sum, and the discarded set is
  larger for larger components.
- **P1 (tens of solves).** Re-scoring by negative part changes which candidate
  wins at least one event, and the new winner's objective is lower.
- **P2 (tens of solves).** A state-preserving split (M2) changes the objective
  by less than a template split does at the same event — the invariance holds
  numerically.
- **P3 (free).** `theta` (M4) is computable and is large at the events where
  the controller failed to act, small where it correctly did nothing.
- **P5 (runtime).** Every arm resolves `jacobian_selection` to `analytic`, and
  the measured solve count for a post-event gradient matches
  `jacobian_work_bound` rather than `2 * directions`. If M2's acceptance test
  costs more than one analytic Jacobian per candidate, the mechanism is not
  affordable and section 6a's argument fails.
- **P4 (regression).** With every new path behind a config flag defaulting
  OFF, existing pytest and recorded results are bit-identical.

## 6a. Execution: use the fast analytic runtime, never a new FD probe

SPD-002 (2026-09-16) promoted the **fast analytic CPU profile to the default**;
complete death and split pipelines measure 1.86x/1.89x faster and both still
recover. `solvers/sdf_inverse/runtime.py` is the entry point:

- `current_runtime()` defaults to `PROFILES['fast']` = analytic Jacobian
  (`jacobian='auto'`) with `real_bessel` kernels. `reference` is FD plus
  reference kernels and exists only for validation.
- Select explicitly with the `inverse_runtime('fast')` context manager, the
  `SDF_INVERSE_RUNTIME` environment variable (inherited by spawned workers), or
  `add_runtime_argument` / `configure_runtime_argument` on a script's parser.
- Account work with `jacobian_work_bound(state, directions)`: FD costs
  `2 * directions`, analytic costs `1 + directions * 2` under the current
  `fd_compatible` constraint policy. Do not hand-count probes.

**The trap.** `jacobian_selection` resolves `'auto'` to `'analytic'` *only if
every component is a `CartesianFourierCurveState`*, and silently returns
`'fd'` otherwise. So every measurement here runs with
`TopologyControllerConfig(chart='cartesian')`, and each results row records the
resolved mode. A radial-chart run will quietly cost double and look like a
null result. Assert the resolved selection rather than assuming it.

**Why this makes the plan affordable rather than merely faster.** The speed-up
track's cost profile found that **90.7%-95.1% of all forward solves in
production topology runs are FD Jacobian probes**. That single fact explains
the controller's design: post-event gradients were unaffordable, so the only
usable signal was the *jump* in the loss between enumerated candidates — and
comparing jumps is what forces enumeration in the first place.

Section 4's M2 inverts that. A state-preserving split does not change the
objective, so a loss jump carries no information about it by construction; the
event is judged by the **gradient in the enlarged space afterwards**. Under FD
that judgement costs `2 * directions` solves per candidate and is hopeless.
With the coupled analytic shape Jacobian from BIE-004
(`solvers/gpr_bem_kress/coupled_shape_derivative.py`, qualified at 1.4e-7
relative error, 1.87x per full Jacobian) it is one Jacobian. **The mechanism
this proposal wants became affordable on the day the analytic default landed.**
That is the strongest argument for trying it now, and it is also a falsifiable
claim: see P5.

This side quest makes **no speed-up claim** and does not enter that track's
scope; it only consumes the default. Any timing recorded here is incidental and
declares its machine load, per that track's rule.

## 6. Risks and where this is likely wrong

- The contrast factor `tau` may not be exposed cleanly through the BIE
  assembly; if the contrast is baked into kernel construction, M2/M3 need
  plumbing that is out of scope for a side quest. **Check this first** — it
  gates M2, M3 and M4-acceptance, but *not* P0/P1, which is why P0 leads.
- The negative-part score is not itself a rigorous predictor of objective
  decrease; it is a better-conditioned surrogate. Only P1 tests whether it
  helps, and P1 may simply fail.
- `theta` assumes a level-set representation; our geometry is explicit
  Fourier, so the L^2 inner product must be taken against an indicator field
  built on the workspace grid. That is a defensible discretisation, not the
  theorem's exact setting.
- Min-cut returns ragged pixel boundaries; `fit_mask_component` must be
  checked on a jagged mask and the `min_pixels` guard retained.
- 3DGS optimizes millions of cheap primitives with stochastic minibatches of
  views; we optimize tens of expensive components against a fixed dataset.
  Anything in that literature that relies on sampling many views cheaply
  (including SGLD itself) may simply not transfer. SGLD is listed last for
  that reason.

## 7. Morning deliverable — numbers, not prose

`iteration_01/01_results.md` must lead with these tables filled in. Report
only measured cells; mark anything else unmeasured. Never estimate a number.

**P0 cancellation diagnostic** (one row per scored candidate region, no solves):

| scene | event | kind | region | sum(g) | sum(abs g) | ratio | negative-part mass | admitted by signed sum? | admitted by negative part? |
|---|---|---|---|---|---|---|---|---|---|

**Per event compared:**

| scene | event | kind | N template cands | N field/rescored cands | best template objective | best new objective | change % |
|---|---|---|---|---|---|---|---|

**Summary:**

| Quantity | Value |
|---|---|
| Workspaces replayed | |
| Candidate regions rescored | |
| P0 — regions with cancellation ratio < 0.2 | n / N |
| P0 — rejected-by-signed-sum but admitted-by-negative-part | n |
| P0 — correlation of cancellation ratio with component size | r |
| P1 — events where the new winner has lower objective | n / N |
| P1 — best single improvement | % |
| P2 — objective jump, state-preserving vs template split | x vs y |
| P3 — theta at failed events vs correct no-ops | deg vs deg |
| New BIE solves spent | |
| Wall time | s |
| Runtime profile / resolved jacobian mode | fast / analytic \| fd |
| P5 — solve count per post-event gradient, analytic vs 2*directions | x vs y |
| pytest with flags OFF | n passed / n failed |

If P0 fails, that is the headline and the side quest is probably closed: say
so in the first line with the number.

## 8. Bibliography

**Gaussian splatting density control**
- Kerbl et al., *3D Gaussian Splatting for Real-Time Radiance Field Rendering*, SIGGRAPH 2023 — the original ADC heuristics.
- Kheradmand et al., *3D Gaussian Splatting as Markov Chain Monte Carlo*, NeurIPS 2024. https://arxiv.org/abs/2404.09591 — SGLD Eq. 7-8, state-preserving relocation Eq. 9, sparsity Eq. 10.
- Rota Bulo, Porzi, Kontschieder, *Revising Densification in Gaussian Splatting*, ECCV 2024. https://arxiv.org/abs/2404.06109 — error-based criterion, opacity correction `1 - sqrt(1-a)`, primitive budget.
- Ye, Li et al., *AbsGS: Recovering Fine Details for 3D Gaussian Splatting*, ACM MM 2024. https://arxiv.org/abs/2404.10484 — gradient collision, homodirectional gradient.

**Topological derivative and topology optimization**
- Sokolowski & Zochowski, *On the topological derivative in shape optimization*, SIAM J. Control Optim. 1999.
- Novotny & Sokolowski, *Topological Derivatives in Shape Optimization*, Springer 2013.
- Amstutz & Andra, *A new algorithm for topology optimization using a level-set method*, JCP 2006 — the `theta` optimality criterion and nucleation without initial hole seeding.
- Amstutz, *Analysis of a level set method for topology optimization*, Optim. Methods Softw. 2011; and the multi-material extension, CMAME 2020.
- Carpio & Rapun, *Solving inhomogeneous inverse problems by topological derivative methods*, Inverse Problems 2008.
- Feijoo, *A new method in inverse scattering based on the topological derivative*, Inverse Problems 2004; Guzina & Bonnet on generalized TD for inverse scattering.

**Small-inclusion asymptotics (the presence variable)**
- Ammari & Kang, *Polarization and Moment Tensors*, Springer 2007.
- Ammari & Volkov, leading-order term in the asymptotic expansion of the scattering amplitude for small dielectric inhomogeneities.
- Cedio-Fengya, Moskow & Vogelius, Inverse Problems 1998; Vogelius & Volkov, M2AN 2000.

**Trans-dimensional inference**
- Green, *Reversible jump MCMC computation and Bayesian model determination*, Biometrika 1995.
- Richardson & Green, JRSS-B 1997 — split/merge moves with dimension matching.
- Bodin & Sambridge; Sambridge et al., *Trans-dimensional inverse problems, model comparison and the evidence*, GJI 2006.

**Phase-field alternative (not proposed, noted as the other school)**
- Blank et al., *Phase-field approaches to structural topology optimization*; Takezawa et al. on reaction-diffusion nucleation without a double-well potential.
