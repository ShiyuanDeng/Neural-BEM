# Post-schedule reporting failure

Observed during the 2026-09-15 owner closeout review while the companion S arm
was still running. Numerical source remains frozen at `9bde9d1` until both
workers finish. No physical replay or restart is needed for this diagnosis.

F completed stages 2, 3 and 4. The inherited `run_schedule` saved
`status=COMPLETED_SCHEDULE`, qualified scores for all three endpoints, the final
accepted state and 3,455 attempted/completed solves. The final reconstruction
gates pass. The process then failed in the TOP-018 wrapper's added annotation
loop, before writing its extra objective-identity fields and final integrity
flag. The exact traceback is preserved in `F.log`.

The failing expression compares `last_gradient['active_frequencies_hz']`, a
Python list, against `stage['active_frequencies_hz']`, an inherited tuple. Their
values and ordering agree exactly, but Python list/tuple equality is false.
JSON serializes both as arrays. Read-only verification of all three saved F
stages confirms exact frequency equality and the intended 256/512 resolutions.
There is no measured frequency or numerical-resolution mismatch.

Required closeout repair, after both numerical workers stop:

1. Preserve original metrics, terminal files and failed worker logs.
2. Compare frequency sequences by value with a regression test that exercises
   the actual inherited tuple and gradient list.
3. Rebuild only the missing objective associations from the already saved
   states, observations and resolution settings; do not evaluate a derivative,
   objective or physical forward.
4. Verify the frozen measured sources before editing reporting code, and keep
   the measured Git revision/hashes as the numerical provenance. Record later
   reporting-only source changes separately.
5. Keep worker exit failures visible alongside the recovered reporting and
   completed numerical schedules. Do not relabel the process as an error-free
   execution or discard its artifacts.
