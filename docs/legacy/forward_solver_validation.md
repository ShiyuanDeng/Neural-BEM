# IBIM forward solver: validation, a bug, and an assessment

> **Status: historical snapshot (2026-08-21).** “Current,” “next,” and
> repository-state claims below describe the project on that date. They are
> preserved as evidence, not current implementation guidance. See
> [`../current_architecture.md`](../current_architecture.md) for the live
> pipeline and [`../validation_change_log.md`](../validation_change_log.md)
> for subsequent measurements.

*2026-08-21 — validation of the rectangular-loop forward case against an exact reference solution, the parameter bug it uncovered, a decomposition of the residual error, and notes on the repository as a whole.*

---

## 1. Scope

This covers the **forward** solver only: `run_ibim_rectangular_scan_forward.py` and the `gpr_bem` code it exercises. The inverse loop (`run_ibim_circle_inverse_bscan.py`, `ibim_inverse.py`) and the adjoint (`ibim_tmz_adjoint.py`) were read but not validated — see §8.

Everything below was measured with an **analytic** circle SDF (`circle_signed_distance`), not `SirenSDF2D`. Geometry error is therefore not a variable in any of these numbers.

---

## 2. Summary

The repository contained exactly one stored result. It was produced with a parameter that was silently overridden inside the geometry code, which put the layer-potential trace evaluation 32× further off the surface than intended. Measured against an exact reference, the stored B-scan was wrong by a relative L2 error of **2.9 to 176** depending on frequency — roughly an order of magnitude in amplitude at the pulse centre frequency, not a few percent.

The cause was found, fixed in four places, and the result regenerated and re-validated. After the fix the solver reaches **0.10–0.15 relative L2** below ~3 GHz and degrades above it.

That residual 10–15% is not a tuning problem. It comes from a structural choice in how the boundary integral operators are assembled, and closing it requires redesigning that assembly rather than adjusting parameters. §6 and §7 quantify this.

The underlying reason a wrong result sat in `results/` undetected: **the forward script computes no error metric of any kind**, and the only accuracy check that existed anywhere in the repo ran at a different operating point from the pipeline (§8.2).

---

## 3. What existed before this work

| | status |
|---|---|
| `results/rectangular_loop_forward/` | 3 PNGs + `.npz`. The only stored result. Wrong (§4). |
| `results/rectangular_loop_forward_gpu_test/` | empty — CuPy is not installed |
| Inverse pipeline | **no saved results.** Never run to disk. |
| `run_ibim_geometry_demo.py` | no saved results |
| `notebooks/ibim_forward_pipeline.ipynb` | executed, 7 figures, real accuracy numbers — but at settings that differ substantially from the pipeline (§8.2) |
| `notebooks/ibim_5_step_forward.ipynb` | never executed, zero outputs |
| Stored metrics of any kind | none |

The `bembel`, `bempp-cl`, `ngbem`, `scuff-em`, `gprMax`, `bem_gradients/*` and `layered_Green_function/*` trees were **never used for comparison**. No first-party file imports them, none is built or installed, and all clones are pristine apart from three accidental diffs (a stray `Adjoint`→`bem_gradients` find-replace inside `bempp-cl`, two minified JS files in `Helios`, one `.gitignore` line in `strata`).

The six root-level `*_FDTD.npy` files (each `(6361, 62)`, i.e. gprMax B-scans) are **orphaned** — no file in the repo reads them.

---

## 4. The bug

### Mechanism

`_build_truth_boundary()` requests `merge_distance = 0.01`, and the run script passed `offset_distance = 0.04` — a sane-looking 4× that.

But `compress_implicit_boundary_band` (`gpr_bem/ibim_geometry.py:268-280`) halves `merge_scale` until the sample count reaches `target_min_samples = max(16, ceil(4*sqrt(band_N)))`. With 2477 band points that target is 200, so:

```
0.01 → 0.005 → 0.0025 → 0.00125     (3 halvings, 272 samples)
```

The **effective** merge distance is 8× smaller than requested. The offset was tuned against a number the code discarded, making it **32 × merge_distance** in reality — far outside the accuracy valley:

