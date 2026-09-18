# LAU-005 — does calibration uncertainty explain scattering-assisted shape recovery?

- **Approval status:** APPROVED by the user's 2026-09-18 instruction, *"tryout the
  alternative in the laurent report since we are dropping compression bit for
  now."* That selects the alternative the
  [outsider priority review](../iteration_06/02_proposals/01_outsider_priority_review.md)
  left open: park generic trace compression, prioritise the direct
  inverse-information question, and turn the deferred row *"study shape/calibration
  identifiability using the compiled scattering path"* into a focused successor.
  Existing checkout and branch only; no branch or worktree creation.
  **Compression is parked, not closed:** LAU-001…LAU-004 code, thresholds and
  bundles are untouched, and the review's reopening condition still stands.
- **Execution status:** COMPLETE, 2026-09-18. Both stages ran inside budget
  (1200 of 1400 fits, 606 of 700 oracles, 824 s of 3600 s).
  [Closeout](../iteration_07/01_results.md) ·
  [bundle](../../../../results/validation/laurent/LAU-005-20260918-calibration-sweep-01) ·
  [report](../../../../results/validation/laurent/LAU-005-20260918-closeout/README.md).
  Outcome: **mechanism confirmed on the configuration the neighbour study analysed and
  refuted as a general rule** — the coupled advantage survives exact calibration in
  137 of 189 cells. Fisher and nonlinear orderings agreed at every tested `tau`, so the
  "investigate further" branch was not triggered.
- **Question:** the [neighbour study](../../../../results/experiments/laurent_neighbour_20260916/report.md)
  attributes its coupled-versus-additive gain to *scattering-assisted separation
  of shape and calibration*. Does that benefit vanish continuously as antenna
  calibration improves, and **at what calibration precision does an uncertain
  neighbour stop paying for itself?**
- **Falsifiable hypothesis:** the coupled/additive target-harmonic precision ratio
  is a monotone non-increasing function of calibration precision and reaches
  `<= 1` at perfect calibration. The hypothesis is **wrong** if a coupled
  advantage `> 1` survives at vanishing calibration uncertainty on the selected
  configurations, or if the ratio is non-monotone in the sweep — either would mean
  an illumination mechanism the report's interpretation does not cover.
- **Baseline:** the recorded neighbour bundle
  [`laurent_neighbour_20260916/`](../../../../results/experiments/laurent_neighbour_20260916)
  and its `coupling_control/`, at commit `cfe35ea`. Its two endpoint columns are
  **pinned reference values**, not re-derived: free-gain CRLB
  (`radial_rms_crlb_mm`) and known-gain CRLB (`known_gain_radial_rms_crlb_mm`).
- **Intervention:** one mechanism — replace the binary gains-known / gains-free
  treatment by a **continuous Gaussian log-gain prior** of scale `tau`, applied
  identically to the Fisher analysis and to the nonlinear inverse.
  `tau` multiplies the study's own truth gain scale `s = (0.15 nepers, 0.25 rad)`,
  so `tau = 0` is exact calibration, `tau = 1` is the recorded study's truth
  scale, and `tau -> inf` is the recorded free-gain arm. Report `tau` also as
  `1.303*tau` dB and `14.32*tau` degrees. Nothing else moves: same acquisition,
  frequencies, mask, absolute noise, shapes, truths, initialisations, bounds,
  compiler and oracle.
- **Arms and stages:**
  - **A, information sweep (all 63 screen configurations).** For every candidate
    in the existing screen — separation 105/140 mm, 30-degree angle grid,
    neighbour permittivity 3/12/24 — and each of the 3 prior shape pairs, compute
    the marginal target-harmonic CRLB over a `tau` grid for `absent`,
    `{known,unknown}_additive` and `{known,unknown}_coupled`. Solve for the
    crossover `tau*` at which coupled precision equals additive precision, and
    report its distribution over configurations. Selection of the two named
    configurations is inherited, not redone.
  - **B, matched nonlinear recovery (interaction-specific configuration).**
    `tau` in `{0, 0.03, 0.1, 0.3, 1.0}` with a **matched** prior: truth gains are
    drawn at scale `tau*s` and the inverse carries exactly that prior. Plus one
    **bridge arm** at `tau = 1` with the recorded study's flat (improper) gain
    prior, which must reproduce its published medians. Five arms, 2 shape pairs,
    10 gain/noise seeds, 2 initialisations, lower-training-cost start selected
    without truth.
