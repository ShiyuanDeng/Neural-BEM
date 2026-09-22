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
at commit `bda24bddbf4562497280b671bc174ef891b47c6b` (2024-07-09) to settle
settings the manuscript states loosely or not at all. The routines that matter
for this pipeline are `src/+rla/inverse_solver.m`,
`src/+rla/update_inverse_iterate.m`, `src/+rla/update_geom.m`, and the driver
`examples/inverse_solver_scripts/ex1_plane.m`.

Where the code and the manuscript disagree, the
[audit](../../../experiments/shape_continuation/PAPER.md) follows the code and
says so: the code is what produced the published figures. The repository solves
sound-soft/hard/impedance problems, so its drivers are not the Figure 1
transmission case; its optimizer settings are read as the authors' conventions,
not as recovered Figure 1 inputs.
