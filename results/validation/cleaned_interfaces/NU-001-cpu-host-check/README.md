# NU-001 CPU host check

Runs on the cloud CPU host (4 vCPU, 16 GB, no CUDA; `device=auto` fell back
to the CPU, 4 frequency threads). These runs are evidence for the
[iteration 08 plan](../../../../docs/iterations/cleaned_interfaces/iteration_08/03_plan.md). They are **not** part of the
NU-001 campaigns, which run on the CUDA host
([instructions](../NU-001-VALIDATION.md)).

| Folder | What | Outcome |
|---|---|---|
| `nodal__core__circle_to_c` | Unchanged CI-001 sources, scratch campaign | Decision-identical to CI-001 (GPU): 1167 fit units on both hosts; same accepted steps in every stage; stage losses within 2.7e-9 relative; final curve within 1.3e-13. Fit 1067 s here against 63 s; geometry 23 s of it |
| `A__core__wrong_circle` | Arm A, campaign `NU-001-A` before it was reset for the CUDA run | Same endpoint as nodal (RMS 7.58e-6 mm, max residual 5.3e-14). Final audit fails only the per-column Jacobian gate: columns a37/b37/b36 at about 1e-14 of the largest column have 4% production/refined relative error (absolute 1.4e-15 of the largest column; nodal 1.5e-15) |

Two attempts to run cases concurrently on this host were killed by the OOM
killer and discarded: four cases, then two. The nodal Kress initial audit alone
peaks at about 9 GB with either update (measured: nodal 9.0 GB, arm A 9.1 GB).
