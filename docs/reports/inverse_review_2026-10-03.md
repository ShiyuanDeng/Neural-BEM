# Critical review of the current inverse pipeline

Review date: 3 October 2026. Checkout: `feature/shape-frequency-continuation`, commit `27904e7d536f` (the full reviewed hash is recorded in the accompanying audit). The user explicitly selected this existing branch for the review.

**Verdict under the user's clarified definition: a working node-free modal inverse exists, with numerical qualification on six core configurations; full-suite qualification and a performance advantage over the literature remain unestablished.** Here “node-free” permits parameter-space geometry quadrature and excludes a Cartesian spatial quadrature discretization of the physics; the modal backend also avoids boundary-collocation unknowns. It does not mean sample-free. Its strongest recent controlled improvement is a **1.65× complete-path speedup on six development configurations**, with unchanged numerical trajectories, from moving geometry certificates to the GPU. The best all-36 recovery result uses **nodal physics and additional full-matrix observations**. These are separate results, not one demonstrated combined pipeline.

The main research priorities should now be a fair external baseline, a defensible measurement contract, and broader qualification of the current modal combination. Further representation changes and relaxed-BIE variants have lower evidential value until those gaps are addressed.

## Scope and how this review was checked

This is a critical assessment of maintained code and saved evidence, informed by a targeted primary-literature review. It is not an independent laboratory replication, an exhaustive novelty search, or a new inverse campaign. The reviewer is Codex; no independent second reviewer is claimed.

I read the maintained [package API](../../solvers/bem_inverse/README.md), relevant implementation, campaign definitions, current handoffs, failed-run records and primary papers. I also recomputed summary statistics from saved JSON, checked 36 nodal endpoints and 36 full-matrix endpoints against their summaries, inspected all 18 fresh CPU/GPU modal pairs, verified their exact final-curve equality, work/outcome equality and passing endpoint audits, and recalculated timing medians. Source-archive hashes for CI-001 and NU-007a and the input hashes in the FM-002 comparison were checked.

The [read-only audit script](inverse_review_2026-10-03_audit.py) and [machine-readable findings](inverse_review_2026-10-03_audit.json) record **141 distinct saved JSON inputs** and their SHA256 hashes. The script does not import a solver, generate observations, fit shapes, or modify historical bundles. Its raw-pair checks do not independently reconstruct every accepted intermediate state; the more extensive trajectory-identity claims below are attributed to the campaign's qualification records. Historical pytest counts are reported as recorded, not as freshly rerun tests.

## What is actually implemented

The maintained inverse is now in `solvers/bem_inverse/`. Campaign selection, synthetic observations and truth scoring remain outside that package. `Problem` contains fitting inputs without a target or scene identifier. This is a meaningful architectural improvement: it makes an externally usable solver and separates optimizer decisions from retrospective truth scoring. It does not by itself make the development benchmark independent of prior tuning.

The core problem is shape recovery for a smooth, homogeneous, equal-density transmission inclusion with known contrast. Geometry is an explicit Cartesian Fourier curve with projected normal updates. This maintained pipeline is not a demonstrated neural-SDF inverse merely because the repository name contains “Neural SDF.” Earlier neural, topology, TE, lossy and three-dimensional experiments do not automatically become capabilities of this particular runner.

| Selection or capability | Current status | Qualification limit |
|---|---|---|
| Public default | `nodal_kress` with spline projected geometry | All-36 historical campaign exists; 28 retention passes, 34 recoveries |
| Modal physics | Explicitly register and select `modal_muller` | Fourier–Galerkin trace unknowns; no boundary collocation unknowns in the operator |
| Spline-free geometry | Explicit `spectral` or `certified_spectral` | Normal moves and reparameterization still use sampled quadrature |
| Latest CUDA certificate path | `certified_spectral` selects the qualified GPU implementation on CUDA | Six core cases, three pairs per case; CPU fallback is retained for device-memory exhaustion |
| Analytic geometry tangent | Explicit `analytic_spectral` | Local derivative checks and one bounded inverse; not broad trajectory qualification |
| Full-matrix observations and relaxed loss | Opt-in nodal capabilities | Their success is not a modal/node-free result |
| Resolution recovery | Opt-in nodal response with resumable optimizer state | Four stopped development tails; no additional recoveries |