| offset / md | 0.5 | 1.0 | 1.5 | **2.0** | 3.0 | 4.0 | 8.0 | … | 32.0 |
|---|---|---|---|---|---|---|---|---|---|
| rel. L2 | 2.03 | 0.638 | 0.242 | **0.148** | 0.169 | 0.231 | 1.20 | | **9.15** |

### Impact on the stored result

| f (GHz) | 0.25 | 0.50 | 1.00 | 2.00 | **2.50** | 4.00 | 6.00 | 8.00 |
|---|---|---|---|---|---|---|---|---|
| as stored | 7.06 | 6.07 | 2.94 | 37.4 | **9.15** | 52.0 | 131 | 176 |
| after fix | 0.296 | 0.101 | 0.463 | 3.46 | **0.148** | 1.07 | 0.882 | 2.29 |

Before/after the regeneration:

| | before | after | ratio |
|---|---|---|---|
| peak \|Ez\| | 1.603e3 | 1.049e3 | 1.53 |
| rms \|Ez\|, full record | 1.736e2 | 9.196e1 | 1.89 |
| **rms \|Ez\|, gate t ≥ 2 ns** | **1.484e2** | **4.563e0** | **32.5** |

‖new−old‖/‖old‖ = 0.85, correlation 0.53.

The 32× collapse of the **late-time gate** is the whole story — that gate is the target signal, the part the inverse loop fits. Essentially all of it was numerical artifact. The early record barely changed because it is dominated by the analytic direct wave, which never passes through the BEM solve. **That is exactly why the bug was invisible**: the part of the B-scan that looks right was never being computed by the broken code.

By frequency band, |old|/|new| was 1.03, 1.00, 1.04, **2.02**, **4.66** for 0–0.5, 0.5–1.5, 1.5–3, 3–5, 5–8 GHz — the corruption was concentrated where the human eye checks least.

### Fixes applied

1. `gpr_bem/ibim_tmz_forward.py:767` — `_default_trace_offset_distance`, samples branch: `0.5 * merge_distance` → `2.0 * merge_distance`.
2. `gpr_bem/ibim_geometry.py:281` — `compress_implicit_boundary_band` now emits a `RuntimeWarning` when it overrides the requested `merge_distance`. **This is the important one.** It fires immediately on the real case and on six existing tests, showing how widely the trap was laid.
3. `run_ibim_rectangular_scan_forward.py` — offset derived as `2.0 * boundary.merge_distance` from the *built* boundary; `merge_distance` and `num_boundary_samples` now recorded in the `.npz`.
4. `gpr_bem/ibim_inverse.py:166` — smoke/benchmark config `offset_distance: 0.04` → `None`, resolved per-iteration. A fixed value cannot be correct there: the boundary is rebuilt every iteration as the SDF moves.

### Post-fix sanity check

The regenerated B-scan shows four hyperbolas, one per rectangle edge, apexes at the four closest-approach points. Arrival times are consistent with geometry (v = 1.2239e8 m/s, waveform delay 0.360 ns calibrated from the direct wave): near-edge apexes match the front-surface specular to 0.19 ns, inside the ~0.4 ns pulse width. Across all 240 positions the envelope maximum tracks a back-surface (wrap-around) prediction to a median 0.216 ns versus 1.418 ns for front-surface.

*Caveat:* the mode identification is not clean — front-surface wins at the near-edge apexes, back-surface on the loop median. This is a consistency check, not a proof.

---

## 5. The reference solution

### What it is

Not Lorenz–Mie (that is a plane wave on a sphere). It is the **separation-of-variables Fourier–Bessel series for a penetrable circular cylinder with a 2D line source**, TMz polarisation, with the source expanded onto cylindrical harmonics via Graf's addition theorem.

### Why it is valid here

Separation of variables requires a homogeneous isotropic exterior, a homogeneous isotropic interior, and a separable geometry. All three hold. **It does not require vacuum** — the background enters only through k₁ = ω√(μ₀ε₀εᵣ). It does not require losslessness either; it works with complex k (verified at σ = 0.01 S/m, k = 128.346 − 0.769j).

