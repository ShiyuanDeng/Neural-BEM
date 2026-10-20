# Trial curves at one fixed base

**Question.** At one base boundary (J, g, H_GN, D fixed), which curves do the damping and halving loops build,
which does the geometry update refuse, and where do refused curves cross themselves?

**Run.** One default-method fit of `aphex_twin__c13.3` (`experiments/trial_curves/capture.py`), saving each
`proposal` event. Result: `NUMERICAL_FAILURE` in `stage_3_damped` (rms 4.15 mm); kept as evidence in
`results/trial_curves/`. The first iteration of stage 3 is replayed with geometry operations only
(`replay.py`, `trial_curves.ipynb`): 5 damping trials x 8 halvings, no loss test, no `validate`.

**Check.** Replay step sizes and statuses match the real loop's rows for that iteration.
