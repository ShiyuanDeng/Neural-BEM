# Joint unknown reference field: implementation and first numerical screen

2026-10-11. Track 13, CVX-002. **The 41×41 screen is complete; the pre-registered
57×57 resolution checks are pending.**

The implemented joint-field method improved the coefficient image for the
below-background circle with added full-boundary data. Its occupancy IoU rose
from **0.542 to 0.845**, and sampled contour RMS fell from **21.36 to 15.09 mm**
in the unweighted arm. This is useful partial reconstruction, not a recovered
TG-002 object: Hausdorff error worsened from **39.39 to 100.99 mm**, and the
thresholded shape's original paired-data residual remained large. The weighted
arm was slightly worse on coefficient error, IoU, RMS and paired prediction.
The other six preselected arms stopped at explicit phase qualifications.

## Evidence and experimental scope

- [Pre-registered plan](CVX-002_plan.md).
- [Sparse joint-field implementation](../../../experiments/convexification/joint_tail.py)
  and [campaign/data/readout driver](../../../experiments/convexification/cvx002.py).
- [Complete screen summary](../../../results/validation/convexification/CVX-002/screen/summary.json),
  [launch manifest](../../../results/validation/convexification/CVX-002/screen/manifest.json),
  and [executed source archive](../../../results/validation/convexification/CVX-002/screen/sources.tar.gz).
- [Algebra qualification](../../../results/validation/convexification/CVX-002/screen/algebra_qualification.json),
  [successful data qualification](../../../results/validation/convexification/CVX-002/screen/circle__c0.5/data_qualification.json),
  [unweighted endpoint](../../../results/validation/convexification/CVX-002/screen/circle__c0.5/span0/result.json),
  and [weighted endpoint](../../../results/validation/convexification/CVX-002/screen/circle__c0.5/span4/result.json).
- [Post-run validation](../../../results/validation/convexification/CVX-002/screen/validation.json),
  [numerical table](../../../results/validation/convexification/CVX-002/screen/table.csv),
  and [overview figure](../../../results/validation/convexification/CVX-002/screen/overview.svg).

This is an augmented-acquisition feasibility screen on four frozen TG-002
targets, not the standard 30-case benchmark. It uses one existing source at
three catalog frequencies, 0.25, 0.375 and 0.5 GHz, with full Dirichlet and
outward-normal data on a source-free square enclosing the target. These are
new synthetic measurements. They cannot be obtained by relabeling the existing
paired catalog. Original paired data are used only for post-fit prediction.

Both weight arms use the same prescribed centered 65 mm circle, grid, frequency
set, data, regularization, stopping rules and single start. Interior truth
fields and a true reference field are never supplied to the optimizer. Truth
is used to generate boundary data and to score the final coefficient/readout.
The code remains isolated under `experiments/convexification`; it changes no
maintained solver default.

## Actual screen results

The following numbers concern `circle__c0.5`. The coefficient and raster metrics
include the whole auxiliary grid, with background fixed on its boundary.
Contour metrics include **all** threshold contours, including disconnected
components. They are sampled metrics, not certified geometric bounds.

| Metric | Centered initial circle | Unweighted, span 0 | Weighted, span 4 |
|---|---:|---:|---:|
| Coefficient RMSE | 0.16179 | **0.08392** | 0.08784 |
| Coefficient relative error | 17.032% | **8.834%** | 9.248% |
| Occupancy IoU | 0.54167 | **0.84545** | 0.84234 |
| Area relative error | +70.320% | −14.612% | −13.242% |
| Sampled symmetric contour RMS | 21.358 mm | **15.086 mm** | 15.176 mm |
| Sampled Hausdorff distance | **39.390 mm** | 100.985 mm | 101.107 mm |
| Threshold contour count | 1 | 2 | 2 |
| Grid values outside material interval [0.5, 1] | 0% | 40.809% | 41.344% |
| Raw interior coefficient range | [0.5, 1] | [0.27017, 1.23667] | [0.26804, 1.26783] |
| Accepted nonlinear updates | — | 12 | 12 |
| Fit wall time | — | 15.93 s | 16.42 s |

Both fits stopped at the registered iteration cap. Neither met the small-step
stop: their final relative steps were 0.00714 and 0.04462, respectively. Every
accepted update used the full proposed step; the backtracking alternatives
were unnecessary in these two fits. These endpoint observations do not establish
convergence to a fixed point or a globally optimal reconstruction.

The RMS and IoU gains coexist with a worse Hausdorff distance and a second
contour. Thus the experiment directly exhibits the limitation discussed in
CVX-001: better area overlap or average boundary error does not control the
worst geometric error. The real coefficient is unconstrained in this prototype;
the large fraction outside the known material interval is reported rather than
hidden by display clipping.