It would **not** be valid with an air–ground interface — that is the Sommerfeld half-space problem with no elementary closed form, which is presumably why `layered_Green_function/` exists in this repo. **The current scene has no ground surface** (verified: the kernel is the free-space `0.25j·H₀⁽¹⁾(k·r)` at `ibim_tmz_system.py:167`), so the reference is sound, but it dies the moment a surface is added.

It is an infinite series, not a finite closed form; convergence is geometric once n > k·a.

### Verification

| test | result |
|---|---|
| zero contrast (k₂ := k₁) → no scattering | max\|u\| = **0.000e+00** exactly |
| transmission conditions on Γ, 3 angles | \|[u]\| ≤ 3.1e-17, \|[∂u/∂n]\| ≤ 4.0e-15, vs \|u\| ≈ 0.19 |
| reciprocity u(rx←tx) = u(tx←rx) | 1.2e-15 |
| series convergence at 0.5 / 2.5 / 8 GHz | machine precision (1e-16), stable well past the adaptive `nmax` |
| complex k (lossy media) | finite, well-behaved |

**Known hazard:** terms overflow for n ≫ k·a (`hankel1(200, 6.42)` ≈ 1e300 → `nan`). The adaptive `nmax = 3k₁a + 40` stays safe at every frequency used, but a fixed large `nmax` would silently produce garbage.

### The strongest evidence

A completely independent discretisation converges *onto* the reference value. Uniform-node BEM at 0.5 GHz, refining N: **0.109 → 0.032 → 0.013 → 0.0056 → 0.0055**. Monotone over four octaves of N, agreeing to 0.5%. A wrong reference does not attract an independent method toward it like that.

---

## 6. Why the residual error

Four measured mechanisms, dominant in different bands, plus one (§6.5) found later by
code reading and measured afterwards — with a different answer than this section
predicted. §6.4 turned out to be the dominant one and is now fixed; see §6.5 and
`validation_change_log.md`.

### 6.1 The offset is itself an approximation — binds above ~2.5 GHz

Layer potentials jump across Γ. The code obtains the trace by evaluating at ±d along the normal rather than taking the limit, so there is a consistency error ~ O(k·d).

d cannot be shrunk, because the quadrature is a plain weighted sum with **no singularity correction** — the near-singular kernel is handled *only* by standing off. Below the point spacing h it explodes:

| f (GHz) | d=1h | d=2h | d=4h | d=8h |
|---|---|---|---|---|
| 0.50 | 2.435 | **0.161** | 0.098 | 0.347 |
| 1.50 | 0.725 | **0.245** | 0.624 | 1.821 |
| 2.50 | 0.705 | **0.153** | 0.205 | 3.885 |

So d ≈ 2h is forced from below, and k·d = 2kh grows with frequency: 0.059, 0.178, 0.296, 0.474, **0.949** at 0.5 / 1.5 / 2.5 / 4 / 8 GHz. At 8 GHz the stand-off is a sixth of a wavelength.

**The bind: d ≫ h for the quadrature, d ≪ λ for consistency. That requires h ≪ λ**, i.e. many points per wavelength — which the compression step actively works against.

### 6.2 Node irregularity — sets the floor below ~1 GHz only

Boundary points are Cartesian grid points projected onto Γ and binned. They are not arclength nodes:

| grid | N | mean gap | min gap | max gap | max/min | **std/mean** |
|---|---|---|---|---|---|---|
| 129 | 104 | 0.00302 | 0.00160 | 0.00603 | 3.8 | 0.375 |
| 257 | 272 | 0.00115 | 0.00045 | 0.00297 | 6.6 | 0.392 |
| 385 | 320 | 0.00098 | 0.00047 | 0.00181 | 3.9 | 0.281 |
| 513 | 560 | 0.00056 | 0.00027 | 0.00147 | 5.5 | 0.318 |
| 641 | 592 | 0.00053 | 0.00009 | 0.00135 | **15.0** | 0.316 |

