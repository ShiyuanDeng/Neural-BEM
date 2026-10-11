# CVX-001 Track 13 formulation study

Pre-registered 2026-10-11 before numerical measurements. The user requested a
thorough investigation of Track 13 in the architectural backlog. This is a
literature, derivation and component study, not an inverse campaign or a
qualification of a new solver. Work stays isolated in the existing checkout;
no branch or worktree is created. Pending Track 12 work is unrelated.

## Question

Can a Carleman auxiliary-field formulation accommodate the maintained TMz
transmission physics and the actual TG-002 measurements? Separate three issues:
the PDE across a coefficient jump, the regularity of the transformed unknown,
and the information needed to prescribe its boundary conditions. A formulation
that assumes unmeasured Cauchy data does not qualify as a TG-002 competitor.

Predictions to try to falsify:

1. The jump in TMz is a bounded zeroth-order potential, not a discontinuity in
   the principal Laplacian. The normalized log field generally is not H3, but
   differentiating with respect to frequency cancels its second-derivative
   jump and can produce an H3 auxiliary field.
2. Even a reciprocal low-angular-band exterior kernel has a nontrivial null
   direction under the paired acquisition. Reciprocity alone cannot fill its
   missing source-receiver matrix. This is a statement about unrestricted
   exterior kernels, not nonuniqueness of binary shapes. The witness is not
   asserted to satisfy passivity/unitarity or to be realizable by one object.
3. Twenty-four receiver samples, even for a fixed source, do not determine a
   continuous Dirichlet trace or its normal derivative without extra bounds.
4. A printed Carleman weight must be checked numerically before attributing
   numerical performance to it; normalization removes overflow, not its
   relative dynamic range.

## Bounded diagnostics and controls

The single isolated driver is `experiments/convexification/formulation_checks.py`.
It writes fresh results under `results/validation/convexification/CVX-001/`.
Use the EMNerf environment, CPU, one thread. Hard wall ceiling: five minutes.
No optimizer, tuning, target selection, reconstruction or new synthetic inverse
data is needed. All analytic cases are controls, not extra benchmark scenes.

- **Flat interface:** exact normally incident Fresnel solution, normalized
  background coefficient 1, contrasts 0.5/4/13.3, dimensionless k=0.5/2/5.
  Evaluate log derivatives from field jets on both sides. Check continuity
  of u and ux, the predicted jump in vxx, cancellation in qxx for
  v=log(u/u0)/k² and q=vk, and the nonzero jump in qxxx. Compare frequency
  differentiation with centered differences at relative steps 1e-3 and
  5e-4. Algebra residual <=1e-11 relative to max(1, reference scale);
  fine finite-difference error <=1e-6 on the same scale. Nonzero qxxx jump
  demonstrates the next regularity boundary; no full inverse theorem follows.
- **Paired kernel:** ring radius 0.30 m, 24 equally spaced sources and
  receiver offset 0.2 radians, as in the frozen acquisition. Use
  K(theta_r,theta_s)=cos(theta_r-theta_s)-cos(0.2), with an outgoing Hankel
  extension in each argument. Check paired zeros <=1e-12, nonzero complete
  matrix, reciprocity <=1e-12, and the rank/nullity of the degree-one symmetric
  tensor sampling map (six coefficients). Compare the full matrix sampling
  map; rank tolerance 1e-12 times its largest singular value.
- **Fixed-source sampling:** the outgoing mode-24 minus mode-0 witness,
  normalized on the 0.30 m ring, vanishes at the 24 receiver angles. Evaluate
  unsampled trace and radial derivative, and inward continuation to 0.15 m
  at 0.25/1/2.5 GHz in epsilon_background=6. Check sampled trace <=1e-12,
  finite nonzero off-grid values and derivative. Compare modes 0/12/24/36
  continuation factors. This is a trace-completion limitation, not proof that
  two TG-002 shapes are indistinguishable.
- **Weight arithmetic:** independently evaluate the literal parameters in
  arXiv:2404.04145v2, Lemma 3.1/eq. (3.5) and section 4.2:
  exp(2 lambda |x-x0|^-beta), x0=(0,-10), beta=20, lambda=6,
  x in [-1,1]^2. Record high-precision log range, float64 weight range,
  and contrast with dimensionless generic log spans 10/40/100. This checks
  the printed specification, not unpublished code. Do not infer its actual
  implementation or disprove its theorem.

## Evidence and stopping

Retain source hashes, exact command, environment, elapsed time, arrays, summary,
validation failures and a plot. An exception or failed gate ends the run and
is retained. Fix an implementation defect only with a documented amendment,
not a relaxed scientific gate. No parameter sweep beyond these declared
controls. Stop once the formulation question is answered at this scope.

Root owns all edits and measurements. Independent agents review primary
literature, derive the transmission equations and audit the data contract.
The report must identify theorem assumptions and exact equation/section
locations, distinguish deductions from published results, and name a single
discriminating next step. Verify artifacts, then commit and push only Track 13
work to the current branch's remote; preserve concurrent work separately.
