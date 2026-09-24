# SC-023 to SC-025 plan — conditional atlas analysis, the refit-gate stall and a frozen policy

2026-09-24. Owner: Claude. It follows the [review resolution](02_proposals/02_review_resolution.md);
the user asked for the review to be implemented without further stops. The
review's question is adopted: **does conditional, physically scaled local
information predict which data and update subspace will produce a useful,
admissible step at lower cost?** Existing branch; no new branch or worktree.

## New measurement that shapes this plan

Before planning, I read SC-022's trial records and replayed its geometry. No
physics solves were used; Q0 records these checks. Two findings:

**1. Most refusals come from the refit gate.** In the Borges C run, 489 of
551 trials are refused as `unresolved_projection`. In the three fixed-M=32
runs the count is 288, 125 and 315.

**2. The gate edge is a property of the curve, not of the step.**
- The accepted curves' own arclength-refit error at K=192 climbs step by
  step, from 1e-15 to 9.6e-8 on the C and 9.9e-8 on the fixed-32 wrong
  circle. The top 16 stored modes grow from 1e-17 to 5e-8.
- At the stall, trials fail at 1.05e-7 even at 1/128 of the step.
- At K=384 the same curves refit to 1e-11.
- Zero steps and small smooth steps do not pump the top modes, so the refit
  is not unstable.

**The cause is the shapes the early steps create.** The first accepted steps
move the boundary 18–23 mm in a single step. That is allowed because the
bounds apply per coefficient; this is the review's point 4. They carve
features with curvature radii far below the truths':

| Run | Tightest radius reached | Truth's tightest radius |
|---|---:|---:|
| Borges C | 4.0 mm | 14.6 mm |
| Fixed-32 wrong circle | 2.6 mm | 50 mm |
| Fixed-32 star | 3.7 mm | — |

These features push the curve's arclength content up to the K=192 ceiling,
and from then on every step fails the 1e-7 gate: about 5 nm.

The C "failure" and the fixed-32 stalls are therefore at least partly a
**numerical-resolution gate freezing a rough intermediate state**, in the
terms of principle 3. They are not yet evidence about bands or data. This
must be settled before band rules are compared.

## Q0 — numerical qualification (SC-023 bundle, `qualification/`)

1. **Refit-gate record.** Geometry only. For every recorded SC-022 state,
   record:
   - the refit error at K=192 and K=384;
   - the top-mode fraction;
   - the tightest curvature radius;
   - the curvature tail above 96.

   For every refused trial, record its relative error. This formalizes the
   measurement above.
2. **Atlas refinement (review N1).** The cells are four states:
   - Borges C at the end of stage 3 (stalled, with a cavity);
   - the Borges star's final state (the high-harmonic claims);
   - the fixed-32 star after its first step (far and rough);
   - the Borges wrong circle's final state.

   Each is taken at 0.5, 1.25 and 2.5 GHz and recomputed at N=1024 against
   the stored N=512. Compared:
   - per-harmonic sensitivity (√diag G);
   - the gradient;
   - conditional LM steps for M ∈ {9, 16, 32, 48} at λ=1e-3.

   **Pass** when two conditions hold:
   - sensitivity agrees to ≤1e-3 relative wherever it is at least 1e-6 of
     its maximum;
   - conditional steps agree to ≤1e-2 relative.

   A cell that fails removes its frequency from fine claims at comparable
   states.
3. **Directional check through the actual update.** At the same four states
   and at 1.25 GHz, compare the Jacobian's predicted data change with central
   differences through `BorgesUpdate.trial`, at ±1 µm. The directions are the
   cosine harmonics p ∈ {1, 9, 15, 20, 32, 48}. Pass: ≤1e-3 relative where
   the change is at least 1e-6 of the data. The gate is disabled for this
   check only, because a 1 µm move is below the refit resolution being
   diagnosed.

Budget: ≤ 30 min and ≤ 200 solves.

## SC-023 — conditional candidates offline (no physics solves)

**States.** All 141 unique recorded states from SC-022's six runs. The dense
G and g are verified by regeneration (bitwise, 2026-09-24).

**Candidates** at each state:

| Factor | Levels |
|---|---|
| Frequency set F | Cumulative {0.5, …, f_max}, with f_max ∈ {0.5, 0.75, …, 2.5} (9 sets). Equal weights; the SPD pattern extended over the catalog |
| Update band M | 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 20, 24, 32, 40, 48 |
| Damping λ | 1e-4, 1e-3, 1e-2, with D = max(diag G, 1) |
| Step control | Coefficient clip (SPD); physical, with maximum normal move ≤ 6 mm |
| Refit gate | G1: K=192, 1e-7 (as run); G2: K=192, 1e-5 (0.5 µm) |

Each step is the conditional LM step over M. The finite Borges trial takes
the first halving (0–7) that is admissible under the gate. Admissible means
no self-intersection, a regular parameterization and a resolved refit.

