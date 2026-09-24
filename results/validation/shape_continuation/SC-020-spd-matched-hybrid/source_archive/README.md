# Archived run sources

Added 2026-09-24 in response to the [outsider review](../../../../../docs/iterations/shape_frequency_continuation/iteration_08/02_proposals/01_codex_outsider_review.md),
which found that the current tree no longer matches some of this run's
recorded source hashes. The files here are the exact texts the run used.
They were rebuilt by reversing the two logged post-run edits (SC-021's
`update_modes` parameter in `spd_cases.py`; SC-022's `next_damping`/`step_m`
history fields in `lm_backend.py`), and each file's SHA-256 equals the value
recorded in `../manifest.json` (`check.json`). Every other recorded source
still matches the tree at commit 7477dce.

To replay the run, overlay these files on that commit.
