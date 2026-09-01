# Square Target: Explaining the First Results, and What Could Stand In for gprMax

2026-08-26

## What this is

`test_square_comparison.py` landed with two checks (gprMax on the index-0 ring
pair, self-convergence) and no accuracy gate beyond loose thresholds, because
no closed-form oracle exists for a square cross-section. This is a read-only
follow-up: explain the numbers that came out, and think through whether
anything better than gprMax's ~1-2% floor is available. No code changes here;
see the Plan section for what would need building.

## Results, explained

### The two solvers replicate their circle-case story

| | circle vs Mie | square vs gprMax (index-0 pair) |
|---|---:|---:|
| `gpr_bem_ref` 0.5/1.5/2.5 GHz | 9.15% / 62.84% / 19.58% | 27.18% / 29.64% / 53.46% |
| `gpr_bem_mod` 0.5/1.5/2.5 GHz | 0.03% / 0.36% / 3.42% | 2.03% / 6.35% / 1.95% |
| `gpr_bem_ref` condition number | 3.4e12 - 6.1e12 | 5.8e8 - 6.6e8 |
| `gpr_bem_mod` condition number | 158 - 1.8e4 | 126 - 1.53e4 |

`ref` is bad on both shapes for the same already-documented reason: first-kind
BIE plus a finite-difference normal derivative is a poorly conditioned
combination (`docs/validation_change_log.md`, 2026-08-24 entry). Nothing about
the square specifically makes it worse in kind, only in degree, and the
degree difference is not something to read into: `ref`'s condition number is
four orders of magnitude *smaller* on the square (1e8-1e9 vs 1e12) despite a
larger relative error, which just says its error there is dominated by
discretisation bias, not by amplifying quadrature noise -- the two shapes hit
different points on the same bad formulation, not different failure modes.

`mod` is worse on the square than the circle at every frequency, which is
expected and was flagged as such in the entry that added this test:
`MULLER_OFFSET_SCALE` (0.1375) and the analytic-extrapolated kernel scheme
were tuned against the circle only. Restating the headline number a
different way -- `mod`'s square error is the same *order* as gprMax's own
circle-vs-Mie floor (1.0% / 2.3% / 1.9%) -- is consistent with "no corner
pathology, just untuned constants," which is the reading the change log
already settled on. Nothing here revises that.

### Coincidence, not design: identical N and offset on both shapes

Both tables show `gpr_bem_ref` at offset 0.00469 and `gpr_bem_mod` at offset
0.00064, and both shapes compress to exactly N=168 samples. `merge_distance`
(and hence the offset, a fixed multiple of it) is a function of grid spacing
alone, not of the shape being sampled -- the square and circle tests use the
same grid (161x161) over the same characteristic length, so this was always
going to match. The sample count matching (168 = 168) despite the square's
larger perimeter (0.4 m vs the circle's 0.314 m) is coincidental: compression
merges band cells within `merge_distance` of each other, and how many
survive depends on the band's shape, not just its length.

### The interesting anomaly: `mod`'s error vs gprMax peaks at 1.5 GHz, self-convergence does not

`mod` vs gprMax: 2.03% / 6.35% / 1.95% -- up then back down.
`mod` self-convergence (N=168 -> 256, no gprMax involved): 1.15% / 3.64% / 7.92%
-- monotonically up, the physically expected direction (finer boundary
features matter more as the wavelength shrinks).

These two curves disagree in shape. If the 1.5 GHz bump were `mod`'s own
error, self-convergence -- which needs no external oracle and would catch any
`mod`-side blow-up directly -- should show it too. It doesn't. That points at
gprMax's own square-case error having a hump near 1.5 GHz that happens to
partly cancel against `mod`'s smoothly growing error at 2.5 GHz. Two things
were checked as candidate explanations and can be ruled out (as regards
`mod`, at least):

**Interior-resonance proximity.** Checked whether 1.5 GHz sits near a
Dirichlet eigenfrequency of the plastic-filled square cavity (side 0.1 m,
`k_mn = pi*sqrt((m/a)^2+(n/a)^2)`, converted to a frequency via
`k_interior(f) = k_mn`):

| (m,n) | resonant f |
|---|---:|
| (1,1) | 1.224 GHz |
| (1,2) | 1.935 GHz |
| (2,2) | 2.448 GHz |
| (1,3) | 2.737 GHz |

1.5 GHz sits between two low-order modes, not on top of either, and -- more
to the point -- `mod`'s Müller formulation is specifically constructed (Kress
& Roach; Colton & Kress ch. 3) to stay uniquely solvable at every frequency
for the transmission problem, unlike a naive single-representation exterior
BIE. A true interior-resonance breakdown was never expected. What *would* be
consistent with a near-degeneracy is a local bump in condition number right
at 1.5 GHz -- and there isn't one: `mod`'s condition number climbs smoothly
(126 -> 4310 -> 1.53e4) with no anomaly at that frequency. Ruled out.