Sources: [geometry selection](../../solvers/bem_inverse/geometry_selection.py), [runner](../../solvers/bem_inverse/runner.py), [problem contract](../../solvers/bem_inverse/problem.py), and [campaign guide](../../experiments/cleaned_interface/README.md).

An explicit example of the strongest qualified modal combination is:

```python
from bem_inverse import fit, Execution
from bem_inverse.modal_muller import register

register()
result = fit(
    problem,
    solver="modal_muller",
    geometry_update="certified_spectral",
    execution=Execution(device="cuda", frequency_threads=4),
)
```

This requires a valid `Problem`, including the prescribed real and damped observations. It is a selection example, not a claim that arbitrary inputs have been qualified.

## Is the complete inverse node free and verified

**Yes under the user's clarified definition, which allows integration in the curve parameter.** The earlier version of this review treated absence of all samples as the criterion; that was stronger than the intended meaning. Geometry quadrature in theta is not an objection to the intended node-free claim.

For an operational definition, the modal inverse has coefficient-space boundary unknowns and coefficient-space operator construction, without evaluating the boundary-integral kernels by quadrature over Cartesian boundary points. Geometry-only integration in the curve parameter is allowed. The fact that theta is one real variable is not sufficient by itself to distinguish methods: ordinary nodal two-dimensional BEM can also use a theta parameterization. Its nodal unknowns and pointwise kernel discretization distinguish it from this modal implementation. Evaluating z(theta) to obtain coordinates for geometry operations does not turn those operations into a Cartesian spatial discretization of the physics.

**Verification is a separate question.** Complete paths are numerically qualified on the six core configurations. The latest combined implementation lacks all-36 qualification, and the validity bounds do not have rigorous floating-point error enclosures. Neither limitation is caused merely by allowing parameter-space quadrature. The table below records the implementation's sampling and arithmetic scope, not a list of disqualifications from the clarified node-free definition.

| Component | What remains | Consequence for the claim |
|---|---|---|
| Modal operator | Laurent/Fourier arrays, padded convolution and modal traces | Supports boundary-collocation-free physics |
| Finite geometry move | Sampled displacement and normals followed by an FFT fit | Not a sample-free geometry update |
| Arclength reset | Numerical quadrature of nonlinear speed and oscillatory phase | Spline-free does not mean exact coefficient algebra |
| Metric and observable frontier | Sampled speeds, normals and arclength harmonics | Sampling exists outside the forward operator |
| Certificate proposal | A sampled torus minimum proposes an interval | A coefficient residual subsequently checks the proposal |
| Inconclusive validity | Sampled polygon/speed fallback remains available | A geometry check, not physical-kernel quadrature; prevents a sample-free claim |
| Arithmetic verification | Float64 FFT arithmetic with a heuristic allowance | Numerical evidence, not an interval-verified proof |
| Geometry tangent | Retained fast CUDA preparation uses finite-difference projection tangents | A reciprocal physics derivative does not make every pipeline derivative analytic |

These observations are explicit in [the prior node-free audit](../iterations/cleaned_interfaces/iteration_17/01_results.md), [certificate implementation](../../solvers/bem_inverse/certified.py), [modal geometry](../../solvers/bem_inverse/modal_geometry.py), and [modal frontier/receipts](../../solvers/bem_inverse/modal_muller.py). The receipts themselves say `end_to_end_sample_free=False` and `arithmetic_verified=False`. The first flag is compatible with the user's node-free definition; the second limits rigorous-verification claims.

