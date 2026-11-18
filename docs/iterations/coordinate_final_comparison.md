# Coordinate the final comparison

This document tracks four methods toward one final comparison: our BEM
inverse, GauGal, BRG and the CSI family. For each method it states the
settings, assumptions and unknowns, and it sets how subagents share the work.

The coordinator (the main session) owns this file. Subagents never edit it.
They report back, and the coordinator updates the status board and the cards.

Last updated: 18 November 2026, 02:30 UTC (CSI batch 1 done at eight
frequencies; CSI waits for the user's frequency choice; BRG run without the
curvature limit started).

## Restart notes (18 November 2026)

On 18 November the user had every chat restarted, because the contexts had
grown long. A fresh coordinator or agent starts here.

**Agents.** Both run in Herdr panes beside the coordinator (pane `w1:p1`).

| Name | Pane | Model | Reads first |
|---|---|---|---|
| `brg` | `w1:p7`, top right | Codex `gpt-6-astra`, high effort | `AGENTS.md`, this file, then "State at handoff" in [BRG 04 results](brg_adaptation/04_run_brg_on_tg002_shapes/results.md) |
| `csi` | `w1:p8`, bottom right | Codex `gpt-6.1-sol`, high effort | `AGENTS.md`, this file, then the [CSI 04 handoff note](csi_adaptation/04_run_simulated_tg002_cases/handoff.md) |

The user gave both panes full access. A pane started from scratch begins in
Codex's default sandbox, where MATLAB and git do not work. Only the user
grants full access; the coordinator does not.

**Running, detached. Do not launch a second copy.** (state at 02:30 UTC)

| Campaign | Launcher | State file |
|---|---|---|
| BRG shipped limit, completion of the 20 cases | `run_tg002_control.py --row shipped --campaign` (PID 821706) | `results/brg/tg002_completion/2026-11-18/campaign.json` |
| BRG shipped limit, aphex_twin reruns after the wrapper fix | `run_tg002_control.py --row retry --campaign` (PID 878996) | `results/brg/tg002_aphex_retry/2026-11-18/campaign.json` |
| BRG without the curvature limit (activity 05), 20 cases | `run_tg002_control.py --row control --campaign` (PID 894852) | `results/brg/tg002_no_curvature/2026-11-18/campaign.json` |
| CSI | none running. The old launcher (PID 708268) exited by itself at 02:00 UTC after batch 1. The next launch waits for the user's frequency choice | `results/csi/tg002/2026-11-17_campaign/status.json` (final) |

Each BRG folder has a `STOP` file path for a user-requested stop. None of
these runs stops on time.

**Workers.** A resource monitor (pane `w3:p1`, set up by the user about
02:10 UTC) allocates workers across both sides every 10 minutes. It set BRG
to at most four fits (`results/brg/resource_policy.json`, 02:20 UTC), with
the 14 GiB floor. The coordinator adds no resource loop of its own.

**No result-generating run is stopped because of a time limit, unless the
user says so** (user, 18 November 01:24 UTC, see "Who decides"). A stuck or
faulty run may still be stopped. History: the two launchers written before
that rule carried their own caps. The CSI one exited after batch 1 without
cutting a fit. The BRG one cut `c_shape__c0.5` at 1 h and dropped six
cases; the completion run above restored them from saved state.

The launchers belong to no chat, so closing a pane does not stop them.
Both agent chats were restarted at 00:25 UTC and picked up from their
handoff notes; each confirmed what is running before carrying on.
The CSI campaign started 17 November 23:17 UTC: four batches. A batch was
forecast at 2 h. Measured: 4.2 s per iteration at first and 5.1 s since the
BEM side shares the CPU, so about 2.4 to 2.9 h per batch.

**How the coordinator works.**
- It uses the Herdr skill: `herdr agent prompt <name> "..."` to instruct,
  and `herdr agent wait <name>` in a background shell to be woken. While an
  agent works, read its pane with `--source visible`.
- It does not type into a pane while the user has a side thread open there.
- It answers agents' questions itself (see "Who decides"), records each
  call in "Coordinator decisions", and commits this file by path.
- It leaves permission prompts and full access to the user.

**Next for the coordinator.**
1. BRG on TG-002 shapes: when the 20 cases finish, review the results and
   update the board. The data is provisional until the BEM side freezes it.
   BRG activity 05 then runs the same cases without the curvature limit
   (see the BRG card). Review both rows together.
2. CSI campaign: the user cut the simulated cases to 1, 2 and 3 GHz
   (18 November 00:55 UTC, see the CSI card). Batch 1 of the old
   eight-frequency campaign ends near 02:00 UTC and stays as a side result;
   its launcher then exits by itself and nothing resumes it. **On hold
   (user, 01:36 UTC):** no CSI fit is launched after batch 1. Review the
   batch-1 results with the user first; the user then chooses four or five
   frequencies for the remaining cases. `csi` prepares a review pack and
   keeps the launcher's frequency list as one setting.
3. Deferred: the BRG paper cases from k = 15 to 30, only after the CSI
   campaign and only if still wanted.
4. The BEM side is live since 18 November, 00:15 GMT: a second coordinator
   (pane `w2:p1`) with its own agents, working from
   [coordinate_bem_side.md](coordinate_bem_side.md). It holds the solver
   lock and may edit the BEM rows and the lock paragraph of this file, so
   re-read this file before each edit and commit it by path.
   - It takes from this side: the
     [solver handover](brg_adaptation/03_adapt_bem_to_brg_data/results.md),
     `results/brg/tg002_shapes/2026-11-17/data_request.json`, and the
     hashed CSI data files.
   - This side owes it: BRG reruns on its frozen plane-wave data, only
     where the fields differ from the provisional data.
   - The machine is shared with it. Keep the 14 GB memory guard.
