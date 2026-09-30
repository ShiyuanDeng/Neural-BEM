# Isolated shape and frequency continuation

The cleanup is governed by the user's
[requirements and clarification](../iterations/cleaned_interfaces/iteration_01/02_proposals/01_user_requirements.md): one
cumulative implementation must retain performance on all 36 configurations,
with readable stage policies and a single forward-backend selection. The
historical reference strategies below are regression evidence, not separate
algorithms to copy into the cleaned pipeline.

The [Cleaned interfaces track](../iterations/cleaned_interfaces/README.md)
owns the [CI-001 plan](../iterations/cleaned_interfaces/iteration_01/03_plan.md).

The maintained implementation now lives in
[`experiments/cleaned_interface`](../../experiments/cleaned_interface/README.md).
It extracts one cumulative policy, explicit physics services and the selected
SPD accelerations. Focused interface checks do not establish all-36 retention;
the [implementation handoff](../iterations/cleaned_interfaces/iteration_02/01_results.md)
keeps that campaign, the noise-policy changes and the additional damped-input
contract explicit. The historical inventory below is preserved as the
starting evidence, not a dispatcher inside the new runner.

## Current inverse across the 36 configurations (2026-09-30)

**The newest successful inverse extension is MA-005's DF policy, built on
SC-050 and the SC LM backend. There is no single policy validated across all
36 configurations.** MA-006 is a later operator-atlas study, not a replacement
inverse. SC-051 is the latest all-configuration comparison; its full-band,
frequency-only arm recovers 0/36 single-object configurations.

The reported **34/36** comes from four preselected reference strategies:

| Panel | Configurations | Archived reference | Recovered |
|---|---:|---|---:|
| Core shapes | 6 | SC-043 fixed band release, including its predecessor path | 6/6 |
| Fresh shapes and noise draws | 6 | SC-044 recurrent state cleanup | 6/6 |
| Far initializations | 7 | SC-050 localization + low-frequency warm-up | 7/7 |
| Higher contrasts | 17 | MA-005 damped start + frontier tail (DF) | 15/17 |

The authoritative case inventory is the
[SC-051 manifest](../../results/validation/shape_continuation/SC-051-frequency-only/manifest.json):
select panels `core`, `fresh`, `far`, and `modal`; exclude the four `coupled`
and one `intrinsic` entries. These are 36 configurations, including shared
targets with different starts, contrasts and noise draws, rather than 36
independent shapes. The contrasts are 0.5 (19 configurations), 2 (3), 4 (7),
and 13.3 (7). The
[comparison and endpoint gates](../../results/validation/shape_continuation/SC-051-frequency-only/README.md)
define recovery and retain every failure.

### Candidate to consolidate: MA-005 DF

The same algorithm is used throughout MA-005's 20 development/transfer
configurations; 18 recover. Its stages are:

1. Localize a circle from low-frequency damped observations using a dense
   exact-Mie search and BIE qualification.
2. Fit the 0.25 GHz warm-up and four prefix stages at
   `k * (1 + 0.25i)`, using the exterior-wavenumber band rule for the four
   prefix stages.
3. Return to real-frequency data with an undamped fourth-stage pass.
4. Release the update band through `M = 11, 15, 19, 25, 31, 37`, using all
   19 real frequencies from 0.25 to 2.5 GHz. Apply the inherited one-time
   state cleanup before `M = 25`.
5. Measure the 1% paired-Jacobian column-norm frontier at the current curve
   and highest frequency. Append `M = 43, 49, ...` up to the measured
   frontier, capped at 95, if the preceding schedule completed.
6. Audit the endpoint independently and score geometry only after fitting.

The representation remains Cartesian Fourier geometry with projected scalar
normal updates, nodal Müller/Kress physics, and the SC LM fitter. The late
state storage band is `K = 192`; the frontier controls update band `M`, not
the trace cutoff studied in MA-006.

The implementation is split across:

