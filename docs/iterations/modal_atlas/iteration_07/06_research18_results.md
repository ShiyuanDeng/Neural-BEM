# MA-007: answers from all 18 research policies

2026-10-13. All 18 requested configurations returned on the sealed TG-002
`hook__c13.3` scene, from its centered 65 mm start. Eight recovered. Each
returned result, including failures, was committed and pushed before the next run.

The baseline and its saved 114-cell atlas were reused. No further Phase A run,
baseline repeat, test suite, cap extension, confirmation fit, or new offline
physics calculation was performed. This report analyzes the saved run evidence.

## 1. What useful upper bounds did we actually establish?

**The batch establishes sufficient individual settings and important failures,
but does not establish the frozen plan's scientific no-gain upper bounds.**
The result depends on the path taken to the endpoint, not just its nominal caps.

| Control | Direct comparison | What this batch supports | What remains unknown |
|---|---|---|---|
| F | S0 capped at 1.0 and 1.5 GHz fails the full-catalog residual requirement; G recovers. | Keeping access to the 2.5 GHz catalog is sufficient under S0. G's last accepted updates use frequencies through 2.0 GHz; the 2.5 GHz stage checks the endpoint without another accepted move. | No S0 cap-2.0 run exists. O2 recovers with its last accepted updates at 1.5 GHz, so a universal frequency threshold cannot be inferred. Nothing above the frozen 2.5 GHz catalog was tested. |
| M | M19 fails; M37 recovers with an endpoint bitwise identical to G. | M37 is sufficient on the S0 trajectory. | G enters M95 but accepts zero moves there. Its equality with M37 therefore does not prove that exercised M95 directions add nothing. Intermediate caps and fixed-state plateaus are unmeasured. |
| K | K32, K64, and K192 all return recovered endpoints. | K32 is sufficient in its returned run; K64 is the better observed runtime choice. K32 uses 6,590 fit units versus 4,397 for K64, 49.9% more, and reaches the fitting time limit. | K below 32 was not tested as an S0 cap. Two successive exercised cap increases and local response plateaus were not measured. |
| Ku | Ku64 fails after 22 cap-binding refusals; Ku128 recovers with a bitwise-identical endpoint to G's cap192 run. | Ku128 is sufficient on this S0 trajectory. The retained accuracy checks identify the practical obstruction at Ku64. | G never requests production above 128. Its larger cap192 is therefore unexposed. O4 cannot qualify its retained base even at 192: requirements depend on geometry and trajectory. |

The individually sufficient cap values are F=2.5 GHz, M=37, K=32 or 64,
and Ku=128. Their combined reduced-cap recipe was **not run**. Do not turn
these separate comparisons into an asserted tested four-dimensional ceiling.

The registered C* selection chooses **M1: (2.5,37,192,192)**. M1 and K1 tie
at 4,397 work units; the frozen lexicographic cap rule selects M1. This is
the vector used by every O1–O8 ordering run.

## 2. What does each control do, and why?

**F chooses which measured waves constrain the outline.** Low frequencies help
find its broad shape; adding higher frequencies constrains discrepancies that
a low-frequency fit can leave invisible.

F0 and F1 fit their included real frequencies extremely well: maximum relative
residuals 5.34e-7 and 7.57e-7. Their omitted-frequency residuals are 1.580% and
0.474%, both above the 0.3% requirement. Both are worst at 2.0 GHz.

Their boundary RMS errors are only 0.00631 and 0.00398 mm, well below 1 mm.
Thus their failure is specifically the missing full-catalog field agreement,
not a visibly bad recovered outline. Geometry accuracy alone is insufficient.

**M chooses the detail of the outline change proposed at each step.** M19
cannot remove the remaining measured discrepancy: its full-catalog residual
is 3.664%, despite a 0.0467 mm boundary RMS. Releasing M37 repairs this path.

**K chooses how much detail survives in the stored outline.** It acts through
the actual projected, reparameterized update, so increasing M without enough
K can discard part of the intended motion. More storage alone creates no move.

The comparisons show both sides of this interaction. K32 can recover but needs
many more iterations. O3 holds K8 while releasing M37 and fails; O6 also keeps
K8 and proposes a nearly self-touching curve that the numerical service refuses.

Those ordering arms also change when other controls advance. Their failures
support the need to coordinate controls, but do not isolate projection as the
sole cause. No uncomputed tangent-rank or information-spectrum claim is made.

**Ku controls calculation accuracy, not the amount of measured information.**
It must be high enough for the fields, sensitivities, and finite proposed
movement to agree with their retained higher-resolution witnesses.

G increases Ku64 to 96 when a candidate's field comparison fails, then to 128
at the final M95 stage's sensitivity check. M1 avoids that second increase.
U0 cannot make the first increase and repeatedly refuses candidates at its cap.

The ordering results reveal why Ku should follow the current numerical need.
Raising it early cannot supply missing shape directions: O1 and O4 both fail.
O4 reaches a state where even Ku192 fails its retained-base accuracy comparison.

## 3. How should the four controls be combined?

**For runtime on this scene, retain gradual coordinated F/M/K release, and
raise Ku when the existing accuracy comparisons require it.** K1 is the
fastest observed successful fit return: 99.43 s, including its audits.

K1 follows S0 with storage capped at 64. Its accepted path reaches M37 and
Ku96; it enters the final full-catalog stage and stops without an M95 move.
Its nominal caps are (2.5,95,64,192), not the untested reduced combination.

M1 gives the same final coefficients as G, with a smaller M cap and 100.97 s
audited fit return. G takes 103.67 s. These are single observed timings;
the small differences do not establish a repeatable speed advantage.

For **charged work**, the frozen winner rule instead selects **O2**: release
M and K before F and Ku. It recovers in 3,511 work units, 21.5% less than G,
but takes 140.87 s to return its audited fit, 35.9% longer than G.

