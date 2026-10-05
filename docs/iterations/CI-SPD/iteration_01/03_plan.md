# ON 002 Matched GauGal comparison and conditional hybrid

Prepared 2026-10-05. Approval status: **APPROVED by direct user launch**.
Execution status: **ADAPTER QUALIFICATION IN PROGRESS**. Implementation owner and execution reviewer:
ON-002 agent. This is an alternative eight-hour campaign to ON-001.

## Launch receipt

Actual user instruction: `Go ON-002 using docs/iterations/OVERNIGHT_AGENT_TRACKS.md.`
Started **2026-10-05 01:39:26 UTC**; global deadline **2026-10-05 09:39:26 UTC**;
adapter deadline **2026-10-05 03:39:26 UTC**; stop new variants **05:39:26 UTC**.
The direct launch supersedes the guide's earlier deferred status for ON-002.
Existing branch: `feature/shape-frequency-continuation`; no branch/worktree creation.
B is unchanged `modal_muller` + `certified_spectral`, localization none, pinned
at launch HEAD `6f2c1408f67365d765877bc7c733c8e163bbb2c1`, independent of
unfinished ON-001 changes. Ordinary source archive: ON-002/baseline_sources.tar.gz.
ON-002 owns only `on002*` benchmark modules/tests, its plan, result directory and
CI-SPD iteration_02 closeout. Other agents' active and pre-existing changes
are preserved. Coordination status: `/tmp/neural-sdf-bem-ad-coordination/on002.md`.
Use compute/source/Git locks and acquisition order from the guide.

## Goal

Establish a direct speed/recovery comparison on TG-002 and, if useful, combine
GauGal's volume evolution with the maintained boundary inverse. The goal is
same-problem parity or a better combined pipeline. The previous three-cylinder
pilot remains historical evidence; this plan launches no new legacy scenes.

The [seven-idea integration review](../../cleaned_interfaces/iteration_30/02_proposals/02_gaugal_restructuring_integration.md)
adds reach-informed/Gaussian updates to ON-001 and a separate
[ON-003 Ewald operator plan](04_ON003_ewald_plan.md). Those alternatives do not
expand this campaign's budget or authorize new operator or IBIM work here.

Approve **ON-002** to cover the adapter, specified repairs, comparison and
conditional hybrid below. Approval does not cover ON-001, ON-003, a new branch or a
worktree. Reuse the existing checkout; keep the external GauGal source pinned
and read-only. Put adaptation/orchestration in this repository rather than
silently modifying the released baseline.

## Comparison contract

TG-002's same 30 cases, same 24 paired source/receiver channels, same real and
damped catalogs, known material ratio, centred 65 mm circle and no grid search.
Use no regenerated observations or truth-dependent support box. The physical
domain comes from `Problem`; the frozen acquisition defines all kernel and
source/receiver factors.

**B** is the current modal/certified pipeline, or the already qualified single
ON-001 recipe if that experiment completed before this one begins. Freeze the
choice at launch and retain the unchanged current recipe as a documented
reference. This plan cannot run an unfinished ON-001 method implicitly.

**G** is a clearly named TG-002 adaptation of GauGal. Both B and G receive the
known contrast. Parameterize volume contrast as
`chi(x)=(material_ratio-1)*occupancy(x)`, occupancy in [0,1]. This accommodates
TG-002's sub-background material ratio 0.5. Initialize occupancy from exactly
the prescribed circle, using deterministic cell integration/smoothing. Evolve
one occupancy across all active frequencies; apply the same continuation
catalog sequence initially. Keep paired readout throughout.

This is not the released unknown-material, single-frequency cylinder setup.
Report the adaptation prominently. A future unknown-material comparison is
outside this contract.

## Adapter and first screen

Use the local pinned GauGal source under `/home/drdeng/Gau-Gal` for its separable
Gaussian projection, FFT propagation, batched field/adjoint solve and TV
update machinery. Record its actual HEAD, dependency version and source hashes.
Build operators for the TG physical units, Green-function sign, complex k and
source/receiver normalization. Do not reuse SingleTX archive operators.

Start at pixel grids 128 and 256 on the fixed Problem domain. Use 112 and 224
Gaussian centres per axis respectively, uniformly spanning that domain;
Gaussian standard deviation is 0.8 times centre spacing on each axis.
Use 512 only if 256 fails the refinement comparison and resources allow the
one declared escalation, using 448 centres per axis. Use the separable rendered
occupancy on the pixel grid for the fixed 0.5 contour. Apply
`chi_i=(contrast-1)*b_i` coefficientwise and the same chain-rule factor to the
gradient; a nonnegative chi clamp is incorrect for c0.5.