| Auxiliary endpoint diagnostic | Unweighted | Weighted |
|---|---:|---:|
| Nonlinear objective | 5.6601e-5 | 1.1566e-4 |
| Unweighted PDE residual RMS | 7.5258e-4 | 1.7193e-3 |
| Boundary-normal relative mismatch | 0.18141% | 0.19335% |
| Minimum inferred \(|u/u_0|\) on grid | 0.68708 | 0.68713 |
| Maximum linear normalized stationarity | 1.8138e-14 | 1.6367e-14 |
| Applied interior weight range | [1, 1] | [0.57530, 13.59075] |
| Applied interior weight mean | 1 | 1 |

The weight is genuinely nonconstant: its full-grid maximum/minimum ratio is
54.598, with full-grid log span 4. The PDE uses interior points only, hence its
applied range is narrower than the full-grid range. The objectives use different
spatial weights and should not themselves be read as matched physical errors;
the unweighted PDE RMS and common geometry/prediction diagnostics provide those
comparisons. No benefit from this particular weight is demonstrated by the
successful screen case.

The large objective decrease needs context. Initial objectives were **506.48**
and **479.10**, with a common normal-mismatch contribution of **364.16**.
The initialization takes the physical centered-circle field in the interior
and overwrites its boundary values with the measured target values. This
discrete boundary lift creates large near-boundary derivative residuals.
Consequently the many-order objective reduction substantially includes repair
of that initial lift; it is not evidence of a comparable reduction in physical
shape error. After the first update, objectives were already 0.01477 and
0.01563, respectively. The subsequent improvement and final independent
metrics are the informative reconstruction evidence.

![CVX-002 screen: coefficient images, contours and recorded diagnostics](../../../results/validation/convexification/CVX-002/screen/overview.png)

## Independent prediction does not qualify the recovered shape

The physical readout takes the largest closed contour, resamples by arclength,
and fits Fourier band 16. Each arm discards one other component. Its smoothing
RMS is 0.0409 mm unweighted and 0.0775 mm weighted. Thus these paired predictions
test the declared single-object readout, not the entire raw volume image.

| Original paired-data check, 19 real frequencies | Unweighted | Weighted |
|---|---:|---:|
| RMS of per-frequency relative residuals | 95.473% | 118.321% |
| Maximum relative residual | 330.938% | 381.019% |
| Frequencies at or below 0.3% residual | 0 / 19 | 0 / 19 |
| Relative residual at 0.25 GHz | 11.649% | 11.866% |
| Relative residual at 0.375 GHz | 10.281% | 11.080% |
| Relative residual at 0.5 GHz | 11.607% | 13.477% |

All readout forward solves passed their N256/N512 refinement check. This
qualifies their numerical evaluation, not their fit to measurements. Even at
the three fitting frequencies, changing illumination/receivers to the original
paired catalog exposes substantial readout error. The small auxiliary residual
and boundary-normal mismatch do not transfer to a good binary shape prediction.
The reported RMS is the root mean square of 19 frequency-relative errors, not
one aggregate norm over the full catalog. These checks are not TG-002's
certified endpoint audit and support no recovery count.

## Six arms stopped before optimization

All four cases passed the nodal refinement and initial Mie/field qualification
checks before the log conditions were applied. The failures are retained as
part of the result, rather than replaced by another start or omitted from the
screen denominator.

| Target / contrast | Arms stopped | Recorded phase evidence | Interpretation |
|---|---:|---|---|
| Circle / 4 | 2 | 4 nonzero initial-grid plaquette windings; sampled minimum \(|u/u_0|=0.01557\) | Prescribed initial physical field fails the sampled global-log qualification. |
| Circle / 13.3 | 2 | 22 nonzero initial-grid plaquette windings; sampled minimum \(|u/u_0|=0.01133\) | Same starting-field obstruction, more sampled phase defects. |
| C-shape / 13.3 | 2 | Boundary winding −1 at 0.375 GHz; sampled minimum \(|u/u_0|=0.07002\) | Measured boundary fails the single-valued-log qualification. |

The underlying records are
[circle / 4](../../../results/validation/convexification/CVX-002/screen/circle__c4/log_qualification.json),
[circle / 13.3](../../../results/validation/convexification/CVX-002/screen/circle__c13.3/log_qualification.json),
and [C-shape / 13.3](../../../results/validation/convexification/CVX-002/screen/c_shape__c13.3/log_qualification.json).
These are sampled diagnostics. Nonzero discrete winding warrants the declared
stop; this screen has not located continuous zeros or certified continuous
winding under mesh refinement. The initial-circle failures do not establish
that every possible auxiliary initialization fails. The boundary failure is
different: changing an interior starting field would not remove the recorded
boundary inconsistency. No phase branch cut was silently introduced to continue.

## What was implemented and what follows mathematically

