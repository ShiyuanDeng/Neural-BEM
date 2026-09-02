# Ordered smooth-boundary nodes

This package is the solver-neutral, **node-based** explicit-boundary starting
point for future 2-D BIE backends. It is parallel in role to
`gpr_bem_mod.ImplicitBoundarySamples2D`, but its nodes retain cyclic order,
component identity, periodic parameters, and higher geometric derivatives.

It is usable now with analytic and already-fitted Fourier parameterizations.
No active forward solver consumes it yet, and SDF extraction/fitting remains a
separate future producer.

## Public geometry split

The names encode which objects own nodes and which only produce them:

- `PeriodicParameterization2D` is continuous. It stores an evaluator for
  `x(t)`, `x'(t)`, `x''(t)`, and optional `x'''(t)`. It supports off-node
  evaluation, validation, phase/orientation changes, and changing resolution.
- `PeriodicCurve2D` is node-based. It stores exactly one uniform periodic node
  grid and has no evaluator.
- `OrderedBoundaryParameterization2D` groups continuous component producers.
- `OrderedBoundary2D` is the flattened, component-aware node object passed to
  a future BIE assembler. It has no SDF and no evaluator.

The transition is explicit:

```text
OrderedBoundaryParameterization2D
                 |
                 | .discretize(node_counts)
                 v
          OrderedBoundary2D       # BIE input
```

There is deliberately no `.sample()` method on `OrderedBoundary2D`: it is
already the samples.

## Stored node contract

Each node-based `PeriodicCurve2D` owns immutable `float64` arrays:

```text
parameters             (N,)
points                 (N, 2)
first_derivatives      (N, 2)
second_derivatives     (N, 2)
third_derivatives      (N, 2) or None
speeds                 (N,)
tangents               (N, 2)
normals                (N, 2)
curvatures             (N,)
arc_length_weights     (N,)
```

The parameter nodes are the canonical uniform grid

```text
t_j = parameter_origin + j * period / N,   j = 0, ..., N-1,
```

with no repeated endpoint. Positions and derivatives are authoritative node
data. The remaining fields are derived during construction:

```text
speed               = |x'|
tangent             = x' / |x'|
normal              = (tangent_y, -tangent_x)       # outward for CCW
curvature           = cross(x', x'') / |x'|^3
arc_length_weight   = (period / N) |x'|
```

The component also stores its stable ID, name, period, parameter origin/step,
signed area, and provenance including optional SDF projection and fitting
residuals. Construction rejects nonuniform parameter nodes, nonfinite arrays,
zero speed, inconsistent shapes, and non-CCW solver geometry.

`OrderedBoundary2D` retains the component tuple and exposes flattened versions
of every node array together with component slices, offsets, component IDs,
node-to-component indices, and component-local node indices. Solvers never
need to infer topology from spatial proximity.

## Continuous producers

The `circle`, `ellipse`, `star`, and `fourier_curve` factories return
`PeriodicParameterization2D`. A parameterization is not a BIE boundary. Call
`.discretize(N)` on it, or group several producers and discretize them through
`OrderedBoundaryParameterization2D`.

Keeping the producer separate avoids two competing authoritative geometries:
node objects remain serializable, while exact/Fourier/spline representations
remain available for validation and generating another resolution.

## What geometry does not own

The package contains no:

- SDF, marching-squares, projection, or fitting implementation;
- Torch dependency or differentiation policy;
- material labels or transmission formulation;
- Kress, Alpert, panel, QBX, or Galerkin quadrature;
- pairwise singular weights;
- Maue/trigonometric hypersingular regularization; or
- MOD stand-off/`merge_distance` compatibility guess.

`arc_length_weights` are only the ordinary geometric `ds` weights. Kress
product integration uses target-source weights for a logarithmic factor; those
belong to the operator assembler. Likewise, even node count is a Kress-grid
condition rather than a smooth-geometry condition. `discretize()` accepts odd
counts unless a solver explicitly requests `require_even=True`.

For direct raw hypersingular operators, the solver must supply a valid
regularization such as a Maue identity and periodic differentiation. For a
kernel-difference route, the matching principal hypersingular terms must first
cancel, after which logarithmic product quadrature can be applied to the
remaining difference.

## Validation and limitations

`validate_periodic_parameterization` checks periodic closure through every
available derivative, independent derivative consistency, positive speed,
orientation, area, and sampled self-intersections.
`validate_ordered_parameterization` additionally checks component crossings,
containment, and clearance before node discretization.

These are high-resolution numerical diagnostics, not proofs about arbitrary
callables between every probe. Clockwise or phase-shifted input is never
silently normalized. Use `reversed()` or `with_parameter_shift()` explicitly;
a future extractor must record any such normalization.

## Future SDF adapter

The future path should end in the same node object:

```text
SDF grid/callable
  -> ordered zero contours
  -> topology and stable component IDs
  -> safeguarded projection to phi=0
  -> periodic Fourier or spline fit
  -> deterministic orientation and phase
  -> OrderedBoundaryParameterization2D + residual provenance
  -> validate_ordered_parameterization
  -> discretize(node_counts)
  -> OrderedBoundary2D                 # returned BIE boundary nodes
```

An extraction result may retain the fitted parameterization and diagnostics so
the caller can change resolution, but its solver-facing `boundary` member must
be the node-based `OrderedBoundary2D`.

## Example

```python
from ordered_boundary import (
    OrderedBoundaryParameterization2D,
    ellipse,
    validate_ordered_parameterization,
)

geometry = OrderedBoundaryParameterization2D(
    (ellipse((0.0, 0.0), 0.08, 0.04, component_id="target-0"),)
)
validate_ordered_parameterization(geometry, raise_on_error=True)

boundary = geometry.discretize(128, require_even=True)
# boundary is an OrderedBoundary2D and already owns all BIE node arrays.
# A Kress assembler builds pairwise logarithmic weights component by component.
```

## Numerical references

- R. Kress, “On the numerical solution of a hypersingular integral equation in
  scattering theory,” *Journal of Computational and Applied Mathematics* 61
  (1995), 345–360. [DOI](https://doi.org/10.1016/0377-0427(94)00073-7).
- S. Hao, A. H. Barnett, P. G. Martinsson, and P. Young, “High-order accurate
  Nyström discretization of integral equations with weakly singular kernels on
  smooth curves in the plane,” *Advances in Computational Mathematics* 40
  (2014), 245–272. [DOI](https://doi.org/10.1007/s10444-013-9306-3),
  [arXiv](https://arxiv.org/abs/1112.6262).
- J. Lai, H. Kobayashi, and L. Greengard, “A fast solver for multi-particle
  scattering in a layered medium,” *Optics Express* 22 (2014), 20481–20499.
  [DOI](https://doi.org/10.1364/OE.22.020481),
  [arXiv](https://arxiv.org/abs/1407.3868).
