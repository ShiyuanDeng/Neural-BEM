# Codex review — optimizer fixes accepted; Figure 1 reproduction provisional

2026-09-22. Reviewer: Codex. Reviewed implementation and reports at `1a6a55a`,
including `49f4128`, against upstream commit
`bda24bddbf4562497280b671bc174ef891b47c6b`. The user requested this written
correction after the review. This is a documentation amendment: no numerical
code, settings or saved run measurements were changed, and no new inverse
campaign was run.

## Verdict

The optimizer is substantially cleaner and provides a good foundation for
adaptive shape/frequency continuation. The independent direction searches and
explicit direction policy resolve the two earlier implementation defects.
**Figure 1 reproduction remains provisional.** SC-014 establishes useful
partial agreement at contrast 0.33 under one interpretation of the plotted
error. It does not identify the authors' Figure 1 inputs or plotting convention,
and contrast 10 remains unmatched.

This review supersedes the original iteration-03 replication,
axis-identification and baseline-selection claims. The corrected
[iteration results](../01_results.md) and
[SC-014 report](../../../../../results/validation/shape_continuation/SC-014-figure1-calibration/README.md)
retain all measured values. The original wording is preserved in this
repository's Git history at `1a6a55a`.

## Findings and dispositions

### 1. Independent GN/SD searches — accept the fix

`optimise_step` now searches each selected direction until it finds an
admissible, decreasing candidate, then compares the survivors. An immediately
successful SD step no longer prevents reaching a better, more strongly filtered
GN step. This matches the reference's two search loops. The regression
`test_each_direction_is_filtered_to_admissibility_independently` passes.

### 2. Direction selection across chunks — accept the fix

`FitConfig.directions` replaces the chunk-local warm-up counter. Splitting two
SD updates into separate decisions preserves the accepted geometry and work
counts in `test_direction_policy_does_not_depend_on_how_updates_are_chunked`.
A strategy can select SD or both directions using its frequency history;
reproducing a particular warm-up schedule still requires that strategy.

### 3. Reference stopping norm — open implementation difference

