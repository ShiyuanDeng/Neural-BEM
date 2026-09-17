# LAU-001 — STRUCTURE_ONLY: derivative-aware retention works on both noncircular fixtures, but nothing converts it into work

**COMPLETE. Verdict: `STRUCTURE_ONLY`.**
Executed 2026-09-17 on `feature/ordered-boundary-nystrom` in the existing
checkout. Plan: [`docs/iterations/laurent/iteration_01/03_plan.md`](../../../../docs/iterations/laurent/iteration_01/03_plan.md).
Approved by the user on 2026-09-17 ("go"). Owner Claude; **self-review only** —
no independent reviewer was assigned. No production default, solver file or
prior result bundle was changed.

## The decision

Adaptive, derivative-aware retention of the native Laurent Müller operator's
desingularised remainder **does** preserve receiver fields, geometry
derivatives and the full-system residual at ≈30% retention on both noncircular
fixtures — but only once the trace dimension is refined past the point where
the uncompressed model itself has residual headroom, and **no measured cost
saving follows from it**. The single missing mechanism is a **sparse assembly
and solve that turns a retained fraction into arithmetic**; masking entries of a
matrix that is still built densely and factored densely saves nothing.

This authorises no prototype and no promotion. The one precisely named
unresolved diagnostic is in [§9](#9-single-next-decision).

## 1. What was compressed

Every nonidentity block of `CoefficientGeometry.assemble` is
`2π( S[m,−n] + Σ_ℓ L_ℓ·P[m−ℓ,ℓ−n] )` with `L_ℓ = −1/|ℓ|`, so the exact
identity / log-symbol / smooth split follows from linearity of `kernel_matrix`.
Reconstruction `identity + log + smooth` matched the assembled operator to
**`7.6e-17`–`1.2e-16`** relative on every case. Both split labels ran:

| Label | Protected `S_M` | Candidate pool `R_M` |
|---|---|---|
| `IDENTITY_ONLY` | the exact `I` blocks | log-symbol **and** smooth, every block |
| `VERIFIED_SINGULAR_SPLIT` | `I` plus the exact log-symbol convolution | the smooth polynomial lookup |

The brief's `SPLIT_UNAVAILABLE` contingency was not needed: the verified split
exists in the assembler and is exercised throughout. Results below are the
`VERIFIED_SINGULAR_SPLIT` arm; `IDENTITY_ONLY` is in
[`compression.csv`](compression.csv) and is uniformly worse, as expected.

## 2. Qualification (G1)

Fixed-material, equal-permeability, single-interface TMz; exterior `ε_r = 6`,
interior `ε_r = 3`, lossless. Anchor `a_ref = 36.52 mm` (star, equivalent-area).
Oracle: independent Kress at `N = 384`, checked at 256.

| Case | `k_out·a_ref` | `f` | `K_u` | `M` | `B` | oracle 256/384 | uncompressed data | uncompressed lifted residual |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| circle | 2 | 1.067 GHz | 16 | 33 | 96 | `8.9e-15` | `4.8e-14` | `1.3e-11` |
| circle | 5 | 2.667 GHz | 24 | 49 | 96 | `1.1e-13` | `7.5e-11` | `9.7e-12` |
| ellipse | 2 | 1.067 GHz | 16 | 33 | 96 | `3.7e-15` | `9.3e-15` | `5.8e-13` |
| ellipse | 5 | 2.667 GHz | 24 | 49 | 96 | `1.3e-13` | `6.2e-12` | `1.3e-12` |
| star | 2 | 1.067 GHz | **40** | 81 | 96 | `1.4e-14` | `1.4e-14` | **`3.4e-8`** |
| star | 5 | 2.667 GHz | **48** | 97 | 96 | `6.9e-14` | `4.3e-12` | **`4.6e-8`** |

**`k_out·a_ref = 10` (5.33 GHz) is `UNQUALIFIED` on all three fixtures**, exactly
as the plan's review predicted. With 28 Bessel terms the native forward is
catastrophically wrong (data error `0.92`–`1.9`); with 48 terms it improves to
`3.3e-5` / `9.6e-7` / `2.6e-7` and still never reaches the `1e-7` control gate at
any ladder cutoff up to `K_u = 56`. This is a **reference limitation of the
Bessel power series, not a compression failure**, and it is recorded as such.
Full ladder in [`reference_convergence.csv`](reference_convergence.csv).

The star's uncompressed lifted residual is `3.4e-8` — only **30× below the
`1e-6` gate**. That margin, not the retention rule, is what decides the star
below.

## 3. G1b — the analytic support bound holds, and is useless as a compression rule

If the `P` and `S` argument arrays vanish outside a `β` box then the block is
exactly zero outside `|m−n| ≤ 2β` (log part) and the `β` box (smooth part).
**The bound held on every block of every case: zero violations**, for both the
`(d, p*, log_order)` formula and the measured argument support. But the
resulting support is not small:

| Case | exact support fraction (smooth) | block fraction above `1e-12` | looseness |
|---|---:|---:|---:|
| circle @ ka2 | 0.574–0.669 | 0.021 | 27–32× |
| ellipse @ ka2 | 1.000 | 0.376–0.392 | 2.6× |
| star @ ka2 | 1.000 | 0.63–0.66 | 1.5× |

`ANALYTIC_SUPPORT` therefore retains **1.000** on both noncircular fixtures — no
compression at all. The structure in this operator is in the **magnitudes**, not
the support, so G1b took its designed branch and the full mask sweep ran.
[`structure.csv`](structure.csv), [`decay.csv`](decay.csv).

## 4. The decisive result: forward-only selection destroys derivatives

At matched retention and matched, full-level receiver accuracy:

| Case | frac | FORWARD data | FORWARD `D_vY` | DERIV-AWARE data | DERIV-AWARE `D_vY` |
|---|---:|---:|---:|---:|---:|
| ellipse @ ka2 | 0.30 | `9.3e-15` | **`3.06`** | `3.9e-12` | `2.2e-8` |
| ellipse @ ka5 | 0.30 | `6.2e-12` | **`3.23`** | `2.0e-9` | `2.7e-7` |
| ellipse @ ka5 | 0.50 | `6.2e-12` | **`6.05`** | `6.2e-12` | `3.3e-13` |
| star @ ka2 | 0.50 | `1.5e-14` | **`1.77`** | `3.7e-10` | `2.0e-7` |
| star @ ka5 | 0.50 | `4.3e-12` | **`7.64`** | `4.3e-10` | `1.5e-7` |

Magnitude-based retention of `R` reproduces the uncompressed receiver data to
`1e-12`–`1e-14` while getting the geometry derivative **160%–760% wrong**. The
mechanism is exactly the plan's `R(η)=η·H` control made physical: a shape
perturbation opens `|m−n| = k` couplings that are numerically absent from `R`
itself, so a forward-only mask never selects them and `Π_𝒮 D_vR` discards the
sensitivity. Derivative-aware selection recovers **5 to 13 orders of magnitude**
of derivative accuracy at the same retention and the same field accuracy.

**Answer to the brief's comparison question: on these cases derivative-aware
selection demonstrates a decisive advantage over forward-only selection.**

**The circle is the exception and is reported as a failure.** Both rules fail
there at every retention (`D_vY` error `0.92`–`8.0`), and at `ka5`
derivative-aware is *worse* than forward-only (`8.01` versus `3.37`). The
circle's remainder is nearly diagonal, so neither `R` nor the four training
derivatives carry any signal at the held-out mode-5 harmonic. A mask trained on
four directions is not validated for a fifth.

## 5. Gate outcomes

Lowest retention meeting **all** gates (receiver `1e-6`, lifted residual `1e-6`,
data directional derivative `1e-3` on training and held-out directions):

| Case | at its own qualified `K_u` | at doubled `K_u` |
|---|---|---|
| circle @ ka2 | 0.254 (`BAND` w4) — held-out derivative still fails | **fails** (held-out `1.21`) |
| circle @ ka5 | 0.175 (`BAND` w4) — held-out derivative still fails | **fails** (held-out `8.02`) |
| ellipse @ ka2 | **0.300** (`DERIVATIVE_AWARE`) | **0.300**, all gates |
| ellipse @ ka5 | **0.300** (`DERIVATIVE_AWARE`) | **0.300**, all gates |
| star @ ka2 | **1.000** — nothing passes below full | **0.300**, all gates (`K_u=80`) |
| star @ ka5 | **1.000** — nothing passes below full | **0.300**, all gates (`K_u=96`) |

The star's blocker at its own cutoff is the **lifted full-system residual**, not
the derivative: `DERIVATIVE_AWARE@0.50` reaches data `3.7e-10` and training
derivative `8.3e-10` but residual `8.9e-6`, against a gate of `1e-6` and an
uncompressed value of `3.4e-8`. This is BIE-002's warning reproduced on the
independently constructed operator: **a small receiver error alone would have
given a misleading success label.**

**Refinement stability is positive.** At doubled trace dimension both
noncircular fixtures pass every gate at 0.300 retention, and the star's residual
improves from `8.9e-6` to `4.4e-8` (0.30) and `9.1e-10` (0.50). The retained
fraction does not approach one under refinement; the absolute retained count
grows as the fixed fraction of a larger matrix. [`heldout.csv`](heldout.csv).

BIE-002's centered band reproduces its original negative result here: no band
meets the joint gates on the star at either size below `w32` (0.56–0.64
retention), and `w4`/`w8` fail data, residual and derivative together.

## 6. Derivative qualification (G2)

- **Entrywise `D_v A` versus centered differences** — the check that existed
  nowhere in the repository before this experiment. Worst error over all four
  training directions, per fixture at `ka2`: `7.2e-6 → 1.8e-6 → 4.5e-7` (circle),
  `4.5e-6 → 1.1e-6 → 2.8e-7` (ellipse), `4.6e-6 → 1.1e-6 → 2.9e-7` (star), across
  `h = 1e-3, 5e-4, 2.5e-4`. Clean second order, ratio 4.0 throughout, with a
  stable plateau. [`fd_convergence.csv`](fd_convergence.csv).
- **Frozen-mask objective tangent versus centered differences of the same
  frozen-mask objective**: **44/48 pass**. The four failures are all
  `ellipse@ka2, train_cm1_re`, at relative error `2.26e-3` against a `1e-3` gate.
  That direction's objective derivative is `−1.15e-19`, two orders below the
  other directions', so the comparison is finite-difference-truncation limited;
  the **`FULL` and `DERIVATIVE_AWARE@0.30` tangents are bit-identical there**,
  which shows it is not a compression effect. Recorded as a limitation, not a
  pass.
- Directions where the gradient vanishes by symmetry were decided by the
  plan's cancellation-aware absolute allowance, as designed, and are labelled
  `controlling_term = cancellation` in the CSV.
- The reciprocal/Hadamard path was **not** exercised as a compressed arm; see
  [§8](#8-limitations).

## 7. Cost — the part that does not work

**Coupling retention produced no measured saving.** Every mask requires all
dense entries of `R`, all four analytic `D_vR`, a dense mask construction and a
dense LU. Zeroing entries does not reduce dense factorisation cost, and no
sparse assembly is implemented. Any benefit is **unimplemented**.

The one arm that changes real work is `COEFFICIENT_WINDOW`, which is a different
mechanism — shrinking the coefficient budget `(B, terms)` the assembler runs on:

| Case | window | assembly | speedup | data error |
|---|---|---:|---:|---:|
| circle @ ka2 | `B 96→64`, terms `28→20` | 0.045 → 0.020 s | **2.18×** | `4.6e-14` |
| ellipse @ ka2 | `B 96→64`, terms `28→20` | 0.061 → 0.027 s | **2.28×** | `9.1e-15` |
| ellipse @ ka5 | `B 96→64`, terms 28 | 0.064 → 0.031 s | **2.03×** | `6.2e-12` |
| star @ ka2 | `B 96→80`, terms `28→20` | 0.187 → 0.121 s | **1.54×** | `1.3e-14` |
| star @ ka5 | — | — | — | no smaller window qualifies |

Reducing `terms` to 20 **breaks** at `ka5` (circle `9.2e-3`, ellipse `1.4e-5`,
star `3.3e-6`), so the term count is frequency-critical while the coefficient
window has genuine slack at the lower size. This quantifies the "excludes window
error" caveat the assembler's own source records.

**No end-to-end speed claim is made.** Against the recorded baseline the native
assembler remains far slower than accuracy-matched nodal Kress, and nothing here
changes that.

## 8. Limitations

1. **Self-review only.** No independent reviewer was assigned.
2. **`k_out·a_ref = 10` is unqualified**, so the intended high-electrical-size
   end of the sweep has no result in either direction.
3. **The projected-Nyström control `A_M^proj` was verified but not swept.** The
   square full-DFT equivalence is checked in `test_algebra.py` (receiver
   agreement and lifted residual both `<1e-10` at `N=128`, `K_u=63`); no
   compression arm was run on it, so **no statement is made about whether these
   retention rules transfer to the projected operator**. `A_M^proj` and the
   native `A_M` are different matrices.
4. **The reciprocal/Hadamard derivative was not run as a compressed arm.** The
   plan lists it as a separately labelled third arm; only the operator
   derivative path was compressed and measured.
5. **Four training and two held-out directions, one anchor per fixture, no
   noise, single-component, known topology, fixed lossless equal-permeability
   materials.** A mask built from four directions is not validated for arbitrary
   geometry derivatives — the circle result is the direct evidence.
6. `IDENTITY_ONLY` was run throughout but is not analysed in depth here; its
   rows are retained in `compression.csv`.
7. Timings are single-worker, single-thread, one repeat per configuration, on a
   loaded developer host. They are assembly-cost indications, **not** the plan's
   three-repeat alternating-order protocol, which was not run because no speed
   claim survived to need it.

## 9. Single next decision

**Do not build a hybrid assembler and do not promote anything.** The one
diagnostic worth naming: **measure whether a structured sparse assembly and
solve at the measured 0.30 retention beats the current dense native assembly at
matched field and derivative quality**, on the ellipse and star at
`k_out·a_ref = 2` and `5`, at the refined trace dimension where both qualify.
If it does not, coupling retention is closed for this operator and the
`COEFFICIENT_WINDOW` axis is the only Laurent assembly-cost lever with measured
evidence behind it.

## 10. Work and reproduction

| Resource | Used | Ceiling |
|---|---:|---:|
| Native assemblies | 153 | 500 |
| Factorisations | 483 | 1200 |
| RHS batches | 657 | 2500 |
| RHS columns | 11,592 | — |
| Numerical wall time | 31.3 s | 2700 s |
| Peak RSS | 0.74 GiB | 8 GiB |

`27/27` package tests pass; `30/30` of the imported `modal_muller_research`
suite still passes. Imported source hashes are in [`manifest.json`](manifest.json),
exact commands in [`commands.md`](commands.md), the API and scaling map in
[`audit.md`](audit.md), the self-review in [`review.md`](review.md).
