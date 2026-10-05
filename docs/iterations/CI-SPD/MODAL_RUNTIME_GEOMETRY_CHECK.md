# Modal inverse runtime: verified verdict and geometry-check proposal

2026-10-05. Scope: `feature/shape-frequency-continuation` at `41d8ab4`,
`solvers/bem_inverse/`; pipeline `modal_fixed` with modal Müller physics,
`certified_spectral` geometry, `CumulativePolicy`, localization off. The solver package has no diff between
that revision and verification checkout `0e5a9a7`.

**Verdict:** differences among recovered TG-002 cases mostly follow the amount
of scheduled LM work. Certificate cost is an additional bottleneck in aphex
and hook. Reusing certificates and avoiding certificates on rejected proposals
are sensible changes, but their decision equivalence and speedups remain to be
qualified.

**Material correction to the supplied draft:** `geometry_work` accumulates
initial-audit, fit and final-audit work on one update object. Dividing those
timers by `fit_and_localization_seconds` does not give a measured fit-only
geometry share. With the matching `total_seconds` denominator, geometry is
**13.0–17.8% of whole-run time** in the 23 recovered non-circle cases, and
**68.8%** in failed aphex c13.3. The equal-cost Fix B scenario below gives
**10.5–15.5%** and **31.8–42.5%**, respectively. The supplied aphex **11–19%**
degree-proxy forecast is not independently verified by the saved evidence.

This note reads existing source and receipts and recomputes counts and scalar
estimates. No inverse fit, geometry replay, certificate timing, or new experiment
was run. No proposed fix was implemented.

Tags: **[code]** source; **[measured]** saved receipts; **[derived]** arithmetic,
inference or forecast; **[unverified]** a supplied claim without retained evidence
found during this verification.

## Evidence and timing boundaries

- [PC-001 M1 receipts](../../../results/validation/cleaned_interfaces/PC-001/M1/runs/),
  [summary](../../../results/validation/cleaned_interfaces/PC-001/M1/summary.json) and [manifest](../../../results/validation/cleaned_interfaces/PC-001/M1/manifest.json):
  30 TG-002 cases, 26 recovered.
- [PC-002 NS receipts](../../../results/validation/cleaned_interfaces/PC-002/NS/runs/) and
  [manifest](../../../results/validation/cleaned_interfaces/PC-002/NS/manifest.json): nodal Kress with spline updates, the
  experimental per-curve reuse and band-matched resolution profile. This is a
  comparison of complete pipelines, not an isolated geometry intervention.
- [Maintained package README](../../../solvers/bem_inverse/README.md).

**[code]** [`runner.py`](../../../solvers/bem_inverse/runner.py) constructs
one update object, calls `audit` with it before fitting and again afterwards,
then writes `geometry_work=update.counts`. Each audit prepares once and makes
two FD trials. **[measured]** Every one of the 60 M1/NS receipts has

```text
geometry_work.trial_constructions = sum(len(stage.trials)) + 4
```

In M1 there are 2,511 fit proposals and 2,631 total trial constructions.
The latter includes 120 audit moves. Preparation and certificate timers also
include audits; their fit/audit split is not saved. Physics counters likewise
include audits and sum durations from concurrent frequency threads, so their
sum cannot be interpreted as a wall-time share.

Use `fit_and_localization_seconds` and `fit_and_localization_units` for fit
time and work (localization is disabled in all cases), and `total_seconds` for
whole-run geometry shares. For example, kite c0.5 is 87.736 s fitting,
91.159 s overall, and 16.208 s cumulative geometry. Its whole-run share is
17.78%; 16.208/87.736 = 18.47% is only an upper bound on its fit-only share.
The two audits take 3.405 s, so a loose fit-only geometry-share bound is
14.59–18.47%. Audits are not uniformly 3.5 s: in M1 they range approximately
2.0–4.8 s.

## Notation

