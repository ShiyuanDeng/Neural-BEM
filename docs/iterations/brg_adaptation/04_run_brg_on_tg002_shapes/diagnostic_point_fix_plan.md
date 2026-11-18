# Repair the wrapper diagnostic point and retry aphex_twin

The coordinator authorized this fix and both fresh attempts on 18 November.
Both original aphex attempts failed before any data or inverse frequency:
the centroid is inside but has only 0.00620839 clearance. The old wrapper
only used its grid when the initial candidates were outside, so it never
searched for a point satisfying the retained 0.01 clearance test.

The new owned helper samples a 201-by-201 grid over the true polygon's
bounds, includes the centroid and origin, and selects the interior sample
with greatest distance from the boundary. It retains clearance > 0.01 and
records the coordinate, clearance and grid size. A read-only Python check
of the same saved 2048-point true polygon confirms ample clearance; the
receipt is `results/brg/tg002_shapes/2026-11-17/aphex_diagnostic_point_check.json`.
MATLAB's actual selected point and clearance will be recorded in settings
and the compact BRG progress log.

This source enters only the public forward solver's analytic-error check,
after its field matrices are built. It is not the incident plane wave.
No BRG code, inverse setting, observation layout, truth or clearance
threshold changes. Existing data are retained. The two failed attempts'
receipts, logs, empty-fit scores and checks are preserved before attempt 02.

Run `run_tg002_control.py --row retry --prepare`, then
`run_tg002_control.py --row retry --campaign --detach` using the same
Python environment and thread variables as the continuation plan.
The separate retry state lives at `results/brg/tg002_aphex_retry/2026-11-18/`;
case outputs stay in the original activity-04 folders. There is no time cap.
The retry queue uses one worker while the prior shipped queue has an active
fit, then up to two. Thus total BRG fits never exceed two and nothing is
restarted. Cog at contrast 4 continues in its existing process.

Activity 05's current preparation requires all 20 hashed source datasets;
it cannot share the free slot with missing aphex data. The coordinator
explicitly permitted starting 05 after the shipped row ends in that case.
Use that fallback. Start 05 after the retries and cog have finished, keeping
the same no-time-cap runner and all existing data hashes.

Success means both fresh aphex fits have 37 data files, inverse states,
compact records and final residuals, with finite curves/histories and
unchanged scoring. Keep failures, inspect figures, report raw scores and
rejection counts, and commit/push each completed batch by owned paths.
