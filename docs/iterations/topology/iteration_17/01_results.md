# TOP-024 results — neither arm recovered

One bounded 12-update matched continuation pair is complete under the
[iteration-16 plan](../iteration_16/03_plan.md), with unchanged 256/512 numerical
and original recovery gates. Both arms start from TOP-022's exact failed
terminal state; only initial damping differs.

| Prescribed state | Boundary error (mm) | Sampled IoU | 0.5-GHz relative error | Worst development error | Recovery / numerical gates |
|---|---:|---:|---:|---:|---|
| Shared TOP-022 start | 9.755053 | 0.830130 | 0.0019287484 | 0.61918485 | Fail / Pass |
| A: baseline damping | 9.628346 | 0.828473 | 0.001996214 | 0.62852257 | Fail / Pass |
| B: initial reset to 1e-2 | 9.532729 | 0.827740 | 0.0019993654 | 0.62748754 | Fail / Pass |

Neither arm recovers within the declared bounds. The initial damping reset does not resolve the fresh two-star recovery blocker. No fresh integration or full-suite run is released. Further work needs a separately declared bounded diagnosis of the remaining failure; this experiment does not establish non-recoverability at arbitrary cost or from other starts.

The reset's slightly better boundary error remains far above 1 mm. Both arms
have worse IoU and worst development prediction than the shared start despite
lower aggregate training objectives. Both stop at `maximum_iterations` with
endpoint-associated gradients above the 1e-7 stationarity tolerance.

New work: **7,504 attempted / 7,504 completed frequency systems,
0 failed/refused**. Both first steps match their TOP-023 witnesses.
98 pre-dispatch tests, all 205 frozen source hashes,
input checks and saved-array replay pass. Campaign elapsed: 29.97 min,
two BLAS-1 workers. Stop reasons, terminal gradients, individual work, all gates
and interpretation are in the [authoritative bundle](../../../../results/validation/topology/TOP-024-20260915-201101-bounded-damping-pair/README.md)
and [owner review](../../../../results/validation/topology/TOP-024-20260915-201101-bounded-damping-pair/closeout_review.md).

TOP-018's successful saved-common-start two-star result and TOP-019's corrected
K17 merge control remain valid. TOP-020/022 fresh failures remain preserved.
The overall automatic method is not yet reliable by the full roadmap's criteria.
TOP-021 and the twelve-scene suite remain undispatched; no successor runs here.
