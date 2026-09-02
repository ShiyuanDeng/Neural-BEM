# `gpr_bem_kress`

This is the ordered periodic Kress/Nyström Müller solver. It is a sibling of
`gpr_bem_mod`, not a MOD backend.

Its geometry boundary is deliberately narrow:

```text
PeriodicCurve2D
  -> cancellation-safe Delta V/K/Kp/T assembly
  -> direct unsquared Muller solve
  -> explicit exterior receiver operator C = [D, -S]
  -> full source x receiver fields
```

The package does not import an SDF extractor, fitting method, MOD, gprMax, or
either Nyström oracle. Upstream orchestration freezes an SDF-derived
`PeriodicCurve2D` for a forward/adjoint pair. The explicit `C` matrix and the
actual assembled system matrix are retained so a future adjoint can apply
`C.conj().T` and solve with `A.conj().T` rather than recreating either
operator. Forward snapshots also retain the typed assembly/solve settings and
material values needed to replay the accepted primal discretization.

The ACC measurement is not the full receiver matrix. If `P` selects the
source/receiver diagonal, its data path is

```text
y = P(C q + u_inc),       Psi = P^H psi,       A^H lambda = C^H Psi.
```

Here `P^H` scatters a paired residual vector onto the diagonal of a full
`(num_sources, num_receivers)` dual. Passing that vector directly to
`ExteriorReceiverOperator.apply_adjoint` would instead mean one RHS and is not
the ACC adjoint. Pair selection therefore belongs in a future typed
measurement/adjoint context, not inside this general receiver operator.

A geometry adjoint additionally needs a legal fixed-grid curve direction that
perturbs `gamma`, `gamma_theta`, and the remaining jets coherently, deriving
normal, speed, and `ds` changes from the same direction. Point-only
perturbations with frozen normals or weights are invalid. The returned shape
quantity must say whether it is a nodal directional derivative or an
unweighted normal density so arc length is applied exactly once.

The current implementation supports one smooth, simple, counterclockwise
component in lossless nonmagnetic media, with safely separated exterior
sources and receivers. It remains direct-import only and is not registered in
`solver_select` or any operational inverse pipeline.
