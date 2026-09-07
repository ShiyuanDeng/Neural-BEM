# Legacy known-shape-family controls

These are the parametric inverse runs previously grouped under
`results/inverse/method_b`, now preserved in
[`results/legacy/known_shape_family_parameter_inverse`](../../results/legacy/known_shape_family_parameter_inverse/README.md).
They are separate from both current inverse pipelines.

The optimizer changes a few parameters of an analytic or fixed-feature implicit
field. Method B converts its zero contour into a smooth ordered boundary;
MOD or Kress predicts measurements; parameter finite differences and damped
Gauss–Newton update those same parameters. No full MLP is trained during these
inverse steps.

| Control | Unknowns | Supplied shape information |
|---|---:|---|
| Circle | Center x/y and radius: 3 | Always a circle |
| Ellipse | Center x/y and two axes: 4 | Always an ellipse; rotation fixed; circle target belongs to this family |
| Star | Center x/y, mean radius, amplitude and rotation: 5 | Specified cosine-star formula with five lobes copied from target configuration |
| Random features | Center x/y, radius and four output weights: 7 | Fixed radial tanh features around a circle; hidden features do not train |

The target's shape family is supplied; its unknown numerical parameter values
are inferred from observations. For example, the star run recovers amplitude
and rotation within a five-lobe family, rather than discovering five lobes.
That prior explains why these videos can look much cleaner than full-neural
reconstruction. A successful fit here validates parameter estimation and the
conversion/forward solver within the declared family.

“Implicit field” describes how a boundary is represented as a zero contour.
It does not imply a neural network. Method B is the conversion algorithm;
it does not decide which variables the inverse can change.

The current [Implicit MLP + Method B](../pipelines/implicit_mlp.md) pipeline
updates trainable neural weights. [Explicit Radial Fourier](../pipelines/explicit_radial_fourier.md)
updates a radial Fourier coefficient vector. Its retained `legacy_strict`
option controls neural fitting to the explicit curve, not shape ownership.
The archived controls above are neither of those full inverse pipelines.

Original videos, measurements, configurations and commands remain in the
[archive](../../results/legacy/known_shape_family_parameter_inverse/README.md).
Use the [reproduction guide](../reproduction.md) for optional fresh control
runs; replaying a historical command under changed defaults is not an exact
reproduction of the old code.
