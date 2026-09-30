# Modal Müller service: clean backend and bounded qualification

2026-09-30/10-01. Implementation owner: Claude, at the user's request to
"rewrite a clean version just like the nodal kress" of the latest modal Müller
work. The source was the Chebyshev proposal (`node_free_modal_muller_summary.pdf`),
its [independent review](../node_free_modal_muller_review.md), and the review's
prototype scripts. No Git branch was created.

## What was built

`experiments/cleaned_interface/modal_muller.py` is a `PhysicsBackend` with the
same contract as `NodalKress`:

- `validate`, `resolution_profile` and `refine_resolution`;
- `evaluate` (opaque handle) and `derivative` (complete SC-035 trial);
- `ordered_calls`, `observable_frontier`, `disk_landscape` (the shared exact-Mie
  grid) and `receipt`.

Two new modules hold the numerics, organized in timed stages:

- `modal_geometry.py`: frequency-independent geometry. It builds Laurent
  arrays, the certified log|W|² series, and the T_n(R) and regular-wave bases.
- `modal_operator.py`: per-frequency physics. It holds the scalar radial
  functions, the Chebyshev degree choice, the exact-log Galerkin contraction,
  Müller assembly, Graf sources and receivers, and the Hadamard contraction.

The files are additive. `physics.py`, the tests and the other CI-001-frozen
sources are unchanged, so CI-001's `verify`, `report` and `--reuse-from` stay
valid. Selection needs `register()`, or the
`python -m experiments.cleaned_interface.modal_muller` entry point.

Review findings that the rewrite resolves:

| Review finding | Resolution in the service |
|---|---|
| `beta=0.05` is an assumption; finite Parseval is not a certificate | beta is accepted only when the complete coefficient residual r=‖1−\|W\|²v‖₁ certifies \|W\|² ≥ (1−r)/‖v‖₁; otherwise it is replaced once or the curve is refused. A regular self-crossing curve and a clockwise circle are refused in tests |
| Fixed Ku/B/degrees; no independent refinement | Tokens `8*K_trace`; production/refined raise K_trace **and** window by 32. Log degree comes from its analytic tail bound, radial degree from coefficient decay, Graf order from a rigorous \|J_l\| bound, and wave series length from its first omitted term |
| Source/receiver expansion limits | Bounding-circle refusal, explicit Graf tail bound, and refusal when the cancellation `eps*I0(|k| rho)` exceeds 1e-9 |
| Not registered; no full contract | Registered explicitly; localization, frontier, audits and the runner end-to-end test all pass through the service |

## Measurements

Evidence: [service bundle](../../../../results/validation/cleaned_interfaces/modal-muller-service-20260930/README.md).

- **Accuracy.** Every review fixture reproduces through the service, to within
  roundoff or better (C 2.5 GHz, Ku 64: 1.37e-8 field, 9.11e-8 Jacobian; DF
  endpoint 2.5 GHz, Ku 128: 1.8e-12 / 5.4e-12). Complete-trial centered
  differences agree with the prototype to three digits. The damped 2.5 GHz
  floor of about 6e-9 persists.
- **Stage replays.** `stage_2_damped`, `release_M11` and `fixed_M43` reproduce
  every trial decision, accepted index, exit and stage-only work count. The
  endpoints are within 1.3e-12 package units of the archive.
- **Timing.** On the matched 19-frequency K=192 catalog, a new geometry costs
  4.32 s on one core and 2.19 s with four threads. The prototype took 46.6 s,
  CPU Kress 13.5 s, and CUDA Kress 0.45 s.
- **Tests.** The 11 new tests pass, including an end-to-end runner test on
  nodal-generated data. They run alongside the unchanged cleaned-interface
  suite.

## Interpretation and limits

The backend is complete for the CI-001 single-curve contract. It is
numerically interchangeable with the prototype, and it agrees with nodal
Kress to the fixture-dependent refinement level. It is **not** a faster
replacement for CUDA Kress: per-frequency assembly (0.12 s at K=192) and
geometry preparation (1.4 s per curve) still run on the CPU. No inverse
campaign or real-scene localization-to-tail run has used this backend, so
reconstruction retention and runtime within the 1800 s fit budget are
unknown. A slower backend can change outcomes through time caps.

## Proposed next steps (not run)

1. One full original-start case with `solver='modal_muller'`, in a new
   prepared campaign (for example `modal__c4__development_c`), next to its
   CI-001 nodal result. This tests budget and outcome behaviour before any
   36-case campaign.
2. Speed-up in the order the receipts show:
   - batch or GPU-port the per-frequency radial combination and the seven
     window FFT products;
   - port the geometry recurrences to GPU FFTs;
   - replace the ‖v‖₁ bound by a sampled-plus-derivative sup bound, which
     lowers the log degree by about 20% without losing the certificate.
3. The 36-case campaign, only after step 1 shows the policy completes within
   budget.