| Symbol | Meaning |
|---|---|
| $z(\theta)=\sum_{\lvert j\rvert\le K}z_j e^{ij\theta}$ | Accepted boundary in the complex plane |
| $K$ | Geometry storage band: 4–20 early, 192 later |
| $M$, $a$ | Update band; $a\in\mathbb R^{2M+1}$ contains distances in metres |
| $h(s)$, $\hat n$ | Normal move in normalized arclength $s\in[0,2\pi)$; unit outward normal |
| $N_g$ | $2^{\lceil\log_2\max(1024,16(2K+1))\rceil}$ here; 8192 at $K=192$ |
| $F$, $K_t$ | Active frequencies (1–4 early, 19 later); trace cutoff (64 early, 128 later), refined to $K_t+32$ |
| $r$, $L$, $L^+$ | Normalized residual; $L=\tfrac12\lVert r\rVert^2$; refined loss |
| $J$, $G$, $g$, $D$ | $\partial r/\partial a$, $J^\top J$, $J^\top r$, $\operatorname{diag}(\max(G_{ii},1))$ |
| $\lambda$, $\delta$, $\eta$ | LM damping, direction and halving index |
| $W$ | $(z(\theta)-z(\phi))/(e^{i\theta}-e^{i\phi})$, continuously extended to the diagonal |
| $\Lambda$, $\beta$ | Coefficient upper bound and proposed lower bound for $\lvert W\rvert^2$ |
| $Y$, $\rho$ | Approximate reciprocal of $\lvert W\rvert^2$; $\rho=\lVert1-\lvert W\rvert^2Y\rVert_1$ |
| $\lVert f\rVert_1$, $\nu(f)$ | Coefficient sums $\sum\lvert f_j\rvert$ and $\sum\lvert j\rvert\lvert f_j\rvert$ |
| unit | One forward solve or one Jacobian batch at one frequency in the optimizer ledger |

LM means Levenberg–Marquardt; FD, finite difference; FFT, fast Fourier
transform; LU, dense LU factorization. Geometry code stores $z$ in package
length units; its normal displacement is divided by `length_unit_m`. Equations
below write $z$ in physical units for readability.

## 1. What one fit does [code]

### 1.1 Schedule

[`policy.py`](../../../solvers/bem_inverse/policy.py) schedules:

1. A damped warm-up at 0.25 GHz, $M=1$, $K=4$.
2. Four growing damped frequency prefixes ending at 0.5, 0.75, 1.0 and
   1.25 GHz. For TG-002 these have $M=3,5,7,9$ and $K=2M+2$.
3. One undamped stage on those same four frequencies.
4. Release stages $M=11,15,19$ on all 19 real frequencies, $K=192$,
   with quotas of 1500 units each.
5. Fixed stages $M=25,31,37$, with quotas of 304 units each.
6. A measured frontier followed by tail stages growing $M$ by 6, at most 95.

The noiseless policy also crops the state to band 64 and pads it to 192 before
`fixed_M25`; this changes the curve and invalidates an exact-curve cache.
The frontier is the largest **paired, orthonormal arclength-harmonic** Jacobian
column norm at the highest real frequency (2.5 GHz here) reaching 1% of the
largest paired norm. The tail rounds upward in increments of 6 from $M=37$;
its last band need not equal the measured frontier exactly.

### 1.2 LM and work accounting

[`continuation/lm_backend.py`](../../../solvers/bem_inverse/continuation/lm_backend.py)
forms

$$G=J^\top J,\qquad g=J^\top r,\qquad
D=\operatorname{diag}(\max(G_{ii},1)),\qquad
\delta=-(G+\lambda D)^{-1}g. \tag{1}$$

Coordinates are clipped to 12, 18 and 6 mm for orders 0, 1 and $\ge2$.
The code tries $2^{-\eta}\delta$, $\eta=0,\ldots,7$, at up to five damping
values. Exhaustion multiplies damping by 10; acceptance multiplies it by 0.3.

A production decrease must pass

$$\Delta L=L(z)-L(\tilde z),\quad
\Delta L^+=L^+(z)-L^+(\tilde z),\quad
\min(\Delta L,\Delta L^+)>
\text{margin}+5\lvert\Delta L-\Delta L^+\rvert. \tag{2}$$

The candidate predictions must also agree across resolutions at every active
frequency: $10^{-5}$ at $\le0.5$ GHz, $10^{-7}$ above. A disagreement hard-stops
`modal_fixed`; it has no resolution response. All four M1 numerical failures
(aphex at all three contrasts; hook c13.3) record
`candidate leaves the frozen numerical-resolution regime`.

For a stage with completed physics batches and at least one refined check,

$$U=F\big[1+n_{\rm eval}+(n_{\rm check}+1)+(n_{\rm acc}+1)\big]. \tag{3}$$

