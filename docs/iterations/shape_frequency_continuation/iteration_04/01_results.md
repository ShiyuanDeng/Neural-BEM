# Iteration 04 — measuring the frequency/shape interaction, and what it buys

Opened 2026-09-23 by [SC-015](../../../../results/validation/shape_continuation/SC-015-atlas-structure/README.md),
[SC-016](../../../../results/validation/shape_continuation/SC-016-validity-horizon/README.md)
and [SC-017](../../../../results/validation/shape_continuation/SC-017-atlas-controller/README.md).
[Track handoff](../README.md).

## What opened this cycle

Iteration 03 closed with the optimizer repaired and Figure 1 reproduction still
provisional, and named no numerical follow-up as executed. The user then
supplied a literature review of the proposed "atlas" direction
([local PDF](../Atlas-Driven%20Adaptive%20Continuation%20in%20Inverse%20Scattering_%20Literature%20Review%20and%20Pre-Coding%20Reading%20M.pdf),
ChatGPT Deep Research, cutoff 2026-09-23). Its operative conclusions were that
no verified paper builds a trajectory-dependent frequency-by-shape-harmonic
characterization for a penetrable boundary that keeps **signed** and
**off-diagonal** information and then adapts both the data and the model space
from it; that the three candidate meanings of an atlas cell (visibility,
residual alignment, curvature) are not interchangeable; and that the decisive
unresolved question is whether such a local characterization predicts
**nonlinear** usefulness at all.

This cycle takes those as the experiment design. It measures, at fixed
geometries, what each frequency says about each shape harmonic; it measures
where that statement stops being true; and it tests whether driving
continuation from those measurements beats the fixed ladder at a matched
forward-solve budget.

## Result

### 1. The circle's selection rule is exact, and it is exactly what fails elsewhere

Rotational equivariance plus the Hadamard formula force each Jacobian column of
a centred circle onto the single data-mode line `a + b = p`, and force the
resulting order table `V(a,b)` to be **exactly rank one**, `A_a B_b`. This holds
at any contrast and any receiver radius and is checked as a unit test at
contrast 6 and 10 and receiver radii 10 and 400 (second singular value below
`1e-8` of the first). Ammari–Chow–Zou's `J_n(kR)J_m(kR)h(n-m)` is the
weak-scattering far-field limit of that statement, reproduced to within 8%.

That is a stronger circle result than the review's closest analytical
precedent, and it is the reason a circle-derived selection rule cannot be
exported. Measured on real geometries, the energy a column keeps on that line
is **52.5x** the unstructured share on the circle — the maximum possible — and
**2.2–2.7x** at the glider truth and at a mid-inversion iterate. The same point
appears in the off-diagonal: on a circle the Gauss–Newton block is diagonal in
the arclength harmonics, so the number of harmonics the diagonal calls
detectable equals the number of directions the spectrum determines, *exactly*.
At a real iterate the diagonal over-reports by a median of 1.21x and up to
2.13x. **The circle is the one geometry where a frequency-by-harmonic heatmap
loses nothing**, which is precisely why intuition calibrated on it misleads.

### 2. The band rule is measurable, and the manuscript's is right for the wrong reason

Detectability — the highest harmonic an RMS normal displacement of `1e-2`
moves above one noise unit — grows as **2.53k** at contrast 0.33 and **2.92k**
at contrast 10, against §4's `3 max(k, ki)`. Raising the contrast by 30x moves
the frontier by 1.15x where `sqrt(contrast)` predicts 3.16x, so **the exterior
wavenumber sets the recoverable band and the interior one does not**. Holding
the acquisition fixed at 64 channels instead of `floor(10k)` moves the frontier
by under 5%, so this is physics rather than acquisition growth.

Separately, the **linearization horizon** — the largest RMS normal displacement
at which `J h` still describes the measured change in the data to 10% — is
`0.12/k`, with a fitted exponent of −0.97 and agreement to three digits at
double quadrature. In wavelengths, the shape derivative predicts out to about
`λ/52`. That is the quantitative content of "low frequencies control the
nonlinearity": the first-order model survives a displacement 20x larger at
`k=1` than at `k=20`.