Spacing scatter is 28–39% **at every resolution — it does not improve under refinement.** A single global d is simultaneously too small for the tight clusters and too large for the sparse stretches. This is also the "4-fold Cartesian symmetry ripple" the notebook observed.

### 6.3 The 2.0 GHz spike is not a solver failure

| f (GHz) | \|exact\| mean | err N=272 | err N=592 |
|---|---|---|---|
| 1.80 | 2.82e-3 | 0.530 | 0.264 |
| **2.00** | **7.85e-4** | **3.134** | **1.379** |
| 2.30 | 3.79e-3 | 0.353 | 0.175 |

The **true** scattered field has a near-null at 2.0 GHz — destructive interference between front- and back-surface returns off a fast (εᵢₙ < εₒᵤₜ) inclusion. Relative error divides by that, so it inflates ~5×; absolute error is roughly flat. It halves cleanly under refinement, i.e. converges normally. `cond(A)` is flat (9.65e10 → 9.81e10) straight through the peak, and the nearest interior Dirichlet eigenvalue is at 2.111 GHz, not 2.000. **It is a normalisation artifact, not a resonance.**

### 6.4 Conditioning — alarming, currently harmless

The system **sums** exterior and interior blocks (`ibim_tmz_system.py:111-116`) where Müller requires the difference, so the hypersingular term doubles instead of cancelling. The solver then forms `A²q = Ab` (`:223`):

| f (GHz) | cond(A) | cond(A²) | ‖q_A² − q_A‖/‖q_A‖ |
|---|---|---|---|
| 0.50 | 9.44e10 | 8.92e21 | **4.8e-5** |
| 2.50 | 9.87e10 | 9.73e21 | 6.0e-5 |
| 8.00 | 3.56e11 | 1.27e23 | 2.0e-5 |

cond(A²) is ~1e22, far past float64 — but measured damage is **5e-5**, not the ~2% the notebook estimated. The physical RHS does not excite the ill-conditioned subspace. A real latent hazard (a different RHS, or float32, could expose it), not the present error source.

### 6.5 Not measured: `K'` and `T` are finite differences

Found by code reading after this report was written, so it carries no measurement here.
`build_implicit_adjoint_double_layer_boundary_matrix` and
`build_implicit_hypersingular_boundary_matrix` do not assemble their own kernels. They
finite-difference the single- and double-layer potentials along the normal, sampling at
1x, 2x and 3x the offset on each side (`ibim_tmz_forward.py:342`, `:402`, `:813`). The
stencil is a correct second-order one-sided extrapolation, but it amplifies quadrature
error by ~8/d, draws its third sample from ~6.5 node spacings out where the stand-off
error is already order one (see the table in 6.1), and prevents the Muller
cancellation of 4.4 from ever being expressed analytically. See section 4b of
`ibim_error_mitigation_literature_codex.md`.

**Measured 2026-08-24 — two of those three claims did not survive.** Replacing the
finite difference with analytic normal-derivative kernels is worth a real but modest
1.4-2.4x once each scheme is given its own optimal stand-off. The `8/d` noise argument
is arithmetically right and never binding: under a second-kind formulation the finite
difference stays well behaved down to a sixteenth of the historical stand-off. And it
does *not* block the Muller cancellation — Muller was implemented with these blocks
left as finite differences and produced the entire order-of-magnitude win on its own.
This subsection was written from code reading, and code reading got the attribution
wrong in the same way §10 records for the earlier round. See
`validation_change_log.md`.

### 6.6 Ruled out

Three plausible-sounding causes that measured out as innocent:

- **`band_half_width = 0.06 > R`.** Error is flat across bhw = 0.04 / 0.06 / 0.08 (0.1487 / 0.1477 / 0.1467) once the offset is sane. Compression collapses the wide band back onto Γ. *But see §8.4* — it is not harmless for the volumetric path.
- **float32 in the inverse loop.** 7.703 vs 7.722 at float64 on the same boundary.
- **The `A²` solve.** 5e-5, per §6.4.

---

## 7. The isolation experiment

To separate §6.1 from §6.2 — same solver, same offset rule, same N, only node placement changed:

