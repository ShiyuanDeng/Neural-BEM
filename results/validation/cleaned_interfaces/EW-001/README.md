# EW-001 — closed: CIRCLE_FAILS_AT_UNREGISTERED_SPLIT

Approved user instruction: "go on EW-001". Registered Q1/Q2 only.

| Split | Grid | Cutoff | Max normalized error | Circle gate |
|---:|---:|---:|---:|---|
| 0.35 | 128 | 64 | 0.025227963 | FAIL |
| 0.35 | 128 | 128 | 0.025227963 | FAIL |
| 0.35 | 256 | 64 | 8.7950031e-05 | FAIL |
| 0.35 | 256 | 128 | 0.00049557914 | FAIL |
| 0.4 | 128 | 64 | 0.067038614 | FAIL |
| 0.4 | 128 | 128 | 0.067038614 | FAIL |
| 0.4 | 256 | 64 | 0.00075085518 | FAIL |
| 0.4 | 256 | 128 | 0.0071328799 | FAIL |
| 0.5 | 128 | 64 | 0.20778469 | FAIL |
| 0.5 | 128 | 128 | 0.20778469 | FAIL |
| 0.5 | 256 | 64 | 0.0031715501 | FAIL |
| 0.5 | 256 | 128 | 0.016056897 | FAIL |
| 1 | 128 | 64 | 0.4806176 | FAIL |
| 1 | 128 | 128 | 0.89355132 | FAIL |
| 1 | 256 | 64 | 0.015368467 | FAIL |
| 1 | 256 | 128 | 0.043174055 | FAIL |

The best normalized circle error was 4.9558e-4 (gate 1e-7). Complex128 contraction-only lower bound: 5.129 s per service, 46–48x current modal assembly. See [the report](../../../../docs/iterations/CI-SPD/iteration_03/05_results.md).

Original ON-003 evidence remains unchanged. Full fields, curved blocks, derivatives and inverse integration are unrun.
