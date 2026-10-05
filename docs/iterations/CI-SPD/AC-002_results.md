# AC-002: time spent in each part of the current forward solve

2026-10-05. [Plan](AC-002_plan.md),
[measurements](../../../results/validation/cleaned_interfaces/AC-002/profile.json),
[driver](../../../experiments/benchmark/radial_forward_profile.py).

Current analytic-coefficient implementation (AC-001), TG-002 C-shape truth,
contrast 13.3, real 2.5 GHz, K_trace=96, coefficient window=160. One frequency
thread and one BLAS thread. Each column is the mean of three sequential
repetitions, after untimed device/runtime warm-up. A fresh backend builds its
geometry and arrays; reuse repeats the same curve and frequency on that backend.
The matrix, LU and fields are still recomputed in the reused call.

Timings are exclusive wall time, with CUDA synchronization at nested GPU
boundaries. Percentages divide each category's accumulated duration by the
matching total forward duration. They sum to 100% before display rounding.
These are instrumented single-frequency measurements, not inverse timings or
concurrent 19-frequency catalog throughput. Hardware is an Intel Core Ultra 9
285K and NVIDIA RTX 5090. The radial degree is 62 and log degree is 147.

## CUDA forward solve

| Work | Fresh geometry ms | Share | Reused geometry ms | Share |
|---|---:|---:|---:|---:|
| Log-Chebyshev construction and its interval certificate | 22.479 | 46.49% | 0 | 0% |
| Radial Chebyshev-array setup/extension | 8.877 | 18.36% | 0.026 | 0.22% |
| Scalar analytic Chebyshev coefficients (CPU) | 2.950 | 6.10% | 2.838 | 23.68% |
| Contract scalar coefficients with radial arrays | 0.632 | 1.31% | 0.657 | 5.49% |
| Remaining matrix assembly, including matrix transfer | 1.513 | 3.13% | 1.525 | 12.73% |
| Graf source/receiver waves (CPU) | 7.039 | 14.56% | 2.786 | 23.25% |
| LU factorization (CPU) | 2.707 | 5.60% | 3.011 | 25.13% |
| RHS solve and receiver fields (CPU) | 1.061 | 2.19% | 1.052 | 8.78% |
| Other geometry setup and bookkeeping | 1.092 | 2.26% | 0.088 | 0.73% |
| **Complete forward solve** | **48.351** | **100%** | **11.984** | **100%** |

The 0.026 ms in the reused radial-basis row is the cache check plus instrumented
synchronization, not new polynomial construction. The log row includes the
reciprocal/certificate calculations required by that construction; it is not a
recurrence-only timer. Radial setup includes its multiplication helper and the
first two arrays; extension builds the remaining arrays during assembly.

For this probe, log construction/certification, radial arrays and scalar
coefficients together account for **70.95%** of a fresh forward call. The
reusable log and radial construction alone account for **64.85%**. In the
reused call the scalar coefficients remain a **23.68%** cost. Pure radial
contraction plus remaining matrix assembly takes **4.44%** fresh and **18.21%**
reused. These categories must not be added to an inclusive assembly timer.

## CPU control

| Work | Fresh geometry ms | Share | Reused geometry ms | Share |
|---|---:|---:|---:|---:|
| Log-Chebyshev construction and interval certificate | 211.334 | 55.30% | 0 | 0% |
| Radial Chebyshev-array setup/extension | 90.494 | 23.68% | 0.003 | 0.004% |
| Scalar analytic coefficients | 2.919 | 0.76% | 2.897 | 4.32% |
| Contract scalar coefficients with radial arrays | 10.173 | 2.66% | 9.506 | 14.17% |
| Remaining matrix assembly | 51.871 | 13.57% | 47.630 | 70.98% |
| Graf source/receiver waves | 7.185 | 1.88% | 3.057 | 4.56% |
| LU factorization | 2.659 | 0.70% | 2.662 | 3.97% |
| RHS solve and receiver fields | 1.048 | 0.27% | 1.061 | 1.58% |
| Other geometry setup and bookkeeping | 4.496 | 1.18% | 0.285 | 0.42% |
| **Complete forward solve** | **382.178** | **100%** | **67.100** | **100%** |

The scalar coefficient cost here is about 2.9 ms because this is a particular
high-frequency/high-contrast configuration. AC-001's approximately 1 ms was a
median across 24 different scalar configurations and is not the matched
denominator for this forward profile.

## Validation and historical percentages

All 12 instrumented calls match their uninstrumented device reference exactly
(zero relative difference), passing rtol=1e-11, atol=1e-15. Every category is nonnegative, the
exclusive durations equal elapsed forward time, and the saved source hashes
match the executed implementation. No production code was changed.

The likely remembered percentages are in the
[2026-10-01 modal campaign review](../../../results/validation/cleaned_interfaces/CI-001-modal-review/README.md):
47% Graf, 25% assembly, 13% LU, 9% geometry, 5% fields, 2% Jacobian (rounded).
Those were thread-summed stage durations over an older 36-case campaign,
including derivative work, before the analytic scalar change. Its assembly
bucket included scalar coefficients and lazy radial-array construction;
it did not expose this exclusive split. It is not a current wall-time profile.

Geometry/window changes require reconstruction. Shared geometry across
frequencies amortizes the construction costs; a new frequency may still
extend the stored arrays to a higher required degree. No universal Chebyshev
percentage or whole-inverse speedup follows from this single-state profile.
