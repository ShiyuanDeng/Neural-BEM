# Literature, numerical stopping and GPU review

2026-10-03. Consolidates the discussion after FM-002. Author: Codex.
Independent reviewer: unassigned. This is a literature-informed assessment,
not a claim that every published relaxation variant has been reviewed or
implemented.

## Relevant precedents

| Subject | Primary source | Relevance and limit |
|---|---|---|
| Accuracy during optimization | [Ulbrich & Ziems, 2017](https://ems.press/journals/pm/articles/14763) | Adaptive multilevel trust-region optimization refines discretization using error estimates. This supports testing controlled refinement; its PDE setting and convergence theorem do not directly certify our BIE implementation |
| Boundary regularization | [Borges & Greengard, 2015](https://arxiv.org/abs/1408.5436) | Band-limited boundary updates, filtering and step damping address inverse-obstacle instability. Their sound-soft setting differs from our dielectric transmission problem; our pipeline already contains related controls |
| Complete reduced gradient | [Rizzuti et al., 2021](https://slim.gatech.edu/Publications/Public/Journals/Geophysics/2021/rizzuti2020dfw/rizzuti2020dfw.html) | Variable projection eliminates the optimizing field while retaining the model derivative of the full objective. In our shape problem the receiver rows and penalty also depend on geometry; FM-002 includes those terms |
| Penalty sensitivity | [Aghamiry, Gholami & Operto, 2018 preprint](https://arxiv.org/abs/1809.00891) | Iteratively refined WRI uses an augmented Lagrangian to address penalty-tuning/conditioning difficulties. This is a different algorithm, not an established explanation of our resolution stops |
| Curvature approximation | [Peters & Herrmann, 2014](https://slim.gatech.edu/Publications/Public/Conferences/SEG/2014/peters2014SEGsrh/peters2014SEGsrh.html) | Reduced-Hessian information can improve WRI updates. Our frozen-weight positive curvature remains an approximation; no evidence yet makes its replacement the cheapest next test |

The numerical stop is not evidence of a previously unknown obstruction. The
specific source of each field-discrepancy failure still requires measurement.
Published remedies are candidates for a controlled test, not promises that
our four runs will recover.

## GPU evidence and priorities

FM-002 already used the RTX 5090 for real/damped system assembly, LU
factorization, forward and adjoint solves. The four hard real-prefix runs
recorded no device-memory fallbacks. The rough 2–4 hour follow-up estimate
already assumed these existing capabilities.

The complete relaxed-gradient routine still constructs its reverse graph on
CPU and calls SciPy special functions. In the hard C/R1 run it recorded
527.9 seconds within a 652.9-second elapsed run; for star/R1 it recorded
504.7 seconds within 839.0 seconds. These are saved diagnostic timings, not
matched CPU/GPU measurements or an additive profile of every concurrent task.
A GPU port has substantial potential for full relaxed-prefix reruns, but it
requires verified derivative kernels, not just changing a device flag.

`DeviceFactors` currently offloads matrices and LU factors after the initial
solve, then uploads them for later solves. Keeping a bounded set resident on
GPU is another potential optimization. PyTorch supports complex factored and
batched solves ([LU solve documentation](https://docs.pytorch.org/docs/stable/generated/torch.linalg.lu_solve.html));
that capability does not establish a speedup for this workload. Memory and
transfer costs must be measured at the actual refined resolutions.

For RB-001, the cheapest saving is to resume the four ordinary-loss tails
from qualified saved states. This avoids repeating localization and relaxed
prefixes. Adaptive refinement also limits higher-resolution work to where
it is needed. Those savings do not require a new GPU derivative implementation.

## Resolved recommendations

| Recommendation | Disposition |
|---|---|
| Correct the incomplete relaxed gradient | **Accept; complete in FM-002**. Preserve its finite-difference and CPU/CUDA qualification |
| Keep damping and relaxation independently controlled | **Accept; complete in FM-002**. RB-001 retains both R0 and R1 tails |
| Investigate the numerical stop before broader closure | **Resolve through RB-001**: exact candidate replay, bounded refinement/step retries, then conditional continuation |
| Loosen field-discrepancy tolerances to permit progress | **Reject**. Preserve the original accuracy requirements and improve the evaluation or shorten the step |
| Resume saved ordinary-loss tails on existing CUDA | **Accept into the RB-001 plan**, subject to reconstruction and restart-equivalence checks |
| Port the complete relaxed gradient to GPU now | **Defer** until a later relaxed-prefix experiment needs it; it does not accelerate the ordinary tails that answer RB-001 |
| Add GPU factor residency or frequency batching now | **Defer implementation**. RB-001 records memory, fallback and cost evidence; a separate matched benchmark must justify changing the execution path |
| Replace the penalty schedule or add augmented-Lagrangian updates | **Defer** until the resolution question is resolved; no penalty failure has been diagnosed here |
| Replace the curvature approximation | **Defer** for the same reason; keep it fixed in this experiment |
| Run all 36 cases | **Defer**. Four stopped trajectories and existing controls answer the immediate question |

The [RB-001 plan](../03_plan.md) is the sole proposed execution contract.
This review does not authorize a new run or any of the deferred optimizations.
