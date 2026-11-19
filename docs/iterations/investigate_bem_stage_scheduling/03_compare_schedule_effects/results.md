# Do missing warm-up and early stops explain the BEM failures?

19 November 2026, overnight. Coordinator: Claude, Herdr pane `w4:p1`. Two questions from the user: why BEM misses 14 of the 30 clean TG-002 cases, and why it does poorly on the measured Fresnel cylinder. The user's suspects: "schedules, for examples missing warming up, early stops". This note joins the two worker reports and adds no fit. [Plan](plan.md) · [Clean TG-002 report](../02_compare_clean_failures_and_passes/results.md) · [Measured cylinder report](../../adapt_bem_to_baseline_data/11_test_measured_cylinder_schedule/results.md)

## Answer

**Missing warm-up: yes, for part of each failure.** On clean TG-002 a band-1 fit at the lowest frequency (0.25 GHz) before the unchanged schedule raises recovery from 16/30 to 20/30 and loses no pass. The same change on the first 1% noise draw gives the same 16/30 to 20/30. On the measured cylinder a warm-up at the lowest frequency alone makes things worse; a warm-up that settles the circle on growing frequency sets recovers the cylinder.

**Early stops: yes on the measured cylinder, in a specific form; not shown on TG-002.** The measured fit did not run out of steps or time. Its outline pinched to a 41 nm neck after stage three, every later move was a genuine crossing and was refused, and the fit ended with 894 of 13,412 work units used. On TG-002, ten times more steps in an early stage, a five times longer warm-up and a five times longer wall each recovered nothing.

**What neither suspect explains.** Nine of the ten contrast-13.3 cases still miss with the warm-up. Their lowest-frequency fit lands at the wrong size and material, on either side of the background, and no schedule change tested here moves them. `c_shape__c4` misses because the first shape stage is too narrow to keep its opening. Widening the early stages recovers it and loses two other cases.

| Case group | Count | Cause, as far as the evidence goes | How it is known |
|---|---:|---|---|
| `cog__c0.5`, `kite__c4`, `aphex_twin__c4`, `circle__c13.3` | 4 | No band-1 stage at the lowest frequency | Matched test, crosses 5%; 30-case control; repeated on a noise draw |
| `c_shape__c4` | 1 | First shape stage at band 3 closes the opening | Earlier matched test; tonight, ladder bands two wider recover it (44.0% to 0.00%) |
| `kite__c13.3` | 1 | Weak contrast estimate on the wrong side of the background | Matched test: mirrored start recovers it |
| Eight others at 13.3 | 8 | Lowest-frequency fit ends at the wrong size and material | Observation and failed remedies; cause not isolated |
| Measured cylinder | 1 | Shape detail released on low, noisy frequencies; outline pinches and freezes | Trial replay; loss maps; six matched fits |

## Clean TG-002

All fits use the sealed real data, one centred 65 mm start, the weak contrast estimate, recovered contrast, modal Müller, slider, no localization, 13,412 work units and the 120 s nominal wall, one at a time on the GPU. Recovery is area error of 5% or less.

