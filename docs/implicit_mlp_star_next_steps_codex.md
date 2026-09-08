# Codex task: diagnose and repair the remaining implicit-MLP star inverse

## Repository state

Work from:

- repository: `ShiyuanDeng/Neural-BEM`
- branch: `feature/ordered-boundary-nystrom`
- baseline head when this plan was written: `6496cd367541b404ee396a76acf48c03f383a318`

Read first:

- `docs/pipelines/implicit_mlp.md`
- `results/validation/implicit_mlp_adjoint/failure-audit-20260907/README.md`
- `results/validation/implicit_mlp_adjoint/repairs-20260907/README.md`
- `results/validation/implicit_mlp_adjoint/rerun-20260907/README.md`
- `results/validation/implicit_mlp_adjoint/rerun-20260907/star-bw96/summary.md`
- `run_sdf_inverse_comparison.py`
- `run_implicit_mlp_inverse.py`
- the existing Kress shape-derivative / geometry-pullback code

Do not rewrite working pieces just to make the new experiments convenient. Reuse the existing problem builders, target classes, geometry extraction, Method-B conversion, Kress forward/adjoint, parameter controllers, metrics, gates, and artifact conventions where possible.

---

## What is already established; do not re-debug these first

The 2026-09-07 audit and reruns established the following.

1. The old circle termination contained a false minimum-step line-search stall. The fallback has been repaired.
2. Star pretraining with global Eikonal weight `0.1` was biased because the proxy target was not a global SDF. The validated star default is now zero pretraining Eikonal weight.
3. Raw MLP contour / Method-B disagreement is now guarded explicitly.
4. Method-B Fourier bandwidth, not grid/sample refinement, was the conversion bottleneck. For the star, bandwidth 96 removes that bottleneck.
5. The remaining `star-bw96` failure is therefore not explained by conversion resolution:
   - 32 accepted updates;
   - final train relative L2 about `5.966e-1`;
   - final holdout relative L2 about `1.078`;
   - conversion error about `1.061e-4 m`, safely below the `0.2 mm` gate;
   - center error improves from about `28.3 mm` to `15.5 mm`;
   - mean-radius error improves from `10.0 mm` to `4.83 mm`;
   - five-lobe amplitude error worsens;
   - five-lobe phase/rotation error worsens.
6. The repository already contains two important controls:
   - a legacy known-shape-family five-parameter star inverse that succeeds;
   - a radial `K=5` continuation case that succeeds on its own recorded acquisition.

The missing experiment is a **matched observability/acquisition study**, followed by a matched continuation study. Do not infer from the old controls that the current 8-pair, 0.5/1.5-GHz neural acquisition is sufficient; the acquisitions and optimization spaces were not matched.

---

## Working hypothesis

Keep two bandwidths conceptually separate:

- **forward representation bandwidth**: how many Method-B Fourier modes are needed to represent the MLP zero contour accurately for Kress; this is already high (`K=96` for the repaired star study);
- **inverse information bandwidth**: which shape perturbations are actually visible in the measured fields at a given frequency/acquisition.

The current star result is consistent with low-order modes being observable while the five-lobe information is weak or poorly conditioned at the present training frequencies.

For the current target,

```text
r(theta) = 0.05 * (1 + 0.25*cos(5*theta))
background eps_r = 6
```

so a useful dimensionless diagnostic is approximately

```text
kR ≈ 1.28 at 0.5 GHz
kR ≈ 3.85 at 1.5 GHz
kR ≈ 5.13 at 2.0 GHz
kR ≈ 6.41 at 2.5 GHz
```

Do **not** encode `kR = mode number` as a theorem or hard cutoff. Use it only to motivate measuring mode observability directly.

---

# Phase 1 — modal and physical-parameter observability audit

This is the next task. Do it before another long neural inverse.

Create a diagnostic under a new directory such as

```text
results/validation/implicit_mlp_adjoint/observability-20260908/
```

and a reusable script in the most natural existing diagnostics location.

## 1A. Boundary-mode Jacobian

For a frozen star boundary, define smooth **normal perturbations** using arc length `s` and perimeter `L`:

```text
V_n,m,c(s) = cos(2*pi*m*s/L)
V_n,m,s(s) = sin(2*pi*m*s/L)
```

Use modes `m = 0..10` initially; there is only one constant mode at `m=0`.

Use the existing Kress shape-derivative machinery to obtain the complex measurement derivative for each perturbation. This is a **diagnostic probe basis only**. Do not make these Fourier modes the production geometry representation and do not fit the MLP to a prescribed boundary update.

Evaluate at least these geometries:

1. the analytic wrong initial star;
2. the exact target star;
3. the saved `star-bw96` final MLP checkpoint if it exists locally; if an ignored checkpoint is unavailable, skip this case cleanly and record that fact rather than reconstructing a fake substitute.