| f (GHz) | N | IBIM (irregular) | uniform arclength | gain |
|---|---|---|---|---|
| 0.50 | 272 | 0.161 | 0.032 | **5.1×** |
| 0.50 | 560 | 0.184 | 0.011 | **16.4×** |
| **2.50** | 272 | 0.153 | 0.144 | **1.1×** |
| 2.50 | 560 | 0.139 | 0.107 | 1.3× |
| 8.00 | 272 | 2.281 | 2.238 | 1.0× |

Uniform nodes buy 16× at 0.5 GHz and **essentially nothing at 2.5 GHz** — the pulse centre frequency, the band that carries the B-scan.

With perfect uniform nodes and nothing else changed:

| N | 0.5 GHz | 2.5 GHz | 8.0 GHz |
|---|---|---|---|
| 128 | 0.109 | 0.226 | 2.471 |
| 272 | 0.032 | 0.144 | 2.238 |
| 512 | 0.013 | 0.113 | 0.798 |
| 1024 | 0.006 | 0.072 | 1.121 |
| 2048 | 0.006 | **0.041** | 0.844 |

At 2.5 GHz error tracks k·d almost exactly (k·d = 0.157, 0.079, 0.039 against errors 0.113, 0.072, 0.041) — first-order in the stand-off, confirming §6.1. Since d is tied to node spacing, accuracy costs nodes linearly: **1% at 2.5 GHz needs ~8000 nodes on a 5 cm circle**, in a dense O(N²) assembly solved O(N³), per frequency, per iteration. Prohibitive.

**Conclusion: arclength resampling is not worth doing.** It would be real work in the gradient path, carry real risk to `ibim_tmz_adjoint.py`, and deliver ~10% at the operating frequency. This experiment killed a fix that was about to be built.

8 GHz does not converge even with perfect nodes (0.80 → 1.12 → 0.84). **Unexplained.**

---

## 8. Assessment of the repository

### 8.1 The core method is sound; the assembly is the weak point

The level-set representation works. Geometry extraction is essentially exact — `sum(w)` reproduces the true perimeter to **1.8e-6**, projected points sit on the analytic circle to 6.9e-17, normals are exact. The differentiable-geometry design is coherent and is the right idea.

What is weak is one layer above: the singular kernel is never actually handled. Not by volumetric averaging, not by singularity subtraction — only by a single global stand-off applied to a node set whose local spacing varies 15×. Everything in §6 follows from that one choice.

### 8.2 No metrics — this is the root cause of the whole episode

`run_ibim_rectangular_scan_forward.py` computes **no error metric**. It writes a B-scan and three figures.

`compute_bscan_quality_metrics` exists and is decent (`relative_error_all/gate`, `correlation_all/gate`, plus geometry diagnostics), but it is used only by the inverse loop and compares predicted against a "truth" B-scan **generated by the same solver** — self-consistency, not accuracy. It cannot detect a systematically wrong forward operator, which is exactly what was wrong.

The only external-reference check that existed was in the notebook, and it ran at a different operating point: ±3R box vs full domain, 161² vs 257², default band half-width (≈4.7 mm) vs 0.06 m, single frequency at 0.5 GHz vs 385 frequencies centred at 2.5 GHz, offset 2×md vs the hard-coded 0.04, strict quadrature off vs on. Its headline number (0.0915) was therefore never a statement about the pipeline. The notebook is honest about this in its "natural next steps" — swap in `SirenSDF2D`, go multi-frequency, exercise the adjoint — none of which had been done.

### 8.3 Validation cannot currently reach the shapes that matter

The reference solution exists only for the circle. Everything measured here validates the solver **on a circle with an analytic SDF**. It says nothing about the SIREN-parameterised shapes the inverse loop produces, where no reference exists. This is not one more test frequency away — it needs a manufactured solution or a convergence-under-refinement study on a non-circular shape.

### 8.4 The volumetric path is non-functional

`solve_ibim_tmz_total_field_batch` nominally accepts a raw `ImplicitBoundaryBand2D`, which would be the volumetric quadrature that IBIM's theory actually relies on. It fails at every configuration tried, because many grid points project onto the *same* surface point:

