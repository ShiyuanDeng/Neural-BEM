# Multi-cylinder reference solver

This package is an independent forward oracle for two-dimensional transmission
scattering by disjoint circular cylinders made from one material. It does not
import Kress, IBIM/MOD, SDF, or ordered-boundary assembly code.

For cylinder `p`, the exterior scattered field is represented by

```text
sum_n a[p,n] H_n^(1)(k_e r_p) exp(i n theta_p).
```

The exact single-circle transmission coefficient maps the total regular
incident coefficient at a cylinder to its outgoing coefficient. Graf
translations couple outgoing modes on one cylinder to regular modes on every
other cylinder. Thus the solved system is

```text
a[p,n] - R[p,n] sum(q != p, m) T[p,q,n,m] a[q,m]
    = R[p,n] incident[p,n].
```

The implementation scales each unknown by its outgoing basis value on that
cylinder, `H_n^(1)(k_e radius[p])`. This boundary-normalized basis prevents the
factorial growth and decay of raw high-order Hankel coefficients from making a
well-resolved physical problem look ill-conditioned.

Only exterior waves couple distinct components. Each disconnected interior is
eliminated locally through `R[p,n]`, which makes this formulation useful as an
independent check of multi-component boundary-integral block assembly.

The line-source normalization is `0.25j * H_0^(1)(k r)`, matching the repository
forward solvers. The high-level field functions use paired sources and
receivers; `MultiCylinderSolution` also evaluates a full receiver-by-source
matrix. `converge_multicylinder_scattered_field` raises if successive mode
orders fail to meet its configured tolerance.

Scope is deliberately narrow: circular, strictly disjoint components; one
exterior and one shared interior wavenumber; scalar TMz transmission with
continuous field and normal derivative; exterior sources and receivers only.
It is a validation oracle, not part of the differentiable inverse pipeline.
