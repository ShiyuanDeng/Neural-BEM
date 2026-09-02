# Ordered Nyström solver tests

This directory tests the opt-in `gpr_bem_mod.ordered_nystrom` forward
candidate. Unlike `pytest/ordered_boundary/` and
`pytest/sdf_to_ordered_boundary/`, these tests assemble Helmholtz Müller
operators, solve the coupled boundary system, and measure genuine
operator/solver errors.

The fast suite covers:

- isolation from oracle, archived solver, SDF, and QBX numerics;
- the `PeriodicCurve2D`-only geometry seam and weight ownership;
- the periodic Kress logarithmic rule and the near/direct kernel overlap;
- analytic Fourier–Bessel actions of all four circle difference blocks;
- the project block signs, identity terms, and zero-contrast limit; and
- boundary traces and receiver fields against the penetrable-cylinder Mie
  series, including a resolved 8 GHz case at `N = 128`.

Run it with:

```bash
PYTHONPATH=solvers python -m pytest -q pytest/ordered_nystrom
```

The tolerances are regression and correctness gates, not a claim that every
supported geometry has been accepted. Longer grid, bandwidth, noncircular,
and runtime sweeps belong under `results/ordered_boundary_nystrom/`; dense
operator matrices should not be committed there.