Here $n_{\rm eval}$ counts physics-evaluated trials, **not all proposed moves**.
Refined base values are lazy: the refined $+1$ occurs only if a check is reached.
Quota interruption, partial work and failed calls require the actual ledger;
(3) is not an unconditional identity for every stage. The frontier adds two
units separately. Jacobian batches are billed as units even though they reuse
LU factors and are much cheaper than complete forward evaluations.

**[measured/derived]** Kite c0.5 `release_M19` has 48 proposal rows, but only
47 evaluated trials, 14 refined checks and 14 accepted steps:

$$U=19(1+47+15+15)=1482,$$

matching its [stage receipt](../../../results/validation/cleaned_interfaces/PC-001/M1/runs/kite__c0.5/release_M19.json).

### 1.3 Geometry map and validity

[`spectral.py`](../../../solvers/bem_inverse/spectral.py),
[`certified.py`](../../../solvers/bem_inverse/certified.py),
[`batched.py`](../../../solvers/bem_inverse/batched.py) and
[`device_certified.py`](../../../solvers/bem_inverse/device_certified.py)
implement the centred normal move and arclength quadrature:

$$h(s)=a_0+\sum_{m=1}^{M}(a_m\cos ms+b_m\sin ms), \tag{4}$$
$$y(\theta_i)=z(\theta_i)+h(s(\theta_i))\hat n(\theta_i), \tag{5}$$
$$\mathcal S(y)_k=\frac1{N_g}\sum_i y(\theta_i)\alpha'(\theta_i)
e^{-ik\alpha(\theta_i)},\quad |k|\le K,\qquad
\Pi_z(a)=z+\mathcal S(y)-\mathcal S(z). \tag{6}$$

$\alpha$ is the normalized arclength of the moved Fourier interpolant.
The projection repeats on $2N_g$ and refuses unresolved coarse/fine agreement.
Preparation at each linearized state uses central FD on the complete map:
$2(2M+1)+2$ projections. M1 batches preparation on the GPU; finite trial
projection remains on the CPU. Preparations occur at stage entry, after accepted
steps and in audits, rather than just once per unique curve globally.

Validity is checked in sequence on the coarse moved curve, fine moved curve,
and candidate. An earlier refusal skips later roles.

| Tier | Test | Effect |
|---|---|---|
| 1 | Exact coefficient signed area $>0$ | Refuse if nonpositive |
| 2 | Base-certificate increment bound | Accept if the residual and regularity bounds pass |
| 3 | Own reciprocal certificate of a crop, plus a tail bound; windows 64 then 128 | Accept if decisive |
| 4 | Sampled area, minimum speed and polygon self-intersection | Accept or refuse |

Tier 2 uses

$$b=\rho_z+\epsilon_z+
(2\nu(z)\nu(\Delta)+\nu(\Delta)^2)\lVert Y_z\rVert_1<1,\qquad
\frac{1-b}{\lVert Y_z\rVert_1}\ge10^{-12}\sum_jj^2|x_j|^2, \tag{7}$$

where $\Delta=x-z$ and $\epsilon_z$ is the implementation's rounding allowance.
Tier 3 uses the analogous tail-adjusted bound; $\rho_x<1$ alone is an incomplete
description of the implemented test. The moved-curve crop is
`min(moved_band, max(base_band, 64))`; the discarded tail is explicitly bounded.

The underlying exact-arithmetic lemma is valid: if
$|W|^2Y=1-E$ and $\lVert E\rVert_1=\rho<1$, then

$$|W|^2\lVert Y\rVert_1\ge |1-E|\ge1-\rho>0. \tag{8}$$

Thus the curve is simple and regular, including the diagonal limit
$W=z'/(ie^{i\theta})$. **The numerical certificates are not interval-verified:**
the code explicitly records `arithmetic_verified=False` and a heuristic FFT
rounding allowance. A sampled fallback can accept an inconclusive certificate.
In these M1 receipts all candidate-role checks nevertheless passed tier 2 or 3;
sampled acceptances occurred only for moved curves.

**Certificate cost [derived].** The GPU routine builds a reciprocal Chebyshev
series using windowed 2-D FFT convolutions. Its degree is chosen by the
log-series bound

$$q=\frac{\sqrt\Lambda-\sqrt\beta}{\sqrt\Lambda+\sqrt\beta},\qquad
\frac{2q^{n+1}}{(n+1)(1-q)}\le\tau_c. \tag{9}$$