| band half-width | N | nearest-neighbour distance between distinct projected points | pairs < 1e-10 |
|---|---|---|---|
| 0.01 | 416 | min 0, median 4.3e-4 | 64 |
| 0.03 | 1224 | min 0, median **5.6e-17** | 624 |

The band's own quadrature nodes are mutually coincident, so `_validate_non_singular_distance` always trips. Only the compressed surface path runs.

Separately, at the pipeline's `band_half_width = 0.06` the band reaches **past the circle's centre**, where ∇φ is undefined: exactly one point projects 0.05 off the surface. Compression bins that garbage away, which is why §6.6 finds it harmless in practice — but it is wrong in principle and the volumetric path would have no such protection.

*I could not determine whether this path is unfinished or abandoned. It is not documented either way.*

### 8.5 Repository hygiene

- **`.git` is broken** — the directory exists but `git status` returns *"not a repository"*. There is no history. Nothing in this report could be cross-checked against past intent, and the fixes described here are not version-controlled.
- **Seven vendored solver trees** (~several hundred MB) that nothing imports, none of them built (§3). They read as a reading pile, not dependencies.
- **Six orphaned FDTD `.npy` files** at the repo root — real gprMax B-scans, matching `gprMax/user_models/cylinder_Bscan_GSSI_1500.in`, that no code reads.
- **Dead config fields.** `ABC_TYPE`, `NUM_BOUNDARY_ELEMENTS`, `SCAN_START/END/STEP` are FDTD/legacy leftovers that `gpr_bem` never reads. `ABC_TYPE = 'first_order'` in particular invites the reader to believe there is an absorbing boundary; there is not — the formulation is a free-space BIE.
- **CuPy is not installed**, so `--device cuda` raises. This is why `results/rectangular_loop_forward_gpu_test/` is empty.
- **Test suite: 53 passed, 2 skipped, 1 failed.** The failure (`test_prepare_ibim_bscan_adjoint_context_matches_frequency_directional_derivative`) is **pre-existing, not a regression**: a central-difference check with a 1e-6 tolerance returning 3.50e-6 on the old code and 2.31e-6 after the fixes. The tolerance is too tight for a `step=1e-8` FD on that loss.

### 8.6 What is genuinely good

The geometry code is careful and its accuracy is excellent. The band/compression/projection machinery is clean. The notebook is unusually honest — it went looking for its own faults, found two real ones, and stated them plainly rather than presenting a success. The `.npz` bundles are well-structured. The inverse loop's metric and staging scaffolding is thoughtfully built; it has simply never been run against anything that could falsify it.

---

## 9. Recommendations

**Priority 1 — make wrongness visible.**
1. Add a Mie regression test to the suite: analytic circle, 2–3 frequencies, assert rel. L2 below a threshold. Roughly 40 lines, and it would have caught this bug the day it was introduced.
2. Have the forward script print and store an accuracy metric whenever the target is a circle.
3. Fix `.git` and commit. Nothing here is recoverable otherwise.

**Priority 2 — decide the assembly question.**
4. Build a standalone Kress–Nyström solver for this transmission problem (~150 lines, no repo integration) and compare against the reference. If it reaches ~1e-8 at 2.5 GHz with 272 nodes, the redesign is justified and quantified; if it stalls, the problem is elsewhere and a rewrite is avoided. **This is the single highest-value next experiment.**
5. Do not pursue arclength resampling (§7).

**Priority 3 — close the gaps.**
6. Run the inverse pipeline and store results. It has never produced a saved artifact.
7. Resolve the 8 GHz non-convergence (§7).
8. Decide the fate of the volumetric band path (§8.4) — finish it or delete it.
9. Loosen the FD tolerance in the failing adjoint test, or increase its step.
10. Delete or document the dead config fields, the orphaned `.npy` files, and the unused vendored trees.

---

## 10. Where I was wrong

Recorded because the corrections are informative:

