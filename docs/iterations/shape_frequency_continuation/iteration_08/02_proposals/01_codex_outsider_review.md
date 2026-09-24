# Outsider review of the clean hybrid and trajectory atlas

2026-09-24. Codex review requested by the user, covering commits `9a52b50`
and `5b852c0`, SC-020/021/022, their code, plans and saved artifacts. This is
a separate review, not an implementation or a new recovery campaign. Numerical
measurements below are reproduced in the
[review audit](../../../../../results/validation/shape_continuation/review-20260924/audit.json)
by a [script](../../../../../results/validation/shape_continuation/review-20260924/audit.py)
that performs no physics solves. The targeted backend/atlas suite was rerun:
**12 tests passed**. Equations labelled as derivations are arguments made here;
they are not claims that a cited paper studies this particular hybrid.

## Verdict

**The architecture is in the right direction, and the atlas is now a useful
research instrument. The evidence supports a near-truth backend qualification
and a descriptive trajectory study, not a generally robust inverse or a
successful adaptive policy.** Keep Borges' update and the current hybrid as
the reference. The next scientific task is to identify which regularized,
physically scaled, conditional atlas quantities predict useful finite steps.

The strongest contribution so far is the separation of update, optimizer and
policy, together with the full off-diagonal atlas and retained failures.
The main weaknesses are interpretation of atlas steps as independent harmonic
recommendations, an overstrong meaning assigned to the signed-distance error
layer, and generalization from one near-truth SPD comparison. These are
addressable without replacing the pipeline.

## What I accept from the recorded evidence

| Finding | Review verdict |
|---|---|
| SC-020 passes its frozen SPD gates | Accept on the one 0.554-mm-error ellipse handoff. Passing the 1-mm gate is not accuracy parity: the M=16 endpoint is 0.0762 mm versus SPD's 0.0478 mm. |
| SC-021 improves that same handoff by changing M=16 to M=32 | Accept the measured 0.0088 mm, 150 versus 256 work units, and disappearance of rejected trials. This is a useful controlled development ablation, not a general M rule or a pure comparison of coordinate systems. |
| SC-022 retains six trajectories, including failures | Accept: 159 state records, 141 unique curves within runs and 2,679 computed cells. All twelve local NPZ files match their recorded hashes. |
| The atlas uses the backend's objective and coordinates | Strong implementation evidence: 32 first-trial steps replay to maximum relative difference `1.4895e-13`. This verifies consistency, not independent physical correctness. |
| The small-band ladder is better than fixed M=32 on these distant starts | Accept for these settings and three starts. It does not establish that a wide update space cannot work from distant starts under different regularization or step control. |

The review also reconstructs the model decrease of **all 135 accepted steps**
from the preceding state's stored blocks and the actual clipped/halved step.
Every predicted decrease is positive; actual/predicted gain ranges from
**0.926 to 1.767**. This is encouraging local-model evidence along accepted
steps. It is selected by acceptance and does not validate rejected directions,
newly opened bands, unvisited states or arbitrary steps from the atlas.

## 1. A full-space step component is not a recommendation to add that harmonic

[`atlas_survey.lm_step`](../../../../../experiments/shape_continuation/atlas_survey.py)
computes a joint solution over P=48, or 97 real coefficients. The p=15 entry
therefore depends on every other coordinate allowed in that solve. This is
why storing the full Gauss–Newton matrix was the correct design choice.

**Derivation.** Write the regularized quadratic matrix as `H = G + λD`,
partitioned into an existing coordinate set A and proposed additions B.
Eliminating A gives

```text
S_B = H_BB - H_BA H_AA^{-1} H_AB
q_B = -(S_B)^{-1} (g_B - H_BA H_AA^{-1} g_A).
```

The prediction is conditional on A, B, λ and the metric D. Removing other
coordinates changes the Schur complement and can change the sign of q_B.
Slicing B from a larger solved vector is generally a different operation.

**Saved-data counterexample.** At the final Borges-arm star state and
0.75 GHz, keeping the same `λ=9e-5`:

| Allowed coordinates | p=15 cosine with the stored error proxy | p=15 amplitude |
|---|---:|---:|
| All harmonics through 48 | +0.9522 | 0.4518 mm |
| Current band 0–9 plus the cosine/sine pair at 15 | −0.9983 | 1.3520 mm |
| Contiguous band 0–15 | +1.0000 | 0.5027 mm |

These are offline linear counterfactuals, not executed geometry updates or
recovery results. Nevertheless they directly refute an interpretation of the
full-space p=15 component as an independent “open p=15” instruction. The error
proxy is identical in all three rows, so its limitations do not explain the
sign reversal.

**Consequence:** test candidate bands or subspaces by resolving the conditional
model for each candidate. Treat the original p=15/p=20 observations as
descriptions of a particular joint solve, not properties of those harmonics
alone. For cumulative continuation, combine the weighted G and g blocks first;
an average of independently computed steps is not the joint step.

## 2. The LM atlas is already regularized, and its rank limits matter