The rough asymptotic estimate
$n\approx\tfrac12\sqrt{\Lambda/\beta}\log(1/\tau_c)$ gives 138 and 1382 at
$\beta/\Lambda=10^{-2}$ and $10^{-4}$, $\tau_c=10^{-12}$.
The actual scalar loop gives **125 and 1255**. Both capture the rapid growth
as the proposed minimum shrinks. Near approaches can make $\beta$ small, as
can small speed or a loose coefficient upper bound; thin geometry is not the
only possible cause. The code caps degree at 4000. A reported degree may also
be recomputed after the reciprocal residual is evaluated, so it is not always
the number of recurrence terms actually executed.

### 1.4 Physics per frequency

[`modal_muller.py`](../../../solvers/bem_inverse/modal_muller.py) and
[`modal_geometry.py`](../../../solvers/bem_inverse/modal_geometry.py) use:

1. Frequency-independent geometry cached by exact coefficient bytes, workspace
   window and device; this includes a separate $\log|W|^2$ construction.
2. Fourier–Galerkin Müller assembly from Chebyshev radial expansions and the
   exact log symbol.
3. Graf addition-theorem source/receiver expansions.
4. Dense LU on the CPU, even with CUDA geometry/assembly.
5. One additional reciprocal solve and Hadamard contraction for the Jacobian at
   stage-entry and accepted states, plus audit/frontier derivatives.

Production and refined physics use distinct workspaces. Geometry-update
certificates and physics geometry do not share their $|W|^2$ construction.
Physics uses log tolerance $10^{-16}$, rather than the geometry check's
$10^{-12}$; these are related constructions, not identical cached artifacts.

## 2. Runtime verdict [measured and derived]

`Geometry all` and `Certificates all` below include both audits.
`Geometry/run` has the matching whole-run denominator. Proposal counts are
fit-only. Work percentages use the saved fit ledger: trial production,
all refined evaluations, all Jacobians and initial objectives respectively.
The frontier's two units are separate; rounding can keep percentages from
adding to exactly 100. The refined/Jacobian columns include their stage-entry
work; `entry` in this table means initial production objectives only.

| Case | Fit s | Units | ms/unit | Accepted | Fit proposals | Units % trial / refined / Jacobian / entry | Geometry all s | Geometry/run | Certificates all s |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| circle c13.3 | 4.4 | 461 | 9.5 | 12 | 12 | 11 / 21 / 39 / 28 | 0.7 | 9.6% | 0.1 |
| peanut c4 | 15.1 | 1260 | 12.0 | 34 | 46 | 25 / 33 / 32 / 10 | 2.4 | 13.0% | 0.5 |
| star c13.3 | 56.1 | 4104 | 13.7 | 79 | 106 | 29 / 35 / 30 / 7 | 9.3 | 15.5% | 1.5 |
| cog c13.3 | 69.6 | 4856 | 14.3 | 149 | 154 | 29 / 34 / 32 / 5 | 11.8 | 16.1% | 3.1 |
| kite c0.5 | 87.7 | 4814 | 18.2 | 116 | 220 | 48 / 26 / 24 / 3 | 16.2 | 17.8% | 7.3 |
| hook c13.3, failed | 32.1 | 1180 | 27.2 | 78 | 146 | 36 / 38 / 23 / 3 | 8.1 | 22.4% | 6.9 |
| aphex c13.3, failed | 45.9 | 414 | 110.8 | 72 | 127 | 34 / 34 / 31 / 2 | 32.9 | 68.8% | 31.9 |

Findings:

1. **Scheduled work explains most recovered-case variation.** Units vary
   15.1-fold (322–4856), while fit ms/unit varies 2.54-fold (7.97–20.22).
   Fit times span 2.57–87.74 s. Work units are an accounting metric, not
   equal-cost physical operations, so this is empirical evidence rather than
   a universal constant-price model. Aphex is a clear per-unit-cost exception.
2. **Work grows by two routes.** Kite c0.5 release M15/M19 consume
   $(1463+1482)/4814=61.2\%$ of fit units. Star c13.3 runs through M85;
   cog c13.3 through M73. Accepted steps, backtracking and active-frequency
   counts all contribute; accepted-step count alone is insufficient.
3. **Trial production is usually a minority of billed work.** It accounts for
   roughly one quarter to one third in the selected ordinary examples;
   kite c0.5 reaches 48%. Refined checks and billed derivatives explain much
   of the balance. Their unit shares are not wall-time shares.
