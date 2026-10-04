# PC-001: node-free versus nodal pipelines on TG-002 (N0 stopped by the user)

Plan: [iteration 27](../../../../docs/iterations/cleaned_interfaces/iteration_27/03_plan.md),
approved by the user ("go"). Code at launch: `583b4e0f`. Launched 2026-10-04 19:42 BST
(`python -m experiments.benchmark.pc001 run --arm all`, order M1, N1, N0; 2 workers, CUDA).

**Status: M1 and N1 complete (30/30 each). N0 stopped by the user at 21:32 BST after
12/30 cases**, with the instruction: "stop nodal baseline. we need to make it fair by
reusing geoemtry across frequency first." The process group was terminated. Two N0
folders, `asymmetric__c4` and `star__c13.3`, were in progress and are preserved
incomplete; the campaign runner refuses to reuse them. N0 must be rerun in a fresh
directory under a new approved ID.

| Arm | Pipeline | Done | Recovered (c0.5 / c4 / c13.3) | Median s | Failures |
|---|---|---:|---|---:|---|
| M1 | `modal_fixed` | 30 | 26 (9 / 9 / 8) | 31 | aphex_twin ×3, hook c13.3: `NUMERICAL_FAILURE` in 30–48 s |
| N1 | `nodal_fixed` | 30 | 26 (9 / 9 / 8) | 157 | same four: promoted to N1024/2048, then 2 `ACCURACY_LIMITED_TRIALS`, 2 `TRIAL_WALL_LIMIT` (814–1,863 s) |
| N0 | `nodal_baseline` | 12 (stopped) | 12 (5 / 4 / 3) | 120 | none among the 12 |

- M1 and N1 recover the same 26 cases; their final RMS values agree to about eight
  significant figures. R1 holds at every contrast. R3 = 0: N1's promotion moved its four
  failures further but recovered none.
- Wall time: M1 9 min (sum of case times 1,031 s). N1 84 min (9,926 s), of which 5,811 s
  were the four failed, promoted cases.
- R2 and R4 need a complete N0 and stay pending. P4 failed (`c_shape__c13.3` recovered by
  M1 and N1). P3 holds (N1 promoted, on all three aphex_twin contrasts, not mostly c13.3).
- Timing caveat (user): modal Müller caches frequency-independent geometry per curve,
  while nodal Kress rebuilds it for every frequency. Nodal times here are not yet a
  like-for-like cost comparison.

Files: `report.md` (side-by-side tables, generated from the stopped state),
`comparison.csv`, `report.json`, `comparison.png`, `logs/run.log`, `{M1,N1,N0}/runs/`.