There are 24 complex paired measurements per frequency. For real shape
coefficients this gives a Jacobian with 48 real rows and 97 columns:

```text
rank(J_k) <= 48,       dim ker(J_k) >= 49.
```

This is a dimension bound on the local inverse, not evidence that the forward
solve is defective. In audited first/final states the spectral ranks at a
relative G-eigenvalue threshold of `1e-10` range from 16 to 48. Multiple
frequencies can add independent information; their usefulness must be measured
in the stacked objective.

The stored step is **unclipped LM**, not “unregularized”: it solves
`(G+λ diag(max(diag(G),1)))q=-g`. Standard damped least squares and Tikhonov
regularization explicitly change which weakly determined components enter a
solution. See [Madsen–Nielsen–Tingleff, §3.2](https://www2.imm.dtu.dk/pubdb/edoc/imm3215.pdf)
and [Hansen, §§2.7.1–2.7.3](https://www2.imm.dtu.dk/~pcha/Regutools/RTv4manual.pdf).

**Derivation for this implementation.** With positive diagonal D, write
`J D^{-1/2}=U Σ V^T`. Then

```text
q = -D^{-1/2} V diag(σ_i / (σ_i²+λ)) U^T r.
```

Both the damping and coordinate scaling enter the plotted step. The live λ
was selected along a smaller-band cumulative trajectory; it is not separately
calibrated for every single-frequency, full-band counterfactual. Here it spans
`3.14e-15` to `31.38` on the Borges C trajectory. A change in the map can thus
come from optimizer history as well as the geometry and data.

**Consequence:** retain the raw layers, but label steps by their band, metric,
damping, truncation and clipping. Compare a declared range of regularization
settings or common physical step scales before interpreting an apparent
frequency “demand.” A relative cutoff on eigenvalues of G is a squared
singular-value cutoff; `1e-10` here corresponds to `1e-5` on J, not a calibrated
measurement-noise threshold. The current data normalization is not a measured
noise covariance, so visibility alone is not a noise-resolved admission rule.

## 3. The error layer is a distance proxy, not generally the required normal move

[`true_error`](../../../../../experiments/shape_continuation/atlas_survey.py)
projects negative signed closest-point distance to the target polygon onto
the current arclength harmonics. That is a meaningful evaluation diagnostic,
and it is kept out of the inverse. However, closest-point distance is measured
along the target's normal, not necessarily the current boundary's normal.
The concentric-circle unit test does not distinguish these directions.

The usual smoothness and closest-projection identities for signed distance
hold in a tubular neighborhood; see
[Esedoğlu–Ruuth–Tsai, §4.1, Proposition 1](https://steveruuth.org/wp-content/uploads/2020/10/ert.pdf).
They do not identify the normals of two different curves.

**Derivation.** Let d be the target signed distance, n the current normal,
and seek a small normal correction h at x. Wherever d is smooth,

```text
0 = d(x + h n) = d(x) + h ∇d(x)·n + O(h²),
h ≈ -d(x) / (∇d(x)·n).
```

The stored `-d(x)` is the first-order correction only when the normals are
sufficiently aligned. Near a smooth, close normal graph that approximation
can be appropriate. For a distant curve or a cavity there may be misaligned
normals, multiple normal intersections or no nearby intersection.

**Exact geometry check:** for SC-022's initial 65-mm circle offset by
(-20,20) mm from the 50-mm circle target, the proxy differs from the exact
normal-ray correction by **1.698 mm RMS / 3.144 mm maximum**. Applying the
proxy as a normal move leaves up to **2.655 mm** distance to the target;
the exact ray correction reaches it to roundoff. No BEM computation is used.

**Consequence:** call this the signed-distance error proxy. Keep its spectrum,
but qualify statements that a step “points at the truth,” particularly for
the distant starts and C. Use checked normal-ray correspondence or an actual
change in an external geometry error for stronger direction claims. SC-020's
ellipse report uses an actual normal-ray intersection, so this specific
criticism is of SC-022's layer, not that earlier implementation.

## 4. Coefficient bounds are not physical, band-independent step bounds

[`BorgesUpdate.measure`](../../../../../experiments/shape_continuation/updates.py)
exists, but the current
[`fit_stage`](../../../../../experiments/shape_continuation/lm_backend.py)
clips each coefficient and stops using its Euclidean norm; it does not call
`measure` to impose a physical RMS or maximum-normal bound. This was declared
in the SPD comparison, so it does not invalidate that contract. It is a gap
relative to the draft's intended physical-metric interface.

**Derivation.** For `h=a0+Σ(a_p cos(pθ)+b_p sin(pθ))` in normalized arclength,

```text
||h||_RMS² = a0² + 1/2 Σ_p(a_p²+b_p²).
```

Thus the mass matrix is `W=diag(1,1/2,...,1/2)`. Physical cosines use
`a^T W b / sqrt((a^T W a)(b^T W b))`. Per-pair amplitudes are useful, but a
whole-vector coefficient norm is not RMS displacement. The initial median
raw LM norms reported as 728/2316/595 mm become **515/1638/421 mm physical
RMS** for circle/star/C. They remain very large; the qualitative concern
survives the correction.

If each nonconstant coefficient is independently bounded by b, their combined
RMS can reach `b sqrt(M)` and their maximum can grow with the band. Moreover,
spatial derivatives multiply harmonic p by p and p². A fixed 6-mm coefficient
bound therefore changes both total permitted motion and roughness when M
changes. In SC-022, many proposals are refused before any data evaluation.

**Consequence:** describe the M=32 failures as failures under this specified
regularization, clipping and finite retry budget. They motivate studying
shape-space selection together with physically meaningful local step control;
they do not prove a universal far-start obstruction for M=32. Preserve the
current arm, and make any physical-bound or smoothness-penalty change a
separate shared-backend ablation, not an undocumented advantage for a policy.

## 5. An update band is a local tangent restriction, not a global spectral invariant

The SC-020/021 ablation strongly supports the practical importance of the
update-space mapping on that near-truth handoff. The wording “error beyond M
cannot be reached” is stronger than the evidence or geometry warrants.
Borges' construction adds a normal perturbation and reparametrizes the new
curve; see [§2.1, equations 10–12](https://arxiv.org/html/2210.11607v1#S2.SS1).
The next step's normal and arclength coordinate have changed.

**Derivation of mode mixing.** On a circle of radius R, take a small radial
normal move `h(θ)=ε cos(mθ)`. The new normalized arclength coordinate satisfies
`φ=θ+ε sin(mθ)/(mR)+O(ε²)`. Expressing the radial offset in φ gives

```text
h(φ) = ε cos(mφ) + ε²/(2R) [1-cos(2mφ)] + O(ε³).
```

Even this simple move generates a doubled harmonic in the new coordinate.
Repeated finite updates are not confined to the original tangent span.
Consequently the nearly unchanged >16 error in SC-020 is a measured local
plateau, not a theorem about permanent unreachability. Likewise SC-022's
high-index error identifies a hypothesis for band enlargement, not a proof
that enlargement alone will recover it.

## Numerical qualification and reproducibility still needed

- **Atlas refinement:** SC-022's tiny linear-system residuals certify the
  algebraic solves, not quadrature error in the 97 Jacobian columns. Oracle
  refinement at the truth and refinement of accepted training predictions are
  valuable but distinct. Representative early/stalled/cavity/high-frequency
  atlas cells still need derivative refinement and actual-update directional
  checks before making fine spectral or sign claims. Algebraically,
  `x-x_exact=A^{-1}(Ax-b)` already shows why a small solve residual alone
  does not control solution error, let alone discretization error.
- **Frozen source availability:** SC-022's recorded numerical source hashes
  match the current tree. SC-020/021 input hashes still match, but current
  `lm_backend.py` differs from their recorded source; SC-020's `spd_cases.py`
  also differs. This is a post-run reproduction limitation, not evidence of
  changes during those runs. Archive the exact measured source versions or
  supply a documented compatibility amendment; current hashes alone cannot
  reconstruct missing historical source text.
- **Dense artifacts:** all local atlas/error NPZ hashes match, but those files
  are not tracked in Git. Publish a durable, versioned artifact bundle before
  claiming another researcher can reproduce the offline analysis from the
  repository. Hashes establish integrity only when the files are available.
- **Development scope:** K=192 was selected after examining truth
  representability. That is a defensible shared development resolution, not
  a demonstration of truth-independent resolution selection. The dense
  frequency catalog and all truth-assisted diagnostics also become development
  information; reserve genuinely unused cases/data for the eventual policy
  evaluation.

## Recommended next scientific decision

Continue the atlas work, initially on the saved data. The useful question is:
**does conditional, physically scaled local information predict which data
and update subspace will produce a useful admissible step at lower cost?**

1. Correct the error-layer and metric labels, retain both descriptive and
   physically scaled summaries, and qualify the promising atlas cells.
2. Use the stored G/g blocks to compare conditional candidate bands and
   cumulative frequency sets across declared regularization settings. Replay
   predicted/actual gain for recorded steps using
   `pred=-g^T q-q^T G q/2`; this is the standard local-model assessment
   described in [Madsen–Nielsen–Tingleff, §2.4](https://www2.imm.dtu.dk/pubdb/edoc/imm3215.pdf).
   The new audit provides that replay for accepted steps, but cannot measure
   outcomes of unexecuted counterfactual steps.
3. Only then perform bounded nonlinear probes of the most discriminating
   choices and compare their predictions with realized decrease, geometry
   feasibility and independent recovery. Include failed probes and all costs.
4. Freeze a minimal policy and test it against the fixed ladder and a cheap
   progress-based controller, with frequency-only and band-only ablations,
   followed by untouched cases. Keep alternative geometry updates separate.

A heatmap, a standard damped inverse and a few successful reconstructions are
not yet a publishable adaptive-method result. A diagnostic that predicts when
to change the data/subspace, survives these qualifications and improves
cost–accuracy or recovery reliability would be a credible result. This review
does not establish novelty by literature search; the cited theory supports
the qualifications above, while novelty requires a separate focused review.