4. **Cumulative geometry is modest in recovered non-circle cases:**
   13.0–17.8% of overall wall time. The draft's 13.9–19.1% ratios against fit
   time are upper bounds, not isolated fit-only measurements. In PC-002 NS,
   the analogous all-geometry/fit ratios are 20.8–55.4%; CPU spline preparation
   dominates that geometry bucket. Star c13.3 records 88.995 s preparation,
   90.733 s cumulative geometry and 163.827 s fitting, with the same audit
   boundary caveat.
5. **Invalid aphex proposals spend certificates before sampled rejection.**
   M1 records 43 self-intersection refusals, all in aphex: 5/1/37 at
   c0.5/c4/c13.3. Aphex c13.3 also records 78 failed full-certificate calls.
   Their aggregate duration is not separated from successful calls.

**[unverified]** The supplied draft attributes 73% of aphex c13.3 certificate
work to refused trials, with median degrees 3025 versus 274, from reconstructing
116 of 131 total trials and weighting degree by FFT area. No saved replay,
per-call degree table or timing artifact supporting those numbers was found.
The stage receipts retain step norms, damping/backtrack indices and accepted
step vectors, but not a degree/cost record for every rejected proposal. A
degree proxy also needs window, attempted degree, failed-call and FFT-size
accounting. These numbers and the supplied four-minute CPU-replay anecdote
are not promoted to verified results here.

### Waste identified in source

| Item | Where | Proposed treatment |
|---|---|---|
| Certificates precede sampled rejection; tiers 2–3 only accept | `certified.py::check` | B |
| Both moved grids get coefficient checks | `certified.py::trial` | A2, with equivalence qualification |
| A candidate's own certificate is lost on the next fresh prepared space | `certified.py::_base`, `batched.py::prepare` | A1 |
| Update and two physics workspaces separately construct $\lvert W\rvert^2$ | `device_certified.py`, modal geometry | Outside this proposal |
| New stages repeat objective/linearization work; refined cache is stage-local | `lm_backend.py::Objective`, `fit_stage` | Outside this proposal; many stage settings/curves change, so reuse needs an exact key |
| Cheap Jacobians receive full work units | `lm_backend.py::Ledger` | Outside this proposal; changes the policy budget, not just execution cost |
| CPU spline prepare repeats the complete map for FD | `geometry.py::ProjectedUpdate.prepare` | Separate [GPU spline proposal](GPU_SPLINE_FAIR_BASELINE.md) |

The draft's general 2–5% stage-entry reuse saving was not independently
established: which endpoints have identical curve, data, weights and resolution
must first be counted. Not every stage transition is eligible.

## 3. Proposed fixes

### A1: exact reuse, small implementation change

When an LM-accepted candidate passed tier 3 using **window 64**, retain its own
certificate and reuse it when that exact curve next needs a base certificate.
At candidate role, the crop is the full stage storage band, so this can be the
same input as `_base`. Key reuse by coefficient bytes and shape, certificate
configuration, device and arithmetic. Invalidate on crop/pad, cleanup or other
changes. Do not carry a different-window certificate into a window-64 base.

The current `CertifiedSpace.cache` is local to each preparation, and `certify`
does not return the certificate object for reuse. The change therefore needs
explicit retention across prepared spaces, not just another lookup in the
existing space. For identical inputs/configuration, reuse introduces no new
arithmetic and should preserve decisions and coefficients exactly. It still
requires trace validation; counters/timers will change.

### A2: omit the fine moved-curve coefficient check

Retain the fine projection and the $N_g/2N_g$ agreement gate, but omit the fine
moved-curve validity call in the supplied A2 scenario. **[measured]** All
**2,468 fit trial rows with returned paired tiers** have the same coarse/fine
tier. Aggregate fine-role counters also show no fine-only refusal. The 43
coarse self-intersection refusals stop before the fine check.

This supports A2 on the recorded path; it does not prove decision equivalence
for all curves. Projection agreement is an accuracy check on retained
coefficients and is not a simplicity proof for the full fine moved curve.
Retaining a sampled fine check is a more guarded variant, but adds cost not
included in the A scenario below. Accordingly, **only A1 is an exact reuse
claim; A2 changes a validation gate and needs qualification**.

### B: sampled proposals, coefficient qualification at acceptance

