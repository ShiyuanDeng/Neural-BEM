# Brief for `cylinder` (GPT-6.1-Sol, medium), pane `w4:p3`

From the coordinator, Claude in pane `w4:p1`. 19 November 2026, 02:30 UTC.

## The question

The user wants to know overnight why our BEM inverse does poorly on the measured Fresnel cylinder `dielTM_dec8f` (and, in the other pane, why it misses 14 of 30 clean TG-002 cases). The user's suspects, in their words: "my biggest suspects of these bem failures are about schedules, for examples missing warming up, early stops". Your part is the measured cylinder: the loss maps, the comparison of the matched fits, and the results note.

Read first:

1. `AGENTS.md` (terminal answer rules, experiment rules).
2. [Your activity plan](../../adapt_bem_to_baseline_data/11_test_measured_cylinder_schedule/plan.md), including the coordinator's changes at the end.
3. The saved fit and circle comparison: `results/bem/baseline_data/csi_adapter/2026-11-18/first_fit/dielTM_dec8f/cuda/attempt_01/` and `results/bem/baseline_data/csi_adapter/2026-11-18/cylinder_info/cylinder_info.json`.
4. `experiments/bem_on_baseline_data/csi_cylinder_info.py` (exact circle series against the measured rows) and `csi_measured_schedule.py`.

## How we work tonight

- Your sandbox has no GPU. You write code, analyse on the CPU and write the notes. **The coordinator runs every GPU fit and makes every commit.** Never ask for approval; if something is blocked, say so in your reply and carry on with the rest.
- I will run the two planned fits (`warmup` again in full as `attempt_02`, and `first_cap`) after the TG-002 batch that is running now, and tell you when the outputs are in `results/bem/baseline_data/measured_schedule/2026-11-19/`. Do not start fits yourself, also not on the CPU. Keep your own analysis to four threads while fits run.
- Do not edit `solvers/bem_inverse/`, and do not edit `csi_fit.py`, `csi_data.py` or `csi_measured_schedule.py`. Put new code in new files under `experiments/bem_on_baseline_data/`.
- Files you own: new files in `experiments/bem_on_baseline_data/`, `results/bem/baseline_data/measured_schedule/2026-11-19/` (analysis outputs in a new `analysis/` folder; do not touch the fit folders), and in `docs/iterations/adapt_bem_to_baseline_data/11_test_measured_cylinder_schedule/`: `results.md` and `figures/`. The other agent, `tg-misses` (pane `w4:p2`), is finding out why the slider refuses trials as self-intersections; link its note `docs/iterations/investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes/trial_refusals.md` rather than redoing that.
- Keep committed data under 5 MB. Figures as PNG in the activity's `figures/`.
- Separate measurement from reading. The cylinder's size, place and permittivity are nominal (15 mm, centre (0, 30) mm, 3 ± 0.3), so always give the data loss beside the error against nominal.

## Task 1: the loss map over radius and permittivity (start here)

What we know. The saved BEM fit ends near a circle of radius 19.0 mm and permittivity 2.19, loss 0.0840. A plain exact circle fitted to the same rows gives 15.3 mm and 3.05, loss 0.0375. The stopped warm-up run (`warmup/dielTM_dec8f/cuda/attempt_01/local/`) drove the contrast to 32.6 at 1 GHz with almost the same 1 GHz loss as the original first stage (0.0860 against 0.0909). So at 1 GHz a large weak circle and a small strong one fit about equally.

Make that visible, with the exact circle series of `csi_cylinder_info.py` and the same scaling of the loss as the fit (each frequency divided by its data norm, equal weights):

- Loss over radius (about 2 to 70 mm) and permittivity (about 1.05 to 40, log axis), with the centre set to the best exact-circle centre. One panel per frequency set of the schedule: 1 GHz; 1–2; 1–3; 1–4; 1–8 GHz.
- Draw on each panel: the start (65 mm, the weak estimate 1.093 contrast, so permittivity 2.093), the nominal cylinder, the best exact circle, and the path of the saved fit stage by stage. For the path use each stage's exit curve from `fit.json` (`stages[i].curve`): its area gives an equivalent radius, its centroid the centre, `stages[i].contrast` the contrast (permittivity is contrast plus one). Add the stopped warm-up run's three stages the same way, and later the two new fits.
- Report in numbers: along the valley of the 1 GHz panel, how much does the loss change between contrast 1 and 30? Which frequency set first has a single clear minimum near the best circle? Is the saved fit's end point in a separate local minimum on the 1–8 GHz panel, or on a slope that it stopped descending?
- Save the grid as a compact `.npz` or JSON under `analysis/`, and one figure.

Check the tool first: it must reproduce the saved numbers in `cylinder_info.json` (loss 0.0840 for the BEM-equivalent circle, 0.0579 for nominal).

## Task 2: stage table of the saved fit

One table from `fit.json`: stage, frequencies, update band, accepted steps, stop, loss in and out, contrast in and out, equivalent radius and centre at exit, proposals made and refused. I already see: stage one hit its 22-step cap, the next two made 19 and 7 steps, and six of the last seven stages made none. State plainly how much of the 13,412 work units was used (894).

## Task 3: compare the matched fits

When I tell you the two fits are in, compare them with the saved fit as the plan says: unchanged prefix, per-stage stops and steps, refusals, loss at all eight frequencies, equivalent radius, centre, permittivity, area error against nominal. Then write `results.md`: answer first, one table, evidence links, limits.

## Replies

Short and plain, at most three lines per paragraph. Reply when Task 1 has numbers, when each task is written, or when you are blocked. I am watching your pane.