Requiring a harmonic to be detectable *at an amplitude the model still
predicts* gives an admission band of 4, 7, 12, 21, 30, 38, 47 at
`k = 1, 2, 4, 8, 12, 16, 20`, against `3k`'s 3, 6, 12, 24, 36, 48, 60. So
**`3k` is, at contrast 0.33, the locus where detectability meets the
linearization horizon** — an empirical rule with a measured explanation. The
same construction at contrast 10 gives ≈`3k`, not `9.49k`, which bears directly
on iteration 03's unresolved band-rule question: it supports the `driver`
reading (exterior `k`) over §4's prose, and it predicts that the `scaled`
rule's apparent contrast-10 advantage in SC-014 is not a bandwidth effect.

### 3. One probe per frequency calibrates a whole column of the atlas

Within a frequency, the per-harmonic horizon rises linearly with a harmonic's
relative column sensitivity and then saturates at the frequency's ceiling:

```
eps*(k, p) = eps*(k) * min(1, 2.05 * s(k,p) / max_q s(k,q))
```

Pooled over 188 measured cells the median `|log10(measured/predicted)|` is
**0.044 dex**, with **100% of low-contrast cells within a factor of two** and
per-arm medians of 0.021–0.043 dex at the unit circle, at a mid-inversion
iterate and at the truth. The mechanism is that the second-order remainder of a
normal displacement is nearly harmonic-independent while the first-order term
is proportional to the column norm.

**The law fails at contrast 10**: median error 0.689 dex, only 12% of cells
within a factor of two, because the sensitivity profile is itself non-monotone
in `p` there and the second-order response acquires harmonic structure.

### 4. Frequencies conflict, and it is visible without the truth

At contrast 0.33 from the unit circle the whitened gradient stays aligned with
the `k=1` gradient (cos ≥ 0.74) to `k≈14`, then collapses and reaches **−0.39**
at `k=20`; 14% of all frequency pairs are in outright opposition. At contrast 10
alignment falls below 0.5 by **`k=1.25`**, 42% of pairs oppose, and the sign
flips between adjacent grid points. The median adjacent-frequency alignment is
0.999 at contrast 0.33 and 0.268 at contrast 10.

A fixed `Δk=0.25` ladder is therefore well inside the decorrelation length at
low contrast and marginal at high contrast. This is a data-side explanation for
"contrast 10 remains unmatched" in SC-013/SC-014, obtained without the truth,
and it is exactly the kind of statement a magnitude-only atlas cannot make.

### 5. Driving continuation from the atlas: one component helps, one does not

See [SC-017](../../../../results/validation/shape_continuation/SC-017-atlas-controller/README.md)
for the matched-budget arms and the cost-against-accuracy curves. Summarised
there rather than duplicated here.

## Remaining differences and what is not established

- **The harmonic axis is not gauge-invariant off the circle.** On the glider,
  14% of harmonic 10's amplitude, 7% of harmonic 20's and 0.6% of harmonic 60's
  lie below angular order 5. The apparently flat non-circular detectability
  frontier is mostly this order mixing, not evidence that curvature lifts
  evanescence. Cells from different iterates are not yet comparable;
  `atlas.transport_overlap` measures the drift but nothing corrects for it.
- The `0.12/k` ceiling and the `2.05` saturation constant are fitted on one
  target family at two contrasts, full aperture, noise-free data and one
  declared whitening. The horizon is a 10% criterion on one direction at a
  time, not a convergence radius.
- Nothing here re-opens the Figure 1 reproduction. The band-rule measurement is
  evidence about which rule is physically defensible, not a recovery of the
  authors' settings or plotting convention.
- No claim is made that the atlas is novel. The review's own conclusion is that
  every ingredient exists separately; what is measured here is the coupling.

## Candidate next steps

1. **Settle transport.** Compare atlas cells between iterates in a common
   angular gauge, and re-measure the non-circular frontier there. Until this is
   done, no frequency-by-harmonic figure at a non-circular boundary should be
   read as physics.
2. **Explain the contrast-10 breakdown.** The horizon law, the gradient
   alignment and the sensitivity monotonicity all fail together at contrast 10.
   The cheapest discriminating measurement is the interior-field structure at
   the frequencies where the sign flips.
3. **Isolate the band/step-control interaction.** The Gaussian filter damps
   harmonic `n` by `exp(-(n/M)^2/sigma)`, so a wider band is damped *less* at
   the same filter level. A wider measured band and the paper profile's
   `backtracks=0` are therefore not independent choices; an ablation is running
   and is reported in SC-017.
