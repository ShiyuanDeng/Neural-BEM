# Topology iteration 04 — broad scenes expose shape and feasibility gaps

TOP-006 completed on 2026-09-11. [Full results and visuals](../../../../results/validation/topology/TOP-006-20260911-scenes-v1/README.md).
The numerical controller stayed at `f391eb3`; the new work is a frozen
twelve-scene benchmark and reporting infrastructure.

## What the scenes show

Both default A and selective F pass **5/12 scenes** under the new common
criteria. All 24 runs were attempted: fourteen returned normally, four failed
with a geometry exception, and six reached the predeclared ten-minute limit.
Only ten of the normal returns pass all quality gates. Exceptions/timeouts are
failed measurements, with last-state geometry and work lower bounds retained.

| Scene family | Outcome in both policies |
|---|---|
| Repeated birth, death, circular split, mixed | PASS; exact original final states, solve counts and stop reasons reproduced |
| Original merge | Same original result, but FAIL under the new absolute holdout gate: 9.40% against 5%, despite only 0.554-mm boundary error |
| Distant large circle → two circles | PASS, boundary error below 0.1 µm |
| Distant large circle → ellipse + star | FAIL: three circular components, then uncaught refined separation error |
| Empty start → ellipse + star | FAIL with the same type of inferred-separation error |
| Central/enclosing starts → ellipse + star | FAIL: ten-minute timeout, substantial extra or incorrect material remains |
| Distant large circle → two stars | FAIL: correct count, circular shapes; 7.60-mm boundary error and 100.3% worst holdout error |
| Distant large circle → three different shapes | FAIL: timeout with extra circular components |

The user's requested initial circle has radius 75 mm and is disjoint from the
ellipse and star, with a minimum boundary gap of 95.41 mm. The targets and
initial circle lie inside the unchanged inspection disk. The final saved
failed state locates the target neighborhoods but uses circles, including an
extra small component: IoU 0.695 and 17.59-mm maximum matched boundary error.
The exception occurs when inferred components approach 9.971 mm separation,
below the solver's required >10 mm. This is not an invalid truth scene.

These outcomes do not erase TOP-005's circular split improvement. They reject
its generalization to this broader scene matrix. The old ellipse/star
replacement challenge used a prescribed two-object replacement and explicit
shape-mode/frequency continuation, so it did not establish automatic recovery
from these initializations. The stricter v1 holdout gate also does not rewrite
the old merge qualification, which used a different comparison criterion.

## Verification and permanent comparison

All twelve oracle checks passed; maximum 256/512-node relative difference for
noncircular analytic truth was 1.64e-13. The oracle uses the same Kress solver
on different analytic geometry/discretization; all-circle scenes instead use
independent cylindrical harmonics. All paired inputs, original-control
reproductions, outcome checks and measured-source checks pass. **546 inverse
tests pass**, including thirteen benchmark tests.

After all 24 jobs stopped, only benchmark input validation/reuse and reporting
were improved. The exact executed harness is archived with its hashes, and
AST checks confirm inversion, geometry metrics, gates and job execution did
not change. Failed-state overlays/videos use saved progress; no inversion was
rerun to fill missing diagnostics. Full candidate trials are unavailable for
uncaught exceptions/timeouts, so their work counts are explicitly lower bounds.
Independent scientific reviewer remains unassigned.

The [v1 specification and usage rules](../../../benchmarks/topology_scenes.md)
are now the required current/future topology performance matrix. All twelve
observation and initial-state files were reused byte-for-byte through
`--reference-data` in a separate preparation check with zero new oracle solves.
Keep failed rows, the original acquisition/budgets and the original thresholds.
New conditions require a separately named comparison or benchmark version.

## Next discriminating questions

1. **Refined feasibility during fixed-topology refinement.** Accepted inner
   steps can reach a state that the refined solver rejects before the next
   topology pass. Test a rejection/backtracking or rollback rule at both
   resolutions before claiming robust recovery. Do not relax the separation
   threshold to hide this failure.
2. **Shape capacity after birth.** Birth seeds are circles, and surviving
   components have no general automatic bandwidth-promotion step. Investigate
   data-driven shape-mode activation with the same twelve scenes and frozen
   observations; distinguish this from proposing more circular objects.
3. **Information beyond the training frequency.** The merge and two-star
   results separate plausible outlines/counts from held-out prediction. Any
   new frequency schedule must be declared separately from the v1 comparison.

No controller fix, schedule change or new inversion was executed as part of
this closeout. TOP-002–TOP-004 remain deferred proposals.
