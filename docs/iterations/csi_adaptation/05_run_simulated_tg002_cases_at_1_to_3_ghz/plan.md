# Run the simulated TG-002 cases at 1–3 GHz

**Current process rule, relayed 18 November 01:24 UTC:** the user's words:
"do not stop result-gerating terminal processes due to time limit unless
i say otherwise. if it stucks or goes wrong you should still stop it.
this is only about time limit". Time is a design target, never an
automatic stop. A stuck/faulty fit may be stopped after reporting what
was seen, unless urgent. The memory guard may act as originally designed.
This supersedes the more restrictive 01:18 wording. The old launcher and
the stopped grid check remain untouched.

18 November 2026. User decision, relayed by the coordinator at 00:55 UTC:
**"id say we just supply less frequency range to it, you know below 4GHz
such that simulated data are accurate there."** This replaces the planned
eight-frequency continuation. Its code is retained but must not launch.
The original eight-frequency batch 1 finishes untouched as a side result.

Question: how does unchanged MF-CC-CSI recover all ten TG-002 shapes at
relative permittivity 4 using only 1, 2 and 3 GHz? The simulated circle
errors in that band are 0.1723, 0.1260 and 0.3034 percent relative L2.
No numerical success cut-off is selected here; report frozen raw metrics.

Settings chosen by the user: 2048 iterations; checkpoints 256, 512,
1024 and final 2048; native back-propagation start; three fits at a time;
14 GiB memory reserve; MF-CC-CSI only. Grid remains 166 by 166, 1.25 mm,
half-width 103.75 mm; native projection, objective, line search, five-cell
border/PML, source calibration and eight wrapper compute threads remain.
No solver, comparison-code or external-upstream changes.

Four batches in the same order: circle/kite/peanut; star/asymmetric/c_shape;
hook/cross/cog; aphex_twin. One centred native start, no grid search.
Start only after original launcher PID 708268 exits by itself and its
first-batch outcomes and push are confirmed. No further go is required.
The cancelled eight-frequency resume never starts.

Data: unchanged eight-frequency 0.625 mm native-generator tables. Reuse
the exact hashed circle, kite and peanut tables. Generate the other seven
with the unchanged original generator and frozen truth. The native driver
has a frequency list; set `fre=1:3`. Pre_InvFresnel_Conf calls ReadFreData
only for those three frequencies, which selects column 3 by equality.
The driver loads the full parent table, but neither configuration nor
inversion uses rows at 4–8 GHz. Save exact selected-row text separately
with a hash and parent hash for the BEM side, without modifying parents.

Coordinator priority update, 18 November approximately 01:31 UTC: generate
the other seven tables now, ahead of fits, so BEM can read them early.
Use one MATLAB at a time and the exact generator/source hashes recorded
by the old campaign. Store all ten parents (copying the first three by
hash) at results/csi/tg002/2026-11-18_low_band_data/{shape}/forward/synthetic_input.txt,
with SHA-256 sidecars and selected-row files/hashes. The old live campaign
folder is read only. Activity 05's inverse launcher must reuse all ten
cache tables by hash and must never regenerate. The prefetch controller
has nice 10 so the existing batch-1 fits retain CPU scheduling priority;
native eight-thread settings stay unchanged. The 14 GiB guard may delay
starts or stop only the newest owned forward on an urgent reserve breach.
No automatic time stop. Commit/push each generated table's compact
metadata/logs, keep full tables local/ignored, and update data_note.md.
Command: EMNerf Python -B -m experiments.baselines.csi.prepare_low_band_data,
with PYTHONPATH=solvers:. This is forward-only work, no inverse test run.

Frequency-dependent native choices: three frequency blocks and matrices;
three back-propagated fields contribute to the common initial contrast;
the objective's native frequency averages divide by three, and its
gradient/line-search sums cover those same three. Conductivity scaling
uses the first frequency, still 1 GHz. Native displayed/history image and
the raw callback use the last frequency, now 3 GHz (formerly 8 GHz).
The real contrast is common to all frequencies. Metadata/scoring must
state 3 GHz; no invented replacement reference or retuning is applied.
Each of 1/2/3 GHz retains its own unchanged per-source calibration.

Time target: initially six hours on this new campaign's own original clock,
including data preparation. Read `budget_hours.txt` at every stop check
and record its initial value and each changed value used. Passing that
target is recorded and reported while every fit continues. STOP is an
independent file and is never removed automatically. Write the completed
first-batch forecast, then carry on without a forecast exit. Time checks
never terminate a running process. STOP and explicit signals remain
controlled-stop paths. The urgent 14 GiB guard may stop the newest owned
fit, preserve that failure and reduce later concurrency to two. It never
touches BRG workers. A controller error is reported and healthy running
workers are monitored to native completion instead of being killed for
an unrelated reporting error. Keep all outcomes and partial evidence.
A failed fit is recorded and the controller continues with remaining
eligible cases; it never changes settings or restarts from an image.

Launcher: new module experiments.baselines.csi.campaign_low_band; results
root results/csi/tg002/2026-11-18_low_band/. Use `setsid nohup`, detached
stdin and an ignored campaign_launcher.log. Provide `--dry-run` and
`--resume`; resume retains start time, STOP, configuration and finished
cases. It must refuse active same-campaign workers and never overwrite
finished fits or restart an optimizer from a contrast image. Interrupted
fits stay recorded; only unstarted fits may run. Source hashes and exact
commands accompany every launch, including resume invocations.

Primary command (EMNerf Python with PYTHONPATH=solvers:.):
`python -B -m experiments.baselines.csi.campaign_low_band`;
check with `--dry-run`, resume with `--resume` if needed. Perform only
read-only real-folder checks and temporary fake-worker checks before
launch; no MATLAB inverse test run. The unchanged output callback was
already checked in activity 04.

Report when the campaign starts (PID, folder, frequency handling), after
about 100 iterations (observed seconds per iteration from numerical log
progress, with basis), and after each batch. Keep native final timing
separate from wrapper/startup timing; record other MATLAB overlap.

After every batch score all snapshots with unchanged protocol-1 helpers
(half signed peak, 0.3/0.7 sensitivities, all components/holes), keep exact
raw float64 arrays, manifests, costs, resources and compressed logs.
Write report figures under this activity's figures/. Keep bulk local and
ignored; about 5 MB per run maximum. Commit only CSI paths by name, push,
and confirm status. Failures are committed too. Final report uses the
coordinator's required activity block and reports actual completion.

The results include the BEM data note: exact parent path/hash, selected
rows/hash, frequency list, pair mask/order and exp(+j omega t) convention.
BEM independently checks every shape on these exact retained data. The
band decision does not turn the circle check into checks of all shapes.