The initial adapted algorithm uses the same equal-frequency normalized data
loss as B, `sum_f ||prediction_f-data_f||^2/||data_f||^2/(2*F)` on each active
catalog. Use bounded occupancy TV with `TV(b)=sum sqrt(Dx(b)^2+Dy(b)^2)/(n-1)`
on the n by n coefficient grid, one-sided zero differences at its boundary.
Set its normalized-objective weight to `1e-4` during the damped prefix and
linearly decay it to zero over the first 20 full-real iterations; retain zero
thereafter. Cap each TV proximal solve at 50 iterations and relative iterate
change `1e-4`. Record achieved tolerance. Use FISTA momentum damping 0.5 and
reset momentum at catalog changes or failed descent.

Calibrate a stage's initial scalar step from the occupancy gradient at stage
entry: `alpha=0.1/max(||g||_infinity,1e-12)`. Reuse it within that stage, with
at most six halvings for actual composite-objective descent; reset momentum
and retry once before reporting exhaustion. This is a specified normalized
adaptation, not the cylinder implementation's raw-gradient step. Use at most
20 accepted outer iterations per stage and 240 total, subject to the case
wall cap. Full-real maximum residual at most 0.003 triggers contour conversion
and the common audit; failed conversion/audit may continue within the budget.

Use batched BiCGSTAB with Jacobi preconditioning, true relative residual target
`1e-6`, and a 200-iteration cap per system. Recompute the true residual before
using a field or adjoint for an update. Nonconverged systems refuse that update.
One inversion-phase repair may raise the cap to 400 and halve the calibrated
outer step globally. All additional iterations are charged. Fix precision at
complex64/float32 for the initial G arm; a failed refinement/derivative check
may use complex128/float64 as its one adapter repair, with the resulting cost
reported. Repeated precision changes are outside the plan.

Before fitting, qualify the prescribed circle for all three contrasts on the
lowest and highest active frequencies of each catalog. Compare fields with
independent BEM/Mie evaluation, check paired indexing, check the adjoint and
finite-difference occupancy derivative, and report physical/grid discrepancy
separately from iterative-solve residual. Initial field agreement target is
1e-3 relative per tested frequency, tightening the iterative tolerance to
1e-6 if needed. This adapter screen qualifies a first inversion attempt; final
benchmark success still requires the full original gates.

Adapter implementation plus these checks has a hard 120-minute cap. The one
repair may correct units/sign/indexing, increase the declared grid or use the
declared higher precision. There is one repair in the adapter phase and one
in the inversion-screen phase. A grid already raised to 512 exhausts all grid
escalations; a later contour failure cannot introduce a new grid. If it still
fails, close the comparison as adapter-incomplete
and preserve evidence. Do not publish a timing ratio for different physics.

First inversion screen: circle at all three contrasts, kite0.5, star13.3,
c_shape13.3, hook13.3 and aphex_twin13.3. Run B and G from their matched centred
objects, one case worker, identical hardware and output timing boundaries.

## Output and performance definitions

Always save G's native occupancy image and its native-data residual. For common
boundary scoring, extract the occupancy=0.5 contour using a fixed contouring
algorithm. Require one closed component; retain/report extra components
instead of selecting a component by truth. Project the contour to the declared
Fourier storage band and independently recompute fields and the standard
geometry scores. Extraction/projection/BEM audit time counts in G's comparable
time to a qualified boundary output.

Report the native image result and common boundary result separately. A good
volume residual does not establish a good extracted boundary. Known-material
occupancy is a fitting parameterization, not permission to threshold until a
desired score is reached. The 0.5 threshold is fixed for every case.

Timing starts with observations already in memory and includes method-specific
operator construction, fitting, contour conversion, audits and required output.
Also report observation loading, cold initialization and warm repeated time
separately. Never compare a warm optimization-only number to an audited total.
Charge all frequency solves, TV work, warm starts, failed solves and retries.

**BEM parity target:** B retains its declared reference recovery set and its
recovery set contains G's; median paired B/G total-time ratio at most 1.25 on
common successes and 90th percentile at most 2. At least 26/30 must qualify.
**Hybrid target:** H retains the union of B and G recovery sets and either
adds two recoveries beyond B, or is at least 2x faster than the faster
constituent on common successes. No recovery loss means set inclusion,
not merely the same count. Show every failure and total suite time beside
these conditional timing statistics.

## Decisions after the first screen