**Evaluation-only labels:**
- gain = 1 − d_after/d_before, where d is the symmetric RMS distance to the
  truth;
- the first-order normal-ray gain 1 − ‖e−q‖_W/‖e‖_W;
- the admissible halving;
- the change in the tightest curvature radius.

**Truth-free features:**
- the model's predicted decrease as a fraction of the F-loss;
- the model change at the next frequency above f_max, a cross-frequency
  check (none for f_max = 2.5);
- the physical step size (maximum normal and RMS);
- the effective degrees of freedom, tr(G(G+λD)⁻¹)/(2M+1);
- band capture, pred(M)/pred(48).

**Band rules, declared now:**

| Rule | M chosen |
|---|---|
| Ladder | floor(3·k_max(F)), Borges §4 |
| Fixed32 | 32 |
| Knee | the smallest M with pred(M) ≥ 0.9·pred(48) |
| Validation | the M that maximizes the next-frequency model decrease; ties go to the smaller M |
| DOF | the largest M with dof(M)/(2M+1) ≥ 0.5 |

**Measurements.** Per rule, and per state group (first stage, "far"; final
stage, "near"; and pooled):
- the median gain;
- the fraction of states with gain > 0;
- the fraction admissible without halving;
- the regret against the best M (the oracle) at the same F, λ, control and
  gate.

Descriptive maps: the oracle M against state error and f_max, and gain
against |F|. Spearman correlations between the features and gain.

**Qualification for SC-025.** A rule qualifies if, pooled and under both
gates at λ=1e-3 with physical control, it meets both conditions:
- its median regret is at least 0.05 below the ladder's;
- its fraction of positive gain is at least the ladder's.

If no rule qualifies, the record states a negative for one-step conditional
band selection at this level, and SC-025 compares only the ladder with the
progress controller.

**Limits:**
- The states are those the fixed schedules visited.
- The labels are one-step and geometric.
- Data acceptance is not modelled; SC-024(b) measures it.

## SC-024 — nonlinear checks

**(a) Trajectory ablations of the shared backend.** SC-022's schedule, caps,
start and cases, with no atlas. The factors are:
- band rule: ladder, fixed32;
- backend variant:
  - V1 physical step control at 6 mm;
  - V2 refit gate at 1e-5;
  - V3 both.

That makes 18 new runs; the six SC-022 runs are the coefficient-clip / 1e-7
controls. The question is whether the C failure and the fixed-32 stalls come
from:
- (i) the gate freezing rough states — V2 recovers;
- (ii) oversized steps creating those states — V1 recovers;
- or both.

Records:
- symmetric RMS distance and Hausdorff at each stage end (evaluation);
- work units;
- refusal counts by reason;
- the tightest curvature radius along the trajectory.

**(b) Probes at recorded states.** Four states per SC-022 run (start, end of
stage 1, end of stage 2, final). At each, execute the step that every rule
proposes, plus the oracle M, under that stage's F, with λ=1e-3 and physical
control:
- production solves give the realized decrease against the predicted one;
- refined solves at N=1024 give the backend's acceptance verdict.

Budget ≤ 2,500 solves. This tests the local model on steps that were never
executed, which the review said the audit could not do.

## SC-025 — frozen minimal policy (declared now; run after the SC-023/024 decisions)

**Policy.** The qualifying rule, or none, chooses M inside SPD's cumulative
schedule, with F and the quotas unchanged. The backend variant is the one
SC-024(a) selects. It is applied to every arm alike.

**Arms:**
- ladder;
- fixed32;
- a progress controller: it starts on the ladder, and when a stage ends with
  `no_decreasing_step` and less than a 10% loss reduction, the next stage's M
  doubles, up to 48;
- the frozen policy;
- ablations of the policy, if it changes more than one factor.

**Cases.** The development cases first, then the held-out cases below. All
start from the legacy circle. Scores (evaluation only):
- the final symmetric RMS distance, Hausdorff and area error;
- the work units.

Generalization claims use the held-out cases only.

**Held-out cases**, declared 2026-09-24. They will not be generated or run
until the policy is frozen:

| ID | Truth (physical units, scene centre (0.5, 0.5)) |
|---|---|
| H1 kite | (x, y) = 0.025·(cos t + 0.65 cos 2t − 0.65, 1.5 sin t), rotated 0.5 rad, centred at (0.505, 0.497) |
| H2 peanut | r(t) = 0.05·(0.75 + 0.3 cos 2t), rotated 1.1 rad, centred at (0.497, 0.503) |
| H3 hook (non-star) | A thick arc like the C: centreline 36 mm, half-thickness 13 mm, half-angle 130°, rotated 2.4 rad, centred at (0.496, 0.506), smoothed to natural band 10 |

Their observations use SC-022's oracle and checks. K stays 192.
Representability at K is reported, and is not used to change K.

## Budget and records

- SC-023: ≤ 1 h on 24 processes.
- SC-024(a): SPD caps for each run (8012 units, 7200 s), 12 in parallel.
- SC-024(b): ≤ 2,500 solves.
- SC-025: 4 arms × 6 cases, under SPD caps.

