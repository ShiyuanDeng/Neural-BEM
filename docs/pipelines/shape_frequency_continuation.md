# Isolated shape and frequency continuation

The working research entry point is
[`experiments/shape_continuation`](../../experiments/shape_continuation/README.md).
It follows the boundary-inversion structure in Borges, Rachh and Greengard,
*On the robustness of inverse scattering for penetrable, homogeneous objects
with complicated boundary*, Inverse Problems 39 (2023) 035004,
[DOI](https://doi.org/10.1088/1361-6420/acb2ec).

```text
Cartesian Fourier curve, parameterized by arclength
    → ordered boundary nodes
    → dense nodal Müller/Kress, plane-wave illumination
    → complex scattered fields and normal-shape Jacobian
    → single-frequency GN/SD update + geometry/curvature checks
    → reparameterize and accept only a decreasing candidate
    → hand the curve to the next frequency/update band
```

The normal update band, curve storage band, and quadrature node count are
separate. There is no polar-angle restriction. Complex Fourier coefficients
are an equivalent storage notation for Cartesian Fourier geometry; they do
not select the native Fourier–Galerkin Müller solver.

The only project dependencies are `ordered_boundary`, `gpr_bem_kress`, and its
`periodic_kress` dependency. The former inverse drivers, SDF/MLP machinery,
topology controller, automatic runtime selection, and modal research packages
are absent from the import graph. Production defaults remain unchanged.

The package README owns the API, exact commands, paper-to-code differences,
and limitations. The [qualification record](../../results/validation/shape_continuation/README.md)
owns measurements. The pilot is a single-component, known-contrast,
lossless/equal-density, full-aperture problem in dimensionless coordinates.
It is ready for controlled continuation development; the paper's complete
high-frequency and complicated-boundary results have not been reproduced.