- **Controls:**
  - **Endpoint reproduction.** Stage A at `tau -> inf` must match the recorded
    free-gain CRLB and at `tau = 0` the recorded known-gain CRLB, both to
    `<= 1e-8` relative, on every configuration/prior/arm. This is the primary
    guard that the new algebra is the same quantity.
  - **Monotonicity.** CRLB must be non-decreasing in `tau` — a looser prior
    cannot add information. Checked on every swept curve, not just asserted.
  - **Known-gain additive inequality.** At `tau = 0` an additive neighbour cannot
    beat the isolated target; the existing test is re-run unchanged.
  - **Shared randomness.** One standard-normal gain draw per seed, scaled by
    `tau`, so every `tau` shares noise and shape truth and the sweep is paired.
  - **Matched data.** The additive arm keeps its own correctly matched synthetic
    observations and inverse; it is never a mismatched model of coupled data.
  - Same fixed absolute noise (1% of the nominal isolated target) at every `tau`
    and in every world; it is not rescaled when the scene gets brighter.
- **Scope and shared interfaces:** new package
  `experiments/laurent_identifiability/`. It imports `laurent_neighbour`,
  `laurent_calibration`, `modal_muller_research` and `solvers/` **read-only**;
  their source hashes must continue to validate against the recorded neighbour
  and LAU-00x manifests. No production solver, default or prior bundle changes.
- **Metrics and comparison criteria:** marginal target-harmonic radial RMS CRLB
  (mm) against `tau`; coupled/additive and additive/absent precision ratios;
  crossover `tau*` with its dB/degree reading, and its distribution over the 63
  configurations; nonlinear median and ensemble shape RMS per arm per `tau`, with
  seed-paired differences and bootstrap intervals resampling seeds within each
  fixed shape pair; agreement between the Fisher-predicted ordering and the
  nonlinear ordering.
- **Compute budget and stopping rules:** stage A `<= 2` minutes (Jacobians once
  per configuration/prior/world; the `tau` sweep is linear algebra). Stage B
  `<= 1400` nonlinear fits, `<= 700` 192-node oracle checks, 60 minutes, 6 GiB,
  single BLAS thread. Stop and record if endpoint reproduction fails, if any
  swept curve is non-monotone beyond `1e-9`, or if any recovered state fails its
  fresh full-boundary check at `1e-8`.
- **Artifacts:** fresh `results/validation/laurent/LAU-005-20260918-<stage>-<nn>/`
  and a `LAU-005-20260918-closeout/` report. Raw sweep, recoveries, summaries,
  paired statistics, qualification and source/environment manifest are saved;
  failed arms are retained.
- **Decision criteria:**
  - **Mechanism confirmed** if the ratio is monotone and `<= 1` at `tau = 0` on
    both named configurations: report the crossover calibration precision as the
    condition under which an uncertain neighbour helps, and state it as a
    local-Fisher result corroborated at the tested `tau` by nonlinear recovery.
  - **Mechanism refuted** if a coupled advantage survives exact calibration:
    record it, and the neighbour report's interpretation is revised rather than
    the result discarded.
  - **Investigate further** if Fisher and nonlinear orderings disagree at any
    tested `tau`; that discrepancy becomes the next cycle's question.
  - No production promotion, no speed claim, no Laurent-specific novelty claim,
    and no field-GPR claim follows from any outcome.
- **Standing limits:** unchanged from the track handoff and the neighbour report —
  lossless homogeneous 2-D TMz, relative permittivity 6 exterior, one target plus
  at most one neighbour, disjoint bounding circles, known component count and
  identity, locally constrained initial guesses, surface-style acquisition with no
  air/soil interface, antenna pattern, clutter or conductivity. Gains are modelled
  as per-antenna complex log factors with one transmitter reference; a Gaussian
  prior on them is a modelling choice, not a measured calibration distribution.
  Two fixed shape pairs and ten seeds are feasibility statistics.
- **Owner:** Claude. **Reviewer:** unassigned.
