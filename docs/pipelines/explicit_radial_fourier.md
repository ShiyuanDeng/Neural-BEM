# Explicit Radial Fourier inverse and representation policies

Status reviewed on 2026-09-07. This implemented family provides a controlled
single-object reconstruction and isolates failures in fitting an MLP to a
known curve. Canonical radial recovery works on recorded cases, with MLP
representation delivery assessed separately. The implemented
[Implicit MLP + Method B](implicit_mlp.md) still fails current
recovery acceptance. No matched benchmark between these pipelines has been
completed.

## Implemented state and forward path

Preferred command: [`run_explicit_radial_fourier_inverse.py`](../../run_explicit_radial_fourier_inverse.py).
The old `run_mlp_sdf_inverse_comparison.py` command remains a compatibility
entry point for this same explicit-curve algorithm. Neural-owned adjoint
updates use [`run_implicit_mlp_inverse.py`](../../run_implicit_mlp_inverse.py).

This family's active results are under `results/inverse/radial_fourier/`,
including `representation_policies/`, `shape_material/` and `neural_metric/`.
The [Legacy known-shape-family controls](../../results/legacy/known_shape_family_parameter_inverse)
have their own archive. They estimate a few controls in prescribed families;
their results are separate from both current inverse pipelines.

```text
initial implicit contour --Method B--> ordered initial curve
  -> one-time projection into radial Fourier coefficients
  -> direct radial curve -> MOD or Kress -> measured residual
  -> finite-difference coefficient Jacobian and damped step
  -> validated accepted radial coefficients
  -> MLP fitting / export according to the selected policy
```

The authoritative state is a center, mean radius and radial cosine/sine
coefficients for modes 2 through K. Mode one is fixed to zero because exact
Cartesian center translation supplies those two degrees of freedom. There
are `1 + 2K` controls: eleven at K5. A positive radial graph is star-shaped
and has one component. Network width does not enlarge this shape space.
See [curve state and updates](../../solvers/sdf_inverse/curve_updates.py).

The continuous curve is rebuilt from those coefficients without successive
node refits. Each direct forward probe bypasses SDF extraction and Method B;
the same accepted radial state supplies the next Jacobian. Method B remains
in initial implicit-contour conversion and MLP representation audits. The
one-time radial projection also changes an initial ellipse slightly and must
be recorded when comparing initializations.

[The radial comparison driver](../../run_mlp_sdf_inverse_comparison.py)
explicitly selects radial retraction and defaults to cumulative low-to-high
frequency continuation. Joint full-band and progressive-mode continuation
remain selectable experiments. Frequency stages have different objectives;
their raw losses should not be plotted as if they shared one normalization
and dataset. Node count, radial mode K and the Cartesian Method-B bandwidth
are separate settings.

The library's default `direct_curve_retraction="normal"` is a retained
direct-normal-update option. The driver overrides it with `"radial_fourier"`.
Successive low-order normal updates do not define a fixed low-order radial
shape family; this distinction explains why historical normal-update results
are catalogued separately.

## MLP policies and entry points

| Policy | Accepted reconstruction state | Neural work | Entry point |
|---|---|---|---|
| `legacy_strict` | Radial coefficients | Initialization fit and per-step fitting/audits; representation can reject a candidate or prevent successful completion under this policy | Explicit Radial Fourier driver; also representation ablation |
| `curve_only` | Same radial coefficients | No neural queries or fitting during reconstruction; no SDF delivery requested | Representation ablation / library |
| `export_only` | Same radial coefficients | Curve-only reconstruction, then one separately gated final smooth-target fit/export | Representation ablation / library |

`legacy_strict` is the Explicit Radial Fourier driver's fitting policy. The
radial coefficients remain the accepted geometry; its MLP represents that
curve and supplies an audit. The CLI does not expose a distillation
policy switch. The separate
[representation ablation](../../run_sdf_representation_ablation.py) exposes
`short` and `saved-star` profiles and the three policies. It runs continuation
before the single export, so export is not repeated at stage boundaries.

[Neural distance fitting](../../solvers/sdf_inverse/neural.py) defaults to
polygon-distance supervision. Smooth-curve targets are an explicit option
requiring a matching continuous producer. Export trains a copy and commits
it only after its own checks. A failed export leaves a valid canonical
reconstruction and an incomplete requested SDF delivery, with absent
exported-contour quantities reported as absent.

## Saved evidence and its limits

| Run | Scene / date recorded | Outcome and interpretation |
|---|---|---|
| [Radial continuation K5](../../results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/summary.md) | Wrong ellipse → five-lobe star; 2026-09-04 | 44 accepted steps; canonical training/holdout relative errors `1.068e-8` / `1.339e-8`; `legacy_strict` stop `representation_limited_stationary` |
| [Saved-star policy ablation](../../results/inverse/radial_fourier/representation_policies/saved-star-20260905/summary.md) | Same recorded star configuration; 2026-09-05 | All policies produce identical recorded canonical coefficients and 44 updates; `legacy_strict` and final-only representation delivery fail |
| [Short policy contract](../../results/inverse/radial_fourier/representation_policies/short-final-20260905/summary.md) | Wrong ellipse → circle; 2026-09-05 | Four-update contract exercise; not a converged reconstruction benchmark |
| [Frozen neural metric comparison](../../results/inverse/radial_fourier/neural_metric/comparison-20260906/README.md) | Circle and star; recorded 2026-09-06 | Three frozen neural metrics lag the tested explicit controls; all star arms exhaust their 15-update budget |

The saved-star ablation records reconstruction times of about 229.74 s
(`legacy_strict`), 81.61 s (curve-only) and 81.62 s (export-only), with 8.41 s more for
the failed final export. It isolates fitting overhead in this radial-owned
loop. The MLP fitted under `legacy_strict` has approximately `0.329 mm` curve drift and `0.004327`
holdout relative field error even though the canonical curve is extremely
accurate. Neither the timing result nor unchanged radial coefficients settle
the effectiveness of Implicit MLP + Method B.

The [neural metric driver](../../run_neural_metric_comparison.py) is another
distinct experiment: it uses a discrete Kress objective adjoint, projects
directions into a radial chart and compares identity, Sobolev and a metric
computed from an initialized network's parameter Jacobian. The network is
not trained and is not queried during reconstruction. This is neither MLP
distillation nor direct neural-weight inversion; the result only qualifies
the tested frozen metric and budgets.

These results concern declared synthetic, homogeneous full-space 2-D TMz
problems. The successful star is exactly representable in K5, with known
material and calibrated observations. Good field refinement can also occur
at the wrong recovered shape. Keep canonical reconstruction, actual MLP
representation, independent holdout prediction and numerical refinement in
separate result columns. Historical run names and successful progress exit
codes are not convergence certificates.
