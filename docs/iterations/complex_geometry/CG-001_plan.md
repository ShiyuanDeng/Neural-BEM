# CG-001 — physical folds and complex geometry monodromy

Pre-registered 2026-10-11, before measurement. User authorized Track 12 research
and explicitly selected the existing `feature/shape-frequency-continuation`
branch. Root owns implementation and measurements; `theory_review` and
`implementation_review` independently reviewed the mathematical design.

## Question and scope

Can genuinely complex geometry transport a stationary solution around a
qualified fold of a transmission-data objective and return to a different
valid real stationary shape? Does that transport yield a minimum, or merely
exchange a minimum and maximum? This is an architecture component experiment,
not a new unrestricted inverse or a TG-002 recovery claim.

Use a fixed-center disk with radius q in the repository's 50 mm length units.
The start is exactly TG-002's centered 65 mm circle, q0=1.3. Data are the
sealed TG-002 `circle` observations, including their off-center placement;
the fitting instrument receives observations only. Fixing the center creates
deliberate model mismatch. No truth, alternate initialization, localization
grid, far start, or extra acquisition enters continuation. Sampling a scalar
stationary branch is a component diagnostic, not a grid-search initializer.

This changed construction uses exact Mie transmission physics to isolate the
continuation mechanism before undertaking a general complex BIE engine. It
does not use complex frequency. The maintained real solver is untouched.

## Derivation and predictions

For fixed real exterior k and interior ki=k sqrt(contrast), let

    N = ki Jn'(ki q) Jn(k q) - k Jn(ki q) Jn'(k q)
    D = k Jn(ki q) Hn'(k q) - ki Jn'(ki q) Hn(k q)
    cn = (i/4) N/D.

Multiply cn by the exact, fixed-center line-source/receiver cylindrical waves,
sum over n, and include source strength. This follows from matching field and
normal derivative at the disk interface; the Bessel Wronskian establishes
equivalence to the maintained Mie formula. Radius derivatives through order
three use Bessel derivatives, Leibniz products and quotient differentiation.
The mode cutoff stays fixed throughout each trajectory.

Normalize each frequency by the observed norm and square root of frequency
count. With g0=g(q0), delta=d-g0, and gsharp(q)=conj(g(conj(q))), use

    r = g(q)-g0-t delta
    rsharp = gsharp(q)-conj(g0)-t conj(delta)
    PhiC = rsharp.T r / 2
    F = (gsharp'.T r + g'.T rsharp)/2 = A(q)-t B(q).

All transposes are bilinear. Conjugating the current t or q inside a residual,
dropping its imaginary part, or using Gauss–Newton instead of Fq changes the
problem. Fq includes the residual-weighted second derivatives. Fqq includes
third derivatives. On the real axis this is exactly the ordinary data-loss
gradient. The real stationary branch is t(q)=A(q)/B(q), wherever B != 0.

A simple fold obeys F=Fq=0, Ft=-B != 0, Fqq != 0. Locally
Ft*(t-tf)+Fqq*(q-qf)^2/2=0. A semicircle past tf normally ends at complex q;
one complete loop swaps the two local sheets, and two loops restore the
original sheet. Real pseudo-arclength also crosses a simple fold. Thus a
successful complex loop is not by itself an advantage over real continuation,
and the exchanged real stationary point is expected to reverse Hessian sign.

## Registered stages and gates

1. **Tracker and physics qualification.** A cubic with known folds validates
   loop permutation, double-loop restoration and complex endpoints. Exact
   real disk fields and radial derivatives are checked independently against
   CPU nodal Kress at N512/N1024 at radii 0.7, 1.3 and 1.8, contrasts .5/4/13.3,
   frequencies .5 and 2.5 GHz (18 states). Relative field and derivative
   tolerances 1e-8 and 1e-6. At q=1.1+.03i and 1.3-.02i, check modal refinement
   and symmetric real/imaginary directional derivatives (1e-6 derivative
   tolerance, 1e-8 field refinement). Never replace nonfinite modes by zero.
2. **Physical fold census.** Frozen model order: contrast 13.3 at .5, 1, 1.5,
   2, 2.5 GHz; then contrast 4 and .5 at 2.5 GHz; then contrast 13.3 with all
   19 real frequencies. Scan q in [.5,2] with 601 points. Refine sign changes
   of A'B-AB' with a scalar root solver. Retain all candidates and failures;
   a non-sign-changing fold may be missed. Qualify |F|,|Fq| <= 1e-8 times
   their constituent scales, |Ft|,|Fqq| > 1e-6; require refined cutoff fold
   coordinates within 1e-7. Count folds with t in [0,1] separately from
   diagnostic extensions t in [-2,3].
