# Where the modal inverse still samples the curve

Current at `fb5074aa` (2026-10-06). Scope: the default TG-002 recipe, policy
`baseline` = `CumulativePolicy` + pipeline `modal_fixed` (modal Müller physics,
`certified_spectral` geometry), localization off. This list supersedes the
2026-10-03 lists in the [NF-001 review](../iterations/cleaned_interfaces/iteration_17/01_results.md)
and the [inverse review](../reports/inverse_review_2026-10-03.md). Both are retained
as historical records.

**Meaning of "node free".** Under the project's definition, the claim covers the physics:
coefficient-space Müller unknowns and operators, with no boundary-collocation unknowns
and no Cartesian kernel quadrature. Parameter-space geometry quadrature is permitted.
That claim holds. The items below are sampled steps that rule out a stronger claim,
such as **end-to-end sample-free** or **certified validity**.

## Sample-free in the default path

| Step | Code | Note |
|---|---|---|
| Müller operator: Laurent arrays, exact log symbol, Chebyshev arrays | `modal_geometry.py`, `modal_operator.py::muller_matrix` | FFT grids only implement padded linear convolutions |
| Radial Chebyshev coefficients | `modal_operator.py::radial_coefficients` | Analytic Bessel products since AC-001 (2026-10-05). Previously sampled radial functions, a DCT and a sampled amplification peak |
| Sources and receivers | `modal_operator.py::point_kernels` | Graf about z₀; bounding radius Σ_{j≠0}\|z_j\| |
| Jacobian contraction | `modal_muller.py::derivative` | Hadamard product in coefficients; its geometry columns come from row 5 below |
| Signed-area tier, LM step clip, Marquardt metric | `certified.py`, `continuation/lm_backend.py` | Defaults: `step_control="coefficient"`, `metric="marquardt"` |

## Still sampled in the default path

| # | Step | What is sampled | Effect on decisions | Code |
|---|---|---|---|---|
| 1 | log\|W\|² interval and every \|W\|² certificate | Minimum of \|W\|² on a uniform torus grid proposes β; the coefficient residual then accepts or replaces it | A non-positive sampled minimum refuses the physics evaluation or makes the certificate inconclusive | `modal_geometry.py::log_modulus`, `modal_cuda.py::log_modulus`, `device_certified.py::device_certificate` |
| 2 | Normal move | h(α)n on the uniform θ grid (8192 points at K=192; 16384 for the fine copy), then an FFT refit | Defines every trial curve | `certified.py::_moved`, `batched.py::batched_projection` |
| 3 | Arclength reset (eq. 9) | Speed, arclength primitive and phase e^{−ikα} by quadrature on those grids; finite-grid aliasing | Defines every trial curve | `spectral.py::arclength_quadrature` |
| 4 | Coarse/fine refinement gate | max\|c−f\| evaluated on the 2×count grid | Refuses `unresolved_projection` | `certified.py::trial` |
| 5 | Geometry tangent | Central differences (10⁻⁷ m) of the sampled projection, batched on the GPU. Opt-in `analytic_spectral` differentiates the same quadrature, still on the grid nodes | Jacobian columns | `batched.py::prepare`, `analytic_projection.py` |
| 6 | Validity fallback | Sampled area, minimum speed and polygon self-intersection | Tiers 2–3 can only accept. The sampled test makes every self-intersection refusal and accepts every inconclusive certificate | `certified.py::check` |
| 7 | Domain-box containment | Trial curve on `grid_size(K)` points against the box | Refuses `outside_domain`. Every `Problem` has a box | `continuation/lm_backend.py::inside_box` |
| 8 | Observable frontier | Arclength-harmonic weights from ≥1024 curve samples | Chooses tail bands. Runs only when the fixed schedule completes before the noise or accuracy exit | `modal_muller.py::observable_frontier` |
| 9 | Receipts | Max/RMS normal move, speed ratio, intentional projection error | Recorded only; no default decision uses them | `geometry.py::measure`, `continuation/updates.py::speed_ratio` |
| 10 | Certificate arithmetic | Not sampling: float64 FFTs plus a heuristic allowance 80·size·ε·Λ·‖Y‖₁ | `arithmetic_verified=False`; numerical, not interval-verified | same as row 1 |

**Measured use of rows 6 and 8 on TG-002** (ON-001 baseline arm `all_B`, 30 runs,
[raw receipts](../../results/validation/cleaned_interfaces/ON-001/all_B/runs/)):

- The 26 recovered cases never reached the sampled validity test. All of their checks were decided by tier 2 or 3.
- In the four unrecovered cases (aphex_twin 0.5/4/13.3 and hook 13.3), the sampled test accepted 46 moved-curve trials and refused 43. That is 89 of 2,631 trials. Aphex 13.3 accounts for 64 of them.
- Candidate curves were always certified: 0 sampled acceptances and 0 sampled refusals.
- The ON-001 `all_E` arm and the DP-001 E arm have identical counts. The DP-001 F arm (`feedback`) has 85 sampled acceptances and 43 sampled refusals.
- The observable frontier was measured in 12/30 baseline runs and in 2/30 runs with the accuracy exit.

## Opt-in recipes that add sampling

| Recipe | Added sampling | Status |
|---|---|---|
| `validity_first` and its descendants `exact_fast`, `compact_release`, `resolution_response`, `adaptive_resolution` | `validity_order="sampled_first"`: after the increment tier, the sampled test decides. The full certificate only overturns a sampled refusal. The accept set is the same by construction, but receipts then record mostly `sampled_accepted` | PS-001 candidates |
| `four_phase` | The similarity trial is exact, but `SimilarityUpdate.prepare` runs the sampled `FourierCurve.validate()` | CS-001 candidate |
| `reach_clip` | Sampled reach estimate (`reach.py`) | Rejected |
| `step_control="physical"`, `metric="mass"/"curvature"` | Sampled arclength weights | Options, off by default |
| `gaussian_lipschitz` | Gaussian displacement map | Experimental; failed ON-001 |

If a promoted recipe uses `sampled_first`, describe validity as "sampled, with
certificate override", not "certified".

## Changes since the 2026-10-03 lists

- **Removed:** radial-function samples and the DCT (AC-001).
- **Newly measured:** the sampled validity fallback runs in practice, but only in the four unrecovered TG-002 cases.
- **Missing from the earlier lists:** the domain-box test (row 7) and the sampled maximum in the refinement gate (row 4).
- **New since then:** the PS-001 `sampled_first` candidates.
- **Unchanged:** interval proposal, move and reset quadrature, FD tangent, frontier and arithmetic status.
- **Unchanged code:** the modal receipt's `sampling` field (`modal_muller.py::receipt`) still omits the domain box. It was left unchanged because editing maintained sources changes campaign seals.

## Cheapest replacements (proposed, not run)

1. **Domain box:** accept when the disk centred at z₀ with radius Σ_{j≠0}\|z_j\| lies inside the box. This is exact and O(K). Keep the sampled test only as a fallback, as validity does now.
2. **Refinement gate:** replace the sampled max\|c−f\| by Σ\|c_j−f_j\|. This is a rigorous upper bound, but more conservative. Before adopting it, check that it does not add `unresolved_projection` refusals.
3. **Validity fallback:** only the aphex and hook trials reach this test. Removing it needs certificates that are decisive on those curves, or a certificate that can refuse. Neither exists yet.