| Screen result | Next stage |
|---|---|
| B already matches/exceeds G quality and its median total time is within 1.25x | Freeze both; run all 30 and confirm timings; close parity if it holds |
| G is at least 2x faster with comparable recovery | Release the hybrid below; retain G as the serious baseline |
| G recovers a B failure but is slower | Release hybrid with a shorter volume phase |
| G has low native residual but contour fails common audit | One repair: the declared finer grid, keeping threshold 0.5; otherwise close sharp-boundary parity |
| G fails mainly at high contrast because inner solves do not converge | The one inversion-phase repair raises the iteration cap to 400 and halves the calibrated outer step; require true residual qualification and rerun the screen once |
| Both methods pass but speed gap is below 2x | Complete direct comparison; skip hybrid unless it can add recovery |
| G loses controls and the allowed repair fails | Close G/hybrid for this contract; report B's comparative advantage |

The step-size repair halves the calibrated outer step once globally. It is not
a per-case search. Grid choices are determined by numerical qualification,
not post-run shape score. High-contrast failures stay in the 30-case table.

## Conditional volume to boundary hybrid

**H** begins with exactly G's centred occupancy. Its short volume schedule has
four outer iterations on each of five objectives: the 0.25 GHz damped warmup
and the four growing damped prefixes. Use at most 20 outer iterations or five
seconds of volume fitting, whichever comes first; record the catalog reached
if the time limit interrupts the schedule. Extract the fixed 0.5 contour and
project it to K=192, without a low-band crop. If it is a valid single curve and
passes the maintained numerical field/derivative audit, enter BEM at
`release_M11` with all 19 real frequencies, M=11 and K=192, followed by its
declared remaining release/fixed/frontier sequence. This audit checks numerical
accuracy and validity, not whether the data are already fitted. Do not rerun
the low-band warmup that could erase the transferred shape.

If no qualified contour exists, continue the same volume run to 40 total
iterations or ten total seconds once, cycling the same five volume objectives
for four more iterations each. If it still cannot hand off, return a
failed hybrid result; do not start BEM from a separately selected circle or
choose between candidate contours. All volume and conversion work is charged.
Continue the declared BEM suffix with the same remaining total budget. Truth
never selects handoff timing. Its eventual prescribed cleanup is retained and
reported, distinct from an accidental low-band crop during transfer.

Screen H on the same eight cases. If it retains constituent successes and
adds recovery or saves at least 20% audited time versus the better constituent,
freeze it for all 30. Otherwise close H and finish B versus G. If H succeeds
on all 30, confirm it and close the experiment; do not begin a new material or
topology study in the remaining night.

## Time and implementation budget

Eight-hour global ceiling, including reporting. Allocate at most 120 minutes
to the adapter, 60 to the first B/G screen and allowed repair, 50 to the hybrid
if released, 200 to complete comparison and confirmation, and 50 to regression
checks, results, commit and verified push. Unused time may fund declared later
stages. Stop starting new variants after hour four.

Every case has a complete 120-second ceiling including build, initial audit,
fitting, conversion, endpoint audit and output, reserving 30 seconds for common
qualification/output. Fitting also has a 90-second upper bound; build and
initial checks reduce the available fit time. The complete three-arm 30-case
nominal cap allocation is 180 minutes; if H closes, complete only B/G. Actual
between-call deadline overshoots remain charged to the global ceiling. Use the
remaining allowance for two repeated timing runs on circle4, kite0.5 and
star13.3 where both qualify; launch a repeat only if its whole cap fits the
remaining budget. No concurrent benchmark jobs or hidden GPU warm-up.
Reference diagnostics and adapter costs are reported in the night total.

Campaign code belongs in `experiments/benchmark/`; any reusable BEM changes
belong in `solvers/bem_inverse/`. Keep a thin GauGal adapter with an explicit
dependency boundary; the maintained BEM package must not import the external
repository. Reuse existing scoring and result formats. Validate circle
physics, paired masks, signed material chain rule, complex-frequency fields,
shared multifrequency gradient and contour conversion before fitting.

## Completion

After each new experiment batch, validate then commit/push its code,
documentation and complete or failed evidence to the configured remote;
verify remote HEAD and working-tree status. Never edit a source snapshot while
its batch is measured. Store artifacts under
`results/validation/cleaned_interfaces/ON-002/` and open the next CI-SPD
iteration with the closeout.

The morning deliverables are a 30-case boundary/occupancy gallery, matched
quality and total-time table, accurate labels for released versus adapted
GauGal, and a decision: parity established, hybrid retained, GauGal retained
as faster baseline, BEM retained as stronger baseline, or adapter/experiment
incomplete. A winner ends this contract. Additional physics, noise,
unknown-material fitting and a new experiment ID remain future work.
