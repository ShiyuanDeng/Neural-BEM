# NU-001: coefficient-space normal update, drift audit (pre-registered)

2026-10-01. Implementation owner: Claude. Written and committed **before** any
NU-001 campaign run; the decision rules below are fixed.

## Approval

The user supplied the [coefficient-space update proposal](02_proposals/01_coefficient_space_update.md)
and, after the [review against the code](02_proposals/02_review_against_code.md),
replied **"just do them all"**: arm A, arm B, the pre-run control, the drift
logging and the six-configuration runs.

## What changes

Only the geometry update. Code: [`n_update.py`](../../../../experiments/cleaned_interface/n_update.py),
[`n_update_audit.py`](../../../../experiments/cleaned_interface/n_update_audit.py),
tests in [`test_n_update.py`](../../../../experiments/cleaned_interface/test_n_update.py).

| Arm | Trial map | Derivative |
|---|---|---|
| `nodal` | CI-001 `ProjectedUpdate`: z + P_K[A(z+h n) − A(z)], 8192-node splines | central FD, 2(2M+1)+2 projections per prepare |
| `A` | z + P_K[g_a N], g_a = h_a(θ)/σ₀, N = Σ j z_j w^j | exact (affine trial; index shifts) |
| `B` | z + P_K[g_a N + ψ_a z′], ψ_a from eq. 11 (HLS) | exact (one extra convolution) |

h_a has the same coordinates as CI-001 (a₀, a_m, b_m in metres), so the clips
(12/18/6 mm by order), damping, M schedule, cleanup and frontier transfer
unchanged. The normal move is h_a σ/σ₀, i.e. metres up to the speed ratio.

Validity in arms A/B is tiered (first decisive tier wins): exact signed area;
the incremental certificate of Lemmas 3–4 against the accepted curve's |W|²
reciprocal (window 64, computed at every prepare, failures tolerated); a
Bernstein bound on min|z′|² from exact samples; otherwise the baseline sampled
`FourierCurve.validate`. Decisions therefore equal the nodal semantics
whenever the cheaper tiers are inconclusive.

No CI-001 frozen source is modified. `n_update_audit` substitutes the runner's
update class and policy for one run; `configuration.json` records the
substituted update and `plan.json` the arm's construction string.

## Execution

- Physics: `nodal_kress` in every arm, `Execution(device='auto', frequency_threads=1)`.
  This host has 4 vCPUs and no CUDA, so `auto` falls back to the CPU and records it.
- Cases: the six core configurations, from the prescribed original start.
- The **nodal arm is the archived CI-001 campaign** (GPU host). A full rerun of
  `core__circle_to_c` on this CPU host with the unchanged CI-001 sources was
  decision-identical: 1167 fit units on both hosts, the same accepted steps in
  every stage, stage losses within 2.7e-9 relative and the final curve within
  1.3e-13. Rerunning all six would cost about 7 CPU-hours for no new
  information. The rerun took 1067 s of fitting (CI-001: 63 s on the GPU), of
  which geometry was 23 s.
- Deviation for arms A and B: `fit_seconds` 1800 → 14400 and `audit_seconds`
  300 → 3600, because this CPU host is about 17× slower than the RTX 5090 host
  that set those caps (CI-001 itself never reached them). Work-unit caps are
  unchanged, so the budget that binds is the same as in CI-001.
- Up to four cases run concurrently. Wall times are indicative; the geometry
  seconds recorded by each update (`geometry_work`) are the timing measure, set
  against the host rerun and the per-prepare timings of the control.
- Campaigns: `results/validation/cleaned_interfaces/NU-001-{A,B}`, each
  prepared from the commit that adds this plan, with augmentation copied from
  CI-001.

## Pre-registered decision rules

Computed by `n_update_audit.decide` from `drift.json`.

**Drift flags** for arm X on case c (any one flags c):

1. max speed ratio r_σ over accepted states > 1.5;
2. max r_σ > 1.1 × the nodal arm's max r_σ on c (the nodal path already
   drifts to 1.06–1.16, see the review);
3. log|W|² Chebyshev degree (window 64, tolerance 1e-12) at the last accepted
   state of any stage > 1.3 × the nodal arm's degree at that stage.

**Match** on c: (X passes the frozen CI-001 comparison gates, or the nodal arm
does not) and (X recovers, or the nodal arm does not).

**Outcome.**

- Arm A qualifies if it has no drift flag on any case and matches on ≥ 5/6.
- If A qualifies, adopt the N-update (arm A).
- Otherwise, if B qualifies under the same rule, adopt arm B.
- Otherwise keep the nodal trial map.

The proposal's third outcome ("adopt only the hybrid cos(mα)σ columns") is
withdrawn before the runs: the control shows those columns are not the
baseline's basis (up to 66% different), so they cannot replace its Jacobian.

K_tr is replaced by the log-series degree in rule 3: `nodal_kress` has no
trace cutoff, and the degree is the drift-sensitive quantity behind it.

## Logged, not decisive

Per accepted state: r_σ. Per stage (last state): β_W, Λ_W, Λ_W/β_W, log
degree, ‖Y‖₁, ρ_c, energy fraction above K/2, LM iterations and accepted
steps, trials by status and refusal cause, validity tier counts, crop tail
(max and median). Per case: m*, outcome, recovery, RMS, fit units, wall time,
geometry preparation/trial/certificate seconds and physics seconds.

## Deferred

Full arclength emulation (eqs. 8–9) as a trial map; the Gram–Cholesky
frontier; SOS/SDP certificates; conformal and Möbius gauges; direct Cartesian
coefficient updates; the Mikula–Ševčovič relaxation term (it breaks
T_z(0) = z and the update cannot see which trial LM accepts); an all-36 rerun.

## Next iteration

Iteration 09 opens with the NU-001 results: the decision, the drift table and
the timing split.
