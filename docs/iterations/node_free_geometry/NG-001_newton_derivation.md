# Multiplication-only speed construction: derivation for a follow-up

2026-10-11. Mathematical proposal prompted by NG-001's recorded binomial
range/degree failures. This note alone does not register or claim a measured
replacement. The full initial replay determines the follow-up panel and plan.

## Literature and what is being adapted

[Higham and Al-Mohy, *Computing Matrix Functions*, section 6,
equations (6.18)–(6.20)](https://eprints.maths.manchester.ac.uk/1406/1/covered/MIMS_ep2010_18.pdf)
describe inverse-root Newton iteration, convergence regions and the need for
stable formulations in matrix arithmetic. The article was downloaded and its
full text inspected. The author also describes the multiplication-only sign
iteration and its relation to square roots in
[What Is the Matrix Sign Function?](https://nhigham.com/2020/12/15/what-is-the-matrix-sign-function/).

The application here is a commutative scalar function of angle, composed in
Laurent coefficients. Matrix convergence and stability theorems do not certify
a cropped coefficient iteration. Full residuals remain necessary.

## Scalar mechanism and initialization

Let S=|p'|² and let the coefficient range proposer enclose 0<a≤S≤b.
Set c=γ[S]₀, where γ is a locally fixed power of two, at least two, selected
so c≥b. Initialize u₀=c⁻¹ᐟ². Without cropping, iterate

uₙ₊₁ = uₙ(3−S uₙ²)/2.

Writing eₙ=1−S uₙ² gives the exact identity

eₙ₊₁ = eₙ²(3+eₙ)/4.

Initially 0≤e₀≤1−a/c<1. Hence uₙ remains positive, eₙ decreases to zero,
and convergence eventually becomes quadratic. Unlike expansion about the
mean, this initialization does not require b<2[S]₀. Choose the finite
iteration count from this scalar recurrence with a declared residual target
and count budget. This estimate selects a proposer, not an acceptance proof.

## Finite map and actual directional derivative

Let C_B denote a crop and * a padded linear convolution. One finite step is

vₙ=C_B(S*(uₙ*uₙ)), gₙ=3−vₙ,
uₙ₊₁=C_B(uₙ*gₙ)/2.

Compute q=C_B(S*u) for the speed. Every crop and grouping above is part of
the implemented map: crops make multiplication nonassociative. Do not replace
its derivative with the continuous inverse-root derivative.

For a real Cartesian direction dp,

dS=2 Re(dp' conjugate(p')), dc=γ[dS]₀,
du₀=−u₀ dc/(2c),
dvₙ=C_B(dS*(uₙ*uₙ)+2S*(uₙ*duₙ)),
duₙ₊₁=C_B(duₙ*gₙ−uₙ*dvₙ)/2,
dq=C_B(dS*u+S*du).

The products inside dv must follow the same intermediate crop as v. The
integer scaling and count branches are locally fixed while differentiating.
At a branch boundary the finite algorithm can have a kink; independent
central differences must detect any material discrepancy. The subsequent
mean-speed normalization, anchored primitive, phase recurrence and output
contractions retain their existing complete derivatives.

## Acceptance and falsifiable predictions

Compute the full, uncropped residuals q²−S and 1−S u², including all modes
beyond B. Require the same NG-001 tolerances and positive q. Select the positive
inverse-root branch explicitly. The existing phase residual and independent
working-band comparison remain active. These are float64 construction
receipts; directed admissibility is a separate claim.

Prediction: range/degree refusals should disappear for positive-speed curves
whose nonlinear tails fit the working band, and high-degree successful cases
should become cheaper. This is falsified by unchanged scalar refusals,
unqualified residuals or a failed complete tangent. Fourier tails, an
unproved positive speed range and geometric crossings are not repaired by
quadratic scalar convergence. They remain independent failure mechanisms.
