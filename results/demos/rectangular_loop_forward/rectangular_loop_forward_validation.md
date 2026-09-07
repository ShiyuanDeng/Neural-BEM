# Rectangular Forward Validation

- solve_strategy: `direct`
- scattered broadband relative error: 0.696145
- total B-scan relative error, all samples: 0.0259846
- total B-scan relative error, t >= 2 ns: 0.564599
- scattered B-scan relative error, t >= 2 ns: 0.696116

## Frequency Error

| f (GHz) | abs error | rel error | mixed error | reference norm |
|---:|---:|---:|---:|---:|
| 0.504687 | 6.668473e-09 | 0.0998889 | 0.0998889 | 6.675893e-08 |
| 1.50406 | 2.720002e-08 | 0.244445 | 0.244445 | 1.112727e-07 |
| 2.00375 | 7.986371e-08 | 3.39807 | 3.39807 | 2.350268e-08 |
| 2.50344 | 1.672734e-08 | 0.153756 | 0.153756 | 1.087915e-07 |
| 4.0025 | 5.861544e-08 | 1.06712 | 1.06712 | 5.492859e-08 |
| 8 | 1.384321e-09 | 2.29568 | 0.232253 | 6.030110e-10 |

## Direct vs Squared State Solve

| f (GHz) | direct residual | squared residual | state diff | receiver diff | cond(A) | cond(A^2) |
|---:|---:|---:|---:|---:|---:|---:|
| 0.504687 | 3.014e-15 | 4.727e-08 | 8.418e-05 | 4.574e-10 | 1.414e+11 | 1.730e+15 |
| 1.50406 | 1.465e-15 | 4.114e-08 | 1.454e-04 | 7.501e-10 | 1.436e+11 | 1.395e+15 |
| 2.00375 | 1.121e-15 | 6.068e-08 | 1.984e-04 | 1.337e-09 | 1.470e+11 | 1.134e+15 |
| 2.50344 | 9.988e-16 | 4.218e-08 | 1.266e-04 | 9.706e-10 | 1.510e+11 | 1.147e+15 |
| 4.0025 | 1.261e-15 | 3.355e-08 | 6.233e-05 | 8.066e-10 | 2.948e+11 | 1.130e+16 |
| 8 | 1.163e-15 | 1.781e-08 | 2.409e-05 | 4.942e-10 | 6.101e+11 | 4.382e+16 |
