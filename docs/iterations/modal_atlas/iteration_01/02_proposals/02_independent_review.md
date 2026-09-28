# Independent review of the modal-atlas research vision

2026-09-28. Reviewer: Claude (Opus 5.5), at the user's request to "think
independently: don't take the instructions as absolute truth". The subject is
[01_research_vision.md](01_research_vision.md), the user-supplied document of
the same date. This review is a record of what was checked, what I disagree
with, and why I chose MA-001 as the first experiment. The document itself is
kept unchanged.

## What was checked and holds

Each algebraic statement the vision labels an identity or a direct
consequence was rederived. None needs correcting:

| Section | Statement | Check |
|---|---|---|
| §5.2 | `D_pT = (D_pR)X + R A⁻¹[(D_pB) − (D_pA)X]` | Differentiate `AX = B`, `T = RX`. |
| §5.3 | `g = Re(J*r)`, `G = Re(J*J)` for real parameters | Standard. |
| §6 | `DF[h]_rs = Δ L Σ_{n+j+p=0} U_n V_j ĥ_p` | Exact to the finite-difference floor on the circle (`7.7e-9` at step `1e-6`; test `test_circle.py`). On noncircular BIE states see the [MA-001 results](../../iteration_02/01_results.md). |
| §7.3 | Fisher matrix `2Re[z*(D_pH)*C⁻¹(D_qH)z]` | Proper complex Gaussian model. |
| §7.4 | actual ≥ predicted − ‖r+Jη‖ε − ε²/2 | Expand `½‖r+Jη+E‖²`. |
| §8 | Trace-error bound on `DF[h]` | Cauchy–Schwarz on the §6 identity. |
| §8 | Schur-complement statement | Block elimination. |
| §9 | Unitary invariance of `J*J` and `J*r` | Direct. |

The four-way distinction (generated, accessible, computed, usable) and the
separation of `f`, `K`, `M` and `K_u` are sound and should be kept.

## Where I disagree or would sharpen the vision

**1. The trace-band remark in §6 is right but stops short of the useful statement.**
The vision says high opposing field orders can feed low shape orders, so
`K_u = M/2` is not sufficient. That is true, but the same identity also bounds
the effect. Let `U`, `V` be projected onto `|n| ≤ K`, and write `T_U(m)` for
the ℓ² tail beyond order `m`. Every omitted pair `(n, −p−n)` has *both* indices
beyond `K − |p|`. Therefore

```
|J_p − J_p^(K)| ≤ |Δ| L [ T_U(K) T_V(K−|p|) + T_U(K−|p|) T_V(K) ].
```

The truncation error is a *product* of two tails. When `|p| ≪ K`, the
sensitivity converges about twice as fast (in exponent) as either trace. For
exponentially decaying spectra, `T(K)T(K−p) ~ e^{−a(2K−p)}`. The band needed
for column `p` to tolerance `τ` is therefore about `K_tail(√τ) + p/2`. The
`p/2` slope the vision rejects is in fact the right slope, but it needs the
`√τ` trace offset added. (My first draft of this review said
`M + K_tail(√τ)`. That is a valid but loose sufficient condition, and MA-001
measured the sharper form.) High opposing orders matter only where *both*
fields actually carry energy there. This applies to projections of the
exact traces. A Galerkin solve at cutoff `K_u` adds the Schur feedback of §8,
which is a separate error that MA-001 does not measure.

**2. The frontier of observable shape harmonics is a field-bandwidth statement, and it is classical.**
By the same identity, `J_p` vanishes identically once `|p|` exceeds
`K_U + K_V`, the combined support of the two trace spectra. An exterior
illumination excites boundary orders up to about `k_e R`, plus an
`O((k_e R)^{1/3})` transition layer. Orders with `k_e R < |n| < k_i R` are
trapped and reached only by tunnelling. So the observable band is about
`2 k_e R + O((k_e R)^{1/3})`. This is the Born/Ewald `2k` limit of diffraction
tomography, restated on the boundary. It explains iteration 04's two
unexplained findings. The frontier grew as about `2.5k` because the fit window
`k ≤ 20` sits in the transition regime. The exterior wavenumber, not the
interior one, sets it. It also predicts that `frontier/k` is not constant and
falls toward 2. The atlas should present this as a known limit that it
measures, not as a discovery.

**3. The resonance mechanism in §7.2 is real and quantitatively exact. It does not apply to the current continuation benchmark.**
On the circle the pole-shift estimate holds with its constant. Near a trapped
pole `k*`, the 10%-linearization radius is `0.10–0.13 · |k − k*| / |k*|` for
Q from 54 to 78,000. Relative sensitivity rises 100–1000×. The
[MA-001 results](../../iteration_02/01_results.md) give the figures. But trapped
modes require `k_i > k_e`. The whole shape/frequency continuation campaign
(SC-013 onward, including the kite, C and peanut failures) uses contrast
`k_i²/k_e² = 0.5`. There the circle has no trapped band, and the horizon stays
at the smooth `≈ 0.10/k` law. The vision lists the failed kite, C and
high-contrast paths together as candidates for this explanation. The kite and
C paths should be removed from that list. Their finite-validity problem must
come from geometry and the update construction, not from resonance. The
resonance mechanism is a strong candidate for iteration 04's contrast-10
breakdown and for high-permittivity GPR targets.

**4. The internal operator atlas `D_p(A_f)_ij` (§5.1) is gauge-dependent and should be deprioritized.**
A tangential velocity or a reparametrization changes `A` and `D_pA` but not
`T`, `F` or `J`. Its cells therefore mix physics with the parametrization,
the same problem iteration 04 found for the non-circular harmonic axis. The
four-index object is also the largest of the three levels. I would build §5.2
and §6 first, and use §5.1 only to diagnose numerics in a fixed gauge.

**5. Decision value needs a prospective quantity, not more description.**
SC-043 showed that a richer diagnostic does not improve continuation by
itself. The modal structure does yield two quantities that are available
before a step, without truth or residual:

- the **data-supported band per frequency**, `K_U + K_V` from the current
  trace spectra. Harmonics released above it are not constrained by that
  frequency at all;
- the **resonance distance** `|k − k*|/|k*|` where trapped modes exist. It
  bounds the useful step length directly.

These are the candidates I would carry into a continuation test. Heatmaps of
pair contributions are not.

## Why MA-001 is the first experiment

MA-001 tests the one bridge the whole vision rests on (§6), on exact circle
solutions and on the qualified BIE states the campaign actually visited. It
measures what the bridge predicts: the frontier, the trace band that
sensitivities need, cancellation, and the pole horizon. It changes no solver,
default or continuation policy. Its [plan](../03_plan.md) records the scope.