| Responsibility | Source |
|---|---|
| DF tail and campaign entry point | [`experiments/modal_atlas/frontier_tail.py`](../../experiments/modal_atlas/frontier_tail.py) |
| Damped localization, prefix, real-data handoff and fitting loop | [`experiments/modal_atlas/damped_screen.py`](../../experiments/modal_atlas/damped_screen.py) |
| Complex-frequency forward solve | [`experiments/modal_atlas/damped.py`](../../experiments/modal_atlas/damped.py) |
| SC-050 schedule, localization baseline and audits | [`SC-050-localization-robustness/run.py`](../../results/validation/shape_continuation/SC-050-localization-robustness/run.py) |
| Shared numerical fitter | [`experiments/shape_continuation/lm_backend.py`](../../experiments/shape_continuation/lm_backend.py) |

`contrast_screen.sc050()` dynamically imports the SC-050 result-folder
driver, which in turn loads SC-049 and older SC helpers. This is why the
latest inverse spans both tracks and archived result directories. The
existing MA-005 CLI runs its frozen experiment and uses its fixed output
paths; it is not a general all-36 runner.

### What remains for one cumulative all-36 pipeline

MA-005 DF is the latest inverse extension to examine when extracting the
cumulative algorithm. The cleanup must retain the earlier SC capabilities and
verify the latest implementation across all 36 configurations. Applying DF
unchanged everywhere is not an established retention result; the
[requirements](../iterations/cleaned_interfaces/iteration_01/02_proposals/01_user_requirements.md) govern the integration and
regression checks.

- DF covers the 17 modal configurations and three of the seven far cases
  at contrast 0.5. The other 16 configurations have no DF run: six core,
  six fresh/noisy, and four remaining far cases.
- DF requires observations at complex frequencies in addition to the
  stored real-frequency measurements. The existing MA-004 input mapping
  supplies these for the 20 DF cases. Extending it requires qualified
  damped inputs for the remaining configurations. MA-004 generated these
  synthetically from the targets; its noisy damped data use an independent
  noise draw, not a transform of the saved noisy real-frequency samples.
  Preserve that distinction when defining a common benchmark.
- The original C at contrast 13.3 remains unrecovered from both starts
  (`development_c` and `opposite_c`), with about 6.396 mm RMS. Consolidation
  alone does not resolve this failure.
- The tail ignores the noise level and worsens geometric accuracy on the
  two reported noisy transfer cases, although both still pass recovery.
  A noise-aware tail would be a new policy requiring a separate test.

See [MA-005 results and limitations](../iterations/modal_atlas/iteration_06/01_results.md)
and the [MA current handoff](../iterations/modal_atlas/README.md). The older
API and paper-reproduction description below documents the foundation; it
does not supersede this current campaign reconciliation.

## Core API and paper-reproduction foundation