O2 reaches the 120 s fitting deadline with a recovered retained endpoint.
Its last accepted updates use frequencies through 1.5 GHz; entry at 2.0 GHz
adds no accepted move before the stop. This is strong evidence of path dependence.

O7's balanced ordering also recovers, in 4,274 units and 105.46 s. O1, O3,
O4, O5, O6, and O8 do not recover. Therefore an arbitrary two-controls-first
sequence cannot be substituted for the coordinated schedule.

O8's charged adaptive contests exhaust the time allowance before the real-data
bridge. Its three completed selections are HOLD, F, M; the incomplete fourth
contest retains the base. It records 709 full-catalog monitor field evaluations.

The implemented O8 gives no successful adaptive-policy result at this budget.
The recorded monitor/branch work is the relevant cost; its low work-unit total
alone does not mean that it is fast or that useful shape progress was achieved.

G's progress-based exits use 4,473 units versus G_E0's 5,293: historical rung
exits add 18.3% work for essentially the same recovered endpoint. Keep the
tested progress exits when using S0 under this experiment's conditions.

**O2 is a provisional work winner, not a confirmed replacement.** No independent
confirmation repeats were requested or run in this 18-policy batch. The practical
runtime recommendation is K1's tested schedule; repository defaults are unchanged.

## All returned configurations

Recovery requires the original full-catalog field and geometric conditions.
A numerical endpoint check passing does not alone imply recovery. Times below
separate fitting compute from fit return including audits.

| ID | Recovered | RMS mm | Max full-catalog residual % | Fit units | Fit compute s | Audited fit return s | Outcome |
|---|---|---:|---:|---:|---:|---:|---|
| G | yes | 0.000434 | 0.036530 | 4473 | 82.77 | 103.67 | REQUIRED_ACCURACY_REACHED |
| F0 | no | 0.006307 | 1.579712 | 4837 | 115.71 | 136.66 | COMPLETED_SCHEDULE |
| M0 | no | 0.046726 | 3.664445 | 4745 | 88.28 | 107.85 | COMPLETED_SCHEDULE |
| K0 | yes | 0.000211 | 0.022315 | 6590 | 120.12 | 140.50 | TRIAL_WALL_LIMIT |
| U0 | no | 0.036539 | 8.831488 | 6275 | 120.16 | 142.59 | TRIAL_WALL_LIMIT |
| F1 | no | 0.003981 | 0.474168 | 5354 | 111.85 | 133.19 | COMPLETED_SCHEDULE |
| M1 | yes | 0.000434 | 0.036530 | 4397 | 81.53 | 100.97 | REQUIRED_ACCURACY_REACHED |
| K1 | yes | 0.000434 | 0.036536 | 4397 | 80.34 | 99.43 | REQUIRED_ACCURACY_REACHED |
| U1 | yes | 0.000434 | 0.036530 | 4473 | 82.99 | 102.74 | REQUIRED_ACCURACY_REACHED |
| G_E0 | yes | 0.000433 | 0.036422 | 5293 | 97.50 | 118.61 | REQUIRED_ACCURACY_REACHED |
| O1 | no | 9.399324 | 159.978904 | 7474 | 120.07 | 138.86 | TRIAL_WALL_LIMIT |
| O2 | yes | 0.001884 | 0.214993 | 3511 | 120.09 | 140.87 | TRIAL_WALL_LIMIT |
| O3 | no | 0.139741 | 30.522553 | 6424 | 120.07 | 138.99 | TRIAL_WALL_LIMIT |
| O4 | no | 8.474925 | 191.764902 | 2949 | 90.32 | 111.72 | KU_CAP_UNRESOLVED |
| O5 | no | 9.398282 | 158.976510 | 7515 | 120.02 | 139.84 | TRIAL_WALL_LIMIT |
| O6 | no | 4.050856 | 188.139016 | 535 | 57.28 | 81.17 | NUMERICAL_FAILURE |
| O7 | yes | 0.000725 | 0.117195 | 4274 | 86.18 | 105.46 | REQUIRED_ACCURACY_REACHED |
| O8 | no | 9.318069 | 161.877047 | 2342 | 120.11 | 136.27 | TRIAL_WALL_LIMIT |

The authoritative numeric table and terminal outcome for each arm are generated
directly from its saved result in [results.md](../../../../results/validation/modal_atlas/MA-007/research18-001/results.md)
and [results.csv](../../../../results/validation/modal_atlas/MA-007/research18-001/results.csv).

## Evidence and limits

[summary.json](../../../../results/validation/modal_atlas/MA-007/research18-001/summary.json)
records result hashes, actual exposure, timing, storage, numerical refusals,
and the calculations used above. [actual_paths.json](../../../../results/validation/modal_atlas/MA-007/research18-001/actual_paths.json) records every returned stage.

The existing worker preserved full online recording and failure receipts.
Raw arrays remain on this machine, including the approved DATA-volume route;
the pushed receipts contain local paths, byte counts, and hashes, not those arrays.

Recording serialization overlaps numerical computation. Do not add its seconds
to fitting seconds. Audited fit return excludes later truth scoring, recorder
completion, receipt processing, retention, and Git push; it is not total task time.

The 18 requested fits and their three-question analysis are complete. The wider
frozen plan remains incomplete: new five-role research atlases/local probes,
conditional extensions, and independent confirmations were not performed.

Consequently no scientific NO_GAIN_BOUND, fixed-state mechanism plateau,
confirmed production winner, or benchmark-wide conclusion is asserted.
An unresolved answer does not release additional experiments under AGENTS.md.

Regenerate the numeric summary from the saved receipts only:

```bash
env PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  -m experiments.benchmark.research18_report
```