**Numerical dispersion in gprMax.** Wavelength in sand shrinks with
frequency, so cells-per-wavelength (cell size fixed at 1 mm) falls
monotonically: 245 / 82 / 49 cells at 0.5/1.5/2.5 GHz. Dispersion error should
therefore grow monotonically with frequency too, not peak in the middle.
Doesn't match either.

Net: the middle-frequency bump most likely lives in some other part of
gprMax's own square-case pipeline (the Ricker pulse used by `run_case.py` is
centered at 1.5 GHz, so that is where its spectral energy -- and DFT
extraction accuracy -- is doing something different from the tails; not
investigated further here), not in `mod`. This is exactly the kind of
question a tighter independent oracle would resolve cleanly, by letting the
two be checked separately instead of only against each other.

## Is there an analytical (or semi-analytical) baseline for a square, beyond gprMax?

### Ruled out: closed-form separation of variables

A closed-form Mie-style series exists only when the scatterer's boundary is a
coordinate surface of a system in which the 2D Helmholtz equation separates
(circular -> Bessel/Hankel, elliptical -> Mathieu functions). A square is not
such a boundary in any known separable coordinate system. This was already
established before building the test and remains true; restated here only for
completeness.

### Candidate 1 (recommended): T-matrix / Extended Boundary Condition Method

Waterman's method: expand the incident and scattered fields in cylindrical
wave functions (Bessel/Hankel, order `-N..N`) centered on the target, and
build the T-matrix relating their coefficients from a surface integral of the
*exact* boundary (the extinction theorem / null-field condition) -- here, four
flat edges, each smooth with no curvature, so each edge's contribution to
that integral is well approximated by a modest-order Gauss rule and the only
awkward points are the four corners, handled by not straddling them in any
one quadrature panel.

Why this is a real independent check and not "BEM again, differently
branded": the representation is a *global* multipole basis with a boundary
integral used only to fix its coefficients, not a mesh of local boundary
elements evaluated near-field with a Green's function the way `gpr_bem_*`
and gprMax's FDTD each are (in their own, unrelated ways). Different failure
modes: no near-singular kernel evaluation, no narrow-band SDF sampling, no
Yee-grid staircasing or CFL-linked time stepping. Agreement with it is
evidence of a different kind than agreement with gprMax.

Feasibility check: a standard rule of thumb for the truncation order needed
for accurate multipole-basis scattering (Wiscombe's criterion, imported from
Mie-series practice) is `N ~ ka + 4(ka)^(1/3) + 2`. At this case's largest
`ka` (2.5 GHz, `ka = 6.42`): `N ~ 6.4 + 7.4 + 2 ~ 16`, so an order-20
truncation should already be comfortable -- a `~40x40` complex linear system,
trivially cheap, not a scaling risk.

Caveat, not a blocker: T-matrix/EBCM methods are documented in the light-
scattering literature (Mishchenko & Travis and others, in the context of
non-spherical-particle T-matrix codes) to have convergence and conditioning
trouble for shapes with sharp corners or large aspect ratios -- precisely the
feature a square has and a circle doesn't. It is not safe to assume this
converges cleanly to sub-percent just because the order-of-magnitude
estimate above looks comfortable; it would need its own convergence study
(sweep truncation order N, confirm the T-matrix result stabilizes) before
being trusted as ground truth, the same way `nystrom_ref` earned trust with
its own convergence study rather than by assumption.

Bonus, not just accuracy: once a T-matrix is computed for one frequency, the
scattered field for *any* Tx/Rx pair is a cheap linear evaluation. That
removes the 4-fold-symmetry limitation that currently restricts the gprMax
check to the ring scan's index-0 pair only -- a T-matrix oracle could gate
all 24 pairs, not one, closing a gap `test_square_comparison.py` currently
just documents and lives with.

### Candidate 2 (escalation path): Generalized Multipole Technique / MMP

