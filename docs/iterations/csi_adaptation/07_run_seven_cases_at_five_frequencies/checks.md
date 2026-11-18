# Checks before launch

18 November 2026, 03:55–03:57 UTC, from `date -u`.
No fit or forward solve ran. No frozen table was written or regenerated.
No upstream numerical change is needed.

## Native frequency handling

MATLAB R2026a ran `experiments/baselines/csi/check_five_frequency.m`.
The check executes unchanged native source sections on tiny array fixtures:
ReadFreData's column-3 equality filter, complex subtraction and TM reshape;
Pre_InvFresnel_Conf's five-cell-array allocations, five 36-source initial
blocks, and first-frequency scaling. The real native get_chiMF initializer
also recovers its known complex fixture with the five-frequency list.
Each selected frequency has 1764 rows, reshaped to 49 receivers by 36
sources. The image metadata and native image/history use the final list
entry, 2.5 GHz; conductivity scaling uses the first, 0.5 GHz.
ReadFreData uses floating frequency values in wavelength calculation and
num2str for cache names; it never uses them as frequency-array indices.
No cache was read or created by the array-only check.

The owned executed driver was materialized in a temporary folder with
process creation mocked. It contains the literal five-entry half-integer
list, the unchanged 2048 iterations and only MF-CC-CSI. It reads the same
full frozen input path as BEM, with no subset file. Removing the recording
function rename and output callback from the recorded numerical copy
restores the full upstream CC_CSI_Brent text exactly.

Evidence: [native result](../../../../results/csi/tg002/2026-11-18_five_frequency/checks/native_check.json)
and [native log](../../../../results/csi/tg002/2026-11-18_five_frequency/checks/native_check.log).

## Controller and frozen-input checks

`python -B -m experiments.baselines.csi.check_five_frequency_launcher`
passed with seven fake fits and zero real fits, all in temporary folders.
Releases arriving after controller startup were consumed. Dynamic worker
limits were read repeatedly; dropping the ceiling below the running count
did not call stop. Missing policy defaults to three; a noninteger is
rejected. The informational time target was already exceeded, and all
seven fake fits still completed. A finished resume kept the original
start and launched nothing; an interrupted launch was kept and not retried.
STOP remains in place and blocks a resume. Synthetic input fixtures
checked row count, frequency order, mask/order, pinned releases and a
changed-hash rejection. Test fixtures never touched the real data folder.

The first Python check hit Python 3.9's nesting limit in its test mocks;
replacing the nested mock context with ExitStack fixed it. No fit ran.
Evidence: [controller result](../../../../results/csi/tg002/2026-11-18_five_frequency/checks/launcher_check.json).

The real `--dry-run` is read-only and reports seven shapes, zero releases,
the five-frequency list, and the live resource ceiling of two. It starts
no worker. The controller remains unlaunched pending the coordinator's go.
All old launchers remain unlaunched. `git diff --check` passed.
