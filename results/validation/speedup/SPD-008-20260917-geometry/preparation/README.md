# Geometry integration preparation — 2026-09-17

Preparation requested by the user while TOP-025's twelve-scene compiled
campaign runs. Everything in this bundle is outside the measured checkout.
No numerical source, test, configuration or result was changed. No repository
module was imported; no geometry test or inverse solve was run.

- [Integration design and staged checks](integration_plan.md)
- [Validation matrix](validation_matrix.md)
- [Reproducible saved-evidence audit](audit_saved_evidence.py)
- [Audit results](audit.json)
- [19 saved-state fixtures, with source hashes and selectors](fixtures.json)

The audit verified all **211 manifest-listed live sources**, all **7 listed
test files**, **13 historical qualification inputs**, and **60 consumed
SPD-006 artifacts against their saved artifact manifest**. This is scoped hash
verification, not a complete rerun of the campaign verifier or its tests.
It inventoried **81 test functions in 9 files** without executing them.

The fixtures comprise the 11 existing SPD-006 qualification cases, the TOP-006
resolution-sensitive abort, the saved compiled profile input, and the first
and last stage-one trajectory records from three compiled workers. These are
19 selected records; some describe identical geometries. The schema check
verified Cartesian parameter counts and distinct component IDs, not geometry
admissibility. Preserve each record's source and role when reusing it.

Across the 16 archived SPD-006 workers, 616 continuation Jacobian log records
report zero one-sided and unresolved columns, while 20 logged candidate
refusals report the component feature-radius floor. All 20 occur in the hard
central/two-star scenes (3 and 2 per worker respectively). Thus zero constrained
Jacobian columns does not imply an unconstrained line-search trajectory.
Candidate feasibility must remain active under either analytic policy.

Three design corrections came from this preparation:

1. `PeriodicCurveAdapter` owns the exact caller curve object. The safest first
   optimization caches the expensive validation result, not a complete adapter
   belonging to a different, numerically equal curve.
2. Continuous-parameterization validation and sampled-node validation have
   different sampling and tolerance contracts. Sharing is permitted only when
   the actual arrays and resolved tolerance arguments match.
3. A saved geometry passes at 64 nodes and fails at 128/256. Resolution must be
   part of sampled/pair cache keys; a coarse result cannot certify a refined
   boundary.

Run the audit again with:

```bash
python -B /tmp/geometry-integration-prep-20260917/audit_saved_evidence.py
```

It writes only `audit.json` and `fixtures.json` beside itself. It reads only
stable metadata from the active campaign and uses archived SPD-006 workers for
diagnostics. Its output is not a runtime measurement. Initial audit development
needed the SPD-006 artifact manifest's nested `files` mapping; the final script
validates that mapping and its declared file count explicitly.

Future implementation remains deferred until the user reports the active
campaign finished. Copy the design into the speedup track's current iteration
when integrating; do not overwrite the pre-existing modified handoff/history.
The intended next proposal is SPD-008; SPD-009 remains a separate policy study.