Use the same ring acquisition as the repaired neural study with 8 Tx/Rx pairs. Sweep at least

```text
0.25, 0.5, 1.0, 1.5, 2.0, 2.5 GHz
```

with the same materials as the production target.

For the forward geometry, keep the conversion demonstrably resolved. For the star, reuse the repaired high-resolution configuration (`bandwidth=96`, `grid=513`, `projected_samples=256`, `num_nodes>=194`) unless the analytic direct boundary path makes Method B unnecessary for this diagnostic. Do not silently compare derivatives from mismatched forward discretizations.

For each geometry/frequency, record:

- raw complex Jacobian column norm per cosine/sine mode;
- the same after the production residual normalization;
- singular values of the real-stacked Jacobian `[Re J; Im J]`;
- numerical effective rank under several declared relative thresholds, e.g. `1e-2`, `1e-3`, `1e-4` of `sigma_max`;
- condition numbers for retained subspaces;
- normalized column correlations / Gram matrix;
- especially the cosine/sine content around mode 5.

Do not claim that arc-length mode 5 is exactly identical to the radial star amplitude/phase parameters away from a circle. It is a local probe of comparable spatial complexity.

## 1B. Five-parameter physical Jacobian

Also measure the response Jacobian of the existing analytic star family with respect to its low-dimensional geometric controls. Use the same parameterization/controller already present in the repository rather than introducing another star model.