Our [stopping test](../../../../../experiments/shape_continuation/inverse.py)
uses `rms_displacement <= step_tolerance`. Upstream
[`inverse_solver.m`, lines 265–275](https://github.com/flatironinstitute/inverse-obstacle-scattering2d/blob/bda24bddbf4562497280b671bc174ef891b47c6b/src/%2Brla/inverse_solver.m#L265)
uses the Euclidean norm of the filtered normal-update coefficients. Our saved
`update_norm` already measures that quantity; `coefficient_step_norm` is the
unfiltered proposal norm and must not be substituted for it.

The distinction affects the saved stage endpoints:

| SC-014 arm | Stages | Stopped on small RMS step | Of those, filtered coefficient norm still above tolerance |
|---|---:|---:|---:|
| driver, contrast 0.33 | 17 | 17 | **6** |
| driver, contrast 10 | 9 | 7 | **3** |
| paper, contrast 0.33 | 17 | 17 | **2** |
| paper, contrast 10 | 9 | 5 | **1** |
| scaled, contrast 10 | 9 | 7 | **2** |

For example, driver/0.33 at k=1.25 stops with RMS `0.0009309391`, while its
filtered coefficient norm is `0.0011120352`, above the `0.001` threshold.
The reference's step test would not stop there. This does not establish how
much the final reconstruction would change; that was not rerun.

**Recommendation:** make the stopping measure explicit and use filtered
coefficient norm in a profile intended to follow the reference. Retain RMS as
a useful physical diagnostic. Until corrected, label the difference in all
profile comparisons; identical numerical tolerances do not make the tests equal.

### 4. Driver resolution — correct the attribution; implementation remains open

The upstream
[`driver_charlie_transmission.m`](https://github.com/flatironinstitute/inverse-obstacle-scattering2d/blob/bda24bddbf4562497280b671bc174ef891b47c6b/tests/driver_charlie_transmission.m)
sets local `nppw=30` inside its **data-generation** branch (lines 139 and 185).
It never sets `opts.nppw` for the inverse and supplies a 500-node initial
circle (line 269). In
[`update_inverse_iterate.m`, lines 217–222](https://github.com/flatironinstitute/inverse-obstacle-scattering2d/blob/bda24bddbf4562497280b671bc174ef891b47c6b/src/%2Brla/update_inverse_iterate.m#L217),
the absent option leaves `rlam=Inf`; the
[`update_geom.m` node rule](https://github.com/flatironinstitute/inverse-obstacle-scattering2d/blob/bda24bddbf4562497280b671bc174ef891b47c6b/src/%2Brla/update_geom.m#L109)
retains at least the existing node count. Thus 30 is not the inverse resolution
setting of that script.

Our `driver` profile uses 30 in the inverse K/N sizing formulas, giving 64
nodes at the first contrast-0.33 stage and 330 at k=5. Its saved N/2N checks
pass; the attribution error alone does not invalidate that numerical resolution.
It does invalidate describing the profile as the authors' exact driver settings
or attributing its lower cost to their inverse resolution choice.

The cited script also uses a Charlie cavity and different material settings;
it is a transmission example, not an identified Figure 1 glider driver.
**Recommendation:** retain `driver` as the existing CLI name but describe it
as a profile inspired by that driver, with our resolution and stopping choices
declared. Decide those choices explicitly before freezing an adaptive baseline.

### 5. Plotting convention and recovered band rule — reject the certainty

The inspected upstream drivers save raw symmetric-difference area; the paper
defines a normalized error. We have not recovered the plotting code or data
that connect those saved values to Figure 1. The raw-area interpretation is
plausible and gives the best low-contrast agreement among the tested arms.
It remains a hypothesis; the high-contrast `driver` arm actually agrees better
under the normalized interpretation (log10 RMS 0.276 versus 0.629).

The argument that a normalized published point would be worse than the initial
circle does not settle the issue: decreasing scattering residual does not
guarantee decreasing shape-area error. Nor does matching one scalar error at
k=1 identify the update bandwidth. The profiles change optimizer, resolution,
tolerance and iteration cap together; they do not isolate bandwidth's effect.

**Disposition:** withdraw claims that the axis and Figure 1 band rule are
settled. Report both area interpretations. Confirmation needs the actual
Figure 1 plotting provenance or author clarification, not further tuning to the
same digitized curve.

### 6. Partial agreement and baseline choice — accept the measurement, narrow the claim

For driver/0.33 over k=1…5, the raw-reading published/ours ratios have median
**1.0367**, range **0.6504–1.5688**, and log10 RMS **0.1170**. The median is
not a claim of pointwise agreement within 4%. These are encouraging similarities
over a partial frequency window, with appreciable discrepancies. Contrast 10
does not reproduce the published curve. Two tested curves lying on opposite
sides of it does not identify a band rule between them.

`scaled` was selected after seeing the high-contrast comparison. Its equality
with `driver` below unit contrast is an algebraic property, not independent
evidence that the high-contrast rule is correct. These figure comparisons are
development evidence; any generalization claim needs an untouched case.

**Recommendation:** use a clearly specified fixed ladder as the eventual
adaptive control, after resolving the profile differences. Paper reproduction
and adaptive improvement are separate questions. Do not select the control
solely because its shape-error curve resembles the published one, and compare
cost at declared recovery/data-fit quality rather than proximity to that curve.

## Validation and limits

- At `1a6a55a`, **171 tests passed in 5.30 s** with single-thread settings:
  `python -m pytest -q experiments/shape_continuation pytest/gpr_bem_kress pytest/ordered_boundary`.
- All five SC-014 manifests' **41 source hashes each** match the reviewed
  checkout. Their recorded base commit is `8e5c152` with working-tree edits;
  the hashes identify the measured source more precisely than that base commit.
- All 61 saved stage records are committed and report passing field/Jacobian
  qualification. These records were inspected, not regenerated.
- Stopping counts above come from each case's `summary.json`: select
  `stop_reason == "small_step"` and compare the last history entry's
  `update_norm` with the recorded `step_tolerance`. Agreement statistics come
  from SC-014's unchanged `comparison.json`.
- No MATLAB/Fortran reference run, extended ladder, or numerical profile repair
  was performed during this review. Nodal Müller/Kress remains the chosen solver.