3. **Continuation controls.** Select the first model in the frozen order
   having a qualified positive-t fold connected to q0 without a pole in t(q),
   preferring the first fold encountered toward increasing t. If none, use
   the nearest qualified fold in q, explicitly labeling it a local component
   control rather than a start-connected example. Base loop radius is 0.02
   in t, reduced to isolate nearby real fold values, minimum 1e-5. Compare
   natural-parameter tracking through the fold, real pseudo-arclength, upper
   and lower semicircle detours, one and two loops, and reverse-path transport.
   Endpoint reality <= 1e-8 in q, stationarity <= 1e-8, two-loop restoration
   <= 1e-7, conjugate symmetry <= 1e-7. Require nonzero imaginary geometry
   during complex paths and retain the returned Hessian sign and data loss.
   Verify tracked states at cutoff+12 and half continuation step. Independent
   review amendment, before measurement: also repeat at half loop radius and
   check endpoint separation against the local square-root prediction. Nearby
   real fold values alone do not isolate complex critical values or poles.
   Failure of local-pair/swap/restoration checks means unqualified or nonlocal
   transport, not demonstrated monodromy of this fold.
4. **Conditional exploration.** If one-loop transport qualifies, try one
   additional adjacent fold from the same stationary branch, where the census
   supplies one, to test whether two branch exchanges can return a different
   real minimum. Preselect by nearest radius along the branch, not loss or
   truth. Stop at a branch-domain refusal or after two such fold tours. This
   is exploratory component evidence; no global-minimum claim.

## Numerical domain, work and stop rules

Use principal Hankel functions only in Re(q)>0.25 and |Im(q)|<0.5, and
Re(q)<2.5. These bounds prevent crossing the radius branch cut/zero, but do
not prove absence of transmission poles. Monitor min |D|/(|term1|+|term2|),
refuse below 1e-10, record minimum margin along every accepted path. Fixed
cutoff ceil(k sqrt(max(contrast,1))*2.5+24); refinement adds 12. Newton uses
analytic Fq, predictor dq/dt=-Ft/Fq, adaptive subdivision, <=10 corrector
iterations, 20,000 attempted steps/path, minimum step 1e-8. Prevent large
corrector jumps from masquerading as branch tracking. Pseudo-arclength solves
the augmented real system with its full 2x2 Jacobian.

One CPU process, one BLAS thread, 30 minute overall wall budget, at most
12 physical path arms plus their step/cutoff checks. Qualification and scan
work is charged. Log field-frequency evaluations, derivative jets, attempted
and failed steps, wall time, process peak RSS, source/input hashes, complete
accepted states, exceptions and failed candidates. No speedup claim.

An implementation defect may receive one bounded correction followed by
requalification; preserve the original failed bundle. An absent fold is
inconclusive about the architecture. A qualified loop ending at a maximum
supports sheet transport and refutes the stronger inference that fold bypass
automatically improves inversion. A complex endpoint is not a recovered shape.
Do not continue to a 30-case inverse campaign from this component evidence.

## File map, validation and preservation

- `solvers/bem_inverse/complex_radius.py`: isolated opt-in holomorphic disk
  and scalar continuation instrument; no experiment/result dependencies.
- `experiments/benchmark/cg001.py`: qualification, frozen census, path arms,
  receipts and read-only report/plots.
- `pytest/bem_inverse/test_complex_radius.py`: independent mathematical
  controls, mirror correctness, branch permutation and domain refusals.
- `docs/iterations/complex_geometry/`: plan, derivation and results.
- `results/validation/complex_geometry/CG-001/`: immutable run bundles.

Before each run, run focused numerical tests and TG-002 seal verification.
After each new run (including failure), validate/read back, commit and push
code, notes and evidence to the configured current remote, verify remote HEAD
and working-tree status, before further measured experiments. A results report
is reconstructed from saved JSON; plotting must not fit or retune.

## Primary sources and applicability

- Dölz and Henríquez, [shape holomorphy](https://arxiv.org/html/2305.19853):
  holomorphic operator families and local inverse stability, especially
  Proposition 5. Their detailed scattering application is sound-soft, so it
  does not certify this transmission implementation.
- Hiptmair, Schwab and Spence, [frequency-explicit transmission shape
  holomorphy](https://arxiv.org/html/2408.01194v2), Theorem 4.1 and §§1.3–1.4:
  the quantitative nontrapping domain assumes star shapes and interior index
  below the exterior index. It does not guarantee the same domain at contrast
  4/13.3; nearby complex poles are a specific risk, to be measured.
- Dickson et al., [pseudo-arclength conditioning](https://arxiv.org/pdf/math/0603716),
  Definition 2.5 and §3: the augmented system can remain regular at simple
  folds, motivating the mandatory real control.
- [DLMF §10.11](https://dlmf.nist.gov/10.11), especially 10.11.7–9: Hankel
  analytic continuation and conjugation; the mirror is an analytic reflected
  function, not the same outgoing function evaluated without conjugation.

The scalar branch and square-root predictions above are our deductions.
They are not a global convergence theorem. The earlier repository statement
that complex paths “always” get past turning points is only locally applicable:
poles, branch cuts, escape and nonreal endpoints remain possible.