5. Still waiting on the user: a deadline.
6. Open questions: MR-CSI against the paper's Figure 5; BRG's gap to the
   paper's Figure 1; U1 and U5 below.

## Status board

| Method | Investigation | Latest activity | State | Next step |
|---|---|---|---|---|
| Our BEM (default) | [evaluate_our_method](evaluate_our_method/) | [01](evaluate_our_method/01_measure_clean_and_noisy_recovery/results.md), [02](evaluate_our_method/02_run_ablations/results.md), run 17 Nov | TG-002 done. BEM side started 18 Nov: GPU table path, six BRG paper cases, CSI adapter | Status in [coordinate_bem_side.md](coordinate_bem_side.md) |
| GauGal | [evaluate_our_method](evaluate_our_method/) | [03](evaluate_our_method/03_record_untuned_gaugal_reference/results.md), run 17 Nov | TG-002 untuned reference done | Stage 2 role open (U1) |
| BRG | [brg_adaptation](brg_adaptation/) | [01 results](brg_adaptation/01_run_published_examples/results.md), [02 plan](brg_adaptation/02_rebuild_paper_examples/plan.md) | 01 done 17 Nov. [02](brg_adaptation/02_rebuild_paper_examples/results.md) done to k = 15 (six cases). [03](brg_adaptation/03_adapt_bem_to_brg_data/results.md): adapter done, 1 of 6 fits run, stopped for handover. [04](brg_adaptation/04_run_brg_on_tg002_shapes/plan.md) (BRG on TG-002 shapes): baseline half started 18 Nov 00:40 | `brg` agent (Codex, astra, high effort): 13 of 20 cases complete by 01:34 UTC (circle and star recovered; asymmetric, kite, peanut, hook and c_shape at contrast 4 not). The old queue cut `c_shape__c0.5` at its 1 h cap and dropped six cases. A completion run with no time cap started 01:35 UTC (supervisor PID 821706): that case from its saved state, then the six. Then activity 05: the same 20 without the curvature limit. Provisional data; no BEM work |
| CSI family | [csi_adaptation](csi_adaptation/) | [01 results](csi_adaptation/01_run_published_examples/results.md) | 01, [02](csi_adaptation/02_run_fresnel_dielectric_cylinder/results.md) and [03](csi_adaptation/03_prepare_simulated_tg002_cases/results.md) done 17 Nov. [04](csi_adaptation/04_run_simulated_tg002_cases/plan.md) (10 simulated cases, MF-CC-CSI) started 18 Nov 00:10 | `csi` agent (Codex, sol, high effort): let batch 1 of 04 finish (eight frequencies; circle, kite, peanut), then send a review pack. Nothing launches until the user has reviewed it and chosen the frequencies. Meanwhile it generates the other seven tables for the BEM side |

**Setup checked on 17 November 2026:** the user made the MaxwellFDFD link and
signed in to MATLAB (online licensing). `matlab -batch` runs, the C compiler
is gcc 11, and the shipped `DGradient.mexa64` loads in R2026a. MATLAB starts
with one compute thread on this CPU, so each wrapper sets and records its
thread count.

**Solver lock:** with the BEM side since 18 November 2026, 00:15 GMT
(system clock), when the user started it
([coordinate_bem_side.md](coordinate_bem_side.md)). `bem-gpu` held it for
the GPU table path and finished at 00:32: commit `3612f5195`, table mode
now runs on the GPU, default TG-002 fit byte-identical on CPU and GPU.
No agent holds it now; the BEM-side coordinator assigns it next. The BRG investigation (`brg` agent) held the lock from
17 November, 21:45, for
[activity 03](brg_adaptation/03_adapt_bem_to_brg_data/results.md); its
solver edits are finished and frozen (commits `f81719a31`, `4dde44c96`).
Only one investigation may edit `solvers/bem_inverse/` at a time.

**Split planned by the user (17 November, 23:15):** a second coordinator
with two subagents will own the BEM side. This coordinator keeps the
baseline side.

| Baseline side (this file) | BEM side (new coordinator) |
|---|---|
| Their code, patches and baseline runs | `solvers/bem_inverse/` and the solver lock |
| Converting shared data into their formats | Plane-wave data on TG-002 scenes, generated and frozen there |
| BRG and CSI results | Every BEM fit, on TG-002, BRG and CSI data |

Only the frozen data files, the scoring in `experiments/comparison/` and
the data notes cross that line. The user confirmed the data ownership with
"yes". The BEM side's plan is in
[coordinate_bem_side.md](coordinate_bem_side.md): agreed with the user on
18 November and started the same day (tables B2 and C; B1 held). It is a
temporary second file, to be merged back.
BEM-side work already done here: BRG activity 03 (adapter built and tested,
one of six fits run). It stops there.

## The final comparison

