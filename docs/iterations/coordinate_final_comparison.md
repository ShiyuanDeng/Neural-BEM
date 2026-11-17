# Coordinate the final comparison

This document tracks four methods toward one final comparison: our BEM
inverse, GauGal, BRG and the CSI family. For each method it states the
settings, assumptions and unknowns, and it sets how subagents share the work.

The coordinator (the main session) owns this file. Subagents never edit it.
They report back, and the coordinator updates the status board and the cards.

Last updated: 17 November 2026, 20:35 (BRG 02 and CSI 02 running).

## Status board

| Method | Investigation | Latest activity | State | Next step |
|---|---|---|---|---|
| Our BEM (default) | [evaluate_our_method](evaluate_our_method/) | [01](evaluate_our_method/01_measure_clean_and_noisy_recovery/results.md), [02](evaluate_our_method/02_run_ablations/results.md), run 17 Nov | TG-002 done | Extend for BRG and CSI data, later inside those investigations |
| GauGal | [evaluate_our_method](evaluate_our_method/) | [03](evaluate_our_method/03_record_untuned_gaugal_reference/results.md), run 17 Nov | TG-002 untuned reference done | Stage 2 role open (U1) |
| BRG | [brg_adaptation](brg_adaptation/) | [01 results](brg_adaptation/01_run_published_examples/results.md), [02 plan](brg_adaptation/02_rebuild_paper_examples/plan.md) | 01 done 17 Nov. 02 (six paper cases) started 17 Nov 20:20 | `brg` agent (Codex, astra, high effort): run the six cases; draft the BEM adaptation plan (03) meanwhile |
| CSI family | [csi_adaptation](csi_adaptation/) | [01 results](csi_adaptation/01_run_published_examples/results.md) | 01 done 17 Nov. 02 (measured Fresnel cylinder, all three methods) started 17 Nov 20:35 | `csi` agent (Codex, sol, high effort): run `dielTM_dec8f`, preview its score, cost the simulated cases |

**Setup checked on 17 November 2026:** the user made the MaxwellFDFD link and
signed in to MATLAB (online licensing). `matlab -batch` runs, the C compiler
is gcc 11, and the shipped `DGradient.mexa64` loads in R2026a. MATLAB starts
with one compute thread on this CPU, so each wrapper sets and records its
thread count.

**Solver lock:** `solvers/bem_inverse/` is free. Only one investigation may
edit it at a time. The coordinator records the holder here.

## The final comparison

| Table | Cases | Methods | State |
|---|---|---|---|
| A. TG-002 (Stage 1) | 10 shapes at contrasts 0.5 and 4 (20 cases); contrast 13.3 for BEM only | BEM default, GauGal untuned | Done. No claims (user: claims "should wait until we see how baselines perform in stage 2") |
| B. BRG cases | Paper examples 1–3, seven runs | BRG, BEM with known contrast | Not started |
| C. CSI cases | Fresnel `dielTM_dec8f`, plus TG-002 shapes simulated in the Fresnel layout | MF-CC-CSI, MR-CSI, CSI, BEM with recovered contrast | Not started |

Rules for every table:
- Their code and published settings are not changed. Our method is adapted to
  their cases, and the user said: "for fair comparison we should avoid changing their code and
  settings, we should instead adapt our code to their test cases."
- BRG and CSI are not run on TG-002.
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

## Who decides

On 17 November 2026 the user handed these calls to the coordinator: "you are
the coordinator, you should make judgements when they are asking for my
feedbacks. remember the big picture: to generate comparison with my bem."

- Agents send questions to the coordinator, and the coordinator decides. The
  aim of every call is the final comparison against our BEM inverse.
- The coordinator still asks the user before any branch or worktree, before
  leaving an investigation's topic, and before passing a limit the user set.
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
- **U4.** Simulated CSI cases: generated with their FDFD forward, our BEM
  forward, or both, cross-checked?
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
| 17 Nov | U2: the BRG investigation extends our solver first; `brg` drafts that plan (03), and the coordinator reviews it before any solver edit | Plane waves plus an unpaired table cover what CSI needs too |

**Open with the user:** about 654 MB of result files are already pushed
(561 MB CSI, 93 MB BRG). Removing them needs a history rewrite, so it waits
for the user's word.

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
- Stop after each activity and report.

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