Run the existing sampled tests on coarse moved, fine moved and candidate
curves before any physics, short-circuiting a refusal. Retain projection
agreement and all current physics/refined acceptance checks. Once a proposal
passes the numerical acceptance gate, qualify its candidate with a coefficient
certificate before committing the new accepted state, then retain that
certificate as the next base. This requires an acceptance hook in the LM path;
placing the certificate in `trial` would still certify numerically rejected
proposals and would not implement the claimed count reduction.

If the accepted-candidate certificate is inconclusive, **do not claim that
every accepted state is certified while silently using sampled fallback**.
Either retain fallback and weaken that guarantee, or declare a certificate
refusal/retry rule, which may change the path. The strict B proposal here
requires successful qualification of each new accepted state. A fresh full
certificate may be inconclusive even when today's incremental certificate
passes; that must be checked separately. "Certified" retains the current
heuristic floating-point meaning described above.

`CertifiedSpectralUpdate(shadow=True)` counts cases where today's certificate
accepts but the sampled test refuses. Require zero such disagreements before
changing to sampled-first. M1's recorded zero counters are **not evidence of
this condition**: all M1 receipts have `shadow=false`. Zero shadow disagreements
is necessary for this gate change on the old path, but does not establish that
fresh certificates, the new acceptance hook and all later trajectories agree.

## 4. Expected effect [derived; no new timings]

Forecast against the matching **whole-run** timing boundary. Let $T$ be
`total_seconds`, $P$ preparation time, $C$ certificate time and
$O=$ trial-construction time minus $C$. These are cumulative update timers.
Let $S$ be existing sampled-test time, which is already inside $O$.

$$G=P+O+C,\quad
T'=T-C+C'+\Delta S,\quad
\operatorname{share}'=\frac{P+O+C'+\Delta S}{T'}. \tag{10}$$

Assumptions: unchanged accepted path, stage/work schedule and non-certificate
costs; removed serial geometry time reduces whole-run wall time one-for-one;
equal cost per certificate call within each case. Actual per-window timing is
not retained, so $\omega=1,2$ are scenarios, not measured call counts.

| Symbol | Count, from cumulative receipts unless specified |
|---|---|
| $n_b$ | Base certificate attempts |
| $n_3$ | Role checks entering tier 3: full + sampled accepted + sampled refused |
| $n_3^f$ | Those tier-3 checks for the fine moved role |
| $n_a^{\rm full}$ | LM-accepted candidates recorded as tier 3 |
| $n_a$, $n_{\rm st}$ | Accepted LM steps and executed fit stages |
| $n_{\rm tr}$ | Total constructions, including four audit FD moves |

$$n_c=n_b+\omega n_3,\qquad C'=C\frac{n_c'}{n_c}. \tag{11}$$
$$\text{A: }n_c'=n_c-\omega n_3^f-n_a^{\rm full},\qquad\Delta S=0. \tag{12}$$
$$\text{B: }n_c'=n_a+n_{\rm st}+2,\qquad
\Delta S=3n_{\rm tr}t_s-S,\quad t_s=0.0006\text{ s}. \tag{13}$$

The two extra B certificates model the audit bases. A counts every accepted
tier-3 candidate as eligible for one reuse; the receipts do not record whether
it passed window 64 or whether that next base was actually requested. Thus
A1's reuse count is optimistic. B assumes one successful full certificate per
listed state; escalation/failure costs are not included. Stage entries that
need no fresh certificate could reduce that count. The sampled term assumes
three tests even on short-circuited proposals, and subtracts existing sampled
time to avoid double counting. It excludes sampled base-state qualification.

**[measured/derived]** The saved M1 fallback tests total 0.082770 s across
135 calls, or **0.613 ms/call**, supporting the 0.6 ms representative value.
Those calls are concentrated in failed scenes; this is not a per-case timing
measurement for sampled-first on all curves.

### Worked example: kite c0.5, one-window scenario

From its receipts: $T=91.159$, $P=2.207$, $O=6.672$, $C=7.329$ s;
$n_b=122$, $n_3=367$, $n_3^f=124$, $n_a^{\rm full}=58$,
$n_a=116$, $n_{\rm st}=12$, $n_{\rm tr}=224$ and $S=0$.

$$\operatorname{share}=16.208/91.159=17.78\%.$$
$$C'_B=7.329\frac{116+12+2}{122+367}=1.948\text{ s},\qquad
\Delta S_B=3(224)(0.0006)=0.403\text{ s}.$$
$$T'_B=91.159-7.329+1.948+0.403=86.182\text{ s},\qquad
\operatorname{share}'_B=13.03\%.$$

