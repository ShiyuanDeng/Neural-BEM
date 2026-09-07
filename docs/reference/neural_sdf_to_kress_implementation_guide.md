# Implementation Guide: Neural SDF → Smooth Parametric Boundary → Kress Geometry

## Purpose and authority

This file is a **Codex-facing implementation companion** to the report:

> **From Neural SDFs to Kress-Ready Smooth Closed Boundaries**

Use the report for literature background, rationale, alternatives, and references. Use this guide as the **authoritative first-pass scope, software contract, comparison design, and implementation order**.

The immediate task is **not** to implement a full boundary-integral solver. It is to implement and compare a small number of methods that convert a two-dimensional neural SDF or implicit field into a continuous, smooth, ordered, periodic boundary representation suitable for later Kress quadrature.

The central pipeline is

\[
F_\theta
\;\longrightarrow\;
\Gamma_\theta=\{x:F_\theta(x)=0\}
\;\longrightarrow\;
\gamma(t)
\;\longrightarrow\;
\{\gamma(t_j),\gamma'(t_j),\gamma''(t_j),n(t_j),J(t_j)\}
\;\longrightarrow\;
\text{Kress quadrature}.
\]

Here:

- \(F_\theta:\mathbb R^2\to\mathbb R\) is the neural SDF or implicit field.
- \(\Gamma_\theta\) is the zero set as an **unparameterized geometric set**.
- \(\gamma:[0,2\pi)\to\mathbb R^2\) is a **continuous periodic parameterization** whose image approximates one connected component of \(\Gamma_\theta\).
- \(t_j=2\pi j/N\), with even \(N\), are uniform nodes in the final computational parameter used by Kress.

A marching-squares polygon is useful for discovering and ordering the zero set, but it is **not** the final Kress geometry. The main implementation target is the object representing \(\gamma\).

---

# 1. Initial scope

Implement the following now:

1. A common interface for evaluatable two-dimensional implicit fields.
2. A common continuous `ParametricBoundary2D` interface for \(\gamma\).
3. A common `KressGeometry2D` sampled representation.
4. One shared contour-discovery and zero-set-projection front end.
5. Three SDF-to-\(\gamma\) methods:
   - **Method A — simple baseline:** periodic cubic spline.
   - **Method B — strong classical baseline:** bandlimited Fourier least-squares fit.
   - **Method C — best shot:** SDF-constrained Fourier optimization initialized by Method B.
6. Geometry-fidelity, topology, parameterization, and Kress-readiness metrics.
7. Analytic tests and a comparison script.

Do not implement in this phase:

- a full BIE solver;
- Helmholtz kernels or Müller assembly;
- learned SDF-to-curve decoders;
- differentiable marching squares;
- MeshSDF, DMTet, FlexiCubes, Analytic Marching, or Marching Neurons;
- neural-SDF Hessian-based curvature as the production geometry source;
- close-evaluation or near-touching-component quadrature;
- a general topology-changing optimizer.

The initial benchmark should emphasize one smooth, simple, closed component. The data model should nevertheless represent multiple components as **one independent \(\gamma_\ell\) per component**, rather than concatenating them into one discontinuous curve.

---

# 2. The exact software meaning of the pipeline

## 2.1 Input: implicit field

Define or adapt the repository's existing SDF interface rather than duplicating it unnecessarily.

```python
class ImplicitField2D(Protocol):
    """A scalar implicit field whose target boundary is value(x) == 0."""

    def value(self, xy: Array) -> Array:
        """xy shape (..., 2); return shape (...,)."""

    def gradient(self, xy: Array) -> Array:
        """xy shape (..., 2); return shape (..., 2)."""
```

Required documented conventions:

- physical coordinate order is `(x, y)`;
- sign convention, preferably `F < 0` inside and `F > 0` outside;
- dtype/device behavior;
- whether the field is a true SDF or merely a regular implicit level-set function;
- an explicit physical bounding box supplied by the caller.

Do not assume \(\|\nabla F\|=1\). Projection must work for a generic regular implicit function.

## 2.2 Intermediate geometric set

The mathematical zero set is

\[
\Gamma_\theta=\{x\in\mathbb R^2:F_\theta(x)=0\}.
\]

This is not yet ordered or parameterized. Contouring produces discrete ordered approximations to its connected components. These points are initialization and diagnostic data only.

## 2.3 Main output: continuous parameterized boundary

For each component, return a continuous object representing

\[
\gamma(t)=\begin{pmatrix}x(t)\\y(t)\end{pmatrix},
\qquad t\in[0,2\pi),
\qquad \gamma(t+2\pi)=\gamma(t).
\]

The object must derive its values and derivatives from its authoritative coefficients or spline representation. It must not be only an `N x 2` point array.

```python
class ParametricBoundary2D(ABC):
    period: float = 2.0 * math.pi

    @abstractmethod
    def position(self, t: Array) -> Array:
        """Return gamma(t), shape (..., 2)."""

    @abstractmethod
    def derivative(self, t: Array, order: int = 1) -> Array:
        """Return d^order gamma / dt^order, shape (..., 2)."""

    def sample_uniform(self, n: int) -> "KressGeometry2D":
        """Sample at t_j = 2*pi*j/n. Require even n."""

    def validate(self, config: "BoundaryValidationConfig") -> "BoundaryDiagnostics":
        """Dense geometry and parameterization checks."""
```

Required semantic properties:

- one object represents one connected component;
- the parameter interval is always `[0, 2*pi)`;
- the endpoint is identified periodically and is not duplicated in uniform samples;
- orientation is explicit;
- Phase 1 obstacle curves should be counterclockwise;
- for a counterclockwise curve, the outward normal is the right-hand normal.

A container for multiple components may be

```python
@dataclass(frozen=True)
class BoundarySet2D:
    components: tuple[ParametricBoundary2D, ...]
```

Do not force disconnected components into a single `gamma`.

## 2.4 Kress-facing sampled output

The downstream Kress implementation should consume a sampled immutable object, not the SDF, marching polygon, fitting optimizer, or raw contour connectivity.

```python
@dataclass(frozen=True)
class KressGeometry2D:
    n: int
    t: Array                 # (N,), exactly 2*pi*j/N
    dt: float                # 2*pi/N
    points: Array            # gamma(t_j), (N, 2)
    d1: Array                # gamma'(t_j), (N, 2)
    d2: Array                # gamma''(t_j), (N, 2)
    speed: Array             # J_j = |gamma'(t_j)|, (N,)
    tangent: Array           # d1 / speed, (N, 2)
    outward_normal: Array    # (y', -x') / speed for CCW, (N, 2)
    curvature: Array         # signed scalar curvature, (N,)
    log_speed: Array         # log J_j, useful in the Kress diagonal limit
    ds_weights: Array        # dt * J_j, ordinary trapezoidal line weights
```

Use

\[
J(t)=|\gamma'(t)|,
\qquad
\tau(t)=\frac{\gamma'(t)}{J(t)},
\]

and, for counterclockwise orientation,

\[
n(t)=\frac{1}{J(t)}\begin{pmatrix}y'(t)\\-x'(t)\end{pmatrix}.
\]

The signed curvature may be stored using

\[
\kappa(t)=
\frac{x'(t)y''(t)-y'(t)x''(t)}
{\bigl(x'(t)^2+y'(t)^2\bigr)^{3/2}}.
\]

Document the curvature sign convention. The basic logarithmic Kress split fundamentally needs uniform \(t_j\), \(\gamma(t_j)\), and \(J_j\). Particular BIE kernels additionally use normals and sometimes second derivatives or curvature, so the common adapter should provide all of them.

---

# 3. What Kress requires from gamma

Kress singularity splitting uses

\[
\log|\gamma(t)-\gamma(s)|
=
\frac12\log\left(4\sin^2\frac{t-s}{2}\right)
+
q_\gamma(t,s),
\]

with

\[
q_\gamma(t,s)
=
\log\frac{|\gamma(t)-\gamma(s)|}
{2|\sin((t-s)/2)|}.
\]

For a regular smooth parameterization,

\[
q_\gamma(t,t)=\log|\gamma'(t)|.
\]

Therefore the converter must produce a curve satisfying, numerically:

1. **Periodic closure**
   \[
   \gamma(t+2\pi)=\gamma(t).
   \]

2. **Periodic derivatives** at least through the derivative order used by the kernel treatment.

3. **Regularity**
   \[
   \min_t|\gamma'(t)|>0.
   \]

4. **Simplicity:** no self-intersection and no duplicate nonlocal parameter pairs.

5. **Sufficient smoothness and resolution:** the smooth Kress remainder must be resolved on a uniform periodic grid.

6. **Uniform computational nodes**
   \[
   t_j=2\pi j/N,
   \qquad j=0,\ldots,N-1,
   \]
   with even \(N\).

Uniform physical arc length is advantageous but not formally required. Kress requires uniformity in the final computational parameter. Arc-length reparameterization is the default because it reduces crowding and makes \(J(t)\) nearly constant.

Important separations:

- the SDF locates and constrains the boundary;
- the final curve representation supplies \(\gamma'\), \(\gamma''\), normals, and curvature;
- Kress consumes uniform samples of that final curve;
- do not finite-difference the marching polygon to obtain production derivatives;
- do not use neural Hessians as the default curvature source.

---

# 4. Shared front end for all compared methods

For the initial comparison, keep this front end identical across Methods A, B, and C. Otherwise extraction/topology differences become confounded with representation differences.

## 4.1 Evaluate and contour

Inputs:

- `field: ImplicitField2D`;
- physical bounding box `[xmin, xmax] x [ymin, ymax]`;
- grid resolution or `(nx, ny)`;
- zero level, normally `0.0`.

Procedure:

1. Evaluate `field.value` on the Cartesian grid.
2. Extract zero contours using the repository's existing contouring dependency, or a tested marching-squares implementation.
3. Convert array-index coordinates back to physical `(x, y)` coordinates carefully.
4. Assemble one ordered closed loop per connected component.
5. Remove a repeated terminal point from the internal cyclic representation.
6. Reject open contours or contours touching the bounding box.
7. Record all components; do not silently select the largest component.
8. For the Phase 1 single-component benchmark, fail clearly when the number of components is not one.

The comparison script should vary grid resolution independently from curve resolution.

## 4.2 Orient and validate the polygon

For each loop:

1. Compute signed polygon area.
2. Reverse the order if needed to obtain counterclockwise orientation.
3. Check that each contour vertex has the expected cyclic connectivity.
4. Check nonadjacent polygon segments for intersection.
5. Record raw perimeter, signed area, point count, and grid resolution.

## 4.3 Resample by cumulative chord length

Do not use the marching output array index directly as the parameter. First resample the loop approximately uniformly in polygonal arc length.

For ordered points \(p_j\), define cumulative length

\[
s_0=0,
\qquad
s_j=\sum_{\ell<j}\|p_{\ell+1}-p_\ell\|,
\]

with the closing segment included. Interpolate periodically to obtain a configurable number \(M\) of approximately equally spaced initializer points.

## 4.4 Project every initializer onto the zero set

Use safeguarded Newton/closest-point correction:

\[
p^{(r+1)}
=
p^{(r)}
-
\frac{F_\theta(p^{(r)})}
{\|\nabla F_\theta(p^{(r)})\|^2+\varepsilon_g}
\nabla F_\theta(p^{(r)}).
\]

Implementation requirements:

- vectorize where practical;
- stop on a configurable field residual or maximum iteration count;
- detect and report `||grad F||` below a threshold;
- cap an individual correction step relative to the local grid spacing so a bad field cannot jump to a remote branch;
- retain per-point convergence status and iteration count;
- reject or report points that do not converge;
- after projection, rerun self-intersection and orientation checks;
- optionally resample once more by chord length after projection.

When the field is not reliably SDF-like, use the normalized residual

\[
\frac{|F_\theta(p)|}{\|\nabla F_\theta(p)\|+\varepsilon}
\]

as the approximate geometric normal error.

## 4.5 Initial parameter values

After final projected resampling, assign

\[
t_j=2\pi\frac{s_j}{L},
\]

where \(s_j\) is cumulative chord length and \(L\) is the total polygonal length.

These \((t_j,p_j)\) pairs are the common input to all three representation methods.

---

# 5. Common postprocessing: arc-length reparameterization

Implement one reusable routine:

```python
def reparameterize_by_arclength(
    curve: ParametricBoundary2D,
    refit_factory: Callable[[Array, Array], ParametricBoundary2D],
    dense_n: int,
    output_n: int,
) -> ParametricBoundary2D:
    ...
```

Procedure:

1. Evaluate \(\gamma(t)\) and \(J(t)=|\gamma'(t)|\) on a dense uniform grid.
2. Numerically integrate cumulative arc length
   \[
   s(t)=\int_0^tJ(\tau)\,d\tau.
   \]
3. Normalize
   \[
   u(t)=2\pi s(t)/L.
   \]
4. Invert the monotone sampled map \(u(t)\).
5. Evaluate the same geometric curve at uniform \(u\)-values.
6. Refit those samples in the method's native representation.
7. Validate that geometry displacement from reparameterization/refitting is small.

Apply one common arc-length reparameterization/refit to Methods A and B. Method C performs it after nonlinear shape refinement and then uses a brief final SDF correction.

Arc-length reparameterization changes the parameter map, not the intended geometric image. Refitting can introduce a small shape change; record it.

---

# 6. Method A — simple baseline: projected periodic cubic spline

## Role

This is the **simple conventional baseline**. It answers:

> How well does a straightforward smooth periodic interpolant of accurately projected ordered points work?

It is Kress-usable but is not expected to preserve spectral convergence as cleanly as a global Fourier curve, because a standard cubic spline has finite global smoothness at its knots.

## Pipeline

\[
F_\theta
\to
\text{marching squares}
\to
\text{ordered projected points}
\to
\text{periodic cubic spline}
\to
\text{arc-length reparameterization/refit}
\to
\gamma_A.
\]

## Representation

Store two periodic scalar splines, one for \(x(t)\) and one for \(y(t)\), sharing the same parameter knots.

```python
@dataclass(frozen=True)
class PeriodicSplineBoundary(ParametricBoundary2D):
    x_spline: object
    y_spline: object
    degree: int = 3
```

The authoritative state is the spline knots and coefficients, not sampled points.

## Fitting instructions

1. Use the shared \((t_j,p_j)\) data.
2. Add the periodic endpoint only in the form required by the spline library:
   \[
   t_M=2\pi,\qquad p_M=p_0.
   \]
3. Use a truly periodic boundary condition. Do not merely duplicate the first point while leaving endpoint derivatives unconstrained.
4. Initially use interpolation, not an opaque smoothing parameter.
5. If interpolation reproduces neural/grid noise, add an explicitly configured periodic smoothing-spline variant as a later ablation rather than silently changing the baseline.
6. Obtain first and second derivatives analytically from the spline object.
7. Perform one arc-length reparameterization/refit using the same spline construction.

## Expected strengths

- minimal implementation complexity;
- local control;
- stable interpolation;
- analytic first and second derivatives;
- useful sanity baseline.

## Expected limitations

- finite smoothness at knots;
- possible derivative oscillation if projected samples contain noise;
- no native spectral coefficient-tail diagnostic;
- likely algebraic rather than spectral Kress convergence at sufficiently high resolution.

---

# 7. Method B — strong classical baseline: bandlimited Fourier least squares

## Role

This is the **strong classical baseline** and should be the primary comparator. It answers:

> How far can a globally periodic analytic curve go without nonlinear optimization against the SDF?

## Pipeline

\[
F_\theta
\to
\text{marching squares}
\to
\text{ordered projected points}
\to
\text{Fourier least-squares fit}
\to
\text{arc-length reparameterization/refit}
\to
\gamma_B.
\]

## Representation

Use

\[
\gamma_K(t)=c_0+
\sum_{k=1}^{K}
\left[a_k\cos(kt)+b_k\sin(kt)\right],
\]

where \(c_0,a_k,b_k\in\mathbb R^2\).

```python
@dataclass(frozen=True)
class FourierBoundary(ParametricBoundary2D):
    c0: Array               # (2,)
    cos_coeffs: Array       # (K, 2)
    sin_coeffs: Array       # (K, 2)
```

Analytic derivatives are

\[
\gamma_K'(t)=
\sum_{k=1}^{K}k
\left[-a_k\sin(kt)+b_k\cos(kt)\right],
\]

and

\[
\gamma_K''(t)=
-\sum_{k=1}^{K}k^2
\left[a_k\cos(kt)+b_k\sin(kt)\right].
\]

## Fitting instructions

1. Build the real trigonometric design matrix at the common chord-length parameters \(t_j\).
2. Solve independent linear least-squares systems for the two coordinate functions.
3. Keep the number of projected samples \(M\) comfortably larger than the number of Fourier degrees of freedom; expose both as configuration.
4. Do not interpolate all high-frequency marching noise by automatically taking \(K\approx M/2\).
5. Sweep \(K\) over a configured sequence and record fidelity, speed, self-intersection, and coefficient-tail metrics.
6. Normalize/center coordinates internally if needed for conditioning, then restore physical coordinates exactly.
7. Perform one numerical arc-length reparameterization and refit at the same bandwidth \(K\).
8. Do not use nonlinear SDF loss optimization in Method B.

## Bandwidth selection

Do not encode one universal \(K\). Select by convergence and diagnostics:

- SDF residual decreases and then plateaus;
- geometric distance to the exact reference decreases and then plateaus, when available;
- high-frequency coefficient tail is small before Nyquist;
- \(\min|\gamma'|\) remains safely positive;
- no self-intersection appears;
- area and perimeter stabilize.

The comparison script may begin with a modest sweep such as `K = [8, 16, 32, 64]`, adjusted to the scene scale and available samples. These are experiment defaults, not universal physical rules.

## Expected strengths

- exact periodicity;
- analytic \(C^\infty\) finite representation;
- transparent bandwidth control;
- exact derivatives of the represented curve;
- direct coefficient-tail diagnostics;
- close match to the periodic spectral structure of Kress.

## Expected limitations

- global basis;
- no automatic protection against self-intersection;
- excessive bandwidth can fit neural noise and amplify it in derivatives;
- least squares alone does not force the fitted curve exactly back onto the SDF zero set.

---

# 8. Method C — best shot: SDF-constrained Fourier refinement

## Role

This is the **best-shot method** recommended for the first research implementation. It retains the topology and ordering discovered by the common contour front end, but refines the finite-dimensional Fourier curve directly against the neural field.

Method C must initialize from a valid Method B result. Do not initialize an unrestricted general curve from a circle in the first pass; that introduces avoidable topology and branch-selection failure modes.

## Pipeline

\[
F_\theta
\to
\text{shared projected loop}
\to
\gamma_B
\to
\text{SDF-constrained Fourier optimization}
\to
\text{arc-length reparameterization/refit}
\to
\text{brief final SDF refinement}
\to
\gamma_C.
\]

## Optimized variables

Optimize the Fourier coefficient arrays of `FourierBoundary`. Use the repository's existing autodiff framework, preferably PyTorch if the neural SDF is already a PyTorch module. Do not introduce a second autodiff framework.

## Core loss

Use a staged, configurable loss rather than one hard-coded set of weights:

\[
\mathcal L
=
\lambda_F\mathcal L_F
+
\lambda_A\mathcal L_{\rm anchor}
+
\lambda_Q\mathcal L_{\rm spectral}
+
\lambda_V\mathcal L_{\rm speed}
+
\lambda_R\mathcal L_{\rm regularity}
+
\lambda_N\mathcal L_{\rm normal}
+
\lambda_{SI}\mathcal L_{\rm self}.
\]

### Zero-set fidelity

For a well-calibrated SDF:

\[
\mathcal L_F
=
\frac1Q\sum_{q=0}^{Q-1}
F_\theta(\gamma(t_q))^2.
\]

For a generic implicit field, prefer the scale-normalized proxy

\[
\mathcal L_F
=
\frac1Q\sum_q
\frac{F_\theta(\gamma(t_q))^2}
{\|\nabla F_\theta(\gamma(t_q))\|^2+\varepsilon}.
\]

Use dense uniform parameter samples \(t_q\), not only the original fitting nodes.

### Component/parameter anchor

Keep the optimizer attached to the discovered component and initial correspondence:

\[
\mathcal L_{\rm anchor}
=
\frac1M\sum_j
\|\gamma(t_j)-p_j\|^2.
\]

This should normally be weakened after the optimizer is stably following the intended branch, not necessarily removed.

### Spectral regularization

For derivative order \(q\), for example \(q=2\), use

\[
\mathcal L_{\rm spectral}
=
\sum_{k=1}^{K}k^{2q}
\left(\|a_k\|^2+\|b_k\|^2\right).
\]

This directly suppresses unsupported high-frequency coordinate oscillations.

### Speed-uniformity term

Let \(J_q=|\gamma'(t_q)|\). Use a scale-free coefficient-of-variation penalty:

\[
\mathcal L_{\rm speed}
=
\frac{\operatorname{Var}(J_q)}
{\operatorname{Mean}(J_q)^2+\varepsilon}.
\]

### Regularity barrier

The hard requirement is \(J_q>0\). Add a soft barrier below a configurable fraction of the mean speed, for example

\[
\mathcal L_{\rm regularity}
=
\frac1Q\sum_q
\operatorname{softplus}(J_{\rm floor}-J_q)^2.
\]

The exact floor is scale- and parameter-dependent; expose it and report \(J_{\min}/\bar J\).

### Optional normal agreement

When `field.gradient` is trustworthy:

\[
\mathcal L_{\rm normal}
=
\frac1Q\sum_q
\left(1-n_\gamma(t_q)\cdot
\frac{\nabla F_\theta(\gamma(t_q))}
{\|\nabla F_\theta(\gamma(t_q))\|+\varepsilon}
\right)^2.
\]

Use the oriented dot product after confirming the SDF sign convention. Do not hide an orientation error with an absolute value during optimization.

### Self-intersection protection

At minimum:

- run an explicit dense segment-intersection test after every optimization stage;
- reject checkpoints with a self-intersection;
- record minimum nonlocal distance.

A differentiable nonlocal-distance barrier may be added for pairs separated by more than a configured cyclic-neighbourhood width. Exclude adjacent parameter pairs, whose physical distance is expected to be small.

## Optimization schedule

Use a conservative staged schedule:

1. Initialize from Method B.
2. Optimize zero-set fidelity + anchor + weak spectral regularization.
3. Add speed and regularity terms after the curve is stably attached to the branch.
4. Add normal agreement only if gradients have passed validation.
5. Validate self-intersection and minimum speed after each stage.
6. Arc-length reparameterize and refit at the same \(K\).
7. Run a short final zero-set/spectral refinement with a small learning rate.
8. Return the lowest-loss **valid** checkpoint, not merely the last checkpoint.

Expose optimizer, learning rate, iteration counts, dense sample count, and every loss weight. Record the full loss and diagnostic history.

## Failure and fallback policy

Method C is only accepted when it remains:

- on the intended component;
- simple;
- regularly parameterized;
- no worse than Method B in primary geometry metrics within configured tolerance.

If optimization introduces a self-intersection, speed degeneracy, branch jump, or major geometry drift, report failure and fall back to Method B rather than silently returning an invalid best-shot curve.

## Expected strengths

- directly reduces the discrepancy between the smooth curve and the neural zero set;
- retains analytic periodic Fourier geometry;
- gives explicit control over smoothness and parameter crowding;
- differentiable with respect to Fourier coefficients and, if later required, potentially to SDF parameters.

## Expected limitations

- nonconvex optimization;
- weight tuning and validation required;
- self-intersection is not excluded by ordinary Fourier coordinates;
- can overfit unreliable high-frequency structure if \(K\) or regularization is poorly chosen.

---

# 9. Why these three methods, and what is not a method here

The comparison should be interpreted as:

| Label | Full converter | Purpose |
|---|---|---|
| Diagnostic only | marching polygon, optionally projected | Verify contour topology and projection; **not Kress-ready** |
| Method A | projected contour → periodic cubic spline | Simple conventional baseline |
| Method B | projected contour → Fourier least squares | Strong classical/Kress-native baseline |
| Method C | Method B → direct SDF-constrained Fourier refinement | Best shot |

Do not use raw marching squares as the only baseline supplied to Kress. It is piecewise linear, has discontinuous tangent at vertices, and does not provide the smooth removable-diagonal remainder assumed by the Kress construction.

Do not initially make “marching squares versus tracking versus Fourier optimization” the principal three-way comparison. Those alternatives change different stages of the pipeline. First compare final \(\gamma\) representations using a common topology/localization front end. A later ablation may compare marching squares with predictor-corrector level-set tracking as two ways to produce the shared ordered projected samples.

Deferred research variants from the report include:

- predictor-corrector level-set tracking plus Fourier fitting;
- Beylkin–Rokhlin tangent-angle bandlimited fitting;
- positive radial Fourier representation for guaranteed star-shaped scenes;
- speed-plus-tangent-angle Fourier representation to guarantee positive speed;
- periodic high-degree B-splines/NURBS;
- learned amortized SDF-to-Fourier coefficient decoders.

Do not implement these until Methods A–C and the metrics are working.

---

# 10. Metrics

Keep four categories separate. Do not collapse them into one score.

## 10.1 Geometry fidelity to the implicit field

Evaluate on a dense uniform parameter grid much finer than the final fitted degrees of freedom.

### Raw SDF residual

\[
r_{F,\infty}=\max_q|F_\theta(\gamma(t_q))|,
\qquad
r_{F,2}=\sqrt{\frac1Q\sum_qF_\theta(\gamma(t_q))^2}.
\]

### Normalized geometric residual

For a generic implicit field:

\[
r_{\perp,\infty}
=
\max_q
\frac{|F_\theta(\gamma(t_q))|}
{\|\nabla F_\theta(\gamma(t_q))\|+\varepsilon}.
\]

When \(F_\theta\) is a true SDF, raw field residual already has an approximate distance interpretation.

### Reference-set distance

When an exact boundary is available, compute symmetric sampled closest-point/Hausdorff distance between the two geometric sets. Do not compare `candidate.position(t)` and `reference.position(t)` at identical `t` unless phase, orientation, and parameterization have first been aligned.

### Integral geometry

Report:

- perimeter;
- signed area;
- relative area error;
- relative perimeter error.

### Differential geometry

When exact reference values are available:

- normal-angle error;
- curvature error.

Do not use a neural Hessian as the default curvature ground truth.

## 10.2 Topology and validity

Report:

- number of components;
- open/closed status;
- orientation;
- self-intersection count;
- minimum nonlocal distance;
- winding number around configured test points;
- topology stability under extraction-grid refinement.

A self-intersecting result is invalid regardless of its average residual.

## 10.3 Parameterization and Kress readiness

### Seam consistency

\[
e_{\rm seam}^{(m)}
=
\|\gamma^{(m)}(0)-\gamma^{(m)}(2\pi)\|,
\qquad m=0,1,2.
\]

Fourier values should agree to floating-point accuracy. Periodic splines must satisfy their actual periodic derivative conditions.

### Speed regularity

\[
J_{\min}=\min_q|\gamma'(t_q)|,
\qquad
R_J=\frac{\max_q|\gamma'(t_q)|}{\min_q|\gamma'(t_q)|},
\qquad
r_J=\frac{J_{\min}}{\operatorname{mean}_qJ_q}.
\]

`J_min > 0` is a hard requirement. A large `R_J` is not formally invalid but signals poor physical node distribution.

### Spectral tail

For both spline and Fourier candidates, densely sample \(x(t),y(t)\), apply a periodic FFT, and report coordinate and derivative-weighted high-mode tails:

\[
E_{\rm tail}^{(m)}
=
\frac{
\sum_{|k|\ge k_0}|k|^{2m}
\left(|\hat x_k|^2+|\hat y_k|^2\right)
}{
\sum_k|k|^{2m}
\left(|\hat x_k|^2+|\hat y_k|^2\right)
},
\qquad m=0,1,2.
\]

This allows a fair comparison even though the spline does not natively store global Fourier coefficients.

### Smooth Kress-remainder diagonal test

Define

\[
q_\gamma(t,s)
=
\log\frac{|\gamma(t)-\gamma(s)|}
{2|\sin((t-s)/2)|},
\qquad
q_\gamma(t,t)=\log|\gamma'(t)|.
\]

For shrinking offsets \(h\), evaluate

\[
e_{\rm diag}(h)
=
\max_t
\left|
\frac{q_\gamma(t,t+h)+q_\gamma(t,t-h)}{2}
-
\log|\gamma'(t)|
\right|.
\]

This is the most direct geometry-only test of whether the logarithmic singularity leaves the expected smooth remainder. Use numerically stable evaluation and avoid offsets below useful floating-point scale.

### Uniform-node adapter checks

For each requested even \(N\), assert:

- exactly `N` nodes;
- no duplicated endpoint;
- `t[j] == 2*pi*j/N` within machine precision;
- `dt == 2*pi/N`;
- all speeds finite and positive;
- normals are unit length;
- `ds_weights == dt * speed`;
- orientation and normal direction are consistent.

## 10.4 Direct Kress proxy tests

These are optional in the first converter commit but recommended before coupling to a BIE.

### Manufactured unit-circle logarithmic integral

For \(\gamma(t)=(\cos t,\sin t)\) and integer \(m\ge1\), use

\[
\int_0^{2\pi}
\log|\gamma(t)-\gamma(s)|\cos(ms)\,ds
=
-\frac{\pi}{m}\cos(mt),
\]

and the analogous sine identity, to validate the later Kress product weights independently of the SDF converter.

### Fixed-geometry N-doubling

On one frozen fitted \(\gamma\), compare Kress results at \(N,2N,4N\). This measures quadrature convergence only. It must be kept separate from changing the extraction grid or the Fourier bandwidth, which changes the geometry itself.

---

# 11. Controlled test geometries

Implement analytic reference curves through the same `ParametricBoundary2D` interface.

Minimum suite:

1. **Circle**
   \[
   \gamma_*(t)=(c_x+R\cos t,c_y+R\sin t).
   \]
   Method B with \(K=1\) should recover it to near numerical precision when the projected points are accurate.

2. **Ellipse**
   \[
   \gamma_*(t)=(c_x+a\cos t,c_y+b\sin t).
   \]
   Use either an exact/accurate ellipse distance field or treat a standard ellipse level-set function explicitly as a generic implicit field, not as a true SDF.

3. **Smooth Fourier-perturbed curve**
   Define a known simple closed Fourier curve with several modes and verified non-self-intersection. This directly tests bandwidth recovery.

4. **Strongly nonuniform curvature but smooth curve**
   Use a rounded, non-star-shaped or strongly perturbed simple curve to expose parameter crowding and derivative artifacts.

5. **Two separated components** as an API/topology test.
   The result must contain two independent curves. Do not yet use this case for the primary single-component ranking.

6. **Failure fixtures**
   - contour touches the bounding box;
   - near-critical gradient;
   - deliberately underresolved grid;
   - a Fourier fit that self-intersects at excessive or unstable bandwidth.

Where a true analytic SDF is unavailable, distinguish clearly between:

- testing zero-set extraction from a generic implicit function;
- testing an SDF-calibrated residual as physical distance.

---

# 12. Fair comparison protocol

For each test shape:

1. Fix the field and physical bounding box.
2. For one grid resolution, generate one shared projected ordered loop.
3. Feed exactly that loop to Methods A, B, and C.
4. Use the same dense evaluation grid for all metrics.
5. Sweep extraction resolution independently from representation resolution.
6. For Fourier methods, sweep \(K\).
7. For the spline method, sweep projected/control sample count independently.
8. For each final curve, evaluate several even Kress sample counts \(N\) without refitting the curve.
9. Record runtime, SDF calls, gradient calls, projection iterations, fit time, and optimization iterations.
10. Store failure reasons explicitly rather than dropping failed runs.

Recommended experimental axes:

- grid spacing \(h\): coarse, medium, fine;
- projected sample count \(M\);
- spline sample/knot count;
- Fourier bandwidth \(K\);
- final Kress sample count \(N\).

These variables answer different questions and must not be conflated.

Primary comparison table columns:

- method and status;
- grid resolution;
- projected sample count;
- spline degree/control count or Fourier \(K\);
- max/RMS raw and normalized SDF residual;
- symmetric boundary distance when reference exists;
- area and perimeter error;
- max normal error and curvature error when reference exists;
- seam errors through order 2;
- minimum speed and speed ratio;
- self-intersection count and minimum nonlocal distance;
- spectral tails for orders 0, 1, and 2;
- Kress-remainder diagonal errors at several \(h\);
- SDF/gradient evaluation counts;
- runtime.

Do not select the winning method from plots or one scalar aggregate. A method with a tiny SDF residual but a self-intersection or nearly zero speed has failed.

---

# 13. Suggested repository layout

Adapt this to the existing project rather than forcing new conventions.

```text
geometry/
    implicit_field_2d.py
    parametric_boundary_2d.py
    boundary_set_2d.py
    kress_geometry_2d.py

geometry/extraction/
    marching_squares_frontend.py
    contour_validation.py
    chord_resampling.py
    zero_set_projection.py

geometry/parameterizations/
    periodic_spline.py
    fourier_boundary.py
    fourier_fit.py
    fourier_sdf_refinement.py
    arclength_reparameterization.py

geometry/metrics/
    geometry_fidelity.py
    topology.py
    parameterization.py
    kress_readiness.py

scripts/
    compare_sdf_to_gamma_methods.py

 tests/
    test_parametric_boundary_contract.py
    test_kress_geometry_adapter.py
    test_zero_set_projection.py
    test_periodic_spline_baseline.py
    test_fourier_fit.py
    test_fourier_sdf_refinement.py
    test_kress_readiness_metrics.py
    test_analytic_shapes.py
```

Prefer small pure functions and immutable final curve objects. Optimizer state and diagnostic history belong in `ExtractionResult`, not inside the authoritative geometry object.

```python
@dataclass(frozen=True)
class ExtractionResult:
    method_name: str
    curves: BoundarySet2D
    raw_contours: tuple[Array, ...]
    projected_contours: tuple[Array, ...]
    diagnostics: dict[str, Any]
    config: Mapping[str, Any]
    status: Literal["success", "failed", "fallback"]
    failure_reason: str | None
```

---

# 14. Unit-test expectations

At minimum, tests should assert:

## Common curve contract

- output shapes are correct;
- scalar and batched parameter inputs work;
- periodic values agree at \(0\) and \(2\pi\);
- first and second analytic derivatives agree with high-accuracy finite-difference checks on smooth test curves;
- `sample_uniform(N)` rejects odd or too-small \(N\);
- no duplicate endpoint appears.

## Projection

- circle points converge to the exact radius;
- a generic scaled implicit function projects correctly despite \(\|\nabla F\|\ne1\);
- near-zero gradients produce an explicit failure status;
- correction-step limiting prevents branch jumps in a constructed stress test.

## Method A

- periodic seam position, first derivative, and second derivative are continuous to expected tolerance;
- circle/ellipse geometry converges under increased input sampling;
- orientation is preserved.

## Method B

- a circle is recovered at \(K=1\);
- a known finite Fourier curve is recovered when \(K\) includes all true modes and the inputs are sufficiently accurate;
- analytic derivatives match the known reference;
- high-mode tails behave as expected under under- and over-resolution.

## Method C

- starts exactly from Method B coefficients;
- decreases the configured objective on a controlled field;
- improves or preserves zero-set fidelity without introducing self-intersection;
- returns a valid earlier checkpoint when a later step becomes invalid;
- falls back explicitly to Method B on constructed failure.

## Kress readiness

- unit circle gives constant speed and zero seam error;
- `q_gamma(t,t+h)` approaches `log(speed(t))` as \(h\to0\);
- outward normals point outward for the counterclockwise circle;
- `ds_weights` integrate the constant function to the perimeter with convergence.

---

# 15. Implementation order for Codex

Proceed in this order:

1. Inspect the repository and reuse existing tensor, SDF, geometry, logging, and test conventions.
2. Implement/adapt `ImplicitField2D`.
3. Implement `ParametricBoundary2D`, `BoundarySet2D`, and `KressGeometry2D`.
4. Implement exact circle, ellipse, and known-Fourier reference boundaries.
5. Implement the uniform sampling adapter and core Kress-readiness tests.
6. Implement the shared marching-squares, polygon validation, chord-resampling, and safeguarded projection front end.
7. Implement Method A and its tests.
8. Implement `FourierBoundary`, Method B, and its tests.
9. Implement common arc-length reparameterization.
10. Implement metrics and the comparison script before Method C, so optimization failures are visible.
11. Implement Method C with staged optimization, checkpoint validation, and Method B fallback.
12. Run grid, representation-resolution, and Kress-sample sweeps; produce machine-readable results and plots.
13. Document limitations and unresolved failures. Do not tune away failed cases without retaining them in the output.

---

# 16. Non-negotiable implementation rules

1. **Do not pass a raw marching polygon to Kress and call it a smooth boundary.**
2. **Do not store only point samples as the authoritative gamma representation.** Store Fourier or spline coefficients.
3. **Do not estimate final normals and curvature from neighbouring marching points.** Differentiate the final curve representation.
4. **Do not assume the same parameter value identifies the same physical point on two different curves** when computing set error.
5. **Do not silently choose the largest connected component.**
6. **Do not concatenate multiple components into one gamma.**
7. **Do not duplicate the endpoint in Kress samples.**
8. **Do not use odd N for the standard Kress adapter.**
9. **Do not treat arc-length spacing as a substitute for uniform computational t.** Final nodes are always uniform in the chosen periodic parameter.
10. **Do not judge Method C only by its loss.** Enforce topology, minimum speed, seam, and fidelity validation.
11. **Do not use universal hard-coded tolerances without scale normalization.** Expose tolerances and establish them by convergence.
12. **Do not conflate neural error, contour error, fitting error, parameterization error, and later quadrature error.** Report them separately.

---

# 17. Expected conclusion of the first experiment

The experiment is designed to determine whether:

- a simple periodic spline is already adequate;
- a global Fourier representation materially improves periodic smoothness and Kress-readiness;
- direct SDF-constrained Fourier refinement improves zero-set fidelity without sacrificing regularity or topology;
- extraction-grid error or representation bandwidth is the current bottleneck.

The expected ranking from the report is:

1. **Method A: baseline** — easiest, locally controlled, finite smoothness.
2. **Method B: strong baseline** — analytic periodic geometry and likely the best cost/robustness tradeoff.
3. **Method C: best shot** — highest potential fidelity and future differentiability, but accepted only when its nonlinear optimization remains geometrically valid.

Method C should not be presumed superior merely because it is more complicated. The comparison and failure checks must be capable of showing that Method B is preferable on a given field.