The relevant geometric directions are the existing star controls (center coordinates, mean radius, amplitude, rotation; preserve the repository's exact parameter conventions).

For each frequency, report:

- individual parameter-column norms;
- singular values/conditioning of the full physical Jacobian;
- correlations between amplitude/rotation and center/radius directions;
- how amplitude and rotation sensitivity changes with frequency.

This is the most direct test of whether 0.5/1.5 GHz actually contains enough local information to recover the five-lobe degrees of freedom.

## 1C. Derivative validation

Spot-check the new diagnostic derivatives with fresh central finite differences at selected frequencies/modes/parameters. Use several perturbation magnitudes and show a convergence window instead of choosing one epsilon that happens to agree.

The existing Kress derivative validation remains the foundation; this phase only verifies the new diagnostic assembly and normalization.

## Phase-1 artifacts

At minimum produce:

```text
README.md
metrics.json
modal_sensitivity.csv
physical_parameter_sensitivity.csv
singular_values.csv
```

and compact plots for:

- modal sensitivity vs frequency;
- physical amplitude/rotation sensitivity vs frequency;
- singular-value spectra vs frequency;
- optionally selected correlation matrices.

The README must state observations without forcing the expected hypothesis. If mode-5 information is already strong at 0.5/1.5 GHz, say so.

---

# Phase 2 — matched five-parameter star controls

Only after Phase 1 is working, run the existing known-shape-family star inverse under **the same acquisition and forward conversion resolution as the neural star**.

Reuse `run_sdf_inverse_comparison.py` with the existing `StarLevelSet2D`/parameter controller and Kress parameter-FD optimizer. Do not write a second low-dimensional optimizer unless the existing path genuinely cannot express the matched experiment.

Use:

```text
num_pairs = 8
Method-B bandwidth = 96
projected_samples = 256
grid_resolution = 513
num_nodes >= 194
same initial star as the neural run
same target and materials
```

Use one fixed holdout set across the new acquisition ablation so results are comparable. A reasonable new independent holdout is

```text
0.25, 1.0, 3.0 GHz
```

which leaves 0.5, 1.5, 2.0 and 2.5 GHz available for training experiments. Do not use holdout loss for line search, hyperparameter selection, or choosing the winning training band.

Run at least:

```text
P0: train = {0.5, 1.5} GHz          # matched current baseline
P1: train = {0.5, 2.0} GHz
P2: train = {0.5, 2.5} GHz
P3: train = {1.5, 2.5} GHz
P4: train = {0.5, 1.5, 2.5} GHz
```

Keep optimizer and work-budget settings declared and comparable.

The important outputs are not only field loss. Track the existing star shape errors after every accepted iterate:

- center;
- mean radius;
- lobe amplitude;
- lobe rotation/phase;
- maximum node-to-target distance;
- training and holdout relative L2.

### Decision after Phase 2

- If the five-parameter control **cannot** recover amplitude/rotation even with the higher frequencies, stop changing the MLP. The immediate problem is acquisition/local inverse geometry, not neural overparameterization.
- If the five-parameter control fails at `{0.5,1.5}` but succeeds when 2.0/2.5 GHz is included, the current star failure has a strong acquisition-frequency explanation.
- If the five-parameter control succeeds already at `{0.5,1.5}` but the MLP fails, the key remaining issue is the high-dimensional neural optimization/regularization.

Write this decision explicitly into the result README.

---

# Phase 3 — matched direct-MLP frequency ablation

Do this only for the one or two training sets that Phase 1/2 identify as genuinely informative.

Run the **existing production implicit-MLP adjoint unchanged** except for training frequencies. Keep:

- same SIREN architecture and seed;
- same repaired star pretraining policy;
- same `bandwidth=96` resolved conversion;
- same 8 Tx/Rx pairs;
- same optimizer settings and 60-update budget unless there is a documented reason to change them.

Do not add a new regularizer yet.

Primary success evidence is geometric:

1. lobe amplitude moves toward the target;
2. lobe phase moves toward the target;
3. center/radius do not catastrophically regress;
4. independent holdout improves;
5. conversion remains refinement-resolved.

A lower training loss alone is not success; the existing bad star run already demonstrates that.

---

# Phase 4 — recursive frequency continuation with the MLP still owning geometry

If higher-frequency information helps, implement the smallest possible recursive-linearization/continuation driver around the **existing direct MLP adjoint**.

Important: preserve the current ownership model.

```text
accepted MLP weights
 -> extraction / Method B
 -> Kress forward + adjoint
 -> reverse all the way into MLP weights
 -> accepted MLP weights
```

Do **not** insert the historical pattern

```text
boundary sensitivity -> prescribed boundary motion -> fit MLP to that curve
```

as a production update. Boundary Fourier modes in Phase 1 are diagnostics only.

## Default continuation experiment

Use a frequency path such as

```text
0.5 -> 1.0 -> 1.5 -> 2.0 -> 2.5 GHz
```

while reserving a separate holdout set for evaluation. At each stage:

1. start from the accepted MLP from the previous frequency;
2. build the objective only from the current stage frequency for the first implementation, matching classical recursive linearization as closely as practical;
3. run a declared per-stage update budget or until the normal production stop condition;
4. retain accepted MLP weights for the next stage;
5. record all shape and field metrics before and after each stage.

Reset optimizer moments between stages by default so the continuation variable is the geometry, not hidden Adam state. If preserving moments is easy, it may be a clearly labelled secondary ablation.

A cumulative-frequency variant can be tested later:

```text
{0.5}
{0.5,1.0}
{0.5,1.0,1.5}
...
```

but do not implement both before the basic sequential path is measured.

Produce a per-stage summary showing when the lobe amplitude/phase become observable and whether they begin moving correctly only after the higher-frequency stages.

---

# Phase 5 — only if the low-dimensional control succeeds but direct-MLP continuation still fails

At this point the problem is much more specifically **neural overparameterization / ill-conditioned optimization**.

The preferred next experiment is not a boundary-to-MLP fitting loop. Keep the MLP as the optimization variable and regularize in neural/data space.

## Candidate: damped / truncated Gauss-Newton in MLP weight space

There are only a small number of real data residuals compared with 8,577 SIREN weights. Assemble or apply the measurement Jacobian with respect to the MLP weights using the existing end-to-end Kress adjoint/pullback.

For a real-stacked residual `r` and Jacobian `J`, test the minimum-norm damped Gauss-Newton step

```text
delta_theta = -J^T (J J^T + lambda I)^(-1) r
```

or the equivalent TSVD/IRGN form.

This has several advantages for this repository:

- the update is still directly in MLP weights;
- no prescribed boundary velocity is fitted back into the SDF;
- the step lies in the data-informed span of `J^T` instead of arbitrary Adam directions;
- tiny singular directions can be damped/truncated explicitly;
- the residual dimension is small enough that a data-space solve may be practical even though the network has thousands of weights.

Before implementing a full optimizer, first make a diagnostic that reports the singular values of the real data-to-weight Jacobian at the initial star for one small acquisition. If obtaining individual response cotangents from the current adjoint API requires a large invasive rewrite, document that before proceeding.

Any Gauss-Newton/IRGN implementation must continue to use the existing actual-candidate extraction, conversion-fidelity guard, BEM solve, geometry validity checks and rollback contract. Do not accept a linearized step solely because the local quadratic model predicts improvement.

---

# What not to change in this study

Unless a new diagnostic disproves a previous result, do not spend this task on:

- Kress quadrature redesign;
- new singular-kernel treatment;
- Method-B grid/sample refinement at fixed bandwidth;
- relaxing the `0.2 mm` conversion guard to make runs continue;
- reverting the repaired line-search fallback;
- restoring the star pretraining Eikonal weight to `0.1`;
- enlarging the SIREN merely because the inverse is failing;
- topology changes or multi-object support;
- fitting the MLP to a boundary step generated by a separate explicit optimizer;
- choosing settings from holdout performance.

The point of this study is to isolate **information content, frequency continuation and high-dimensional neural conditioning**.

---

# Required experiment discipline

1. Preserve all historical result bundles. Use new output directories.
2. Record branch SHA, source hashes, CLI/configuration, random seed and exact frequency sets in every result bundle.
3. Keep independent observation generation (`nystrom_ref`) unchanged.
4. Keep training and holdout frequencies disjoint in every individual experiment.
5. Do not claim a continuous Hausdorff certificate from sampled contour distances.
6. Do not claim a root cause from one seed if the matched controls disagree; state the measured result narrowly.
7. Avoid committing huge per-weight trajectories. Track compact metrics/README/CSV summaries and follow the repository's existing ignore policy for large checkpoints/arrays.
8. Run the relevant existing inverse/adjoint tests after implementation and `git diff --check`. Do not weaken old tests or gates to make the new experiments pass.

---

# Suggested result structure

```text
results/validation/implicit_mlp_adjoint/observability-20260908/
  README.md
  metrics.json
  modal-jacobian/
  matched-parametric/
    p0-0p5-1p5/
    p1-0p5-2p0/
    p2-0p5-2p5/
    p3-1p5-2p5/
    p4-0p5-1p5-2p5/
  mlp-frequency-ablation/
  mlp-rla/
  neural-jacobian/          # only if Phase 5 is reached
```

The top-level README should end with a short decision table:

| Observation | Interpretation | Next action |
|---|---|---|
| Physical amplitude/phase Jacobian weak until high frequency | acquisition-frequency limited | use higher-frequency continuation |
| Matched five-param inverse fails even at higher frequency | inverse geometry/acquisition still insufficient | stop neural changes; study acquisition/multistart |
| Five-param succeeds, direct MLP fails | neural overparameterization/conditioning | continuation, then neural IRGN/TSVD |
| Direct MLP succeeds after higher-frequency continuation | missing continuation was dominant | qualify on more shapes/noise/seeds |
| MLP continuation fails but neural IRGN works | Adam/null-space motion was dominant | compare and qualify IRGN optimizer |

---

# Literature motivation for this plan

Use these as conceptual guidance, not as drop-in formulas with copied constants:

1. Carlos Borges, Manas Rachh, Leslie Greengard, **“On the robustness of inverse scattering for penetrable, homogeneous objects with complicated boundary,”** *Inverse Problems* 39 (2023) 035004, DOI `10.1088/1361-6420/acb2ec`.
   - Very close classical problem: known homogeneous penetrable obstacle, boundary unknown, recursive linearization / shape optimization.

2. Carlos Borges, Leslie Greengard, **“Inverse Obstacle Scattering in Two Dimensions with Multiple Frequency Data and Multiple Angles of Incidence,”** *SIAM Journal on Imaging Sciences* (2015), DOI `10.1137/140982787`.
   - Uses boundary band-limiting as physical regularization and multifrequency Newton-style reconstruction.

3. Carlos Borges, Manas Rachh, **“Multifrequency inverse obstacle scattering with unknown impedance boundary conditions using recursive linearization,”** *Advances in Computational Mathematics* 48 (2022), DOI `10.1007/s10444-021-09915-1`.
   - Explicitly uses band-limited shape updates and recursive frequency continuation; the authors' public `inverse-obstacle-scattering2d` code makes the number of update coefficients frequency dependent and supports high-frequency update filtering.

4. Thorsten Hohage, Frédérique Le Louër, **“A spectrally accurate method for the dielectric obstacle scattering problem and applications to the inverse problem,”** arXiv `2006.10830`.
   - Boundary-integral dielectric forward problem with iteratively regularized Gauss-Newton shape inversion.

5. Tin Vlašić et al., **“Implicit Neural Representation for Mesh-Free Inverse Obstacle Scattering,”** arXiv `2206.02027`.
   - Neural implicit SDF geometry + boundary-integral physics + autodiff; latent/generative restriction acts as inverse regularization. Relevant if the direct full-weight MLP remains too underdetermined after acquisition/continuation are fixed.

The immediate goal is **not** to reproduce these papers. It is to use their mature ideas to distinguish what is currently limiting this repository before adding another complex mechanism.

---

# Deliverable

Implement and run **Phase 1 first**. Then proceed through later phases only when the preceding result justifies them. A partial result with a clean diagnosis is preferable to implementing all five phases without evidence.

At the end, update the new result README with:

1. what was measured;
2. whether 0.5/1.5 GHz observes star amplitude/phase adequately;
3. whether higher frequencies fix the matched five-parameter control;
4. whether the same change fixes the direct MLP;
5. whether recursive continuation was necessary;
6. the smallest next code change justified by the measurements.
