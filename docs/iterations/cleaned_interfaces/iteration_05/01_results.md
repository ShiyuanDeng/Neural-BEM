# Modal Müller on CUDA

2026-10-01. Implementation owner: Claude.

## Approval and plan

The user chose speed-ups before the proposed full modal case: "i say we do
speedups first im short on time". The user approved the stated plan with
**"cp, then go."** The plan had four parts:

- commit the CPU service (done, `88f5ee1b`);
- port the modal service's hot stages to CUDA;
- keep `device=cpu` as the unchanged reference;
- validate against predeclared gates: CUDA−CPU fields ≤ 1e-12 and Jacobians
  ≤ 1e-10, identical replay decisions, tests on both devices, and a matched
  benchmark against CUDA Kress.

## Change

[`modal_cuda.py`](../../../../experiments/cleaned_interface/modal_cuda.py)
mirrors the geometry preparation and the per-frequency assembly in torch
float64/complex128. That covers the polynomial products, the certified
log|W|² recurrence, T_n(R), the combination, the window products and the
Galerkin contraction. Several parts stay on the CPU:

- scalar Bessel/Hankel values (no `torch.special`);
- Graf waves;
- LU, fields and the Jacobian.

Handles therefore hold no device memory. Device semantics follow Kress:
`cpu` is the reference, `auto` falls back after out-of-memory with a
recorded reason, and `cuda` is strict.

One CPU-side change came with the port. Regular waves are now built once per
wavenumber and shared by sources and receivers. CPU predictions and
Jacobians are bitwise identical to `88f5ee1b` on four fixture evaluations.

## Measurements

Evidence: [CUDA bundle](../../../../results/validation/cleaned_interfaces/modal-muller-cuda-20261001/README.md).

| Gate | Outcome |
|---|---|
| CUDA−CPU Jacobians ≤ 1e-10 | **Pass** (worst 7.6e-12) |
| CUDA−CPU fields ≤ 1e-12 | **Fail** (2.7e-12 at C, 2.5 GHz, K_trace 96; 3.7e-9 at damped 2.5 GHz, the known cancellation floor outside the policy) |
| Three archived replays on CUDA | **Pass**: every decision, accepted index, exit and work count; endpoints ≤ 1.24e-12 units |
| Tests on both devices | **Pass**: 16 modal tests, including OOM fallback, strict CUDA, and matching CUDA/CPU LM decisions |

The failed field gate was set below the method's own roundoff floor.
Against the independent 2048-node Kress reference, CUDA's error stays
within 2.0× of the CPU error on every fixture. So accuracy is preserved,
but the ≤ 1e-12 gate as declared is not met.

The matched 19-frequency K=192 catalog compares new-geometry forward time
with four frequency threads:

| Level | Modal CUDA | CUDA Kress | Speed-up | Modal CPU |
|---|---:|---:|---:|---:|
| Production | 0.261 s | 0.435 s | 1.7× | 2.06 s |
| Refined | 0.342 s | 1.725 s | 5.0× | — |

With the Jacobian included, production is 0.284 s against 0.647 s (2.3×).
For a single cold frequency, CUDA Kress remains faster (0.030 s against
0.089 s at K=192), because the once-per-curve geometry preparation (about
0.05 s) dominates.

## Interpretation

On multi-frequency and refined workloads, modal Müller on CUDA is now faster
than the maintained CUDA Kress. LM production evaluations use all stage
frequencies and acceptance uses the refined level, so the per-evaluation
physics cost of a K=192 stage should fall. This is not yet an inverse
runtime result. SC geometry updates and their sampled validation are
unchanged CPU work, and could now dominate.

## Next (proposed, not run)

1. One full original-start case with `solver='modal_muller'` and
   `device=auto`, beside its CI-001 nodal result. It measures total runtime,
   the inverse-level bottleneck and outcome equality.
2. Only if physics still dominates: batch frequencies per geometry and move
   LU and Graf onto the device.