Coordinates use the repository's 50 mm length unit, with dimensionless
wavenumber \(k\). For a known incident field, put
\(a_j=\nabla\log u_{0,j}\),
\(v_j=k_j^{-2}\log(u_j/u_{0,j})\), and

\[
F_j(v_j)=\Delta v_j+k_j^2\nabla v_j\cdot\nabla v_j
 +2a_j\cdot\nabla v_j.
\]

The solver retains one real common coefficient and all complex fields:

\[
F_j(v_j)+c-1=0. \tag{1}
\]

It stores the fields in sparse coordinates, but explicitly distinguishes
\(V=v_{K-1}\) and reference secants
\(s_j=(v_j-V)/(t_j-1)\), where
\(t_j=(k_j-k_0)/(k_{K-1}-k_0)\). The inverse map is
\(v_j=V+(t_j-1)s_j\). Consequently \(V\) is a genuine unknown; no supplied
interior tail or basis-truncation inversion conceals the missing constant part.
Subtracting equations (1) eliminates \(c\), while their last-frequency equation
provides the explicit anchor relation.

CVX-001 derived \([D^2v_j]=-[c]n\otimes n\) under its local smooth-interface
and nonvanishing assumptions. Therefore \([D^2s_j]=0\). This motivates the
separate discrete \(H^2\) penalty on \(V\) and \(H^3\) penalties on the
secants. It does not place the rough reference field in \(H^3\), and it does
not prove global zero-freeness from finitely sampled minima.

For each iteration, the code freezes one factor of the quadratic term:

\[
\left[\Delta+
 (k_j^2\nabla v_j^{(p)}+2a_j)\cdot\nabla\right]v_j^{(p+1)}
 +c^{(p+1)}=1. \tag{2}
\]

The resulting weighted least-squares subproblem is real-linear after complex
stacking. Dirichlet data are imposed by elimination; normal data are penalized.
Positive zeroth-order terms in the reference/secant regularizers, together with
positive coefficient regularization, make the finite linear system injective:
zero reference and zero secants force every field to vanish, and the coefficient
regularizer forces its remaining component to vanish. Thus each regularized
subproblem has a unique minimizer. This elementary finite-dimensional fact does
not make the original nonlinear inverse objective convex or prove that the
Picard map contracts. Backtracking evaluates the actual nonlinear objective.

This implementation takes its one-factor linearization from
[Nguyen, Nguyen and Vu, 2404.04145v2, equation (2.17)](https://arxiv.org/html/2404.04145v2).
That paper treats a projected angular system with full Cauchy data and smooth,
nonvanishing fields. Its theorem does not cover this joint coefficient/reference
model, sharp-interface truth, or present finite-difference regularization.

The multifrequency precedent
[Truong, Nguyen and Klibanov, 2002.08427](https://arxiv.org/html/2002.08427)
uses an \(H^2\)-regularized auxiliary functional and boundary penalties, but
its Algorithm Step 2b also solves a forward problem after each coefficient
update. CVX-002 does not perform that physical refresh during optimization.
It is a new feasibility variant inspired by these papers, not a literal
reproduction of either published method. The qualifications and limitations
identified in [CVX-001](CVX-001_results.md) remain applicable.

## Verification and next registered action

The nonlinear residual directional-derivative check was **6.22e-12** relative;
the independent full linear residual check was **2.47e-16**. Polynomial stencil
error was **1.71e-13**, and the small qualification matrix had rank **343/343**.
For the successful case, the analytic normal derivative's finer off-surface
finite-difference error was **1.34e-10**. Linear stationarity stayed below
**1.82e-14** in all 24 solves; all used scaled sparse normal equations and none
invoked the declared LSMR fallback. These checks verify implementation
consistency, not stability of the inverse problem or accuracy of the spatial
discretization across an interface.

The complete screen took **113.60 s** on the recorded host, including data
generation, both successful fits and their physical checks, and the retained
qualification failures. Source hashes remained unchanged during execution.

Both successful arms meet the pre-registered development-refinement rule:
at least 25% sampled RMS improvement, at least 0.10 IoU improvement, and passed
linear/forward qualifications. That rule did not require good paired residuals
or improved Hausdorff distance, so refinement eligibility must not be read as
recovery qualification. The next authorized action is the unchanged pair of
57×57 runs on `circle__c0.5`, with the same parameters and iteration cap. Their
results are pending at this screen checkpoint.

The present conclusion is limited but concrete: a jointly unknown reference
field and smoother frequency secants can produce a better low-contrast
coefficient image from augmented Cauchy data. This weight did not improve that
result, physical binary-shape prediction remains poor, and the single-valued
log requirement blocks the other preselected cases. These numbers justify
the registered resolution check; they do not justify a global-convergence
claim, adoption as the maintained solver, or a TG-002 recovery claim.