A gives 88.431 s overall and 15.24% geometry. The B scenario removes about
5.0–5.8 s overall across the one/two-window assumptions. If audit savings are
small, fitting remains approximately 82–83 s; its exact split is not available.

### Whole-run scenarios

| Group | Measured geometry/run | A | B | Remove certificate time only | B overall wall time |
|---|---|---|---|---|---|
| 23 recovered non-circle cases | 13.0–17.8% | 11.6–15.3% | 10.5–15.5% | 6.8–13.4% | About 0.1% slower to 6.5% faster |
| 3 circles | 9.6–16.7% | Same | 10.6–17.9% | 8.9–15.9% | About 0.07–0.09 s slower |
| hook c13.3, failed | 22.4% | 16.1–16.5% | 10.2–13.1% | 4.1% | 36.1 → 31.2–32.3 s |
| aphex c0.5, failed | 46.0% | 33.4–34.8% | 15.6–22.5% | 2.9% | 29.6 → 18.9–20.6 s |
| aphex c4, failed | 20.3% | 14.0–14.5% | 8.4–10.7% | 3.9% | 38.4 → 33.4–34.3 s |
| aphex c13.3, failed | 68.8% | 59.4–60.5% | 31.8–42.5% | 6.0% | 47.8 → 21.9–26.0 s |

"Remove certificate time only" is a diagnostic subtraction with sampled costs
held fixed. It is not a deployable no-certificate algorithm forecast.
The equal-cost model plausibly overweights the certificates B keeps when
rejected moves are more expensive, but the saved per-call evidence does not
prove that B's forecast is an upper bound. **[unverified]** The supplied
degree-weighted aphex forecast of roughly 11–19% geometry and 15–24 s fitting
could be investigated; it must not appear as a verified outcome.

Preparation and CPU trial projection remain after these fixes. These costs,
physics geometry/assembly and the amount of LM work explain why the changes
can trim certificate outliers without eliminating the recovered-scene spread.
Removing checks also does not repair the numerical-resolution failures.

## 5. Qualification plan — proposed, not approved or executed

1. Pre-register a new experiment ID under `docs/iterations/`, using TG-002's
   30 centred-start cases only, and obtain explicit user approval of that ID
   before running. Read the [benchmark README](../../../experiments/benchmark/README.md).
2. Run the unchanged recipe with shadow enabled; require
   `shadow_disagreements=0` on every case. Retain the four M1 failures as
   comparison evidence; failure is not permission to omit them.
3. Qualify A1 independently. Require identical accepted coefficients, numerical
   decisions, trial traces and units, ignoring the deliberately changed
   timing/certificate counters. Record exact cache hits and eligible windows.
4. Qualify A2 independently, then B. Record fresh-certificate failures and
   require the same accepted trajectory, outcome and final coefficients before
   claiming decision equivalence. Check the acceptance hook occurs before any
   accepted-state callback. Passing the shadow gate alone is insufficient.
5. Preserve passing final audits. For the four baseline numerical failures,
   compare their stop and failed-run evidence as well as their endpoint audit;
   three M1 endpoint audits pass despite failed recovery; aphex c13.3's
   endpoint audit fails. Preserve this distinction rather than requiring
   equivalence to an audit result the baseline did not achieve.
6. Add phase-specific geometry counter/timer snapshots before and after audits
   and fitting, plus per-role/window/degree certificate timings. Report fit and
   overall wall time separately, fit-only geometry share, certificate time,
   units and decisions. Compare forecasts to the boundary they actually model.

No experiment ID is registered or approved by this evidence note. Repository
instructions require committing and pushing all evidence after any future new
experiment; the read-only verification in this note does not run one.

## 6. Per-case whole-run forecast [derived]

`Now` uses cumulative geometry divided by `total_seconds`. A/B ranges vary
$\omega$ only, under (10)–(13). Fit times are measured and are not forecast
with the cumulative geometry timers. Aphex and hook c13.3 are baseline failures.