- I flagged **`band_half_width = 0.06 > R`** as likely serious. It is harmless for the path in use (§6.6).
- I flagged **float32** in the inverse loop as a likely error source. It contributes ~0.2%.
- I called the **2.0 GHz spike** a probable spurious resonance. It is a null in the true solution (§6.3).
- I attributed the error floor to **node irregularity**. True below 1 GHz, false at the operating frequency (§7). I was one step from implementing a fix that would have delivered ~10% for substantial risk.
- I repeated the notebook's claim that the **`A²` solve loses ~2%**. It loses 5e-5 (§6.4).

The pattern is consistent: every mechanism that *sounded* alarming was benign, and the one that mattered was an unremarkable-looking hard-coded constant. That is an argument for measuring rather than reasoning about numerical error — and for the regression test in §9.1.

---

## 11. Open questions

1. Why does 8 GHz fail to converge even with uniform nodes?
2. Is the volumetric band path unfinished or abandoned?
3. ~~Was the operator **sum** at `ibim_tmz_system.py:111-116` intended as Müller? If so it is a sign error; if not, what formulation is it?~~ **Answered 2026-08-24.** It was neither Müller nor a sign error: it is the *difference* of the exterior and interior Calderón systems, which is internally consistent and correctly signed, but first-kind — the identity terms annihilate and every block becomes a sum. Müller is the *sum* of the two systems. `gpr_bem_mod` now implements both behind `formulation={"muller", "difference"}` and defaults to `muller`; `cond(A)` at 2.5 GHz falls from 1.5e11 to 1.7e4 and the scattered-field error by 29-1020x. `gpr_bem_ref` keeps the original. See `validation_change_log.md`.
4. How can non-circular shapes be validated at all?
5. Is the scene meant to acquire an air–ground interface? If so the reference solution used here stops being valid and `layered_Green_function/` becomes load-bearing.

---

## Appendix — the scene

2D TMz electromagnetic transmission problem. Dielectric cylinder in an **infinite homogeneous sand full-space** — free-space Hankel Green's function, no air layer, no ground interface, no ABC, despite the GPR framing.

| | exterior (sand) | interior (plastic) |
|---|---|---|
| εr | 6.0 | 3.0 |
| σ | 0.0 S/m | 0.0 S/m |
| μr | 1.0 | 1.0 |
| n = √εr | 2.4495 | 1.7321 |
| v = c₀/n | 1.2239e8 m/s | 1.7309e8 m/s |

Lossless, non-magnetic, k purely real. Contrast εᵢₙ/εₒᵤₜ = 0.5 — a *fast* inclusion.

- **Target**: circle, centre (0.5, 0.5), R = 0.05 m, perimeter 0.31416 m
- **Acquisition**: 240 bistatic Tx/Rx pairs on a rectangular loop, x ∈ [0.24, 0.76], y ∈ [0.32, 0.68], 60 per edge, Tx–Rx separation 0.06 m. Standoff 0.18 m (edge midpoints) to 0.316 m (corners).
- **Source**: gprMax Gaussian, 2.5 GHz centre, 385 frequencies over 5 MHz–8 GHz, 15 ns / 301 samples, 2 ns gate
- **Discretisation**: 257² grid, band half-width 0.06, delta half-width 0.03 → 2477 band points → **272 boundary samples**, effective merge distance 0.00125 m, float64, strict quadrature

Per-frequency scales:

| f (GHz) | k_out | k_in | λ_out (m) | λ_in (m) | k·R | perim/λ | pts/λ |
|---|---|---|---|---|---|---|---|
| 0.50 | 25.67 | 18.15 | 0.2448 | 0.3462 | 1.28 | 1.28 | 211.9 |
| 2.50 | 128.34 | 90.75 | 0.0490 | 0.0692 | 6.42 | 6.42 | 42.4 |
| 4.00 | 205.35 | 145.20 | 0.0306 | 0.0433 | 10.27 | 10.27 | 26.5 |
| 8.00 | 410.70 | 290.41 | 0.0153 | 0.0216 | 20.54 | 20.54 | 13.2 |

Validation runs used every 8th scan position (30 Tx/Rx pairs) and unit source strength; relative error is strength-invariant.