| Schedule | 0.5 | 4 | 13.3 | All | Gained and lost |
|---|---:|---:|---:|---:|---|
| Default (saved, 17 November) | 9/10 | 7/10 | 0/10 | 16/30 | |
| + band-1 warm-up at 0.25 GHz | 10/10 | 9/10 | 1/10 | 20/30 | against the default: four gained, none lost |
| The same on 1% noise, draw 0 (saved default 16/30) | 10/10 | 9/10 | 1/10 | 20/30 | against the default: four gained, none lost |
| Warm-up, then band 1 on each ladder set and the whole catalog, then the default schedule | 10/10 | 7/10 | 1/10 | 18/30 | against the warm-up row: none gained, two lost |
| The same band-1 stages, then the full-catalog stages only (the measured cylinder's best schedule) | 3/10 | 2/10 | 1/10 | 6/30 | against the warm-up row: none gained, 14 lost |
| Warm-up, then the default schedule with its four ladder bands two wider (5, 7, 9, 11) | 9/10 | 9/10 | 1/10 | 19/30 | against the warm-up row: one gained, two lost |

- **It is the lowest frequency that matters.** The default ladder starts at 0.5 GHz and never fits 0.25 GHz alone. Moving the same band-1 stage to 0.5 GHz loses three of the four rescues (`circle__c13.3` 149%, `kite__c4` 936%, `aphex_twin__c4` 571%); only `cog__c0.5` keeps its recovery.
- **What the warm-up does.** Kite and Aphex Twin are the two smallest targets: the 65 mm start has 4.6 and 5.9 times their area. Eleven of the 14 misses are already too large and too weak after the first default stage. The circle at 13.3 moves 80 mm off centre in its first default stage; with the warm-up it ends that stage within 0.3 mm in radius and 1.3% in contrast of the truth. Coordinator's reading, not a tested claim: at band 3 the first stage deforms the oversized circle before it has shrunk and moved.
- **Early stops.** `asymmetric__c13.3` with its capped stage raised from 22 to 220 steps: 187% (was 186%). `c_shape__c13.3` with a 240 s wall: 85% (was 86%). A 220-step warm-up sends star and C-shape at 13.3 to contrasts in the thousands. A 600 s wall changes none of three cases.
- **More circle stages do not help TG-002.** Band-1 stages on each ladder set and on the whole catalog, before the unchanged default schedule, lose `aphex_twin__c4` (0.22% to 51%, ended on the wall) and `peanut__c4` (0.01% to 401%) and gain nothing. For peanut the 0.5 GHz circle stage itself takes the area error from 52% to 295%, where the default shape stage takes it to 10%. Dropping the low-frequency shape ladder as well, which is what recovered the measured cylinder, loses 14 of the warm-up row's 20 recoveries.
- **Wider early bands trade one case for two.** With the ladder bands two wider, `c_shape__c4` recovers (44.0% to 0.00%), and both Aphex Twin recoveries are lost by a small margin (0.64% to 8.9% at 0.5, 0.22% to 9.1% at 4). The C-shape gain shows at the first ladder stage (15% against 54% area error); the Aphex Twin losses show only from the last ladder stage on, and the 0.5 case ended on the 120 s wall with two scheduled stages left. The other 18 recoveries are kept, the worst at 0.24%.
- **Contrast 13.3.** For six cases the weak estimate starts below the background (0.485, or clipped at 0.05) and the warm-up drives the contrast to zero. Trying the mirrored start as well and keeping the lower warm-up loss recovers kite (0.09%); for the other five the mirrored warm-up stalls at a worse loss, so the rule keeps the wrong side. A truth-free search over exact disks at 0.25 GHz lands close for four cases; started from it, kite recovers and cog, star and cross improve to 31 to 43% and still miss.
- **Trial refusals on TG-002.** Two of 80 miss stages and none of 170 pass stages refused every trial before any loss was computed. The saved TG-002 fits do not record refusal reasons, so the measured cylinder's failure mode cannot be counted there.

## Measured cylinder

One target, `dielTM_dec8f`, 1 to 8 GHz. Nominal: radius 15 mm, centre (0, 30) mm, permittivity 3 ± 0.3. Area error is against the nominal disk; the second number moves that disk to the fitted centre, because the nominal position is itself uncertain by about 4 mm.

| Fit | Area error | With the disk at the fitted centre | Radius mm | Permittivity | Loss |
|---|---:|---:|---:|---:|---:|
| Saved default | 67.9% | 61.5% | 19.05 | 2.19 | 0.0840 |
| First stage cap 22 to 220 | 46.1% | 35.2% | 12.79 | 3.79 | 0.0429 |
| Band-1 warm-up at 1 GHz only | 95.1% | 95.1% | 3.34 | 32.1 | 0.2066 |
| **Band 1 on 1; 1–2; 1–3; 1–4; 1–8 GHz, then the full-catalog stages** | **36.6%** | **3.7%** | 15.28 | 3.05 | 0.0375 |
| The same band-1 stages, then the whole default schedule | 60.7% | 57.3% | 10.34 | 4.76 | 0.0772 |
| Bands capped at the measured frontier | 87.4% | 86.5% | 5.51 | 13.7 | 0.1361 |
| Best exact circle (diagnostic, not a fit of ours) | 36.6% | 3.6% | 15.27 | 3.05 | 0.0375 |
| MF-CC-CSI / MF-MR-CSI / classical CSI (saved) | 35.1% / 34.2% / 38.5% | not computed | 15.31 / 15.09 / 13.43 | 2.73 / 3.01 / 3.28 | |

- **Why the saved fit failed.** Its first stage fits 1 GHz alone at band 3 and hits its 22-step cap. At 1 GHz a large weak circle and a small strong one fit almost equally: along that valley the loss changes by 3% while the radius changes sixfold. The next two stages add shape detail on 1 to 3 GHz, where the data are noisiest, and the outline grows lobes until two sides are 41 nm apart. From there every trial crosses itself. The end point lies on a slope towards the best circle, not in a separate minimum.
- **What recovers it.** Settle place, size and material at band 1 while frequencies are added, up to the whole catalog, and release shape detail only there. The fit then reaches the best circle and stays within 0.01 mm and 0.001 in permittivity through all six shape stages. On the nominal score it is 1.9 points better than classical CSI and 1.5 and 2.4 points behind the two multi-frequency CSI methods; the saved fit was 29 to 34 points behind all three.
- **What does not.** The lowest frequency alone cannot anchor the fit (permittivity 32). Returning to the low-frequency shape ladder after the circle is settled undoes it within one stage. Capping each band at the solver's measured frontier fails too: on a small, strong outline the 1% rule lets bands 3 and then 10 through.

## What this means for the default

These are decisions for the user; the evidence for each is above.

1. **Add the band-1 warm-up at the lowest frequency to the TG-002 default.** Four cases gained on clean data and four on a noise draw, none lost in 60 fits.
2. **The measured-data schedule and the TG-002 schedule now differ after the warm-up.** TG-002 shapes need the low-frequency shape ladder; the measured cylinder is destroyed by it. No single rule tested tonight serves both. The measured cylinder's best schedule recovers 6/30 on clean TG-002, against 20/30 for the warm-up alone; the TG-002 schedule after the same circle stages scores 60.7% on the cylinder, against 36.6%.
3. **Contrast 13.3 needs a different start, not a different schedule.** One of ten recovers with the warm-up, two with the mirrored start. Both remedies that helped are forms of trying more than one start, which the benchmark rule (one centred start, no grid search) excludes.
4. **`c_shape__c4`.** Ladder bands two wider (5, 7, 9, 11 for 3, 5, 7, 9) recover it and lose both Aphex Twin recoveries, so the total falls from 20/30 to 19/30. A fixed widening is not ready for the default. The Aphex Twin fits lead through the early ladder with the wider bands and fall behind at the last ladder stage or the first full-catalog stage; why is not tested.

## Limits

- One measured target, and its reference position is nominal. The 3.7% figure uses a centre fitted to the same data and is not comparable with the CSI scores, which use the nominal centre.
- The noise check is one draw of three.
- The cause of eight contrast-13.3 misses is an observation (where the lowest-frequency fit ends), not a matched result. Complex-frequency data, which the older method used for dense targets, was outside this investigation: the default is real data only.
- The 120 s wall is nominal and depends on machine load; wall-limited fits ran alone. Two self-tests shared the GPU briefly with a running fit and are noted in the plans.
- The individual gains and losses in the last three table rows are single runs per case. Where each loss starts is read from the stage records in the TG-002 report and was not tested further.
- The wall is checked when a trial returns. One fit (`c_shape__c13.3`, wider ladder) ran 586 s under the 120 s wall because its first full-catalog trial took 520 s.
- The frontier-cap run on all 30 TG-002 cases was withdrawn once the rule failed on the cylinder. One measured control was stopped by the coordinator after its completed stages matched the reference exactly.

## How this was done

Two Codex agents in Herdr panes, sandboxed, with no GPU: `tg-misses` (GPT-6.2-Astra, high effort) for mechanisms and the TG-002 report, `cylinder` (GPT-6.1-Sol, medium effort) for loss maps, frontier measurements and the measured report. The coordinator wrote the round-two to round-five drivers, ran every GPU fit from detached launchers, and made every commit. One solver change was approved by the coordinator: the runner's frontier operation may name the observation it measures at; without that key it behaves as before (commit `f1f5c79d6`, reviewed by `tg-misses`).

Fits run tonight for these two questions: 178 on TG-002 (148 clean in twelve arms, 30 on the noise draw) and six on the measured cylinder, one of them the stopped control. All 178 TG-002 fits wrote a result; fits that ended in a numerical failure or at the wall are scored as they ended. Self-tests are listed in the plans.

Evidence: [TG-002 fits and tables](../../../../results/bem/stage_scheduling/2026-11-19/) · [measured fits](../../../../results/bem/baseline_data/measured_schedule/2026-11-19/) · [trial refusals](../02_compare_clean_failures_and_passes/trial_refusals.md) · [stage frontiers](../02_compare_clean_failures_and_passes/stage_frontiers.md) · [TG-002 circle loss maps](../02_compare_clean_failures_and_passes/circle_loss_maps.md) · [coordination record](../../coordinate_bem_side.md#failure-investigation-opened-19-november-0221-utc)