Hafner's Multiple Multipole Program addresses EBCM's corner-convergence
weakness directly, by placing several auxiliary multipole expansion origins
near/behind each corner (instead of one origin at the shape's center) and
fitting their amplitudes to the boundary condition in a least-squares sense.
More implementation work -- a nonlinear placement problem, not just a linear
solve -- so this is worth reaching for only if Candidate 1's convergence
study shows the corners are in fact the limiting factor, not a first move.

### Candidate 3 (cheap, narrow scope): quasi-static limit via conformal mapping

In the strict `ka -> 0` limit the transmission problem reduces to Laplace's
equation, which transforms exactly under a conformal map. The exterior of a
square maps to the exterior of a disk via a classical Schwarz-Christoffel
transform available in closed form, giving a closed-form leading-order
polarizability/dipole scattering strength -- a real closed-form check, unlike
Candidates 1-2.

Checked against this case's actual frequencies: `ka` = 1.28 / 3.85 / 6.42
(side-to-wavelength 0.41 / 1.23 / 2.04). None of these are in the quasi-static
regime -- `ka` at the *low* end is already order 1, not `<< 1`. A leading-order
Rayleigh check would carry its own large, uncontrolled error at all three
test frequencies, so this cannot serve as the primary oracle here. Cheap
enough to be worth adding later as a consistency check if the test suite ever
adds a sub-100 MHz case, but not a near-term priority.

### Considered and deprioritized

**FEM.** A third independent numerical method (volumetric mesh + variational
weak form, vs. BEM's boundary discretisation and FDTD's structured grid), but
a new heavy dependency (FEniCS/scikit-fem) and a from-scratch transmission-
problem-plus-absorbing-boundary implementation for a benefit that mostly
duplicates gprMax's role: another volume-discretisation method with an
`O(h^p)`-type floor, unlikely to land meaningfully tighter than gprMax already
does at a comparable mesh size. Low priority relative to Candidate 1, which
can in principle reach much higher precision for the same shape.

**Published benchmark values.** Square/rectangular dielectric cylinders are a
common EBCM/T-matrix benchmark case in the light-scattering literature,
enough that a paper with matching `epsr`/`ka` combinations plausibly exists.
Zero implementation cost if it does. Not verified here -- no specific
reference was located or confirmed to match this case's parameters, so this
is a lead to check, not a claim.

## Plan

**Phase 0 -- literature search, no code.** Look for a published T-matrix or
EBCM benchmark for a dielectric square cylinder at `epsr` around 3/6 and `ka`
in the 1-6 range. If one lines up closely enough to compare against directly,
it validates Phase 1's implementation almost for free once built, and might
even substitute for building it immediately.

**Phase 1 -- build the T-matrix/EBCM oracle as a new sibling solver**, e.g.
`solvers/tmatrix_ref/`, following the `nystrom_ref` precedent: standalone,
forward-only, no SDF, no adjoint, written from scratch against only the
shared problem definition (`config/simulation_config.py`, the `Material`
wavenumber convention, the line-source normalisation) so it cannot inherit a
`gpr_bem_*` bug. Steps:

1. Multipole expansion of incident/scattered/interior fields (cylindrical
   Bessel/Hankel, order `-N..N`).
2. Surface integral (Gauss quadrature per edge, corners as panel boundaries,
   never straddled) building the T-matrix from the exact polygon -- not an
   SDF-sampled approximation of it, the same way `nystrom_ref` uses an
   explicit boundary parametrisation rather than IBIM's implicit one.
3. **Convergence study before trusting any output**: sweep truncation order N
   (e.g. 8, 12, 16, 20, 24) at all three test frequencies, confirm the
   scattered field stabilizes to several digits, and report where it stops
   improving. If it doesn't stabilize cleanly near the corners, that is the
   trigger for Candidate 2 (MMP), not a reason to ship an untrusted number.
4. Write up the convergence result as `docs/tmatrix_reference_study.md`,
   mirroring `nystrom_reference_study.md`'s structure.

**Phase 2 -- wire into `test_square_comparison.py`.** Once trusted, this
becomes a third comparison row alongside gprMax, and -- because a T-matrix
evaluation is cheap for any Tx/Rx pair -- can gate the full 24-pair ring
scan rather than the index-0 pair only, which also finally lets the 1.5 GHz
anomaly above be attributed to gprMax or to `mod` individually instead of
only to their difference.

**Not planned now:** MMP (Candidate 2) unless Phase 1's convergence study
shows corner convergence is actually the bottleneck; the conformal-mapping
quasi-static check (Candidate 3) unless a sub-100 MHz case is added to the
suite; FEM, deprioritized as largely redundant with gprMax's role.
