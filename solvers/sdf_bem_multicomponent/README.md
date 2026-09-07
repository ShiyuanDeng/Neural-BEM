# Automatic multi-component SDF/Kress seam

This sibling package is deliberately separate from the active inverse and
neural-SDF optimizer. Importing it never imports `sdf_inverse`. It provides
the complete automatic extraction and Kress-forward seam: component count is
discovered from each field, and the canonical result is always an
`OrderedBoundary2D`, including when the discovered count is one.

```python
import numpy as np

from sdf_bem_multicomponent import (
    CircleUnionSDF2D,
    MaterialSpec,
    MultiComponentOrderedSDFGeometryConfig,
    PairedForwardProblem,
    predict_multicomponent_kress_paired_boundary_response,
    predict_multicomponent_kress_paired_response,
)

model = CircleUnionSDF2D(
    centers=((0.43, 0.5), (0.57, 0.5)),
    radii=(0.035, 0.035),
)
geometry_config = MultiComponentOrderedSDFGeometryConfig(
    bounds=((0.30, 0.35), (0.70, 0.65)),
    minimum_intercomponent_clearance=0.05,
)
problem = PairedForwardProblem(
    source_points=np.array(((0.20, 0.40), (0.80, 0.60))),
    receiver_points=np.array(((0.20, 0.60), (0.80, 0.40))),
    angular_frequencies=np.array((2.0 * np.pi * 0.8e9,)),
    source_strengths=1.0,
    exterior=MaterialSpec(epsr=6.0),
    interior=MaterialSpec(epsr=3.0),
    eps0=8.8541878128e-12,
    mu0=1.25663706212e-6,
)
result = predict_multicomponent_kress_paired_response(
    model,
    problem,
    geometry_config,
)

# Inverse code that already owns an OrderedBoundary2D skips extraction:
direct_result = predict_multicomponent_kress_paired_boundary_response(
    result.geometry_build.boundary,
    problem,
)
```

`problem` may be this package's local `PairedForwardProblem` or any
object with the same fields. The structural adapter copies the data without
importing its owning package. The result preserves the fitted
`OrderedBoundary2D`, component IDs and offsets, each frequency's full Kress
solve, and the paired response arrays expected by inverse work.

`predict_multicomponent_kress_paired_boundary_response` is the wiring seam for
an optimizer that already owns its canonical `OrderedBoundary2D`. It accepts
the same structural problem contract, retains the exact boundary object, and
performs no SDF evaluation, contour extraction, projection, or Fourier fit.
The component count comes from the boundary at each call; `M=1` and arbitrary
`M>1` use the same code path.

## Supported contract

- Any discovered positive number of closed, counterclockwise components;
  `expected_num_components` is an optional exact-count assertion only.
- Disjoint, non-nested, sufficiently separated inclusions.
- Negative-inside fields whose gradient has positive projection onto each
  component's outward normal; sign-reversed zero sets are rejected.
- One common lossless, nonmagnetic interior material in a lossless,
  nonmagnetic exterior.
- Independent even Kress node counts per component.
- Zero-component, resource-limit, unresolved-small-loop, readiness, and
  clearance failures are explicit; no largest-loop or fallback selection is
  performed.

By default, a successful build repeats the complete extraction and readiness
pipeline on a grid with the opposite point-count parity. The two builds must
agree on component count and on a one-to-one geometric matching of their
fitted loops. Grid-relative area, perimeter, two-axis span, and separation
floors reject sub-cell speckles and unresolved near-touching objects. A final
node-weight clearance gate matches the default multi-Kress cross-component
quadrature policy, so geometry labelled ready is also admissible to that
default adapter. A custom, stricter Kress assembly configuration can still
reject it explicitly. These checks provide resolution confidence; they do not
claim a proof of the continuous zero-set topology.

The marching-squares frontend already returns each closed loop independently.
The geometry builder fits every loop with Method B and retains topology in
`OrderedBoundary2D`. Component IDs use the frontend's deterministic spatial
order. A future optimizer that attaches component-specific state should match
components between accepted iterates (for example by centroid assignment)
rather than treating that spatial order as persistent identity.

For a target component `i` and source component `j`, self blocks use the
existing cancellation-safe exterior-minus-interior Kress assembly. Distinct
component blocks use only the smooth exterior operator with the source
component's arc-length weights. Nearly touching components require a future
close-evaluation method and are rejected here.

Kress exposes `MultiComponentKressGeometryError` with topology and field-point
subclasses, so future line searches can reject expected geometric
infeasibility without swallowing unrelated `ValueError`s.

## One-circle to two-circle validation

The deterministic Cassini fixture exercises a genuine topology event. It
starts as one exact circle, narrows to a Bernoulli-lemniscate pinch, separates
into two regular lobes, and ends as two exact circles:

```bash
PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_multicomponent_split_demo.py
```

Every regular video frame goes through automatic extraction with
`expected_num_components=None`. The exact pinch is not a valid smooth
boundary: its gradient vanishes where the lobes touch. The fixture therefore
stores that one frame as exact raw polylines, labels it
`topology_transition`, and skips Method B and BEM. The archive uses
`RaggedBoundaryTrajectory` with independent frame-to-component and
component-to-point offsets, so it never joins two loops with a spurious bridge
or pretends there is a one-to-one node interpolation across the split.

The endpoint is solved through the direct multi-Kress boundary seam. Its
focused test also compares the field with the independent cylindrical-harmonic
multi-cylinder oracle.

## Integration boundary after the MLP repair

The repaired MLP inverse intentionally owns one `PeriodicCurve2D` in a
gauge-fixed, star-shaped radial Fourier state. Its finite-difference probes
solve that curve directly; the distilled MLP zero set is an audit rather than
the next optimization state. That is the correct fast path for its current
single-object benchmark, but it cannot represent a split.

Consequently, this work wires the reusable seams without changing that
optimizer: automatic MLP/SDF-to-`OrderedBoundary2D`, direct
`OrderedBoundary2D`-to-multi-Kress, and ragged artifacts are ready. A future
topology-changing inverse still needs a proposal/handoff layer that creates a
new multi-boundary state at an accepted event, component-aware update charts
and re-distancing, and records keyed by component offsets. Merely injecting a
different predictor into the one-curve optimizer would leave its state space
at `M=1` and would be misleading.

The current one-curve dispatcher, MLP re-distancing, and optimizer records are
therefore intentionally unchanged.
