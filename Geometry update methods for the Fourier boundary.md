# Geometry update methods for the Fourier boundary

Oct 15, 2026 · @Shiyuan Deng

## Introduction

The task of the geometry update is to compute new boundary coefficients, given the current boundary coefficients and the normal displacement coefficients.

A boundary can be represented using different parameterisations, hence multiple coefficients can represent the same boundary. (a pic here). The difference between them is the speed of the parameter as it goes along the boundary.

In theory this doesn't matter. Our forward solve only sees the boundary, hence any parameterisation that is not band-limited produces the same receiver trace.

In practice we crop the shape and normal modes to K and M, and naively computing z + hν creates a drift in parameterisation. The biggest disadvantage is that these limits then become subjective, i.e. they don't actually restrict the shape complexity.

We are trying to prevent this drift. This can be done using an arclength gauge, i.e. to use arclength as our new parameterisation after each geometry update; or, as later methods suggest, we can 'slide' the parameterisation along the boundary such that the coefficients move to the combination with even speed without changing the boundary. Finally we propose to formulate the unevenness of speed as a soft constraint, adding a penalty term to the data loss.

Sections 1 and 2 use the arclength gauge, section 3 the soft constraint, and section 4 the slide.

## 1. Centred update

This is the baseline which uses a nodal arclength refit.

&#91;image: image.png\]

```latex
c_p^{\mathrm{new}} = c_p + R_p(w_a) - R_p(0)
```

The motivation behind this is that c\_p is essentially non-gauged. Hence R\_p(0) which is gauged coefficients of the boundary, is different from c\_p.&#32;

The zero step shows why the update is centred. At a = 0 the push does nothing, so w\_0 = z, and the centred update returns the stored coefficients unchanged:

```latex
c_p^{\mathrm{new}}\big|_{a=0} = c_p + R_p(0) - R_p(0) = c_p
```

The drawback is that the centred update never removes the unevenness already in c\_p, so it stays near arclength only if c\_p already is. Hence we cannot provide clear physical meaning for the shape mode bandlimit.

## 2. Uncentred refit

Here we propose to use R\_p(w\_a) directly. The main gain is consistency: after every step, the stored coefficients are the arclength-gauged coefficients of the current boundary (up to the crop to band K), whatever path the inversion took.

So band K means the same thing at every step: the finest mode has wavelength L/K along the curve, the same everywhere, where L is the boundary length. With the centred update this resolution varies along the curve and depends on past steps.

As a side benefit, each step needs one regauge instead of two, since the centred update needs both R\_p(w\_a) and R\_p(0).

## 3. N-update with level penalty (Soft Constraint)

&#91;image: image.png\]

We add the speed unevenness to the data loss as a soft constraint:

```latex
\Phi_{\text{total}}(c) = \Phi_{\text{data}}(c) + \lambda_J \left\langle \left( \frac{J_\Gamma^2}{\langle J_\Gamma^2 \rangle} - 1 \right)^{2} \right\rangle
```

Here J\_Γ(t) = |z'(t)| is the speed, ⟨·⟩ is the mean over t, and λ\_J > 0 is the penalty weight. The penalty is the relative spread of squared speed around its mean, and it is zero only when the speed is uniform.

### What is computed

The stored curve and its unnormalised outward normal are

```latex
z(t) = \sum_{|p| \le K} c_p\, e^{ipt}, \qquad N(t) = -i\,z'(t) = \sum_{|p| \le K} p\,c_p\, e^{ipt}
```

N has length J\_Γ and points outward when the curve runs counterclockwise. Using N instead of the unit normal avoids dividing by J\_Γ, so every step stays a product of Fourier series.

N-update: move each point along N by a real amount η(t), slide it along the tangent z′ by a real amount τ(t), then crop back to band K:

```latex
z^{\mathrm{new}} = \Pi_K\big[\, z + \eta\,N + \tau\,z' \,\big]
```

Here η and τ are real Fourier series of band M, and Π\_K keeps the modes with |p| ≤ K. The plain N-update is τ = 0 and η = h/J̄, where h is the requested normal push and J̄ = L/2π is the mean speed.

In coefficients the products are convolutions, so the update is exact before the crop:

```latex
c_q^{\mathrm{new}} = c_q + \sum_{|k| \le M} \big(\hat\eta_k + i\,\hat\tau_k\big)\,(q-k)\,c_{q-k}, \qquad |q| \le K
```

Here η̂\_k and τ̂\_k are the Fourier coefficients of η and τ. Since both are real, the coefficient at −k is the conjugate of the one at k.

The proposal: the LM unknowns are η̂ and τ̂, and each trial is scored by Φ\_total above. The η part moves the boundary. The τ part only re-spaces points along it, apart from a small boundary change from the crop (0.2–3% of the slide in our tests).

Two caveats. The penalty acts on the level of unevenness, not its change, so it is nonzero even for a zero step and favours rounder shapes. The plain N-update moves the boundary by h J\_Γ/J̄, which equals h only at arclength; without τ and the penalty it drifts (it failed on kite, C and hook).

## 4. Slider

&#91;image: image.png\]

We still update the boundary using z=z+hv. We get the coefficients that represent a curve of non-even speed. We then slide this coefficient vector directly within the coefficient space, to keep the speed as even as it was before the step.

### What is computed

The slider turns the requested normal push h(t; a) = Σ a\_l ψ\_l(t) into one linear coefficient step, dc = A a. It asks for two things at once: the boundary moves normally by h, and the relative speed change is the same everywhere, so all gaps between points scale by one factor.

For a coefficient step dc, with curve change dz, the two linearised quantities are

```latex
v_n = \mathrm{Re}\big(\bar\nu\,dz\big), \qquad \frac{dJ}{J_\Gamma} - \Big\langle \frac{dJ}{J_\Gamma} \Big\rangle, \qquad dJ = \mathrm{Re}\big(\bar{\hat T}\,dz'\big)
```

v\_n is the normal velocity, ν = −i z′/J\_Γ is the unit outward normal, T̂ = z′/J\_Γ is the unit tangent, and ⟨·⟩ is the arclength-weighted mean.

Write dc as a real vector of length 4K+2: real parts, then imaginary parts. Sample at Q points t\_j with arclength weights w\_j = J\_Γ(t\_j)·2π/Q. This gives three matrices, each row scaled by √w\_j: B maps dc to v\_n, U maps dc to the uneven speed change, and H maps a to h(t\_j). The slider solves

```latex
dc = \arg\min_{dc}\ \|B\,dc - H a\|^2 + \xi\,\|U\,dc\|^2 \;\Rightarrow\; dc = A\,a, \qquad A = \big(B^\top B + \xi\,U^\top U\big)^{-1} B^\top H
```

ξ ≥ 0 weights even spacing against exact normal motion. ξ = 0 is a plain least-squares normal move, which drifts; we start with ξ = 10.

One LM iteration: build B, U and H at the current c, form A, use F\_a = F′(c) A as the Jacobian in a, then

```latex
a = -\big(F_a^\top F_a + \lambda I\big)^{-1} F_a^\top \big(F(c) - F_{\mathrm{obs}}\big), \qquad c^{\mathrm{new}} = c + A\,a
```

F(c) is the forward-solve data, F′ its Jacobian in c, F\_obs the measured data and λ the LM damping. There is no resampling, no refit and no crop.

What it does: the step is exactly linear in a, and a zero step gives zero change. The penalty is on the change of unevenness, not its level, so it does not pull the shape. It holds the unevenness of c (about 9% in the kite test) rather than lowering it, and each normal move falls 3–6% short. An occasional refit resets the unevenness.