The working research entry point is
[`experiments/shape_continuation`](../../experiments/shape_continuation/README.md).
Research cycles and the current handoff are in
[`docs/iterations/shape_frequency_continuation`](../iterations/shape_frequency_continuation/README.md).
It follows the boundary-inversion structure in Borges, Rachh and Greengard,
*On the robustness of inverse scattering for penetrable, homogeneous objects
with complicated boundary*, Inverse Problems 39 (2023) 035004,
[DOI](https://doi.org/10.1088/1361-6420/acb2ec).

The complete paper is stored locally as the
[24-page arXiv v1 PDF](../reference/papers/borges_rachh_greengard_2210.11607v1.pdf),
with [source and version details](../reference/papers/README.md). The authors'
[reference implementation](../reference/papers/README.md#reference-implementation)
is read, not vendored; it settles the filter, steepest-descent scaling and
trust-region band that the manuscript states loosely.

```text
Cartesian Fourier curve, parameterized by arclength
    → ordered boundary nodes
    → dense nodal Müller/Kress, plane-wave or line-source illumination
    → complex scattered fields and normal-shape Jacobian
    → single-frequency GN/SD update + geometry/curvature checks
    → reparameterize and accept only a decreasing candidate
    → hand the curve to the next frequency/update band
```

The normal update band, curve storage band, and quadrature node count are
separate. There is no polar-angle restriction. Complex Fourier coefficients
are an equivalent storage notation for Cartesian Fourier geometry; they do
not select the native Fourier–Galerkin Müller solver.

The experiment controls have distinct jobs:

| Control | Meaning |
|---|---|
| `Stage.wavenumber` | Selects one measured complex data matrix and its acquisition. |
| `Stage.update_modes` | Chooses the `2M+1` real Fourier coefficients of the normal update. This is the primary shape-harmonic continuation control. |
| `Stage.curvature_modes` | Sets the curvature-energy band used for admissibility; its tail tolerance is explicit in `FitConfig`. |
| `Stage.curve_modes` | Resolves Cartesian curve storage and arclength refitting. Insufficient storage rejects a proposal rather than silently smoothing it. |
| `Stage.nodes` | Resolves nodal Müller/Kress quadrature, independently of the update band. |

`optimise_step` is the experiment unit: it attempts one accepted update and
retains the candidate's already-computed forward state and LU. `prepare_state`
reuses that solve when only M/C, tolerances, or zero-padded K change; changes to
geometry, frequency, acquisition, material or N rebuild it. `fit_prepared`
groups updates into a chunk; `fit_frequency` prepares a fresh one-frequency fit.

`run_adaptive` asks a plain callable strategy for `Decision(Stage, FitConfig,
reason)`, or `None` to finish. The strategy sees the current committed curve,
full decision history, available frequencies and cumulative work. It may repeat
or revisit frequencies and alter harmonics/resolution between updates by using
`max_iterations=1`. One work budget spans the whole run, including optional
N/2N qualification. Failed qualification rolls back the entire decision while
preserving its rejected trajectory for the next strategy call. Decision records
do not retain dense physics caches. The existing `run_continuation` API is now
an adapter over this controller, preserving the increasing-ladder baseline.

See the [controller contract and pseudocode](../../experiments/shape_continuation/README.md#adaptive-controller-contract)
for cache rules, stopping semantics, diagnostics and checkpoint hooks.

The synthetic harness saves stage checkpoints, can resume a saved run with an
explicit new budget, and qualifies both fields and normal Jacobians at N/2N.
Truth and held-out observations remain evaluation inputs. A small filtered
step means small physical movement; it does not assert stationarity or recovery.

The core's only project dependencies are `ordered_boundary`, `gpr_bem_kress`, and its
`periodic_kress` dependency. The former inverse drivers, SDF/MLP machinery,
topology controller, automatic runtime selection, and modal research packages
are absent from the core import graph. The separate `legacy_cases.py` comparison
harness imports the previous Cartesian Fourier inverse and fixture builders
to run both methods on shared inputs. Production defaults remain unchanged.

The package README owns the API, exact commands, paper-to-code differences,
and limitations. The [qualification record](../../results/validation/shape_continuation/README.md)
owns measurements. The pilot is a single-component, known-contrast,
lossless/equal-density, full-aperture problem in dimensionless coordinates.
It is ready for controlled continuation development; the paper's complete
high-frequency and complicated-boundary results have not been reproduced.

The opt-in [SC-047 coupled extension](../../results/validation/shape_continuation/SC-047-coupled-continuation/README.md)
adds `MultiCurve` and `MultiUpdate` for disjoint general Cartesian components.
It reuses the existing multi-component Müller assembly and the same LM backend;
freezing an object's geometry retains its scattering interactions. State band K
is shared in this first adapter, while update bandwidth and active objects may
differ. N is per component. The independent-circle and complete-trial
derivative qualification passed for an ellipse/C pair at two separations.
Its fixed-count strategy and diagnostic-only topology evidence have their own
frozen contract; this does not replace the single-object defaults or connect
the old polar-gauge topology controller to the new core.

The [Figure 1 preparation and audit](../../experiments/shape_continuation/PAPER.md)
supplies the actual glider contrasts (0.33 and 10), an explicit paper
frequency/resolution profile, and evaluation-only polygon set-difference error.
Its default command produces a plan with zero solves. Smoke is fixed to one
update at k=1 per contrast under shared small work caps; a campaign run requires
explicit budgets. The §4.1 boundary inverse now recovers the glider along the
paper's ladder; [SC-013](../../results/validation/shape_continuation/SC-013-paper-glider-recovery/README.md)
owns those measurements and their limits.

[SC-014](../../results/validation/shape_continuation/SC-014-figure1-calibration/README.md)
compares five profiles with the digitized figure. The
[2026-09-22 Codex review](../iterations/shape_frequency_continuation/iteration_03/02_proposals/01_codex_review.md)
accepts the independent GN/SD searches and explicit direction policy. It records
partial low-contrast agreement, unmatched high contrast, unresolved area-plotting
provenance, and differences in stopping norm and driver-resolution attribution.
These concerns must remain explicit when choosing the fixed adaptive control.