| Table | Cases | Methods | State |
|---|---|---|---|
| A. TG-002 (Stage 1) | 10 shapes at contrasts 0.5 and 4 (20 cases); contrast 13.3 for BEM only | BEM default, GauGal untuned | Done. No claims (user: claims "should wait until we see how baselines perform in stage 2") |
| B1. BRG on TG-002 shapes (main BRG table) | 10 shapes at contrasts 0.5 and 4, with BRG-style plane-wave data | BRG, BEM with known contrast; BEM with recovered contrast as an extra row | BRG: running on provisional data (activity 04); a second row without the curvature limit follows (activity 05). BEM (18 Nov 02:21 UTC): data checks pass on the 17 cases BRG has saved (the two forward copies differ by at most 1.6e-7, limit 1%). Known-contrast row done on those 17: every fit completed its schedule; area error at most 0.29% (`cog__c0.5`), under 0.1% on the other 16; 7 to 115 s per fit. Recovered-contrast row done on the same 17 (02:26 UTC): every fit completed; area error at most 0.21% (`cog__c0.5`), under 0.1% on the other 16; contrast within 2e-6 of the truth, relative; 9 to 96 s per fit. `aphex_twin__c0.5` passed its data check (8.8e-6) and is being fitted; `aphex_twin__c4` and `cog__c4` wait for BRG's data. [Results](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/results.md) |
| B2. BRG paper cases | Paper examples 1–3, six runs | BRG; BEM with known contrast up to about k = 10 | BRG: done to k = 15. BEM (GPU pass, 18 Nov): area error at k = 15 is 0.061% on `glider_033`, 0.58% on `star_full`, 0.60% on `star_limited`; `glider_10` failed (14% at k = 12); both cavity cases skipped by the user (series limit). [Results](adapt_bem_to_baseline_data/02_fit_brg_paper_cases/results.md) |
| C. CSI cases | Fresnel `dielTM_dec8f` (1 scene), plus the 10 TG-002 shapes at contrast 4 simulated in the Fresnel layout, on a reduced band the user will choose | Measured scene: MF-CC-CSI, MR-CSI, CSI. Simulated scenes: MF-CC-CSI only, for now. BEM with recovered contrast on both | CSI: measured scene done. Simulated scenes: a reduced band for both methods, because the data above 3 GHz is up to 5.9% from the exact solution. The user first said 1 to 3 GHz, then put that launch on hold: review batch 1 (eight frequencies) with the user, who then chooses four or five frequencies. BEM (18 Nov): measured scene fitted, and the default fit stalled (radius 19.0 mm against 15, permittivity 2.19 against 3, area error 67.8%); the adapter itself is cleared. Simulated scenes: an early look at 1 to 3 GHz gave 1.17%, 3.08% and 1.50% area error on circle, kite and peanut; the reported pass on all ten waits for the frequency list. [Results](adapt_bem_to_baseline_data/04_fit_csi_cases/results.md) |

Rules for every table:
- Their code and published settings are not changed. Our method is adapted to
  their cases, and the user said: "for fair comparison we should avoid changing their code and
  settings, we should instead adapt our code to their test cases."