The certificate idea is substantive. With the divided difference (W=(z(w)-z(v))/(w-v)), λ = |W|², and a finite Laurent polynomial Y, the complete residual condition `r = ||1 - lambda Y||_1 < 1` gives `lambda >= (1-r)/||Y||_1 > 0` in exact arithmetic. This can certify regularity and injectivity. The missing part of a computer-assisted proof is rigorous enclosure of the implemented floating-point operations. The relevant distinction is explained in [Rump's verification review](https://www.tuhh.de/ti3/paper/rump/Ru10.pdf); a safety allowance without a proved error bound does not provide that enclosure.

Likewise, nonlinear speed and phase functions do not retain finite Fourier support. Periodic trapezoidal quadrature can converge very rapidly, but finite-grid aliasing remains. [Trefethen and Weideman](https://people.maths.ox.ac.uk/trefethen/publication/PDF/2014_149.pdf) provide the mathematical context. The project's own aspect-100 ellipse check changes from approximately 6.06e-4 coefficient error at 64 quadrature samples to 3.80e-15 at 2048. That is successful numerical convergence, not evidence that samples were unnecessary.

**Recommended terminology:** “Node-free Fourier–Galerkin Müller inverse, with coefficient-space physics and parameter-space geometry quadrature.” Define node-free at first use and specify that there are no boundary-collocation unknowns. Use “numerically verified on the six core configurations” for the current inverse evidence, and distinguish it from full-suite qualification and rigorous floating-point verification.

## Performance that the evidence supports

### Recovery and retention are different outcomes

The frozen recovery predicate requires a passing numerical audit, boundary RMS ≤ 1 mm, Hausdorff upper bound ≤ 2 mm, and each real-frequency residual ≤ the larger of 0.003 and three times the realized relative noise. Historical retention compares with a previous result using separate absolute/relative tolerances. A failed reconstruction can retain a failed historical baseline.

| Evidence | Recovery | Retention or qualification | Interpretation |
|---|---:|---|---|
| CI-001 nodal, paired observations | **34/36** | **28/36** historical passes | Broadest paired-data default evidence; two high-contrast C starts fail |
| Original CI-001 modal campaign | **28/36** | **19/36** passes | Older modal profile; exposed Graf and trace-resolution limits |
| Modal repair rerun | Nine affected configurations | **7/9** pass and match nodal | Remaining 27 were not rerun under the repaired profile; do not invent a new all-36 score |
| Latest NU-007a modal plus certified spectral geometry | **6/6** core configurations | 18/18 CPU/GPU pairs qualified; five PASS and one retained REGRESSION | Strong local retention, no new recovery benefit |
| FM-001 ordinary full-matrix nodal arm | **36/36** on full-data recovery | **32/36** on unchanged paired recovery; **15/36** historical paired retention | More observations and a different aggregate stopping contract |
| FM-002 corrected relaxation | Damped ordinary and relaxed: **3/3 each**; real-prefix ordinary and relaxed: **1/3 each** | All 12 selected runs completed | No added recoveries from relaxation |
| RB-001 refined continuation | **0/4** additional full or paired recoveries | All four finer endpoint audits pass | Removes immediate numerical stops without solving the recovery problem |

Evidence: [CI-001 comparison](../../results/validation/cleaned_interfaces/CI-001/comparison.json), [original modal campaign](../iterations/cleaned_interfaces/iteration_06/01_results.md), [repair rerun](../iterations/cleaned_interfaces/iteration_07/01_results.md), [NU-007a](../../results/validation/cleaned_interfaces/NU-007a-20261003/README.md), [FM-001](../iterations/cleaned_interfaces/iteration_18/01_results.md), [FM-002](../iterations/cleaned_interfaces/iteration_19/01_results.md), and [RB-001](../iterations/relaxed_bie/iteration_02/01_results.md).

In CI-001, **both unrecovered cases are among the 28 retention passes**. Conversely, all seven noisy cases recover but fail historical retention. Their errors are 0.0234–0.1582 mm RMS; five improve geometrically over the reference despite residual-gate failure. One noisy case has a genuine geometric regression. The all-case median RMS is 0.00366 mm, but the worst cases are approximately 6.396 mm. Reporting just the median would hide the most consequential failures.

### Best controlled recent timing result

The following are per-case medians over three repetitions of each arm. Both arms use modal physics, GPU geometry preparation, the same starts and observations, four frequency workers and one BLAS thread. The intervention is CPU versus GPU certificate evaluation.

| Core configuration | CPU certificate path seconds | GPU certificate path seconds | Latest RMS mm |
|---|---:|---:|---:|
| Wrong circle | 6.958 | 6.870 | 0.00000758 |
| Circle to star | 22.860 | 18.554 | 0.0188145 |
| Circle to C | 29.506 | 20.590 | 0.000975743 |
| Kite | 128.928 | 63.841 | 0.0118055 |
| Peanut | 17.737 | 15.936 | 0.00206817 |
| Hook | 41.203 | 23.842 | 0.00138729 |
| **Sum of per-case medians** | **247.192** | **149.634** | Six recoveries |

This is **39.5% less wall time, or 1.65× faster**. Certificate time falls from 103.496 to 7.477 seconds, a **13.84× component speedup**. The campaign reports identical accepted states, trial traces, decisions, units and final coefficients across all 18 pairs. The review independently confirmed raw final curves, work/outcomes and timing medians. Both endpoint audits pass in each pair. The star's existing historical residual regression is retained, not cured. [Qualification and raw samples](../../results/validation/cleaned_interfaces/NU-007a-20261003/qualification.json).

This is credible internal execution evidence. Limitations are three repetitions, one RTX 5090 host, six familiar low-contrast cases, and load sampling only at fit boundaries. The approximately 1.3% wrong-circle saving is too small to emphasize as a reliable individual speed advantage. The aggregate and expensive cases carry the useful result.

Earlier six-case totals were **572.8 s nodal**, **292.6 s modal plus spectral geometry**, and **198.5 s modal plus spline geometry**. These were single runs, not matched runtime pairs. Comparing 572.8 s with the latest 149.6 s produces an attractive approximately 3.83× ratio, but **that is a cross-campaign ratio, not a newly controlled modal-versus-nodal speedup**. Nor can the 13.84× certificate improvement be advertised as the inverse speedup. [Original timing scope](../iterations/cleaned_interfaces/iteration_12/01_results.md).

The full nodal CI-001 campaign records 4382 summed case seconds, approximately 73 minutes. FM-001 full acquisition records 3323 seconds, approximately 55 minutes. Data, schedules encountered, stopping decisions and host conditions differ; the second number does not establish that increasing measurement count makes the algorithm faster.

### What the latest negative results mean

FM-002 repaired a serious issue: the original relaxed loss gradient omitted geometry-dependent receiver/penalty derivatives, and one saved descent direction was nearly opposite the complete gradient. The subsequent factorial comparison separates relaxation from early damping. That is a strong methodological correction. It also substantially weakens the case for adopting relaxation: it adds no recoveries in the selected comparison.

RB-001 then showed that each of four numerical stops admitted a qualified finer-resolution or shorter step. After continuing under retained budgets, C errors ended at 22.957 and 9.849 mm, and star errors at 7.478 and 5.597 mm. Residuals remained roughly 0.95–1.05. The complete numerical phases cost 47.12 minutes. These are accurate evaluations of poor reconstructions, not successful inversions. The tails were time/quota limited, so they do not prove stationary wrong minima or universal failure of relaxation. [Saved endpoint comparison](../../results/validation/relaxed_bie/RB-001/comparison.json).

My assessment is to retain the corrected derivatives and resolution-response infrastructure, while keeping ordinary damped fitting as the default. More relaxation variants need a discriminating hypothesis; simply extending a sequence of small improvements in failed shapes is not a compelling next headline.

## How rigorous are the test cases

### Strong internal numerical discipline

The repository has substantial engineering evidence: preserved failures, frozen contracts, source/input seals, independent circle-series comparisons, forward resolution checks, complete-trial derivative tests, CPU/CUDA checks, original-start paths, work accounting and explicit numerical failures. NU-007a passed 864 offline trial comparisons on 72 states before its paired runs. The latest RB-001 qualification records 506 passing tests. These support implementation correctness within tested regimes.

The documentation also preserves rejected ideas: failed coefficient-update arms, the original GPU certificate comparison gate, incomplete paper reproduction and the bad relaxed gradient. That preservation strengthens the reviewability of the work. Test counts, however, measure code coverage and regressions; they are not counts of independent scientific successes.

### The suite is a development collection rather than a generalization study

The all-36 inventory comprises six core, six fresh/noisy, seven far-start and seventeen contrast configurations. Contrast `ki²/ke²` is 0.5 in 19 configurations, 2 in three, 4 in seven and 13.3 in seven. The review finds **15 truth-file paths but only 12 distinct exact coefficient arrays**. This count does not quotient out rotations, translations or parameterization, so intrinsic shape diversity can be smaller still. Repeated contrasts, starts and noise draws are worthwhile controls, but 36 configurations must not be described as 36 independent geometries.

The core cases have repeatedly guided development. Historically “fresh” targets have now been examined in multiple follow-ups. A truth-free runtime API prevents direct target access during fitting; it does not reverse this benchmark reuse. Statistical uncertainty calculated as if all 36 outcomes were independent would be misleading. A new holdout should be frozen by shape family, with all its contrasts, starts and noise draws kept together.

### Numerical accuracy and inverse identifiability need separate evidence

Independent nodal/modal calculations and refined synthetic oracles reduce discretization bias. They do not eliminate a shared physical-model bias or an inverse crime based on the same smooth geometry family, known material and ideal source model. Extremely small noiseless boundary errors show reproducibility in that setting, not experimental resolution. Even the circle's reported Hausdorff upper bound has a sampling/error-bound floor far above its tiny RMS.

The maintained all-36 problem assumes known contrast and one smooth component. It does not establish simultaneous material recovery, topology discovery, nonsmooth boundaries, partial-aperture robustness, uncertain antenna positions, correlated noise, unknown phase/gain, absorption or a three-dimensional vector Maxwell inverse. There is related exploratory work on several of these topics, but those results need their own scope and integration qualification.

There are only seven noisy configurations in this collection, mostly approximately 1% noise, with two draws on each of two fresh shapes and additional repeated-family contrast cases. This is useful regression coverage, not a noise robustness curve or a stable estimate of failure probability. Low-frequency nonuniqueness, indistinguishable geometries and uncertainty are not resolved by small residuals alone.

### Complex-frequency data are the most important fairness issue

`Problem` requires matched real and damped catalogs. The benchmark uses `k * (1 + 0.25j)` for the latter. CI-001 generated sixteen missing damped catalogs from truth; twenty existing catalogs were reused. Noisy damped observations use separately recorded draws. These are **additional observations from a synthetic oracle**, not a demonstrated stable transformation of the supplied noisy real-frequency measurements. [Input construction](../../experiments/cleaned_interface/benchmark.py), [sealed observation contract](../../results/validation/cleaned_interfaces/CI-001/manifest.json).

That is legitimate if the problem statement grants those data to every method. It cannot silently support a claim about real-frequency-only inversion. A physical transient acquisition could motivate transformed complex-frequency data, but the transformation, finite time window, source spectrum, errors and noise covariance must be demonstrated. This review found no qualification of that bridge for the maintained all-36 pipeline. FM-002's real-prefix arms still use damped localization, so they are not fully real-data-only controls.

### Full acquisition improves the experiment but changes its information content

The paired benchmark has 24 complex values at each of 19 real frequencies: **456 real-frequency measurements**. Full 24×24 acquisition has **10,944**, before counting damped catalogs. This is 24 times as many entries, not necessarily 24 times as much independent information.

FM-001's recovery of the high-contrast C is consequently an important acquisition result. It does not isolate a superior optimizer or establish universal removal of local minima. The original diagonal noise is preserved, new off-diagonal noise follows a full-matrix scale, and the aggregate discrepancy rule changes which errors control stopping. Four noisy endpoints lose unchanged-paired recovery even though all 36 pass full-data recovery. Both outcomes should appear in any presentation.

### Real measurements exist but remain a pilot

It would be inaccurate to say the repository has no experimental-data evidence. The [Fresnel pilot](../../results/fresnel/README.md) processes actual single- and twin-cylinder measurements. The single-cylinder study fixes permittivity at 3 and uses a low-order K=2 shape model; its original equivalent radius is 15.54 mm against a nominal 15 mm. The twin study assumes two circular components. This is not unrestricted topology recovery or a run of the latest modal pipeline.

The [incident-field follow-up](../../results/fresnel/source_qualification/README.md) improves the final 4 GHz residual from 24.77% to 16.49%, using incident-only calibration and withheld-angle checks. That is useful progress on the physical model. Coordinate interpretation, separation of transmitter/receiver response and the 5–8 GHz continuation remain unresolved. The original data were obtained from a pinned mirror; byte equivalence to the publisher originals was not verified. Very small numerical refinement errors beside large measured residuals are evidence that model/calibration error now matters more than extra quadrature accuracy.

## Comparison with the relevant literature

This is a targeted comparison, not a claim to have surveyed every 2026 method. The appropriate competitors are methods solving the same transmission and acquisition problem. A sound-soft obstacle method or a learned volumetric method is not automatically a fair numerical baseline.

| Primary source | What it contributes to the comparison | Implication for this project |
|---|---|---|
| [Borges and Greengard, 2015](https://epubs.siam.org/doi/10.1137/140982787) | Band-limited boundary updates, Newton iteration and recursive linearization for sound-soft obstacles | Frequency continuation and filtered normal updates are established ideas; boundary conditions differ |
| [Borges, Rachh and Greengard, 2022 preprint / 2023 journal article](https://arxiv.org/html/2210.11607v1) | Direct comparison of penetrable-boundary and volumetric inversions; contrast, data density, cavities and multiple objects | Closest conceptual benchmark; include a volume method when claiming robustness |
| [Borges, Gillman and Greengard, 2016 preprint / 2017 journal article](https://arxiv.org/abs/1608.06871) | High-resolution volume inversion with recursive linearization and fast direct forward solves | A broader scaling comparator, not a runtime number to compare with small shape-only cases |
| [Borges and Rachh, 2021](https://arxiv.org/abs/2104.13489) | Joint boundary and impedance recovery with multifrequency data | Known-material shape recovery solves a narrower problem |
| [Askham, Borges, Hoskins and Rachh, 2023](https://arxiv.org/html/2308.00559v1) | Tests cavity sensitivity to initialization/optimization and random frequency paths for sound-soft obstacles | A relevant continuation control; their benefits also have limits and need transmission adaptation |
| [Rizzuti et al., 2021](https://slim.gatech.edu/Publications/Public/Journals/Geophysics/2021/rizzuti2020dfw/rizzuti2020dfw.html) | Wavefield relaxation and variable projection in seismic inversion | Relaxation is established; this project's geometry-dependent gradient is a specific implementation responsibility |
| [Ulbrich and Ziems, 2017](https://ems.press/journals/pm/articles/14763) | Adaptive discretization within multilevel trust-region PDE optimization | Resolution control has prior art; their theorem does not certify this implementation |
| [Carpio, Pena and Rapún, arXiv deposit 2025](https://arxiv.org/html/2501.15327v1) | Topological imaging on the Fresnel data, including illumination treatment | A concrete experimental-data comparator; its inference assumptions differ from fixed-topology fitting |

The closest transmission paper generally uses **117 real frequencies from k=1 to 30**, plane-wave illumination, receivers at radius 10, and typically `Nd = Nr = floor(10k)`. It tests cavities and multiple components and reports normalized area error; its volume method is more robust in some difficult cases. [Numerical setup and results](https://arxiv.org/html/2210.11607v1#S4).

Our maintained suite uses point-source illumination, 19 real frequencies, fixed 24-pair or 24×24 acquisition, plus damped data. Its exterior nondimensional wavenumber range is approximately **0.642–6.417**, using the declared 50 mm length unit and background permittivity. Bare k or GHz values do not establish relative difficulty: compare `ke D`, `ki D`, perimeter/wavelength, cavity opening/wavelength and material ratio on the same geometry. Map contrast definitions explicitly; the implementation uses `ki²/ke²`.

The project's earlier [paper-reproduction review](../iterations/shape_frequency_continuation/iteration_03/01_results.md) remains decisive: low-contrast Figure 1 agreement is partial under an unresolved area convention, high contrast is unmatched, and stopping norm/resolution choices differ. It expressly does not establish an authoritative paper-matched baseline. A method looking better than a digitized curve under a different metric is not evidence of an advantage.

The local unrestricted frequency-only arm's 0/36 result also cannot stand in for a strong literature baseline: established approaches regularize their shape bandwidth. The [SC-051 closeout](../iterations/shape_frequency_continuation/iteration_31/01_results.md) itself limits the inference. Defeating a deliberately unrestricted or incompletely reproduced control does not defeat a tuned, faithful recursive-linearization method.

## Claims I would accept and reject as a reviewer

| Proposed claim | Decision |
|---|---|
| The maintained package has a selectable boundary-collocation-free modal solver | **Accept**, with the geometry/sampling scope stated |
| The selected modal inverse is node-free when parameter-space geometry quadrature is allowed | **Accept under the user's clarified definition**; define the coefficient-space physics distinction explicitly |
| GPU certificate evaluation preserves the six-case modal paths and saves 39.5% total wall time | **Accept**, on the recorded host, repetitions and data |
| The fastest modal/spectral combination has full all-36 qualification | **Reject**; those exact combined runs are missing |
| A fully sample-free or rigorously floating-point-verified inverse has been completed | **Reject**; implementation and receipts explicitly contradict it |
| Full acquisition recovers the selected high-contrast C under the ordinary damped nodal policy | **Accept**, as an acquisition-and-policy result |
| One pipeline has 36/36 recovery, the fastest modal timing, full relaxation and topology support | **Reject**; it combines results from different methods, data and scopes |
| Relaxed BIE improves recovery | **Reject for the tested variant**; no added recoveries in FM-002 or RB-001 |
| The method is faster or more robust than comparable published methods | **Not established**; no faithful matched external benchmark |
| The source-calibrated Fresnel pilot improves measured residuals | **Accept conditionally**, with fixed material/topology and remaining model error |
| Fourier geometry, continuation or an adjoint alone establishes novelty | **Reject**; substantial prior art exists |

My judgment is that the most credible potential contribution is the **specific modal implementation, coherent derivative/geometry treatment, and measured complete-inverse execution savings**, with a reproducible failure analysis. Establishing originality of that combination still requires a focused algorithmic novelty review. “Node free” accurately describes the intended architecture when defined, but a performance or novelty claim also needs evidence of its practical or mathematical benefit. Parameter-space quadrature is a compatible implementation choice, not an inherent defect.

## Recommended next direction

These are review recommendations, not newly approved experiments or a numerical execution plan.

1. **Qualify the current combined modal path across the frozen 36 configurations.** Compare current nodal and modal implementations on identical data, starts, policies, independent accuracy targets and final scoring. Keep failures and expose trace/window/radial-degree limits separately. This closes an existing integration gap; it does not create a new holdout.

2. **Build a faithful transmission literature baseline before another superiority claim.** Use author code or a documented reproduction, resolve contrast/normalization/stopping differences, and evaluate both algorithms on shared observations. Include a regularized boundary RLA control and a volume inverse for the cavity subset. If adaptations are needed, name them and tune them on a separate development set.

3. **Split the measurement question from the optimization question.** Run separate real-only and real-plus-damped tracks; within each, compare paired and full acquisition with consistent weighting. Give every competitor the same information in each track. For a practical damping claim, first qualify how damped observations are obtained without target access. Charge any preprocessing and account for correlated transformed noise.

4. **Freeze genuinely new evaluation families.** Include deep/narrow cavities, close boundaries, higher electrical size, offsets near acquisition limits and smooth shapes outside the current Fourier-generated truth collection. Add multiple components only for methods that actually support them. Use several independent noise draws over declared noise levels, multiple starts and selected calibration/model perturbations. Predeclare recovery and noise-aware stopping; keep existing historical gates intact.

5. **Measure time to a shared quality target.** Use repeated, order-balanced runs on the same host, synchronize GPU measurements and record load, memory, assembly/factorization/solve/geometry/audit costs. Report failure rate and capped runtime as well as successful-case medians. Work units alone are insufficient across N512 and N2048 or different RHS counts. Do not multiply speedups from separate campaigns.

6. **Prioritize measured-data modeling over extra accuracy in already converged solves.** Resolve the Fresnel coordinate convention and receiving-antenna model, freeze incident calibration without scattered-target fitting, then compare predictions at withheld angles/frequencies. Extend the portable source interface only after its input contract is clear. A repeatable experimental comparison is more valuable now than another noiseless near-machine-precision circle.

7. **Keep relaxation and ambitious theory conditional on a specific benefit.** A smaller-step-first response is a reasonable bounded follow-up because archived diagnostics found such steps, but it competes for effort with the qualification and data-contract gaps above. Pursue rigorous interval certificates if a theorem-level claim is central; otherwise retain honest numerical certificates and test difficult inconclusive cases. Do not optimize away sampling merely for terminology if that adds cost without improving accuracy, reliability or usable scope.

For publication, I would require at least three distinct pieces of evidence: a same-data modal-versus-nodal execution benchmark, a fresh same-data comparison against a credible published inverse method, and a realistic measurement/model-mismatch evaluation if practical imaging is claimed. The existing archive supplies much of the numerical-engineering foundation. It does not yet supply the second or a broadly qualified third piece.

## Suggested public description

“We implement a modular inverse solver for two-dimensional homogeneous transmission shapes, with selectable nodal Kress and node-free Fourier–Galerkin Müller physics. Node-free denotes coefficient-space physics without boundary-collocation unknowns or Cartesian boundary-kernel quadrature; parameter-space geometry quadrature is permitted. On six fixed development configurations, GPU evaluation of spectral-geometry validity bounds preserves the tested inverse trajectories while reducing the sum of median complete-path times from 247.2 to 149.6 seconds. Broader modal qualification, real-data-only comparison and performance against published methods remain open. A separate nodal full-matrix study recovers all 36 development configurations under its augmented acquisition contract.”

This wording distinguishes the established node-free architecture from the specific scope of its numerical verification.
