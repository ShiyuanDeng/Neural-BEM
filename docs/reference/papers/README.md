# Papers used by the continuation pipeline

[Borges, Rachh and Greengard — On the robustness of inverse scattering for
penetrable, homogeneous objects with complicated boundary (PDF)](borges_rachh_greengard_2210.11607v1.pdf).

This is the complete, unmodified 24-page **arXiv v1 author manuscript**, the
version used in our [paper audit](../../../experiments/shape_continuation/PAPER.md).
It is the preprint corresponding to *Inverse Problems* 39 (2023), 035004,
[DOI: 10.1088/1361-6420/acb2ec](https://doi.org/10.1088/1361-6420/acb2ec).

- Downloaded on 2026-09-22 from [arXiv PDF](https://arxiv.org/pdf/2210.11607v1).
- [Version and bibliographic record](https://arxiv.org/abs/2210.11607v1).
- File size: 14,453,610 bytes.
- SHA-256: `255af58b961c7c9af8292e5b06e665e18ea06ccd22dc750f7894472ca033307c`.

The [pipeline guide](../../pipelines/shape_frequency_continuation.md) links the
implementation and its qualification records. The PDF was added at the user's
explicit request to keep the paper with the documentation.

## Reference implementation

The authors' MATLAB/Fortran code is
[flatironinstitute/inverse-obstacle-scattering2d](https://github.com/flatironinstitute/inverse-obstacle-scattering2d),
identified by the user on 2026-09-22. It is **not** vendored here; it was read
at commit `bda24bddbf4562497280b671bc174ef891b47c6b` (2024-07-09) to audit
settings the manuscript states loosely or differently. The routines that matter
for this pipeline are `src/+rla/inverse_solver.m`,
`src/+rla/update_inverse_iterate.m`, `src/+rla/update_geom.m`,
`src/+rla/rla_inverse_solver.m`, and the example drivers
`examples/inverse_solver_scripts/ex1_plane.m` (Dirichlet) and
`tests/driver_charlie_transmission.m` (transmission, Charlie cavity).

The [audit](../../../experiments/shape_continuation/PAPER.md) distinguishes
inspected code conventions, manuscript settings and our implementation choices.
The repository includes transmission as well as sound-soft/hard/impedance
problems. Neither cited driver has been identified as the exact Figure 1
glider input, and the Figure 1 plotting path has not been recovered. In
particular, the transmission driver's `nppw=30` is for data generation, not its
inverse resolution. The [2026-09-22 Codex review](../../iterations/shape_frequency_continuation/iteration_03/02_proposals/01_codex_review.md)
records pinned source links, confirmed optimizer fixes and remaining fidelity
concerns. Attribution to this repository alone does not establish which version
or settings produced the published figure.