- CSI is not run on the sealed TG-002 data. BRG was not either, until
  17 November: the user then chose to compare BRG on the TG-002 shapes as
  well ("for brg i think we should compare it on my tb 002 scenes, its more
  variety?"; then "yeah" to making it the main BRG table). BRG takes plane
  waves only, so it gets BRG-style data on those shapes, not the sealed data.
- Clean data first; noise only after the clean results are reviewed.
- Our method gets exactly the data the baseline gets, and picks its own
  frequency schedule within it.
- Our forward solver is checked on each true shape before any inversion.
- Score with set-difference area over true area, counting all components,
  plus contrast error and wall time. Raw metrics are saved per fit, so a
  changed cut-off means a recount, not a rerun.
- Report each method's native timings separately from its timings on adapted
  cases (user decision D13).

## Method cards

### Our BEM inverse: default method

- **Code:** `solvers/bem_inverse/`, `modal_muller` + `slider`, run through
  `experiments/comparison/`.
- **Unknown:** one closed curve plus one real contrast, recovered by default.
  Equal-density transmission.
- **Data:** paired point sources only (24 source–receiver pairs in TG-002),
  using real frequencies only, with no damped data.
- **Frequencies:** starts at 0.5 GHz, then adds 0.75, 1.0 and 1.25 GHz one at
  a time. Then all 19 frequencies, with shape bands 11 to 37 and an adaptive
  tail up to 95.
- **Start and stop:** centred 65 mm circle, no localization and no warm-up.
  Stops on residual, step and budget rules. On noisy runs it is also told the
  noise level, for the discrepancy rule.
- **Limits:** 13,412 work units and a nominal 120 s per fit.
- **Output:** a curve, scored directly.
- **Results so far:**
  - clean: 16/30 cases, or 16/20 at contrasts 0.5 and 4;
  - 1% noise, three draws: 16, 17 and 17 of 30;
  - contrast 13.3: no case recovered.
- **Assumptions:** the background enters only through the wavenumber, so
  vacuum or sand is a matter of k. The contrast is real and positive, and the
  object is one component.
- **Unknowns:**
  - Production code accepts no plane waves and no unpaired sources yet.
  - Untested at BRG's wavenumbers (up to 30 on objects of size about 1) and
    with full apertures of up to 300 × 300 data.
  - How to use measured Fresnel data: the per-source calibration and the
    vacuum setting.

### GauGal

- **Code:** `~/Gau-Gal`, adapter `experiments/gaugal_comparison/gaugal_arm.py`,
  family `experiments/comparison/gaugal.py`.
- **Unknown:** a susceptibility image on a Gaussian lattice, from collocation
  with FISTA and total variation. One coefficient vector covers all
  frequencies. It runs on the GPU.
- **Settings (frozen, untuned since 2 November):**
  - lattice 51, width 0.7, TV weight 0.5, step 0.05;
  - susceptibility limit 15, 80 iterations;
  - all 19 frequencies at once;
  - 400 s optimization and 600 s outer time per case.
- **Output:** an image. Its support is half the peak with the peak's sign,
  as in protocol version 1.
- **Results so far:** 0/20 on 1% noise draw 0, and 0/30 on the imported clean
  fits.
- **Timing:** about 1 s per case on its native cylinder cases at 0.4 GHz;
  median 328 s on TG-002.
- **Assumptions:** these are reference results, chosen on clean circles and
  never tuned for TG-002. It is not given the noise level.
- **Unknowns:**
  - Its role in Stage 2 (U1).
  - Whether its adapter can take plane waves or Fresnel line-source tables.
  - Why TG-002 takes so much longer than its native cases.

### BRG (Borges–Rachh–Greengard)

- **Code:** `~/neural_bem_external/inverse-obstacle-scattering2d` at
  `bda24bd`. MATLAB with Fortran MEX files.
- **Unknown:** one closed curve. The contrast is known, because the interior
  wavenumber is an input. Equal density.
- **Data:** plane waves only. Receivers are arbitrary points; each datum is a
  (receiver, direction) pair per frequency.
- **Paper settings** ([arXiv 2210.11607](https://arxiv.org/abs/2210.11607)):
  - k from 1 to 30 in steps of 0.25 (117 frequencies);
  - ⌊10k⌋ directions and ⌊10k⌋ receivers on a circle of radius 10;
  - 100 points per wavelength for the data and 70 in the solver;
  - ⌊3·max(k, k_inside)⌋ update modes;
  - the better of Gauss–Newton and steepest descent, within a roughness limit;
  - stop at 1e-5 or after 50 iterations per frequency, starting from the
    unit disk.
- **Output:** a curve, scored by set-difference area over true area, the
  paper's own measure.
- **Assumptions:** time sign e^{−iωt}, the same as ours. The unmerged
  coefficient fix does not matter at equal density.
- **Unknowns:**
  - The paper's example drivers are not public, so cases must be rebuilt from
    the text.
  - The inversion never updates the interior wavenumber per frequency. How
    the authors handled this is unknown.
  - Runtime at k = 30.
  - Whether every paper setting is reachable through the public options.

- **Found in activity 01 (17 November):**
  - The public transmission inverse does not run as shipped. Two small
    fixes are needed, both approved by the coordinator:
    [patches 03 and 04](../../external/patches/brg/README.md).
  - Patch 04 sets the interior wavenumber at every frequency to the
    driver's ratio times the exterior one. Without it the inversion keeps a
    stale value.
  - The driver's `bc.q` is a wavenumber ratio (1.5, so 2.25 squared). The
    paper states contrast as the squared ratio, interior over exterior.
  - The shipped driver uses `ceil(10k)` receivers and directions; the paper
    says floor.
  - Data layout, signs and scaling for our adapter:
    [data_handoff.md](brg_adaptation/01_run_published_examples/data_handoff.md).
  - The shipped star data example is dissipative, so it is not a paper case.

  - Result of 01: their shipped cavity example ran all 117 frequencies in
    23 minutes. Area error 57.6%; it does not resolve the cavity, as the
    paper also reports for its own cavity.
- **Decided for activity 02 (coordinator, 17 November):**
  - Six runs, not seven; the earlier count was a slip.
  - The star and paper cavity are recovered from the paper's vector figure
    files, and labelled so.
  - Points per wavelength follow the public code (exterior wavenumber).
  - Curvature limit: the shipped driver's values, checked by reproducing
    the paper's Figure 1 on the first glider case.
  - 4 h per case, all 117 frequencies.

- **Activity 02 so far (17 November):**
  - Glider, eta 0.33: 0.003% area error at k = 30; 68 minutes.
  - Its error is 2 to 8 times below the paper's Figure 1 up to k = 10. The
    curvature limit is not the cause: the driver's value and no limit give
    identical errors. The gap is unexplained and BRG is not handicapped.
  - Star and cavity recovered from the vector figures to about 6e-4 and
    2e-4 in data units.
- **Activity 02 result, six paper cases to k = 15 (17 November):**

  | Case | Area error at k = 10 | At k = 15 |
  |---|---|---|
  | Glider, eta 0.33 | 0.24% | 0.052% (0.003% at k = 30) |
  | Glider, eta 10 | 0.010% | 0.004% |
  | Star, full data | 1.7% | 0.52% |
  | Star, limited data | 1.7% | 0.81% |
  | Cavity, eta 0.9 | 134% | 134% |
  | Cavity, eta 2 | 131% | 134% |

  BRG recovers the glider and the star and fails on the cavity, as its
  paper reports. The resume to k = 30 is deferred.
- **Activity 03 result (17 November):** the adapter is built and tested
  (109 tests pass, a default TG-002 fit is bit-identical). Our forward
  agrees with BRG's data to 1.3e-6 on the glider up to k = 12. The one fit
  run, glider eta 0.33 with known contrast, took 60 s and reached 0.21%
  area error at k = 10, then refused k = 12.
- **Activity 04 (BRG on TG-002 shapes, coordinator 18 November):** the
  baseline half only runs here. Sweep: TG-002's 19 frequencies plus
  midpoints (37), which keeps the band and gives BRG steps no coarser than
  its own rule. Data: floor(10k) directions and receivers on the radius-10
  ring. Until the BEM side freezes the data, runs use BRG's own forward
  and are labelled provisional. A data request file states the layout.
- **Activity 04 so far (18 November, 00:40 UTC; 10 of 20 cases, provisional):**
  - Recovered: circle (both contrasts) and star (0.25% and 0.04% area
    error).
  - Not recovered: asymmetric (11% and 28%), kite (48% and 46%) and peanut
    (12% and 50%), at contrasts 0.5 and 4.
  - Cause, read from the saved logs: BRG's own curvature test rejects every
    update (error code 2 in `rla.update_geom`, for both step types at all
    ten filter levels). The frequency then ends after one iteration and
    the curve stays frozen. The kite at contrast 0.5 freezes at iteration 6
    of the first frequency.
  - The shipped limit allows a curvature tail ratio of 0.1 beyond band
    max(20, update modes). The true kite, star, asymmetric, cog and
    aphex_twin curves give 0.24 to 0.38 at band 20 (coordinator's copy of
    the test), so the limit excludes them at low k. The other five pass.
  - So this is BRG's behaviour under its example driver's limit, not a
    wrapper fault. The public code's default is no limit.
- **Activity 04, completion run (18 November, from 01:35 UTC, no time
  cap):** `c_shape__c0.5` continued from its saved state and finished at
  5.3%. Cross: 0.09% and 24.6%. Cog at contrast 0.5: 0.23%. With hook (58%
  and 52%) and c_shape at contrast 4 (44%), 6 of 17 finished cases are
  under 5%: circle and star at both contrasts, cross and cog at contrast
  0.5. Still to come: cog at contrast 4 (running) and aphex_twin at
  contrast 4 (running). Both aphex_twin cases first failed at start on our
  wrapper's interior-point check and were rerun after a wrapper fix; at
  contrast 0.5 the rerun finished at 80%.
- **Activity 05 (coordinator, 18 November):** the same 20 cases with the
  curvature limit removed and nothing else changed. Started 02:28 UTC
  with `kite__c0.5`, no time cap, data reused from 04 by hash. The table
  then shows both BRG rows.
- **Our BEM on BRG data (activity 03, coordinator review 17 November):**
  - Our default forward builds its incident waves from a power series that
    it refuses to use beyond about k times object radius = 17. On BRG's
    unit-size shapes that is about k = 13.
  - So our method will use BRG's data up to that k, not to 30. The table
    must show BRG at the same k as well as at k = 30.
  - Lifting the limit needs a redesign of that series. It is not part of
    activity 03 and would be proposed separately.

### CSI family (MF-CC-CSI, MR-CSI, CSI)

- **Code:** `~/neural_bem_external/CC-CSI` at `73a64e1`, with MaxwellFDFD at
  `690ca8d`. Pure MATLAB, with one prebuilt MEX file.
- **Unknown:** a complex contrast image on an FDFD grid with a 5-cell PML.
  - One real part is shared by all frequencies; the imaginary part scales
    as 1/ω.
  - Each iteration clips Re χ ≥ 0 and Im χ ≤ 0.
  - The outer 5 cells are fixed at zero.
- **Data:** line sources on a ring and receivers on a ring, as a full table
  with a mask for missing entries. Background is vacuum only, 2D TM or TE.
  The incident field is calibrated per source and frequency from the measured
  incident field.
- **Paper settings** ([arXiv 1906.10814](https://arxiv.org/abs/1906.10814)):
  - 2048 iterations;
  - cells of at most λ0 / (15·√max εr);
  - starts from back-propagation.

  Its Fresnel case is `FoamTwinDielTM` at 7–10 GHz.
- **Output:** per-frequency contrast images, scored by thresholding the image.
- **Assumptions:** time sign e^{+jωt}, opposite to ours, so conjugate when
  exchanging data.
- **Unknowns:**
  - Runtime of 2048 iterations.
  - Who generates the simulated Fresnel-layout cases (U4).
  - The threshold rule for its images (U3).
  - Whether the shipped MEX file loads in R2026a.

- **Found in activity 01 (17 November):**
  - The shipped MEX file loads in R2026a.
  - R2026a needed two compatibility patches, both in
    `external/patches/cc-csi/`: a removed plotting call, and three
    `interp2` calls with a negative factor inside MR-CSI.
  - The coordinator approved replacing those three calls with
    every-other-node sampling. The old `interp2(V,n)` queried
    `1:1/2^n:end`, so n = -1 read nodes `1:2:end`; the method is unchanged.
  - Shipped example I builds a 94 × 94 grid. Its `xs = 70` is a half-width
    in mm, not a cell count.
  - The paper case is one small cylinder inside the foam and one beside it,
    not two inside.

  - Result of 01: all three steps ran, 34 minutes in total. On the paper
    case MF-CC-CSI agrees with Figure 5 by eye (two cylinders, contrast
    near 2.5). MR-CSI gives a clean image where the paper shows a failure;
    this is unexplained and is checked first in activity 02.
  - Native time on the paper case: 948 s (MF-CC-CSI) and 840 s (MR-CSI)
    for 2048 iterations, with BRG overlapping.
  - Data table, mask, calibration and sign rules for our adapter are in
    the last section of the
    [01 results](csi_adaptation/01_run_published_examples/results.md).
- **Decided for activity 02 (coordinator, 17 November):**
  - Case `dielTM_dec8f`, all eight frequencies, 2048 iterations, all three
    methods. The driver and paper give this case no domain or cell, so:
    centre at the origin, half-widths 70 mm, 1.25 mm cells.
  - The shipped antenna radius stays; it only matters for second-opus
    cases, which table C does not use.

  - Result of 02 (measured cylinder `dielTM_dec8f`, 17 November): all
    three methods ran 2048 iterations, about 32 minutes each. Support area
    against the nominal cylinder: +4.2% (MF-CC-CSI), +1.3% (MF-MR-CSI),
    -19.9% (CSI). Mean permittivity 2.73, 3.01 and 3.28; the truth is
    3 ± 0.3. The Fresnel frame is not yet matched to their grid axes.
  - The MR-CSI difference from Figure 5 stays unexplained after a reading
    check. The interpolation patch is exact on eight test arrays.
- **Decided for the simulated cases (coordinator, 17 November):**
  - Contrast 0.5 is left out for CSI. In vacuum it is a negative
    susceptibility, which their projection forbids.
  - So table C's simulated cases are the 10 TG-002 shapes at contrast 4.
  - Grid 166 × 166 at 1.25 mm, because the shapes reach 96 mm.
  - Cost forecast: about 34 h for three methods, about 12 h for MF-CC-CSI
    alone, at 2048 iterations.
  - User, 17 November: "okay for now keep only mf-cc-csi, and run them
    three at time". So the simulated campaign is MF-CC-CSI only, three fits
    at a time, 2048 iterations with snapshots at 256, 512 and 1024.
    MR-CSI and CSI stay on the measured cylinder only, for now.
  - Result of 03 (preparation, 17 November): one simulated fit costs
    3.44 s per iteration on the 166 × 166 grid, so about 2 h per fit and
    about 8 h for the ten in batches of three. The coordinator extended the
    budget from 6 h to 9 h; the first estimate given to the user (4 to 5 h)
    was too low.
  - 2048 iterations are needed: at 1024 the support area is still 3.2%
    from its final value, and at 512 it is 4.8%.
  - The measured cylinder's nominal centre is (0, +30) mm on their grid.
    Against it the set-difference area error is 34 to 38%, caused by a
    3.6 mm centre offset; the database gives the position only as "about
    30 mm". Size and centre are reported separately for this case.
  - Budget (coordinator, 18 November 00:45 UTC): batch 1 runs at 4.2 to
    5.1 s per iteration, not 3.44, because BRG and the BEM side share the
    CPU. The forecast for all ten was near 10:00 UTC, so the limit went
    from 9 h to 12 h with a resume after batch 1. The user's cut to 1 to
    3 GHz below replaced this plan the same hour.
  - Error in the simulated data (BEM side, 18 November 00:36): on the true
    circle the simulated table differs from the exact series by 0.17, 0.13,
    0.30, 1.14, 0.82, 1.68, 2.29 and 5.91% at 1 to 8 GHz. It grows roughly
    as frequency cubed, as grid dispersion would. The generator samples the
    boundary as a staircase and averages four cells, at 0.625 mm.
  - The BEM side asked the user and fits no simulated case until the
    answer. The campaign continues meanwhile. `csi` measures the error at
    1.25, 0.625 and 0.3125 mm cells for that decision.
  - What the error means (coordinator's check, 18 November 00:50 UTC, exact
    series only, no solver): the table matches an exact circle with the
    true radius and centre and a contrast of 4.001 at 1 GHz rising to
    4.010 at 8 GHz. With that contrast the mismatch is 0.13 to 1.3%. One
    circle fitted to all eight frequencies has radius 49.98 mm, contrast
    4.009 and the centre within 0.01 mm; it leaves 0.3 to 2.7%.
  - So the 5.9% field error equals a contrast shift of at most 0.26%. The
    shape is right to 0.02 mm. `csi` reproduces this in its results.
  - **User decision, 18 November 00:55 UTC:** "id say we just supply less
    frequency range to it, you know below 4GHz such that simulated data
    are accurate there." So the simulated cases use 1, 2 and 3 GHz only,
    for CSI and for our BEM. The circle error there is 0.17, 0.13 and
    0.30%. The table files stay the same hashed eight-frequency files; the
    1 to 3 GHz rows are the data.
  - What follows (coordinator): CSI activity 05 reruns all ten shapes at
    1 to 3 GHz, with 2048 iterations, three at a time and the same 1.25 mm
    inversion grid, which meets their cell rule and keeps the image as
    fine as before. Batch 1 of the eight-frequency campaign finishes as a
    side result on circle, kite and peanut. Its resume, the 12 h limit and
    the finer-grid check are dropped.
  - Cost of the cut: 3 GHz in vacuum is a 100 mm wavelength outside and
    50 mm inside. TG-002's top frequency gives 49 mm and 24 mm. Both
    methods get the same, coarser data.
  - **On hold (user, 18 November 01:36 UTC):** "Let the current
    eight-frequency batch finish. Hold the automatic 1-3 GHz launch.
    Review those results with me before choosing four or five frequencies
    for the remaining cases." So nothing launches after batch 1. The
    frequency list is open again and the BEM side has been told.
  - Tables for the BEM side (its request, 01:30 UTC): all ten simulated
    tables are frozen under
    `results/csi/tg002/2026-11-18_low_band_data/<shape>/forward/` (commit
    `8d4c6123d`), each with all eight frequencies and a hash file. The
    three old ones are byte-identical copies. Hashes:
    [data note](csi_adaptation/05_run_simulated_tg002_cases_at_1_to_3_ghz/data_note.md).
  - **Batch 1 result (18 November 02:00 UTC; eight frequencies, 2048
    iterations, 4.74 s per iteration, 2 h 42 min per fit):**

    | Shape | Area error at half the peak | At 0.3 and 0.7 of the peak | Mean permittivity (truth 4) |
    |---|---|---|---|
    | circle | 13.7% | 22.3% and 4.7% | 3.43 |
    | kite | 16.1% | 41.0% and 44.4% | 3.25 |
    | peanut | 21.1% | 36.1% and 25.7% | 3.21 |

    The images follow the true outlines. At half the peak nearly all the
    error is excess area: the contour lies outside the true boundary. The
    scores still fall between 1024 and 2048 iterations (kite 21% to 16%).
    The launcher then exited by its own rule and nothing was launched.
    Figure: [batch 1](csi_adaptation/04_run_simulated_tg002_cases/figures/batch_1.png).
  - For the review (BEM side's early look, 1 to 3 GHz, not its reported
    pass): circle 1.17%, kite 3.08%, peanut 1.50% area error in 71 to
    178 s; the kite's last stage ended on a numerical failure.

## Who decides

On 17 November 2026 the user handed these calls to the coordinator: "you are
the coordinator, you should make judgements when they are asking for my
feedbacks. remember the big picture: to generate comparison with my bem."

- Agents send questions to the coordinator, and the coordinator decides. The
  aim of every call is the final comparison against our BEM inverse.
- The coordinator still asks the user before any branch or worktree, before
  leaving an investigation's topic, and before passing a limit the user set.
- Time limits (user, 18 November 01:18 UTC): "the time limit isnt for you
  to cutoff agent, but something as a design requirement. do not stop
  running terminal ifi didnt say so. keep it as it is now". Rephrased at
  01:24 UTC: "do not stop result-gerating terminal processes due to time
  limit unless i say otherwise. if it stucks or goes wrong you should
  still stop it. this is only about time limit". So a time figure shapes
  how a run is designed and never stops a run. A stuck or faulty run may
  still be stopped.
- Permissions: the agents started in Codex's default sandbox. The user
  switched both to full access on 17 November ("i just gave them full
  access").
- Models, in the user's words: "the heavier work might use astra high, and
  the easy work give it to sol high."
- The user started both investigations on 17 November. Their follow-up
  activities are opened by the coordinator, without a new go.

## Open decisions

- **U1.** Does GauGal run on tables B and C, untuned as in table A, or stay a
  TG-002 reference only?
- **U2.** Which investigation extends `solvers/bem_inverse/` first? The user
  said this comes "down the line in these iterations".
- **U3.** Decided by the coordinator, 17 November: keep protocol version 1
  for CSI images (half the peak, with the peak's sign; 0.3 and 0.7 kept as
  sensitivity scores). Raw arrays are saved, so a recount needs no rerun.
- **U4.** Decided by the coordinator, 17 November: the simulated CSI
  cases use their own forward, on a finer grid (0.625 mm) than the
  inversion (1.25 mm). The BEM side later checks the same hashed data files
  with our forward on each true shape.
- **U5.** Success cut-off for tables B and C: keep area error ≤5%, or report
  the raw error only, as the BRG paper does?
- **U6.** Decided by the coordinator, 17 November: BRG and CSI runs may
  overlap in activity 01, because its timings feed no table. Each agent
  records its MATLAB thread count. Timed runs for tables B and C run alone.
  Measured with both agents active (17 November, 19:24): the GPU is idle
  (0%, 0.9 of 32 GB) and neither baseline uses it; CPU load is under 1 of
  24 cores; 39 GB of memory and 38 GB of disk are free. Two MATLAB runs at
  8 threads each fit. Disk is the tightest limit.

U1–U5 are now the coordinator's calls. Each is made when an activity first
needs it, and recorded here.

## Coordinator decisions

| Date | Decision | Reason |
|---|---|---|
| 17 Nov | BRG and CSI may overlap in activity 01 (U6) | Its timings feed no table; the machine has room |
| 17 Nov | CSI: replace negative `interp2` calls with node sampling | Same numbers as the authors' MATLAB; a version fix |
| 17 Nov | CSI: later version fixes of that kind need no question | Keeps the agent moving; each is saved as a patch |
| 17 Nov | BRG: approve patches 03 and 04, start the full run | Matches the driver's own data generation; upstream branches have no fix |
| 17 Nov | BRG: draft the activity 02 plan during the 4 h run | Uses the waiting time; nothing in 02 runs yet |
| 17 Nov | Commit at most about 5 MB per run; bulk stays local and ignored | The first hour pushed 654 MB of results |
| 17 Nov | BRG 02: go, with the choices listed in the BRG card | The paper leaves them open; each choice follows the authors' code or their published figure |
| 17 Nov | CSI 02: go on the measured Fresnel cylinder, with the choices in the CSI card | It is table C's measured case; its timings cost the simulated cases |
| 17 Nov | U3: protocol version 1 threshold for CSI images | Same rule as table A; no new choice to defend |
| 17 Nov | BRG 02: stop the no-limit glider rerun at k = 10 | Both settings agree at every Figure 1 frequency; the question is answered |
| 17 Nov | BRG 03: plan approved with changes; solver lock to BRG | Exact plane-wave coefficients instead of a projection; a pair mask so CSI can reuse it; default path must reproduce; 1 h per fit; stop after one glider fit |
| 17 Nov | BRG may run two paper cases at once | The user asked how long is left; three heavy workers fit, and clean timings are re-measured later |
| 17 Nov | BRG paper cases stop at k = 15 for now and run side by side; resume to k = 30 later from saved states | The user is short of time. To k = 15 costs 10 of 65 minutes per case, and our BEM stops near k = 13 |
| 17 Nov | Do not move BRG to the GPU | This MATLAB has no GPU toolbox, and 64% of a solve is their single-threaded Fortran kernel assembly. Dense algebra is under a third, so the best gain is about 1.3 times |
| 18 Nov | CSI 04: budget extended from 6 h to 9 h, start now | The forecast is 8 h; it runs overnight, pushes after each batch, and can be stopped without loss |
| 18 Nov | BRG 04: go for the baseline half, on provisional data from BRG's forward | Cases are cheap at TG-002's frequencies; it fixes the data request for the BEM side; reruns are only needed where frozen data differs |
| 18 Nov | CSI 05: rerun all ten shapes at 1 to 3 GHz on the 1.25 mm grid; batch 1 of 04 finishes as a side result; no eight-frequency resume | Follows the user's cut to 1 to 3 GHz. The grid already meets their cell rule; a coarser one would blur CSI's image. Batch 1 was 60% done and shows CSI with its full band |
| 18 Nov | Superseded by the row above: CSI 04 limit raised from 9 h to 12 h; resume batches 2 to 4 after the launcher exits | The measured pace is 4.2 to 5.1 s per iteration with the CPU shared. The 9 h limit was the coordinator's. Settings and three-at-a-time stay |
| 18 Nov | BRG 05: rerun the 20 TG-002 cases without the curvature limit | BRG's curvature test freezes it on kite, peanut and asymmetric. No limit is the public code's default, so the table shows both rows and BRG is not handicapped |
| 18 Nov | CSI: grid check of the simulated circle data at 1.25, 0.625 and 0.3125 mm cells | The BEM side measured up to 5.9% error. The user needs its size and cause to decide |
| 17 Nov | No high-k redesign of our solver | With TG-002 shapes as the main BRG table, the k = 13 cap only limits the paper cases |
| 17 Nov | U2: the BRG investigation extends our solver first; `brg` drafts that plan (03), and the coordinator reviews it before any solver edit | Plane waves plus an unpaired table cover what CSI needs too |

**Pushed result files:** about 654 MB (561 MB CSI, 93 MB BRG) were pushed
in the first hour. The user freed disk space and said "alr should be enough
space now", so they stay and history is not rewritten. The 5 MB per run
rule stays for new runs.

## How subagents work

**Roles.** One agent per investigation:
- `brg` agent: the BRG investigation;
- `csi` agent: the CSI investigation;
- our-BEM work, when assigned.

Under D15, a stronger agent writes the code with minimal tests, then a cheaper
agent runs the commands and does the wider checks.

**Ownership.** Each agent edits only its own paths:

| Agent | Paths |
|---|---|
| `brg` | `docs/iterations/brg_adaptation/`, `experiments/baselines/brg/`, `results/brg/`, `external/patches/brg/` |
| `csi` | `docs/iterations/csi_adaptation/`, `experiments/baselines/csi/`, `results/csi/`, `external/patches/cc-csi/` |
| Solver holder | `solvers/bem_inverse/`, only while it holds the solver lock |
| Coordinator | this file, `experiments/comparison/` (frozen scoring protocol), `external/sources.json` |

**Rules.**
- Same checkout, current branch. Ask the user before any new branch or
  worktree.
- Stage only your own files, by path. The git index is shared, so commit
  with `git commit -m "..." -- <your paths>`, never a bare `git commit`.
- Commit at most about 5 MB per run: what scoring and figures need. Keep
  bulk data local and git-ignored, with its command and SHA-256.
- The agents have full access. They do not request approvals.
- Agents may debug upstream code (user: "the agent is allowed to debug").
  Every upstream change goes to `external/patches/` and into the report.
- Runner agents do not edit our solver or the scoring code. They report a
  crash instead.
- Start no activity without the coordinator's go. Activity 01 of both
  investigations has it.
- Questions go to the coordinator: stop and ask in the pane. Do not guess on
  anything that changes the physics, the data or a baseline's settings.
- `brg` only: report the interior-wavenumber finding and the proposed fix to
  the coordinator before the full 117-frequency run.
- Write `plan.md` before running and `results.md` after.
- Commit and push after each run, failed runs included.
- One MATLAB process per agent. The GPU is used only by BEM and GauGal. At
  most 3 heavy workers in total (a fit peaks near 8 GB).
- Never stop a result-generating run because of a time limit, unless the
  user says so. Launchers do not stop on time: they record an overrun,
  report it and carry on. A stuck or faulty run may be stopped; tell the
  coordinator what you saw. The memory guard works as designed.
- After each activity, report and wait for the coordinator.

**Report format.** Each agent ends an activity with this block:

```text
Activity: <investigation>/<NN_name>, <date>
Runs: <done>/<planned>; wall time <h:mm>
Result: <one line per case or step, with numbers>
Failures: <what failed, where the log is>
Upstream patches: <none | files in external/patches/...>
Changes to our code: <none | files>
New unknowns: <list>
Proposed next activity: <one line>; needs user decision: <Ux or none>
```

The coordinator copies each report into the status board and the method
cards, and moves resolved unknowns into the cards as settings.

## Sources

- Stage 1 decisions: [docs/cleanup/user_decisions.md](../cleanup/user_decisions.md),
  D12–D15.
- Grilling record for BRG and CSI, kept in the legacy workspace:
  [02_design_decisions.md](../../../Neural_SDF_BEM_AD/docs/iterations/baselines/iteration_01/02_proposals/02_design_decisions.md).
- Pinned upstream code: [external/sources.json](../../external/sources.json).
- Raw Stage 1 metrics: [results/metrics.csv](../../results/metrics.csv).
