# Topology iteration 05 — the crash is gone; the shapes are the problem

TOP-007 completed on 2026-09-11.
[Full results and visuals](../../../../results/validation/topology/TOP-007-20260911-refined-feasibility/README.md)
· [videos of all twelve guarded scenes](../../../../results/validation/topology/TOP-007-20260911-refined-feasibility/videos.md).
The intervention is one opt-in mechanism in the fixed-topology optimizer; the
frozen twelve-scene v1 benchmark, its observations, budgets and gates are
unchanged, and the default controller is untouched.

## What the guard did

| Measure | Default A | Guarded G |
|---|---:|---:|
| Runs that returned | 7/12 | **9/12** |
| Uncaught exceptions | 2 | **0** |
| Ten-minute timeouts | 3 | 3 |
| Scenes passing all gates | 5/12 | 5/12 |

Arm A reproduced TOP-006 exactly — same final states, solve counts, stop
reasons and training errors on every completed scene, and the same two aborts
at the same 9.971374e-03 m clearance. That is the check that says the change
left the default alone.

Wherever both arms completed, **their final states are identical**. Five of the
seven also match solve-for-solve; `repeated-birth` costs 30 more solves and
`far-two-circles` 9 more for the same answer. The guard rejected 1–216 trial
states per guarded run, and the controller-level rollback never fired once:
refusing the step was enough, and no accepted state had to be withdrawn. The
newly completing runs end with 38.1 mm of refined clearance, so the guard is
not parking states on the floor.

## What the finished runs then showed

`far-ellipse-star`, the case the user asked about, now runs birth, birth,
death, birth and **merge** — merging exactly the two components whose approach
ended the unguarded run — and stops `topology_stationary` with the **correct
2/2 object count**, 18.62 mm matched boundary error, 0.704 IoU, 3.06% refined
training error and 140% worst holdout error. `empty-ellipse-star`, from an
empty domain, converges to the same two components to within 1e-8 m.

Two initializations that share nothing reaching the same wrong shapes puts the
remaining error in the representation and the objective, not in the start.

The reconstruction is a mode-1 circle where the star is and a **mode-9 curve
where the ellipse is**. That component already carries nine modes and still
stops 18.6 mm away with 3.06% training error. Bandwidth is therefore not the
missing ingredient on its own: the optimizer is not exploiting the bandwidth it
already has. TOP-008 was framed as promoting bandwidth after birth; this result
says that framing is incomplete and the promotion question has to be asked
together with why an existing mode-9 component stalls.

## Adoption decision

The plan's three criteria are met: no guarded run aborts, no TOP-006 pass is
lost, and the arms agree wherever they can be compared. The declared
"identical wherever the guard rejects nothing" check turned out to have no
members — every completed guarded run rejected at least one trial — so the
stronger per-scene agreement above stands in its place, and the record says so
rather than claiming a check that did not apply.

**The guard stays opt-in in this cycle, and making it the default is the
recommendation for the next one.** The evidence supports the default, but
flipping it would change the reference behaviour that TOP-001 and TOP-005
replay bundles reproduce against — `repeated-birth` alone would cost 30 more
solves for the same answer — so that change belongs in a declared comparison,
not in a closeout.

## Next discriminating questions

1. **Why a mode-9 component stalls 18.6 mm from an ellipse at 3.06% training
   error.** Answered by a read-only
   [review diagnostic](02_proposals/01_stall_diagnostic.md): that component sits
   exactly on the 8-mm feature-radius floor, 15 of its 20 gauge directions are
   refused by the floor, and each refusal freezes a Jacobian column. The merge
   contour fit handed it a peanut neck 0.8 mm above the floor and refinement
   drove it onto the floor. So the next test is candidate acceptance that asks
   for refinement headroom, together with an FD Jacobian that projects along an
   active constraint instead of freezing the column.
2. **Shape capacity after birth**, as in the iteration-04 question, but now
   conditioned on (1): birth seeds are still circles, the star in both new
   completions is still a circle, and `far-two-stars` leaves 1.4% of its
   training data unexplained with nothing pinned and 22 mm of headroom. Giving a
   component nine modes did not by itself make them usable.
3. **Acquisition.** Of the seven failures only `merge` fits its training data
   (7.9e-05) and still misses the holdout at 9.4%; that one is information
   limited at 0.5 GHz. The rest leave 1.4–3.1% of the training residual on the
   table, so more data is not what they are short of.
4. **The three remaining timeouts.** Central, enclosing and far-three-shapes
   spend ten minutes without converging in either arm. Cost per cycle, not
   feasibility, now dominates those scenes.

No controller default, gate, scene or budget changed in this cycle.
TOP-002–TOP-004 remain deferred proposals.