| Case | Fit s | Overall s | Now | A geometry/run | B geometry/run | B overall s |
|---|---:|---:|---:|---:|---:|---:|
| aphex_twin c0.5 | 27.2 | 29.6 | 46.0% | 33.4–34.8% | 15.6–22.5% | 18.9–20.6 |
| aphex_twin c13.3 | 45.9 | 47.8 | 68.8% | 59.4–60.5% | 31.8–42.5% | 21.9–26.0 |
| aphex_twin c4 | 33.9 | 38.4 | 20.3% | 14.0–14.5% | 8.4–10.7% | 33.4–34.3 |
| asymmetric c0.5 | 22.3 | 25.7 | 16.5% | 14.9–14.9% | 13.8–14.7% | 24.9–25.2 |
| asymmetric c13.3 | 41.6 | 45.2 | 14.9% | 13.9–13.9% | 13.3–14.0% | 44.3–44.7 |
| asymmetric c4 | 30.4 | 34.0 | 15.5% | 14.4–14.5% | 13.9–14.6% | 33.3–33.6 |
| c_shape c0.5 | 19.5 | 23.0 | 14.7% | 12.4–12.5% | 11.1–12.3% | 22.0–22.4 |
| c_shape c13.3 | 32.2 | 36.1 | 14.3% | 12.4–12.4% | 11.1–12.3% | 34.8–35.3 |
| c_shape c4 | 31.0 | 34.7 | 14.4% | 12.5–12.5% | 11.3–12.4% | 33.5–33.9 |
| circle c0.5 | 2.6 | 6.0 | 16.7% | 16.7–16.7% | 17.9–17.9% | 6.1–6.1 |
| circle c13.3 | 4.4 | 7.5 | 9.6% | 9.6–9.6% | 10.6–10.6% | 7.5–7.5 |
| circle c4 | 2.9 | 6.3 | 16.5% | 16.5–16.5% | 17.7–17.7% | 6.4–6.4 |
| cog c0.5 | 24.2 | 27.5 | 16.6% | 14.8–14.9% | 13.8–14.7% | 26.6–26.9 |
| cog c13.3 | 69.6 | 73.1 | 16.1% | 14.9–15.0% | 14.2–14.9% | 71.5–72.1 |
| cog c4 | 24.9 | 28.4 | 14.9% | 14.4–14.4% | 14.6–15.1% | 28.2–28.4 |
| cross c0.5 | 22.4 | 25.8 | 16.0% | 15.0–15.1% | 14.7–15.5% | 25.4–25.7 |
| cross c13.3 | 41.7 | 45.0 | 13.9% | 13.3–13.4% | 13.2–13.6% | 44.7–44.9 |
| cross c4 | 22.1 | 25.8 | 13.4% | 12.5–12.6% | 12.3–12.9% | 25.5–25.7 |
| hook c0.5 | 22.6 | 26.5 | 16.3% | 12.9–13.0% | 10.5–12.3% | 24.8–25.3 |
| hook c13.3 | 32.1 | 36.1 | 22.4% | 16.1–16.5% | 10.2–13.1% | 31.2–32.3 |
| hook c4 | 44.2 | 49.0 | 17.1% | 14.1–14.2% | 11.8–13.3% | 46.0–46.8 |
| kite c0.5 | 87.7 | 91.2 | 17.8% | 15.2–15.3% | 12.2–13.0% | 85.3–86.2 |
| kite c13.3 | 52.5 | 56.1 | 13.0% | 11.6–11.6% | 10.7–11.5% | 54.6–55.1 |
| kite c4 | 34.0 | 37.5 | 15.7% | 13.7–13.8% | 12.1–13.0% | 36.0–36.3 |
| peanut c0.5 | 16.9 | 20.2 | 13.0% | 12.5–12.6% | 12.6–13.1% | 20.1–20.3 |
| peanut c13.3 | 17.9 | 21.4 | 13.8% | 13.0–13.1% | 13.0–13.6% | 21.2–21.3 |
| peanut c4 | 15.1 | 18.6 | 13.0% | 12.4–12.4% | 12.4–12.9% | 18.5–18.6 |
| star c0.5 | 18.1 | 21.4 | 14.4% | 13.8–13.8% | 13.7–14.3% | 21.3–21.4 |
| star c13.3 | 56.1 | 60.1 | 15.5% | 15.0–15.1% | 15.0–15.4% | 59.7–60.0 |
| star c4 | 29.7 | 33.2 | 15.3% | 14.6–14.6% | 14.5–15.0% | 32.9–33.1 |

Reproduction of this arithmetic requires only saved JSON: read each case's
`fit_result.json` and executed `stage*.json`/release/fixed/warm-up receipts;
count accepted rows with candidate tier `full`; sum the tier-3 counters;
apply (10)–(13). It does not require solving or replaying any boundary.