Each experiment gets a fresh bundle with a manifest, source hashes, inputs,
configurations, per-run histories, evaluation files and a README. Failed
arms stay in the comparison.

## Amendment A1, 2026-09-24 — a post hoc rule from the SC-024(b) probes

**Observed, before this amendment** (SC-024 `probes/`, 110 executed
rule-chosen steps at 24 recorded states):
- The Gauss–Newton model predicts the realized decrease of steps that were
  never executed well: realized/predicted has median 1.04, and 85% lie
  within ±20%.
- **The data decrease of the step the backend would actually take ranks
  bands like the geometric gain.** Within a state it is positive in all 21
  states with at least three executed bands (median Spearman +1.0). By eye,
  its maximum sits at the oracle band at about 20 of the 22 states that
  have an oracle.
- SC-023's `predicted_fraction` is the model decrease of the *raw*
  conditional step, before step control and halving. It grows with the band
  by construction, which is why it ranked bands backwards (−0.27).

**The rule, labelled post hoc.** Call it `controlled`. At each decision it
chooses the band whose executed step, computed truth-free, has the largest
model decrease:
- the conditional LM step at λ;
- then the decision's step control (clip or physical 6 mm);
- then halving to the first trial the decision's refit gate admits
  (geometry only, as recorded in SC-023's `halving` column).

Ties go to the smaller band, and a band with no admissible halving
contributes 0. The step-control budget is what penalizes bands whose
direction spends displacement on weakly determined harmonics. A
trust-region reading of the same idea is standard: compare subspaces by the
model decrease each achieves within a physical step bound (Nocedal & Wright,
*Numerical Optimization*, ch. 4; Conn, Gould & Toint, *Trust-Region
Methods*, 2000).

**Evaluation, fixed now.**
- Compute the rule's feature for every SC-023 decision from the stored
  blocks and the recorded halvings. No new solves and no new trials.
- Apply the plan's SC-023 qualification gate unchanged. In addition, apply
  the same criteria under coefficient control with gate G2, the backend
  that SC-025 uses.
- The rule qualifies only if it passes both.

These are development data, and the probe states are among them, so a pass
is development evidence only.

**If it qualifies**, it is frozen as SC-025's `atlas` arm, with SC-025's
backend variant (coefficient clip, gate 1e-5, λ from the LM state):
- At each stage start, fresh P=48 cells at the stage's frequencies give G
  and g; they are charged to the ledger.
- The rule's feature is computed with the backend's own control and gate at
  λ = 1e-3.
- The arm runs on the development cases and then the held-out cases, with
  the other arms unchanged.

The held-out cases have not been generated or run with any arm when this
amendment is written.

## A1 outcome and Amendment A2, 2026-09-24 — parsimony, and the last development amendment

**A1 outcome, as declared: not qualified**
(`SC-023-conditional-candidates/amendment_a1.json`).

What went right:
- `controlled` has median regret ≈0 in every setting.
- Within a decision it orders bands correctly, with Spearman 0.84–0.97,
  positive in 96–97% of decisions.

What failed:
- Its mean gain is below the ladder's in the G2 settings (0.042 against
  0.118 with physical control; 0.072 against 0.146 with coefficient
  control).
- Its positive-gain fraction is lower under G2: 0.94 against 0.97–0.98.

The declared margin (0.05 below the ladder's median regret) also cannot be
met under G1, where the ladder's median regret is 0.005. That is a flaw of
the gate's design; it does not change the verdict.

**Where the tail comes from.** Under the SC-025 backend setting
(coefficient control, G2), 72 of 1,269 decisions lose more than 5%. All but
two are near-converged Borges wrong-circle or star states. There, many bands
drive the stage loss down by 99.8–100%, and the strict maximum picks a wide
band that fits the few stage frequencies while making the geometry 2–8×
worse. This is under-determination, the case that model-selection practice
handles with a parsimony tolerance (Hastie, Tibshirani & Friedman, *The
Elements of Statistical Learning*, §7.10, the one-standard-error rule).

**Rule A2, `parsimonious`: the smallest band whose controlled-step decrease
is at least 0.9 of the best band's.** The tolerance matches the knee rule's
0.9. The feature is A1's, unchanged.

**The gate is recalibrated for A2 only** (A1's verdict stands). A2
qualifies if, at λ=1e-3, in each of physical/G1, physical/G2 and
coefficient/G2, all three hold:
- (i) its median gain is at least the ladder's;
- (ii) its mean gain is at least the ladder's, which guards the tail;
- (iii) its positive-gain fraction is at least the ladder's minus 0.02.

**A2 is the last development amendment.** Whatever its verdict, SC-025
then runs its held-out cases:
- with the A2 rule as the `atlas` arm, if it qualifies;
- without an atlas arm, if it does not.

No further rule is tuned on these development data before the held-out
runs.
