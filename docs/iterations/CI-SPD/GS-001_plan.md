# GS-001 — single-frequency GauGal high-contrast probe

Preregistered 2026-10-05 in response to the user's request to try GauGal on
one high-contrast benchmark scene and see how far one frequency takes it.
This request authorizes this bounded probe. It does not launch GP-001.

- Case: TG-002 `c_shape__c13.3`; prescribed centred 65 mm circle, no grid search.
- Data: only the frozen 24 paired real-frequency measurements at 0.5 GHz
  (catalog index 2). No damped data or other frequency enters the optimizer.
- Adaptation: known material, bounded occupancy coefficients in [0,1], using
  the pinned read-only GauGal source and ON-002 physical kernel/paired adapter.
  This is an adapted GauGal volume inverse, not its released cylinder setup.
- Primary grid: 128 pixels / 112 Gaussian centres per axis, sigma/spacing 0.8,
  complex128. A single escalation to 256/224 is allowed only if the primary
  start-disk field discrepancy exceeds 1%; the inverse then uses that grid.
- Inner solve: exact separable Gaussian mass preconditioning of the unchanged
  Galerkin equations, pinned batched BiCGSTAB, 400 iterations, true residual
  <=1e-6. If necessary, an independently tested batched BiCGSTAB with relative
  scalar division and per-channel convergence may replace the pinned solve;
  this changes the linear solver, not the operators or physical objective.
- Before fitting: dense small-grid operator/direct-solve/complete-gradient
  tests, full-grid system and paired-sensor adjoints, start disk versus Mie,
  and an occupancy directional finite difference. Failed qualifications and
  rejected trials stay in the evidence. Solves above tolerance cannot update.
- Inverse: projected gradient with GauGal coefficient-TV proximal steps;
  objective = half squared relative data residual + lambda times mean
  isotropic coefficient TV. Lambda=1e-3 for steps 0–99, 1e-4 for 100–199,
  1e-5 for 200–299. Initial step bounds the maximum occupancy change to 0.05;
  subsequent accepted steps grow by 1.5, capped at maximum raw change 0.1.
  At most 12 backtracks per iteration, 300 accepted updates, 30 minutes fit
  wall time. Stop at <=0.003 data residual or unresolved/stalled update.
- Readout: save initial and every 25 accepted states, loss/residual histories,
  inner true residuals, timings, final native image and fixed 0.5 contours.
  After fitting only, read the truth for occupancy IoU, centroid/area error
  and symmetric contour distances. Report all contours, including fragments.
  Compare the initial and final image with truth in a standalone figure.
- Numerical/model limits: measure start-disk field agreement separately;
  post-fit truth rasterization/forward residual is interpretation only. A good
  single-frequency fit is not the all-frequency TG-002 recovery criterion.
- Use the existing checkout and shared compute/source/Git coordination locks;
  do not disturb the running CS-001 job. No branch or worktree creation.
  Preserve other workspace changes. Validate, commit and push this probe's
  code, plan, results and failed evidence to the existing branch.
